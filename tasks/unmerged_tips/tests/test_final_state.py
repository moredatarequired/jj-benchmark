"""Verifier for the unmerged_tips task.

The task asks for the change ids of every tip that is not yet part of `main`,
one per line in `unmerged.txt`.

THE EXPECTED ANSWER IS NEVER A CONSTANT IN THIS FILE
====================================================

The reference revset is EVALUATED in the repository at verification time and the
file is compared against the set it returns. No change id is hard-coded, and no
revset the agent wrote is ever string-matched -- an agent that works the answer
out by reading `jj log` by eye is graded exactly like one that writes
`heads(main..)`, which is R3.

`main` in that revset is the bootstrap's `main`, addressed by its anchored
change id, falling back to `bookmarks(exact:"main")` when there is no anchor
file. Both spellings are evaluated rather than assumed: the bare revset `main`
is not used anywhere here, because a conflicted bookmark makes a bare
bookmark-name revset an ERROR on 0.44 and a verifier must not be breakable by
the repository state it is grading.

WRITTEN AGAINST AN OBSERVED END STATE (R7)
==========================================

The fixture was built from environment/Dockerfile and solved in a container of
that image with

    jj log -r 'heads(main..)' --no-graph -T 'change_id.short(8) ++ "\\n"' \\
        > unmerged.txt

before any of this was written. Two things that run showed, and that the
assertions below are shaped by:

  * the answer is FOUR heads -- three bookmarked (`rate-limit`,
    `oauth-refresh`, `idempotency`) and one with no bookmark at all (the
    settlement spike). Listing bookmarks gives three; `heads(all())` gives five,
    because `main` is itself a head.
  * writing the file rewrote the `idempotency` tip, which is `@`, and preserved
    its change id -- so producing the answer does not move the answer. That is
    why the fixture parks `@` on a tip that is already one of the four rather
    than on a fresh child of `main`, which would have been a fifth.

TWO READINGS, BOTH EVALUATED LIVE -- AND WHY (also R7)
======================================================

Three solves were run on the image before this was finalised, and the third
broke the single-revset version of this verifier:

  1. redirect `jj log -r 'heads(main..)'` into the file          -> agreed
  2. `jj new`, THEN compute and redirect                          -> agreed
  3. compute and redirect, THEN `jj commit` to save the answer    -> DISAGREED

In (3) the agent's four ids are right about the repository it read, and wrong
about the repository the verifier sees: `jj commit` puts a new empty commit on
top of the `idempotency` tip, so that tip stops being a head and the agent's own
scratch commit becomes one. In (2) the same thing happens in the other
direction and cancels out, which is why (2) passed and (3) did not.

Scoring (3) zero would be the `restore_interactive` / `track_untracked_file`
mistake again in a new costume -- failing a correct answer for a bookkeeping
habit. So the answer is compared against TWO reference sets, and each of the
three content assertions below passes if it holds against either of them. Both
are revsets evaluated in this repository at verification time; neither is a
constant, and the difference between them is exactly the commits the agent
created:

  * LIVE     `heads(main..)` -- the tips as they stand now.
  * HANDOVER `heads((main..) & <the commits the bootstrap handed over>)` -- the
    tips of the work that was already there, ignoring anything the agent added.

Any set that is wrong under the user's request is wrong under both, because they
differ only in agent-created commits; the second reading cannot admit a listing
of the wrong bookmarks, of `main`, or of an already-merged tip. With no anchor
file there is no handover set, so only the live reading is used -- never weaker
than the verifier was without it.

Short ids are what `change_id.short()` prints and what an agent will naturally
write, so every line is resolved through `change_id(<token>)` in the repository
rather than compared as text; a full 32-character id is accepted identically.

WHICH TIPS ARE "THE BOOKMARKED ONES" IS A FACT ABOUT THE HANDOVER
=================================================================

Two of the three content assertions split the answer into "the unmerged tips
that carry a bookmark" and "the unmerged tip that carries none". That split is
read out of the ANCHOR -- the bookmark placement `scripts/bootstrap_anchor.py`
recorded on the untouched image, per commit, in `repos[].commits[].bookmarks`.

It used to be read out of live `bookmarks()`, and that punished a correct solve.
An agent that produced all four ids AND put a bookmark of its own on the
settlement spike -- an ordinary thing to do while working, and not something the
instruction forbids -- moved the spike into the live bookmarked set. The
unbookmarked half then had nothing left in it, the guard below fired, and a
right answer scored 0.667 with a message that blamed the fixture for a state the
agent had created. Measured on this image before the change; measured 1.0 after.

The fixture's own invariant is "three of the four unmerged tips were handed over
with a bookmark on them and one was not". That is a property of the repository
AS HANDED OVER, so it is resolved through the anchor, which is the only record
of the handover state that survives the agent. With no anchor -- cold CI, or a
sweep run without `--write` -- it falls back to resolving the bookmarked
descriptions in BOOKMARKS by description, which is exactly as strong as the
description-based resolution used everywhere else in this file and still does
not consult a bookmark the agent created.

Note what the split can and cannot affect. The two halves are asserted as
`(reference & bookmarked) <= answer` and `(reference - bookmarked) <= answer`,
whose conjunction is `reference <= answer` for ANY partition. So the handover
bookmark set decides how credit is SPLIT between two marks; it cannot make a
wrong answer pass or a complete answer fail. What it buys is that the split
tracks the distinction the fixture was built to create -- "tips" misread as
"bookmarks" -- rather than tracking what the agent did to the repository.

WHAT PARTIAL CREDIT IS SHAPED LIKE, AND WHY IT IS SHAPED THAT WAY
=================================================================

tests/test.sh scores a failed run as (scored tests passed) / (scored tests),
where "scored" excludes the names in tests/vacuity_floor.json. So the SHAPE of
this file is the reward curve, and it has to be chosen rather than fallen into.

The first version of this file had five tests, of which one graded the answer
and two graded the file's format -- existence and one-id-per-line. Both of those
hold for ANY well-formed file whatever it says, so they were two free marks:
measured, a file naming ONE BOOKMARKED tip scored 0.75, while `bookmarks()` and
`heads(all())` -- coherent wrong answers, each three or four tips right --
scored 0.50. A barely-right answer outscored a nearly-right one, which is
backwards.

The second version fixed that by demoting the format checks from tests to a
PRECONDITION that all three content tests called. That over-corrected. Because
every scored test went through it, one bad line failed all three at once, and
the two cheapest bad lines are both reachable by ordinary means:

  * a DUPLICATED id. `jj log -r 'bookmarks() | heads(main..)'` without
    `sort -u`, or concatenating the output of two revsets, lists a tip twice.
    The instruction says "each id on its own line" and says nothing about
    duplicates. Measured: all four correct ids with one line repeated -> 0.
  * a token that does not resolve -- a stray word, a truncated prefix, an id
    from a commit the solve then rewrote away. Measured: all four correct ids
    plus one unresolvable token -> 0.

Both are formatting slips on top of a completely correct answer, and both scored
below every coherent wrong answer in the table. A verifier that ranks a right
answer with a typo beneath `bookmarks()` is not measuring the capability.

So well-formedness is now ONE SCORED TEST -- `test_the_answer_file_is_a_clean_
list_of_change_ids` -- and the three content tests are graded on the ids the
file does name, deduplicated, with unresolvable tokens dropped. A duplicate or a
stray token costs exactly one mark of four, the same as any single content
mistake and no more.

Why one scored test rather than the other option on the table, silently
deduplicating before grading: deduplicating makes a duplicate cost NOTHING, and
a file that lists an id twice is worse than one that does not, if only slightly.
It also fixes only half the problem -- an unresolvable token cannot be
deduplicated away, so it would have had to stop being a gate regardless, and
then the two defects belong in the same place. Pricing both at one mark says
what is true: the answer was right and the file was untidy.

The free-mark hazard that killed the first version does not come back, because
the content tests are still gated -- on a much weaker precondition. They need
the file to exist, to be non-empty, and to name at least ONE commit that exists
in this repository. A missing file, an empty file and a file of prose therefore
score 0 across all four, exactly as before: nothing here pays for output that
names nothing. What earns the fourth mark is a clean list of real change ids,
which a nop agent does not have and a garbage answer does not have.

The three content assertions are the three independent ways this fixture makes
an answer wrong -- the same three the Dockerfile was built around:

  * nothing that is not an unmerged tip is listed (`main` itself, an
    already-merged tip, anything else);
  * every unmerged tip that CARRIED A BOOKMARK AT HANDOVER is listed;
  * the unmerged tip that carried NO BOOKMARK at handover is listed.

The last two are the two halves of "nothing missing", split where this task's
capability actually lives: "tips" read as "bookmarks" gets the first and misses
the second, and that is the whole reason the spike exists in the fixture.

MEASURED GRADIENT (jj 0.44.0, this image, whole `tests/test.sh` -> reward.txt)
=============================================================================

Every row below was run in a container of this image, solved by the script the
row names, and scored by the real tests/test.sh with the anchor present.

    untouched (no unmerged.txt)                           0
    empty unmerged.txt                                    0
    garbage prose                                         0
    wipe and rebuild the repository                       0
    all four tips                                         1
    all four tips, plus a bookmark on the spike           1
    all four tips, one line duplicated                    0.75
    all four tips, plus one unresolvable token            0.75
    the three bookmarked tips, spike missed               0.75
    spike kept, oauth-refresh missed                      0.75
    the unbookmarked spike alone                          0.75
    `heads(all())` -- four right, `main` extra            0.75
    one bookmarked tip alone                              0.5
    `bookmarks()` -- three right, two extra, one missing  0.5

Read that as one mark per independent defect, out of four. A right answer with
an untidy file, and a nearly-right answer missing one tip, both cost one mark.
An answer that is wrong in two ways at once -- `bookmarks()` lists commits that
are not unmerged tips AND misses the spike -- costs two. Nothing vacuous scores
at all, and a correct solve is not charged for a bookmark it created.

CREDIT IS NOT MONOTONE IN THE NUMBER OF TIPS LISTED, AND THAT IS DELIBERATE
---------------------------------------------------------------------------

The three content marks are a three-bit vector -- no extras / the bookmarked
tips / the unbookmarked tip -- not a count. So the spike ALONE scores 0.75, the
same as three of the four tips, while a bookmarked tip alone scores 0.5. One id
outscores three, and it is not a bug: the spike is the whole discrimination this
fixture was built to make. An agent that finds it has read "tips" as heads of
the history; an agent that lists `rate-limit` and stops has demonstrated nothing
this task is about, because `rate-limit` is exactly what the wrong reading --
"the bookmarks" -- also produces. The bits are weighted by what they distinguish,
not by how many lines they cover.

Anyone quoting a single number for "a partial answer" is quoting the wrong
thing: which tips appear decides the score, not how many.
"""

