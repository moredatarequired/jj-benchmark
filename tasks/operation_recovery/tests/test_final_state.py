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

WHERE THE REFERENCE VALUES COME FROM
====================================

The reference state cannot be hardcoded: commit and change IDs differ on every
image build. This file used to read it out of the repository's own record of
past operations -- walk to the operation that created `Commit 2`, take `@`'s
change id and the kept commits' ids from there -- and that is the weakness its
own docstring admitted at the bottom of this file: a repository that was wiped,
rebuilt by hand and then rolled back with `jj op restore` supplies its own
reference and agrees with itself, which scored reward 1.0.

So the CHANGE IDS the scored assertions are phrased in now come from the
BOOTSTRAP ANCHOR (tests/anchor.py): a measurement taken on the host, from the
untouched image, before the agent ran. The `--at-op` replay stays -- it is how
"the discarded work is still recorded" is asked, and it is the only way to ask
it -- but it is a CONSISTENCY check, not an identity one, so nothing here rests
on it any more.

The change the recovered working copy has to be is the one the bootstrap went on
to describe `Commit 3`: `jj commit -m "Commit 2"` left an empty commit on top of
`Commit 2`, `echo C3 > file3.txt` filled it in and `jj commit -m "Commit 3"`
described it. Requirement 4 asks for that commit back, empty and undescribed,
which is why tests/anchor_exemptions.json deliberately does NOT exempt it while
it does exempt `Commit 4`, `Commit 5` and the handover `@`.

In cold CI there is no anchor file -- it is a per-build artifact, because change
ids are random per image build -- and every resolver below then falls back to
the operation-log derivation this file used before, printing that no identity
claim was made.
"""

import os
import subprocess

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/project"

# jj stores a non-empty description with a trailing newline, and a bare string
# pattern is not a substring match, so these are spelled out explicitly.
KEPT = ("Commit 1", "Commit 2")
DISCARDED = ("Commit 3", "Commit 4", "Commit 5")

# The bootstrap commits that must be GONE. `Commit 3`'s change must survive (as
# the recovered working copy), so it is not in this list even though no commit
# may still be *described* `Commit 3`.
DISCARDED_CHANGES = ("Commit 4", "Commit 5")

# The bootstrap description of the change the recovered working copy must be.
RECOVERED_WORKING_COPY = "Commit 3"

# Templates. A commit's own description renders as an empty line, so it is
# probed with a conditional rather than read back directly.
PARENT_IDS = 'parents.map(|c| c.commit_id()).join(",")'
PARENT_CHANGES = 'parents.map(|c| c.change_id()).join(",")'
IS_EMPTY = 'if(empty, "empty", "nonempty")'
HAS_DESCRIPTION = 'if(description, "described", "undescribed")'


def exact(description):
    return 'description(exact:"' + description + '\\n")'


def present(revset):
    """`revset`, or nothing, instead of an error when it resolves to nothing.

    An anchored change id that no longer resolves makes `jj log -r <id>` exit
    non-zero -- which is a finding, not an infrastructure failure -- so the
    absence checks wrap it in present() and read an empty result instead.
    """
    return "present(" + revset + ")"


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
_CHANGES = {}


def reference_state():
    """The repository state at the operation that created `Commit 2`.

    Read out of the repository's own record of past operations, so it says how
    THIS repository reached its state -- and nothing more than that. It supplies
    the commit ids for test_kept_commits_are_the_original_commits, which is the
    one assertion here that is about commit ids (the anchor deliberately does not
    assert those: a genuine rewrite changes them), and it supplies the fallback
    values for recovered_changes() when there is no anchor.
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


def recovered_changes():
    """The change ids the recovered state must be made of, from the ANCHOR.

    Three entries: `Commit 1`, `Commit 2`, and RECOVERED_WORKING_COPY -- the
    change the bootstrap described `Commit 3` and which requirement 4 asks back
    as an empty, undescribed working copy.

    Change ids, not commit ids: a change id is generated randomly when a commit
    is created and cannot be reproduced by rebuilding a similar-looking history,
    while it survives every legitimate rewrite. That asymmetry is the whole
    reason it is the value worth anchoring.
    """
    if _CHANGES:
        return _CHANGES

    # The fallback for each is what this file measured before the anchor
    # existed: the same value read at the reference operation, out of this
    # repository. change_id_or_fallback() prints that identity was not claimed.
    reference = reference_state()
    op = reference["op"]
    for description in KEPT:
        _CHANGES[description] = change_id_or_fallback(
            description,
            one(exact(description), "change_id", at_op=op),
            repo=PROJECT_DIR,
        )
    _CHANGES[RECOVERED_WORKING_COPY] = change_id_or_fallback(
        RECOVERED_WORKING_COPY, reference["working_copy_change"],
        repo=PROJECT_DIR,
    )
    return _CHANGES


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
    """The discarded files are off the disk -- and out of the graded commit's tree.

    The disk half cannot be anchored: an anchor says which commits the bootstrap
    created, and says nothing about the absence of a path in a directory. So the
    same absence is also asked of the commit the recovered working copy has to be,
    which is a claim about the bootstrap's own change rather than about whatever
    files happen to be lying around.
    """
    discarded = ("file3.txt", "file4.txt", "file5.txt")
    for name in discarded:
        assert not os.path.exists(os.path.join(PROJECT_DIR, name)), (
            f"{name} should be gone from the working copy."
        )

    change = recovered_changes()[RECOVERED_WORKING_COPY]
    tracked = set(
        path for path in jj("file", "list", "-r", change).splitlines() if path
    )
    still_tracked = sorted(tracked.intersection(discarded))
    assert not still_tracked, (
        f"The commit the recovered working copy has to be ({change[:12]}) still "
        f"tracks {still_tracked}. Recovering the state right after `Commit 2` "
        "leaves that commit holding file1.txt and file2.txt only."
    )


