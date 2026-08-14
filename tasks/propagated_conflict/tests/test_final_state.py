"""Verifier for the propagated_conflict task.

The request is one line: resolve the retry-backoff conflict where it started,
keeping both sides, and leave the stack as the same four commits.

WHAT MAKES THIS TASK DIFFERENT FROM THE SUITE'S OTHER CONFLICT WORK
===================================================================

Every other conflict in the suite is resolved where it is found. Here the
conflict was created by a rebase in the middle of a four-commit stack and has
propagated: `jj log` shows THREE conflicted commits, and only one of them is
the origin. Resolving the one you are standing on -- the git-shaped move,
because in git a conflict is a halt in the working tree and there is nowhere
else to put the fix -- leaves the other two conflicted and is caught by
test_no_conflict_is_left_in_the_repository. Resolving at the origin lets jj
carry the resolution up the stack on its own, which is the model this task
exists to measure.

WRITTEN AGAINST AN OBSERVED END STATE (R7)
==========================================

The fixture was built from environment/Dockerfile and solved twice in a
container of that image, on the pinned jj 0.44.0, before any assertion below
was written. The two routes were:

  A. `jj edit <origin>`, write the union into src/client/retry.py, done.
  B. the route jj ITSELF recommends -- and it prints the recipe unprompted, in
     the hint attached to `jj status`:
         jj new <origin>; ...resolve...; jj squash

Three things those runs showed, each of which changed an assertion here:

  * ROUTE B LEAVES AN EXTRA COMMIT. `jj squash` empties the scratch commit,
    jj abandons it and mints a FRESH empty `@` hanging off the origin as a
    sibling of the stack. A "the repository holds exactly four commits above
    main" test would fail jj's own recommended route. So the four-commit
    assertion is made over the DAG range between the anchored first and last
    stack commits, which that sibling is not in, and the no-fifth-commit half
    ignores EMPTY commits -- rather than ignoring everything outside the tip's
    descendants, which is what it did until a described fifth commit hanging
    off main was measured scoring 1.000. See
    test_the_stack_is_still_four_commits_with_both_sides_kept.

  * A DESCRIBED EMPTY COMMIT IS ALSO A CORRECT SOLVE. `jj commit -m "..."` on
    a working copy parked at the origin -- an ordinary way to finish, after the
    resolution has already been squashed in -- leaves an empty commit that is
    DESCRIBED. An exemption reading "empty AND undescribed" counted it as a
    forbidden fifth commit and docked a correct solve to 0.667 (measured). The
    exemption is therefore `empty()` alone: an empty commit carries no content
    and so cannot encode a wrong answer however it is described. The comment in
    that test records why duplicate_range chose the narrower form for itself and
    why the difference is right.

  * `@` DOES NOT COME BACK. Route A ends with `@` parked on the origin commit,
    not on the stack tip where the bootstrap left it. Nothing here reads `@`'s
    position, per R2 and the three de-positionalisations that preceded it.

  * `description(exact:"...")` DOES NOT MATCH. jj descriptions carry a trailing
    newline, so the exact: form silently matches nothing and every lookup
    returns empty. Every fallback revset below uses substring:.

THE CONTENT IS GRADED BECAUSE `:ours` AND `:theirs` ARE STRUCTURALLY PERFECT
===========================================================================

Measured: `jj resolve --tool :ours` at the origin exits 0, clears the conflict
from all three commits, keeps every change id, and leaves the stack four
commits long. It passes every structural assertion in this file. The only thing
wrong with it is that `RETRY_BUDGET` is gone -- the agent kept one side of a
request that said keep both. That is why two of the three scored tests read
file content, and why the fixture is built so that the union is the only
resolution with a defensible reading (environment/Dockerfile, invariants 3-4).

WHAT A SCORE ON THIS TASK ACTUALLY EVIDENCES -- READ BEFORE QUOTING A 1.0
=========================================================================

Recorded plainly so nobody later reads 1.0 here as more than it is. None of
this is a defect to be patched in passing: it is what this fixture can and
cannot support, measured on this image rather than argued.

  * ON THE QUESTION IT EXISTS TO ASK, IT IS A TWO-LEVEL INSTRUMENT: 0.333 or
    1.0. The three scored tests do not fail independently on that axis, because
    two of them turn on one content judgement (see below). Every route that
    resolves the conflict at all scores 0.333 if it did the git-shaped thing --
    resolving anywhere but the origin fails two together, and so do `:ours` and
    `:theirs` -- and 1.0 if it used jj's model. There is no partial credit
    between those for a better or worse resolution. Read that axis as a
    three-way verdict -- did nothing / did the git-shaped thing / used jj's
    model -- and never as a proportion of a job done.

    ONE BAND SITS BETWEEN THEM, AND IT IS THE FOUR-COMMIT CLAUSE, ON PURPOSE.
    A correct resolution that also leaves a forbidden fifth commit scores
    0.667: it passes the conflict and origin-content tests and fails
    test_the_stack_is_still_four_commits_with_both_sides_kept on that test's
    structural half alone. Measured, both on this image with the anchor
    present: a described non-empty commit ON THE TIP 0.667, and one FORKED OFF
    THE ORIGIN 0.667. That band is the whole point of folding the constraint
    into a scored test -- before it, the first of those scored 0.667 purely
    from test.sh's exit-status cap and the second scored a clean 1.000 -- so it
    is a real third outcome rather than a wobble in a two-level reading. What
    stays two-level is the judgement about WHERE the conflict was resolved.

  * jj PRINTS MOST OF THE ROUTE. `jj status` in the handover state attaches a
    hint that NAMES the origin commit and spells out `jj new <origin>` ...
    resolve ... `jj squash`. The part this task is described as measuring --
    work out where a propagated conflict started -- is therefore handed over by
    the tool to any agent that reads its own terminal. What survives is real
    but smaller: whether the agent acts on that instead of fixing the file in
    front of it, which is what every other conflict task in the suite rewards.
    A 1.0 here is evidence of taking jj's advice, not of knowing unprompted
    where a propagated conflict lives.

  * TWO OF THE THREE SCORED TESTS TURN ON ONE CONTENT JUDGEMENT.
    test_the_resolution_lives_where_the_conflict_started reads
    src/client/retry.py at the origin, and
    test_the_stack_is_still_four_commits_with_both_sides_kept reads the same
    file at the tip -- where jj has propagated the same bytes. An agent that
    gets the union right gets both; one that gets it wrong loses both. The
    second test is not merely a copy of the first, because it also carries the
    four-commit constraint, which is an independent claim and the only one an
    otherwise-correct solve can fail on its own. But its CONTENT half is the
    first test counted twice, so the effective scored width of this task is
    nearer two judgements than three.

  * WHAT WOULD ACTUALLY RAISE IT, unbuilt on purpose: a SECOND conflicted path
    whose origin is a DIFFERENT commit, so that jj's hint names one of them and
    the agent has to find the other unaided. That is a fixture redesign, not an
    assertion change, and it is deliberately not attempted here.
"""

