"""Verifier for the divergent_change task.

The request is one line: one commit is showing twice -- keep the copy with the
tests, drop the other, and repoint idempotency at it.

WHAT MAKES THIS TASK DIFFERENT FROM THE SUITE'S OTHER WORK
==========================================================

A divergent change is a thing git has no name for. Two visible commits carry
ONE change id, and the id that every other task in this suite uses as an
identity -- the one `jj rebase`, `jj squash` and `jj describe` all preserve --
here names two commits at once. `jj log -r <the change id>` refuses outright:

    Error: Change ID `ppzvomws` is divergent
    Hint: Use change offset to select single revision: ppzvomws/0, ppzvomws/1
    Hint: Use `change_id(ppzvomws)` to select all revisions

The git-shaped move is to treat the two entries as two commits and drop
whichever one looks newer or older. That is a coin flip here, and the fixture is
built so the coin lands wrong: `X/N` indexes every version ever recorded for X,
hidden ones included, NEWEST FIRST, so `/0` is the version built LAST -- which
in this repository is the one WITHOUT the tests.

WRITTEN AGAINST AN OBSERVED END STATE (R7)
==========================================

The fixture was built from environment/Dockerfile and solved in a container of
that image, on the pinned jj 0.44.0, before any assertion below was written.
Three things those runs showed, each of which changed an assertion here:

  * ABANDONING ONE VERSION DOES NOT UN-CONFLICT THE BOOKMARK. After
    `jj abandon <the other version>` the log is clean and the divergence is
    gone -- and `idempotency` is STILL conflicted, because one of its recorded
    targets is the now-hidden common ancestor. Measured. So the bookmark is
    scored by its own test, and that test cannot be written as "the revset
    resolves to one commit": after the abandon it already does, while the
    bookmark is still conflicted. It is written against the `conflict`
    template keyword on the LOCAL bookmark row (the row whose `remote` is
    empty), which is the only place the state is visible.

  * THE SURVIVOR IS NOT REWRITTEN. `jj abandon` of a sibling leaves the other
    version's commit id exactly as the bootstrap left it. Nothing here asserts
    that, though: an agent may legitimately arrive by a route that rewrites the
    survivor, and commit ids are never a fair assertion when they are avoidable.
    The content is graded instead.

  * `description(exact:"...")` DOES NOT MATCH. jj descriptions carry a trailing
    newline, so the exact: form silently matches nothing and every lookup
    returns empty. Every fallback revset below uses substring:.

THE CONTENT IS GRADED BECAUSE THE STRUCTURE ALONE CANNOT TELL THE SIDES APART
============================================================================

Both versions carry the same description and the same change id, so after the
wrong one survives, every structural fact about the repository is identical to
the right answer: one visible commit under that change id, an unconflicted
bookmark on it, nothing else moved. The ONLY difference is what is in the
commit. So the survivor's three files are compared byte for byte against the
version the fixture built -- which is also what stops the sideways cheat of
abandoning the right copy and hand-writing the test file into the wrong one.
"""

import subprocess

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/checkout-api"

# The divergent change, and the two commits that must be left alone. These are
# descriptions used to look up ANCHORED change ids; the anchor is what makes
# them identities rather than labels, and a rebuilt repository cannot produce
# them.
DIVERGED = "add idempotency key to charge requests"
MAIN_TIP = "route charges through handlers"
WORKING_HEAD = "start the rate-limit middleware"

BOOKMARK = "idempotency"
TEST_FILE = "tests/test_charge.py"

