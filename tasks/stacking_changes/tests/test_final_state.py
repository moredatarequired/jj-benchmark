"""Verifier for the stacking_changes task.

WHAT CHANGED, AND WHY
=====================

get_change_id_by_desc() scanned `jj log` for the FIRST commit whose description
contained the wanted text. That is attacker-writable: an agent could build a
parallel stack from `root()` with the same three descriptions, leave the
bootstrap's commits untouched beside it (so the session-scoped anchor fixture
still holds -- nothing is destroyed) and the scan would return the fabricated
commit. Measured: reward 1.

The two graded commits are now resolved by the change ids the BOOTSTRAP gave
them, via anchor.py's change_id_or_fallback(). A jj change id is random at
creation and is preserved by the `jj squash --into` / `jj edit` routes that solve
this task, so it names the commit the task handed over and no later commit can
carry it.

The description scan is kept, as the FALLBACK: bootstrap_anchor.json is a
per-build artifact, gitignored and absent in CI (which always builds cold), and
when it is missing the resolver prints that the identity claim is NOT being made
and returns this revset instead. The assertion is then exactly as strong as it
was.

The tip check is anchored the same way. It deliberately does NOT use the
handover `@`: tests/anchor_exemptions.json records that this bootstrap's empty,
undescribed `@` legitimately disappears on both solve routes.

There is one test and its name is unchanged, so tests/vacuity_floor.json does not
move.
"""

import os
import subprocess

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/repo"


def run_cmd(cmd, cwd=PROJECT_DIR):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
    return result.stdout.strip()


def jj(*args):
    """Read-only jj. --ignore-working-copy on every call, --no-graph templates.

    Without --ignore-working-copy a plain jj read snapshots the working copy
    first, so the verifier would mutate the repository it is grading.
    """
    return run_cmd(["jj", "--ignore-working-copy", *args])


def get_change_id_by_desc(desc):
    """The first commit whose description contains `desc` -- the FALLBACK path.

    Kept only so that a run with no anchor file behaves exactly as this verifier
    behaved before the anchor existed. graded() prefers the anchored change id.
    """
    log_output = jj("log", "--no-graph", "-T",
                    'change_id ++ "|" ++ description.first_line() ++ "\\n"')
    for line in log_output.splitlines():
        if "|" in line:
            cid, cdesc = line.split("|", 1)
            if desc in cdesc:
                return cid.strip()
    return None


def graded(desc):
    """The bootstrap's change id for `desc`, or the description scan's answer."""
    return change_id_or_fallback(
        desc, get_change_id_by_desc(desc) or "none()", repo=PROJECT_DIR)


def change_ids(revset):
    out = jj("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\\n"')
    return [line for line in out.splitlines() if line]


def test_final_state():
    # 1. feature1-docs.txt must be in THE BOOTSTRAP'S OWN "Add feature 1" commit
    feature1_id = graded("Add feature 1")
    assert change_ids(feature1_id), (
        f"Could not resolve the bootstrap's 'Add feature 1' commit ({feature1_id})"
    )

    file_content = jj("file", "show", "feature1-docs.txt", "-r", feature1_id)
    assert file_content == "Docs for feature 1", (
        f"feature1-docs.txt at the bootstrap's own 'Add feature 1' commit "
        f"({feature1_id}) holds '{file_content}', expected 'Docs for feature 1'. "
        "That commit is the one the task asked to be modified; a new commit that "
        "merely carries the same description is not it."
    )

    # 2. The bootstrap's three commits must still be one stack, in order
    feature3_id = graded("Add feature 3")
    assert change_ids(feature3_id), (
        f"Could not resolve the bootstrap's 'Add feature 3' commit ({feature3_id})"
    )

    stack = change_ids(f"{feature1_id}::{feature3_id}")
    log_output = jj("log", "-r", f"{feature1_id}::{feature3_id}", "--no-graph",
                    "-T", 'description.first_line() ++ "\\n"')
    assert "Add feature 1" in log_output
    assert "Add feature 2" in log_output
    assert "Add feature 3" in log_output
    assert len(stack) >= 3, (
        "The bootstrap's three commits must still be a stack of at least three "
        f"commits from 'Add feature 1' to 'Add feature 3'; got {stack}. You must "
        "not abandon or collapse any of them."
    )

    # 3. The working copy must be at the tip -- i.e. AT or ON TOP OF the
    #    bootstrap's own "Add feature 3". Not "some commit described that way".
    tip = change_ids(feature3_id)
    here = change_ids("@") + change_ids("@-")
    assert set(tip) & set(here), (
        f"Working copy should be at the tip of the stack: `@` or `@-` must be the "
        f"bootstrap's own 'Add feature 3' commit ({tip}), but they are {here}."
    )


if __name__ == "__main__":
    test_final_state()