import os
import re
import subprocess

import anchor
from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/checkout-api"
ANSWER_FILE = os.path.join(PROJECT_DIR, "unmerged.txt")

MAIN = "note the retry behaviour in the changelog"

# The four heads outside ::main, and the commits that must NOT appear.
EXPECTED_TIP_DESCRIPTIONS = (
    "cap charges per account",
    "refresh oauth tokens before they expire",
    "spike: batch settlement into one payout",
    "return 409 on duplicate keys",
)
MERGED_TIP = "retry failed charges with backoff"

# Every commit the bootstrap handed over. Used by the anti-pruning test: the
# cheapest way to make this task's answer small is to abandon the heads.
BOOTSTRAP_DESCRIPTIONS = EXPECTED_TIP_DESCRIPTIONS + (
    MAIN,
    MERGED_TIP,
    "add the charge endpoint",
    "extract the http client",
    "read the oauth client credentials from config",
    "add idempotency keys to charge requests",
)

BOOKMARKS = {
    "main": MAIN,
    "retry-backoff": MERGED_TIP,
    "release/2.4": MERGED_TIP,
    "rate-limit": "cap charges per account",
    "oauth-refresh": "refresh oauth tokens before they expire",
    "idempotency": "return 409 on duplicate keys",
}

# jj change ids are rendered in the reverse-hex alphabet k-z. Matching that
# rather than accepting arbitrary text is what lets each line be interpolated
# into a revset safely.
CHANGE_ID_RE = re.compile(r"\A[k-z]{4,32}\Z")

