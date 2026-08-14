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


# Exactly what environment/Dockerfile writes into `add the charge endpoint`,
# byte for byte. The same seven lines in the same order ship in all four
# fixtures of this task set -- sha256
# 667e996c96b4b8fcd40525cb2e3b3026a1da94f3ca89eac16d6bf1d761b093ff. The
# backslash on `\#*#` is load-bearing: a gitignore line starting with `#` is a
# comment, so the unescaped spelling matches nothing at all.
GITIGNORE = "__pycache__/\n*.pyc\n.pytest_cache/\n*~\n*.sw[a-p]\n\\#*#\n.#*\n"
EARLIEST = "add the charge endpoint"

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


def test_the_gitignore_is_in_force_from_the_earliest_commit():
    """The .gitignore's PLACEMENT is load-bearing, so it is checked, not trusted.

    jj 0.44 auto-tracks new files. With no ignore in force, a `__pycache__`
    .pyc from running the project's own tests -- or a `charge.py~` an editor
    left beside a file the agent read -- joins whatever commit `@` is sitting
    on and is then graded as work. Measured on this image before the file
    existed, that cost an otherwise perfect solve 0.667.

    `add the charge endpoint` is the only commit below every path-set assertion
    in tests/test_final_state.py and an ancestor of every head in the
    repository, so committing the .gitignore there is what puts it in force
    everywhere the grading looks. Moving it even one commit later fails
    nothing and moves no score -- measured on exactly that image, this
    task's vacuity floor is unchanged, the same count and the same test
    names as the fixture as shipped. That SILENCE is the reason it is
    asserted here: a move costs real coverage and nothing in CI would ever
    report it. So it is checked in four steps, in the order they can break:
    the earliest commit is the one we think it is; every other commit
    descends from it; it carries this exact .gitignore; and -- since being
    born there does not keep it there -- so does every other commit.
    """
    earliest = lines("log", "-r", "roots(all() ~ root())", "--no-graph",
                     "-T", 'description.first_line() ++ "\\n"')
    assert earliest == [EARLIEST], (
        f"Expected exactly one earliest commit, `{EARLIEST}`; the roots of this "
        f"repository are {earliest}. The .gitignore rides on that commit."
    )
    uncovered = lines("log", "-r",
                      "all() ~ root() ~ descendants(roots(all() ~ root()))",
                      "--no-graph", "-T", 'description.first_line() ++ "\\n"')
    assert uncovered == [], (
        f"{uncovered} do not descend from `{EARLIEST}`, so the .gitignore "
        "committed there is not in force for them."
    )
    shown = jj("file", "show", "-r", "roots(all() ~ root())", ".gitignore")
    assert shown.returncode == 0, (
        f"`{EARLIEST}` has no .gitignore in its tree: {shown.stderr}. If it was "
        "moved to a later commit, move it back -- see environment/Dockerfile."
    )
    assert shown.stdout == GITIGNORE, (
        f"The .gitignore in `{EARLIEST}` is {shown.stdout!r}; this fixture "
        f"ships {GITIGNORE!r}, identical across all four tasks in this set."
    )
    # BIRTH IS NOT FORCE, and the three checks above only establish birth. They
    # say the file was INTRODUCED in the earliest commit and that every commit
    # descends from that one; neither stops a later commit from emptying,
    # replacing or deleting it, after which every descendant inherits the hole
    # and `@` is unprotected wherever the agent parks it. Measured: a control
    # with these lines in commit 1 and the file truncated in commit 2 passes
    # all three checks above and still costs a correct solve its full score.
    # So read the file back out of EVERY commit -- which covers the heads, the
    # commits the grading actually walks, as well as the root.
    for row in lines("log", "-r", "all() ~ root()", "--no-graph",
                     "-T", 'commit_id ++ "\\x1f" ++ description.first_line() ++ "\\n"'):
        commit, _, description = row.partition("\x1f")
        shown = jj("file", "show", "-r", commit, ".gitignore")
        assert shown.returncode == 0, (
            f"`{description}` ({commit[:12]}) has no .gitignore in its tree: "
            f"{shown.stderr}. It is committed in `{EARLIEST}` and nothing in "
            "this fixture may remove it -- see environment/Dockerfile."
        )
        assert shown.stdout == GITIGNORE, (
            f"The .gitignore in `{description}` ({commit[:12]}) is "
            f"{shown.stdout!r}; this fixture ships {GITIGNORE!r} in every "
            "commit, identical across all four tasks in this set."
        )
