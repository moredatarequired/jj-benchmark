"""Verifier for split_commit_interactive.

The task splits the commit described "Add feature A and feature B" into
"Add feature A" (feature_a.py only) and "Add feature B" (feature_b.py only).

WHERE THE REFERENCE VALUES COME FROM
====================================

The two halves used to be located POSITIONALLY, as `@--` and `@-`. Position is
not identity, and here it was not even a dependable position. `jj edit @-`
followed by `jj split` -- the interactive route this task is named for, and the
route tests/anchor_exemptions.json already blesses by name -- leaves `@` ON the
second half, so `@-` is then the FIRST half and `@--` is the root commit. A
textbook-correct split scored 0 that way, while the exemption file said the
route was legitimate: the fixture permitted it and the verifier failed it. That
contradiction is what this addressing removes.

So the halves are now resolved from the BOOTSTRAP's own commit. The anchor
(tests/anchor.py) supplies the change id the bootstrap gave "Add feature A and
feature B" -- a measurement made on the host, from the untouched image, before
the agent ran. Splitting a commit rewrites it into its halves, so that change id
is still carried by one of them; the other half is the adjacent commit, found by
ancestry rather than by distance from `@`:

  * if the anchored commit still has a parent other than the root, the split
    gave the change id to the NEWER half and the older half is that parent;
  * otherwise the anchored commit is the OLDER half and the newer half is its
    single child.

That is deliberately agnostic about WHICH half keeps the change id. Measured on
jj 0.38.0, the non-interactive `jj split -r X <paths>` gives it to the older
half; the interactive form this task is named for is not measured, and the
requirement -- one of the two halves IS the original commit -- is true of either.
It is equally agnostic about where `@` ends up, which is the point: a solve is
graded on the two commits it produced, not on where the agent is standing when it
stops.

WHY THIS IS STRONGER THAN THE POSITIONAL FORM, NOT WEAKER
=========================================================

Under the old addressing the bootstrap's commit only had to be *among* the two
commits at `@--` and `@-`. Now it IS one of the two graded commits, by
construction, and every description and content assertion below is made about it.

  * `jj new -r 'root()' -m 'Add feature A'` + a file + `jj new -m 'Add feature
    B'` + a file + `jj new` builds a fabricated pair and leaves the original
    commit standing untouched beside it. Nothing is destroyed, so the integrity
    fixture in conftest.py holds -- but the fabricated pair is never looked at.
    The original is what gets graded, it is still described "Add feature A and
    feature B", and both scored tests fail.
  * A wipe-and-rebuild (`rm -rf .jj`, re-init, replay) fails earlier still, in
    conftest.py, on the handover operation id, which is never exempted.

The resolution runs in both scored tests on purpose. Partial credit is scored
per test, so a check that lives in only one of two scored tests still pays half
of the task's reward to a fabrication.

In cold CI there is no anchor file -- change ids are random per image build --
and the resolver ABSTAINS: it returns the `@--`/`@-` pair this file used before,
prints that no identity claim was made, and leaves each test exactly as strong as
it was. A missing anchor never fabricates a failure.
"""

import subprocess

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/myproject"

ORIGINAL = "Add feature A and feature B"

# Marker asking the resolver for "nothing", so a caller can tell the anchored
# path from the fallback path. It never reaches jj.
NO_ANCHOR = ""

# The positions the two halves occupy when the instruction's end state is
# followed to the letter (`@` an empty child of the second half). Used ONLY when
# there is no anchor file, so that this file then asserts exactly what it
# asserted before the anchor existed -- never more, never less.
FALLBACK_HALVES = ("@--", "@-")

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


