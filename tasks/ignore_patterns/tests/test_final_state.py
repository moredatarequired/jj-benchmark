"""Untracking debug.log has to happen in THIS repository's history.

The three scored assertions used to be satisfiable by a working copy that never
tracked debug.log in the first place: a `.gitignore` on disk containing `*.log`, a
`jj file list` that does not mention debug.log, and one that does mention
`.gitignore`. So `jj new -r 'root()'` plus writing the two files passes all three
-- and it removes nothing, so the bootstrap anchor holds and the verifier grades a
commit that has nothing to do with the one the task set up (measured: reward 1).

The bootstrap left exactly one commit here, its working copy, with debug.log
tracked in it. Every scored test below therefore also asserts that the working
copy being inspected still descends from (or is) that commit, addressed by the
change id the anchor recorded before the agent ran -- see tests/anchor.py, and note
that it is named through the anchor's reserved per-workspace working-copy key
because its description is `""`.

Descends-from rather than is-exactly, because `jj file untrack` leaves the change
in place while `jj commit` or a preceding `jj new` puts the working copy on a
descendant of it. All three routes are correct and all three still score 1.
"""

import os
import subprocess

from anchor import working_copy_or_fallback

PROJECT_DIR = "/home/user/myproject"

# The revset the bootstrap's working copy is resolved by when the anchor cannot
# supply its change id -- CI always builds cold, and so does any sweep run without
# `scripts/bootstrap_anchor.py --write`. `@` makes the ancestry claim below
# trivially true, so a missing anchor leaves every assertion exactly as strong as
# it was; working_copy_or_fallback() prints a line saying the identity claim was
# not made.
WC_FALLBACK = "@"


def snapshot():
    """Snapshot the working copy once, deliberately, before reading it.

    This is the one call here that does NOT pass --ignore-working-copy, and it is
    load-bearing rather than an oversight: the ignore rules are only really in
    force if a fresh snapshot leaves debug.log out. A file jj does not consider
    ignored is added straight back by the next command, so a verifier that only
    ever read committed state could be satisfied by an untracking that the next
    `jj status` would undo. Everything after this reads with
    --ignore-working-copy so nothing else mutates what is being graded.
    """
    result = subprocess.run(
        ["jj", "status"], cwd=PROJECT_DIR, capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"`jj status` failed in {PROJECT_DIR}: {result.stderr.strip()}"
    )


def jj(*args):
    """A read-only jj call that never snapshots."""
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
        f"The working copy does not descend from {handover[:12]}, the commit this "
        "task handed over with debug.log tracked in it. Whatever is being "
        "inspected was built elsewhere in the repository, so nothing here was "
        "ever untracked -- a commit that never tracked debug.log is not the same "
        "as one that stopped tracking it."
    )


def test_gitignore_exists_and_contains_log():
    gitignore_path = os.path.join(PROJECT_DIR, ".gitignore")
    assert os.path.isfile(gitignore_path), ".gitignore file does not exist."
    with open(gitignore_path) as f:
        content = f.read()
    assert "*.log" in content, ".gitignore does not contain '*.log'."

    assert_working_copy_descends_from_the_bootstrap()
    committed = jj("file", "show", "-r", "@", ".gitignore")
    assert "*.log" in committed, (
        f"The .gitignore on disk contains '*.log' but the one recorded in the "
        f"working-copy commit is {committed!r}. The rule has to be in the "
        "repository, not only in the filesystem."
    )


def test_debug_log_is_untracked():
    snapshot()
    result = subprocess.run(
        ["jj", "--ignore-working-copy", "-R", PROJECT_DIR, "file", "list", "-r", "@"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Failed to list jj files: {result.stderr}"
    assert not any(line.endswith("debug.log") for line in result.stdout.splitlines()), "debug.log is still tracked by jj."
    assert_working_copy_descends_from_the_bootstrap()


def test_debug_log_exists_on_disk():
    log_path = os.path.join(PROJECT_DIR, "debug.log")
    assert os.path.isfile(log_path), "debug.log was deleted from disk."


def test_gitignore_is_tracked():
    snapshot()
    result = subprocess.run(
        ["jj", "--ignore-working-copy", "-R", PROJECT_DIR, "file", "list", "-r", "@"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Failed to list jj files: {result.stderr}"
    assert any(line.endswith(".gitignore") for line in result.stdout.splitlines()), ".gitignore is not tracked by jj."
    assert_working_copy_descends_from_the_bootstrap()
