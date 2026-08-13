"""Verifier for the restore_interactive task.

The task asks for a file that a mid-stack commit deleted by mistake to be put
back *in that commit*, leaving everything else about the history alone.

Every assertion below is made against repository state -- commit trees, the
paths a commit changes, file contents at a revision -- and never against jj's
human-readable prose. The one place where jj output is parsed at all,
`descriptions()` and `changed_paths()`, uses an explicit template and
`--name-only`, whose output is data (descriptions, paths) rather than English.

REVISION ADDRESSING: WHY THE POSITIONAL REVSETS ARE GONE
=======================================================

The previous version addressed the four commits POSITIONALLY -- `@---` was
`Initial commit`, `@--` was `remove legacy module`, `@-` was `add logging` --
and relied on the floored test_history_shape to pin those positions to the right
commits. That is the wrong place for the check to live, because a floored test
earns no credit: an agent could build a fabricated four-commit chain from
`root()`, park `@` on it, leave the bootstrap's four commits untouched beside it
-- so the session-scoped anchor fixture still holds, nothing having been
destroyed -- and every positional revset would then resolve into the fabrication.
Measured: 6 of 6 scored tests passed that way, i.e. all the credit there is.

So the four graded commits are now resolved by the change ids the BOOTSTRAP gave
them. A jj change id is generated randomly at commit creation and preserved by
rebase / squash / describe, so it names the commit the task handed over and no
commit created afterwards can carry it.

graded() and handover_working_copy() go through anchor.py's fallback resolvers,
which is what keeps this working in CI: bootstrap_anchor.json is a per-build
artifact, gitignored and absent in CI (which always builds cold). When it is
missing the resolver prints that the identity claim is NOT being made and returns
the positional revset this file used before, so every assertion degrades to
exactly its old strength -- never weaker, and never an error.

Test names and count are unchanged, so tests/vacuity_floor.json does not move.
test_history_shape stays floored and is left exactly as it was.
"""

import os
import subprocess

import pytest

from anchor import change_id_or_fallback, working_copy_or_fallback

PROJECT_DIR = "/home/user/myproject"

INITIAL = "Initial commit"
CLEANUP = "remove legacy module"
LOGGING = "add logging"

# The position each commit occupied in the handover chain. Used ONLY as the
# fallback when there is no anchor file, i.e. it reproduces exactly what this
# file asserted before the anchor existed.
FALLBACK_POSITION = {INITIAL: "@---", CLEANUP: "@--", LOGGING: "@-"}

EXPECTED_DESCRIPTIONS = [
    "Initial commit",
    "remove legacy module",
    "add logging",
    "",
]

SETTINGS_TOML = '[server]\nhost = "127.0.0.1"\nport = 8080\n\n[logging]\nlevel = "info"\n'
MAIN_INITIAL = "from legacy import old_helper\n\n\ndef main():\n    print(old_helper())\n"
MAIN_AFTER_CLEANUP = 'def main():\n    print("running")\n'
MAIN_AFTER_LOGGING = (
    "import logging\n\n\ndef main():\n    logging.info(\"start\")\n    print(\"running\")\n"
)
NOTES_TXT = "todo: review the release checklist\n"

_snapshotted = False


def snapshot_working_copy():
    """Take the ONE working-copy snapshot this verifier is allowed, explicitly.

    The bootstrap leaves notes.txt written but unsnapshotted, and the solve may
    add nothing further to the working copy, so `@`'s stored tree only reflects
    the checked-out files once jj snapshots. Every jj call below passes
    --ignore-working-copy -- otherwise the verifier mutates the repository it is
    grading and can disagree with its own second run -- so the snapshot has to be
    taken deliberately, once. It preserves change ids, so it cannot disturb the
    anchor, and it is the same single snapshot the previous version of this file
    took implicitly on its first jj call.
    """
    global _snapshotted
    if not _snapshotted:
        subprocess.run(["jj", "status"], cwd=PROJECT_DIR,
                       capture_output=True, text=True)
        _snapshotted = True


def graded(description):
    """The bootstrap's change id for `description`, or its handover position."""
    return change_id_or_fallback(
        description, FALLBACK_POSITION[description], repo=PROJECT_DIR)


def handover_working_copy():
    """The change id of the `@` the bootstrap handed over, or `@` itself.

    Anchor keys are description first lines and this bootstrap's working copy is
    undescribed, so the workspace name is the only unique key for it.
    """
    return working_copy_or_fallback("@", repo=PROJECT_DIR)


def jj(*args):
    """Run a read-only jj command in the project and return the CompletedProcess.

    --ignore-working-copy on every call: a plain jj read snapshots first, which
    appends an operation and rewrites `@`. See snapshot_working_copy() for the
    one deliberate exception.
    """
    return subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=PROJECT_DIR, capture_output=True, text=True,
    )


def jj_ok(*args):
    result = jj(*args)
    assert result.returncode == 0, (
        f"`jj {' '.join(args)}` failed with exit code {result.returncode}: "
        f"{result.stderr.strip()}"
    )
    return result.stdout