_snapshotted = False


def snapshot_working_copy():
    """The ONE working-copy snapshot this verifier takes, deliberately.

    `unmerged.txt` is written on disk and a solve need not snapshot it, so `@`'s
    stored tree may not mention it. Nothing below reads the file out of a tree
    -- it is read off disk -- but the reference revset is evaluated against the
    repository, and the repository has to be in the state the agent left it.
    Snapshotting preserves change ids, so it cannot disturb the anchor.
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


def change_ids(revset):
    out = jj_ok("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\\n"')
    return [line for line in out.splitlines() if line]


def graded(description):
    return change_id_or_fallback(
        description, 'description(substring:"%s")' % description,
        repo=PROJECT_DIR)


def resolve_one(revset, what):
    found = change_ids(revset)
    assert len(found) == 1, (
        f"expected `{revset}` to name exactly one commit ({what}), it names "
        f"{len(found)}: {found}"
    )
    return found[0]


def unmerged_revset():
    """`main..`, with `main` addressed by the bootstrap's own change id."""
    main = resolve_one(graded(MAIN), "main")
    return f"all() ~ ::change_id({main})"


def handover_change_ids():
    """The change ids the bootstrap handed over, or None when there is no anchor.

    Read from the anchor rather than from BOOTSTRAP_DESCRIPTIONS so that the
    handover set is a measurement of the image, not a list in this file that
    could drift from it.
    """
    try:
        record = anchor.load()
    except anchor.AnchorUnavailable as exc:
        print("%s: only the live reading of the tips is used (%s)"
              % (anchor.IDENTITY_NOT_CLAIMED, exc))
        return None
    found = set()
    for repo in record["repos"]:
        for commit in repo["commits"]:
            found.add(commit["change_id"])
        for working_copy in repo.get("working_copies") or []:
            found.add(working_copy["change_id"])
    return found or None


