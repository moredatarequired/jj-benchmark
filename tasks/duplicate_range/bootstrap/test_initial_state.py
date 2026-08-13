"""Bootstrap check for the duplicate_range task.

Asserts the starting state the request depends on: exactly three contiguous
commits about duplicate keys and no others, unrelated commits both below and
above them, a release branch that is a real fork with its own commit and
nothing descending from it, and a described, non-empty working copy.

Each assertion corresponds to one of the five fixture invariants written out in
environment/Dockerfile. They are checked rather than trusted because the prompt
names neither endpoint of the run: "the three duplicate-key commits" only picks
out a span while the fixture is built this way.
"""

import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/checkout-api"

RUN = (
    "validate the duplicate-key format",
    "return 409 on duplicate keys",
    "add tests for duplicate keys",
)
BELOW_THE_RUN = "add a client-side rate limiter"
MAIN_TIP = "start the 2.5 changelog"
RELEASE_TIP = "pin the 2.4 dependency set"
WORKING_COPY = "sketch the refund endpoint"


# Exactly what environment/Dockerfile writes into `add the charge endpoint`,
# byte for byte. The same six lines in the same order ship in all four fixtures
# of this task set.
GITIGNORE = "__pycache__/\n*.pyc\n.pytest_cache/\n*~\n*.swp\n*.swo\n"
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
    """main's line, with the run in the middle and unrelated work either side."""
    found = lines("log", "-r", "::@ ~ root()", "--no-graph", "--reversed",
                  "-T", '"[" ++ description.first_line() ++ "]\\n"')
    assert found == [
        "[add the charge endpoint]",
        "[route charges through handlers]",
        f"[{BELOW_THE_RUN}]",
        f"[{RUN[0]}]",
        f"[{RUN[1]}]",
        f"[{RUN[2]}]",
        f"[{MAIN_TIP}]",
        f"[{WORKING_COPY}]",
    ], f"Unexpected starting history: {found}"


def test_exactly_three_commits_mention_duplicate_keys():
    """Invariant 1: the run names itself, and names three things."""
    found = lines("log", "-r", 'description(substring:"duplicate")', "--no-graph",
                  "--reversed", "-T", 'description.first_line() ++ "\\n"')
    assert found == list(RUN), (
        f"Expected exactly the three commits {list(RUN)} to mention duplicate "
        f"keys; {found} do. The request says `the three duplicate-key commits`, "
        "which is only a definite description while that is true."
    )


def test_the_run_is_contiguous_and_fenced_by_unrelated_work():
    """Invariant 1: one commit too many or too few is a different end state."""
    span = lines("log", "-r",
                 f'description(substring:"{RUN[0]}")::description(substring:"{RUN[2]}")',
                 "--no-graph", "-T", 'description.first_line() ++ "\\n"')
    assert sorted(span) == sorted(RUN), (
        f"The run is not contiguous: the span between its ends holds {span}."
    )
    for neighbour in (BELOW_THE_RUN, MAIN_TIP, WORKING_COPY):
        assert "duplicate" not in neighbour, (
            f"The neighbouring commit {neighbour!r} mentions duplicate keys, so "
            "the run does not name itself."
        )


def test_the_release_branch_is_a_real_fork_with_nothing_on_top():
    """Invariant 2: `onto release/2.4` is a destination, and it is empty above."""
    tip = lines("log", "-r", 'bookmarks(exact:"release/2.4")', "--no-graph",
                "-T", 'description.first_line() ++ "\\n"')
    assert tip == [RELEASE_TIP], (
        f"Expected `release/2.4` on `{RELEASE_TIP}`; it is on {tip}."
    )
    above = lines("log", "-r",
                  'descendants(bookmarks(exact:"release/2.4")) '
                  '~ bookmarks(exact:"release/2.4")',
                  "--no-graph", "-T", 'change_id ++ "\\n"')
    assert above == [], (
        f"Expected nothing to descend from `release/2.4` at handover; "
        f"{len(above)} commit(s) do. That set is how tests/test_final_state.py "
        "finds the copies, so it has to start empty."
    )
    forked = lines("log", "-r",
                   'bookmarks(exact:"release/2.4") & ::bookmarks(exact:"main")',
                   "--no-graph", "-T", 'change_id ++ "\\n"')
    assert forked == [], (
        "`release/2.4` is an ancestor of `main`, so it is a point on main "
        "rather than a branch off it."
    )