# What the surviving version of the change must contain, read back out of the
# container with `jj file show` after the fixture was built. The version that
# must NOT survive differs in exactly two of these: it has no tests/ file at all
# and its CHANGELOG.md is missing the last line.
SURVIVING_CONTENT = {
    "CHANGELOG.md": """\
# Changelog

## Unreleased
- charge endpoint
- idempotency keys on charge requests
""",
    "src/api/charge.py": """\
from decimal import Decimal

from client.http import post


IDEMPOTENCY_HEADER = "Idempotency-Key"


def charge(account_id, amount, currency="USD", idempotency_key=None):
    payload = {
        "account_id": account_id,
        "amount": str(Decimal(amount)),
        "currency": currency,
    }
    headers = {IDEMPOTENCY_HEADER: idempotency_key} if idempotency_key else {}
    return post("/v1/charges", payload, headers=headers)
""",
    # Written as joined lines rather than as a triple-quoted block on purpose:
    # this is the text of a pytest file, and a `def test_...` at the start of a
    # line inside a string literal is still counted as a test of THIS file by
    # scripts/lint_tasks.py's TEST_FUNC_RE, which then reports the vacuity floor
    # as stale for ever.
    TEST_FILE: "\n".join([
        "from api.charge import charge",
        "",
        "",
        "def test_charge_sends_the_idempotency_key(monkeypatch):",
        "    sent = {}",
        "",
        "    def fake_post(path, payload, headers=None):",
        '        sent["headers"] = headers or {}',
        '        return {"id": "ch_1"}',
        "",
        '    monkeypatch.setattr("api.charge.post", fake_post)',
        '    charge("acct_1", "10.00", idempotency_key="key-1")',
        '    assert sent["headers"]["Idempotency-Key"] == "key-1"',
        "",
    ]),
}

# Which paths each untouched commit is responsible for, so "nothing else moved"
# is checkable without reading any content.
OWN_PATHS = {
    MAIN_TIP: {"src/api/handlers.py"},
    WORKING_HEAD: {"src/client/limits.py"},
}

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


# jj change ids are 32 characters over the k-z alphabet. Used only to tell an
# anchored change id apart from the description-based fallback REVSET that
# change_id_or_fallback returns when there is no anchor.
CHANGE_ID_ALPHABET = set("klmnopqrstuvwxyz")


def graded(description):
    """A REVSET naming a bootstrap commit -- anchored where possible.

    change_id_or_fallback returns either an anchored change id or the fallback
    revset, and on this task the difference matters more than it does anywhere
    else in the suite: a BARE divergent change id is an ERROR on jj 0.44

        Error: Change ID `ppzvomws` is divergent

    rather than a two-element result. So an anchored id is always wrapped in
    `change_id(...)`, which resolves to every version and never errors, and the
    fallback revset is passed through untouched. Wrapping the fallback instead
    would be malformed, which is the mistake that broke a sibling task in cold
    CI the first time it ran.
    """
    value = change_id_or_fallback(
        description, 'description(substring:"%s")' % description,
        repo=PROJECT_DIR)
    if len(value) == 32 and not set(value) - CHANGE_ID_ALPHABET:
        return "change_id(%s)" % value
    return value