import subprocess

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/checkout-api"
CONFLICTED_PATH = "src/client/retry.py"

# The four commits of the stack, oldest first. These are descriptions used to
# look up ANCHORED change ids; the anchor is what makes them identities rather
# than labels, and a rebuilt repository cannot produce them.
STACK = (
    "count retry attempts in the charge metrics",
    "make the retry budget configurable",
    "stop retrying once the budget is spent",
    "note the retry budget in the changelog",
)
FIRST, ORIGIN, MIDDLE, TIP = STACK

# Which paths each stack commit is responsible for. Disjoint by construction, so
# a route that shuffles content between commits while clearing the conflict is
# visible without reading a byte of any file.
OWN_PATHS = {
    FIRST: {"src/api/metrics.py"},
    ORIGIN: {"config.toml", CONFLICTED_PATH},
    MIDDLE: {CONFLICTED_PATH, "tests/test_retry.py"},
    TIP: {"CHANGELOG.md"},
}

# The one satisfying content of src/client/retry.py AT THE ORIGIN COMMIT: main's
# rename applied in place, the stack's constant on the line after it, and
# nothing else disturbed. This is not a guess -- it is what both solve routes
# produced, read back out of the container with `jj file show`.
#
# It is a constant here for the same reason restore_interactive's settings.toml
# is: it is the graded content itself, not a stand-in for a computation. The
# structural claims around it are all evaluated live.
RESOLVED_AT_ORIGIN = """\
import time

MAX_ATTEMPTS = 4
REQUEST_TIMEOUT = 5.0
RETRY_BUDGET = 30.0
BACKOFF_BASE = 0.2


def with_backoff(call, attempts=MAX_ATTEMPTS, budget=RETRY_BUDGET, sleep=time.sleep):
    delay = BACKOFF_BASE
    for attempt in range(attempts):
        try:
            return call(timeout=REQUEST_TIMEOUT)
        except OSError:
            if attempt == attempts - 1:
                raise
            sleep(delay)
            delay *= 2
"""

