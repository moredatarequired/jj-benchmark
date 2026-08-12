"""Verifier for the edit_commit_message task.

WHAT CHANGED, AND WHY
=====================

The three scored tests graded a description found via `files("b.txt")`, `@`'s own
description, and d.txt read off disk. None of them pinned WHICH commits were being
graded, so `jj new -r 'root()'` + rebuilding an A/B/C/D chain satisfied all three
-- `files("b.txt")` then matched two commits and the substring check passed on the
fabricated one -- while destroying nothing, so the session-scoped anchor fixture
held. Measured: reward 1.

Now:

  * the renamed commit is addressed by the change id the BOOTSTRAP gave its
    "Add file B" commit. `jj describe` preserves change ids, which is exactly why
    a rename is checkable this way and a description is not.
  * the new "Add file D" commit is created BY THE AGENT, so it has no bootstrap
    change id of its own. It is anchored by RELATION instead: the task says to
    create it "on top of the current working copy", so its parent must be the
    bootstrap's own "Add file C" commit.
  * d.txt is still read off disk -- that is what the test is for -- but only after
    the same parent claim, so the tree it is read from has to descend from the
    bootstrap's stack.

change_id_or_fallback() keeps all of this working in CI, where bootstrap_anchor.json
is absent (it is gitignored and CI always builds cold): it prints that the identity
claim is NOT being made and returns the revset each test used before.

Test names and count are unchanged, so tests/vacuity_floor.json does not move.
test_commit_c_still_exists stays floored and is left exactly as it was.
"""

import os
import subprocess
import pytest

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/repo"

_snapshotted = False


def snapshot_working_copy():
    """Take the ONE working-copy snapshot this verifier is allowed, explicitly.

    d.txt is written into the working copy, and jj records it in `@`'s tree only
    when it snapshots. Every read after this one passes --ignore-working-copy so
    the verifier does not keep mutating what it grades. A snapshot preserves change
    ids and cannot disturb the anchor.
    """
    global _snapshotted
    if not _snapshotted:
        subprocess.run(["jj", "status"], cwd=PROJECT_DIR,
                       capture_output=True, text=True)
        _snapshotted = True


def jj(*args):
    proc = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        capture_output=True, text=True, cwd=PROJECT_DIR,
    )
    assert proc.returncode == 0, (
        f"`jj {' '.join(args)}` failed ({proc.returncode}): {proc.stderr.strip()}"
    )
    return proc.stdout


def change_ids(revset):
    return [
        line for line in
        jj("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\\n"').splitlines()
        if line
    ]


def assert_new_commit_sits_on_the_handover_tip():
    """`@`'s parent must be the bootstrap's own "Add file C" commit.

    The "Add file D" commit is created by the agent, so there is no bootstrap
    change id for it. What the task fixes is its POSITION -- "on top of the current
    working copy" -- and the handover working copy is the commit the bootstrap
    described "Add file C". That is an anchored claim a stack fabricated from
    `root()` cannot satisfy.
    """
    snapshot_working_copy()
    tip = change_id_or_fallback(
        "Add file C", 'description(substring:"Add file C")', repo=PROJECT_DIR)
    parents = jj("log", "-r", "@", "--no-graph", "-T",
                 'parents.map(|p| p.change_id()).join(" ") ++ "\\n"').split()
    expected = change_ids(tip)
    assert parents == expected, (
        f"`@` sits on parent change id(s) {parents}, but the new commit has to be "
        f"created on top of the working copy the bootstrap handed over, which is "
        f"its 'Add file C' commit {expected}."
    )


def test_commit_b_description_updated():
    """Priority 1: the description of the commit the BOOTSTRAP described 'Add file B'."""
    commit_b = change_id_or_fallback(
        "Add file B", 'files("b.txt")', repo=PROJECT_DIR)
    out = jj("log", "-r", commit_b, "--no-graph", "-T", "description")
    assert "Add second file" in out, (
        f"Expected description 'Add second file' on the bootstrap's own "
        f"'Add file B' commit ({commit_b}), got: {out}"
    )

def test_working_copy_description_updated():
    """Priority 1: the working copy is the new commit, and it sits in the right place."""
    assert_new_commit_sits_on_the_handover_tip()
    out = jj("log", "-r", "@", "--no-graph", "-T", "description")
    assert "Add file D" in out, \
        f"Expected description 'Add file D' for working copy, got: {out}"

def test_d_txt_exists_and_content():
    """Priority 3 fallback: basic file existence and content check.

    The content is read off disk, which is the point of the test; what the anchor
    adds is that the commit holding it descends from the bootstrap's own stack.
    """
    assert_new_commit_sits_on_the_handover_tip()
    d_txt_path = os.path.join(PROJECT_DIR, "d.txt")
    assert os.path.isfile(d_txt_path), f"d.txt not found at {d_txt_path}"
    with open(d_txt_path, "r") as f:
        content = f.read().strip()
    assert content == "d", f"Expected content 'd' in d.txt, got: '{content}'"

def test_commit_c_still_exists():
    """Priority 1: Use jj CLI to verify the commit with c.txt still exists and has correct description."""
    result = subprocess.run(
        ["jj", "log", "-r", "files(\"c.txt\")", "--no-graph", "-T", "description"],
        capture_output=True, text=True, cwd=PROJECT_DIR
    )
    assert result.returncode == 0, f"'jj log' failed: {result.stderr}"
    assert "Add file C" in result.stdout, \
        f"Expected description 'Add file C' for commit with c.txt, got: {result.stdout}"
