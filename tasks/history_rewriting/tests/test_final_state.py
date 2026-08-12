"""Verifier for the history_rewriting task.

WHY test_file_content DOES NOT READ base.txt OFF DISK ANY MORE
==============================================================

The task is "edit the Base commit so that base.txt contains new". Reading
/home/user/repo/base.txt asks a weaker question -- "is there a file somewhere in
the working directory with the right bytes" -- and an agent can answer it
without editing the bootstrap's commit at all: build a fabricated stack from
`root()`, leave the original stack untouched beside it (so the session-scoped
anchor fixture still holds, because nothing was destroyed) and park the working
copy on the fabrication. Measured: reward 1.

So this test resolves the graded commit by the change id the BOOTSTRAP gave it.
A jj change id is generated randomly at commit creation and preserved by
rebase / squash / describe, so it names the commit the task handed over and
cannot be reproduced by a commit created afterwards.

change_id_or_fallback() is what makes that safe in CI. bootstrap_anchor.json is
a per-build artifact -- gitignored, and absent in CI, which always builds cold
-- so when it is not there the resolver prints that the identity claim is NOT
being made and returns the description-based revset this test used before. The
assertion is then exactly as strong as it was: never weaker, and never an error.

Test names and count are unchanged, so tests/vacuity_floor.json does not move.
test_jj_log stays floored and is left exactly as it was.
"""

import os
import subprocess

import pytest

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/repo"


def jj(*args):
    """Read-only jj. --ignore-working-copy on every call, no exceptions.

    A plain jj read snapshots the working copy before answering, which appends
    an operation and creates a new version of `@` -- a verifier without it
    mutates the repository it is grading and can disagree with its own second
    run. --no-graph everywhere too, so there is never a graph glyph to strip
    (and a glyph character class containing `x` would truncate change ids, which
    use the letters k-z).
    """
    proc = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=PROJECT_DIR, capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"`jj {' '.join(args)}` failed ({proc.returncode}): {proc.stderr.strip()}"
    )
    return proc.stdout


def test_file_content():
    base = change_id_or_fallback(
        "Base", 'description(substring:"Base")', repo=PROJECT_DIR)
    content = jj("file", "show", "-r", base, "base.txt").strip()
    assert content == "new", (
        f"base.txt at the bootstrap's own 'Base' commit ({base}) holds "
        f"{content!r}, expected 'new'. That commit is the one the task asked to "
        "be edited; editing a different commit, or creating a new commit that "
        "looks like it, does not count."
    )

    on_disk = os.path.join(PROJECT_DIR, "base.txt")
    with open(on_disk) as fh:
        assert fh.read().strip() == "new", (
            f"{on_disk} does not hold 'new', so the edited commit is not the one "
            "that is checked out."
        )

def test_jj_log():
    result = subprocess.run(["jj", "log", "-T", "description"], cwd=PROJECT_DIR, capture_output=True, text=True)
    assert "Commit 3" in result.stdout, "Expected 'Commit 3' in jj log."
    assert "Commit 2" in result.stdout, "Expected 'Commit 2' in jj log."
    assert "Commit 1" in result.stdout, "Expected 'Commit 1' in jj log."
    assert "Base" in result.stdout, "Expected 'Base' in jj log."
