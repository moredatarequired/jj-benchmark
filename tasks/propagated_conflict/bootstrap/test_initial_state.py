"""Bootstrap check for the propagated_conflict task.

Asserts the starting state the request depends on: a four-commit branch that
has been rebased onto a main that moved underneath it, exactly one conflicted
path, and a conflict whose origin is the SECOND commit of the four while the
two above it are conflicted only by inheritance.

Each assertion here corresponds to one of the five fixture invariants written
out in environment/Dockerfile. They are checked rather than trusted because the
prompt names neither the file nor the commit nor the two symbols: every one of
those is a definite description that only resolves because the fixture is built
this way.
"""

import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/checkout-api"
CONFLICTED_PATH = "src/client/retry.py"

STACK = (
    "count retry attempts in the charge metrics",
    "make the retry budget configurable",
    "stop retrying once the budget is spent",
    "note the retry budget in the changelog",
)


def jj(*args):
    return subprocess.run(
        ["jj", *args], cwd=PROJECT_DIR, capture_output=True, text=True
    )


def change_ids(revset):
    result = jj("log", "-r", revset, "--no-graph", "-T",
                'description.first_line() ++ "\\n"')
    assert result.returncode == 0, f"jj log failed: {result.stderr}"
    return [line for line in result.stdout.splitlines() if line]


def test_jj_binary_available():
    assert shutil.which("jj") is not None, "jj binary not found in PATH."


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), f"{PROJECT_DIR} does not exist."


def test_jj_repo_initialized():
    result = jj("status")
    assert result.returncode == 0, (
        f"jj status failed, not a jj repository. Error: {result.stderr}"
    )


def test_history_shape():
    """The branch is the four commits, sitting on top of main's new commit."""
    result = jj("log", "-r", "::@ ~ root()", "--no-graph", "--reversed",
                "-T", '"[" ++ description.first_line() ++ "]\\n"')
    assert result.returncode == 0, f"jj log failed: {result.stderr}"
    lines = [line for line in result.stdout.splitlines() if line]
    assert lines == [
        "[add the charge endpoint]",
        "[extract the http client]",
        "[retry failed charges with backoff]",
        "[give the http client an explicit request timeout]",
        "[count retry attempts in the charge metrics]",
        "[make the retry budget configurable]",
        "[stop retrying once the budget is spent]",
        "[note the retry budget in the changelog]",
    ], f"Unexpected starting history: {lines}"


def test_exactly_one_conflicted_path():
    """Invariant 1: `the conflict` names one thing."""
    result = jj("resolve", "--list")
    assert result.returncode == 0, f"jj resolve --list failed: {result.stderr}"
    paths = [line.split()[0] for line in result.stdout.splitlines() if line.strip()]
    assert paths == [CONFLICTED_PATH], (
        f"Expected exactly one conflicted path ({CONFLICTED_PATH}); the "
        f"repository has {paths}. The request says `the conflict`, which is "
        "only a definite description while there is one."
    )


def test_the_conflict_starts_in_the_second_commit_of_the_stack():
    """Invariant 2: one origin, and it is not the first of the four.

    Three commits render conflicted; the first of the four does not. That gap
    between what `jj log` shows and what actually collided is the task.
    """
    conflicted = set(change_ids("conflicts()"))
    assert conflicted == set(STACK[1:]), (
        f"Expected exactly {sorted(STACK[1:])} to be conflicted; "
        f"{sorted(conflicted)} are."
    )
    assert STACK[0] not in conflicted, (
        f"`{STACK[0]}` must rebase cleanly, so that the origin of the conflict "
        "is not simply the bottom of the stack."
    )


