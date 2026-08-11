"""Verifier for the log_template_author task.

The task asks for /home/user/project/get_author.sh to hold a `jj log` command
that prints the author of the working-copy commit as `Author: Name <email>`.
Checking only that the script prints that string scores
`echo 'Author: Test User <test@example.com>'` as a solve, which exercises no jj
templating at all -- and the instruction's own constraint ("must contain the
`jj log` command") went unenforced.

The load-bearing check here is test_output_follows_the_repository_identity: it
makes the answer depend on the repository. It adds a commit authored by a
throwaway identity supplied through JJ_USER / JJ_EMAIL, re-runs the script, and
requires the output to track that new identity. A hardcoded string cannot
follow; `jj log` reading `@` does. The environment variables are used instead of
`jj config set` on purpose, so that the repo's user.name / user.email are left
saying "Test User" throughout -- a script that shells out to
`jj config get user.email` rather than templating a commit is caught too.

The probe is reversible: the working copy is snapshotted first (so the restore
point contains whatever the agent left on disk), the baseline operation id is
recorded, and `jj op restore` puts the repository back before the test returns.
The original exact-output assertion is checked before the mutation and again
after the restore.

No network, python3 stdlib + pytest only.
"""

import os
import re
import subprocess

import pytest

PROJECT_DIR = "/home/user/project"
SCRIPT_NAME = "get_author.sh"
SCRIPT_PATH = os.path.join(PROJECT_DIR, SCRIPT_NAME)

# The identity the bootstrap configures, and therefore the author of every
# commit that exists when the agent starts.
EXPECTED_OUTPUT = "Author: Test User <test@example.com>\n"

# A throwaway identity for the probe. Not in any config file: passed to one jj
# invocation through the environment, which overrides user.name / user.email
# without changing them. .invalid is reserved by RFC 2606, so nothing resolves.
PROBE_NAME = "Verifier Probe"
PROBE_EMAIL = "probe@verifier.invalid"
PROBE_OUTPUT = f"Author: {PROBE_NAME} <{PROBE_EMAIL}>\n"

# `jj` and `log` on one line, with room for global flags in between
# (`jj --repository . log`, `jj log -r @ --no-graph -T ...`, ...).
JJ_LOG_RE = re.compile(r"\bjj\b[^\n]*\blog\b")


def clean_env(**overrides):
    """The ambient environment with any inherited jj identity stripped out.

    The script must be re-run with no JJ_USER / JJ_EMAIL set, or a script that
    reads the identity from its own environment instead of from the repository
    would pass the probe.
    """
    env = {k: v for k, v in os.environ.items() if k not in ("JJ_USER", "JJ_EMAIL")}
    env.update(overrides)
    return env


def run_script():
    """Run the agent's script exactly as the task describes and return stdout."""
    try:
        result = subprocess.run(
            [f"./{SCRIPT_NAME}"],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            env=clean_env(),
        )
    except OSError as exc:
        pytest.fail(f"Could not run {SCRIPT_PATH}: {exc}")
    if result.returncode != 0:
        pytest.fail(
            f"./{SCRIPT_NAME} exited with status {result.returncode}.\n"
            f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )
    return result.stdout


def jj(*args, env=None):
    """Run a jj command in the project, asserting it succeeded."""
    result = subprocess.run(
        ["jj", *args],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        env=clean_env() if env is None else env,
    )
    assert result.returncode == 0, (
        f"`jj {' '.join(args)}` failed with status {result.returncode}: "
        f"{result.stderr.strip()}"
    )
    return result.stdout


def current_operation_id():
    return jj(
        "op", "log", "--no-graph", "--ignore-working-copy", "-n", "1", "-T", "id"
    ).strip()


def test_script_exists_and_executable():
    assert os.path.isfile(SCRIPT_PATH), f"Script {SCRIPT_PATH} does not exist."
    assert os.access(SCRIPT_PATH, os.X_OK), f"Script {SCRIPT_PATH} is not executable."


def test_script_output():
    """The original assertion: the exact required output, before any mutation."""
    output = run_script()
    assert output == EXPECTED_OUTPUT, (
        f"Expected {EXPECTED_OUTPUT!r} from ./{SCRIPT_NAME}, got {output!r}."
    )