def test_the_run_applies_cleanly_on_the_release_branch():
    """Invariant 3: a conflict afterwards is a real failure, not the fixture.

    Two of the three create files the release branch does not have; the third
    appends to src/api/handlers.py, which the release branch has not touched
    since the fork. Checked by path rather than by trial so this stays a
    read-only assertion.
    """
    release_paths = set(lines("diff", "-r",
                              f'description(substring:"{RELEASE_TIP}")',
                              "--name-only"))
    run_paths = set()
    for description in RUN:
        run_paths |= set(lines("diff", "-r",
                               f'description(substring:"{description}")',
                               "--name-only"))
    assert not (release_paths & run_paths), (
        f"The release branch and the run both touch {sorted(release_paths & run_paths)}, "
        "so the copy could conflict."
    )
    assert lines("log", "-r", "conflicts()", "--no-graph",
                 "-T", 'change_id ++ "\\n"') == [], (
        "The repository already holds a conflicted commit."
    )


def test_each_commit_in_the_run_touches_a_distinct_path():
    """Invariant 5: copies can be matched to sources by what they change."""
    expected = {
        RUN[0]: {"src/api/keys.py"},
        RUN[1]: {"src/api/handlers.py"},
        RUN[2]: {"tests/test_duplicate_keys.py"},
    }
    for description, paths in expected.items():
        changed = set(lines("diff", "-r", f'description(substring:"{description}")',
                            "--name-only"))
        assert changed == paths, (
            f"`{description}` should change {sorted(paths)}; it changes "
            f"{sorted(changed)}"
        )


def test_the_working_copy_is_described_and_not_empty():
    """Invariant 4: the D11 guard.

    jj 0.44 silently abandons an empty, undescribed `@` when you `jj edit` or
    `jj new` elsewhere -- printing nothing at all -- and `jj new release/2.4` is
    a plausible first move for a hand-built copy.
    """
    found = lines("log", "-r", "@", "--no-graph", "-T",
                  'description.first_line() ++ "|" ++ if(empty, "empty", "nonempty")'
                  ' ++ "\\n"')
    assert found == [f"{WORKING_COPY}|nonempty"], (
        f"Expected `@` to be the described, non-empty refund sketch; got {found}"
    )


def test_bookmarks():
    found = lines("bookmark", "list", "--all-remotes", "-T",
                  'name ++ "\\x1f" ++ remote ++ "\\n"')
    local = sorted(row.split("\x1f")[0] for row in found if row.endswith("\x1f"))
    assert local == ["main", "release/2.4"], (
        f"Expected exactly the `main` and `release/2.4` bookmarks; got {local}"
    )


def test_the_gitignore_is_in_force_from_the_earliest_commit():
    """The .gitignore's PLACEMENT is load-bearing, so it is checked, not trusted.

    jj 0.44 auto-tracks new files. With no ignore in force, a `__pycache__`
    .pyc from running the project's own tests -- or a `charge.py~` an editor
    left beside a file the agent read -- joins whatever commit `@` is sitting
    on and is then graded as work. Measured on this image before the file
    existed, that cost an otherwise perfect solve 0.000 when `@` had been
    parked on the release line -- the extra file made it non-empty, so it
    counted as a FOURTH copy -- and 0.667 when it had not.

    `add the charge endpoint` is the only commit below every path-set assertion
    in tests/test_final_state.py and an ancestor of both `main` and
    `release/2.4`, so committing the .gitignore there is what puts it in force
    everywhere the grading looks. Moving it even one commit later would not
    fail a verifier loudly -- it would change what
    `test_nothing_else_in_the_repository_moved`, a FLOORED test, sees on an
    untouched image, and so surface as a shifted vacuity floor, which is a much
    harder thing to read back to a cause. So it is asserted here instead, in
    three steps, in the order they can break: the earliest commit is the one we
    think it is; every other commit descends from it; and it carries this exact
    .gitignore.
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
