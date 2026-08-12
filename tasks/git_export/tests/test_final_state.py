"""The exported branch has to be the bookmark the bootstrap created.

Both assertions used to be about the backing Git repository alone: a branch
called `feature-x` exists and its tip message mentions `jj commit`. A commit
message is free text the agent writes, so `jj new -r 'root()' -m "jj commit"`
plus `jj bookmark set feature-x` plus `jj git export` satisfies both while the
bookmark the bootstrap actually created was never exported -- an additive
fabrication that destroys nothing, so the bootstrap anchor still holds and the
verifier grades the fabricated commit.

Exporting is the one operation in this task, and what it means is that the Git
ref ends up pointing at the SAME commit the jj bookmark points at. So both tests
now compare the exported ref against the commit id that the bootstrap's own
`jj commit` change resolves to at verification time -- the change id comes from
the anchor (tests/anchor.py), and the commit id is resolved from it here, never
read out of the anchor file, because commit ids are rewritten by every honest
rewrite while change ids are not.
"""

import os
import subprocess

from anchor import change_id_or_fallback

GIT_DIR = "/home/user/git-repo"
JJ_DIR = "/home/user/jj-repo"

# The bootstrap's description for the commit under the feature-x bookmark, and
# the revset it falls back to when the anchor cannot supply the change id -- in
# CI, which always builds cold, or in a sweep run without
# `scripts/bootstrap_anchor.py --write`. The fallback is what these assertions
# could have said before the anchor existed, so the identity claim is dropped
# rather than the test breaking; change_id_or_fallback() prints a line saying so.
EXPORTED = "jj commit"
EXPORTED_FALLBACK = 'description(substring:"jj commit")'


def jj(*args):
    """A read-only jj call in the jj repository, never snapshotting."""
    result = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=JJ_DIR, capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"`jj {' '.join(args)}` failed in {JJ_DIR} ({result.returncode}): "
        f"{result.stderr.strip()}"
    )
    return result.stdout


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=GIT_DIR, capture_output=True, text=True,
    )


def bookmarked_commit_id():
    """The commit id the bootstrap's `jj commit` change resolves to right now."""
    revset = change_id_or_fallback(EXPORTED, EXPORTED_FALLBACK, repo=JJ_DIR)
    found = [
        line for line in
        jj("log", "-r", revset, "--no-graph", "-T", 'commit_id ++ "\n"').splitlines()
        if line
    ]
    assert len(found) == 1, (
        f"{revset!r} resolves to {len(found)} commit(s) in {JJ_DIR} ({found}); "
        "exactly one commit should carry the work this task exports."
    )
    return found[0]


def exported_ref():
    """The commit id `refs/heads/feature-x` points at in GIT_DIR, or None."""
    result = git("rev-parse", "--verify", "refs/heads/feature-x")
    return result.stdout.strip() if result.returncode == 0 else None


def test_feature_x_branch_exists_in_git():
    result = subprocess.run(["git", "branch", "--list", "feature-x"], cwd=GIT_DIR, capture_output=True, text=True)
    assert "feature-x" in result.stdout, "Branch feature-x was not exported to the Git repository."

    wanted = bookmarked_commit_id()
    exported = exported_ref()
    assert exported == wanted, (
        f"{GIT_DIR}'s feature-x points at {exported}, but the commit the "
        f"bootstrap's `{EXPORTED}` change resolves to in {JJ_DIR} is {wanted}. A "
        "branch of that name exists, but it is not the bookmark this task asked "
        "to be exported."
    )


def test_feature_x_commit_content():
    # Verify the commit has the expected message
    result = subprocess.run(["git", "log", "-1", "--format=%B", "feature-x"], cwd=GIT_DIR, capture_output=True, text=True)
    assert "jj commit" in result.stdout, "The exported branch feature-x does not have the expected commit."

    wanted = bookmarked_commit_id()
    exported = exported_ref()
    assert exported == wanted, (
        f"{GIT_DIR}'s feature-x tip is {exported}, whose message happens to "
        f"mention {EXPORTED!r}, but the commit the bootstrap's own `{EXPORTED}` "
        f"change resolves to is {wanted}. A message is free text; the exported "
        "ref has to be the same commit the jj bookmark points at."
    )
