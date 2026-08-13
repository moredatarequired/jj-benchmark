"""Verifier for the duplicate_range task.

The request is one line: copy the three duplicate-key commits onto release/2.4
in the same order, and leave the originals on main alone.

WHAT MAKES THIS TASK DIFFERENT FROM THE SUITE'S OTHER WORK
==========================================================

Every other history-moving task in the suite RELOCATES work. This one asks for
the work to exist in two places at once, and the git-shaped instinct -- reach
for the command that puts commits on another branch -- relocates it instead.
`jj rebase -r <the run> -d release/2.4` produces a release branch that looks
exactly right and a main with a three-commit hole in it, and it does so while
PRESERVING the change ids, so the bootstrap anchor cannot see it: a rebase is
a rewrite, not a fabrication. Only reading where the originals ended up
separates the two, which is why that reading is a scored test here rather than
a floored one.

HOW THE COPIES ARE IDENTIFIED, GIVEN THAT NOTHING ABOUT THEM CAN BE ANCHORED
============================================================================

A copy is a NEW change. Its change id was minted after the bootstrap, so the
anchor has never seen it and no assertion here can name it. The copies are
therefore found the only way they can be: structurally, as the commits that
descend from the anchored release tip -- at handover, nothing does -- and then
matched to their sources by what they change and by the content they leave
behind. No copy is ever looked up by its description, which is agent-writable
text and would make a hand-typed log entry indistinguishable from the work.

WRITTEN AGAINST AN OBSERVED END STATE (R7)
==========================================

The fixture was built from environment/Dockerfile and solved in a container of
that image, on the pinned jj 0.44.0, before any assertion below was written.
Three things those runs showed, each of which changed an assertion here:

  * `jj duplicate` DOES NOT MOVE THE DESTINATION BOOKMARK. After
    `jj duplicate <A>::<C> --onto release/2.4` the three copies sit above the
    release tip and `release/2.4` still marks the tip itself. A test requiring
    the bookmark to end up on the newest copy would fail the most direct
    correct route, so this file requires only that `release/2.4` still marks a
    commit on that line -- the old tip or one of the copies.

  * THE ORIGINALS KEEP THEIR COMMIT IDS. `jj duplicate` does not touch them at
    all; measured, all three commit ids are byte-identical to the bootstrap's.
    That makes a commit-id comparison SAFE here, and it is the sharpest
    available statement of "left alone" -- but it is safe only because nothing
    the task asks for rewrites those commits or any ancestor of them. It is not
    a pattern to copy into a task where an ancestor is rewritten: jj rebases
    descendants and mints new commit ids while preserving change ids, so the
    same assertion elsewhere fails every correct solve.

  * THE COPIES ARE CONTENT-IDENTICAL AT THE PATHS THEY TOUCH. Each copy changes
    the same single path its source does, and the file at that path is
    byte-identical between source and copy, because the release branch has not
    touched any of the three paths since the fork. Measured for all three
    pairs, which is what licenses the content comparison below.

  * THE DESCRIPTION FALLBACK HAD TO BE NARROWED, and only running the solve
    showed it. change_id_or_fallback falls back to a revset when there is no
    anchor file, which is the normal condition in CI -- and the plain
    `description(substring:...)` fallback every other task uses is wrong here
    BY CONSTRUCTION, because the task's whole output is a second commit with
    the same description. The first genuine solve scored 0.333 on that alone.
    Each original is now restricted to main's own ancestry, which a copy on the
    release branch is not in. See ONLY_ON_MAIN below.

  * `description(exact:"...")` DOES NOT MATCH. jj descriptions carry a trailing
    newline, so the exact: form silently matches nothing. Every fallback revset
    below uses substring:.
"""

import subprocess

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/checkout-api"

# The run to be copied, oldest first, and the two anchored landmarks that fence
# it in. These are descriptions used to look up ANCHORED change ids; the anchor
# is what makes them identities rather than labels.
RUN = (
    "validate the duplicate-key format",
    "return 409 on duplicate keys",
    "add tests for duplicate keys",
)
BELOW_THE_RUN = "add a client-side rate limiter"
MAIN_TIP = "start the 2.5 changelog"
RELEASE_TIP = "pin the 2.4 dependency set"
RELEASE_BOOKMARK = "release/2.4"

_snapshotted = False


