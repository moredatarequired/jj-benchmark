import os
import shutil
import subprocess

REPO_DIR = "/home/user/repo"

# `evolog` is the current name of the command; the `obslog` alias it replaced is
# deprecated, so the bootstrap check does not depend on the alias surviving.
EVOLOG_TEMPLATE = (
    r'commit.commit_id() ++ "\0" ++ commit.description().first_line() ++ "\n"'
)


def jj(*args):
    """Read-only jj call: `--ignore-working-copy` stops it snapshotting."""
    result = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"`jj {' '.join(args)}` failed with status {result.returncode}: "
        f"{result.stderr.strip()}"
    )
    return result.stdout


def test_jj_installed():
    assert shutil.which("jj") is not None, "jj executable not found in PATH"


def test_repo_exists():
    assert os.path.isdir(REPO_DIR), f"Repository directory {REPO_DIR} does not exist"
    assert os.path.isdir(os.path.join(REPO_DIR, ".jj")), (
        f"jj repository not initialized in {REPO_DIR}"
    )


def test_working_copy_change_has_evolved():
    """The working-copy change must have several superseded versions to report."""
    lines = [
        line for line in jj(
            "evolog", "--no-graph", "--color=never", "-T", EVOLOG_TEMPLATE
        ).splitlines() if line
    ]
    assert len(lines) >= 3, (
        f"Expected at least 3 versions in the working-copy change's evolution, "
        f"found {len(lines)}"
    )

    descriptions = {line.partition("\x00")[2] for line in lines}
    assert {"v1", "v2"} <= descriptions, (
        f"Expected the change's evolution to include versions described 'v1' and "
        f"'v2', found {sorted(descriptions)}"
    )


def test_report_file_absent():
    """The task's output file must not exist before the agent runs."""
    assert not os.path.exists("/home/user/obslog.txt"), (
        "/home/user/obslog.txt already exists in the bootstrap image"
    )