def change_ids(revset):
    """Every change id the revset names, in jj's order. May be empty."""
    result = jj("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\\n"')
    assert result.returncode == 0, (
        f"`jj log -r {revset!r}` failed: {result.stderr.strip()}")
    return result.stdout.split()


def change_id_of(revset, what="the revset"):
    found = change_ids(revset)
    assert len(found) == 1, (
        f"Expected {what} to be exactly one commit, but {revset!r} names "
        f"{len(found)}: {found}. Splitting {ORIGINAL!r} leaves exactly two "
        "commits where it stood, the newer one the only child of the older."
    )
    return found[0]


def assert_the_split_consumed_the_original():
    """The two halves of the split, oldest first, from the bootstrap's commit.

    Returns a pair of revsets, `(older, newer)`. The anti-fabrication guard is
    not a side check any more: the bootstrap's own commit is one of the two
    revsets returned, so the descriptions and file lists asserted by the callers
    are asserted ABOUT it. Two commits that merely carry the right descriptions
    and the right files are never reached.
    """
    original = change_id_or_fallback(ORIGINAL, NO_ANCHOR, repo=PROJECT_DIR)
    if not original:
        # No anchor: abstain from the identity claim rather than invent a
        # failure, and grade the positions this file graded before.
        return FALLBACK_HALVES

    anchored = f"change_id({original})"
    parent = f"parents({anchored}) ~ root()"
    if change_ids(parent):
        # The change id went to the newer half; the older half is its parent.
        older, newer = parent, anchored
    else:
        # The change id stayed on the older half; the newer half is its child.
        older, newer = anchored, f"children({anchored})"

    halves = [change_id_of(older, "the first (older) half"),
              change_id_of(newer, "the second (newer) half")]
    # This cannot fire while the pair above is derived from `original`. It is
    # kept as the statement of the invariant that the addressing rests on, so a
    # later change to the derivation cannot silently stop grading the commit the
    # bootstrap handed over.
    assert original in halves, (
        f"Neither graded commit ({halves[0][:12]}, {halves[1][:12]}) is the "
        f"commit the bootstrap described {ORIGINAL!r} (change {original[:12]}). "
        "Splitting a commit rewrites it into its halves, so one of them is it. "
        "Two commits that carry the right descriptions and the right files are "
        "not a split of that commit."
    )
    return older, newer


def test_first_commit_content():
    """The older half: described `Add feature A`, carrying only feature_a.py."""
    first, _ = assert_the_split_consumed_the_original()

    # Check description
    result_desc = jj("log", "-r", first, "--no-graph", "-T", "description")
    assert result_desc.returncode == 0, f"jj log failed: {result_desc.stderr}"
    assert result_desc.stdout.strip() == "Add feature A", \
        f"Expected first commit description to be 'Add feature A', got '{result_desc.stdout.strip()}'."

    # Check files
    result_diff = jj("diff", "-s", "-r", first)
    assert result_diff.returncode == 0, f"jj diff failed: {result_diff.stderr}"
    assert "feature_a.py" in result_diff.stdout, "Expected feature_a.py to be added in the first commit."
    assert "feature_b.py" not in result_diff.stdout, "feature_b.py should not be in the first commit."


def test_second_commit_content():
    """The newer half: described `Add feature B`, carrying only feature_b.py."""
    _, second = assert_the_split_consumed_the_original()

    # Check description
    result_desc = jj("log", "-r", second, "--no-graph", "-T", "description")
    assert result_desc.returncode == 0, f"jj log failed: {result_desc.stderr}"
    assert result_desc.stdout.strip() == "Add feature B", \
        f"Expected second commit description to be 'Add feature B', got '{result_desc.stdout.strip()}'."

    # Check files
    result_diff = jj("diff", "-s", "-r", second)
    assert result_diff.returncode == 0, f"jj diff failed: {result_diff.stderr}"
    assert "feature_b.py" in result_diff.stdout, "Expected feature_b.py to be added in the second commit."
    assert "feature_a.py" not in result_diff.stdout, "feature_a.py should not be in the second commit."


def test_working_copy_empty():
    """Priority 1: Use jj CLI to verify the working copy (@) is empty.

    Still positional, and deliberately so: this one is *about* `@`. It is the
    instruction's own end-state bullet ("the current working copy should remain
    empty and be a child of the `Add feature B` commit"), it is floored, and it
    is the only assertion in this file that a correct split can leave unsatisfied
    -- `jj edit @-` + `jj split` parks `@` on the second half, and finishing with
    `jj new` is what the instruction asks for. If that bullet is ever dropped
    from instruction.md, this test has to go with it.
    """
    result_diff = jj("diff", "-s", "-r", "@")
    assert result_diff.returncode == 0, f"jj diff failed: {result_diff.stderr}"
    assert result_diff.stdout.strip() == "", \
        f"Expected working copy to be empty, but it has changes: {result_diff.stdout}"
