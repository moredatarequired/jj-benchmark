"""Bootstrap check for the unmerged_tips task.

Asserts the starting state that makes the request answerable and the two cheap
wrong revsets wrong:

  * four heads sit outside `::main`, and exactly one of them carries no bookmark
    at all -- so listing bookmarks misses it;
  * two bookmarks (`retry-backoff`, `release/2.4`) are already inside `::main`
    -- so listing bookmarks also returns two commits that do not belong;
  * `main` is itself a head -- so `heads(all())` returns one commit too many;
  * `@` is one of the four answers, described and non-empty, so producing the
    answer in the working copy does not move the answer.

Each of those is a property of the fixture the prompt leans on. If a future edit
breaks one, the prompt stops having a single right answer, and this fails rather
than letting that ship.
"""

import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/checkout-api"

UNMERGED_TIPS = {
    "cap charges per account",
    "refresh oauth tokens before they expire",
    "spike: batch settlement into one payout",
    "return 409 on duplicate keys",
}
MAIN = "note the retry behaviour in the changelog"
MERGED_TIP = "retry failed charges with backoff"


def jj(*args):
    return subprocess.run(
        ["jj", *args], cwd=PROJECT_DIR, capture_output=True, text=True
    )


def lines(*args):
    result = jj(*args)
    assert result.returncode == 0, f"`jj {' '.join(args)}` failed: {result.stderr}"
    return [line for line in result.stdout.splitlines() if line]


def descriptions(revset):
    return set(lines("log", "-r", revset, "--no-graph",
                     "-T", 'description.first_line() ++ "\\n"'))


def test_jj_binary_available():
    assert shutil.which("jj") is not None, "jj binary not found in PATH."


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), f"{PROJECT_DIR} does not exist."


def test_jj_repo_initialized():
    result = jj("status")
    assert result.returncode == 0, f"not a jj repository: {result.stderr}"


def test_four_heads_sit_outside_main():
    assert descriptions("heads(main..)") == UNMERGED_TIPS, (
        f"Unexpected unmerged tips: {descriptions('heads(main..)')}"
    )


def test_one_of_them_carries_no_bookmark():
    """Listing bookmarks instead of heads has to give a wrong answer."""
    unbookmarked = descriptions("heads(main..) ~ bookmarks()")
    assert unbookmarked == {"spike: batch settlement into one payout"}, (
        f"exactly one unmerged tip should have no bookmark; found {unbookmarked}"
    )


def test_two_bookmarks_are_already_inside_main():
    """...and in the other direction, listing bookmarks has to over-answer."""
    named = {}
    for row in lines("bookmark", "list", "-T",
                     'name ++ "\\t" ++ normal_target.description().first_line() ++ "\\n"'):
        name, _, description = row.partition("\t")
        named[name] = description
    assert named == {
        "main": MAIN,
        "retry-backoff": MERGED_TIP,
        "release/2.4": MERGED_TIP,
        "rate-limit": "cap charges per account",
        "oauth-refresh": "refresh oauth tokens before they expire",
        "idempotency": "return 409 on duplicate keys",
    }, f"Unexpected bookmarks: {named}"
    assert MERGED_TIP in descriptions("::main"), (
        "`retry-backoff` / `release/2.4` must already be part of main."
    )


def test_main_is_itself_a_head():
    """So `heads(all())` returns five commits where the answer is four."""
    assert MAIN in descriptions("heads(all())"), (
        "`main` should be a head, so that heads(all()) is a wrong answer."
    )
    assert len(descriptions("heads(all())")) == 5, (
        f"expected five heads in all(); found {descriptions('heads(all())')}"
    )


def test_the_working_copy_is_one_of_the_four_and_is_not_empty():
    """Writing the answer into `@` must not change what the answer is."""
    assert descriptions("@") == {"return 409 on duplicate keys"}, (
        f"`@` should be the idempotency tip; it is {descriptions('@')}"
    )
    assert lines("log", "-r", "@", "--no-graph", "-T", 'empty ++ "\\n"') == ["false"], (
        "`@` must carry content, so that jj cannot abandon it when the agent "
        "moves off it."
    )


def test_the_answer_file_does_not_exist_yet():
    assert not os.path.exists(os.path.join(PROJECT_DIR, "unmerged.txt")), (
        "unmerged.txt should not exist before the agent runs."
    )