def reference_tips():
    """The reference answers: the live reading, and the handover reading.

    Both are revsets evaluated in the repository at verification time -- see the
    module docstring for why there are two and what separates them. Returns a
    list of (label, set) with the live reading always first.
    """
    snapshot_working_copy()
    unmerged = unmerged_revset()
    readings = [("live `heads(main..)`", set(change_ids(f"heads({unmerged})")))]

    handover = handover_change_ids()
    if handover is not None:
        visible = set(change_ids("all() ~ root()"))
        anchored = sorted(handover & visible)
        if anchored:
            restriction = " | ".join(f"change_id({c})" for c in anchored)
            readings.append((
                "handover `heads((main..) & <bootstrap commits>)`",
                set(change_ids(f"heads(({unmerged}) & ({restriction}))")),
            ))
    return readings


def answer_lines():
    """The non-blank lines of unmerged.txt, verbatim, with the trailing \\n gone."""
    assert os.path.isfile(ANSWER_FILE), f"{ANSWER_FILE} does not exist."
    with open(ANSWER_FILE) as handle:
        text = handle.read()
    return text, [line.strip() for line in text.splitlines() if line.strip()]


def resolve_token(token):
    """The one visible commit `token` names, or None if it names none or many.

    Never raises and never asserts: an unresolvable token is a thing this
    verifier has to be able to REPORT, so it must not be a thing that stops the
    verifier. `jj log -r 'change_id(<unknown prefix>)'` exits non-zero on 0.44,
    which is why this goes through jj() rather than jj_ok().
    """
    if not CHANGE_ID_RE.match(token):
        return None
    result = jj("log", "-r", f"change_id({token})", "--no-graph",
                "-T", 'change_id ++ "\\n"')
    if result.returncode != 0:
        return None
    found = [line for line in result.stdout.splitlines() if line]
    return found[0] if len(found) == 1 else None


def graded_answer():
    """The ids the file names -- the precondition of the three CONTENT tests.

    Deliberately weak, and deliberately not the same thing as the file being
    well formed. Duplicates collapse and unresolvable tokens are dropped, so a
    correct answer with an untidy line is graded on its content and pays for the
    untidiness once, in test_the_answer_file_is_a_clean_list_of_change_ids
    (see the module docstring for the measurement that forced this apart).

    What it still refuses to grade is output that names nothing: no file, an
    empty file, or a file with no resolvable id in it. Those fail here, and
    therefore fail all three content tests as well as the format test, which is
    what keeps a nop agent and a garbage answer at exactly 0.

    Resolution rather than text comparison is the point of the last step: a
    solve that prints 8-character ids, one that prints the full 32, and one that
    pastes them in by hand are the same answer and are graded the same.
    """
    snapshot_working_copy()
    _, lines = answer_lines()
    assert lines, f"{ANSWER_FILE} is empty."
    resolved = {found for found in (resolve_token(t) for t in lines) if found}
    assert resolved, (
        f"{ANSWER_FILE} has {len(lines)} non-blank line(s) and not one of them "
        "names a commit in this repository, so there is no answer here to "
        f"grade. Lines: {lines[:5]}"
    )
    return resolved


