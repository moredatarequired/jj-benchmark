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

Short ids are what `change_id.short()` prints and what an agent will naturally
write, so every line is resolved through `change_id(<token>)` in the repository
rather than compared as text; a full 32-character id is accepted identically.
"""

import os
import re
import subprocess

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


def reference_tips():
    """The change ids of every head that is not an ancestor of `main`, NOW.

    Computed in the repository at verification time, so it describes the
    repository the agent is being graded on rather than the one the task author
    imagined. `main` is the bootstrap's `main`; see the module docstring.
    """
    snapshot_working_copy()
    main = resolve_one(graded(MAIN), "main")
    return set(change_ids(f"heads(all() ~ ::change_id({main}))"))


def answer_lines():
    """The non-blank lines of unmerged.txt, verbatim, with the trailing \\n gone."""
    assert os.path.isfile(ANSWER_FILE), f"{ANSWER_FILE} does not exist."
    with open(ANSWER_FILE) as handle:
        text = handle.read()
    return text, [line for line in text.splitlines() if line.strip()]


def test_unmerged_txt_was_written():
    """The deliverable exists and is not empty."""
    text, lines = answer_lines()
    assert lines, f"{ANSWER_FILE} is empty."
    assert "<Error:" not in text, (
        f"{ANSWER_FILE} contains a jj template runtime error rendered inline "
        "(`<Error: ...>`), which jj 0.44 emits at exit 0. The file is not a "
        "list of change ids."
    )


def test_each_line_holds_one_change_id():
    """One id per line, as asked -- no graph glyphs, no descriptions, no dupes."""
    _, lines = answer_lines()
    bad = [line for line in lines if not CHANGE_ID_RE.match(line.strip())]
    assert not bad, (
        f"{ANSWER_FILE} has {len(bad)} line(s) that are not a single change id: "
        f"{bad[:5]}. Each id must be on its own line, with nothing else on it."
    )
    tokens = [line.strip() for line in lines]
    duplicates = sorted({t for t in tokens if tokens.count(t) > 1})
    assert not duplicates, (
        f"{ANSWER_FILE} lists the same id more than once: {duplicates}"
    )


def resolved_answer():
    """Each line of the file resolved to a full change id in the repository.

    Resolution rather than text comparison is the whole point: a solve that
    prints 8-character ids, one that prints the full 32, and one that pastes
    them in by hand are the same answer and are graded the same.
    """
    snapshot_working_copy()
    _, lines = answer_lines()
    resolved = set()
    for line in lines:
        token = line.strip()
        assert CHANGE_ID_RE.match(token), (
            f"{token!r} in {ANSWER_FILE} is not a change id."
        )
        found = change_ids(f"change_id({token})")
        assert len(found) == 1, (
            f"{token!r} in {ANSWER_FILE} does not name exactly one visible "
            f"commit in this repository (it names {len(found)})."
        )
        resolved.add(found[0])
    return resolved


def describe(cids):
    """change id -> first description line, for readable failure messages."""
    if not cids:
        return "(none)"
    revset = " | ".join(f"change_id({c})" for c in sorted(cids))
    out = jj_ok("log", "-r", revset, "--no-graph",
                "-T", 'change_id.short(8) ++ " " ++ description.first_line() ++ "\\n"')
    return "; ".join(line for line in out.splitlines() if line)


def test_the_listed_ids_are_exactly_the_unmerged_tips():
    """Set equality against the revset, evaluated here and now."""
    expected = reference_tips()
    actual = resolved_answer()
    missing, extra = expected - actual, actual - expected
    assert not missing and not extra, (
        f"{ANSWER_FILE} does not list the tips that are outside main.\n"
        f"  missing: {describe(missing)}\n"
        f"  extra:   {describe(extra)}\n"
        "The expected set is recomputed in this repository at verification "
        "time; it is not a constant in the verifier."
    )


def test_nothing_already_in_main_is_listed():
    """The specific wrong answers, failed by name.

    Two cheap revsets give two different wrong answers here, and each is a
    mistake about a different word in the request. `bookmarks()` returns the two
    bookmarks that are already ancestors of main (`retry-backoff` and
    `release/2.4`) and misses the unbookmarked spike entirely -- that is
    "tips" read as "bookmarks". `heads(all())` returns `main` itself, which is a
    head -- that is "not yet part of main" left out altogether.
    """
    actual = resolved_answer()
    main = resolve_one(graded(MAIN), "main")
    merged = resolve_one(graded(MERGED_TIP), MERGED_TIP)
    inside = {c for c in actual if c in set(change_ids(f"::change_id({main})"))}
    assert not inside, (
        f"{ANSWER_FILE} lists commits that are already part of main: "
        f"{describe(inside)}"
    )
    assert main not in actual, (
        "`main` itself is listed. It is a head, but it is not a tip that is "
        "not yet part of main."
    )
    assert merged not in actual, (
        "the `retry-backoff` / `release/2.4` tip is listed; it was merged into "
        "main before the task started."
    )


def test_the_history_was_not_pruned_to_shrink_the_answer():
    """Every bootstrap commit still resolves and every bookmark is where it was.

    The reference set is computed from the repository, so the cheapest way to
    make a short answer right is to abandon the heads that would have been in
    it. This is an anti-fabrication check, not a method check: it cannot fail an
    honest solve of any shape.
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
