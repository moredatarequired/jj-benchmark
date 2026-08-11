"""Verifier for operation_recovery.

The task is to bring the repository back to the state it was in immediately
after `Commit 2` was created, by returning it to that earlier point rather than
by rewriting history. Every assertion here is structural: commit and change IDs,
revset membership, and templated `--no-graph` output over explicit revsets. In
particular nothing greps the graph-formatted output of a bare `jj log`, whose
contents depend on the default revset (`present(@) | ancestors(immutable_heads()..,
2) | trunk()`) -- a stray `main` bookmark is enough to elide `Commit 2` from it --
and nothing matches on jj's own English operation descriptions, which change
between releases.

The reference state is not hardcoded: commit IDs differ on every image build, so
the verifier reads the repository's own record of past operations, finds the
operation that created `Commit 2`, and compares today's repository against the
state at that operation.
"""

import os
import subprocess

PROJECT_DIR = "/home/user/project"

# jj stores a non-empty description with a trailing newline, and a bare string
# pattern is not a substring match, so these are spelled out explicitly.
KEPT = ("Commit 1", "Commit 2")
DISCARDED = ("Commit 3", "Commit 4", "Commit 5")

# Templates. A commit's own description renders as an empty line, so it is
# probed with a conditional rather than read back directly.
PARENT_IDS = 'parents.map(|c| c.commit_id()).join(",")'
IS_EMPTY = 'if(empty, "empty", "nonempty")'
HAS_DESCRIPTION = 'if(description, "described", "undescribed")'


def exact(description):
    return 'description(exact:"' + description + '\\n")'


def substring(description):
    return 'description(substring:"' + description + '")'


def jj(*args):
    """Run jj in the project and return stdout, failing the test on error.

    `--ignore-working-copy` keeps every call read-only: jj otherwise snapshots
    the working copy first, which would let the check mutate the very state it
    is inspecting (and make a second run see something different from the
    first).
    """
    result = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"`jj {' '.join(args)}` failed with status {result.returncode}: "
        f"{result.stderr.strip()}"
    )
    return result.stdout


def field(revset, template, at_op=None):
    """Render `template` for `revset`, as a list of one string per commit."""
    args = ["log", "--no-graph", "--color=never", "-r", revset, "-T",
            template + ' ++ "\\n"']
    if at_op is not None:
        args += ["--at-op", at_op]
    return [line for line in jj(*args).splitlines() if line]


def one(revset, template, at_op=None):
    """Render `template` for a revset that must resolve to exactly one commit."""
    values = field(revset, template, at_op=at_op)
    assert len(values) == 1, (
        f"Expected exactly one commit matching {revset}"
        f"{'' if at_op is None else f' at operation {at_op}'}, found "
        f"{len(values)}: {values}"
    )
    return values[0]


def operations_newest_first():
    return [line for line in jj(
        "op", "log", "--no-graph", "--color=never", "-T", 'id.short(12) ++ "\\n"'
    ).splitlines() if line]


def first_operation_with(revset):
    """The oldest recorded operation whose repository state contains `revset`."""
    for op in reversed(operations_newest_first()):
        if field(revset, "commit_id", at_op=op):
            return op
    return None


def last_operation_with(revset):
    """The newest recorded operation whose repository state contains `revset`."""
    for op in operations_newest_first():
        if field(revset, "commit_id", at_op=op):
            return op
    return None


_REFERENCE = {}


def reference_state():
    """The repository state at the operation that created `Commit 2`.

    That operation is still in the repository's record of past operations
    whichever way the agent went back, so the expected end state can be read
    out of the repository instead of being hardcoded.
    """
    if _REFERENCE:
        return _REFERENCE

    op = first_operation_with(exact("Commit 2"))
    assert op is not None, (
        "No recorded operation has a commit described 'Commit 2'. The "
        "repository's record of past operations is gone, so the state to "
        "recover cannot be identified."
    )
    _REFERENCE.update(
        op=op,
        working_copy_change=one("@", "change_id", at_op=op),
        commits={
            description: one(exact(description), "commit_id", at_op=op)
            for description in KEPT
        },
    )
    return _REFERENCE