def snapshot_working_copy():
    """The one working-copy snapshot this verifier takes, deliberately.

    A solve may end having written something to disk without running a further
    jj command. Every read below is of committed state, so the repository has to
    be in the state the agent left it before any of them run. Snapshotting
    preserves change ids, so it cannot disturb the anchor.
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


# The description-based fallback used when there is no anchor file, which is the
# normal condition in CI. A bare `description(substring:...)` is WRONG on this
# task and the first genuine solve proved it: the whole point of the task is to
# put a second commit with the same description into the repository, so after a
# correct copy every one of the run's descriptions matches TWO commits and every
# lookup fails. Restricting each original to main's own ancestry fixes it,
# because a copy on the release branch is not an ancestor of main's tip.
#
# `start the 2.5 changelog` is the anchor of that restriction and is never
# copied by any route: it sits ABOVE the run, so no span that starts inside the
# run reaches it.
ANCESTRY_OF_MAIN_TIP = '::description(substring:"start the 2.5 changelog")'
ONLY_ON_MAIN = set(RUN) | {BELOW_THE_RUN, MAIN_TIP}


def graded(description):
    """The revset naming a bootstrap commit: its anchored change id if there is
    an anchor, and a description-based revset if there is not.

    change_id_or_fallback returns a REVSET, not always a change id -- so it is
    evaluated to get a concrete id rather than being interpolated into
    `change_id(...)`, which would be malformed on the fallback path.
    """
    fallback = 'description(substring:"%s")' % description
    if description in ONLY_ON_MAIN:
        fallback = "(%s) & %s" % (fallback, ANCESTRY_OF_MAIN_TIP)
    return change_id_or_fallback(description, fallback, repo=PROJECT_DIR)


def field(revset, template):
    out = jj_ok("log", "-r", revset, "--no-graph", "-T", template + ' ++ "\\n"')
    return [line for line in out.splitlines() if line]


def change_ids(revset):
    return field(revset, "change_id")


def resolve_one(description):
    """The change id of the single visible commit the anchor (or fallback) names."""
    snapshot_working_copy()
    found = change_ids(graded(description))
    assert len(found) == 1, (
        f"the bootstrap commit `{description}` resolves to {len(found)} "
        "visible commit(s), expected exactly one."
    )
    return found[0]


def commit_id_of(change_id):
    found = field(f"change_id({change_id})", "commit_id")
    assert len(found) == 1, (
        f"change {change_id[:12]} resolves to {len(found)} visible commits."
    )
    return found[0]


def parents_of(change_id):
    out = jj_ok("log", "-r", f"change_id({change_id})", "--no-graph", "-T",
                'parents.map(|p| p.commit_id()).join(",") ++ "\\n"')
    line = [l for l in out.splitlines() if l]
    return [p for p in (line[0].split(",") if line else []) if p]


def paths_changed(change_id):
    out = jj_ok("diff", "-r", f"change_id({change_id})", "--name-only")
    return {line for line in out.splitlines() if line}


def file_at(change_id, path):
    result = jj("file", "show", "-r", f"change_id({change_id})", path)
    return result.stdout if result.returncode == 0 else None


def describe(cids):
    if not cids:
        return "(none)"
    revset = " | ".join(f"change_id({c})" for c in sorted(cids))
    out = jj_ok("log", "-r", revset, "--no-graph",
                "-T", 'change_id.short(8) ++ " " ++ description.first_line() ++ "\\n"')
    return "; ".join(line for line in out.splitlines() if line)


def copies_in_order():
    """The commits that descend from the anchored release tip, oldest first.

    At handover nothing descends from it, so this is empty on an untouched
    image. The chain is walked by parent rather than trusting jj's log order,
    because "in the same order" is one of the two things being graded and a
    topological listing would let a wrong order pass.
    """
    snapshot_working_copy()
    base = resolve_one(RELEASE_TIP)
    added = set(change_ids(
        f"descendants(change_id({base})) ~ change_id({base})"))
    by_parent = {}
    for cid in added:
        for parent in parents_of(cid):
            by_parent.setdefault(parent, []).append(cid)
    ordered = []
    current = commit_id_of(base)
    while current in by_parent:
        children = by_parent[current]
        if len(children) != 1:
            break  # the line forks: reported by the caller as a shape failure
        ordered.append(children[0])
        current = commit_id_of(children[0])
    return added, ordered


def test_three_new_commits_sit_on_the_release_branch():
    """Exactly three, in one line, above where release/2.4 was.

    Named for the wrong solves it catches: copying the whole span above the
    fork point (four commits, because `add a client-side rate limiter` sits
    below the run), copying two of the three, and landing the copies as
    siblings rather than as a chain.
    """
    added, ordered = copies_in_order()
    assert len(added) == 3, (
        f"{len(added)} commit(s) descend from `{RELEASE_TIP}`, expected the "
        f"three copies: {describe(added)}.\nThe run to copy is the three "
        "commits about duplicate keys; the commits immediately below and above "
        "it on main are about other things."
    )
    assert len(ordered) == 3, (
        "the commits on the release branch are not a single line above "
        f"`{RELEASE_TIP}`: walking parents from it reaches "
        f"{len(ordered)} of {len(added)}. {describe(added)}"
    )
    conflicted = change_ids("conflicts()")
    assert not conflicted, (
        f"the repository holds conflicted commit(s): {describe(conflicted)}. "
        "The three commits apply cleanly on the release branch, so a conflict "
        "means something other than a copy happened."
    )
    marks = change_ids(f'bookmarks(exact:"{RELEASE_BOOKMARK}")')
    allowed = {resolve_one(RELEASE_TIP)} | set(ordered)
    assert marks and set(marks) <= allowed, (
        f"`{RELEASE_BOOKMARK}` no longer marks the release line; it marks "
        f"{describe(marks)}. (Either the tip it marked at handover or the "
        "newest copy is fine -- `jj duplicate` leaves it where it was.)"
    )


def test_the_copies_carry_the_same_changes_in_the_same_order():
    """Copy i changes what original i changed, and leaves the same bytes.

    This is where "in the same order" is graded. The copies cannot be matched
    to their sources by description -- a description is text an agent can type
    -- so they are matched positionally and then checked by content.
    """
    added, ordered = copies_in_order()
    assert len(ordered) == 3, (
        f"expected three copies in a line above `{RELEASE_TIP}`; found "
        f"{len(ordered)}. {describe(added)}"
    )
    for position, (source_description, copy_cid) in enumerate(
            zip(RUN, ordered), start=1):
        source = resolve_one(source_description)
        expected_paths = paths_changed(source)
        found_paths = paths_changed(copy_cid)
        assert found_paths == expected_paths, (
            f"copy {position} of 3 on the release branch ({copy_cid[:12]}) "
            f"changes {sorted(found_paths)}; the {position}(st/nd/rd) commit of "
            f"the run, `{source_description}`, changes "
            f"{sorted(expected_paths)}. Either the order is wrong or this is "
            "not a copy of that commit."
        )
        for path in sorted(expected_paths):
            want = file_at(source, path)
            got = file_at(copy_cid, path)
            assert got is not None, (
                f"{path} is missing from copy {position} ({copy_cid[:12]})."
            )
            assert got == want, (
                f"{path} at copy {position} ({copy_cid[:12]}) does not match "
                f"the same file at `{source_description}` ({source[:12]}). A "
                "copy of a commit carries the same content."
            )


def test_the_originals_are_still_on_main_untouched():
    """The run is still on main, with the commit ids the bootstrap gave it.

    Named for the wrong solve it catches, and the reason it is written as one
    test rather than two: `jj rebase -r <the run> -d release/2.4` RELOCATES the
    three commits, which leaves a release branch that satisfies the two tests
    above and a main with a hole in it. Because a rebase preserves change ids,
    the bootstrap anchor does not see it either. Asserting the originals alone
    would not do: that assertion holds on an untouched image, so it would be
    measured into the vacuity floor and excluded from scoring -- and the
    relocation would then score full marks. So this test re-derives the copies
    as well, and therefore fails on an untouched image, where there are none.

    The parent links are compared by COMMIT id, which is normally the wrong
    thing to assert. It is safe on this task and only on this task: nothing the
    request asks for rewrites these commits or any ancestor of them, so a
    correct solve cannot move them and their commit ids cannot change. Where an
    ancestor IS rewritten, jj rebases the descendants and mints new commit ids
    while keeping the change ids, and the same assertion would fail every
    correct solve.
    """
    added, _ = copies_in_order()
    assert len(added) == 3, (
        f"nothing was copied onto the release branch: {len(added)} commit(s) "
        f"descend from `{RELEASE_TIP}`. The originals staying put is only half "
        "of the request."
    )
    below = resolve_one(BELOW_THE_RUN)
    main_tip = resolve_one(MAIN_TIP)
    ordered_originals = [resolve_one(description) for description in RUN]
    span = change_ids(
        f"change_id({below})::change_id({main_tip})")
    expected_span = {below, main_tip} | set(ordered_originals)
    assert set(span) == expected_span, (
        "main no longer holds the run between "
        f"`{BELOW_THE_RUN}` and `{MAIN_TIP}`.\n  missing: %s\n  extra:   %s"
        % (describe(expected_span - set(span)), describe(set(span) - expected_span))
    )
    parent = commit_id_of(below)
    for description, cid in zip(RUN, ordered_originals):
        assert parents_of(cid) == [parent], (
            f"`{description}` ({cid[:12]}) no longer sits where it did on main; "
            f"its parent is {parents_of(cid)}, expected {[parent]}. Copying is "
            "not moving."
        )
        parent = commit_id_of(cid)
    assert not set(ordered_originals) & set(added), (
        "the commits on the release branch ARE the originals, not copies of "
        "them: " + describe(set(ordered_originals) & set(added))
    )
    marks = change_ids('bookmarks(exact:"main")')
    assert marks == [main_tip], (
        f"the `main` bookmark no longer marks `{MAIN_TIP}`; it marks "
        f"{describe(marks)}."
    )


def test_nothing_else_in_the_repository_moved():
    """No collateral damage above or below the run.

    Copying three commits onto a release branch is not a licence to touch the
    unrelated work on either side of them, or the release branch's own commit.
    """
    snapshot_working_copy()
    expected = {
        BELOW_THE_RUN: {"src/client/limits.py"},
        MAIN_TIP: {"CHANGELOG.md"},
        RELEASE_TIP: {"config.toml"},
        "sketch the refund endpoint": {"src/api/refund.py"},
    }
    for description, paths in expected.items():
        cid = resolve_one(description)
        changed = paths_changed(cid)
        assert changed == paths, (
            f"`{description}` ({cid[:12]}) should change exactly "
            f"{sorted(paths)}; it changes {sorted(changed)}."
        )
