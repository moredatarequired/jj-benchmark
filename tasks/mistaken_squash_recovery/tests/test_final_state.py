"""Verifier for the mistaken_squash_recovery task.

The request is one line: undo the squash I did by mistake, keeping the two
commits I made after it.

The repository is handed over with the mistake already in it. Two commits were
squashed into one, and two further commits landed on top afterwards, so the
mistaken operation is five entries back in the operation log and has to be
found rather than assumed to be the most recent thing that happened.

THE EXPECTED ANSWER IS NEVER A CONSTANT IN THIS FILE
====================================================

The change id of the squashed-away commit does not exist in the handover
repository -- the squash abandoned it before the agent ever saw it -- so it
cannot come from the anchor, which only records what was visible at handover.
It is recovered here the only way it can be: by REPLAYING THE OPERATION LOG.
The verifier reads the repository at each bootstrap operation with `--at-op`,
finds the one operation where a change id left the visible set, and reads that
commit's identity and content out of the state just before it. Everything the
recovered commit is compared against is measured from the repository at
verification time.

That also means no English is matched anywhere. The mistaken operation is
identified by what it DID to the repository -- a change id disappeared -- not
by jj's description of it ("squash commits into ..."), which is not something a
verifier should depend on.

WRITTEN AGAINST AN OBSERVED END STATE (R7), AND THE DESIGN WAS WRONG TWICE
=========================================================================

The fixture was built from environment/Dockerfile and `jj op revert <the
squash>` was run in a container of that image, on the pinned jj 0.44.0, before
any assertion below was written. Two things the design this task was written
from asserted, and the binary denied:

  * THERE IS NO DIVERGENCE. The design said the correct route leaves a divergent
    change and warned at length that its offsets would not be `/0` and `/1`.
    Measured on this fixture, `jj op revert` leaves nothing divergent at all --
    `divergent` is false for every visible commit. So there is no offset
    handling here to get wrong, and no `may_be_divergent` exemption to write.
    (The rule the warning came from still stands and is still worth knowing:
    `X/N` indexes every version ever recorded, hidden ones included. It simply
    does not arise here.)

  * THE LATER COMMITS DO NOT KEEP THEIR COMMIT IDS. The design asked for the
    two later commits to be found "with their bootstrap commit ids intact".
    They cannot be: reverting the squash rewrites the commit they descend from,
    so jj rebases them and both get new commit ids while keeping their change
    ids. Asserting commit-id equality there would have failed every correct
    solve. Their content is compared instead, read out of the repository as it
    stood at the handover operation.

The shape of the end state was a third surprise worth stating: the recovered
commit comes back as a SIBLING of the later work, not underneath it. `jj op
revert` restores B as a child of A and rebases the two later commits onto A as
well, so the graph forks. It cannot be otherwise -- the later commits were made
on top of the squashed A, and reverting the squash cannot retroactively put
them above a commit they were never built on. So the order assertion here is
that A is an ancestor of B, which is the order the two of them were made in;
nothing requires the later work to sit above B.

WHAT SEPARATES THE ROUTES
=========================

  `jj op revert <the squash>`     the asked-for end state.
  `jj op restore <op before it>`  restores A and B perfectly AND DELETES BOTH
                                  LATER COMMITS. Measured. The repository looks
                                  entirely healthy afterwards; it just has a
                                  day of work missing, which is exactly why
                                  this has to be graded rather than eyeballed.
                                  The bootstrap anchor catches it before any
                                  test in this file runs, because two anchored
                                  change ids stop resolving.
  `jj undo`                       reverses the changelog snapshot and leaves
                                  the squash untouched.
  `jj split` on the combined      a right-looking log built out of new change
                                  ids, and -- because both original commits
                                  edited src/api/charge.py -- not even the
                                  right content on either side.
"""

import subprocess

import anchor
from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/checkout-api"