def test_script_contains_a_jj_log_command():
    """The constraint the instruction states but nothing checked.

    A text check is weak on its own -- it says nothing about where the printed
    string came from, which is what
    test_output_follows_the_repository_identity is for -- but it does reject a
    script that never mentions jj, and the constraint is stated in the
    instruction, so it is fair to hold the script to it.
    """
    assert os.path.isfile(SCRIPT_PATH), f"Script {SCRIPT_PATH} does not exist."
    with open(SCRIPT_PATH, "r", errors="replace") as handle:
        text = handle.read()
    assert re.search(r"\bjj\b", text), (
        f"{SCRIPT_PATH} never invokes `jj`:\n{text}"
    )
    assert JJ_LOG_RE.search(text), (
        f"{SCRIPT_PATH} contains no `jj log` command, which the task requires:\n"
        f"{text}"
    )


def test_output_follows_the_repository_identity():
    """The script's output must come from the repository, not from a literal.

    Give the working-copy commit a different author and the output has to
    change with it. Everything is put back before this test returns, so the
    repository the other assertions look at is the one the agent left.
    """
    assert os.path.isfile(SCRIPT_PATH), f"Script {SCRIPT_PATH} does not exist."

    # Keep a copy of the script: `jj op restore` resets the working copy, and
    # this test must not be able to destroy the artifact it is grading.
    with open(SCRIPT_PATH, "rb") as handle:
        script_bytes = handle.read()
    script_mode = os.stat(SCRIPT_PATH).st_mode

    baseline = run_script()
    assert baseline == EXPECTED_OUTPUT, (
        f"Expected {EXPECTED_OUTPUT!r} from ./{SCRIPT_NAME} before the probe, "
        f"got {baseline!r}."
    )

    # Snapshot the working copy first, so the operation restored at the end
    # already contains whatever the agent left in the working directory. Without
    # this, restoring to a pre-snapshot operation deletes untracked-then-tracked
    # files -- including get_author.sh itself.
    jj("status")
    baseline_op = current_operation_id()
    assert baseline_op, "Could not read the current operation id from `jj op log`."

    try:
        # A new working-copy commit whose author is the probe identity. jj takes
        # JJ_USER / JJ_EMAIL over user.name / user.email, so the repo config
        # still says "Test User <test@example.com>" while `@`'s author does not.
        jj(
            "new",
            "-m",
            "verifier: author probe",
            env=clean_env(JJ_USER=PROBE_NAME, JJ_EMAIL=PROBE_EMAIL),
        )

        recorded = jj(
            "log", "-r", "@", "--no-graph", "--ignore-working-copy",
            "-T", 'author.name() ++ " <" ++ author.email() ++ ">"',
        ).strip()
        assert recorded == f"{PROBE_NAME} <{PROBE_EMAIL}>", (
            "Setup check: the probe commit's author is "
            f"{recorded!r}, expected {PROBE_NAME + ' <' + PROBE_EMAIL + '>'!r}."
        )

        probed = run_script()
        assert probed == PROBE_OUTPUT, (
            f"./{SCRIPT_NAME} printed {probed!r} after the author of the "
            f"working-copy commit (@) was changed to {PROBE_NAME} "
            f"<{PROBE_EMAIL}>; expected {PROBE_OUTPUT!r}. The script's output "
            "does not come from the repository -- a `jj log` template reading "
            "@'s author would have followed the change, so the string is "
            "hardcoded, or is read from somewhere other than the commit."
        )
    finally:
        restore = subprocess.run(
            ["jj", "op", "restore", baseline_op],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            env=clean_env(),
        )
        if not os.path.isfile(SCRIPT_PATH):
            with open(SCRIPT_PATH, "wb") as handle:
                handle.write(script_bytes)
            os.chmod(SCRIPT_PATH, script_mode)

    assert restore.returncode == 0, (
        f"Could not restore the repository to operation {baseline_op[:12]}: "
        f"{restore.stderr.strip()}"
    )

    after = run_script()
    assert after == EXPECTED_OUTPUT, (
        f"After the probe was rolled back, ./{SCRIPT_NAME} printed {after!r}, "
        f"expected {EXPECTED_OUTPUT!r}."
    )
