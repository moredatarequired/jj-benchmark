"""Verifier for abandon_commits.

The task abandons the commit the `experiment` bookmark points at (keeping the
bookmark, which then sits on that commit's parent), abandons the commit `draft`
points at (deleting the bookmark), and describes the working copy
`cleanup complete`.

WHERE THE REFERENCE VALUES COME FROM
====================================

Every assertion is phrased in the change ids the BOOTSTRAP gave its four commits,
taken from the anchor (tests/anchor.py) -- a measurement made on the host, from
the untouched image, before the agent ran. Before that, this file asked whether
some file was on disk, whether the commit `experiment` resolves to mentions
"commit A", and whether `@`'s description mentions "cleanup complete". All three
are satisfiable by a repository built from nothing beside the original one:
`jj new -r 'root()' -m 'cleanup complete'`, `echo a > a.txt; echo d > d.txt`,
`jj bookmark set experiment`. Nothing is destroyed by that, so the integrity
fixture holds; a change id is what says WHICH commits are being talked about.

`commit B` and `commit C` are named in this task's anchor_exemptions.json as
commits the asked-for work removes -- abandoning them IS the task -- so the
fixture permits their absence. Requirement 2's real content is that `commit C` is
actually gone, which is asserted here.

One deliberate snapshot before reading repository state: the bootstrap's last
command writes `d.txt` WITHOUT committing it, so `d.txt` only belongs to a commit
once jj has snapshotted the working copy. Every jj read this file used to make did
that implicitly (a plain jj command snapshots first); doing it once, explicitly,
keeps that behaviour while letting every other call pass --ignore-working-copy and
so be repeatable.

In cold CI there is no anchor file -- change ids are random per image build -- and
each assertion falls back to exactly what this file asked before, printing that no
identity claim was made.
"""

import os
import subprocess

from anchor import change_id_or_fallback, working_copy_or_fallback

PROJECT_DIR = "/home/user/myproject"

# The bootstrap's four commits: root() <- A (feature-a) <- B (experiment)
# <- C (draft) <- D (the working copy).
RETAINED_BOOKMARK_TARGET = "commit A"  # `experiment` must end up here
DELETED_COMMIT = "commit C"            # `draft` points here at handover

# Marker asking the resolvers for "nothing", so a test can tell the anchored path
# from the fallback path. It never reaches jj.
NO_ANCHOR = ""

_SNAPSHOTTED = []


def snapshot_once():
    """Let jj record the working copy exactly once per run. See the module docstring."""
    if not _SNAPSHOTTED:
        _SNAPSHOTTED.append(
            subprocess.run(["jj", "status"], cwd=PROJECT_DIR,
                           capture_output=True, text=True)
        )
    return _SNAPSHOTTED[0]


def run_jj_cmd(args):
    """A read-only jj call. Returns the CompletedProcess; the caller checks it."""
    snapshot_once()
    return subprocess.run(
        ["jj", "--ignore-working-copy"] + args,
        cwd=PROJECT_DIR, capture_output=True, text=True,
    )


def jj(*args):
    result = run_jj_cmd(list(args))
    assert result.returncode == 0, (
        f"`jj {' '.join(args)}` failed ({result.returncode}): {result.stderr.strip()}"
    )
    return result.stdout


def anchored_change(description):
    """The bootstrap's change id for `description`, or "" if there is no anchor."""
    return change_id_or_fallback(description, NO_ANCHOR, repo=PROJECT_DIR)


def anchored_working_copy():
    """The change id of the `@` the bootstrap handed over, or "" if no anchor."""
    return working_copy_or_fallback(NO_ANCHOR, repo=PROJECT_DIR)


