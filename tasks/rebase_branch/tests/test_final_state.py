import os
import subprocess
import pytest

PROJECT_DIR = "/home/user/repo"


def _jj(*args):
    """Run jj in the task repository and return the CompletedProcess."""
    return subprocess.run(
        ["jj", *args], capture_output=True, text=True, cwd=PROJECT_DIR
    )


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
    nothing here depends on jj's human-readable prose.
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


def test_conflict_resolved_content():
    """Priority 1: Use jj CLI to check the content of data.txt in feature-branch."""
    result = subprocess.run(
        ["jj", "file", "show", "data.txt", "-r", "feature-branch"],
        capture_output=True, text=True, cwd=PROJECT_DIR
    )
    assert result.returncode == 0, f"'jj file show' failed: {result.stderr}"

    expected_content = "Line from main\nLine from feature\n"
    assert result.stdout == expected_content, f"Expected data.txt to contain exactly '{expected_content}', got '{result.stdout}'"


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