def handover_bookmarked_commits():
    """The commits that carried a bookmark IN THE FIXTURE AS HANDED OVER.

    Read from the anchor's per-commit `bookmarks`, never from live
    `bookmarks()`: a bookmark the AGENT created is not evidence about the
    fixture, and consulting one made a correct solve that bookmarked the spike
    score 0.667 with a message blaming the fixture. See the module docstring.

    Falls back to resolving the bookmarked descriptions in BOOKMARKS when there
    is no anchor -- the same description-based resolution the rest of this file
    abstains to, and still not a reading of the agent's bookmarks.
    """
    def by_description(why):
        print("%s: the handover bookmark placement is resolved by description "
              "instead (%s)" % (anchor.IDENTITY_NOT_CLAIMED, why))
        return {resolve_one(graded(description), description)
                for description in sorted(set(BOOKMARKS.values()))}

    try:
        record = anchor.load()
    except anchor.AnchorUnavailable as exc:
        return by_description(exc)
    found = {
        commit["change_id"]
        for repo in record["repos"]
        for commit in repo["commits"]
        if commit.get("bookmarks")
    }
    if not found:
        return by_description(
            "the anchor records no bookmark on any bootstrap commit, so it "
            "predates the per-commit `bookmarks` key")
    return found


def describe(cids):
    """change id -> first description line, for readable failure messages."""
    if not cids:
        return "(none)"
    revset = " | ".join(f"change_id({c})" for c in sorted(cids))
    out = jj_ok("log", "-r", revset, "--no-graph",
                "-T", 'change_id.short(8) ++ " " ++ description.first_line() ++ "\\n"')
    return "; ".join(line for line in out.splitlines() if line)


def test_the_answer_file_is_a_clean_list_of_change_ids():
    """The format mark: one change id per line, each real, none repeated.

    One scored test rather than a precondition of the three content tests. As a
    precondition it was a GATE: one repeated line or one stray token scored the
    whole task 0, below `bookmarks()`, even when all four ids were right and
    both slips are reachable by ordinary means (`jj log -r 'bookmarks() |
    heads(main..)'` without `sort -u`; a concatenation of two revsets). As a
    test it costs one mark of four -- the same as any single content mistake.

    It is also not a free mark for a well-formed lie, because it is the only
    test here that does not look at the content of the answer and the three that
    do are still gated on the file naming at least one real commit. A file of
    prose fails this AND all three of those.
    """
    snapshot_working_copy()
    text, lines = answer_lines()
    assert lines, f"{ANSWER_FILE} is empty."
    assert "<Error:" not in text, (
        f"{ANSWER_FILE} contains a jj template runtime error rendered inline "
        "(`<Error: ...>`), which jj 0.44 emits at exit 0. The file is not a "
        "list of change ids."
    )

    bad = [line for line in lines if not CHANGE_ID_RE.match(line)]
    assert not bad, (
        f"{ANSWER_FILE} has {len(bad)} line(s) that are not a single change id: "
        f"{bad[:5]}. Each id must be on its own line, with nothing else on it."
    )

    repeated = sorted({t for t in lines if lines.count(t) > 1})
    assert not repeated, (
        f"{ANSWER_FILE} lists the same id more than once: {repeated}. Each "
        "unmerged tip belongs on exactly one line."
    )

    resolved = {}
    unresolvable = []
    for token in lines:
        found = resolve_token(token)
        if found is None:
            unresolvable.append(token)
        else:
            resolved.setdefault(found, []).append(token)
    assert not unresolvable, (
        f"{ANSWER_FILE} has {len(unresolvable)} line(s) that do not name "
        f"exactly one visible commit in this repository: {unresolvable[:5]}."
    )

    aliased = {c: t for c, t in resolved.items() if len(t) > 1}
    assert not aliased, (
        f"{ANSWER_FILE} names the same commit under more than one prefix: "
        + "; ".join(f"{sorted(t)} all name {c[:12]}"
                    for c, t in sorted(aliased.items()))
    )


