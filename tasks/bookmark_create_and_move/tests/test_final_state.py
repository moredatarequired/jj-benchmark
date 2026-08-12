"""The bookmark has to end up on this repository's history, not beside it.

Both assertions used to be satisfiable without touching the repository the task
handed over: a bookmark named `feature-x` appears in `jj bookmark list`, and the
commit it points at has a description containing `add feature y`. A description is
free text, so `jj new -r 'root()' -m "add feature y"` + `jj bookmark create
feature-x` passes both. Done additively -- nothing removed -- every anchored
change id is still visible too, so the bootstrap anchor holds and the verifier
grades the fabricated commit (measured: reward 1).

The commit that carries `add feature y` is created BY the agent, so it has no
bootstrap change id of its own. What the anchor can pin is where it has to sit:
the task says to bookmark the initial working copy and then build on top of it,
so the bootstrap's own working-copy commit must be an ancestor of (or be) the
commit `feature-x` points at. A commit built from `root()` beside it is not.

Ancestor-of rather than parent-of on purpose: `jj new` + `jj bookmark move` leaves
`feature-x` on a child of the initial commit, while `jj commit` describes the
initial commit itself and carries the bookmark along with it. Both routes score 1
today and both still do.
"""

import os
import subprocess

from anchor import working_copy_or_fallback

PROJECT_DIR = "/home/user/my-project"

# The revset the bootstrap's working copy is resolved by when the anchor cannot
# supply its change id -- CI always builds cold, and so does any sweep run
# without `scripts/bootstrap_anchor.py --write`. The fallback is the bookmark
# itself, which makes the ancestry claim below trivially true (a commit is its own
# ancestor) and so collapses each test into exactly what it asserted before the
# anchor existed. working_copy_or_fallback() prints a line recording that the
# identity claim was not made.
WC_FALLBACK = 'bookmarks(exact:"feature-x")'


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


def change_ids(revset):
    return [
        line for line in
        jj("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\n"').splitlines()
        if line
    ]


def assert_bookmark_is_on_the_bootstrap_line():
    """THE anchored claim: feature-x descends from the working copy handed over."""
    revset = working_copy_or_fallback(WC_FALLBACK, workspace="default",
                                     repo=PROJECT_DIR)
    wanted = change_ids(revset)
    assert len(wanted) == 1, (
        f"{revset!r} resolves to {len(wanted)} commit(s) in {PROJECT_DIR}: "
        f"{wanted}."
    )
    initial = wanted[0]
    reachable = change_ids(f'{initial} & ::bookmarks(exact:"feature-x")')
    assert reachable == [initial], (
        f"The commit `feature-x` points at does not descend from {initial[:12]}, "
        "the working copy this task handed over. The task asks for a bookmark on "
        "that commit and then a commit built ON TOP of it, so whatever "
        "`feature-x` names now was created somewhere else in the repository "
        "rather than on top of what was there."
    )


def test_bookmark_exists_via_cli():
    """Priority 1: Use jj CLI to verify the bookmark exists."""
    result = subprocess.run(
        ["jj", "--ignore-working-copy", "bookmark", "list"],
        capture_output=True, text=True, cwd=PROJECT_DIR
    )
    assert result.returncode == 0, f"'jj bookmark list' failed: {result.stderr}"
    assert "feature-x" in result.stdout, f"Expected 'feature-x' in bookmarks, got: {result.stdout}"
    assert_bookmark_is_on_the_bootstrap_line()


def test_bookmark_target_description_via_cli():
    """Priority 1: Use jj CLI to verify the commit description of the bookmark."""
    result = subprocess.run(
        ["jj", "--ignore-working-copy", "log", "-r", "feature-x", "--no-graph",
         "-T", "description"],
        capture_output=True, text=True, cwd=PROJECT_DIR
    )
    assert result.returncode == 0, f"'jj log' failed: {result.stderr}"
    assert "add feature y" in result.stdout, f"Expected commit description to be 'add feature y', got: {result.stdout}"
    assert_bookmark_is_on_the_bootstrap_line()
