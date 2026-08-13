"""Verifier for the merge_bookmarks task.

The task asks for one commit sitting on top of both `rate-limit` and
`oauth-refresh`, whose `config.toml` carries the block each bookmark's tip
contributed. On jj 0.44 the only spelling for that is `jj new <r1> <r2>` --
`jj merge` was removed -- and the merge lands 2-sided-conflicted in
`config.toml`, so "keeping both bookmarks' blocks" is work the agent does rather
than something the merge does for it.

WRITTEN AGAINST AN OBSERVED END STATE (R7)
==========================================

The fixture was built from environment/Dockerfile, `jj new rate-limit
oauth-refresh` was run in a container of that image, the conflict was resolved,
and the assertions below were written from what the repository then looked like.
Two of them exist only because of what that run showed:

  * the merge commit's diff against its parents is exactly `config.toml` -- the
    merge is otherwise empty -- so nothing here may require the merge to carry a
    diff to anything else;
  * the bootstrap's empty, undescribed `@` is auto-abandoned by `jj new <r1>
    <r2>` and prints nothing while doing it (D11 in the measured 0.44
    change-id table). That is why tests/anchor_exemptions.json exists for this
    task; without it every correct solve would error out in the anchor fixture.

HOW THE GRADED COMMIT IS FOUND
==============================

Structurally, never positionally: the merge is the commit in `all()` whose
parent change ids are exactly the two anchored bookmark tips. `@` is not
consulted, so an agent that carries on working after making the merge -- or that
makes the merge somewhere other than under its own working copy -- is graded the
same. Requiring `parents.len() == 2` AND the parent identities is what fails the
plausible wrong answer: a single-parent commit on one bookmark into which the
other side's block was pasted by hand.
"""

import subprocess

import anchor
from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/checkout-api"

RATE_TIP = "reject charges over the per-account rate limit"
OAUTH_TIP = "refresh oauth tokens before they expire"
RATE_BASE = "count charges per account in redis"
OAUTH_BASE = "read the oauth client credentials from config"
MAIN = "extract the http client"
ROOT_COMMIT = "add the charge endpoint"

# Used ONLY when there is no anchor file (cold CI). Reproduces the strength the
# tests would have had without one: never weaker, never an error.
FALLBACK = {
    desc: 'description(substring:"%s")' % desc
    for desc in (RATE_TIP, OAUTH_TIP, RATE_BASE, OAUTH_BASE, MAIN, ROOT_COMMIT)
}

# config.toml as each side has it, parsed into {section: (line, line, ...)}.
# Compared section-wise rather than byte-wise because the request does not say
# which order the two blocks go in, and neither order is more correct.
BASE_SECTIONS = {
    "server": ('host = "0.0.0.0"', "port = 8080"),
    "database": ('url = "postgres://localhost/checkout"', "pool_size = 10"),
}
RATELIMIT_SECTION = ("per_account_per_minute = 60", "burst = 10")
OAUTH_SECTION = (
    'token_url = "https://auth.example.com/oauth/token"',
    "refresh_margin_seconds = 120",
)

LIMITS_PY = (
    "import time\n"
    "\n"
    "WINDOW_SECONDS = 60\n"
    "\n"
    "\n"
    "def bucket_for(account_id, now=None):\n"
    "    now = time.time() if now is None else now\n"
    '    return "%s:%d" % (account_id, int(now // WINDOW_SECONDS))\n'
    "\n"
    "\n"
    "def over_limit(account_id, seen, limit):\n"
    "    return seen.get(bucket_for(account_id), 0) >= limit\n"
)

OAUTH_PY = (
    "import time\n"
    "\n"
    "\n"
    "class Token:\n"
    "    def __init__(self, value, expires_at):\n"
    "        self.value = value\n"
    "        self.expires_at = expires_at\n"
    "\n"
    "    def expired(self, now=None):\n"
    "        return (time.time() if now is None else now) >= self.expires_at\n"
    "\n"
    "\n"
    "def refresh_if_needed(token, margin, fetch):\n"
    "    if token.expires_at - time.time() <= margin:\n"
    "        return fetch()\n"
    "    return token\n"
)

# Anything jj writes into a materialised conflict. Their presence in a graded
# file means the merge was never resolved, whatever the section parse makes of
# the rest of it.
CONFLICT_MARKERS = ("<<<<<<<", ">>>>>>>", "%%%%%%%", "+++++++", "\\\\\\\\\\\\\\")

_snapshotted = False


def snapshot_working_copy():
    """Take the ONE working-copy snapshot this verifier is allowed, explicitly.

    Every other jj call passes --ignore-working-copy, so that the verifier does
    not mutate the repository it is grading. A solve may leave the resolved
    `config.toml` written but unsnapshotted, so the snapshot has to happen once,
    deliberately. It preserves change ids and so cannot disturb the anchor.
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
    """The bootstrap's change id for `description`, or a description revset."""
    return change_id_or_fallback(description, FALLBACK[description],
                                 repo=PROJECT_DIR)


