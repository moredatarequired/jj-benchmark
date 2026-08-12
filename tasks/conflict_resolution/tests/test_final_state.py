"""Verifier for the conflict_resolution task.

WHAT CHANGED, AND WHY
=====================

Both scored tests used to name the graded commits only indirectly: one read
file.txt off disk, the other asked whether the string "feature-b" appeared in
`jj log -r "feature-a::feature-b"`. Neither pins WHICH commits were graded, so an
agent could fabricate a parallel shape from `root()`, move both bookmarks onto
it, destroy nothing -- every bootstrap change id stays visible, so the
session-scoped anchor fixture still holds -- and collect the full reward.
Measured: reward 1 with the anchor in place.

Both now resolve the graded commits by the change ids the BOOTSTRAP gave them.
A jj change id is random at creation and survives a genuine rebase, which is
exactly why it can tell "the bootstrap's Feature B, rebased" apart from "a new
commit that looks like Feature B".

The old revset also could not tell "descendant of" from "identical to", so a
squash that collapsed both graded commits onto one commit carrying both bookmarks
passed it; asking for the two anchored ids to be distinct closes that too.

change_id_or_fallback() keeps this working in CI: bootstrap_anchor.json is
gitignored and CI always builds cold, so when it is absent the resolver says the
identity claim is NOT being made and hands back the description-based revset --
the assertion is then exactly as strong as it was before.

Test names and count are unchanged, so tests/vacuity_floor.json does not move.
test_no_conflicts stays floored and is left exactly as it was.
"""

import os
import subprocess

import pytest

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/myproject"

_snapshotted = False


def snapshot_working_copy():
    """Take the ONE working-copy snapshot this verifier is allowed, explicitly.

    Resolving a conflict means editing the file; jj notices only when it
    snapshots. Every read after this one passes --ignore-working-copy so the
    verifier cannot keep mutating what it grades, and so a second run sees what
    the first one saw. A snapshot preserves change ids, so it cannot disturb the
    anchor.
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


def change_ids(revset):
    return [
        line for line in
        jj("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\n"').splitlines()
        if line
    ]


def graded(description):
    return change_id_or_fallback(
        description, f'description(substring:"{description}")', repo=PROJECT_DIR)


def test_conflict_resolved():
    snapshot_working_copy()
    feature_b = graded("Feature B")
    content = jj("file", "show", "-r", feature_b, "file.txt")
    assert "Feature A and Feature B" in content, (
        f"file.txt at the bootstrap's own 'Feature B' commit ({feature_b}) holds "
        f"{content!r}; the conflict was not resolved in that commit. A different "
        "commit holding the resolved line is not the same thing."
    )
    assert "<<<<<<<" not in content, "Conflict markers still present."

    on_disk = os.path.join(PROJECT_DIR, "file.txt")
    with open(on_disk) as fh:
        assert "Feature A and Feature B" in fh.read(), (
            f"{on_disk} does not hold the resolved line."
        )

def test_rebase_successful():
    feature_a = graded("Feature A")
    feature_b = graded("Feature B")

    expected = change_ids(feature_b)
    on_bookmark = change_ids('bookmarks(exact:"feature-b")')
    assert on_bookmark == expected, (
        f"The bookmark feature-b sits on {on_bookmark}, but the bootstrap put it "
        f"on {expected}. Rebasing preserves change ids, so the commit under "
        "feature-b must still be the bootstrap's own 'Feature B' commit -- it is "
        "not, so either the bookmark was moved onto a different commit or that "
        "commit was collapsed into another one."
    )

    reachable = change_ids(f"{feature_a}::{feature_b}")
    a_ids, b_ids = change_ids(feature_a), change_ids(feature_b)
    assert set(a_ids) <= set(reachable) and set(b_ids) <= set(reachable), (
        f"The bootstrap's 'Feature B' commit ({b_ids}) is not reachable from its "
        f"'Feature A' commit ({a_ids}), so feature-b was never rebased onto "
        "feature-a."
    )
    assert len(reachable) >= 2, (
        f"{a_ids} and {b_ids} are the same commit, so the two graded commits were "
        "collapsed into one rather than one rebased onto the other. The revset "
        "`feature-a::feature-b` cannot see that difference; this can."
    )

def test_no_conflicts():
    result = subprocess.run(["jj", "st"], cwd=PROJECT_DIR, capture_output=True, text=True)
    assert "conflict" not in result.stdout.lower(), "Repository still has conflicts."
