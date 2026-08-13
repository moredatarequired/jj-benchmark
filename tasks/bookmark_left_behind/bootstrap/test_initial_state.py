"""Bootstrap check for the bookmark_left_behind task.

Asserts the starting state the request depends on: a bare origin holding
`main` and `rate-limit` as they were three commits ago, a local `rate-limit`
that is tracked and has not moved since, three described commits of work above
it, and -- the invariant the whole task is -- that the two obvious pushes exit 0
having published nothing.

Each assertion corresponds to one of the six fixture invariants written out in
environment/Dockerfile. The push probes are read-only in effect: they are the
measured no-ops, and if either of them ever stops being a no-op the task has
changed and this fails at build time.
"""

import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/checkout-api"
ORIGIN_DIR = "/home/user/checkout-api.git"
BOOKMARK = "rate-limit"
BOOKMARK_WAS_ON = "add a token bucket to the client"
WORK = (
    "read the rate limit from config",
    "refill the bucket between attempts",
    "add tests for the token bucket",
)


def jj(*args):
    return subprocess.run(
        ["jj", *args], cwd=PROJECT_DIR, capture_output=True, text=True
    )


def lines(*args):
    result = jj(*args)
    assert result.returncode == 0, f"jj {' '.join(args)} failed: {result.stderr}"
    return [line for line in result.stdout.splitlines() if line]


def git_origin(*args):
    return subprocess.run(
        ["git", "--git-dir", ORIGIN_DIR, *args], capture_output=True, text=True
    )


def test_jj_binary_available():
    assert shutil.which("jj") is not None, "jj binary not found in PATH."


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), f"{PROJECT_DIR} does not exist."


def test_jj_repo_initialized():
    result = jj("status")
    assert result.returncode == 0, (
        f"jj status failed, not a jj repository. Error: {result.stderr}"
    )


def test_the_bare_origin_exists():
    """Invariant 4: the remote is on disk, so nothing here needs a network."""
    assert os.path.isdir(ORIGIN_DIR), f"{ORIGIN_DIR} does not exist."
    result = git_origin("rev-parse", "--is-bare-repository")
    assert result.stdout.strip() == "true", (
        f"{ORIGIN_DIR} is not a bare git repository: {result.stdout.strip()!r}"
    )


def test_history_shape():
    found = lines("log", "-r", "::@ ~ root()", "--no-graph", "--reversed",
                  "-T", '"[" ++ description.first_line() ++ "]\\n"')
    assert found == [
        "[add the charge endpoint]",
        "[route charges through handlers]",
        f"[{BOOKMARK_WAS_ON}]",
    ] + [f"[{d}]" for d in WORK], f"Unexpected starting history: {found}"


def test_the_bookmark_is_three_commits_behind_the_work():
    """Invariant 1: the bookmark did not follow the commits."""
    on = lines("log", "-r", f'bookmarks(exact:"{BOOKMARK}")', "--no-graph",
               "-T", 'description.first_line() ++ "\\n"')
    assert on == [BOOKMARK_WAS_ON], (
        f"Expected `{BOOKMARK}` on `{BOOKMARK_WAS_ON}`; it is on {on}."
    )
    above = lines("log", "-r",
                  f'descendants(bookmarks(exact:"{BOOKMARK}")) '
                  f'~ bookmarks(exact:"{BOOKMARK}")',
                  "--no-graph", "--reversed",
                  "-T", 'description.first_line() ++ "\\n"')
    assert above == list(WORK), (
        f"Expected exactly the three commits {list(WORK)} above the bookmark; "
        f"found {above}."
    )


def test_both_bookmarks_are_already_on_the_remote_and_tracked():
    """Invariant 3: nothing here turns on new-bookmark handling.

    `--allow-new` does not exist on jj 0.44 in any case, and `jj git push -b`
    tracks an untracked bookmark by itself -- so a fixture where the bookmark
    was new would be measuring a different thing.
    """
    rows = lines("bookmark", "list", "--all-remotes", "-T",
                 'name ++ "\\x1f" ++ remote ++ "\\n"')
    remotes = {(row.split("\x1f")[0], row.split("\x1f")[1]) for row in rows}
    for name in ("main", BOOKMARK):
        assert (name, "origin") in remotes, (
            f"`{name}` is not tracked on origin; known rows are "
            f"{sorted(remotes)}"
        )
    for name in ("main", BOOKMARK):
        assert git_origin("rev-parse", "--verify",
                          f"refs/heads/{name}").returncode == 0, (
            f"origin has no `{name}` branch."
        )


def test_the_remote_is_three_commits_behind():
    """The work has not been published, which is what the request asks for."""
    result = git_origin("rev-list", f"refs/heads/{BOOKMARK}")
    assert result.returncode == 0, result.stderr
    published = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    for description in WORK:
        commit = lines("log", "-r", f'description(substring:"{description}")',
                       "--no-graph", "-T", 'commit_id ++ "\\n"')[0]
        assert commit not in published, (
            f"`{description}` is already on origin, so there is nothing to push."
        )


def test_the_obvious_pushes_do_nothing_and_say_so_with_exit_0():
    """Invariant 2: the silent success that IS this task.

    Both spellings are run, and both must leave origin byte-identical. If a
    future jj makes either of them publish the work, or fail loudly, the task
    has stopped measuring what it was built to measure and this says so at build
    time.
    """
    before = git_origin("show-ref").stdout
    for args in (("git", "push"), ("git", "push", "-b", BOOKMARK)):
        result = jj(*args)
        assert result.returncode == 0, (
            f"`jj {' '.join(args)}` exited {result.returncode}; the point of "
            f"this fixture is that it SUCCEEDS and publishes nothing: "
            f"{result.stderr.strip()}"
        )
    after = git_origin("show-ref").stdout
    assert after == before, (
        "the obvious pushes changed the remote, so there is no trap left:\n"
        f"before: {before!r}\nafter:  {after!r}"
    )


def test_each_commit_changes_its_own_paths():
    """Invariant 6: folding the three into one is visible in the end state."""
    expected = {
        BOOKMARK_WAS_ON: {"src/client/limits.py"},
        WORK[0]: {"config.toml"},
        WORK[1]: {"src/client/limits.py"},
        WORK[2]: {"tests/test_limits.py"},
    }
    for description, paths in expected.items():
        changed = set(lines("diff", "-r", f'description(substring:"{description}")',
                            "--name-only"))
        assert changed == paths, (
            f"`{description}` should change {sorted(paths)}; it changes "
            f"{sorted(changed)}"
        )


def test_the_working_copy_is_the_described_non_empty_tip():
    """Invariant 5: the D11 guard.

    jj 0.44 silently abandons an empty, undescribed `@` when you `jj edit` or
    `jj new` elsewhere, printing nothing at all. Measured: jj pushes a bookmark
    pointing at `@` without complaint, so a correct solve never has to move off
    it.
    """
    found = lines("log", "-r", "@", "--no-graph", "-T",
                  'description.first_line() ++ "|" ++ if(empty, "empty", "nonempty")'
                  ' ++ "\\n"')
    assert found == [f"{WORK[2]}|nonempty"], (
        f"Expected `@` to be the described, non-empty tip of the work; got "
        f"{found}"
    )