def test_kept_files_present_with_original_contents():
    for name, expected in (("file1.txt", "C1\n"), ("file2.txt", "C2\n")):
        path = os.path.join(PROJECT_DIR, name)
        assert os.path.isfile(path), f"{name} should be present in {PROJECT_DIR}."
        with open(path, encoding="utf-8") as handle:
            content = handle.read()
        assert content == expected, (
            f"{name} should still contain {expected!r}, but contains {content!r}."
        )


def test_discarded_files_absent():
    for name in ("file3.txt", "file4.txt", "file5.txt"):
        assert not os.path.exists(os.path.join(PROJECT_DIR, name)), (
            f"{name} should be gone from the working copy."
        )


def test_working_copy_tracks_only_the_kept_files():
    tracked = sorted(
        path for path in jj("file", "list", "-r", "@").splitlines() if path
    )
    assert tracked == ["file1.txt", "file2.txt"], (
        f"The working copy should contain file1.txt and file2.txt and nothing "
        f"else, but it tracks {tracked}."
    )


def test_discarded_commits_not_visible():
    revset = " | ".join(substring(description) for description in DISCARDED)
    found = field(revset, 'commit_id.short(8) ++ " " ++ description.first_line()')
    assert not found, (
        f"No commit described 'Commit 3', 'Commit 4' or 'Commit 5' should be "
        f"visible any more, but these are: {found}."
    )


def test_kept_commits_are_the_original_commits():
    """`Commit 1` and `Commit 2` must be the same commits, not rebuilt copies."""
    reference = reference_state()
    for description in KEPT:
        actual = one(exact(description), "commit_id")
        assert actual == reference["commits"][description], (
            f"The commit described '{description}' has commit ID {actual}, but "
            f"in the state being recovered it is "
            f"{reference['commits'][description]}. It was rewritten or rebuilt "
            f"rather than kept."
        )

    parent_of_two = one(exact("Commit 2"), PARENT_IDS)
    assert parent_of_two == reference["commits"]["Commit 1"], (
        f"'Commit 2' should sit directly on top of the original 'Commit 1', but "
        f"its parent is {parent_of_two}."
    )


def test_working_copy_is_the_commit_from_that_earlier_state():
    """The working copy must be the same commit it was back then.

    This is what separates going back to the earlier state from editing history
    forward into a similar-looking shape: abandoning the later commits, or
    starting a fresh empty commit on top of `Commit 2`, leaves the working copy
    on a different change.
    """
    reference = reference_state()

    change = one("@", "change_id")
    assert change == reference["working_copy_change"], (
        f"The working copy is change {change[:12]}, but in the state being "
        f"recovered it is change {reference['working_copy_change'][:12]}. The "
        f"repository was not returned to that state -- a new or different "
        f"working-copy commit is checked out."
    )

    assert one("@", IS_EMPTY) == "empty", (
        "The working-copy commit should be empty, as it was in the state being "
        "recovered, but it contains changes."
    )
    assert one("@", HAS_DESCRIPTION) == "undescribed", (
        "The working-copy commit should have no description, as it had in the "
        "state being recovered."
    )

    parent = one("@", PARENT_IDS)
    assert parent == reference["commits"]["Commit 2"], (
        f"The working copy's parent should be 'Commit 2' "
        f"({reference['commits']['Commit 2'][:12]}), but it is {parent[:12]}."
    )


def test_visible_history_is_exactly_the_recovered_state():
    commits = field("all()", 'commit_id.short(8) ++ " " ++ description.first_line()')
    assert len(commits) == 4, (
        f"The repository should hold exactly four commits -- the root commit, "
        f"'Commit 1', 'Commit 2' and the empty working-copy commit -- but "
        f"{len(commits)} are visible: {commits}."
    )


def test_earlier_operations_are_still_recorded():
    """The discarded work must still be recoverable, not erased.

    Wiping the repository and rebuilding the first two commits by hand satisfies
    every other assertion here, because the reference state would then be read
    out of the rebuilt record and agree with itself. This is the check it cannot
    satisfy: the repository must still hold operations in which `Commit 5`
    existed.
    """
    op = last_operation_with(substring("Commit 5"))
    assert op is not None, (
        "No recorded operation has a commit described 'Commit 5'. The earlier "
        "work was erased rather than set aside, so it can no longer be "
        "recovered."
    )