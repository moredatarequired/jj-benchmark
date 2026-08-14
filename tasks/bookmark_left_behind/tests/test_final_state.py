"""Verifier for the bookmark_left_behind task.

The request is one line: push everything I have done on rate-limit to origin.

WHAT MAKES THIS TASK DIFFERENT FROM THE SUITE'S OTHER WORK
==========================================================

A jj bookmark is not a git branch, and the difference that costs people work is
that it DOES NOT MOVE WHEN YOU COMMIT. In git the branch is wherever your last
commit landed; in jj the bookmark is wherever you last put it. This repository
has three commits of work above `rate-limit`, and `rate-limit` is exactly where
it was when the branch was one commit long.

So the obvious command succeeds and publishes nothing. Measured on jj 0.44.0:

    $ jj git push
    Warning: No bookmarks/tags found in the default push revset:
      remote_bookmarks(remote=origin)..@
    Nothing changed.                                            # exit 0

    $ jj git push -b rate-limit
    Bookmark rate-limit@origin already matches rate-limit
    Nothing changed.                                            # exit 0

Two spellings of "push my branch", both exit 0, neither publishes a line. There
is no error to read and no flag to remember -- `--allow-new` does not exist on
0.44, and would not help here in any case, because the bookmark is already
tracked. The only way through is to know that the bookmark has to be moved onto
the work first. That is the mental-model failure this task measures, and the
suite has had no bookmark coverage at all since the cut.

WHY THE REMOTE IS READ WITH GIT PLUMBING AND NOT THROUGH jj
===========================================================

The ground truth about what reached the remote is in the bare repository at
/home/user/checkout-api.git, and that is what is read. jj's `rate-limit@origin`
is jj's RECORD of the last push it knows about, which is a different claim; a
solve that pushed from the colocated git side would leave that record stale
while having genuinely published the work. Reading the bare repository is what
keeps the two REMOTE assertions method-neutral -- push it with jj, push it with
git, the same facts are read either way -- and keeps the verifier from grading
its own bookkeeping.

The local bookmark is a third, separate assertion rather than part of that, and
it is what separates a half-solve from a solve: moving `rate-limit` onto the
work and never pushing scores 0.333 here rather than 0, which is the right
description of that attempt. Measured, it does NOT punish the git-side route --
`git push origin <tip>:refs/heads/rate-limit` moves the remote-tracking ref, jj
imports it on the next command, and because the local bookmark is a tracked
ancestor of the new remote position it fast-forwards to follow. That route
scores 1.0, which is correct: the work is published and the repository is
consistent afterwards.

The commits are matched between the two repositories by COMMIT id, which is
sound in exactly this direction: a git commit id is a content hash over the
tree, the parents and the metadata, so the same id in the bare repository is the
same commit. The identity claim that matters -- that these are the BOOTSTRAP's
commits and not lookalikes -- is made on the jj side, through the anchor, before
their commit ids are looked up.

WRITTEN AGAINST AN OBSERVED END STATE (R7)
==========================================

The fixture was built from environment/Dockerfile and solved in a container of
that image, on the pinned jj 0.44.0, before any assertion below was written.
Three things those runs showed, each of which changed an assertion here:

  * jj PUSHES A BOOKMARK THAT POINTS AT `@`. There is no refusal and no warning,
    so a correct solve does not have to `jj new` first -- and a test that
    expected an extra commit on top would fail every direct route.

  * THE COMMITS ARE NOT REWRITTEN. `jj bookmark set` moves a label; it does not
    touch a commit. All four commit ids are unchanged from the bootstrap's, so
    the ids the bare repository ends up holding are the ones the jj repository
    already had. Nothing below asserts a commit id EQUALS a bootstrap value,
    though: they are read live on both sides and compared with each other.

  * `description(exact:"...")` DOES NOT MATCH. jj descriptions carry a trailing
    newline, so the exact: form silently matches nothing. Every fallback revset
    below uses substring:.
"""

import subprocess

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/checkout-api"
ORIGIN_DIR = "/home/user/checkout-api.git"
BOOKMARK = "rate-limit"

# Where the bookmark was left, and the three commits of work above it, oldest
# first. These are descriptions used to look up ANCHORED change ids; the anchor
# is what makes them identities rather than labels.
BOOKMARK_WAS_ON = "add a token bucket to the client"
WORK = (
    "read the rate limit from config",
    "refill the bucket between attempts",
    "add tests for the token bucket",
)
TIP = WORK[-1]
MAIN_TIP = "route charges through handlers"

