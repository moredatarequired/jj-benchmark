"""The pushed branch has to carry the working copy the bootstrap handed over.

Both assertions used to be about the remote repository alone: a branch called
`my-feature` exists and some commit reachable from it has a path called
`feature.txt`. Neither says where that came from, so `jj new -r 'root()' -m "Add
feature.txt"` + `echo ... > feature.txt` + `jj bookmark create my-feature` +
`jj git push` passes both while the working copy the task handed over -- the one
that actually holds the file -- was never pushed. That fabrication destroys
nothing, so the bootstrap anchor holds and the verifier grades the fabricated
commit (measured: reward 1).

Both tests now name that working copy by the change id the anchor recorded before
the agent ran (see tests/anchor.py) and require the remote to hold it. The commit
id is resolved from the change id at verification time, never read out of the
anchor file: `jj describe` rewrites the commit id, which is exactly what the task
asks for, while the change id survives it.

Reachable-from rather than equal-to on purpose. Both routes that jj actually
allows here end with the bookmark either ON that change (`jj describe` then
`jj bookmark create`) or on a descendant of it (`jj commit` then
`jj bookmark create -r @-`), and pushing a bookmark pushes its ancestry, so
"the bootstrap's commit is in the pushed history" covers both without letting a
commit built beside it count.
"""

import os
import subprocess

from anchor import working_copy_or_fallback

PROJECT_DIR = "/home/user/repo"
REMOTE_DIR = "/home/user/remote.git"

# The bootstrap left exactly one commit in this repository -- the working copy
# holding feature.txt, with no description -- so it is named through the anchor's
# reserved per-workspace working-copy key rather than by a description, which is
# `""` and would identify nothing.
#
# The fallback for cold CI (and for any sweep run without
# `scripts/bootstrap_anchor.py --write`) is the bookmark itself. That is
# deliberately circular: it makes the two assertions below collapse into exactly
# what they said before the anchor existed -- "the commit `my-feature` points at
# is in the remote and carries feature.txt" -- so a missing anchor drops the
# identity claim without changing a single verdict. Naming a position such as `@`
# instead would be WRONG here: after the `jj commit` route the bookmark sits on
# `@-` and `@` is an unpushed empty child, so a correct solve would fail in cold
# CI. working_copy_or_fallback() prints a line recording that the identity claim
# was not made.
WC_FALLBACK = "my-feature"


def jj(*args):
    """A read-only jj call in the task repository. Never snapshots."""
    result = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=PROJECT_DIR, capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"`jj {' '.join(args)}` failed in {PROJECT_DIR} ({result.returncode}): "
        f"{result.stderr.strip()}"
    )
    return result.stdout


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=REMOTE_DIR, capture_output=True, text=True,
    )


def bootstrap_commit_id():
    """The commit id the bootstrap's working-copy change resolves to right now."""
    revset = working_copy_or_fallback(WC_FALLBACK, workspace="default",
                                      repo=PROJECT_DIR)
    found = [
        line for line in
        jj("log", "-r", revset, "--no-graph", "-T", 'commit_id ++ "\n"').splitlines()
        if line
    ]
    assert len(found) == 1, (
        f"{revset!r} resolves to {len(found)} commit(s) in {PROJECT_DIR} "
        f"({found}); the work this task pushes lives in exactly one."
    )
    return found[0]


def assert_pushed_history_contains_the_bootstrap_commit():
    """THE anchored claim: the branch in the remote descends from what was handed over."""
    wanted = bootstrap_commit_id()
    known = git("cat-file", "-e", f"{wanted}^{{commit}}")
    assert known.returncode == 0, (
        f"The commit the task handed over ({wanted}) is not in {REMOTE_DIR} at "
        "all, so whatever was pushed was not this repository's work. A bookmark "
        "push sends the bookmarked commit and its ancestors; a commit built "
        "beside them is not one of them."
    )
    reachable = git("merge-base", "--is-ancestor", wanted, "my-feature")
    assert reachable.returncode == 0, (
        f"{REMOTE_DIR}'s `my-feature` does not descend from {wanted}, the commit "
        "this task handed over. A branch of that name exists, but it carries "
        "different commits."
    )


def test_remote_branch_exists():
    """Priority 1: Use Git CLI to verify the branch exists in the remote repository."""
    result = subprocess.run(
        ["git", "branch", "--list", "my-feature"],
        capture_output=True, text=True, cwd=REMOTE_DIR
    )
    assert result.returncode == 0, f"'git branch' failed: {result.stderr}"
    assert "my-feature" in result.stdout, f"Expected branch 'my-feature' in remote repo, got: {result.stdout}"
    assert_pushed_history_contains_the_bootstrap_commit()


def test_remote_branch_contains_file():
    """Priority 1: Use Git CLI to verify the branch contains the expected file."""
    result = subprocess.run(
        ["git", "ls-tree", "-r", "my-feature"],
        capture_output=True, text=True, cwd=REMOTE_DIR
    )
    assert result.returncode == 0, f"'git ls-tree' failed: {result.stderr}"
    assert "feature.txt" in result.stdout, f"Expected 'feature.txt' in branch 'my-feature', got: {result.stdout}"

    assert_pushed_history_contains_the_bootstrap_commit()
    wanted = bootstrap_commit_id()
    listed = git("ls-tree", "-r", wanted)
    assert listed.returncode == 0, (
        f"`git ls-tree -r {wanted}` failed in {REMOTE_DIR}: {listed.stderr.strip()}"
    )
    assert "feature.txt" in listed.stdout, (
        f"The commit this task handed over ({wanted}) reached the remote, but it "
        f"does not contain feature.txt: {listed.stdout!r}. The file that was "
        "pushed came from somewhere other than the working copy the task set up."
    )
