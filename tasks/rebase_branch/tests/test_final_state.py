"""Verifier for rebase_branch.

The task rebases `feature-branch`'s two commits onto `main` and resolves the
conflict in data.txt so it holds the line from main followed by the line from
feature.

WHERE THE REFERENCE VALUES COME FROM
====================================

`main`, and the two commits in the rebased stack, are pinned to the change ids the
BOOTSTRAP gave them (tests/anchor.py: captured on the host, from the untouched
image, before the agent ran). Before that, everything here was phrased in terms of
the bookmarks and of ancestry between them -- and a bookmark is a pointer the agent
can move. Measured shape of the fabrication: build base -> main' -> f1 -> f2 from
`root()`, move both bookmarks onto it, write the resolved data.txt into the
fabricated f1. Every ancestry assertion holds of the fabricated stack, nothing is
destroyed (so the integrity fixture in conftest.py holds), and both scored tests
pass.

Change ids are what a rebase preserves and a rebuild cannot reproduce, so
"feature-branch's two commits now sit on main" is stated as: `main` is the
bootstrap's `main commit`, and `main..feature-branch` is exactly the bootstrap's
`feature commit 2` and `feature commit 1`.

The bootstrap's empty `@` is named in this task's anchor_exemptions.json: the
solve has to `jj edit` the conflicted commit, and jj auto-abandons the empty
working copy on the way.

In cold CI there is no anchor file -- change ids are random per image build -- and
every check falls back to what this file asserted before, printing that no
identity claim was made.
"""

import os
import subprocess

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/repo"

MAIN_COMMIT = "main commit"
FEATURE_1 = "feature commit 1"
FEATURE_2 = "feature commit 2"

# Marker asking the resolver for "nothing", so a caller can tell the anchored path
# from the fallback path. It never reaches jj.
NO_ANCHOR = ""

_SNAPSHOTTED = []


def snapshot_once():
    """One deliberate working-copy snapshot per run, then read-only calls only.

    Every jj call this file used to make snapshotted implicitly; doing it once
    keeps that behaviour -- an agent that resolves the conflict by writing the file
    and leaving it uncommitted is still graded the way it was -- while making the
    reads repeatable.
    """
    if not _SNAPSHOTTED:
        _SNAPSHOTTED.append(subprocess.run(
            ["jj", "status"], cwd=PROJECT_DIR, capture_output=True, text=True))
    return _SNAPSHOTTED[0]


def _jj(*args):
    """Run jj in the task repository and return the CompletedProcess."""
    snapshot_once()
    return subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        capture_output=True, text=True, cwd=PROJECT_DIR,
    )


def anchored(description):
    return change_id_or_fallback(description, NO_ANCHOR, repo=PROJECT_DIR)