def change_ids(revset):
    out = jj_ok("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\\n"')
    return [line for line in out.splitlines() if line]


def commit_ids(revset):
    out = jj_ok("log", "-r", revset, "--no-graph", "-T", 'commit_id ++ "\\n"')
    return [line for line in out.splitlines() if line]


def visible_versions(description):
    """Every visible commit carrying the named change, as commit ids."""
    return commit_ids(graded(description))


def resolve_one(description):
    """The change id of the single visible commit the anchor (or fallback) names."""
    snapshot_working_copy()
    revset = graded(description)
    found = commit_ids(revset)
    assert len(found) == 1, (
        f"the bootstrap commit `{description}` resolves to {len(found)} "
        "visible commit(s), expected exactly one."
    )
    return change_ids(revset)[0]


def file_at(revset, path):
    """A file's content at a revision, or None when it is not there."""
    result = jj("file", "show", "-r", revset, path)
    return result.stdout if result.returncode == 0 else None


def local_bookmarks():
    """name -> whether the LOCAL bookmark of that name is conflicted.

    `jj bookmark list` prints one row per (name, remote) pair, and the local
    bookmark is the row whose `remote` is empty. Reading only the name would
    conflate the local bookmark with its `@git` remote-tracking twin, which is
    never conflicted even when the local one is -- git cannot represent a
    bookmark with two targets, which is why the export fails rather than the
    conflict propagating.
    """
    out = jj_ok("bookmark", "list", "--all-remotes", "-T",
                'name ++ "\\x1f" ++ remote ++ "\\x1f" '
                '++ if(conflict, "conflict", "clean") ++ "\\n"')
    found = {}
    for line in out.splitlines():
        if not line:
            continue
        parts = line.split("\x1f")
        if len(parts) != 3 or parts[1]:
            continue
        found[parts[0]] = parts[2] == "conflict"
    return found


def test_the_change_is_recorded_once_now():
    """One visible commit under the change id that had two.

    This is the half a `jj bookmark set` on its own does not reach: pointing the
    bookmark at one version leaves both versions visible and the change still
    divergent.
    """
    snapshot_working_copy()
    versions = visible_versions(DIVERGED)
    assert len(versions) == 1, (
        f"the change described `{DIVERGED}` still resolves to {len(versions)} "
        f"visible commits ({', '.join(v[:12] for v in versions)}). Two visible "
        "commits under one change id is what jj calls a divergent change, and "
        "the request was to end with one of them."
    )


def test_the_version_with_the_tests_is_the_one_that_survived():
    """The survivor is the version that carries tests/test_charge.py.

    Named for the wrong solve it catches. The two versions are
    indistinguishable structurally -- same change id, same description, same
    parent, same bookmark -- so an agent that picks by offset has a 50/50 shot,
    and the fixture is built so that the offset heuristic picks wrong: `/0` is
    the version built LAST, which is the one without the tests.

    Compared line by line, rstripped, so trailing whitespace is not the
    difference between 1.0 and 0.
    """
    snapshot_working_copy()
    cid = resolve_one(DIVERGED)
    revset = f"change_id({cid})"
    for path, expected_text in SURVIVING_CONTENT.items():
        content = file_at(revset, path)
        assert content is not None, (
            f"{path} is missing from the surviving version of `{DIVERGED}` "
            f"({cid[:12]}). The version that was asked for is the one carrying "
            f"{TEST_FILE}; this one does not have {path} at all."
        )
        found = [line.rstrip() for line in content.splitlines()]
        expected = [line.rstrip() for line in expected_text.splitlines()]
        assert found == expected, (
            f"{path} at the surviving version of `{DIVERGED}` ({cid[:12]}) is "
            "not what that version held.\n"
            + "\n".join(
                f"  line {n}: expected {want!r}, found {got!r}"
                for n, (want, got) in enumerate(
                    zip(expected, found + [None] * len(expected)), start=1)
                if want != got
            )[:1200]
            + f"\n  (expected {len(expected)} lines, found {len(found)})"
        )


def test_the_bookmark_names_one_commit_and_it_is_that_one():
    """`idempotency` is no longer conflicted, and marks the surviving version.

    Measured: resolving the divergence does NOT resolve the bookmark. After the
    abandon, `bookmarks(exact:"idempotency")` already resolves to exactly one
    visible commit while the bookmark itself still holds two targets, one of
    them the hidden common ancestor -- so the revset alone cannot tell a
    finished solve from a half-finished one, and the `conflict` keyword is read
    as well.
    """
    snapshot_working_copy()
    conflicted = local_bookmarks()
    assert BOOKMARK in conflicted, (
        f"there is no local `{BOOKMARK}` bookmark any more. The request was to "
        "repoint it, not to remove it."
    )
    assert not conflicted[BOOKMARK], (
        f"the `{BOOKMARK}` bookmark is still conflicted: it holds more than one "
        "target, so nothing can be pushed or checked out through it. Abandoning "
        "one version of the change does not resolve this on its own."
    )
    pointed = change_ids(f'bookmarks(exact:"{BOOKMARK}")')
    assert len(pointed) == 1, (
        f"`{BOOKMARK}` marks {len(pointed)} visible commit(s), expected one."
    )
    cid = resolve_one(DIVERGED)
    assert pointed[0] == cid, (
        f"`{BOOKMARK}` marks change {pointed[0][:12]}, which is not the "
        f"surviving version of `{DIVERGED}` ({cid[:12]})."
    )


def test_nothing_else_in_the_repository_moved():
    """No collateral damage: the two untouched commits still carry their diffs.

    Nobody asking for a duplicated commit to be tidied up is asking for the rest
    of the repository to be reorganised, so this is the no-collateral-damage
    default rather than a stated requirement.
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
    marks = {
        name: change_ids(f'bookmarks(exact:"{name}")')
        for name in ("main", "rate-limit")
    }
    assert marks["main"] == [resolve_one(MAIN_TIP)], (
        "the `main` bookmark no longer marks the commit it did."
    )
    assert marks["rate-limit"] == [resolve_one(WORKING_HEAD)], (
        "the `rate-limit` bookmark no longer marks the commit it did."
    )