# The two commits made AFTER the mistake. These exist at handover, so unlike the
# squashed-away commit they are anchorable by description.
LATER = (
    "raise the retry budget for charges",
    "note the 409 behaviour in the changelog",
)
# Everything the bootstrap handed over, for the anti-collateral-damage check.
UNTOUCHED = ("add the charge endpoint", "retry failed charges with backoff")

_snapshotted = False


def snapshot_working_copy():
    """The one working-copy snapshot this verifier takes, deliberately.

    Every read below is of committed state, so the repository has to be in the
    state the agent left it first. Snapshotting preserves change ids, so it
    cannot disturb the anchor.
    """
    global _snapshotted
    if not _snapshotted:
        subprocess.run(["jj", "status"], cwd=PROJECT_DIR,
                       capture_output=True, text=True)
        _snapshotted = True


def jj(*args):
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


def change_ids(revset, at_op=None):
    pre = ["--at-op", at_op] if at_op else []
    out = jj_ok(*pre, "log", "-r", revset, "--no-graph", "-T",
                'change_id ++ "\\n"')
    return [line for line in out.splitlines() if line]


def graded(description):
    return change_id_or_fallback(
        description, 'description(substring:"%s")' % description,
        repo=PROJECT_DIR)


def resolve_one(description):
    snapshot_working_copy()
    found = change_ids(graded(description))
    assert len(found) == 1, (
        f"the bootstrap commit `{description}` resolves to {len(found)} "
        "visible commit(s), expected exactly one."
    )
    return found[0]


# --------------------------------------------------------------------------
# Replaying the operation log
# --------------------------------------------------------------------------

def handover_operation():
    """The newest operation as of bootstrap, or None when there is no anchor.

    Restricting the scan below to this operation's ancestry is what keeps the
    search inside the BOOTSTRAP's operations. Operations are append-only, so
    anything the agent did lands after it and cannot be mistaken for the
    mistake the request is about.
    """
    try:
        record = anchor.load()
    except anchor.AnchorUnavailable as exc:
        print("%s: scanning the whole operation log for the mistaken "
              "operation and taking the earliest candidate (%s)"
              % (anchor.IDENTITY_NOT_CLAIMED, exc))
        return None
    for repo in record["repos"]:
        if repo.get("path") == PROJECT_DIR and repo.get("handover_operation_id"):
            return repo["handover_operation_id"]
    return None


def operations():
    """[(op id, parent op id)] oldest-first, over the bootstrap's operations."""
    at_op = handover_operation()
    pre = ["--at-op", at_op] if at_op else []
    out = jj_ok(*pre, "op", "log", "--no-graph", "-T",
                'id ++ " " ++ parents.map(|p| p.id()) ++ "\\n"')
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        rows.append((parts[0], parts[1] if len(parts) > 1 else None))
    return list(reversed(rows))


def visible_at(op):
    """change_id -> commit_id, as the repository stood at `op`.

    `--at-op` implies `--ignore-working-copy`, which is required: the verifier
    must not take a snapshot while reading history.
    """
    out = jj_ok("--at-op", op, "log", "-r", "all() ~ root()", "--no-graph",
                "-T", 'change_id ++ " " ++ commit_id ++ "\\n"')
    return dict(line.split() for line in out.splitlines() if line.strip())


_mistake = None


def the_mistaken_operation():
    """(before_state, after_state, squashed_away_cid, squashed_into_cid).

    The mistaken operation is the one bootstrap operation that made a change id
    LEAVE the visible set. The fixture guarantees there is exactly one -- see
    environment/Dockerfile, invariant 1 -- and the bootstrap check asserts it,
    so an ambiguous result here means the fixture drifted, not that the agent
    did something clever.
    """
    global _mistake
    if _mistake is not None:
        return _mistake
    candidates = []
    for op, parent in operations():
        if parent is None:
            continue
        before, after = visible_at(parent), visible_at(op)
        gone = set(before) - set(after)
        if gone:
            candidates.append((op, before, after, gone))
    assert candidates, (
        "no operation in this repository's history removed a commit, so the "
        "squash the request refers to cannot be found. The fixture is built so "
        "that exactly one operation does; if this fires, the bootstrap changed."
    )
    op, before, after, gone = candidates[0]
    assert len(gone) == 1, (
        f"operation {op[:12]} removed {len(gone)} commits; the mistaken squash "
        "removed exactly one."
    )
    squashed_away = next(iter(gone))
    rewritten = sorted(
        cid for cid in set(before) & set(after) if before[cid] != after[cid]
    )
    assert len(rewritten) == 1, (
        f"operation {op[:12]} rewrote {len(rewritten)} commits; the mistaken "
        "squash rewrote exactly one, the commit it squashed into."
    )
    _mistake = (before, after, squashed_away, rewritten[0])
    return _mistake