def change_id_at(revset):
    """The change id of the single commit `revset` names."""
    found = jj("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\\n"').split()
    assert len(found) == 1, (
        f"Expected revset {revset!r} to name exactly one commit, got {found}"
    )
    return found[0]


def test_files_in_working_copy():
    """The files on disk, and the files the graded commit actually tracks."""
    assert os.path.isfile(os.path.join(PROJECT_DIR, "a.txt")), "a.txt should exist."
    assert os.path.isfile(os.path.join(PROJECT_DIR, "d.txt")), "d.txt should exist."
    assert not os.path.isfile(os.path.join(PROJECT_DIR, "b.txt")), "b.txt should be removed."
    assert not os.path.isfile(os.path.join(PROJECT_DIR, "c.txt")), "c.txt should be removed."

    # ...and the same question asked of the bootstrap's own last commit, which is
    # what abandoning B and C rebases onto A. Files on disk say nothing about
    # which repository they belong to.
    change = anchored_working_copy()
    tracked = sorted(
        path for path in jj("file", "list", "-r", change or "@").splitlines() if path
    )
    assert tracked == ["a.txt", "d.txt"], (
        f"The commit being graded ({(change or '@')[:12]}) should track a.txt and "
        f"d.txt and nothing else, but it tracks {tracked}: abandoning `commit B` "
        "and `commit C` must take b.txt and c.txt with them."
    )


def test_experiment_bookmark_retained():
    """`experiment` must still exist, on the abandoned commit's parent.

    With an anchor, the bookmark's target is compared by change id against the
    bootstrap's own `commit A`: "the commit it points at mentions commit A" is a
    claim about text, and `jj describe` can write that text onto anything.
    """
    expected = anchored_change(RETAINED_BOOKMARK_TARGET)
    if not expected:
        res = run_jj_cmd(["log", "-r", "experiment", "-T", "description"])
        assert res.returncode == 0, "Bookmark 'experiment' should exist."
        assert RETAINED_BOOKMARK_TARGET in res.stdout, (
            f"Bookmark 'experiment' should point to {RETAINED_BOOKMARK_TARGET!r}."
        )
        return

    res = run_jj_cmd(["log", "-r", 'bookmarks(exact:"experiment")', "--no-graph",
                      "-T", 'change_id ++ "\\n"'])
    assert res.returncode == 0, "Bookmark 'experiment' should exist."
    found = res.stdout.split()
    assert found == [expected], (
        f"Bookmark 'experiment' points at {[c[:12] for c in found]}, expected the "
        f"bootstrap's {RETAINED_BOOKMARK_TARGET!r} ({expected[:12]}) -- the parent "
        "of the commit it pointed at before, which requirement 1 abandons."
    )


def test_draft_bookmark_deleted():
    """`draft` is gone -- and so is the commit it pointed at.

    The bookmark's absence on its own is satisfied by deleting a bookmark and
    doing nothing else. Requirement 2 is that the commit is abandoned, which is a
    statement about the bootstrap's `commit C` and is checked as one. That commit
    is named in tests/anchor_exemptions.json for exactly this reason: its removal
    is the asked-for work.
    """
    res = run_jj_cmd(["log", "-r", "draft"])
    assert res.returncode != 0, "Bookmark 'draft' should be deleted and not resolvable."

    change = anchored_change(DELETED_COMMIT)
    revset = (f"present({change})" if change
              else f'description(substring:"{DELETED_COMMIT}")')
    still_here = jj("log", "-r", revset, "--no-graph",
                    "-T", 'change_id ++ " " ++ description.first_line() ++ "\\n"')
    assert not still_here.strip(), (
        f"The commit the bootstrap described {DELETED_COMMIT!r} is still visible "
        f"({still_here.strip()}); requirement 2 abandons it."
    )


def test_working_copy_description():
    """The working copy is the bootstrap's own last commit, described `cleanup complete`."""
    change = anchored_working_copy()
    res = run_jj_cmd(["log", "-r", change or "@", "-T", "description"])
    assert res.returncode == 0
    assert "cleanup complete" in res.stdout, (
        f"The commit being graded ({(change or '@')[:12]}) is described "
        f"{res.stdout.strip()!r}; requirement 3 sets its description to "
        "'cleanup complete'."
    )

    if change:
        current = change_id_at("@")
        assert current == change, (
            f"The working copy is change {current[:12]}, but the commit the "
            f"bootstrap left checked out is {change[:12]}. Requirement 3 describes "
            "the CURRENT working-copy commit, so those have to be the same commit."
        )