def test_working_copy_tracks_only_the_kept_files():
    """...and the working copy asked about is the anchored one, not whatever `@` is.

    `-r @` grades whichever commit happens to be checked out, so a fabricated
    commit holding two files named file1.txt and file2.txt satisfied it. The
    revset is the bootstrap's own change id instead.
    """
    change = recovered_changes()[RECOVERED_WORKING_COPY]
    tracked = sorted(
        path for path in jj("file", "list", "-r", change).splitlines() if path
    )
    assert tracked == ["file1.txt", "file2.txt"], (
        f"The commit the recovered working copy has to be ({change[:12]}) "
        f"should contain file1.txt and file2.txt and nothing else, but it "
        f"tracks {tracked}."
    )


def test_discarded_commits_not_visible():
    """Nothing described `Commit 3`/`4`/`5`, and the anchored 4 and 5 are gone.

    The description half is requirement 2 as written. The change-id half is what
    a description cannot say: `Commit 4` and `Commit 5` are named in this task's
    anchor_exemptions.json as commits the solve is allowed to remove, and this is
    where their removal is actually required rather than merely permitted.
    """
    revset = " | ".join(substring(description) for description in DISCARDED)
    found = field(revset, 'commit_id.short(8) ++ " " ++ description.first_line()')
    assert not found, (
        f"No commit described 'Commit 3', 'Commit 4' or 'Commit 5' should be "
        f"visible any more, but these are: {found}."
    )

    changes = {
        description: change_id_or_fallback(
            description, substring(description), repo=PROJECT_DIR)
        for description in DISCARDED_CHANGES
    }
    still_here = {
        description: field(present(change), "commit_id.short(8)")
        for description, change in changes.items()
    }
    still_here = {d: v for d, v in still_here.items() if v}
    assert not still_here, (
        "The commit(s) the bootstrap created and described "
        f"{sorted(still_here)} are still visible: {still_here}. The work after "
        "`Commit 2` has to be set aside, not merely renamed."
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

    Both the working copy's own change id and its parent's are compared against
    the anchor, so a repository that was rebuilt cannot supply its own answer.
    """
    changes = recovered_changes()
    expected = changes[RECOVERED_WORKING_COPY]

    change = one("@", "change_id")
    assert change == expected, (
        f"The working copy is change {change[:12]}, but the state being "
        f"recovered had change {expected[:12]} checked out -- the commit the "
        f"bootstrap went on to describe {RECOVERED_WORKING_COPY!r}. The "
        f"repository was not returned to that state: a new or different "
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

    parent = one("@", PARENT_CHANGES)
    assert parent == changes["Commit 2"], (
        f"The working copy's parent should be the bootstrap's 'Commit 2' "
        f"(change {changes['Commit 2'][:12]}), but it is {parent[:12]}."
    )


def test_visible_history_is_exactly_the_recovered_state():
    """Four commits, and WHICH four: the anchored three plus jj's root commit.

    The count on its own accepts four commits none of which the bootstrap
    created. Naming the three by change id is what makes this the recovered
    state rather than a state of the right size.
    """
    commits = field("all()", 'commit_id.short(8) ++ " " ++ description.first_line()')
    assert len(commits) == 4, (
        f"The repository should hold exactly four commits -- the root commit, "
        f"'Commit 1', 'Commit 2' and the empty working-copy commit -- but "
        f"{len(commits)} are visible: {commits}."
    )

    visible = set(field("all() ~ root()", "change_id"))
    changes = recovered_changes()
    missing = {d: c for d, c in changes.items() if c not in visible}
    assert not missing, (
        "The three commits the recovered state is made of are the ones the "
        "bootstrap created. These are not among the visible commits: "
        + "; ".join(
            f"the change the bootstrap described {d!r} ({c[:12]})"
            for d, c in sorted(missing.items())
        )
        + ". The repository holds four commits, but not these four."
    )


def test_earlier_operations_are_still_recorded():
    """The discarded work must still be recoverable, not erased.

    This is requirement 5 -- "nothing may be erased from the record" -- and it is
    a question about the operation log, so the operation log is what answers it.

    It used to carry a second job it was not able to do. Wiping the repository
    and rebuilding `Commit 1` and `Commit 2` by hand satisfied every other
    assertion here, because the reference state was read out of the rebuilt
    record and agreed with itself, and this check was the only thing left
    standing in the way -- which a rebuild defeats too, by recreating all five
    commits and then rolling back to the second. The scored assertions above now
    take their reference change ids from the bootstrap anchor instead, so this
    test is back to being what it says it is.
    """
    op = last_operation_with(substring("Commit 5"))
    assert op is not None, (
        "No recorded operation has a commit described 'Commit 5'. The earlier "
        "work was erased rather than set aside, so it can no longer be "
        "recovered."
    )