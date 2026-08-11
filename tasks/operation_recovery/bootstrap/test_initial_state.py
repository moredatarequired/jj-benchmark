import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/project"

# jj stores a non-empty description with a trailing newline, and a bare string
# pattern is not a substring match, so the pattern kind is spelled out.
DESCRIPTIONS = ("Commit 1", "Commit 2", "Commit 3", "Commit 4", "Commit 5")


def jj(*args):
    """Read-only jj call: `--ignore-working-copy` stops it snapshotting."""
    result = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"`jj {' '.join(args)}` failed with status {result.returncode}: "
        f"{result.stderr.strip()}"
    )
    return result.stdout


def log(revset, template):
    """Structural query: templated, graphless output over an explicit revset."""
    return [line for line in jj(
        "log", "--no-graph", "--color=never", "-r", revset, "-T",
        template + ' ++ "\\n"'
    ).splitlines() if line]


def test_jj_binary_available():
    assert shutil.which("jj") is not None, "jj binary not found in PATH."


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), "Project directory not found."
    assert os.path.isdir(os.path.join(PROJECT_DIR, ".jj")), (
        "jj repository not initialized in the project directory."
    )


def test_five_described_commits_present():
    for description in DESCRIPTIONS:
        revset = 'description(exact:"' + description + '\\n")'
        found = log(revset, "commit_id")
        assert len(found) == 1, (
            f"Expected exactly one commit described '{description}', found "
            f"{len(found)}."
        )


def test_working_copy_is_empty_commit_on_top_of_commit_5():
    empty = log("@", 'if(empty, "empty", "nonempty")')
    assert empty == ["empty"], f"Expected an empty working-copy commit, got {empty}."

    parent = log("@", 'parents.map(|c| c.description().first_line()).join(",")')
    assert parent == ["Commit 5"], (
        f"Expected the working copy to sit on top of 'Commit 5', got {parent}."
    )


def test_all_five_files_present():
    for index in range(1, 6):
        name = f"file{index}.txt"
        assert os.path.isfile(os.path.join(PROJECT_DIR, name)), (
            f"{name} should be present in the starting state."
        )