def anchored_commit_id(description):
    """The bootstrap's COMMIT id for `description`, or None with no anchor.

    Commit ids are not what the integrity anchor rests on -- they are
    content-derived and therefore forgeable in principle -- but for "this
    bookmark tip was not rewritten" they are exactly the right instrument, and
    forging one is not a route to passing this task. Returns None when there is
    no anchor file so that the caller can fall back to comparing content, which
    is what the test asserted before the anchor existed.
    """
    try:
        record = anchor.load()
    except anchor.AnchorUnavailable as exc:
        print("%s: not checking commit ids (%s)"
              % (anchor.IDENTITY_NOT_CLAIMED, exc))
        return None
    for repo in record["repos"]:
        for commit in repo["commits"]:
            if commit["description"] == description:
                return commit["commit_id"]
    return None


def change_ids(revset):
    out = jj_ok("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\\n"')
    return [line for line in out.splitlines() if line]


def resolve_one(revset, what):
    found = change_ids(revset)
    assert len(found) == 1, (
        f"expected `{revset}` to name exactly one commit ({what}), it names "
        f"{len(found)}: {found}"
    )
    return found[0]


def rows(revset, template):
    out = jj_ok("log", "-r", revset, "--no-graph", "-T", template)
    return [line for line in out.splitlines() if line]


def changed_paths(rev):
    out = jj_ok("diff", "-r", rev, "--name-only")
    return {line for line in out.splitlines() if line}


def tree_paths(rev):
    out = jj_ok("file", "list", "-r", rev)
    return {line for line in out.splitlines() if line}


def file_at(rev, path):
    result = jj("file", "show", "-r", rev, path)
    assert result.returncode == 0, (
        f"`{path}` is not present in revision `{rev}`: {result.stderr.strip()}"
    )
    return result.stdout


def sections(text):
    """config.toml as {section name: tuple of its non-blank lines}.

    A deliberately small parser rather than tomllib: it has to survive being
    handed a file with conflict markers still in it and report that as a section
    layout that does not match, instead of raising a parse error the test would
    have to translate.
    """
    found = {}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1]
            found.setdefault(current, [])
            continue
        if current is None:
            found.setdefault("", []).append(line)
        else:
            found[current].append(line)
    return {name: tuple(lines) for name, lines in found.items()}


def find_merge():
    """The commit whose parents are exactly the two anchored bookmark tips.

    Resolved out of `all()`, so where the agent left `@` is not graded and a
    merge made under a different working copy counts the same.
    """
    rate, oauth = graded(RATE_TIP), graded(OAUTH_TIP)
    rate_id = resolve_one(rate, "the rate-limit tip")
    oauth_id = resolve_one(oauth, "the oauth-refresh tip")
    wanted = {rate_id, oauth_id}

    template = (
        'change_id ++ "\\t" ++ parents.map(|p| p.change_id()).join(",") ++ "\\n"'
    )
    merges = []
    for row in rows("all() ~ root()", template):
        cid, _, parent_field = row.partition("\t")
        parents = [p for p in parent_field.split(",") if p]
        if set(parents) == wanted and len(parents) == 2:
            merges.append(cid)
    return merges, rate_id, oauth_id


def merge_or_fail():
    merges, rate_id, oauth_id = find_merge()
    assert len(merges) == 1, (
        "Expected exactly one commit whose parents are the two bookmark tips "
        f"{rate_id[:12]} (rate-limit) and {oauth_id[:12]} (oauth-refresh); "
        f"found {len(merges)}: {[m[:12] for m in merges]}. A commit with one "
        "parent that merely contains both sides' text is not a commit on top "
        "of both bookmarks."
    )
    return merges[0]


def test_a_commit_sits_on_top_of_both_bookmarks():
    """One commit, two parents, and the parents are the two anchored tips.

    This is the assertion the task exists for. It fails the two wrong answers a
    git-shaped instinct produces: a single-parent commit on one bookmark with
    the other side's block pasted in, and a rebase of one bookmark onto the
    other (which produces no two-parent commit at all and rewrites a tip
    besides).
    """
    snapshot_working_copy()
    merge = merge_or_fail()
    parents = rows(
        f"change_id({merge})", 'parents.len() ++ "\\n"'
    )
    assert parents == ["2"], (
        f"the merge {merge[:12]} reports {parents} parents, expected exactly 2"
    )


def test_the_merge_is_not_conflicted():
    """`config.toml` merges 2-sided-conflicted, so this is not automatic."""
    snapshot_working_copy()
    merge = merge_or_fail()
    flags = rows(f"change_id({merge})", 'conflict ++ "\\n"')
    assert flags == ["false"], (
        f"the merge {merge[:12]} is still conflicted ({flags}). Creating the "
        "merge is only half of it -- `config.toml` conflicts, and a conflicted "
        "commit does not contain both bookmarks' blocks, it contains markers."
    )