def descriptions(revset):
    """First line of the description of every commit in revset, oldest first.

    Each description is bracketed in the template so that an empty description
    is still a line of output, and so trailing whitespace cannot be lost.
    """
    out = jj_ok(
        "log", "-r", revset, "--no-graph", "--reversed",
        "-T", '"[" ++ description.first_line() ++ "]\\n"',
    )
    lines = [line for line in out.splitlines() if line]
    for line in lines:
        assert line.startswith("[") and line.endswith("]"), (
            f"unexpected line in jj log output: {line!r}"
        )
    return [line[1:-1] for line in lines]


def change_ids(revset):
    out = jj_ok("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\\n"')
    return [line for line in out.splitlines() if line]


def changed_paths(rev):
    """The set of paths a revision changes relative to its parent."""
    out = jj_ok("diff", "-r", rev, "--name-only")
    return {line for line in out.splitlines() if line}


def tree_paths(rev):
    """The set of paths present in a revision's tree."""
    out = jj_ok("file", "list", "-r", rev)
    return {line for line in out.splitlines() if line}


def file_at(rev, path):
    """Contents of path at rev. Fails the test if the path is not there."""
    result = jj("file", "show", "-r", rev, path)
    assert result.returncode == 0, (
        f"`{path}` is not present in revision `{rev}`: {result.stderr.strip()}"
    )
    return result.stdout


def assert_the_handover_working_copy_is_still_checked_out():
    """The bootstrap's working-copy commit must still be `@` or an ancestor of it.

    This is the identity claim that makes the disk-level and working-copy-level
    assertions below mean something: without it they are satisfied by any commit
    with the right tree, including one fabricated from `root()`.

    It used to demand `@` BE that change. That is stricter than the task, and
    strictly so: an agent that runs `jj new` at any point -- to keep the working
    copy clean while it rewrites history, which is an ordinary jj habit and one
    nothing in the request speaks against -- ends on a fresh empty change whose
    parent is the handover commit. The mid-stack fix is then completely correct
    and two of the six scored tests fail on where the agent happened to be
    standing.

    Requiring the handover change to be on `@`'s ancestry keeps every property
    that mattered. A fabricated stack built from `root()` and checked out is not
    a descendant of the handover change, so it still cannot be what gets graded,
    and each caller goes on to assert about the handover change itself rather
    than about `@`.
    """
    snapshot_working_copy()
    handover = handover_working_copy()
    assert change_ids(f"({handover}) & ::@"), (
        f"The working copy the bootstrap handed over ({change_ids(handover)}) "
        f"is not `@` ({change_ids('@')}) and is not an ancestor of it. Fixing "
        "the mid-stack commit rebases the working copy and preserves its change "
        "id, so that change has to still be the one checked out -- or the "
        "parent of wherever the agent finished."
    )
    return handover


def test_history_shape():
    """Exactly the original four commits, in the original order, still exist.

    Empty undescribed commits are excluded from the comparison. They are what
    `jj new` leaves behind, and an agent that starts a fresh change before
    rewriting history -- see
    assert_the_handover_working_copy_is_still_checked_out() -- adds one without
    changing the history in any way a reviewer would call a change. This test is
    floored, so it earns nothing; per tests/test.sh a failing floored test is
    still enough to cap a correct solve below a full mark, so it must not fail
    for something the task never asked about. A commit with content or with a
    description is still counted, which is the case this is here for: work
    parked in a fifth commit rather than folded into the one that dropped the
    file.

    The snapshot is taken here as well as in the working-copy tests: the
    bootstrap leaves notes.txt written but unsnapshotted, so without it the
    handover `@` reads as empty-and-undescribed and would be filtered out of the
    comparison it is supposed to be part of.
    """
    snapshot_working_copy()
    scratch = '(empty() & description(exact:""))'
    chain = descriptions(f"(::@ ~ root()) ~ {scratch}")
    assert chain == EXPECTED_DESCRIPTIONS, (
        "The four commits above the root must still be, oldest first: "
        f"{EXPECTED_DESCRIPTIONS}. Got: {chain}"
    )
    all_commits = descriptions(f"(all() ~ root()) ~ {scratch}")
    assert len(all_commits) == 4, (
        "The repository must still contain exactly four commits above the root "
        f"(empty, undescribed ones aside); found {len(all_commits)}: "
        f"{all_commits}"
    )


def test_settings_restored_into_cleanup_commit():
    """`remove legacy module` contains settings.toml with the original content."""
    cleanup = graded(CLEANUP)
    assert "settings.toml" in tree_paths(cleanup), (
        "`settings.toml` is still missing from the bootstrap's own "
        f"`remove legacy module` commit ({cleanup})."
    )
    assert file_at(cleanup, "settings.toml") == SETTINGS_TOML, (
        f"`settings.toml` in the bootstrap's `remove legacy module` commit "
        f"({cleanup}) does not have the content it has in `Initial commit`."
    )


def test_cleanup_commit_no_longer_deletes_settings():
    """Structural check: that commit does not change settings.toml at all.

    Compared against its parent rather than against a literal, so that a
    solution which "fixed" things by rewriting `Initial commit` instead cannot
    pass; the parent's content is pinned separately below.
    """
    initial, cleanup = graded(INITIAL), graded(CLEANUP)
    assert file_at(initial, "settings.toml") == SETTINGS_TOML, (
        f"`settings.toml` in the bootstrap's `Initial commit` ({initial}) was "
        "modified; it must be left alone."
    )
    assert file_at(cleanup, "settings.toml") == file_at(
        initial, "settings.toml"
    ), (
        f"The bootstrap's `remove legacy module` commit ({cleanup}) still changes "
        "`settings.toml`."
    )
    assert "settings.toml" not in changed_paths(cleanup), (
        f"The bootstrap's `remove legacy module` commit ({cleanup}) must no "
        "longer touch `settings.toml`, but it changes: "
        f"{sorted(changed_paths(cleanup))}"
    )


def test_cleanup_commit_keeps_its_own_changes():
    """The rest of that commit is untouched: legacy.py gone, main.py rewritten."""
    initial, cleanup = graded(INITIAL), graded(CLEANUP)
    assert "legacy.py" in tree_paths(initial), (
        f"`legacy.py` is missing from the bootstrap's `Initial commit` "
        f"({initial}); that commit must be left alone."
    )
    assert file_at(initial, "main.py") == MAIN_INITIAL, (
        f"`main.py` in the bootstrap's `Initial commit` ({initial}) was modified; "
        "it must be left alone."
    )
    assert "legacy.py" not in tree_paths(cleanup), (
        "`legacy.py` must still be deleted by the bootstrap's "
        f"`remove legacy module` commit ({cleanup})."
    )
    assert file_at(cleanup, "main.py") == MAIN_AFTER_CLEANUP, (
        f"The bootstrap's `remove legacy module` commit ({cleanup}) had its "
        "change to `main.py` altered."
    )
    assert changed_paths(cleanup) == {"legacy.py", "main.py"}, (
        f"The bootstrap's `remove legacy module` commit ({cleanup}) must change "
        "exactly `legacy.py` and `main.py`, but it changes: "
        f"{sorted(changed_paths(cleanup))}"
    )


def test_later_commit_intact():
    """`add logging` still records only its own change to main.py."""
    logging_rev = graded(LOGGING)
    assert changed_paths(logging_rev) == {"main.py"}, (
        f"The bootstrap's `add logging` commit ({logging_rev}) must change only "
        f"`main.py`, but it changes: {sorted(changed_paths(logging_rev))}"
    )
    assert file_at(logging_rev, "main.py") == MAIN_AFTER_LOGGING, (
        f"The bootstrap's `add logging` commit ({logging_rev}) had its change to "
        "`main.py` altered."
    )
    assert file_at(logging_rev, "settings.toml") == SETTINGS_TOML, (
        "`settings.toml` must be present with the original content in the "
        f"bootstrap's `add logging` commit ({logging_rev})."
    )
    assert "legacy.py" not in tree_paths(logging_rev), (
        f"`legacy.py` must stay deleted in the bootstrap's `add logging` commit "
        f"({logging_rev})."
    )


def test_working_copy_intact():
    """The working copy still adds notes.txt and nothing else."""
    handover = assert_the_handover_working_copy_is_still_checked_out()
    assert changed_paths(handover) == {"notes.txt"}, (
        "The working copy's only change relative to its parent must be the "
        f"addition of `notes.txt`, but it changes: {sorted(changed_paths(handover))}"
    )
    assert file_at(handover, "notes.txt") == NOTES_TXT, "`notes.txt` was modified."
    assert file_at(handover, "settings.toml") == SETTINGS_TOML, (
        "`settings.toml` must be present with the original content in the "
        "working copy."
    )
    assert file_at(handover, "main.py") == MAIN_AFTER_LOGGING, "`main.py` was modified."
    assert "legacy.py" not in tree_paths(handover), (
        "`legacy.py` must stay deleted in the working copy."
    )


def test_settings_on_disk():
    """The checked-out tree really has the file back, not just the commits.

    The content check here is unavoidably a read off disk -- that is the whole
    point of the test. What the anchor adds is the identity of the tree being
    read: `@` has to still be the working-copy commit the bootstrap handed over,
    so "the file is back on disk" cannot be satisfied by checking out a
    fabricated commit that happens to contain it.
    """
    assert_the_handover_working_copy_is_still_checked_out()
    settings_path = os.path.join(PROJECT_DIR, "settings.toml")
    assert os.path.isfile(settings_path), (
        f"{settings_path} does not exist on disk."
    )
    with open(settings_path) as fh:
        assert fh.read() == SETTINGS_TOML, (
            f"{settings_path} on disk does not have the original content."
        )
