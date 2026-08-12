"""Verifier for the restore_specific_revision task.

WHAT CHANGED, AND WHY
=====================

The task is "restore config.txt in the WORKING COPY to its content in `@-`,
without creating a commit". The previous version graded that by reading
/home/user/repo/config.txt off disk, which asks only "is there a file with the
right bytes somewhere". An agent could satisfy it while never touching the
commit the task handed over: build a fabricated chain from `root()`, leave the
bootstrap's commits untouched beside it (so the session-scoped anchor fixture
still holds -- nothing is destroyed) and park the working copy on the
fabrication. Measured: reward 1.

So test_config_restored now names the graded commit by the change id the
BOOTSTRAP gave the working copy, and asserts both that `@` is still THAT commit
and that config.txt reads `version=2` in it.

working_copy_or_fallback() is the reserved-key resolver: anchor keys are
description first lines and this bootstrap leaves the working copy undescribed,
so a workspace NAME is the only unique key for it. When bootstrap_anchor.json is
absent -- it is gitignored and CI always builds cold -- the resolver prints that
the identity claim is NOT being made and returns the positional `@` this test
used before, so the assertion degrades to exactly its old strength.

Test names and count are unchanged, so tests/vacuity_floor.json does not move.
test_jj_repo_intact stays floored and is left exactly as it was.
"""

import os
import subprocess

import pytest

from anchor import working_copy_or_fallback

PROJECT_DIR = "/home/user/repo"

_snapshotted = False


def snapshot_working_copy():
    """Take the ONE working-copy snapshot this verifier is allowed, explicitly.

    Every other jj call here passes --ignore-working-copy so the verifier cannot
    mutate what it is grading. But the asked-for work is a change to a FILE in
    the working copy, and jj records that in `@`'s tree only when it snapshots --
    so a solve that wrote the file and then ran no further jj command would leave
    `@`'s stored tree stale and a --ignore-working-copy read would grade the
    wrong bytes. The verifier therefore snapshots once, deliberately, and reads
    everything afterwards with --ignore-working-copy. This is the same single
    snapshot the previous version of this file took implicitly on its first plain
    jj call, and it preserves change ids, so it cannot disturb the anchor.
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


def test_config_restored():
    snapshot_working_copy()
    handover = working_copy_or_fallback("@", repo=PROJECT_DIR)

    here, there = change_ids("@"), change_ids(handover)
    assert here == there, (
        f"`@` is {here}, but the working-copy commit the bootstrap handed over is "
        f"{there}. The task says to update the working copy in place and to "
        "create no new commit, so `@` has to still be that change. Building a "
        "fresh commit that holds the right bytes is not the same thing."
    )

    content = jj("file", "show", "-r", handover, "config.txt").strip()
    assert content == "version=2", (
        f"config.txt in the bootstrap's working-copy commit ({handover}) holds "
        f"{content!r}; it must be restored to the parent revision's "
        "'version=2'."
    )

    config_path = os.path.join(PROJECT_DIR, "config.txt")
    assert os.path.isfile(config_path), f"Config file {config_path} does not exist."
    with open(config_path) as f:
        on_disk = f.read().strip()
    assert on_disk == "version=2", (
        f"Expected config.txt to be restored to 'version=2', but got '{on_disk}'."
    )

def test_jj_repo_intact():
    # Verify it's still a valid jj repo by running a simple command
    result = subprocess.run(["jj", "log", "-n", "1"], cwd=PROJECT_DIR, capture_output=True, text=True)
    assert result.returncode == 0, f"jj command failed, repository might be corrupted: {result.stderr}"