def test_config_toml_keeps_both_bookmarks_blocks():
    """The merged config.toml carries the base plus one block from each side."""
    snapshot_working_copy()
    merge = merge_or_fail()
    text = file_at(merge, "config.toml")
    for marker in CONFLICT_MARKERS:
        assert marker not in text, (
            f"`config.toml` in the merge {merge[:12]} still contains the "
            f"conflict marker {marker!r}."
        )
    found = sections(text)
    expected = dict(BASE_SECTIONS)
    expected["ratelimit"] = RATELIMIT_SECTION
    expected["oauth"] = OAUTH_SECTION
    assert found == expected, (
        f"`config.toml` in the merge {merge[:12]} does not carry exactly the "
        "base configuration plus rate-limit's [ratelimit] block and "
        f"oauth-refresh's [oauth] block.\n  expected: {expected}\n  found:    "
        f"{found}\n(Section order is not graded; contents are.)"
    )


def test_the_merge_carries_the_code_from_both_sides():
    """A merge of the two bookmarks has both bookmarks' files in its tree.

    Cheap to satisfy honestly and impossible to satisfy by editing config.toml
    alone, which is what makes it worth asserting separately: it fails a
    "merge" assembled by hand on one side.
    """
    snapshot_working_copy()
    merge = merge_or_fail()
    assert file_at(merge, "src/api/limits.py") == LIMITS_PY, (
        f"`src/api/limits.py` in the merge {merge[:12]} is not the file the "
        "rate-limit tip has."
    )
    assert file_at(merge, "src/client/oauth.py") == OAUTH_PY, (
        f"`src/client/oauth.py` in the merge {merge[:12]} is not the file the "
        "oauth-refresh tip has."
    )
    assert {"src/api/limits.py", "src/client/oauth.py"} <= tree_paths(merge), (
        f"the merge {merge[:12]} is missing one of the two sides' files."
    )


def test_neither_bookmark_was_rewritten():
    """Both tips are the bootstrap's own commits, unchanged, still bookmarked.

    Bringing two lines of work together does not license rewriting either of
    them, and the wrong answer this catches by name is `jj rebase -b
    oauth-refresh -d rate-limit`: it produces a linear history with the right
    file contents and no merge commit, and it rewrites every commit it moves.
    """
    snapshot_working_copy()
    rate = resolve_one(graded(RATE_TIP), "the rate-limit tip")
    oauth = resolve_one(graded(OAUTH_TIP), "the oauth-refresh tip")

    for name, cid in (("rate-limit", rate), ("oauth-refresh", oauth)):
        pointed = change_ids(f'bookmarks(exact:"{name}")')
        assert pointed == [cid], (
            f"the `{name}` bookmark must still point at the bootstrap's tip "
            f"{cid[:12]}; it points at {[p[:12] for p in pointed]}"
        )

    for description, cid in ((RATE_TIP, rate), (OAUTH_TIP, oauth)):
        recorded = anchored_commit_id(description)
        if recorded is not None:
            current = rows(f"change_id({cid})", 'commit_id ++ "\\n"')
            assert current == [recorded], (
                f"the commit `{description}` was rewritten: its commit id is "
                f"{current} where the bootstrap handed over {recorded[:12]}."
            )

    assert changed_paths(rate) == {"config.toml", "src/api/limits.py"}, (
        "the rate-limit tip must still change exactly config.toml and "
        f"src/api/limits.py; it changes {sorted(changed_paths(rate))}"
    )
    assert changed_paths(oauth) == {"config.toml", "src/client/oauth.py"}, (
        "the oauth-refresh tip must still change exactly config.toml and "
        f"src/client/oauth.py; it changes {sorted(changed_paths(oauth))}"
    )
    assert sections(file_at(rate, "config.toml")) == dict(
        BASE_SECTIONS, ratelimit=RATELIMIT_SECTION
    ), "the rate-limit tip's own config.toml was modified."
    assert sections(file_at(oauth, "config.toml")) == dict(
        BASE_SECTIONS, oauth=OAUTH_SECTION
    ), "the oauth-refresh tip's own config.toml was modified."


def test_the_history_below_the_two_bookmarks_is_intact():
    """The six bootstrap commits still exist, in the shape they were handed over.

    An anti-fabrication check rather than a method check: it cannot fail an
    honest solve of any shape, and it does fail the route that rebuilds a
    plausible-looking graph beside the original one.
    """
    snapshot_working_copy()
    main = resolve_one(graded(MAIN), "main")
    for description, parent in (
        (RATE_BASE, main),
        (OAUTH_BASE, main),
        (RATE_TIP, resolve_one(graded(RATE_BASE), RATE_BASE)),
        (OAUTH_TIP, resolve_one(graded(OAUTH_BASE), OAUTH_BASE)),
    ):
        cid = resolve_one(graded(description), description)
        actual = rows(
            f"change_id({cid})",
            'parents.map(|p| p.change_id()).join(",") ++ "\\n"',
        )
        assert actual == [parent], (
            f"`{description}` no longer sits on {parent[:12]}; its parents are "
            f"{actual}"
        )
    pointed = change_ids('bookmarks(exact:"main")')
    assert pointed == [main], (
        f"the `main` bookmark must still point at {main[:12]}; it points at "
        f"{[p[:12] for p in pointed]}"
    )
