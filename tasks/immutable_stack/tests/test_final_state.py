"""Verifier for the immutable_stack task.

The request is one line: unblock my stack so I can reword 'fix nonce handling'
to 'handle nonces on retried charges', but keep main protected.

WHAT MAKES THIS TASK DIFFERENT FROM THE SUITE'S OTHER WORK
==========================================================

Nothing else in the suite makes jj REFUSE. The repository ships with a
repo-scoped `immutable_heads()` alias -- `bookmarks()` -- which reads as
"protect the branches" and evaluates to "protect main, and also the author's own
in-progress stack, because that has a bookmark on it too". The first rewrite the
agent tries is rejected:

    Error: Commit 5a79110ab0dc is immutable
    Hint: Could not modify commit: qnsutptm 5a79110a fix nonce handling

There is a one-keystroke way past that (`--ignore-immutable`) which does the
reword and leaves the repository exactly as blocked as it was, and a one-line
way to "fix the config" (delete the alias) which unblocks everything and
silently unprotects main, because there is no git remote here and jj's default
`trunk()` falls back to `root()`. Both are graded against, and neither is
graded by looking at what the config file SAYS: the alias is evaluated in the
repository, through jj's own `immutable()` / `mutable()` revsets, so any way of
narrowing it counts and any way of appearing to narrow it without narrowing it
does not.

That last point is not decoration. jj 0.44 accepts five configuration keys it
has removed without printing anything at all, so a config edit that changes
nothing exits 0 and looks like success. A verifier that string-matched the
setting would agree with it.

WRITTEN AGAINST AN OBSERVED END STATE (R7)
==========================================

The fixture was built from environment/Dockerfile and solved in a container of
that image, on the pinned jj 0.44.0, before any assertion below was written.
Three things those runs showed, each of which changed an assertion here:

  * THE TWO COMMITS ABOVE THE TARGET GET NEW COMMIT IDS. The reword rewrites the
    second of four, so jj rebases the two above it: same change ids, different
    commit ids, and `Rebased 2 descendant commits.` on stderr. An assertion that
    those commits keep their commit ids would fail every correct solve. Only the
    three commits at or below `main` -- which nothing legitimately rewrites --
    are checked that way, and they are checked only through the anchor.

  * `mutable()` AND `immutable()` ARE BUILT-IN REVSET ALIASES, defined in terms
    of whatever `immutable_heads()` currently expands to. That is what lets this
    file evaluate the protection instead of reading it.

  * `description(exact:"...")` DOES NOT MATCH. jj descriptions carry a trailing
    newline, so the exact: form silently matches nothing. The description
    assertion below compares `description.first_line()` instead.

WHY THE FALLBACK FOR THE REWORD TARGET IS A PATH AND NOT A DESCRIPTION
=====================================================================

change_id_or_fallback falls back to a revset when there is no anchor file, which
is the normal condition in CI. The usual fallback -- `description(substring:)`
-- cannot be used for a commit whose description the task CHANGES: it matches on
the untouched image and matches nothing once the task is done, so the verifier
would fail exactly the solves it is meant to pass. The fixture therefore gives
that commit a path nothing else in the repository touches,
`src/api/nonce_store.py`, and the fallback is `files(...)` on it. This is the
same shape edit_commit_message uses (`files("b.txt")`).
"""

import subprocess

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/checkout-api"

# The reword, both ends of it.
OLD_DESCRIPTION = "fix nonce handling"
NEW_DESCRIPTION = "handle nonces on retried charges"
TARGET_PATH = "src/api/nonce_store.py"

# The four commits of the stack, oldest first, keyed by the description the
# BOOTSTRAP gave them -- which for the second of them is the description the
# task replaces, hence the path-based fallback above.
STACK = (
    "record retry attempts in the charge metrics",
    OLD_DESCRIPTION,
    "reuse the nonce on retried charges",
    "note the nonce work in the changelog",
)

# main and the two commits below it. Everything here must stay protected.
PROTECTED = (
    "add the charge endpoint",
    "route charges through handlers",
    "issue a nonce with every charge",
)
MAIN_TIP = PROTECTED[-1]

