"""Untracking .env has to happen in the commit that was tracking it.

The two scored assertions used to be satisfiable by a working copy that never
tracked .env: a `.gitignore` on disk with a `.env` line in it, and a `jj file list`
that does not mention .env. So `jj new -r 'root()'` plus writing the two files
passes both -- and it removes nothing, so the bootstrap anchor holds and the
verifier grades a commit that has nothing to do with the accident the task
describes.

The bootstrap left exactly one commit here, its working copy, with .env tracked in
it. Both scored tests therefore also assert that the working copy being inspected
still descends from (or is) that commit, addressed by the change id the anchor
recorded before the agent ran -- see tests/anchor.py, and note that it is named
through the anchor's reserved per-workspace working-copy key because its
description is `""`.
"""

import os
import subprocess

from anchor import working_copy_or_fallback

PROJECT_DIR = "/home/user/myproject"

# The revset the bootstrap's working copy is resolved by when the anchor cannot
# supply its change id -- CI always builds cold, and so does any sweep run without
# `scripts/bootstrap_anchor.py --write`. `@` makes the ancestry claim trivially
# true, so a missing anchor leaves both tests exactly as strong as they were;
# working_copy_or_fallback() prints a line saying the claim was not made.
WC_FALLBACK = "@"


def snapshot():
    """Snapshot the working copy once, deliberately, before reading it.

    The one call here that does NOT pass --ignore-working-copy, and it is
    load-bearing: a file jj does not consider ignored is added straight back by the
    next command, so "not tracked" is only meaningful just after a fresh snapshot.
    Everything else reads with --ignore-working-copy so the verifier does not
    otherwise mutate what it is grading.
    """
    result = subprocess.run(
        ["jj", "status"], cwd=PROJECT_DIR, capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"`jj status` failed in {PROJECT_DIR}: {result.stderr.strip()}"
    )


def jj(*args):
    result = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=PROJECT_DIR, capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"`jj {' '.join(args)}` failed in {PROJECT_DIR} ({result.returncode}): "
        f"{result.stderr.strip()}"
    )
    return result.stdout


def change_ids(revset):
    return [
        line for line in
        jj("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\n"').splitlines()
        if line
    ]


def assert_working_copy_descends_from_the_bootstrap():
    """THE anchored claim: `@` is, or descends from, the commit handed over."""
    revset = working_copy_or_fallback(WC_FALLBACK, workspace="default",
                                     repo=PROJECT_DIR)
    found = change_ids(revset)
    assert len(found) == 1, (
        f"{revset!r} resolves to {len(found)} commit(s) in {PROJECT_DIR}: {found}"
    )
    handover = found[0]
    reachable = change_ids(f"{handover} & ::@")
    assert reachable == [handover], (
        f"The working copy does not descend from {handover[:12]}, the commit that "
        "was tracking .env when this task was handed over. A commit that never "
        "tracked .env is not the same as one that stopped tracking it."
    )


def test_env_file_exists():
    env_path = os.path.join(PROJECT_DIR, ".env")
    assert os.path.isfile(env_path), "The .env file was deleted! It should remain on the filesystem."
    with open(env_path) as f:
        content = f.read()
    assert "SECRET=" in content, "The .env file content was modified."


def test_env_in_gitignore():
    gitignore_path = os.path.join(PROJECT_DIR, ".gitignore")
    assert os.path.isfile(gitignore_path), ".gitignore file does not exist."
    with open(gitignore_path) as f:
        content = f.read().splitlines()
    assert ".env" in content, ".env is not in .gitignore."

    assert_working_copy_descends_from_the_bootstrap()
    snapshot()
    recorded = jj("file", "show", "-r", "@", ".gitignore").splitlines()
    assert ".env" in recorded, (
        f"The .gitignore on disk ignores .env but the copy recorded in the "
        f"working-copy commit is {recorded!r}. The rule has to be in the "
        "repository, not only in the filesystem."
    )


def test_env_not_tracked_by_jj():
    snapshot()
    result = subprocess.run(
        ["jj", "--ignore-working-copy", "file", "list", "-r", "@"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, "Failed to run 'jj file list'."
    tracked_files = result.stdout.splitlines()
    assert ".env" not in tracked_files, ".env is still tracked by jj."
    assert_working_copy_descends_from_the_bootstrap()
