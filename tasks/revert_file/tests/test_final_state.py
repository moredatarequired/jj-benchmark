"""Verifier for the revert_file task.

WHAT CHANGED, AND WHY
=====================

The task says to modify only the current working-copy commit and to create no new
commits. The three scored tests graded that by reading two files off disk and by
reading `@`'s description -- none of which pins WHICH commit `@` is. So an agent
could run `jj new -r 'root()' -m "Restore configuration and utilities"`, write the
three files, leave the bootstrap's commits untouched beside it (the session-scoped
anchor fixture still holds, nothing having been destroyed) and collect the full
reward. Measured: reward 1.

All three now require `@` to still be the working-copy commit the BOOTSTRAP handed
over, addressed by its change id, and read the two graded files at that change
rather than only off disk. `jj restore` and `jj describe` both rewrite that commit
in place and preserve its change id, so a genuine solve is unaffected.

working_copy_or_fallback() is the reserved-key resolver -- anchor keys are
description first lines and the handover working copy is undescribed, so a
workspace NAME is the only unique key for it. When bootstrap_anchor.json is absent
(it is gitignored, and CI always builds cold) it prints that the identity claim is
NOT being made and returns the positional `@`, so every assertion degrades to
exactly its old strength.

Test names and count are unchanged, so tests/vacuity_floor.json does not move.
test_app_py_unchanged stays floored and is left exactly as it was.
"""

import os
import subprocess
import pytest

from anchor import working_copy_or_fallback

PROJECT_DIR = "/home/user/myproject"

_snapshotted = False


def snapshot_working_copy():
    """Take the ONE working-copy snapshot this verifier is allowed, explicitly.

    The graded files live in the working copy, and jj records their contents in
    `@`'s tree only when it snapshots. Every read after this one passes
    --ignore-working-copy, so the verifier cannot keep mutating what it grades. A
    snapshot preserves change ids and cannot disturb the anchor.
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
        jj("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\\n"').splitlines()
        if line
    ]


def handover_working_copy():
    """The `@` the bootstrap handed over; also asserts `@` is still that change."""
    snapshot_working_copy()
    handover = working_copy_or_fallback("@", repo=PROJECT_DIR)
    here, there = change_ids("@"), change_ids(handover)
    assert here == there, (
        f"`@` is {here}, but the working-copy commit the bootstrap handed over is "
        f"{there}. The task says to modify only the current working-copy commit "
        "and to create no new commits, so `@` has to still be that change."
    )
    return handover


def test_config_py_reverted():
    """Verify config.py matches the parent commit's state, in the graded commit."""
    handover = handover_working_copy()
    content = jj("file", "show", "-r", handover, "config.py").strip()
    assert "DEBUG = False" in content, (
        f"Expected config.py at the bootstrap's working-copy commit ({handover}) "
        f"to be 'DEBUG = False', but got: {content}"
    )

    config_path = os.path.join(PROJECT_DIR, "config.py")
    with open(config_path, "r") as f:
        on_disk = f.read().strip()
    assert "DEBUG = False" in on_disk, \
        f"Expected config.py to be 'DEBUG = False', but got: {on_disk}"

def test_utils_py_restored():
    """Verify utils.py matches the v1.0 state, in the graded commit."""
    handover = handover_working_copy()
    content = jj("file", "show", "-r", handover, "utils.py").strip()
    assert content == 'def helper(): return "v1"', (
        f"Expected utils.py at the bootstrap's working-copy commit ({handover}) to "
        f"be 'def helper(): return \"v1\"', but got: {content}"
    )

    utils_path = os.path.join(PROJECT_DIR, "utils.py")
    with open(utils_path, "r") as f:
        on_disk = f.read().strip()
    assert on_disk == 'def helper(): return "v1"', \
        f"Expected utils.py to be 'def helper(): return \"v1\"', but got: {on_disk}"

def test_app_py_unchanged():
    """Verify app.py retains the working copy changes."""
    app_path = os.path.join(PROJECT_DIR, "app.py")
    with open(app_path, "r") as f:
        content = f.read().strip()

    assert content == 'print("working copy app")', \
        f"Expected app.py to be 'print(\"working copy app\")', but got: {content}"

def test_working_copy_description():
    """Priority 1: the description of THE working copy the bootstrap handed over."""
    handover = handover_working_copy()
    description = jj("log", "-r", handover, "--no-graph", "-T", "description").strip()
    expected_description = "Restore configuration and utilities"

    assert description == expected_description, \
        f"Expected working copy description to be '{expected_description}', but got: '{description}'"