# Which paths each stack commit is responsible for. Disjoint by construction, so
# "the stack is still the stack" is checkable without reading any content.
OWN_PATHS = {
    STACK[0]: {"src/api/metrics.py"},
    STACK[1]: {"src/api/nonce.py", TARGET_PATH},
    STACK[2]: {"config.toml", "src/client/retry.py"},
    STACK[3]: {"CHANGELOG.md"},
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


def graded(description):
    """The revset naming a bootstrap commit: its anchored change id if there is
    an anchor, and a fallback revset if there is not.

    change_id_or_fallback returns a REVSET, not always a change id -- so it is
    evaluated to get a concrete id rather than being interpolated into
    `change_id(...)`, which would be malformed on the fallback path.
    """
    if description == OLD_DESCRIPTION:
        fallback = 'files("%s")' % TARGET_PATH
    else:
        fallback = 'description(substring:"%s")' % description
    return change_id_or_fallback(description, fallback, repo=PROJECT_DIR)


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


def first_lines(revset):
    out = jj_ok("log", "-r", revset, "--no-graph", "-T",
                'description.first_line() ++ "\\n"')
    return [line for line in out.splitlines()]


def describe(cids):
    if not cids:
        return "(none)"
    revset = " | ".join(f"change_id({c})" for c in sorted(cids))
    out = jj_ok("log", "-r", revset, "--no-graph",
                "-T", 'change_id.short(8) ++ " " ++ description.first_line() ++ "\\n"')
    return "; ".join(line for line in out.splitlines() if line)


def test_the_commit_carries_the_new_description():
    """The bootstrap's own `fix nonce handling` commit now says the new thing.

    Resolved through the anchor, so this is the commit the bootstrap created and
    not merely something that looks like it. `--ignore-immutable` reaches this
    assertion; it does not reach test_the_stack_can_be_rewritten_again.
    """
    snapshot_working_copy()
    cid = resolve_one(OLD_DESCRIPTION)
    found = first_lines(f"change_id({cid})")
    assert found == [NEW_DESCRIPTION], (
        f"the commit the bootstrap described `{OLD_DESCRIPTION}` ({cid[:12]}) "
        f"is described {found!r}; the request was for it to say "
        f"{NEW_DESCRIPTION!r}."
    )


def test_no_commit_is_still_described_the_old_way():
    """Nothing anywhere still says `fix nonce handling`.

    Named for the wrong solve it catches: rewording by making a NEW commit that
    says the right thing, or by duplicating the old one, leaves the original
    text visible somewhere in the repository. A reword replaces text; it does
    not add a second copy of it.
    """
    snapshot_working_copy()
    still = change_ids(f'description(substring:"{OLD_DESCRIPTION}")')
    assert not still, (
        f"{len(still)} commit(s) are still described `{OLD_DESCRIPTION}`: "
        f"{describe(still)}. The reword was asked for, not a second commit "
        "beside the first."
    )


def test_the_stack_can_be_rewritten_again():
    """All four stack commits are in `mutable()`.

    This is the half that `jj describe --ignore-immutable` does not reach: that
    flag "only affects the check", in jj's own words, and leaves
    `immutable_heads()` exactly as wide as it was, so the next rewrite is
    refused all over again. The protection is EVALUATED here, through jj's
    builtin `mutable()` alias, rather than read out of a config file -- any way
    of narrowing the alias counts, and jj 0.44 accepts several removed config
    keys in silence, so a setting that changes nothing must not be able to pass.
    """
    snapshot_working_copy()
    anchored = {description: resolve_one(description) for description in STACK}
    mutable = set(change_ids("mutable()"))
    blocked = [
        description for description, cid in anchored.items()
        if cid not in mutable
    ]
    assert not blocked, (
        "the stack is still protected from rewrites: "
        + describe([anchored[d] for d in blocked])
        + ".\nThe request was to unblock the stack, so `immutable_heads()` has "
        "to stop covering these -- an override on one command leaves the next "
        "rewrite refused."
    )


def test_main_and_everything_below_it_is_still_protected():
    """main and its two ancestors are still in `immutable()`.

    Named for the wrong solve it catches: deleting the alias. That unblocks the
    stack in one line and passes every other test here -- and because this
    repository has no git remote, jj's default `immutable_heads()` expands to
    `trunk() | tags() | untracked_remote_bookmarks()` with `trunk()` falling
    back to `root()`, so main ends up protected by nothing at all. Measured on
    jj 0.44.0.
    """
    snapshot_working_copy()
    anchored = {description: resolve_one(description) for description in PROTECTED}
    immutable = set(change_ids("immutable()"))
    exposed = [
        description for description, cid in anchored.items()
        if cid not in immutable
    ]
    assert not exposed, (
        "main is no longer protected from rewrites: "
        + describe([anchored[d] for d in exposed])
        + f".\n`{MAIN_TIP}` is main, and the request was to keep it protected "
        "while unblocking the stack -- not to turn the protection off."
    )
    marks = change_ids('bookmarks(exact:"main")')
    assert marks == [anchored[MAIN_TIP]], (
        f"the `main` bookmark no longer marks `{MAIN_TIP}`; it marks "
        f"{describe(marks)}."
    )


def test_the_stack_is_still_the_same_four_commits():
    """Four anchored commits between the anchored ends, each with its own diff.

    No collateral damage: unblocking a stack is not a licence to rebuild it, and
    the anchored change ids catch a rebuild because a fresh commit gets a fresh
    random change id. `retry-backoff` is checked too -- deleting it would shrink
    `bookmarks()` and so "unblock the stack" by throwing away the label the
    author was working under.
    """
    snapshot_working_copy()
    anchored = [resolve_one(description) for description in STACK]
    span = change_ids(f"change_id({anchored[0]})::change_id({anchored[-1]})")
    assert set(span) == set(anchored), (
        "the stack is no longer the four commits it was.\n"
        "  missing: %s\n  extra:   %s"
        % (describe(set(anchored) - set(span)), describe(set(span) - set(anchored)))
    )
    for description, expected in OWN_PATHS.items():
        cid = resolve_one(description)
        out = jj_ok("diff", "-r", f"change_id({cid})", "--name-only")
        changed = {line for line in out.splitlines() if line}
        assert changed == expected, (
            f"`{description}` ({cid[:12]}) should change exactly "
            f"{sorted(expected)}; it changes {sorted(changed)}."
        )
    pointed = change_ids('bookmarks(exact:"retry-backoff")')
    assert pointed and set(pointed) <= set(anchored), (
        "the `retry-backoff` bookmark no longer marks one of the four stack "
        f"commits; it points at {describe(pointed)}."
    )