def paths_changed(cid, at_op=None):
    pre = ["--at-op", at_op] if at_op else []
    out = jj_ok(*pre, "diff", "-r", f"change_id({cid})", "--name-only")
    return {line for line in out.splitlines() if line}


def file_at(cid, path, at_op=None):
    pre = ["--at-op", at_op] if at_op else []
    result = jj(*pre, "file", "show", "-r", f"change_id({cid})", path)
    return result.stdout if result.returncode == 0 else None


def describe(cids):
    if not cids:
        return "(none)"
    revset = " | ".join(f"change_id({c})" for c in sorted(cids))
    out = jj_ok("log", "-r", revset, "--no-graph", "-T",
                'change_id.short(8) ++ " " ++ description.first_line() ++ "\\n"')
    return "; ".join(line for line in out.splitlines() if line)


def pre_squash_op():
    """The operation id just before the mistake, for `--at-op` reads."""
    for op, parent in operations():
        if parent is None:
            continue
        if set(visible_at(parent)) - set(visible_at(op)):
            return parent
    raise AssertionError("no operation removed a commit")


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------

def test_the_squashed_commit_exists_again():
    """The commit the squash swallowed is visible, under its own change id.

    This is the identity claim, and it is the whole difference between undoing
    the operation and re-creating something that looks like its result. jj mints
    change ids randomly at commit creation, so a hand-rebuild -- `jj split` on
    the combined commit, or a fresh commit with the same message and the same
    files -- cannot produce this id. Nothing here reads a description.
    """
    snapshot_working_copy()
    _, _, squashed_away, _ = the_mistaken_operation()
    found = change_ids(f"change_id({squashed_away})")
    assert found, (
        f"the commit the squash swallowed ({squashed_away[:12]}) is still not "
        "in the repository. Re-creating a commit that looks like it is not the "
        "same thing: jj generates change ids at commit creation, so only "
        "reversing the operation that removed it brings this id back."
    )
    assert len(found) == 1, (
        f"{squashed_away[:12]} resolves to {len(found)} visible commits; "
        "expected exactly one."
    )


def test_the_recovered_commit_is_the_original_work():
    """It carries the diff it carried before the squash, in the same order.

    Compared against the repository as it stood at the operation before the
    mistake -- read with `--at-op`, never against a constant in this file. The
    order claim is that the commit it was squashed into is still its ancestor,
    which is the order the two were made in.
    """
    snapshot_working_copy()
    _, _, squashed_away, squashed_into = the_mistaken_operation()
    before_op = pre_squash_op()
    if not change_ids(f"change_id({squashed_away})"):
        raise AssertionError(
            f"the squashed-away commit ({squashed_away[:12]}) is not visible, "
            "so its content cannot be compared."
        )
    expected_paths = paths_changed(squashed_away, at_op=before_op)
    actual_paths = paths_changed(squashed_away)
    assert actual_paths == expected_paths, (
        f"the recovered commit ({squashed_away[:12]}) should change "
        f"{sorted(expected_paths)}, as it did before the squash; it changes "
        f"{sorted(actual_paths)}."
    )
    for path in sorted(expected_paths):
        want = file_at(squashed_away, path, at_op=before_op)
        got = file_at(squashed_away, path)
        assert got == want, (
            f"{path} in the recovered commit does not match what that commit "
            "held before the squash."
        )
    ancestors = change_ids(f"::change_id({squashed_away})")
    assert squashed_into in ancestors, (
        f"the recovered commit ({squashed_away[:12]}) no longer sits after "
        f"`{describe([squashed_into])}`, which is the order the two were made "
        "in."
    )


