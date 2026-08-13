"""Verifier for the rebase_touched_commits task.

The request is one line: put the change ids of every commit my rebase changed
into touched.txt, one per line.

Nothing in the repository is meant to move. The whole difficulty is that the
answer is a property of the OPERATION LOG and cannot be read off the current
graph: the branch has five commits on it and the rebase changed four, because a
fifth was made after the rebase ran. Every cheap current-graph revset --
`main..retry-backoff`, `main..@`, `main..` -- returns that fifth commit too and
is wrong by exactly one.

THE EXPECTED ANSWER IS NEVER A CONSTANT IN THIS FILE
====================================================

It is recomputed here, at verification time, by differencing the repository
across the operation: `jj --at-op <the rebase>` and `jj --at-op <its parent>`,
and the change ids whose COMMIT id differs between the two are what the rebase
changed. No change id is hard-coded and no revset the agent wrote is ever
string-matched -- an agent that works the answer out by reading `jj op show` by
eye is graded exactly like one that scripts it, which is R3.

THE OPERATION IS FOUND BY WHAT IT DID, NOT BY WHAT JJ CALLED IT
===============================================================

The rebase is located as the one bootstrap operation that REPARENTED a commit --
where some surviving change id's set of parent change ids changed. jj's own
English for the operation ("rebase commit ... and descendants") is never read.

That signature was chosen after measuring the alternative. "The operation that
rewrote the most commits" also picks out the rebase here, but only four against
three: the `jj describe` in the bootstrap rewrites THREE commits, because
describing a commit rewrites all of its descendants too. A one-commit margin is
luck, not a signature. Reparenting separates them outright -- a describe
reparents nothing -- and the bootstrap check asserts the fixture keeps exactly
one such operation.

THE N4 ARTIFACT DOES NOT REACH THIS TASK, AND THAT WAS MEASURED
===============================================================

The hazard that broke unmerged_tips was an answer that is a function of the
CURRENT graph: the agent read it correctly, then `jj commit` moved the tips and
the verifier's reference set no longer matched the agent's correct answer.

Here the reference set is a function of two FIXED PAST OPERATIONS. The rebase
and its parent are immutable points in an append-only log, so nothing the agent
does afterwards can move them. That was not left as an argument -- the solve was
run twice on the image, once plainly and once followed by `jj commit` to save
the answer, and the recomputed reference set was identical in both runs. (The
`jj commit` run also rewrote `@`'s description to the agent's commit message,
which is why nothing here reads `@`'s description or its position.)

Resolution of the agent's tokens is likewise kept off the live repository: each
line is matched as a prefix against the union of the expected set and the
currently visible change ids, so an agent that hid or rewrote something cannot
turn a wrong answer into a crashed verifier.
"""

import os
import re
import subprocess

import anchor
from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/checkout-api"
ANSWER_FILE = os.path.join(PROJECT_DIR, "touched.txt")

# Every commit the bootstrap handed over, for the anti-fabrication check. The
# reference set is computed from the repository, so the cheapest way to make a
# short answer right would be to prune the history it is computed from.
BOOTSTRAP_DESCRIPTIONS = (
    "add the charge endpoint",
    "extract the http client",
    "regenerate the api client from the 2.4 schema",
    "retry failed charges with backoff",
    "cap the retry budget at 30 seconds per charge",
    "surface retry counts in the charge response",
    "note the retry behaviour in the changelog",
)
BOOKMARKS = {
    "main": "regenerate the api client from the 2.4 schema",
    "release/2.4": "extract the http client",
}

# jj change ids are rendered in the reverse-hex alphabet k-z. Matching that
# rather than accepting arbitrary text is what makes each line safe to compare.
CHANGE_ID_RE = re.compile(r"\A[k-z]{4,32}\Z")

_snapshotted = False


