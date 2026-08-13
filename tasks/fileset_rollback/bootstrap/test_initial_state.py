"""Bootstrap check for the fileset_rollback task.

Asserts the starting state the request depends on, and above all the one
property that makes it a fileset task rather than a path task: `src/generated`
is NESTED INSIDE `src`, and both subtrees carry uncommitted work. If a future
edit ever moves the generated tree out from under `src/`, or leaves one of the
two subtrees clean, `jj restore src` stops being the wrong answer and the task
stops measuring anything -- so that is checked here rather than assumed.

It also pins the shape of the uncommitted work: modified files under src/, a
file ADDED under src/, modified and added files under src/generated, and edits
outside src/ entirely. Each of the three wrong answers the verifier is written
against needs one of those four groups to exist.
"""

import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/checkout-api"

MODIFIED_UNDER_SRC = {
    "src/api/charge.py",
    "src/api/handlers.py",
    "src/client/http.py",
}
ADDED_UNDER_SRC = {"src/api/refunds.py"}
GENERATED = {
    "src/generated/models.py",
    "src/generated/openapi_client.py",
    "src/generated/webhooks.py",
}
OUTSIDE_SRC = {"CHANGELOG.md", "tests/test_charge.py"}


def jj(*args):
    return subprocess.run(
        ["jj", *args], cwd=PROJECT_DIR, capture_output=True, text=True
    )


def lines(*args):
    result = jj(*args)
    assert result.returncode == 0, f"`jj {' '.join(args)}` failed: {result.stderr}"
    return [line for line in result.stdout.splitlines() if line]


def test_jj_binary_available():
    assert shutil.which("jj") is not None, "jj binary not found in PATH."


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), f"{PROJECT_DIR} does not exist."


def test_jj_repo_initialized():
    result = jj("status")
    assert result.returncode == 0, f"not a jj repository: {result.stderr}"


def test_history_shape():
    committed = lines("log", "-r", "::@- ~ root()", "--no-graph", "--reversed",
                      "-T", '"[" ++ description.first_line() ++ "]\\n"')
    assert committed == [
        "[add the charge endpoint]",
        "[let the http client read as well as write]",
    ], f"Unexpected committed history: {committed}"


def test_the_generated_tree_is_nested_inside_src():
    """The whole task. No single path argument separates the two."""
    tracked = set(lines("file", "list", "-r", "@"))
    assert GENERATED <= tracked, (
        f"the generated files must live under src/; tracked paths are {sorted(tracked)}"
    )
    for path in GENERATED:
        assert path.startswith("src/"), (
            f"{path} is not under src/, so `jj restore src` would not be the "
            "wrong answer this task exists to catch."
        )


def test_the_uncommitted_work_is_the_four_groups():
    changed = set(lines("diff", "-r", "@", "--name-only"))
    expected = MODIFIED_UNDER_SRC | ADDED_UNDER_SRC | GENERATED | OUTSIDE_SRC
    assert changed == expected, (
        f"Unexpected uncommitted work.\n  expected: {sorted(expected)}\n"
        f"  found:    {sorted(changed)}"
    )


def test_both_halves_of_src_are_dirty():
    """Neither half of the boundary is trivially satisfied at the start."""
    for group, what in ((MODIFIED_UNDER_SRC | ADDED_UNDER_SRC, "outside generated"),
                        (GENERATED, "the generated tree")):
        changed = set(lines("diff", "-r", "@", "--name-only"))
        assert group <= changed, (
            f"the uncommitted work must touch src/ {what}; it does not."
        )


def test_the_added_files_are_new_in_the_working_copy():
    """`src/api/refunds.py` and `src/generated/webhooks.py` are additions."""
    parent = set(lines("file", "list", "-r", "@-"))
    for path in ADDED_UNDER_SRC | {"src/generated/webhooks.py"}:
        assert path not in parent, (
            f"{path} should not exist in the last commit; it is meant to be a "
            "file the uncommitted work added."
        )


def test_the_working_copy_is_undescribed_and_not_empty():
    assert lines("log", "-r", "@", "--no-graph", "-T", 'empty ++ "\\n"') == ["false"]
    assert lines("log", "-r", "@", "--no-graph",
                 "-T", '"[" ++ description ++ "]\\n"') == ["[]"]


def test_the_files_are_on_disk():
    for path in MODIFIED_UNDER_SRC | ADDED_UNDER_SRC | GENERATED | OUTSIDE_SRC:
        assert os.path.isfile(os.path.join(PROJECT_DIR, path)), (
            f"{path} is missing from the working directory."
        )
