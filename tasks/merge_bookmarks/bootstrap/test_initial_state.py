"""Bootstrap check for the merge_bookmarks task.

Asserts the starting state the request depends on: two bookmarks off `main`
whose tips each add exactly one block to `config.toml`, no merge commit anywhere
in the repository, and a working copy sitting on `main` with nothing in it.

The one-block-per-side check is the load-bearing one. The prompt says "both
bookmarks' blocks" rather than naming `[ratelimit]` and `[oauth]`, and it has a
single satisfying content only while each tip contributes exactly one block; if
a future edit to the Dockerfile makes a tip touch two, this fails rather than
letting an ambiguous prompt ship.
"""

import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/checkout-api"

BASE_CONFIG = (
    "[server]\n"
    'host = "0.0.0.0"\n'
    "port = 8080\n"
    "\n"
    "[database]\n"
    'url = "postgres://localhost/checkout"\n'
    "pool_size = 10\n"
)
RATELIMIT_BLOCK = "\n[ratelimit]\nper_account_per_minute = 60\nburst = 10\n"
OAUTH_BLOCK = (
    "\n[oauth]\n"
    'token_url = "https://auth.example.com/oauth/token"\n'
    "refresh_margin_seconds = 120\n"
)


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


def test_the_bookmarks_are_where_the_task_says():
    named = {}
    for row in lines("bookmark", "list", "-T",
                     'name ++ "\\t" ++ normal_target.description().first_line() ++ "\\n"'):
        name, _, description = row.partition("\t")
        named[name] = description
    assert named == {
        "main": "extract the http client",
        "rate-limit": "reject charges over the per-account rate limit",
        "oauth-refresh": "refresh oauth tokens before they expire",
    }, f"Unexpected bookmarks: {named}"


def test_neither_bookmark_is_an_ancestor_of_the_other():
    """There is work on both sides that the other does not have."""
    for a, b in (("rate-limit", "oauth-refresh"), ("oauth-refresh", "rate-limit")):
        only = lines("log", "-r", f"{a} ~ ::{b}", "--no-graph",
                     "-T", 'description.first_line() ++ "\\n"')
        assert only, f"`{a}` is already contained in `{b}`."


def test_there_is_no_merge_commit_yet():
    """The capability being measured is not already exercised by the fixture."""
    counts = lines("log", "-r", "all() ~ root()", "--no-graph",
                   "-T", 'parents.len() ++ "\\n"')
    assert set(counts) <= {"1"}, (
        f"some commit already has more than one parent: {counts}"
    )


def test_each_tip_adds_exactly_one_config_block():
    for bookmark, block in (("rate-limit", RATELIMIT_BLOCK),
                            ("oauth-refresh", OAUTH_BLOCK)):
        result = jj("file", "show", "-r", bookmark, "config.toml")
        assert result.returncode == 0, f"config.toml missing at {bookmark}."
        assert result.stdout == BASE_CONFIG + block, (
            f"`{bookmark}` must add exactly one block to config.toml; it has "
            f"{result.stdout!r}"
        )
        # The 2 is config.toml plus exactly one source file -- src/api/limits.py
        # at `rate-limit`, src/client/oauth.py at `oauth-refresh`. `jj diff -r X`
        # is X against its parent, so this count is a property of the TIP commit
        # alone and of nothing below it.
        #
        # That is the only reason the fixture's .gitignore does not show up here:
        # it is written in the first fixture commit ("add the charge endpoint"),
        # which this diff never inspects. Move it to either bookmark tip -- or
        # add any further file to one -- and `changed` becomes 3 and this fails.
        # It is meant to: the count is the guard that each tip stays a
        # single-concern commit, which is what makes the merge the task asks for
        # a clean one. If this ever fails after a fixture edit, put the new file
        # back below the bookmarks rather than raising the number.
        changed = set(lines("diff", "-r", bookmark, "--name-only"))
        assert "config.toml" in changed and len(changed) == 2, (
            f"the `{bookmark}` tip should change config.toml and one source "
            f"file; it changes {sorted(changed)}"
        )


def test_the_working_copy_is_an_empty_change_on_main():
    parents = lines("log", "-r", "@", "--no-graph",
                    "-T", 'parents.map(|p| p.description().first_line()).join(",") ++ "\\n"')
    assert parents == ["extract the http client"], (
        f"`@` should sit on main; its parents are {parents}"
    )
    assert lines("log", "-r", "@", "--no-graph", "-T", 'empty ++ "\\n"') == ["true"], (
        "`@` should be empty at handover."
    )


def test_config_toml_on_disk_is_the_base_version():
    with open(os.path.join(PROJECT_DIR, "config.toml")) as handle:
        assert handle.read() == BASE_CONFIG, (
            "config.toml on disk should be the version on main, with neither "
            "bookmark's block in it."
        )
