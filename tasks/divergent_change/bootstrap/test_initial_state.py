"""Bootstrap check for the divergent_change task.

Asserts the starting state the request depends on: exactly one divergent change,
two versions of it under one change id carrying the same description, exactly
one of them holding the repository's only test file, a conflicted `idempotency`
bookmark, and a working copy that is neither of the two.

Each assertion corresponds to one of the six fixture invariants written out in
environment/Dockerfile. They are checked rather than trusted because the prompt
names neither the commit nor the file: both are definite descriptions that only
resolve because the fixture is built this way.
"""

import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/checkout-api"
DIVERGED = "add idempotency key to charge requests"
TEST_FILE = "tests/test_charge.py"


def jj(*args):
    return subprocess.run(
        ["jj", *args], cwd=PROJECT_DIR, capture_output=True, text=True
    )


def lines(*args):
    result = jj(*args)
    assert result.returncode == 0, f"jj {' '.join(args)} failed: {result.stderr}"
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
    """Two commits on main, two versions of one change, one unrelated head."""
    found = lines("log", "-r", "all() ~ root()", "--no-graph",
                  "-T", '"[" ++ description.first_line() ++ "]\\n"')
    assert sorted(found) == sorted([
        "[add the charge endpoint]",
        "[route charges through handlers]",
        "[add idempotency key to charge requests]",
        "[add idempotency key to charge requests]",
        "[start the rate-limit middleware]",
    ]), f"Unexpected starting history: {found}"
    ancestry = lines("log", "-r", '::bookmarks(exact:"main")', "--no-graph",
                     "--reversed", "-T",
                     '"[" ++ description.first_line() ++ "]\\n"')
    assert ancestry == [
        "[]",
        "[add the charge endpoint]",
        "[route charges through handlers]",
    ], f"Unexpected main ancestry: {ancestry}"


def test_exactly_one_divergent_change():
    """Invariant 1: `one commit is showing twice` names one thing."""
    divergent = lines("log", "-r", "all() ~ root()", "--no-graph", "-T",
                      'if(divergent, change_id ++ "\\n", "")')
    assert len(divergent) == 2, (
        f"Expected exactly two divergent commits; found {len(divergent)}. "
        "The request says `one commit is showing twice`, which is only a "
        "definite description while exactly one change is divergent."
    )
    assert len(set(divergent)) == 1, (
        f"The divergent commits carry {len(set(divergent))} distinct change "
        "ids, so more than one change is divergent."
    )


def test_both_versions_carry_the_same_description():
    """Invariant 2: it is one change recorded twice, not two commits."""
    descriptions = lines("log", "-r", "all() ~ root()", "--no-graph", "-T",
                         'if(divergent, description.first_line() ++ "\\n", "")')
    assert descriptions == [DIVERGED, DIVERGED], (
        f"Expected both versions to be described {DIVERGED!r}; got "
        f"{descriptions}. Differing descriptions would read as two commits "
        "rather than one commit showing twice."
    )


def test_exactly_one_version_carries_the_only_test_file():
    """Invariant 3: `the copy with the tests` identifies one version."""
    everywhere = lines("log", "-r", "all() ~ root()", "--no-graph", "-T",
                       'change_id ++ "\\n"')
    with_tests = lines("log", "-r", f'files("{TEST_FILE}")', "--no-graph",
                       "-T", 'commit_id ++ "\\n"')
    assert len(with_tests) == 1, (
        f"Expected exactly one commit to hold {TEST_FILE}; {len(with_tests)} "
        "do."
    )
    any_test = lines("log", "-r", 'files("tests")', "--no-graph", "-T",
                     'commit_id ++ "\\n"')
    assert any_test == with_tests, (
        f"{TEST_FILE} must be the repository's only test file, so that `the "
        f"copy with the tests` is unambiguous; tests/ appears in "
        f"{len(any_test)} commit(s)."
    )
    assert len(everywhere) == 5, f"Unexpected commit count: {len(everywhere)}"


def test_the_offsets_are_the_trap_way_round():
    """Invariant 4: `/0` is the version WITHOUT the tests.

    `X/N` indexes every version ever recorded for X, hidden ones included,
    newest first -- so `/0` is the one built last. Here that is deliberately the
    wrong one to keep, which is what makes picking by offset a coin flip that
    lands badly. Asserted here so that a rebuild which reorders the two fails at
    build time rather than quietly removing the trap. Nothing in
    tests/test_final_state.py mentions an offset.
    """
    change_id = lines("log", "-r", 'files("%s")' % TEST_FILE, "--no-graph",
                      "-T", 'change_id ++ "\\n"')[0]
    zero = lines("log", "-r", f"{change_id[:12]}/0", "--no-graph", "-T",
                 'commit_id ++ "\\n"')
    one = lines("log", "-r", f"{change_id[:12]}/1", "--no-graph", "-T",
                'commit_id ++ "\\n"')
    with_tests = lines("log", "-r", f'files("{TEST_FILE}")', "--no-graph",
                       "-T", 'commit_id ++ "\\n"')
    assert one == with_tests, (
        "Expected the version WITH the tests to be at offset /1; it is not. "
        f"/0={zero} /1={one} with_tests={with_tests}"
    )
    assert zero != with_tests, (
        "Expected offset /0 to be the version WITHOUT the tests, so that an "
        "agent picking by offset picks wrong."
    )


def test_the_bookmark_is_conflicted():
    """Invariant 5: `idempotency` cannot say which version it means."""
    rows = lines("bookmark", "list", "--all-remotes", "-T",
                 'name ++ "\\x1f" ++ remote ++ "\\x1f" '
                 '++ if(conflict, "conflict", "clean") ++ "\\n"')
    local = {}
    for row in rows:
        name, remote, state = row.split("\x1f")
        if not remote:
            local[name] = state
    assert local.get("idempotency") == "conflict", (
        f"Expected the local `idempotency` bookmark to be conflicted; local "
        f"bookmarks are {local}."
    )
    assert local.get("main") == "clean" and local.get("rate-limit") == "clean", (
        f"Only `idempotency` may be conflicted; local bookmarks are {local}."
    )


def test_the_working_copy_is_a_described_non_empty_commit_elsewhere():
    """Invariant 6: the D11 guard, and `@` is not one of the two versions.

    jj 0.44 silently abandons an empty, undescribed `@` when you `jj edit` or
    `jj new` elsewhere -- printing nothing at all -- and inspecting the two
    versions is the first thing a solve does. A described, non-empty `@` on an
    unrelated head cannot be lost that way.
    """
    found = lines("log", "-r", "@", "--no-graph", "-T",
                  'description.first_line() ++ "|" ++ if(empty, "empty", "nonempty") '
                  '++ "|" ++ if(divergent, "divergent", "single") ++ "\\n"')
    assert found == ["start the rate-limit middleware|nonempty|single"], (
        f"Expected `@` to be the described, non-empty rate-limit head; got "
        f"{found}"
    )
