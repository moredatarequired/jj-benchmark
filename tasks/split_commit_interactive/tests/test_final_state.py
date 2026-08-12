"""Verifier for split_commit_interactive.

The task splits the commit described "Add feature A and feature B" into
"Add feature A" (feature_a.py only) and "Add feature B" (feature_b.py only), with
`@` left an empty child of the second.

WHERE THE REFERENCE VALUES COME FROM
====================================

The two commits are still located positionally, as `@--` and `@-`, because that is
how the instruction words the end state. What is new is that the split has to have
actually consumed the BOOTSTRAP's own commit: exactly one of `@--` and `@-` must
carry the change id the bootstrap gave "Add feature A and feature B", read from
the anchor (tests/anchor.py) -- a measurement made on the host, from the untouched
image, before the agent ran.

Without that, `jj new -r 'root()' -m 'Add feature A'` + a file + `jj new -m 'Add
feature B'` + a file + `jj new` puts a fabricated pair at `@--` and `@-`, leaves
the original commit standing untouched beside them, and collects both scored
tests. Nothing is destroyed, so the integrity fixture in conftest.py holds; the
change id is what distinguishes a split of that commit from a pair of commits that
look like one.

Deliberately agnostic about WHICH half keeps the change id. Measured on jj 0.38.0,
the non-interactive `jj split -r X <paths>` gives it to the older half; the
interactive form this task is named for is not measured, and the requirement -- one
of the two halves is the original commit -- is true of either.

The assertion is repeated in both scored tests on purpose. Partial credit is
scored per test, so a check that lives in only one of two scored tests still pays
half of the task's reward to a fabrication.

In cold CI there is no anchor file -- change ids are random per image build -- and
the check is skipped with a printed note that no identity claim was made, leaving
each test exactly as strong as it was before.
"""

import subprocess

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/myproject"

ORIGINAL = "Add feature A and feature B"

# Marker asking the resolver for "nothing", so a caller can tell the anchored path
# from the fallback path. It never reaches jj.
NO_ANCHOR = ""

_SNAPSHOTTED = []


def snapshot_once():
    """One deliberate working-copy snapshot per run, then read-only calls only.

    Every jj call this file used to make snapshotted implicitly (a plain jj
    command records the working copy first), which is also why a stray helper
    script left in the project makes test_working_copy_empty fail. Doing it once,
    explicitly, keeps that behaviour rather than quietly changing it, and lets
    every other call be repeatable.
    """
    if not _SNAPSHOTTED:
        _SNAPSHOTTED.append(subprocess.run(
            ["jj", "status"], cwd=PROJECT_DIR, capture_output=True, text=True))
    return _SNAPSHOTTED[0]


def jj(*args):
    snapshot_once()
    return subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=PROJECT_DIR, capture_output=True, text=True,
    )


def change_id_of(revset):
    result = jj("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\\n"')
    assert result.returncode == 0, f"jj log failed: {result.stderr}"
    found = result.stdout.split()
    assert len(found) == 1, (
        f"Expected revset {revset!r} to name exactly one commit, got {found}")
    return found[0]


def assert_the_split_consumed_the_original():
    """One of `@--` and `@-` must be the commit the bootstrap handed over."""
    original = change_id_or_fallback(ORIGINAL, NO_ANCHOR, repo=PROJECT_DIR)
    if not original:
        return
    halves = [change_id_of("@--"), change_id_of("@-")]
    assert original in halves, (
        f"Neither @-- ({halves[0][:12]}) nor @- ({halves[1][:12]}) is the commit "
        f"the bootstrap described {ORIGINAL!r} (change {original[:12]}). Splitting "
        "a commit rewrites it into its halves, so one of them is it. Two commits "
        "that carry the right descriptions and the right files are not a split of "
        "that commit."
    )


def test_first_commit_content():
    """Priority 1: Use jj CLI to verify the grandparent commit (@--)."""
    assert_the_split_consumed_the_original()

    # Check description
    result_desc = jj("log", "-r", "@--", "--no-graph", "-T", "description")
    assert result_desc.returncode == 0, f"jj log failed: {result_desc.stderr}"
    assert result_desc.stdout.strip() == "Add feature A", \
        f"Expected first commit description to be 'Add feature A', got '{result_desc.stdout.strip()}'."

    # Check files
    result_diff = jj("diff", "-s", "-r", "@--")
    assert result_diff.returncode == 0, f"jj diff failed: {result_diff.stderr}"
    assert "feature_a.py" in result_diff.stdout, "Expected feature_a.py to be added in the first commit."
    assert "feature_b.py" not in result_diff.stdout, "feature_b.py should not be in the first commit."


def test_second_commit_content():
    """Priority 1: Use jj CLI to verify the parent commit (@-)."""
    assert_the_split_consumed_the_original()

    # Check description
    result_desc = jj("log", "-r", "@-", "--no-graph", "-T", "description")
    assert result_desc.returncode == 0, f"jj log failed: {result_desc.stderr}"
    assert result_desc.stdout.strip() == "Add feature B", \
        f"Expected second commit description to be 'Add feature B', got '{result_desc.stdout.strip()}'."

    # Check files
    result_diff = jj("diff", "-s", "-r", "@-")
    assert result_diff.returncode == 0, f"jj diff failed: {result_diff.stderr}"
    assert "feature_b.py" in result_diff.stdout, "Expected feature_b.py to be added in the second commit."
    assert "feature_a.py" not in result_diff.stdout, "feature_a.py should not be in the second commit."


def test_working_copy_empty():
    """Priority 1: Use jj CLI to verify the working copy (@) is empty."""
    result_diff = jj("diff", "-s", "-r", "@")
    assert result_diff.returncode == 0, f"jj diff failed: {result_diff.stderr}"
    assert result_diff.stdout.strip() == "", \
        f"Expected working copy to be empty, but it has changes: {result_diff.stdout}"
