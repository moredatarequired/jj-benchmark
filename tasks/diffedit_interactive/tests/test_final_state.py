"""Verifier for the diffedit_interactive task.

WHAT CHANGED, AND WHY
=====================

test_commit_content_updated used to find the graded commit by scanning `jj log`
output for the first entry containing the text "add features". A description is
free text the agent can write, so an agent could create a new commit described
"add features" containing only foo(), leave the bootstrap's commit untouched
beside it (so the session-scoped anchor fixture still holds -- nothing is
destroyed) and the scan would return the fabrication. Measured: reward 1.

The graded commit is now resolved by the change id the BOOTSTRAP gave it. Change
ids are random at creation and are preserved by the `jj edit` / `jj squash`
routes that solve this task, so the id names the commit the task handed over.
The eighteen lines of hand-rolled log parsing go with it.

change_id_or_fallback() keeps this working in CI, where there is no anchor file
(it is gitignored and CI always builds cold): the resolver then prints that the
identity claim is NOT being made and returns the description revset, so the
assertion is exactly as strong as it was before.

Test names and count are unchanged, so tests/vacuity_floor.json does not move.
test_working_copy_clean stays floored and is left exactly as it was.
"""

import os
import subprocess
import pytest

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/myproject"

def test_commit_content_updated():
    change_id = change_id_or_fallback(
        "add features", 'description(substring:"add features")', repo=PROJECT_DIR)

    # --ignore-working-copy: a plain jj read snapshots the working copy first,
    # which would have this verifier mutate the repository it is grading.
    result = subprocess.run(
        ["jj", "--ignore-working-copy", "show", "-r", change_id],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, (
        f"Could not show the bootstrap's own 'add features' commit ({change_id}): "
        f"{result.stderr.strip()}"
    )
    assert "def foo():" in result.stdout, (
        f"The bootstrap's own 'add features' commit ({change_id}) is missing foo()."
    )
    assert "def bar():" not in result.stdout, (
        f"The bootstrap's own 'add features' commit ({change_id}) still contains "
        "bar(). Removing bar() from a different commit that carries the same "
        "description is not the same thing."
    )

def test_working_copy_clean():
    # Check that the working copy has no modifications
    result = subprocess.run(
        ["jj", "status"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, "Failed to run jj status."
    # A clean working copy should say "The working copy has no changes."
    assert "The working copy has no changes." in result.stdout, "Working copy is not clean."
