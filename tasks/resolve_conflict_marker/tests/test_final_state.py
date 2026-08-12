"""Verifier for the resolve_conflict_marker task.

WHAT CHANGED, AND WHY
=====================

Both tests used to grade a file read off disk plus the absence of jj's English
"unresolved conflicts". Neither pins WHICH commit was resolved, so an agent could
rebuild the whole base/A/B shape from `root()` with an unconflicted tip, leave the
bootstrap's conflicted merge untouched beside it -- the session-scoped anchor
fixture still holds, nothing having been destroyed -- and pass both. Measured:
reward 1.

Both now address the working-copy commit the BOOTSTRAP handed over by the change
id it was created with, read file.txt at that change, and ask jj's own `conflict`
keyword about it instead of grepping prose. Resolving a conflict rewrites that
commit in place and preserves its change id, so a genuine solve is unaffected --
and the task explicitly forbids creating new commits, which is the same claim
stated the other way round.

working_copy_or_fallback() is the reserved-key resolver: anchor keys are
description first lines and the conflicted merge is undescribed, so the workspace
NAME is the only unique key for it. With no bootstrap_anchor.json -- it is
gitignored and CI always builds cold -- it prints that the identity claim is NOT
being made and returns the positional `@`.

Test names and count are unchanged, so tests/vacuity_floor.json does not move.
"""

import os
import subprocess
import pytest

from anchor import working_copy_or_fallback

PROJECT_DIR = "/home/user/myproject"

EXPECTED_CONTENT = "A and B\n"

_snapshotted = False


def snapshot_working_copy():
    """Take the ONE working-copy snapshot this verifier is allowed, explicitly.

    This task is solved by editing the file; jj recognises the resolution only when
    it snapshots, which is exactly what the instruction describes. Every read after
    this one passes --ignore-working-copy, so the verifier does not keep mutating
    the repository it is grading and a second run sees what the first one saw. A
    snapshot preserves change ids and so cannot disturb the anchor; it is also the
    same single snapshot this file used to take implicitly on its `jj status` call.
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
    """The conflicted `@` the bootstrap handed over; asserts `@` is still it."""
    snapshot_working_copy()
    handover = working_copy_or_fallback("@", repo=PROJECT_DIR)
    here, there = change_ids("@"), change_ids(handover)
    assert here == there, (
        f"`@` is {here}, but the conflicted working-copy commit the bootstrap "
        f"handed over is {there}. The task says to resolve the conflict in the "
        "current working copy and to create no new commits, so `@` has to still be "
        "that change."
    )
    return handover


def test_file_txt_content():
    handover = handover_working_copy()
    content = jj("file", "show", "-r", handover, "file.txt")
    assert content == EXPECTED_CONTENT, (
        f"Expected file.txt at the bootstrap's own conflicted commit ({handover}) "
        f"to contain exactly {EXPECTED_CONTENT!r}, but got {content!r}"
    )

    file_path = os.path.join(PROJECT_DIR, "file.txt")
    assert os.path.isfile(file_path), f"{file_path} does not exist."
    with open(file_path, "r") as f:
        on_disk = f.read()
    assert on_disk == EXPECTED_CONTENT, (
        f"Expected file.txt to contain exactly {EXPECTED_CONTENT!r}, but got "
        f"{on_disk!r}"
    )

def test_jj_status_no_conflicts():
    handover = handover_working_copy()
    conflicted = jj("log", "-r", handover, "--no-graph",
                    "-T", 'conflict ++ "\\n"').split()
    assert conflicted == ["false"], (
        f"jj still reports the bootstrap's own working-copy commit ({handover}) as "
        f"conflicted (conflict={conflicted}), so the conflict it handed over is "
        "still unresolved."
    )