# Which paths each commit of the work is responsible for. Disjoint by
# construction, so folding the three into one before pushing is visible.
OWN_PATHS = {
    BOOKMARK_WAS_ON: {"src/client/limits.py"},
    WORK[0]: {"config.toml"},
    WORK[1]: {"src/client/limits.py"},
    WORK[2]: {"tests/test_limits.py"},
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


def git_origin(*args):
    return subprocess.run(
        ["git", "--git-dir", ORIGIN_DIR, *args],
        capture_output=True, text=True,
    )


def graded(description):
    """The revset naming a bootstrap commit: its anchored change id if there is
    an anchor, and `description(substring:...)` if there is not.

    change_id_or_fallback returns a REVSET, not always a change id -- so it is
    evaluated to get a concrete id rather than being interpolated into
    `change_id(...)`, which would be malformed on the fallback path.
    """
    return change_id_or_fallback(
        description, 'description(substring:"%s")' % description,
        repo=PROJECT_DIR)


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


def commit_id_of(description):
    """The commit id the named bootstrap change carries RIGHT NOW.

    Read live rather than taken from the anchor: a solve is free to rewrite
    these commits on the way (nothing asks it to, but nothing forbids it
    either), and what has to be true at the end is that what reached the remote
    is what the repository holds.
    """
    cid = resolve_one(description)
    found = field(f"change_id({cid})", "commit_id")
    assert len(found) == 1
    return found[0]


def origin_ref(name):
    """The commit id origin's `name` branch points at, or None."""
    result = git_origin("rev-parse", "--verify", f"refs/heads/{name}")
    return result.stdout.strip() if result.returncode == 0 else None


def origin_history(name):
    """Every commit id reachable from origin's `name` branch."""
    result = git_origin("rev-list", f"refs/heads/{name}")
    assert result.returncode == 0, (
        f"origin has no `{name}` branch to read: {result.stderr.strip()}"
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def local_bookmark_target(name):
    """(change id, is-conflicted) for the LOCAL bookmark of that name.

    The local bookmark is the `jj bookmark list` row whose `remote` is empty;
    reading only the name would conflate it with its `@git` / `@origin`
    remote-tracking twins.
    """
    out = jj_ok("bookmark", "list", "--all-remotes", "-T",
                'name ++ "\\x1f" ++ remote ++ "\\x1f" '
                '++ if(conflict, "conflict", "clean") ++ "\\n"')
    conflicted = None
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 3 and parts[0] == name and not parts[1]:
            conflicted = parts[2] == "conflict"
    if conflicted is None:
        return None, None
    return change_ids(f'bookmarks(exact:"{name}")'), conflicted


def test_the_work_reached_the_origin():
    """All three commits are in origin's rate-limit history.

    This is the test both silent no-ops fail. `jj git push` and
    `jj git push -b rate-limit` each exit 0 on the untouched repository and
    leave origin exactly as it was, because the bookmark they are asked to push
    is already where the remote has it -- the three commits above it are not
    part of the branch as far as the bookmark is concerned.
    """
    snapshot_working_copy()
    history = origin_history(BOOKMARK)
    missing = [
        description for description in WORK
        if commit_id_of(description) not in history
    ]
    assert not missing, (
        "origin's `%s` branch does not contain %d of the three commits: %s.\n"
        "A jj bookmark does not move when you commit, so the three commits "
        "above `%s` are not part of what `jj git push` considers the branch "
        "until the bookmark is moved onto them -- and the push exits 0 and "
        "says `Nothing changed.` rather than complaining."
        % (BOOKMARK, len(missing), ", ".join(f"`{d}`" for d in missing),
           BOOKMARK_WAS_ON)
    )


def test_the_origin_branch_ends_on_the_tip_of_the_work():
    """origin's rate-limit points at the newest commit, not merely contains it.

    Named for the wrong solve it catches: publishing PART of the work. Measured
    -- and this is the one that would have slipped past a reachability check
    alone -- `git push origin HEAD:refs/heads/rate-limit` from the colocated
    repository publishes two of the three commits, because in a colocated repo
    git's HEAD is `@-`: jj does not export the working-copy commit to HEAD. The
    branch moves, the push exits 0, and the newest commit is still unpublished.
    """
    snapshot_working_copy()
    tip = commit_id_of(TIP)
    ref = origin_ref(BOOKMARK)
    assert ref is not None, (
        f"origin has no `{BOOKMARK}` branch at all any more."
    )
    assert ref == tip, (
        f"origin's `{BOOKMARK}` points at {ref[:12]}, but the newest commit of "
        f"the work, `{TIP}`, is {tip[:12]}. Whatever else is in the remote's "
        "object store, the branch itself has not been moved onto the work."
    )


def test_the_local_bookmark_marks_the_work():
    """`rate-limit` locally marks the tip of the work, and is not conflicted.

    Separate from the two remote tests because it is a separate failure: a
    `git push` run straight from the colocated repository moves the remote ref
    and leaves the jj bookmark three commits back, which is the same latent
    problem the agent was handed, still there.
    """
    snapshot_working_copy()
    marks, conflicted = local_bookmark_target(BOOKMARK)
    assert marks is not None, (
        f"there is no local `{BOOKMARK}` bookmark any more."
    )
    assert not conflicted, (
        f"the local `{BOOKMARK}` bookmark is conflicted: it holds more than one "
        "target."
    )
    assert marks == [resolve_one(TIP)], (
        f"`{BOOKMARK}` marks {marks}, not the tip of the work, `{TIP}`."
    )


def test_nothing_else_was_published_or_rewritten():
    """No collateral damage: main is where it was, and the work is intact.

    Publishing a branch is not a licence to move main or to reorganise the
    commits on the way. The four commits are checked by their own diffs, so a
    solve that folds the three into one before pushing is visible here even
    though the resulting tree is identical.
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
    assert origin_ref("main") == commit_id_of(MAIN_TIP), (
        "origin's `main` branch has moved; only the rate-limit work was to be "
        "published."
    )
    marks = change_ids('bookmarks(exact:"main")')
    assert marks == [resolve_one(MAIN_TIP)], (
        f"the local `main` bookmark no longer marks `{MAIN_TIP}`."
    )
