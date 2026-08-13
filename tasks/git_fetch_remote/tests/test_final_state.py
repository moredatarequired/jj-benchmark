"""The remote's `feature` has to be the commit the task handed over, rebased.

Both assertions used to be about the remote repository alone: a ref called
`feature` exists, and `main` is an ancestor of it. **`git branch feature main`,
run inside `/home/user/remote.git`, satisfies both** -- `git merge-base
--is-ancestor main main` exits 0 -- so the task could be passed outright without
fetching, rebasing, pushing, or running jj at all (measured: reward 1). The same
thing happens with an additive fabrication: build a fresh commit described
`Feature commit` from `root()`, move the `feature` bookmark onto it and push
that, and the remote looks right while the bootstrap's own commit was never
touched.

So both tests now ask the remote ref to be a specific commit: the one the
bootstrap's `Feature commit` change resolves to right now. That change id came
off the untouched image before the agent ran (see tests/anchor.py) and is
preserved by the rebase the task asks for, while the commit id is rewritten by
it -- which is why the commit id has to be resolved from the change id at test
time and can never be taken from the anchor file.

Carried over from `bookmark_push`, which was folded into this task when the
suite was cut to 14: the tree check in test_feature_pushed_to_remote. Identity
by change id says the *right commit* reached the remote; it does not say that
commit still carries the work, and an agent that restored `feature.txt` away
before pushing would satisfy every id comparison here. `bookmark_push`'s
`test_remote_branch_contains_file` was the only assertion in the pair that read
the pushed tree, so it moves here. Everything else `bookmark_push` did is
already stronger in this file: its bookmark check was reachable-from, this one
is equality; and its "create a bookmark on an anonymous commit and push it as a
NEW remote bookmark" surface is this task's fixture too, because the bootstrap
creates `feature` locally (`jj bookmark create feature`) and never pushes it.
"""

import os
import subprocess

from anchor import change_id_or_fallback

REPO_DIR = "/home/user/repo"
REMOTE_DIR = "/home/user/remote.git"

# The description the bootstrap gave the commit this task rebases and pushes,
# and the revset it is resolved by when the anchor cannot supply its change id
# (cold CI, or a sweep run without `scripts/bootstrap_anchor.py --write`). The
# fallback is the description-based revset these assertions could have used
# before the anchor existed; the identity claim is then not made, and
# change_id_or_fallback() prints a line saying so.
FEATURE = "Feature commit"
FEATURE_FALLBACK = 'description(substring:"Feature commit")'


def jj(*args):
    """A read-only jj call in the task repository, never snapshotting."""
    result = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=REPO_DIR, capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"`jj {' '.join(args)}` failed in {REPO_DIR} ({result.returncode}): "
        f"{result.stderr.strip()}"
    )
    return result.stdout


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=REMOTE_DIR, capture_output=True, text=True,
    )


def feature_commit_id():
    """The commit id the bootstrap's `Feature commit` change resolves to NOW.

    A rebase preserves the change id and rewrites the commit id, so the commit
    id the remote must carry is only knowable at verification time. Resolving it
    from the change id is the whole point: it is the pushed commit's identity,
    not its description.
    """
    revset = change_id_or_fallback(FEATURE, FEATURE_FALLBACK, repo=REPO_DIR)
    found = [
        line for line in
        jj("log", "-r", revset, "--no-graph", "-T", 'commit_id ++ "\n"').splitlines()
        if line
    ]
    assert len(found) == 1, (
        f"{revset!r} resolves to {len(found)} commit(s) in {REPO_DIR} ({found}); "
        "exactly one commit should carry the work this task pushes."
    )
    return found[0]


def remote_ref(name):
    """The commit id the remote's branch `name` points at, or None."""
    result = git("rev-parse", "--verify", f"refs/heads/{name}")
    return result.stdout.strip() if result.returncode == 0 else None


def test_feature_pushed_to_remote():
    result = git("branch", "--list", "feature")
    assert "feature" in result.stdout, "Expected 'feature' branch to be pushed to the remote repository."

    wanted = feature_commit_id()
    pushed = remote_ref("feature")
    assert pushed == wanted, (
        f"The remote's `feature` points at {pushed}, but the commit the task's "
        f"own `{FEATURE}` change resolves to in {REPO_DIR} is {wanted}. The "
        "branch in the remote therefore does not hold the work that was handed "
        "over -- it points at some other commit that was created or moved into "
        "place instead of being pushed."
    )

    # From the folded `bookmark_push`: the pushed commit must still hold the
    # work. Equality above proves *which* commit arrived; only its tree proves
    # the file the `Feature commit` change introduced is still in it.
    listed = git("ls-tree", "-r", "--name-only", wanted)
    assert listed.returncode == 0, (
        f"`git ls-tree -r {wanted}` failed in {REMOTE_DIR}: "
        f"{listed.stderr.strip()}"
    )
    assert "feature.txt" in listed.stdout.split(), (
        f"The commit the task handed over ({wanted}) reached the remote, but it "
        f"no longer contains feature.txt: {listed.stdout!r}. The `{FEATURE}` "
        "change was pushed with its own content removed, so what the remote "
        "now holds is not the work this task is about."
    )


def test_feature_rebased_on_main():
    wanted = feature_commit_id()
    pushed = remote_ref("feature")
    main = remote_ref("main")
    assert main is not None, "The remote has no `main` branch to have rebased onto."
    assert pushed == wanted, (
        f"The remote's `feature` points at {pushed}, not at the commit the "
        f"bootstrap's `{FEATURE}` change resolves to ({wanted})."
    )
    assert pushed != main, (
        "The remote's `feature` and `main` are the same commit, so nothing was "
        "rebased onto anything -- `git merge-base --is-ancestor main main` "
        "succeeds trivially. `feature` has to be a commit ON TOP OF main."
    )
    ancestor = git("merge-base", "--is-ancestor", "main", "feature")
    assert ancestor.returncode == 0, (
        "Expected 'feature' to be rebased onto the latest 'main': the remote's "
        f"main ({main}) is not an ancestor of its feature ({pushed})."
    )
