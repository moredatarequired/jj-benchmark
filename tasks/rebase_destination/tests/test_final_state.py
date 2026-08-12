"""`feature` has to still be on the commit the bootstrap put it on.

The single assertion used to be that the parents of whatever `feature` points at
carry a bookmark called `main`. Both names are things the agent can move, so
building a fresh child of `main` described "Feature commit" and pointing
`feature` at it passes -- and it destroys nothing, so the bootstrap anchor holds
and the verifier grades the fabricated commit (measured: reward 1).

The task says to MOVE the commit `feature` points at, and a jj rebase moves a
commit while preserving its change id. So the check is stated in change ids: the
commit under `feature` is still the bootstrap's own `Feature commit`, and its
parent is the bootstrap's own `Main commit`. Both ids come from the anchor
(tests/anchor.py), captured before the agent ran.
"""

import os
import subprocess

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/myproject"

# The bootstrap's descriptions for the two commits this task relates, and the
# revsets they fall back to when the anchor cannot supply their change ids -- in
# CI, which always builds cold, or in a sweep run without
# `scripts/bootstrap_anchor.py --write`. The fallbacks are the bookmarks the old
# assertion went through, so a missing anchor leaves the test saying what it said
# before rather than erroring; change_id_or_fallback() prints a line recording
# that the identity claim was not made.
FEATURE = "Feature commit"
FEATURE_FALLBACK = "feature"
MAIN = "Main commit"
MAIN_FALLBACK = "main"


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


def change_ids(revset, template='change_id ++ "\n"'):
    return [
        line for line in
        jj("log", "-r", revset, "--no-graph", "-T", template).splitlines()
        if line
    ]


def one(revset):
    found = change_ids(revset)
    assert len(found) == 1, (
        f"{revset!r} resolves to {len(found)} commit(s) in {PROJECT_DIR}: {found}"
    )
    return found[0]


def test_feature_is_rebased_onto_main():
    feature = one(change_id_or_fallback(FEATURE, FEATURE_FALLBACK, repo=PROJECT_DIR))
    main = one(change_id_or_fallback(MAIN, MAIN_FALLBACK, repo=PROJECT_DIR))

    on_bookmark = change_ids('bookmarks(exact:"feature")')
    assert on_bookmark == [feature], (
        f"The bookmark `feature` sits on {[c[:12] for c in on_bookmark]}, but the "
        f"commit this task asks to be moved is {feature[:12]}. A rebase preserves "
        "the change id of the commit it moves, so `feature` should still be on "
        "that same change -- either the bookmark was moved onto some other "
        "commit, or the commit was replaced rather than moved."
    )

    parents = change_ids('bookmarks(exact:"feature")',
                         'parents.map(|p| p.change_id()).join("\n") ++ "\n"')
    assert parents == [main], (
        f"The commit under `feature` has parent(s) {[c[:12] for c in parents]}, "
        f"but the commit `main` pointed at is {main[:12]}. `feature`'s commit was "
        "not moved onto it."
    )
