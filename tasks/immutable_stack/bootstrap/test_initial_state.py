"""Bootstrap check for the immutable_stack task.

Asserts the starting state the request depends on: a four-commit stack above
main, a repo-scoped `immutable_heads()` alias that covers main AND the first
three commits of that stack, a reword target that jj actually refuses to
rewrite, and -- the invariant that makes the second half of the prompt bite --
no git remote, so deleting the alias would leave main protected by nothing.

Each assertion corresponds to one of the seven fixture invariants written out in
environment/Dockerfile.
"""

import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/checkout-api"
OLD_DESCRIPTION = "fix nonce handling"
TARGET_PATH = "src/api/nonce_store.py"

STACK = (
    "record retry attempts in the charge metrics",
    OLD_DESCRIPTION,
    "reuse the nonce on retried charges",
    "note the nonce work in the changelog",
)
PROTECTED = (
    "add the charge endpoint",
    "route charges through handlers",
    "issue a nonce with every charge",
)


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
    found = lines("log", "-r", "::@ ~ root()", "--no-graph", "--reversed",
                  "-T", '"[" ++ description.first_line() ++ "]\\n"')
    assert found == [f"[{d}]" for d in PROTECTED + STACK], (
        f"Unexpected starting history: {found}"
    )


def test_the_alias_is_the_over_broad_one():
    """Invariant 1: `bookmarks()`, set repo-scoped, is what blocks the stack."""
    result = jj("config", "get", 'revset-aliases."immutable_heads()"')
    assert result.returncode == 0, (
        f"no immutable_heads() alias is configured: {result.stderr}"
    )
    assert result.stdout.strip() == "bookmarks()", (
        f"Expected the alias to be `bookmarks()`; it is "
        f"{result.stdout.strip()!r}. tests/test_final_state.py never reads this "
        "value -- it evaluates the alias -- but the task is only the task while "
        "the starting alias is the over-broad one."
    )
    path = jj("config", "path", "--repo")
    assert path.returncode == 0 and path.stdout.strip(), (
        "there is no repo-scoped config path; the alias must be set with "
        "`jj config set --repo`, which on jj 0.44 writes under "
        "$HOME/.config/jj/repos/<20-hex>/ and NOT to .jj/repo/config.toml."
    )
    assert os.path.isfile(path.stdout.strip()), (
        f"{path.stdout.strip()} does not exist, so the alias is not repo-scoped."
    )


def test_the_immutable_set_covers_main_and_most_of_the_stack():
    """Invariant 1, evaluated: six commits protected, the working copy not."""
    immutable = set(lines("log", "-r", "immutable() ~ root()", "--no-graph",
                          "-T", 'description.first_line() ++ "\\n"'))
    assert immutable == set(PROTECTED) | set(STACK[:3]), (
        f"Expected main and the first three stack commits to be immutable; "
        f"immutable() holds {sorted(immutable)}."
    )
    mutable = set(lines("log", "-r", "mutable()", "--no-graph",
                        "-T", 'description.first_line() ++ "\\n"'))
    assert mutable == {STACK[3]}, (
        f"Expected only the working copy to be mutable; mutable() holds "
        f"{sorted(mutable)}. `@` is deliberately outside the immutable set so "
        "the agent is blocked on the stack rather than on everything."
    )


def test_the_reword_is_actually_refused():
    """The refusal is the entry point, so it is checked rather than assumed."""
    result = jj("describe", "-r", f'description(substring:"{OLD_DESCRIPTION}")',
                "-m", "handle nonces on retried charges")
    assert result.returncode != 0, (
        "jj allowed the reword on the untouched image, so there is no obstacle "
        "and no task."
    )
    assert "immutable" in result.stderr.lower(), (
        f"the reword failed for a reason other than immutability: "
        f"{result.stderr.strip()}"
    )


def test_there_is_no_git_remote():
    """Invariant 3: deleting the alias must actually unprotect main.

    jj's default `immutable_heads()` is `trunk() | tags() |
    untracked_remote_bookmarks()`, and `trunk()` falls back to `root()` when
    there is no origin. Add a remote to this fixture and "delete the alias"
    becomes a correct answer, which removes half the discrimination.
    """
    remotes = lines("git", "remote", "list")
    assert remotes == [], f"Expected no git remote; found {remotes}"


def test_the_reword_target_owns_a_unique_path():
    """Invariant 7: the content-based fallback names exactly one commit.

    tests/test_final_state.py cannot fall back to
    `description(substring:"fix nonce handling")` for this commit, because the
    task is to change that description.
    """
    found = lines("log", "-r", f'files("{TARGET_PATH}")', "--no-graph", "-T",
                  'description.first_line() ++ "\\n"')
    assert found == [OLD_DESCRIPTION], (
        f"Expected {TARGET_PATH} to be touched by exactly one commit, "
        f"`{OLD_DESCRIPTION}`; it is touched by {found}."
    )


def test_the_bookmark_stopped_below_the_tip():
    """Invariant 5: `retry-backoff` is on the third commit, not the fourth."""
    found = lines("log", "-r", 'bookmarks(exact:"retry-backoff")', "--no-graph",
                  "-T", 'description.first_line() ++ "\\n"')
    assert found == [STACK[2]], (
        f"Expected `retry-backoff` on `{STACK[2]}`; it is on {found}."
    )


def test_the_working_copy_is_described_and_not_empty():
    """Invariant 6: the D11 guard.

    jj 0.44 silently abandons an empty, undescribed `@` when you `jj edit`
    elsewhere -- printing nothing at all -- and `jj edit` on the reword target
    is a plausible first move.
    """
    found = lines("log", "-r", "@", "--no-graph", "-T",
                  'description.first_line() ++ "|" ++ if(empty, "empty", "nonempty")'
                  ' ++ "\\n"')
    assert found == [f"{STACK[3]}|nonempty"], (
        f"Expected `@` to be the described, non-empty stack tip; got {found}"
    )


def test_each_stack_commit_changes_its_own_paths():
    expected = {
        STACK[0]: {"src/api/metrics.py"},
        STACK[1]: {"src/api/nonce.py", TARGET_PATH},
        STACK[2]: {"config.toml", "src/client/retry.py"},
        STACK[3]: {"CHANGELOG.md"},
    }
    for description, paths in expected.items():
        changed = set(lines("diff", "-r", f'description(substring:"{description}")',
                            "--name-only"))
        assert changed == paths, (
            f"`{description}` should change {sorted(paths)}; it changes "
            f"{sorted(changed)}"
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
