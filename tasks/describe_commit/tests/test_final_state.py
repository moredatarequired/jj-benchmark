"""Verifier for the describe_commit task.

WHAT CHANGED, AND WHY
=====================

The task is "set the description of the CURRENT working copy commit". The previous
version read `jj log -r @ -T description`, which says nothing about which commit
`@` is -- so `jj new -r 'root()' -m "feat: add new feature"` satisfied it while
leaving the commit the task handed over undescribed. That route destroys nothing,
so the session-scoped anchor fixture holds and the reward was 1 (measured).

The test now requires `@` to still be the working-copy commit the BOOTSTRAP handed
over, addressed by the change id it was created with, and reads the description
there. `jj describe` rewrites that commit in place and preserves its change id, so
a genuine solve is unaffected.

working_copy_or_fallback() is the reserved-key resolver: anchor keys are
description first lines, and an UNDESCRIBED working copy has none. When
bootstrap_anchor.json is absent -- it is gitignored, and CI always builds cold --
it prints that the identity claim is NOT being made and returns the positional
`@`, so the assertion degrades to exactly what it was before.

There is one test and its name is unchanged, so tests/vacuity_floor.json does not
move.
"""

import os
import subprocess
import pytest

from anchor import working_copy_or_fallback

PROJECT_DIR = "/home/user/myproject"


def jj(*args):
    """Read-only jj. --ignore-working-copy on every call, --no-graph templates."""
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


def test_commit_description():
    handover = working_copy_or_fallback("@", repo=PROJECT_DIR)
    here, there = change_ids("@"), change_ids(handover)
    assert here == there, (
        f"`@` is {here}, but the working-copy commit the bootstrap handed over is "
        f"{there}. The task asks for the description of THAT commit; creating a "
        "new commit with the right description instead leaves it undescribed."
    )

    description = jj("log", "--no-graph", "-r", handover, "-T", "description").strip()
    assert description == "feat: add new feature", (
        f"Expected description 'feat: add new feature' on the bootstrap's own "
        f"working-copy commit ({handover}), but got '{description}'"
    )
