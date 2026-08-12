"""A workspace is a second working copy OF A REPOSITORY, not a second repository.

Every assertion here used to be about the directory `/home/user/myproject-
workspace2` on its own: it exists, it has a `.jj`, `jj status` runs in it.
Nothing tied it to `/home/user/myproject`, so `jj git init
/home/user/myproject-workspace2` -- a brand-new, unrelated repository that
shares nothing with the project but its path -- passed all three (measured:
reward 1). That is not a weak check of the task, it is a check of a different
task.

What makes a directory a workspace of the project is that it is backed by the
project's repository, and the unforgeable evidence for that is that the
project's own commits resolve from inside it. The bootstrap's working-copy
commit is addressed here by the change id the ANCHOR recorded before the agent
ran (see tests/anchor.py), so "the project's commits" means the commits the task
handed over rather than any commit that happens to look similar.
"""

import os
import subprocess

from anchor import working_copy_or_fallback

PROJECT_DIR = "/home/user/myproject"
WORKSPACE_DIR = "/home/user/myproject-workspace2"

# What the bootstrap's working copy is resolved as when the anchor cannot supply
# its change id -- i.e. in CI, which always builds cold, and in any sweep run
# without `scripts/bootstrap_anchor.py --write`. `@` is the project's working
# copy as the verifier finds it, which is what the assertions below could have
# said before the anchor existed; the identity claim is simply not made then,
# and working_copy_or_fallback() prints a line saying so.
WC_FALLBACK = "@"


def jj(cwd, *args):
    """A read-only jj call. --ignore-working-copy on every one, without exception.

    A plain jj read snapshots the working copy first, which appends an operation
    and creates a new version of `@` -- a verifier that does that mutates the
    repository it is grading.
    """
    return subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=cwd, capture_output=True, text=True,
    )


def change_ids(cwd, revset):
    """The change ids `revset` resolves to for the repo backing `cwd`, or None.

    None means jj could not resolve the revset there at all, which is the answer
    that matters: a repository that is not the project's does not contain the
    project's change ids, so `jj log -r <that id>` exits non-zero in it.
    """
    result = jj(cwd, "log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\n"')
    if result.returncode != 0:
        return None
    return [line for line in result.stdout.splitlines() if line]


def bootstrap_working_copy():
    """The change id of the working copy the bootstrap handed over.

    Resolved inside PROJECT_DIR so that it is a concrete change id in both
    cases: the anchored one when the anchor is available, and whatever `@` is
    now when it is not.
    """
    revset = working_copy_or_fallback(WC_FALLBACK, workspace="default",
                                      repo=PROJECT_DIR)
    found = change_ids(PROJECT_DIR, revset)
    assert found, (
        f"{revset!r} does not resolve in {PROJECT_DIR}, so the project "
        "repository is not there to be shared with a workspace."
    )
    assert len(found) == 1, (
        f"{revset!r} resolves to {len(found)} commits in {PROJECT_DIR}: {found}"
    )
    return found[0]


def assert_backed_by_the_project_repo():
    """THE anchored claim: WORKSPACE_DIR is a working copy of the project repo.

    A jj change id is random at creation and survives every legitimate rewrite,
    so a repository that resolves the project's bootstrap change id is the
    project's repository. One that was created separately cannot resolve it, no
    matter what it is named or what it contains.
    """
    wanted = bootstrap_working_copy()
    found = change_ids(WORKSPACE_DIR, wanted)
    assert found is not None, (
        f"The commit {wanted[:12]} that {PROJECT_DIR} holds does not resolve "
        f"from inside {WORKSPACE_DIR}, so that directory is not a workspace of "
        "the project's repository -- it is a separate repository that only "
        "shares the expected path. A workspace added with `jj workspace add` "
        "shares the project's operation log and commits."
    )
    assert found == [wanted], (
        f"{wanted[:12]} resolves to {found} from inside {WORKSPACE_DIR}."
    )


def test_workspace_dir_exists():
    assert os.path.isdir(WORKSPACE_DIR), f"Workspace directory {WORKSPACE_DIR} was not created."
    root = jj(WORKSPACE_DIR, "workspace", "root")
    assert root.returncode == 0, (
        f"`jj workspace root` fails in {WORKSPACE_DIR}: {root.stderr.strip()}"
    )
    assert root.stdout.strip() == WORKSPACE_DIR, (
        f"{WORKSPACE_DIR} is not itself a workspace root; jj says its workspace "
        f"root is {root.stdout.strip()!r}."
    )
    assert_backed_by_the_project_repo()


def test_workspace_is_jj_repo():
    jj_dir = os.path.join(WORKSPACE_DIR, ".jj")
    assert os.path.isdir(jj_dir), f"{WORKSPACE_DIR} is not a valid jj workspace."

    listed = jj(PROJECT_DIR, "workspace", "list", "-T",
                'name ++ "\x1f" ++ target.change_id() ++ "\n"')
    assert listed.returncode == 0, (
        f"`jj workspace list` failed in {PROJECT_DIR}: {listed.stderr.strip()}"
    )
    workspaces = [line.split("\x1f") for line in listed.stdout.splitlines() if line]
    assert len(workspaces) >= 2, (
        f"{PROJECT_DIR} still has only these workspace(s): {workspaces}. A "
        "second working copy that the project's own repository does not know "
        "about is not a workspace of it."
    )
    targets = {change_id for _, change_id in workspaces}
    assert bootstrap_working_copy() in targets, (
        "The project's own working copy is not among the workspace targets "
        f"{workspaces} that {PROJECT_DIR} reports."
    )

    here = change_ids(WORKSPACE_DIR, "@")
    assert here, f"`jj log -r @` fails in {WORKSPACE_DIR}."
    assert here[0] in targets, (
        f"{WORKSPACE_DIR} says its working-copy commit is {here[0][:12]}, but "
        f"{PROJECT_DIR}'s repository does not list that as any workspace's "
        f"working copy (it lists {workspaces}). The two directories are backed "
        "by different repositories."
    )
    assert_backed_by_the_project_repo()


def test_jj_status_in_workspace():
    # Deliberately without --ignore-working-copy: a workspace whose working copy
    # cannot be snapshotted is not usable, and that is what this test is for.
    result = subprocess.run(
        ["jj", "status"],
        cwd=WORKSPACE_DIR,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"jj status failed in {WORKSPACE_DIR} with output: {result.stderr}"
    assert_backed_by_the_project_repo()
