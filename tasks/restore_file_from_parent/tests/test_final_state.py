"""Verifier for the restore_file_from_parent task.

WHAT CHANGED, AND WHY
=====================

The two scored tests graded config.txt read off disk and the output of a bare
`jj diff`, i.e. whatever `@` happened to be. Neither pins WHICH commit was graded,
so an agent could rebuild the two-commit shape from `root()` with config.txt
already matching its parent, leave the bootstrap's commits untouched beside it --
the session-scoped anchor fixture still holds, nothing having been destroyed --
and pass. Measured: reward 1.

Both now address the working-copy commit the BOOTSTRAP handed over by the change
id it was created with. `jj restore` rewrites that commit in place and preserves
its change id, so a genuine solve is unaffected.

working_copy_or_fallback() is the reserved-key resolver, and this bootstrap is
exactly why it exists: BOTH of its commits are undescribed, so
`anchored_change_id("")` cannot name one of them and a workspace NAME is the only
unique key. With no bootstrap_anchor.json -- it is gitignored, and CI always builds
cold -- it prints that the identity claim is NOT being made and returns the
positional `@`, so both assertions degrade to exactly their old strength.

Test names and count are unchanged, so tests/vacuity_floor.json does not move.
test_app_not_restored stays floored and is left exactly as it was.
"""

import os
import subprocess
import pytest

from anchor import working_copy_or_fallback

PROJECT_DIR = "/home/user/myproject"

_snapshotted = False


def snapshot_working_copy():
    """Take the ONE working-copy snapshot this verifier is allowed, explicitly.

    Everything graded here is working-copy content, and jj records that in `@`'s
    tree only when it snapshots -- the bootstrap deliberately leaves both files
    modified but unsnapshotted. Every read after this one passes
    --ignore-working-copy so the verifier does not keep mutating what it grades. A
    snapshot preserves change ids and cannot disturb the anchor; it is the same
    single snapshot this file used to take implicitly on its `jj diff` call.
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
    """The `@` the bootstrap handed over; asserts `@` is still that change."""
    snapshot_working_copy()
    handover = working_copy_or_fallback("@", repo=PROJECT_DIR)
    here, there = change_ids("@"), change_ids(handover)
    assert here == there, (
        f"`@` is {here}, but the working-copy commit the bootstrap handed over is "
        f"{there}. The task is to discard one file's uncommitted change in THAT "
        "working copy; a fresh commit that happens to hold the right files is not "
        "the same thing."
    )
    return handover


def test_config_restored():
    handover = handover_working_copy()
    content = jj("file", "show", "-r", handover, "config.txt")
    assert "port=8080" in content, (
        f"config.txt at the bootstrap's own working-copy commit ({handover}) holds "
        f"{content!r}; it was not restored to the parent commit's state."
    )

    config_path = os.path.join(PROJECT_DIR, "config.txt")
    with open(config_path) as f:
        on_disk = f.read()
    assert "port=8080" in on_disk, "config.txt was not restored to the parent commit's state."

def test_app_not_restored():
    app_path = os.path.join(PROJECT_DIR, "app.py")
    with open(app_path) as f:
        content = f.read()
    assert "Hello World - v2" in content, "app.py was incorrectly modified or restored."

def test_jj_diff():
    handover = handover_working_copy()
    changed = {
        line for line in
        jj("diff", "-r", handover, "--name-only").splitlines() if line
    }
    assert "config.txt" not in changed, (
        f"config.txt still shows changes in the bootstrap's own working-copy commit "
        f"({handover}); its diff touches {sorted(changed)}."
    )
    assert "app.py" in changed, (
        f"app.py does not show changes in the bootstrap's own working-copy commit "
        f"({handover}); its diff touches {sorted(changed)}. The modification to "
        "app.py had to be kept."
    )
