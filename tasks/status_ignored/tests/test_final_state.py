import os
import subprocess
import pytest

PROJECT_DIR = "/home/user/project"


def _jj(*args):
    """Run jj in the task project and return the CompletedProcess."""
    return subprocess.run(
        ["jj", *args], capture_output=True, text=True, cwd=PROJECT_DIR
    )


def _lines(result, what):
    assert result.returncode == 0, f"'jj {what}' failed: {result.stderr}"
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _tracked_files(revset):
    """The paths tracked at a revision.

    Any jj command snapshots the working copy first, so asking this about `@`
    also proves the ignore rules are in force: an entry jj does not consider
    ignored is added straight back by the next command.
    """
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


def test_build_log_is_not_tracked_via_cli():
    """Priority 1: Use jj file list to verify build.log is not tracked."""
    result = subprocess.run(
        ["jj", "file", "list"],
        capture_output=True, text=True, cwd=PROJECT_DIR
    )
    assert result.returncode == 0, f"'jj file list' failed: {result.stderr}"
    assert "build.log" not in result.stdout.splitlines(), \
        "Expected build.log to no longer be tracked by jj."


def test_build_log_not_in_status_via_cli():
    """Priority 1: the untracking must be recorded in the repository.

    The old body iterated over `jj status` lines looking for one mentioning
    build.log and put its only assertion inside that loop. The untouched
    bootstrap has a clean working copy, so no line mentions build.log, the loop
    body never ran, and the test passed having asserted nothing at all.

    Asked structurally instead, in terms of what the task demands: build.log is
    absent from the working-copy commit's tree, the commit that most recently
    touches build.log is one that *removes* it (its parent still has it), and
    the file is still on disk. That is the difference between untracking the
    file and never having done anything -- and it holds whether the agent left
    the removal in the working-copy commit or described and committed it.
    """
    assert "build.log" not in _tracked_files("@"), (
        "build.log is still tracked in the working-copy commit. Adding it to "
        ".gitignore does not remove an already-tracked file; it has to be "
        "untracked as well."
    )

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