def snapshot_working_copy():
    """The one working-copy snapshot this verifier takes, deliberately.

    touched.txt is written on disk and a solve need not snapshot it. Nothing
    below reads the file out of a tree -- it is read off disk -- but the
    anti-fabrication check reads the repository, which has to be in the state
    the agent left it. Snapshotting preserves change ids, so it cannot disturb
    the anchor. It cannot disturb the reference set either: that is computed
    from operations that already happened.
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


# --------------------------------------------------------------------------
# Differencing the repository across the operation
# --------------------------------------------------------------------------

def handover_operation():
    """The newest operation as of bootstrap, or None when there is no anchor.

    Restricting the search to this operation's ancestry keeps it inside the
    BOOTSTRAP's operations. Operations are append-only, so anything the agent
    did lands after it; with no anchor the search runs over the whole log and
    takes the earliest candidate, which is the same operation.
    """
    try:
        record = anchor.load()
    except anchor.AnchorUnavailable as exc:
        print("%s: searching the whole operation log for the rebase and "
              "taking the earliest candidate (%s)"
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
    """change_id -> (commit_id, frozenset of parent change ids) at `op`.

    `--at-op` implies `--ignore-working-copy`, which is required so that
    reading history does not perturb what is being graded.
    """
    out = jj_ok("--at-op", op, "log", "-r", "all() ~ root()", "--no-graph",
                "-T", 'change_id ++ " " ++ commit_id ++ " [" '
                      '++ parents.map(|p| p.change_id()).join(",") ++ "]\\n"')
    state = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        cid, commit, parents = line.split(" ", 2)
        state[cid] = (
            commit,
            frozenset(p for p in parents.strip("[]").split(",") if p),
        )
    return state


_rebase = None


def the_rebase():
    """(the operation, what it changed) -- recomputed, never a constant.

    The rebase is the one bootstrap operation that reparented a surviving
    commit. What it "changed" is every change id whose commit id differs
    between the state at the operation and the state at its parent.
    """
    global _rebase
    if _rebase is not None:
        return _rebase
    candidates = []
    for op, parent in operations():
        if parent is None:
            continue
        before, after = visible_at(parent), visible_at(op)
        both = set(before) & set(after)
        reparented = {c for c in both if before[c][1] != after[c][1]}
        if reparented:
            changed = {c for c in both if before[c][0] != after[c][0]}
            candidates.append((op, changed))
    assert candidates, (
        "no operation in this repository's history reparented a commit, so "
        "the rebase the request refers to cannot be found. The fixture is "
        "built so that exactly one operation does; if this fires, the "
        "bootstrap changed."
    )
    _rebase = candidates[0]
    return _rebase


def describe(cids):
    if not cids:
        return "(none)"
    revset = " | ".join(f"change_id({c})" for c in sorted(cids))
    result = jj("log", "-r", revset, "--no-graph", "-T",
                'change_id.short(8) ++ " " ++ description.first_line() ++ "\\n"')
    if result.returncode != 0:
        return ", ".join(sorted(c[:8] for c in cids))
    return "; ".join(line for line in result.stdout.splitlines() if line)


# --------------------------------------------------------------------------
# The answer file
# --------------------------------------------------------------------------

def answer_lines():
    assert os.path.isfile(ANSWER_FILE), f"{ANSWER_FILE} does not exist."
    with open(ANSWER_FILE) as handle:
        text = handle.read()
    return text, [line for line in text.splitlines() if line.strip()]


def resolved_answer():
    """Each line resolved to a full change id, by unambiguous prefix.

    Resolution rather than text comparison is the point: a solve that writes
    8-character ids, one that writes the full 32, and one that pastes them in
    by hand are the same answer and are graded the same. The candidate pool is
    the expected set plus everything currently visible, so a line naming a real
    commit that simply is not part of the answer is reported as an extra rather
    than as an unresolvable token.
    """
    snapshot_working_copy()
    _, expected = the_rebase()
    pool = set(expected) | set(change_ids("all() ~ root()"))
    _, lines = answer_lines()
    resolved = set()
    for line in lines:
        token = line.strip()
        assert CHANGE_ID_RE.match(token), (
            f"{token!r} in {ANSWER_FILE} is not a change id."
        )
        matches = {cid for cid in pool if cid.startswith(token)}
        assert matches, (
            f"{token!r} in {ANSWER_FILE} does not name any commit in this "
            "repository, and is not one of the commits the rebase changed."
        )
        assert len(matches) == 1, (
            f"{token!r} in {ANSWER_FILE} is ambiguous -- it is a prefix of "
            f"{len(matches)} different change ids."
        )
        resolved.add(matches.pop())
    return resolved


def test_touched_txt_was_written():
    """The deliverable exists and is not empty."""
    text, lines = answer_lines()
    assert lines, f"{ANSWER_FILE} is empty."
    assert "<Error:" not in text, (
        f"{ANSWER_FILE} contains a jj template runtime error rendered inline "
        "(`<Error: ...>`), which jj 0.44 emits at exit 0. The file is not a "
        "list of change ids."
    )


def test_each_line_holds_one_change_id():
    """One id per line, as asked -- no graph glyphs, no descriptions, no dupes.

    `jj op show` names the same commit three times in its output -- once under
    Changed commits, again under Changed working copy, again under Changed
    local bookmarks -- so a careless scrape of it produces repeats. It also
    prints hidden predecessors in the `X/1` offset form, which is a revision
    spelling for the commit BEFORE the rebase, not the change id of what it
    changed.
    """
    _, lines = answer_lines()
    bad = [line for line in lines if not CHANGE_ID_RE.match(line.strip())]
    assert not bad, (
        f"{ANSWER_FILE} has {len(bad)} line(s) that are not a single change "
        f"id: {bad[:5]}. Each id must be on its own line, with nothing else "
        "on it."
    )
    tokens = [line.strip() for line in lines]
    duplicates = sorted({t for t in tokens if tokens.count(t) > 1})
    assert not duplicates, (
        f"{ANSWER_FILE} lists the same id more than once: {duplicates}"
    )


def test_the_listed_ids_are_exactly_what_the_rebase_changed():
    """Set equality against the operation difference, computed here and now."""
    op, expected = the_rebase()
    actual = resolved_answer()
    assert actual == expected, (
        f"{ANSWER_FILE} does not list the commits the rebase changed.\n"
        f"  missing: {describe(expected - actual)}\n"
        f"  extra:   {describe(actual - expected)}\n"
        f"The expected set is recomputed at verification time by reading this "
        f"repository at operation {op[:12]} and at its parent and taking the "
        "commits whose commit id differs; it is not a constant in the verifier."
    )


def test_no_commit_made_after_the_rebase_is_listed():
    """Named for the wrong solve it catches: reading the branch off `jj log`.

    The branch carries five commits and the rebase changed four, because the
    fifth was made afterwards. `main..retry-backoff`, `main..@` and `main..`
    all return that fifth commit, so every cheap current-graph answer includes
    a commit that did not exist when the rebase ran. The other cheap error --
    including main's own commit, which existed but was not moved -- is caught
    here too.
    """
    op, expected = the_rebase()
    at_rebase = set(visible_at(op))
    actual = resolved_answer()
    later = actual - at_rebase
    assert not later, (
        f"{ANSWER_FILE} lists {describe(later)}, which did not exist when the "
        "rebase ran. The current graph shows the branch as it is now, not what "
        "the operation changed."
    )
    untouched = (actual & at_rebase) - expected
    assert not untouched, (
        f"{ANSWER_FILE} lists {describe(untouched)}, which existed at the time "
        "of the rebase but was not changed by it."
    )


def test_the_history_was_not_rewritten_to_shrink_the_answer():
    """Every bootstrap commit still resolves and every bookmark is where it was.

    The reference set is computed from the repository's own operation log, so
    the cheapest way to make a short answer right would be to prune what it is
    computed from. This is an anti-fabrication check, not a method check: it
    cannot fail an honest solve of any shape.
    """
    snapshot_working_copy()
    for description in BOOTSTRAP_DESCRIPTIONS:
        found = change_ids(graded(description))
        assert len(found) == 1, (
            f"the bootstrap commit `{description}` resolves to {len(found)} "
            "visible commit(s), expected exactly one."
        )
    for name, description in BOOKMARKS.items():
        expected = change_ids(graded(description))
        pointed = change_ids(f'bookmarks(exact:"{name}")')
        assert pointed == expected, (
            f"the `{name}` bookmark must still point at `{description}`; it "
            f"points at {describe(set(pointed))}."
        )