def test_the_two_commits_are_separate_again():
    """The commit that swallowed the other carries only its own work again.

    This is the half of the request that a route touching only the operation
    log gets for free and a hand-rebuild gets wrong: both original commits
    edited src/api/charge.py, so no split by path can put the pieces back where
    they came from.
    """
    snapshot_working_copy()
    _, _, squashed_away, squashed_into = the_mistaken_operation()
    before_op = pre_squash_op()
    expected_paths = paths_changed(squashed_into, at_op=before_op)
    actual_paths = paths_changed(squashed_into)
    assert actual_paths == expected_paths, (
        f"`{describe([squashed_into])}` should be back to changing "
        f"{sorted(expected_paths)}; it changes {sorted(actual_paths)}. While "
        "it still carries the other commit's paths the squash has not been "
        "undone."
    )
    for path in sorted(expected_paths):
        want = file_at(squashed_into, path, at_op=before_op)
        got = file_at(squashed_into, path)
        assert got == want, (
            f"{path} in `{describe([squashed_into])}` does not match what that "
            "commit held before the squash -- the two commits' contents are "
            "still mixed."
        )
    swallowed_only = (
        paths_changed(squashed_away, at_op=before_op) - expected_paths
    )
    for path in sorted(swallowed_only):
        out = jj_ok("file", "list", "-r", f"change_id({squashed_into})")
        assert path not in out.splitlines(), (
            f"{path} still exists in `{describe([squashed_into])}`, so the "
            "other commit's work is still inside it."
        )


def test_the_two_commits_made_afterwards_are_still_here():
    """Named for the wrong solve it catches: rewinding past the mistake.

    `jj op restore <the operation before the squash>` separates the two commits
    perfectly and silently destroys both of these -- time travel rather than an
    inverse patch, and the single most expensive wrong answer available here.
    Their content is compared against the repository as it stood at the
    handover operation; their commit ids are NOT, because reverting the squash
    legitimately rebases them (see the module docstring).
    """
    snapshot_working_copy()
    handover = handover_operation()
    for description in LATER:
        cid = resolve_one(description)
        found = change_ids(f"change_id({cid})")
        assert found, (
            f"`{description}` ({cid[:12]}) is gone. It was made after the "
            "mistake and the request was to keep it: rewinding the repository "
            "to a point before the squash removes it, because that restores an "
            "earlier state rather than reversing one operation."
        )
        if handover is None:
            continue
        expected_paths = paths_changed(cid, at_op=handover)
        assert paths_changed(cid) == expected_paths, (
            f"`{description}` should still change {sorted(expected_paths)}; it "
            f"changes {sorted(paths_changed(cid))}."
        )
        for path in sorted(expected_paths):
            assert file_at(cid, path) == file_at(cid, path, at_op=handover), (
                f"{path} in `{description}` is not what it was at handover; "
                "the work made after the mistake was supposed to be left alone."
            )


def test_nothing_else_in_the_history_moved():
    """The commits below the mistake, and `main`, are where they were."""
    snapshot_working_copy()
    handover = handover_operation()
    for description in UNTOUCHED:
        cid = resolve_one(description)
        assert change_ids(f"change_id({cid})"), (
            f"the bootstrap commit `{description}` ({cid[:12]}) is no longer "
            "visible."
        )
        if handover is not None:
            assert paths_changed(cid) == paths_changed(cid, at_op=handover), (
                f"`{description}` no longer changes what it changed at "
                "handover."
            )
    main = resolve_one("retry failed charges with backoff")
    pointed = change_ids('bookmarks(exact:"main")')
    assert pointed == [main], (
        f"the `main` bookmark should still point at `retry failed charges with "
        f"backoff` ({main[:12]}); it points at {describe(pointed)}."
    )
