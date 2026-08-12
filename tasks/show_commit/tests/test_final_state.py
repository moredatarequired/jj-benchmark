"""The patches have to have come out of THIS repository's commits.

Three of the four assertions used to be substring searches over text: a
`diff --git` header, a `+key=value` line, a `-key=value` line. Text is what an
agent writes, so both patch files could be typed by hand without the script ever
being run, and an additive fabrication -- redescribe the two bootstrap commits,
build a parallel pair from `root()` with the same content, run the script against
those -- produces byte-identical diff bodies, because a git diff of identical
content IS identical, blob hashes included. Neither route touches the bootstrap
commits, so the anchor holds and the verifier grades the wrong thing.

What ties a patch to a commit is the commit's own identity, which `jj show` prints
above the diff (`Commit ID:` / `Change ID:`) and which the task's requirement 3
asks for in as many words: "print that revision's details together with its diff".
So each patch file must carry the identity of the bootstrap commit it claims to
describe, and the script must be exercised against that commit through its
argument -- the ids come from the anchor (tests/anchor.py), captured before the
agent ran, and the commit id is resolved from the change id at verification time
rather than read out of the anchor file.

ONE SCORED TEST HERE CANNOT BE ANCHORED. `test_script_exists_and_executable` asks
only whether a file exists and has the executable bit; no commit is involved, and
no assertion about the repository can be added to it without turning it into a copy
of `test_script_execution`. An additive fabrication therefore still collects that
one test, i.e. 0.25 rather than 0. It is left alone deliberately, and the residual
is stated rather than papered over.
"""

import os
import subprocess

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/project"

# The bootstrap's descriptions for the two commits this task extracts patches for,
# and the revsets they fall back to when the anchor cannot supply their change ids
# -- CI always builds cold, and so does any sweep run without
# `scripts/bootstrap_anchor.py --write`. The fallbacks are the exact revsets the
# task's own instructions name, so a missing anchor leaves each test asking what it
# asked before; change_id_or_fallback() prints a line recording that the identity
# claim was not made.
ADD = "Add configuration file"
ADD_FALLBACK = 'description(substring:"Add configuration file")'
UPDATE = "Update configuration file"
UPDATE_FALLBACK = 'description(substring:"Update configuration file")'

# jj prints ids in full in `jj show`'s header but abbreviates them elsewhere, and
# the abbreviation length grows with the repository. Matching on a PREFIX of the
# full id accepts either, because every abbreviation jj prints is a prefix of the
# full id. 8 is well below any length jj would print and far above coincidence.
ID_PREFIX = 8


def jj(*args):
    """A read-only jj call. --ignore-working-copy on every one, without exception."""
    result = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=PROJECT_DIR, capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"`jj {' '.join(args)}` failed in {PROJECT_DIR} ({result.returncode}): "
        f"{result.stderr.strip()}"
    )
    return result.stdout


def revision(description, fallback):
    """(revset, change id, commit id) for one of the bootstrap's commits."""
    revset = change_id_or_fallback(description, fallback, repo=PROJECT_DIR)
    found = [
        line.split("\x1f") for line in
        jj("log", "-r", revset, "--no-graph",
           "-T", 'change_id ++ "\x1f" ++ commit_id ++ "\n"').splitlines()
        if line
    ]
    assert len(found) == 1, (
        f"{revset!r} resolves to {len(found)} commit(s) in {PROJECT_DIR}: {found}. "
        "The patch this task asks for is the patch of exactly one commit."
    )
    return (revset,) + tuple(found[0])


def assert_identifies(text, change_id, commit_id, where):
    """`text` has to name the commit it claims to be a patch of."""
    assert (change_id[:ID_PREFIX] in text or commit_id[:ID_PREFIX] in text), (
        f"{where} contains a diff, but nothing in it identifies the revision it "
        f"came from: neither the change id {change_id[:12]} nor the commit id "
        f"{commit_id[:12]} appears. `jj show` prints both above the diff, and the "
        "task asks for the revision's details together with its diff. Without "
        "them a patch is just text -- it cannot be told from one that was typed "
        "out, or one taken from a different commit that happens to hold the same "
        "content, since a git diff of identical content is identical."
    )


def test_script_exists_and_executable():
    script_path = os.path.join(PROJECT_DIR, "show_commit.sh")
    assert os.path.isfile(script_path), f"Script {script_path} does not exist."
    assert os.access(script_path, os.X_OK), f"Script {script_path} is not executable."


def test_script_execution():
    script_path = os.path.join(PROJECT_DIR, "show_commit.sh")
    revset, change_id, commit_id = revision(ADD, ADD_FALLBACK)
    # Run the script with the revset argument -- the anchored change id when the
    # anchor can supply it, which is also what the task's requirement 2 ("take a
    # single argument: a Jujutsu revset") is for: a script that ignores its
    # argument cannot answer for an arbitrary revision.
    result = subprocess.run(
        [script_path, revset],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Script failed with error: {result.stderr}"
    assert "diff --git a/config.txt b/config.txt" in result.stdout, "Script output does not contain Git-format diff."
    assert "+key=value" in result.stdout, "Script output does not contain the expected diff content."
    assert_identifies(result.stdout, change_id, commit_id,
                      f"The script's output for {revset!r}")


def test_add_config_patch_exists_and_content():
    patch_path = os.path.join(PROJECT_DIR, "add_config.patch")
    assert os.path.isfile(patch_path), f"File {patch_path} does not exist."

    with open(patch_path, "r") as f:
        content = f.read()

    assert "diff --git a/config.txt b/config.txt" in content, "Patch file does not contain Git-format diff header."
    assert "+key=value" in content, "Patch file does not contain the expected addition."

    _, change_id, commit_id = revision(ADD, ADD_FALLBACK)
    assert_identifies(content, change_id, commit_id, patch_path)


def test_update_config_patch_exists_and_content():
    patch_path = os.path.join(PROJECT_DIR, "update_config.patch")
    assert os.path.isfile(patch_path), f"File {patch_path} does not exist."

    with open(patch_path, "r") as f:
        content = f.read()

    assert "diff --git a/config.txt b/config.txt" in content, "Patch file does not contain Git-format diff header."
    assert "-key=value" in content, "Patch file does not contain the expected removal."
    assert "+key=new_value" in content, "Patch file does not contain the expected addition."

    _, change_id, commit_id = revision(UPDATE, UPDATE_FALLBACK)
    assert_identifies(content, change_id, commit_id, patch_path)
