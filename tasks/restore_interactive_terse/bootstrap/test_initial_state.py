"""Bootstrap check for the restore_interactive task.

Asserts the starting state the task description promises: a four-commit stack
in which the middle commit (`remove legacy module`) deleted `settings.toml` by
mistake, a working copy that adds `notes.txt`, and therefore no `settings.toml`
on disk yet.
"""

import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/myproject"


def jj(*args):
    return subprocess.run(
        ["jj", *args], cwd=PROJECT_DIR, capture_output=True, text=True
    )


def test_jj_binary_available():
    assert shutil.which("jj") is not None, "jj binary not found in PATH."


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), f"Project directory {PROJECT_DIR} does not exist."


def test_jj_repo_initialized():
    result = jj("status")
    assert result.returncode == 0, (
        f"jj status failed, not a jj repository. Error: {result.stderr}"
    )


def test_history_shape():
    result = jj(
        "log", "-r", "::@ ~ root()", "--no-graph", "--reversed",
        "-T", '"[" ++ description.first_line() ++ "]\\n"',
    )
    assert result.returncode == 0, f"jj log failed. Error: {result.stderr}"
    lines = [line for line in result.stdout.splitlines() if line]
    assert lines == [
        "[Initial commit]",
        "[remove legacy module]",
        "[add logging]",
        "[]",
    ], f"Unexpected starting history: {lines}"


def test_settings_deleted_by_middle_commit():
    """The mistake the task is about is actually present."""
    result = jj("diff", "-r", "@--", "--name-only")
    assert result.returncode == 0, f"jj diff failed. Error: {result.stderr}"
    changed = {line for line in result.stdout.splitlines() if line}
    assert changed == {"legacy.py", "main.py", "settings.toml"}, (
        f"Expected `remove legacy module` to change legacy.py, main.py and "
        f"settings.toml; it changes: {sorted(changed)}"
    )

    result = jj("file", "list", "-r", "@--")
    assert result.returncode == 0, f"jj file list failed. Error: {result.stderr}"
    tree = {line for line in result.stdout.splitlines() if line}
    assert tree == {"main.py"}, (
        f"Expected `remove legacy module` to contain only main.py; got {sorted(tree)}"
    )


def test_settings_present_in_initial_commit():
    result = jj("file", "show", "-r", "@---", "settings.toml")
    assert result.returncode == 0, (
        f"settings.toml missing from the initial commit. Error: {result.stderr}"
    )
    assert result.stdout == (
        '[server]\nhost = "127.0.0.1"\nport = 8080\n\n[logging]\nlevel = "info"\n'
    ), f"Unexpected settings.toml in the initial commit: {result.stdout!r}"


def test_working_copy_adds_notes():
    result = jj("diff", "-r", "@", "--name-only")
    assert result.returncode == 0, f"jj diff failed. Error: {result.stderr}"
    changed = {line for line in result.stdout.splitlines() if line}
    assert changed == {"notes.txt"}, (
        f"Expected the working copy to add only notes.txt; it changes: {sorted(changed)}"
    )


def test_on_disk_state():
    assert os.path.isfile(os.path.join(PROJECT_DIR, "main.py")), "main.py missing."
    assert os.path.isfile(os.path.join(PROJECT_DIR, "notes.txt")), "notes.txt missing."
    assert not os.path.exists(os.path.join(PROJECT_DIR, "settings.toml")), (
        "settings.toml should not be on disk yet -- the task is to bring it back."
    )
    assert not os.path.exists(os.path.join(PROJECT_DIR, "legacy.py")), (
        "legacy.py should not be on disk."
    )
