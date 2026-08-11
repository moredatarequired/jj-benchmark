import os
import shutil
import subprocess
import pytest

PROJECT_DIR = "/home/user/project"

def test_jj_binary_available():
    assert shutil.which("jj") is not None, "jj binary not found in PATH."

def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), f"Project directory {PROJECT_DIR} does not exist."

def test_jj_repo_initialized():
    jj_dir = os.path.join(PROJECT_DIR, ".jj")
    assert os.path.isdir(jj_dir), "Jujutsu repository not initialized in the project directory."

def test_jj_author_configured():
    try:
        output = subprocess.check_output(["jj", "config", "get", "user.name"], cwd=PROJECT_DIR, text=True)
        assert "Test User" in output, "jj user.name is not configured correctly."
    except subprocess.CalledProcessError:
        pytest.fail("Failed to get jj user.name config.")


def test_working_copy_commit_has_the_configured_author():
    """@ must actually be authored by the configured identity.

    The task is to print the author of the working-copy commit, so the bootstrap
    has to give @ an author to print. `jj git init` stamps @ with whatever
    identity is configured at that instant, so configuring the identity after
    the init leaves @ authored by " <>" and makes the required output
    unreachable from a template. This asserts on the commit, not on the config,
    because it is the commit the task reads.
    """
    output = subprocess.check_output(
        [
            "jj", "log", "-r", "@", "--no-graph", "--ignore-working-copy",
            "-T", 'author.name() ++ " <" ++ author.email() ++ ">"',
        ],
        cwd=PROJECT_DIR,
        text=True,
    )
    assert output.strip() == "Test User <test@example.com>", (
        f"The working copy commit @ is authored by {output.strip()!r}, expected "
        "'Test User <test@example.com>'. Configure user.name / user.email "
        "before `jj git init`, not after."
    )
