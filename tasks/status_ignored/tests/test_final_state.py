"""build.log has to stop being tracked in THIS history, not in a fresh one.

The scored assertions here were already structural -- build.log is absent from the
working-copy commit, and the most recent commit in `::@` that touches it is one
that REMOVES it while its parent still has it -- which is much stronger than a
disk read. What they still could not tell is WHOSE history that was. An additive
fabrication satisfies all of it: build a commit from `root()` that adds build.log,
then a child that ignores and untracks it, and park `@` there. Nothing is removed,
so the bootstrap anchor holds and the verifier grades a two-commit history the
agent wrote from scratch (measured: reward 1).

So each scored test now also pins the commit that ADDED build.log: the oldest
commit in the working copy's ancestry that touches build.log must be the
bootstrap's own `initial commit`, addressed by the change id the anchor recorded
before the agent ran (see tests/anchor.py).
"""

import os
import subprocess

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/project"

# The bootstrap's description for the commit that added build.log, and the revset
# it falls back to when the anchor cannot supply the change id -- CI always builds
# cold, and so does any sweep run without `scripts/bootstrap_anchor.py --write`.
# The fallback resolves to whatever the oldest build.log-touching ancestor happens
# to be, which makes the identity assertion below trivially true and leaves these
# tests exactly as strong as they were before the anchor existed;
# change_id_or_fallback() prints a line recording that the claim was not made.
ADDED_BY = "initial commit"
ADDED_BY_FALLBACK = 'roots(::@ & files(root-file:"build.log"))'


def snapshot():
    """Snapshot the working copy once, deliberately, before reading it.

    The one call in this file that does NOT pass --ignore-working-copy, and it is
    load-bearing rather than an oversight: an entry jj does not consider ignored
    is added straight back by the next command, so asking about `@` only proves
    the ignore rules are in force if a fresh snapshot has just been taken.
    Everything else reads with --ignore-working-copy, so nothing else mutates the
    repository being graded.
    """
    result = subprocess.run(
        ["jj", "status"], cwd=PROJECT_DIR, capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"`jj status` failed in {PROJECT_DIR}: {result.stderr.strip()}"
    )


def _jj(*args):
    """Run a read-only jj command in the task project, never snapshotting."""
    return subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        capture_output=True, text=True, cwd=PROJECT_DIR
    )


def _lines(result, what):
    assert result.returncode == 0, f"'jj {what}' failed: {result.stderr}"
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _tracked_files(revset):
    """The paths tracked at a revision."""
    return _lines(_jj("file", "list", "-r", revset), f"file list -r {revset}")


def _commit_ids(revset):
    """Full commit ids for `revset`, newest first.

    --no-graph with an explicit template is the only shape of `jj log` worth
    parsing; the graph output wraps lines and elides commits. A bare newline is
    whitespace in jj's template language, so the separator has to be an explicit
    "\\n" concatenated onto the value.
    """
    return _lines(
        _jj("log", "-r", revset, "--no-graph", "-T", 'commit_id ++ "\\n"'),
        f"log -r {revset}",
    )


def _change_ids(revset):
    return _lines(
        _jj("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\\n"'),
        f"log -r {revset}",
    )


def assert_build_log_came_from_the_bootstrap():
    """THE anchored claim: the file that got untracked is the one that was there.

    A jj change id is random at creation and survives every legitimate rewrite, so
    the commit that added build.log in a solved repository is still the bootstrap's
    own commit. In a fabricated history it is a commit the agent made, and no
    amount of matching content or description changes that.
    """
    revset = change_id_or_fallback(ADDED_BY, ADDED_BY_FALLBACK, repo=PROJECT_DIR)
    wanted = _change_ids(revset)
    assert len(wanted) == 1, (
        f"{revset!r} resolves to {len(wanted)} commit(s) in {PROJECT_DIR}: "
        f"{wanted}. Exactly one commit added build.log."
    )
    added_by = wanted[0]

    oldest = _change_ids('roots(::@ & files(root-file:"build.log"))')
    assert oldest == [added_by], (
        f"The oldest commit in the working copy's ancestry that touches build.log "
        f"is {[c[:12] for c in oldest]}, but the commit that added build.log when "
        f"this task was handed over is {added_by[:12]}. The history being graded "
        "is not the one the task started from -- a commit that adds build.log and "
        "a commit that removes it again say nothing if the agent wrote both."
    )


def test_build_log_exists():
    """Priority 3 fallback: basic file existence check."""
    log_path = os.path.join(PROJECT_DIR, "build.log")
    assert os.path.isfile(log_path), f"File {log_path} must not be deleted."


def test_gitignore_contains_build_log():
    """Priority 3 fallback: check .gitignore content."""
    gitignore_path = os.path.join(PROJECT_DIR, ".gitignore")
    assert os.path.isfile(gitignore_path), ".gitignore file must exist."
    with open(gitignore_path) as f:
        content = f.read()
    assert "build.log" in content, ".gitignore must contain 'build.log'."

    assert_build_log_came_from_the_bootstrap()
    snapshot()
    recorded = _jj("file", "show", "-r", "@", ".gitignore")
    assert recorded.returncode == 0, (
        f".gitignore is on disk but is not recorded in the working-copy commit: "
        f"{recorded.stderr.strip()}"
    )
    assert "build.log" in recorded.stdout, (
        f"The .gitignore recorded in the working-copy commit is "
        f"{recorded.stdout!r} and does not mention build.log."
    )


def test_build_log_is_not_tracked_via_cli():
    """Priority 1: Use jj file list to verify build.log is not tracked."""
    snapshot()
    result = _jj("file", "list", "-r", "@")
    assert result.returncode == 0, f"'jj file list' failed: {result.stderr}"
    assert "build.log" not in result.stdout.splitlines(), \
        "Expected build.log to no longer be tracked by jj."
    assert_build_log_came_from_the_bootstrap()


def test_build_log_not_in_status_via_cli():
    """Priority 1: the untracking must be recorded in the repository.

    The old body iterated over `jj status` lines looking for one mentioning
    build.log and put its only assertion inside that loop. The untouched
    bootstrap has a clean working copy, so no line mentioned build.log, the loop
    body never ran, and the test passed having asserted nothing at all.

    Asked structurally instead, in terms of what the task demands: build.log is
    absent from the working-copy commit's tree, the commit that most recently
    touches build.log is one that *removes* it (its parent still has it), the
    commit that ADDED it is the one the bootstrap created, and the file is still
    on disk. That is the difference between untracking the file and never having
    tracked it -- and it holds whether the agent left the removal in the working-
    copy commit or described and committed it.
    """
    snapshot()
    assert "build.log" not in _tracked_files("@"), (
        "build.log is still tracked in the working-copy commit. Adding it to "
        ".gitignore does not remove an already-tracked file; it has to be "
        "untracked as well."
    )

    assert_build_log_came_from_the_bootstrap()

    touching = _commit_ids('::@ & files(root-file:"build.log")')
    assert len(touching) >= 2, (
        "Only one commit in the working copy's ancestry touches build.log -- the "
        f"one that added it ({touching}). Nothing has untracked it."
    )

    remover = touching[0]
    assert "build.log" not in _tracked_files(remover), (
        f"The most recent commit touching build.log ({remover}) still tracks it."
    )
    assert "build.log" in _tracked_files(f"{remover}-"), (
        f"The parent of {remover} does not track build.log, so {remover} is not "
        "the commit that untracked it."
    )

    log_path = os.path.join(PROJECT_DIR, "build.log")
    assert os.path.isfile(log_path), (
        f"{log_path} was deleted from the filesystem; it had to be untracked, not removed."
    )