def test_no_commit_outside_the_unmerged_tips_is_listed():
    """Nothing in the file that is not a tip outside main -- the "no extras" half.

    This is also where the two named wrong answers are failed by name, because
    both of them fail HERE first, on something they added rather than on
    something they left out. `heads(all())` returns `main` itself, which is a
    head but is not a tip that is not yet part of main. `bookmarks()` returns
    the two bookmarks that are already ancestors of main (`retry-backoff` and
    `release/2.4`). Each is a mistake about a different word in the request, and
    each puts a commit in the answer that the request excludes.

    Set INCLUSION rather than equality, so that the two halves of the answer are
    scored independently: an incomplete answer whose every entry is a genuine
    unmerged tip passes this and fails the two below.
    """
    actual = graded_answer()
    readings = reference_tips()
    if any(actual <= expected for _, expected in readings):
        return

    main = resolve_one(graded(MAIN), "main")
    merged = resolve_one(graded(MERGED_TIP), MERGED_TIP)
    named = []
    if main in actual:
        named.append(
            "  `main` itself is listed. It is a head, but it is not a tip that "
            "is not yet part of main."
        )
    if merged in actual:
        named.append(
            "  the `retry-backoff` / `release/2.4` tip is listed; it was merged "
            "into main before the task started."
        )
    inside = {c for c in actual if c in set(change_ids(f"::change_id({main})"))}
    if inside - {main, merged}:
        named.append(
            "  these are already part of main: %s" % describe(inside - {main, merged})
        )
    report = [
        f"  against the {label} reading, extra: {describe(actual - expected)}"
        for label, expected in readings
    ]
    raise AssertionError(
        f"{ANSWER_FILE} lists commits that are not tips outside main.\n"
        + "\n".join(named + report)
        + "\nEvery expected set is recomputed in this repository at "
        "verification time; none of them is a constant in the verifier."
    )


def test_every_bookmarked_unmerged_tip_is_listed():
    """The first half of "nothing missing": the tips a bookmark pointed at.

    Three of the four were handed over bookmarked (`rate-limit`,
    `oauth-refresh`, `idempotency`). Which commits those are comes from the
    anchor's record of the HANDOVER state, not from live `bookmarks()`, so a
    bookmark the agent created while working changes nothing here.
    """
    actual = graded_answer()
    marked = handover_bookmarked_commits()
    readings = reference_tips()
    assert any(expected & marked for _, expected in readings), (
        "the fixture no longer has a single bookmarked tip outside main, so "
        "this test can no longer say anything. Fix the fixture or this file."
    )
    if any((expected & marked) <= actual for _, expected in readings):
        return
    raise AssertionError(
        f"{ANSWER_FILE} is missing bookmarked tip(s) that are not yet part of "
        "main.\n"
        + "\n".join(
            f"  against the {label} reading, missing: "
            f"{describe((expected & marked) - actual)}"
            for label, expected in readings
        )
    )


def test_the_unbookmarked_tip_is_listed():
    """The second half of "nothing missing", and the one the task turns on.

    The settlement spike was handed over as a head outside main with no bookmark
    on it. An agent that reads "tips" as "the bookmarks" produces an answer that
    can pass the test above and still fail this one -- which is the distinction
    the fixture was built to create, so it is scored on its own rather than
    folded into a single all-or-nothing set comparison.

    "Carries no bookmark" is asked of the handover state, not of the repository
    at verification time. An agent that solves the task and then bookmarks the
    spike has still listed it; reading live `bookmarks()` here emptied this half
    and failed that solve.
    """
    actual = graded_answer()
    marked = handover_bookmarked_commits()
    readings = reference_tips()
    assert any(expected - marked for _, expected in readings), (
        "the fixture no longer has an unbookmarked tip outside main, so this "
        "test can no longer say anything. Fix the fixture or this file."
    )
    if any((expected - marked) <= actual for _, expected in readings):
        return
    raise AssertionError(
        f"{ANSWER_FILE} is missing tip(s) outside main that carry no bookmark. "
        "A tip is a head of the history, not a bookmark.\n"
        + "\n".join(
            f"  against the {label} reading, missing: "
            f"{describe((expected - marked) - actual)}"
            for label, expected in readings
        )
    )


def test_the_history_was_not_pruned_to_shrink_the_answer():
    """Every bootstrap commit still resolves and every bookmark is where it was.

    The reference set is computed from the repository, so the cheapest way to
    make a short answer right is to abandon the heads that would have been in
    it. This is an anti-fabrication check, not a method check: it cannot fail an
    honest solve of any shape. In particular it pins the SIX bootstrap bookmarks
    to the commits the bootstrap put them on without saying anything about
    bookmarks the agent added, which is why adding one is free.
    """
    snapshot_working_copy()
    for description in BOOTSTRAP_DESCRIPTIONS:
        cid = resolve_one(graded(description), description)
        assert change_ids(f"change_id({cid})"), (
            f"the bootstrap commit `{description}` ({cid[:12]}) is no longer "
            "visible."
        )
    for name, description in BOOKMARKS.items():
        cid = resolve_one(graded(description), description)
        pointed = change_ids(f'bookmarks(exact:"{name}")')
        assert pointed == [cid], (
            f"the `{name}` bookmark must still point at the bootstrap's "
            f"`{description}` ({cid[:12]}); it points at "
            f"{[p[:12] for p in pointed]}"
        )