# jj renders a materialised conflict with these. Finding any of them in a file
# read out of a commit means that commit is still conflicted.
CONFLICT_MARKERS = ("<<<<<<<", ">>>>>>>", "%%%%%%%", "+++++++")

_snapshotted = False


def snapshot_working_copy():
    """The one working-copy snapshot this verifier takes, deliberately.

    A solve may end having written the resolution to disk without running a
    further jj command, in which case `@`'s stored tree does not have it yet.
    Every read below is of committed state, so the repository has to be in the
    state the agent left it before any of them run. Snapshotting preserves
    change ids, so it cannot disturb the anchor.
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


def graded(description):
    """The revset naming a bootstrap commit: its anchored change id if there is
    an anchor, and `description(substring:...)` if there is not.

    change_id_or_fallback returns a REVSET, not always a change id -- so it is
    evaluated to get a concrete id rather than being interpolated into
    `change_id(...)`, which would be malformed on the fallback path and made
    every test here fail in cold CI the first time this was run.
    """
    return change_id_or_fallback(
        description, 'description(substring:"%s")' % description,
        repo=PROJECT_DIR)


def change_ids(revset):
    out = jj_ok("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\\n"')
    return [line for line in out.splitlines() if line]


def resolve_one(description):
    """The single visible commit the anchor (or the fallback) names."""
    snapshot_working_copy()
    found = change_ids(graded(description))
    assert len(found) == 1, (
        f"the bootstrap commit `{description}` resolves to {len(found)} "
        "visible commit(s), expected exactly one."
    )
    return found[0]


def file_at(revset, path):
    """A file's content at a revision, or None when it is not there."""
    result = jj("file", "show", "-r", revset, path)
    return result.stdout if result.returncode == 0 else None


def describe(cids):
    if not cids:
        return "(none)"
    revset = " | ".join(f"change_id({c})" for c in sorted(cids))
    out = jj_ok("log", "-r", revset, "--no-graph",
                "-T", 'change_id.short(8) ++ " " ++ description.first_line() ++ "\\n"')
    return "; ".join(line for line in out.splitlines() if line)


def test_no_conflict_is_left_in_the_repository():
    """`conflicts()` is empty -- everywhere, not just in the three that showed.

    This is the test the resolve-where-you-are-standing route fails: fixing the
    working copy clears the tip and leaves the origin and the commit between
    them conflicted. It is deliberately repo-wide rather than scoped to the
    stack, because the propagation reached `@` too.
    """
    snapshot_working_copy()
    still = change_ids("conflicts()")
    assert not still, (
        "the repository still holds conflicted commit(s): "
        f"{describe(still)}.\nA conflict resolved in a descendant does not "
        "reach the commit it came from; resolving it where it started lets jj "
        "carry the resolution up the stack on its own."
    )


def test_the_resolution_lives_where_the_conflict_started():
    """src/client/retry.py at the anchored origin commit, line by line.

    Compared against the one content that keeps both sides, rstripped per line
    so trailing whitespace is not the difference between 1.0 and 0.
    """
    snapshot_working_copy()
    cid = resolve_one(ORIGIN)
    content = file_at(f"change_id({cid})", CONFLICTED_PATH)
    assert content is not None, (
        f"{CONFLICTED_PATH} is missing from `{ORIGIN}` ({cid[:12]}), the commit "
        "the conflict started in."
    )
    found = [line.rstrip() for line in content.splitlines()]
    expected = [line.rstrip() for line in RESOLVED_AT_ORIGIN.splitlines()]
    if found == expected:
        return
    markers = [m for m in CONFLICT_MARKERS if any(m in line for line in found)]
    if markers:
        raise AssertionError(
            f"`{ORIGIN}` ({cid[:12]}) is still conflicted: {CONFLICTED_PATH} "
            f"there still carries conflict markers {markers}. The conflict "
            "started in this commit, so this is where the resolution belongs."
        )
    diff = [
        f"  line {n}: expected {want!r}, found {got!r}"
        for n, (want, got) in enumerate(
            zip(expected, found + [None] * len(expected)), start=1)
        if want != got
    ]
    raise AssertionError(
        f"{CONFLICTED_PATH} at `{ORIGIN}` ({cid[:12]}) is not the resolution "
        "that keeps both sides.\n" + "\n".join(diff[:8]) +
        (f"\n  ... and {len(diff) - 8} more line(s)" if len(diff) > 8 else "") +
        f"\n  (expected {len(expected)} lines, found {len(found)})"
    )


