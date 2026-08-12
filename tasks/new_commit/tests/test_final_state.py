"""Verifier for new_commit.

The task turns the repository's single empty working-copy commit into `commit 1`
and stacks `commit 2` and `commit 3` on top of it.

WHERE THE REFERENCE VALUES COME FROM
====================================

`commit 1` is not a commit the agent may create: requirement 1 says to modify the
CURRENT working copy, which is the one commit the bootstrap made. That commit is
addressed here by its anchored change id (tests/anchor.py), captured on the host
from the untouched image before the agent ran, and looked up by workspace name
rather than by description -- an empty description is not a usable key.

The positional form this file used before (`@`, `@-`, `@--` plus descriptions and
file contents) is satisfied by `jj new -r 'root()' -m 'commit 1'` and two more
`jj new`s: a stack of three fabricated commits, with the bootstrap's own commit
left untouched beside them, passing all three tests. Nothing is destroyed, so the
integrity fixture holds as well. Anchoring the bottom of the stack is what makes
the chain be the chain the task asked for -- which is also why this task
deliberately has no anchor_exemptions.json: its one bootstrap commit is the graded
object.

In cold CI there is no anchor file -- change ids are random per image build -- and
each test falls back to the positional form, printing that no identity claim was
made.
"""

import subprocess

from anchor import working_copy_or_fallback

PROJECT_DIR = "/home/user/myproject"

# Marker asking the resolver for "nothing", so a test can tell the anchored path
# from the fallback path. It never reaches jj.
NO_ANCHOR = ""

_SNAPSHOTTED = []


def snapshot_once():
    """One deliberate working-copy snapshot per run, then read-only calls only.

    Load-bearing here: an agent that writes file1.txt and describes the commit
    without running any further jj command leaves the file unsnapshotted, and
    every jj call this file used to make snapshotted it implicitly. Doing it once,
    explicitly, keeps that solve passing while making the reads repeatable.
    """
    if not _SNAPSHOTTED:
        _SNAPSHOTTED.append(subprocess.run(
            ["jj", "status"], cwd=PROJECT_DIR, capture_output=True, text=True))
    return _SNAPSHOTTED[0]


def run_jj_cmd(cmd, cwd=PROJECT_DIR):
    snapshot_once()
    result = subprocess.run(
        cmd[:1] + ["--ignore-working-copy"] + cmd[1:],
        cwd=cwd, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def bootstrap_working_copy():
    """The change id of the commit the bootstrap handed over, or "" if no anchor."""
    return working_copy_or_fallback(NO_ANCHOR, repo=PROJECT_DIR)


def change_id_of(revset):
    found = run_jj_cmd(["jj", "log", "-r", revset, "-T", 'change_id ++ "\\n"',
                        "--no-graph"]).split()
    assert len(found) == 1, (
        f"Expected revset {revset!r} to name exactly one commit, got {found}")
    return found[0]


def assert_is_the_bootstrap_commit(revset):
    """`revset` must name the commit the bootstrap left as the working copy.

    That commit is `commit 1`: requirement 1 describes the CURRENT working copy
    rather than creating a new commit.
    """
    expected = bootstrap_working_copy()
    if not expected:
        return
    found = change_id_of(revset)
    assert found == expected, (
        f"{revset} is change {found[:12]}, but the commit the bootstrap handed "
        f"over is {expected[:12]}. Requirement 1 modifies THAT commit into "
        "`commit 1`, so the chain has to be built on it -- a fresh three-commit "
        "stack created beside it is not this task."
    )


def test_commit_3():
    # Verify current working copy commit (@)
    desc = run_jj_cmd(["jj", "log", "-r", "@", "-T", "description", "--no-graph"])
    assert desc == "commit 3", f"Expected description 'commit 3' for @, got '{desc}'"

    # Verify file3.txt exists and contains 'third' in @
    content = run_jj_cmd(["jj", "file", "show", "file3.txt", "-r", "@"])
    assert "third" in content, f"Expected 'third' in file3.txt at @, got '{content}'"

    # ...and @ is the top of the chain that starts at the bootstrap's own commit.
    assert_is_the_bootstrap_commit("@--")


def test_commit_2():
    # Verify parent commit (@-)
    desc = run_jj_cmd(["jj", "log", "-r", "@-", "-T", "description", "--no-graph"])
    assert desc == "commit 2", f"Expected description 'commit 2' for @-, got '{desc}'"

    # Verify file2.txt exists and contains 'second' in @-
    content = run_jj_cmd(["jj", "file", "show", "file2.txt", "-r", "@-"])
    assert "second" in content, f"Expected 'second' in file2.txt at @-, got '{content}'"

    # ...and its parent is the bootstrap's own commit, i.e. `commit 2` was
    # created as a child of the commit the task started from.
    assert_is_the_bootstrap_commit("@--")


def test_commit_1():
    # Verify grandparent commit (@--)
    assert_is_the_bootstrap_commit("@--")

    desc = run_jj_cmd(["jj", "log", "-r", "@--", "-T", "description", "--no-graph"])
    assert desc == "commit 1", f"Expected description 'commit 1' for @--, got '{desc}'"

    # Verify file1.txt exists and contains 'first' in @--
    content = run_jj_cmd(["jj", "file", "show", "file1.txt", "-r", "@--"])
    assert "first" in content, f"Expected 'first' in file1.txt at @--, got '{content}'"