def _commit_ids(revset):
    """Full commit ids for `revset`, newest first.

    --no-graph plus an explicit template is the only shape of `jj log` that is
    safe to parse: the default graph output wraps lines and elides commits, so
    grepping it silently under- or over-counts. A bare newline is whitespace in
    jj's template language, so the separator has to be an explicit "\\n" string
    concatenated onto the value or the ids run together.
    """
    result = _jj("log", "-r", revset, "--no-graph", "-T", 'commit_id ++ "\\n"')
    assert result.returncode == 0, f"'jj log -r {revset}' failed: {result.stderr}"
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _change_ids(revset):
    """Full change ids for `revset`, newest first."""
    result = _jj("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\\n"')
    assert result.returncode == 0, f"'jj log -r {revset}' failed: {result.stderr}"
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _one_commit_id(revset):
    ids = _commit_ids(revset)
    assert len(ids) == 1, f"Expected revset '{revset}' to name exactly 1 commit, got {ids}"
    return ids[0]


def _parent_ids(revset):
    """Commit ids of the parents of the single commit named by `revset`."""
    result = _jj(
        "log", "-r", revset, "--no-graph",
        "-T", 'parents.map(|p| p.commit_id()).join(" ") ++ "\\n"',
    )
    assert result.returncode == 0, f"'jj log -r {revset}' failed: {result.stderr}"
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1, f"Expected revset '{revset}' to name exactly 1 commit, got {lines}"
    return lines[0].split()


def test_feature_branch_rebased_onto_main():
    """Priority 1: feature-branch's commits must now sit on top of main.

    The old version of this test only counted the commits in
    `main..feature-branch` and asserted the count was 2. That count is 2 before
    the rebase as well -- the two feature commits are outside main's ancestry
    whether they hang off `base` or off `main` -- so the headline assertion of
    this task passed on the untouched image and measured nothing. Writing the
    resolved two-line data.txt into the un-rebased commit scored 1.

    What actually distinguishes the rebased state is ancestry: `main` must be
    an ancestor of `feature-branch`, and the root of the stack must have `main`
    as its parent. Both are structural (commit ids from explicit revsets), so
    nothing here depends on jj's human-readable prose. WHICH commits they are
    comes from the anchor, because a bookmark is a pointer the agent can move
    and ancestry between two moved pointers says nothing about identity.
    """
    main_id = _one_commit_id("main")
    feature_id = _one_commit_id("feature-branch")

    # Ancestry: this is the assertion the old test was missing entirely.
    assert _commit_ids("main & ::feature-branch") == [main_id], (
        f"main ({main_id}) is not an ancestor of feature-branch ({feature_id}): "
        "feature-branch has not been rebased onto main."
    )

    # The rebased stack is still the two feature commits -- not squashed away,
    # not partially left behind on the old base.
    stack = _commit_ids("main..feature-branch")
    assert len(stack) == 2, (
        f"Expected exactly 2 commits in main..feature-branch, got {len(stack)}: {stack}"
    )

    # feature-branch must point at the head of that stack.
    assert feature_id == stack[0], (
        f"feature-branch ({feature_id}) is not the head of the rebased stack {stack}."
    )

    # The stack must be a linear chain planted directly on main:
    # main <- root <- feature-branch.
    root_id = _one_commit_id("roots(main..feature-branch)")
    assert _parent_ids("roots(main..feature-branch)") == [main_id], (
        f"The first commit of the stack ({root_id}) has parents "
        f"{_parent_ids('roots(main..feature-branch)')}, expected main ({main_id})."
    )
    assert _parent_ids("feature-branch") == [root_id], (
        f"feature-branch ({feature_id}) has parents {_parent_ids('feature-branch')}, "
        f"expected the stack root ({root_id}); the rebased commits are not a linear chain."
    )

    # ...and they are the bootstrap's own commits, not a stack that looks like
    # them with the bookmarks moved onto it.
    wanted = {d: anchored(d) for d in (MAIN_COMMIT, FEATURE_2, FEATURE_1)}
    if all(wanted.values()):
        assert _change_ids("main") == [wanted[MAIN_COMMIT]], (
            f"`main` points at change {_change_ids('main')}, expected the "
            f"bootstrap's {MAIN_COMMIT!r} ({wanted[MAIN_COMMIT][:12]})."
        )
        assert _change_ids("main..feature-branch") == [wanted[FEATURE_2],
                                                      wanted[FEATURE_1]], (
            "The two commits between main and feature-branch are changes "
            f"{[c[:12] for c in _change_ids('main..feature-branch')]}, expected "
            f"the bootstrap's {FEATURE_2!r} ({wanted[FEATURE_2][:12]}) then "
            f"{FEATURE_1!r} ({wanted[FEATURE_1][:12]}). Rebasing preserves change "
            "ids, so these are the commits the task asked to be rebased."
        )


def test_conflict_resolved_content():
    """Priority 1: Use jj CLI to check the content of data.txt in feature-branch."""
    expected_content = "Line from main\nLine from feature\n"

    # Read at the bootstrap's own `feature commit 2`, which is what
    # `feature-branch` has to point at, rather than at the bookmark itself.
    head = anchored(FEATURE_2) or "feature-branch"
    result = _jj("file", "show", "data.txt", "-r", head)
    assert result.returncode == 0, f"'jj file show' failed: {result.stderr}"
    assert result.stdout == expected_content, (
        f"Expected data.txt at the head of the rebased stack ({head[:12]}) to "
        f"contain exactly '{expected_content}', got '{result.stdout}'"
    )


def test_no_unresolved_conflicts():
    """Priority 1: no commit in the rebased stack may still be conflicted.

    `jj resolve --list` only reports the working copy's conflicts and leans on
    an English error string when there are none, so this asks the template
    engine instead: the `conflict` keyword is a boolean on every commit.
    """
    result = _jj(
        "log", "-r", "feature-branch | main..feature-branch", "--no-graph",
        "-T", 'commit_id ++ " " ++ conflict ++ "\\n"',
    )
    assert result.returncode == 0, f"'jj log' failed: {result.stderr}"
    conflicted = [
        line.split()[0]
        for line in result.stdout.splitlines()
        if line.strip().endswith("true")
    ]
    assert not conflicted, f"These commits still contain unresolved conflicts: {conflicted}"
