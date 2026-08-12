"""Verifier for concurrent_operations.

The task is to make one change divergent on purpose -- describe it a second time
`--at-operation` an earlier operation, let jj reconcile the two operation logs,
and then resolve the divergence by keeping the `variant 2` commit and abandoning
the `variant 1` one.

WHICH CHANGE, AND WHERE THE REFERENCE COMES FROM
================================================

Every assertion here is about the change the BOOTSTRAP created, addressed by its
anchored change id (tests/anchor.py) rather than by a `description('Feature X*')`
glob. A description is free text the agent can write, so the glob was satisfied
by `jj new -r 'root()' -m 'Feature X - variant 2'` -- a commit created from
nothing, destroying nothing, so the integrity fixture held and both scored tests
passed. A change id is generated randomly at commit creation, is preserved by
`jj describe`, and cannot be written by hand.

The anchor records that change under the description it carried at handover,
`Feature X - variant 1`; requirement 5 leaves it described `Feature X - variant
2`. That the SAME change ends up with the other description is precisely what the
task asks for, and it is a claim only a change id can express.

Two jj details that had to be measured rather than guessed (jj 0.38.0):

  * A bare change-id revset ERRORS on a divergent change -- "Change ID ... is
    divergent" -- so the revset is `change_id(<id>)`, which resolves to all of
    them, wrapped in `present()` so an operation from before the change existed
    reads as empty instead of as an error.
  * The abandoned `variant 1` commit is a divergent SIBLING, not a predecessor,
    so it does NOT appear in `jj evolog` of the surviving commit. The evolution
    log is therefore not where the divergence can be seen; the operation log is.

In cold CI there is no anchor file -- change ids are random per image build, so it
cannot be a committed constant -- and every resolver below falls back to the
description glob this file used before, printing that no identity claim was made.
"""

import subprocess

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/repo"

# The description the graded change carried at handover: the anchor's key for it.
HANDOVER_DESCRIPTION = "Feature X - variant 1"

# The description requirement 5 says it must carry at the end.
FINAL_DESCRIPTION = "Feature X - variant 2"

# What this file resolved the change by before the anchor existed. A bare string
# pattern is a GLOB in jj 0.38 and descriptions are stored with a trailing
# newline, which is why it needs the `*`.
FALLBACK_REVSET = "description('Feature X*')"

# Marker asking change_id_or_fallback() for "nothing" so the caller can tell the
# anchored path from the fallback path. It never reaches jj.
NO_ANCHOR = ""


def jj(*args):
    """Run a read-only jj command in the repo and return stdout.

    `--ignore-working-copy` on every call: a plain jj read snapshots the working
    copy first, which appends an operation and rewrites `@`, so a verifier
    without it mutates the repository it is grading.
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


def graded_revset():
    """A revset naming every visible commit of the bootstrap's change."""
    change = change_id_or_fallback(HANDOVER_DESCRIPTION, NO_ANCHOR,
                                  repo=PROJECT_DIR)
    if not change:
        return FALLBACK_REVSET
    return f"present(change_id({change}))"


def descriptions(revset, at_op=None):
    """First description line of every commit in `revset`, oldest last."""
    args = ["log", "-r", revset, "--no-graph", "--color=never",
            "-T", 'description.first_line() ++ "\\n"']
    if at_op is not None:
        args = [f"--at-op={at_op}"] + args
    return [line for line in jj(*args).splitlines() if line.strip()]


def operations():
    """Every operation id, newest first, full hex so no prefix is ambiguous."""
    return [line.strip() for line in jj(
        "op", "log", "--no-graph", "--color=never", "-T", 'id ++ "\\n"'
    ).splitlines() if line.strip()]


def test_final_commit_description():
    """The bootstrap's change must now be described `Feature X - variant 2`.

    Asked of that change, not of "some commit described Feature X something":
    the point of the task is that ONE change ended up with the second variant's
    description, and the first variant's commit was abandoned.
    """
    revset = graded_revset()
    found = descriptions(revset)
    assert found == [FINAL_DESCRIPTION], (
        f"The change the bootstrap created is described {found}, expected "
        f"exactly [{FINAL_DESCRIPTION!r}]. It carried {HANDOVER_DESCRIPTION!r} "
        f"at handover; requirement 5 keeps the variant 2 commit for that change "
        f"and abandons the variant 1 one."
    )


def test_no_divergence():
    result = jj("log", "--no-graph", "-T", "divergent", "-r", graded_revset())
    assert "true" not in result, "The commit should not be divergent."


def test_operation_log_has_reconcile():
    """The divergence has to have actually happened, and been reconciled.

    Two pieces of evidence for requirement 4. The structural one is the load
    bearing half: at some recorded operation, the bootstrap's change resolved to
    MORE THAN ONE visible commit -- which is what a divergent change is, and what
    the operation-log merge produces. Nothing an additive fabrication does can
    make the anchored change divergent at any operation.

    jj's English "reconcile divergent operations" is kept as well, because it is
    the operation log entry the requirement names; it is not relied on alone.
    """
    revset = graded_revset()
    divergent_at = [
        op for op in operations() if len(descriptions(revset, at_op=op)) > 1
    ]
    assert divergent_at, (
        "No recorded operation has the bootstrap's change resolving to more "
        "than one visible commit, so it was never divergent. Requirement 3 "
        "describes that change a second time at an earlier operation and "
        "requirement 4 merges the two operation logs; the merge is what makes "
        "the change divergent, and the operation log still records it."
    )

    result = jj("op", "log")
    assert "reconcile divergent operations" in result, (
        "The operation log should contain 'reconcile divergent operations' to "
        "indicate the concurrent modification was simulated."
    )
