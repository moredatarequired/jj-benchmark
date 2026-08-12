"""Renaming a bookmark must leave it on the same commit.

The assertion used to be two substring searches over `jj bookmark list`: the name
`new-feature` appears and the name `old-feature` does not. Nothing said which
commit the new name is on, so an agent could put `new-feature` on a commit it
built itself and delete `old-feature`, which is not a rename at all. Built
additively -- a fresh commit from `root()`, nothing removed -- that also leaves
every anchored change id visible, so the bootstrap anchor holds and the verifier
grades the fabricated commit (measured: reward 1).

A rename changes a name, not a target. So the check is: the bookmark
`new-feature` points at the SAME commit `old-feature` pointed at when the task
was handed over, addressed by the change id the anchor recorded before the agent
ran (tests/anchor.py; the bootstrap's only commit is its undescribed working
copy, which is why it is named through the anchor's reserved per-workspace key
rather than by description).
"""

import os
import subprocess

from anchor import working_copy_or_fallback

PROJECT_DIR = "/home/user/myproject"

# The revset the bootstrap's bookmarked commit is resolved by when the anchor
# cannot supply its change id -- CI always builds cold, and so does any sweep run
# without `scripts/bootstrap_anchor.py --write`. Falling back to the bookmark
# itself is deliberately circular: it collapses the assertion into exactly what
# it said before the anchor existed ("a bookmark called new-feature exists"), so
# no verdict changes and the identity claim is simply dropped.
# working_copy_or_fallback() prints a line recording that.
WC_FALLBACK = 'bookmarks(exact:"new-feature")'


def jj(*args):
    """A read-only jj call. --ignore-working-copy on every one, without exception."""
    result = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=PROJECT_DIR, capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"`jj {' '.join(args)}` failed in {PROJECT_DIR} ({result.returncode}): "
        f"{result.stderr.strip()}"
    )
    return result.stdout


def change_ids(revset):
    return [
        line for line in
        jj("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\n"').splitlines()
        if line
    ]


def test_bookmark_renamed():
    result = subprocess.run(
        ["jj", "--ignore-working-copy", "bookmark", "list"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True
    )
    assert "new-feature" in result.stdout, "Expected bookmark 'new-feature' to exist after renaming."
    assert "old-feature" not in result.stdout, "Expected bookmark 'old-feature' to no longer exist after renaming."

    revset = working_copy_or_fallback(WC_FALLBACK, workspace="default",
                                     repo=PROJECT_DIR)
    wanted = change_ids(revset)
    assert len(wanted) == 1, (
        f"{revset!r} resolves to {len(wanted)} commit(s) in {PROJECT_DIR}: "
        f"{wanted}. The bookmark this task renames was on exactly one commit."
    )

    on_new = change_ids('bookmarks(exact:"new-feature")')
    assert on_new == wanted, (
        f"`new-feature` points at {[c[:12] for c in on_new]}, but the commit "
        f"`old-feature` was on when this task was handed over is "
        f"{wanted[0][:12]}. Renaming a bookmark moves the NAME and leaves the "
        "commit alone; a `new-feature` on some other commit means the bookmark "
        "was recreated somewhere else rather than renamed."
    )

    assert change_ids('bookmarks(exact:"old-feature")') == [], (
        "A bookmark named `old-feature` still points at a commit."
    )