def test_the_origin_commit_is_what_collides_with_main():
    """Invariant 3: the two hunks abut, so the union is the only resolution.

    Read off the materialised conflict: main's renamed constant on one side,
    the branch's added constant on the other, and no third party.
    """
    result = jj("file", "show", "-r",
                'description(substring:"make the retry budget configurable")',
                CONFLICTED_PATH)
    assert result.returncode == 0, f"jj file show failed: {result.stderr}"
    body = result.stdout
    assert "<<<<<<< conflict" in body, (
        f"{CONFLICTED_PATH} is not conflicted in the origin commit."
    )
    assert "REQUEST_TIMEOUT = 5.0" in body, (
        "main's renamed constant is not one side of the conflict."
    )
    assert "+RETRY_BUDGET = 30.0" in body, (
        "the branch's added constant is not the other side of the conflict."
    )
    assert body.count("<<<<<<< conflict") == 1, (
        "the file has more than one conflict region; `keeping both sides` "
        "must name a single resolution."
    )


def test_neither_side_alone_is_a_defensible_resolution():
    """Invariant 4: `:ours` and `:theirs` each break the file.

    `with_backoff`'s signature refers to RETRY_BUDGET outside the conflict
    region and the call site refers to REQUEST_TIMEOUT outside it, so dropping
    either side leaves an undefined name behind. Checked here so that a future
    edit to the fixture cannot quietly make one side sufficient.
    """
    result = jj("file", "show", "-r",
                'description(substring:"make the retry budget configurable")',
                CONFLICTED_PATH)
    assert result.returncode == 0, f"jj file show failed: {result.stderr}"
    body = result.stdout
    outside = [
        line for line in body.splitlines()
        if "budget=RETRY_BUDGET" in line or "timeout=REQUEST_TIMEOUT" in line
    ]
    assert len(outside) == 2, (
        "expected both symbols to be referenced from OUTSIDE the conflict "
        f"region, so that neither side can be dropped without breaking the "
        f"file; found {outside}"
    )


def test_the_working_copy_is_the_stack_tip_described_and_not_empty():
    """Invariant 5: the D11 guard.

    jj 0.44 silently abandons an empty, undescribed `@` when you `jj edit`
    elsewhere -- printing nothing at all -- and `jj edit <origin>` is the most
    likely first move here. A described, non-empty `@` cannot be lost that way,
    which is what lets this task ship without an anchor exemption.
    """
    result = jj("log", "-r", "@", "--no-graph", "-T",
                'description.first_line() ++ "|" ++ if(empty, "empty", "nonempty")')
    assert result.returncode == 0, f"jj log failed: {result.stderr}"
    assert result.stdout.strip() == "note the retry budget in the changelog|nonempty", (
        f"Expected `@` to be the described, non-empty stack tip; got "
        f"{result.stdout.strip()!r}"
    )


def test_bookmarks():
    result = jj("bookmark", "list", "--all-remotes")
    assert result.returncode == 0, f"jj bookmark list failed: {result.stderr}"
    names = {line.split(":")[0] for line in result.stdout.splitlines() if ":" in line}
    assert "main" in names and "retry-backoff" in names, (
        f"Expected `main` and `retry-backoff` bookmarks; got {sorted(names)}"
    )
    assert "fork-point" not in names, (
        "the scaffolding bookmark `fork-point` should have been deleted before "
        "handover."
    )


def test_each_stack_commit_changes_its_own_paths():
    """Disjoint diffs, so `carries its own diff` is checkable without content."""
    expected = {
        STACK[0]: {"src/api/metrics.py"},
        STACK[1]: {"config.toml", CONFLICTED_PATH},
        STACK[2]: {CONFLICTED_PATH, "tests/test_retry.py"},
        STACK[3]: {"CHANGELOG.md"},
    }
    for description, paths in expected.items():
        result = jj("diff", "-r", f'description(substring:"{description}")',
                    "--name-only")
        assert result.returncode == 0, f"jj diff failed: {result.stderr}"
        changed = {line for line in result.stdout.splitlines() if line}
        assert changed == paths, (
            f"`{description}` should change {sorted(paths)}; it changes "
            f"{sorted(changed)}"
        )
