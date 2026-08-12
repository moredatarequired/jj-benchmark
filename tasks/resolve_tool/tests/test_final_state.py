"""Verifier for the resolve_tool task.

WHAT CHANGED, AND WHY
=====================

All three tests used to grade files read off disk plus jj's English in
`jj status`. Writing "side 1" and "side 2" into two files anywhere satisfies
that, so an agent could fabricate a commit from `root()`, put the two files in
it, leave the bootstrap's conflicted merge untouched beside it -- so the
session-scoped anchor fixture still holds, nothing having been destroyed -- and
collect the full reward. Measured: reward 1.

All three now address the graded commit by the change id the BOOTSTRAP gave the
conflicted merge, and ask jj's own `conflict` keyword about it rather than
grepping prose. `jj resolve` rewrites that commit and preserves its change id, so
a genuine solve is unaffected.

change_id_or_fallback() keeps this working in CI, where bootstrap_anchor.json is
absent (it is gitignored and CI always builds cold): the resolver then prints that
the identity claim is NOT being made and returns the description-based revset.

test_no_unresolved_conflicts also loses a tautology it used to carry --
`"file1.txt" not in out or "file1.txt" in out`, which is true of every string.

Test names and count are unchanged, so tests/vacuity_floor.json does not move.
"""

import os
import subprocess
import pytest

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/myproject"

# The description the bootstrap gave the conflicted merge commit. Used as an
# ANCHOR KEY -- the commit is addressed by its change id, not by this text.
MERGE = "merge"

_snapshotted = False


def snapshot_working_copy():
    """Take the ONE working-copy snapshot this verifier is allowed, explicitly.

    A conflict can also be resolved by simply editing the files, which jj only
    notices when it snapshots. Every read after this one passes
    --ignore-working-copy so the verifier cannot keep mutating what it grades and
    so a second run sees what the first one saw. A snapshot preserves change ids
    and therefore cannot disturb the anchor.
    """
    global _snapshotted
    if not _snapshotted:
        subprocess.run(["jj", "status"], cwd=PROJECT_DIR,
                       capture_output=True, text=True)
        _snapshotted = True


def jj(*args):
    proc = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=PROJECT_DIR, capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"`jj {' '.join(args)}` failed ({proc.returncode}): {proc.stderr.strip()}"
    )
    return proc.stdout


def graded_merge():
    return change_id_or_fallback(
        MERGE, f'description(substring:"{MERGE}")', repo=PROJECT_DIR)


def resolved_content(path, expected):
    """`path` must read `expected` in the bootstrap's own merge commit, and on disk."""
    snapshot_working_copy()
    merge = graded_merge()
    content = jj("file", "show", "-r", merge, path).strip()
    assert content == expected, (
        f"Expected {path} to have content '{expected}' in the bootstrap's own "
        f"merge commit ({merge}), got: {content}. Writing the right bytes into "
        "some other commit, or only onto disk, does not resolve the conflict the "
        "task handed over."
    )
    with open(os.path.join(PROJECT_DIR, path)) as f:
        on_disk = f.read().strip()
    assert on_disk == expected, (
        f"Expected {path} to have content '{expected}' on disk, got: {on_disk}"
    )


def test_no_unresolved_conflicts():
    snapshot_working_copy()
    merge = graded_merge()
    conflicted = jj("log", "-r", merge, "--no-graph",
                    "-T", 'conflict ++ "\\n"').split()
    assert conflicted == ["false"], (
        f"jj still reports the bootstrap's own merge commit ({merge}) as "
        f"conflicted (conflict={conflicted}). Expected no unresolved conflicts in "
        "that commit -- which is the commit the task asked to be resolved."
    )

def test_file1_resolved_with_ours():
    resolved_content("file1.txt", "side 1")

def test_file2_resolved_with_theirs():
    resolved_content("file2.txt", "side 2")