def test_the_stack_is_still_four_commits_with_both_sides_kept():
    """The end state the request asked to be left standing.

    TWO CLAUSES OF THE ONE-LINE REQUEST ARE GRADED TOGETHER HERE, DELIBERATELY.

    "leave the stack as the same four commits" used to be a test of its own,
    and as one it was decorative -- because it PASSES ON THE UNTOUCHED IMAGE.
    The bootstrap stack already is those four commits, so the test sat in
    tests/vacuity_floor.json, and tests/test.sh drops floored names from BOTH
    sides of its fraction. Breaking the constraint therefore cost nothing the
    fraction could express. Measured on this image, before the merge:

      * a correct resolution at the origin PLUS a forbidden fifth commit on top
        of the tip scored 0.667 -- and every point of that penalty came from
        test.sh's exit-status cap, not from the constraint, which contributed
        nothing to either side of the fraction;
      * a correct resolution PLUS a fifth described commit that was NOT a
        descendant of the tip scored a clean 1.000, because the old check
        looked only at `descendants(tip)` and could not see it at all.

    Half the prompt was unenforced. Folding the range check into this SCORED
    test is what makes the constraint cost a real third of the score, and
    widening it from descendants-of-the-tip to the whole repository is what
    makes it see the sibling. Both wrong routes now score 0.667.

    "keeping both sides" is graded at the TIP because `jj resolve --tool :ours`
    and `--tool :theirs` both exit 0, clear every conflict and leave the stack
    structurally perfect while silently discarding one side's work. Measured:
    `:ours` drops `RETRY_BUDGET` while leaving `budget=RETRY_BUDGET` in the
    signature, so the file it produces does not even import.

    Unpicking the stack and rebuilding it is ruled out by end state alone: the
    range does not resolve to the four ANCHORED change ids, which a rebuilt
    repository cannot reproduce.
    """
    snapshot_working_copy()
    anchored = [resolve_one(description) for description in STACK]

    span = change_ids(f"change_id({anchored[0]})::change_id({anchored[-1]})")
    assert set(span) == set(anchored), (
        "the stack between `%s` and `%s` is no longer the four commits it was.\n"
        "  missing: %s\n  extra:   %s"
        % (FIRST, TIP, describe(set(anchored) - set(span)),
           describe(set(span) - set(anchored)))
    )

    # Nothing was ADDED anywhere -- not merely nothing on top of the tip.
    #
    # Everything the request permits is an ancestor of the stack tip: the four
    # stack commits themselves, and main and the history below it. So the check
    # is the whole repository minus that ancestry, rather than the tip's
    # descendants; a described fifth commit hanging off main is not in the
    # stack's descendants, and under the old form it scored 1.000.
    #
    # THE BREADTH IS DELIBERATE, AND IT IS BROADER THAN THE SENTENCE "the stack
    # is four commits". `all() ~ ...` means a non-empty described commit ANYWHERE
    # outside the tip's ancestry fails this, not only one attached to the stack.
    # That is right for THIS fixture and worth stating rather than leaving to be
    # rediscovered:
    #
    #   * this repository contains nothing but `main`, the history below it and
    #     the four-commit stack. There is no second branch, no unrelated work,
    #     nothing a legitimate solve of THIS request would leave outside that
    #     ancestry. So "outside the tip's ancestry" and "a commit the agent
    #     added" are the same set here, and the wide form is a faithful reading
    #     of "leave the stack as the same four commits" rather than a stricter
    #     one bolted onto it.
    #   * anything narrower reopens the hole this widening closed. The agent
    #     CHOOSES where to fork, so scoping the check to any one subtree --
    #     descendants of the tip, descendants of the origin, the stack's own
    #     range -- leaves a place to put a fifth commit where the check cannot
    #     see it. `descendants(tip)` was that mistake and it scored a clean
    #     1.000 (module docstring); picking a different subtree would only move
    #     the blind spot rather than remove it.
    #
    # IF THE FIXTURE EVER GAINS A SECOND, UNRELATED LINE OF WORK, this revset has
    # to be rescoped -- to the stack's ancestry plus whatever that line is -- or
    # it will start failing solves for commits that were never the agent's doing.
    # It is safe today because of a property of the fixture, not because of a
    # property of the request, and that distinction is the thing to check before
    # copying this revset into another task.
    #
    # EMPTY commits are subtracted -- described or not. Two reasons, and the
    # second is why the exemption is not the narrower "empty AND undescribed":
    #
    #   * the route jj ITSELF recommends leaves an empty commit behind: `jj
    #     squash` empties the scratch commit, jj abandons it and mints a fresh
    #     empty `@` as a sibling of the stack (see the module docstring). That
    #     one happens to be undescribed, so the narrow form covered it.
    #   * but `jj commit -m "..."` on a parked working copy leaves an empty
    #     commit that IS described. That is an ordinary way to finish a solve --
    #     the resolution is already squashed into the origin, so the commit the
    #     agent makes to "save" it captures nothing -- and under the narrow form
    #     it counted as a forbidden fifth commit and cost a correct solve a
    #     third of its score. Measured on this image, below.
    #
    # The claim the exemption rests on: an EMPTY commit carries no content, so
    # it cannot encode a wrong answer however it is described. Everything this
    # test is defending against -- a fix-up on top, a rebuilt stack, a resolution
    # parked in a fifth commit instead of reaching the origin -- has to CHANGE
    # SOMETHING to be wrong, and any of those is non-empty and still caught
    # (measured: a described non-empty commit on the tip, and one forked off the
    # origin, both still fail).
    #
    # NOT THE SAME CHOICE AS duplicate_range, DELIBERATELY. That task
    # (claude/new-tasks-3) excludes only `empty() & description(exact:"")`, the
    # narrow form, and it is right to. There the deliverable IS a commit: the
    # agent is asked to produce a copy, so a described commit is an ASSERTION --
    # something offered AS the copy -- and a described empty one is a claim to
    # have done the work without having done it, which must fail. Here the
    # deliverable is FILE CONTENT AT AN ANCHORED COMMIT; no commit the agent adds
    # can ever be the answer, and this test is a "nothing else was added"
    # constraint rather than a grader. A description carries evidential weight
    # there and none here, so the same word means different things and the two
    # tasks land on different revsets on purpose.
    added = change_ids(
        f"all() ~ root() ~ ::change_id({anchored[-1]}) ~ empty()"
    )
    assert not added, (
        f"a commit was added to the repository: {describe(added)}. The request "
        "was to leave the stack as the same four commits, and a fix-up commit "
        "does not reach the commit the conflict started in."
    )

    pointed = change_ids('bookmarks(exact:"retry-backoff")')
    assert pointed and set(pointed) <= set(anchored), (
        "the `retry-backoff` bookmark no longer marks one of the four stack "
        f"commits; it points at {describe(pointed)}."
    )

    cid = anchored[-1]
    content = file_at(f"change_id({cid})", CONFLICTED_PATH)
    assert content is not None, (
        f"{CONFLICTED_PATH} is missing from the stack tip `{TIP}` ({cid[:12]})."
    )
    markers = [m for m in CONFLICT_MARKERS if m in content]
    assert not markers, (
        f"{CONFLICTED_PATH} at the stack tip still carries conflict markers "
        f"{markers}: the resolution has not reached the top of the stack."
    )
    lines = [line.strip() for line in content.splitlines()]
    assert "REQUEST_TIMEOUT = 5.0" in lines, (
        "main's side is gone: `REQUEST_TIMEOUT = 5.0` is not in "
        f"{CONFLICTED_PATH} at the stack tip. main renamed that constant "
        "before the branch was rebased onto it, and the request was to keep "
        "both sides."
    )
    assert "TIMEOUT = 5.0" not in lines, (
        "main's rename was reverted: `TIMEOUT = 5.0` is back in "
        f"{CONFLICTED_PATH}. Keeping both sides means keeping the rename too -- "
        "the call site main updated still says REQUEST_TIMEOUT."
    )
    assert "RETRY_BUDGET = 30.0" in lines, (
        "the branch's side is gone: `RETRY_BUDGET = 30.0` is not in "
        f"{CONFLICTED_PATH} at the stack tip. That constant is what `make the "
        "retry budget configurable` was for, and `with_backoff` still refers "
        "to it."
    )
    assert "return call(timeout=REQUEST_TIMEOUT)" in lines, (
        "the call site no longer uses main's renamed constant, so main's half "
        "of the change did not survive intact."
    )


def test_each_commit_still_carries_its_own_diff():
    """No collateral damage: the four diffs are where they were.

    Nobody asking for a conflict to be fixed is asking for their commits to be
    reorganised, so this is the no-collateral-damage default rather than a
    stated requirement. It is also the check that catches a resolution folded
    into the wrong commit of the stack.
    """
    snapshot_working_copy()
    for description, expected in OWN_PATHS.items():
        cid = resolve_one(description)
        out = jj_ok("diff", "-r", f"change_id({cid})", "--name-only")
        changed = {line for line in out.splitlines() if line}
        assert changed == expected, (
            f"`{description}` ({cid[:12]}) should change exactly "
            f"{sorted(expected)}; it changes {sorted(changed)}."
        )
