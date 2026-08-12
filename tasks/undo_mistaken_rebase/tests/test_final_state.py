"""Replay the operation log structurally; never match jj's English.

The two scored tests in this file used to substring-match jj's human-readable
operation descriptions: one required some description to contain "rebase", the
other required a description containing "undo" or "revert" to be newer than it.
Nothing checked WHICH commit had been rebased, or which operation the revert had
reverted. Measured on jj 0.38.0 against this task's own bootstrap, that was
wrong in three separate directions at once:

  * TOO LOOSE. `jj new -m throwaway; jj rebase -r @ -d root(); jj undo`, which
    never touches commit `B` at all and leaves the bootstrap state exactly as it
    found it, scored **6 of 6, reward 1.0**.
  * TOO LOOSE AGAIN, and worse. Mistaken rebase, a dirty working copy, a plain
    `jj log` (which appends `snapshot working copy`), then a bare `jj undo`
    reverts THE SNAPSHOT rather than the rebase. `B` is left sitting on `base`
    -- the task simply not done -- and yet both scored tests passed: the two
    tests that failed were `test_topology_restored` and
    `test_file_contents_restored`, which are in the vacuity floor and so are
    excluded from the score. **Reward 0.5 for a repository that was never
    fixed.**
  * TOO TIGHT. `jj op restore <pre-rebase-op>` -- which `jj undo`'s own help
    recommends -- records `restore to operation <hex>`, matching neither "undo"
    nor "revert", so a verifiably correct repository scored **5 of 6, reward
    0.5**.

All three are the same root cause: the grade rested on which of several
equivalent commands the agent happened to pick, and on jj's wording for it.

WHAT REPLACES IT

`jj --at-op=<id>` re-opens the repository as it stood after a given operation,
so the operation log can be interrogated structurally instead of textually. This
file enumerates the operations and, at each one, asks where the commit described
`B` was sitting -- as change ids, with no English anywhere:

    for op in jj op log --no-graph -T 'id ++ "\\n"':
        jj --at-op=$op log -r 'description(substring:"B")' \\
           -T 'parents.map(|p| p.change_id().short(12)).join(",")'

Change ids, not commit ids, because a change id survives a rebase: it is what
lets "the same commit, on a different parent" be stated at all. (`p.change_id`
is a method in 0.38 -- `p.change_id()` -- not a property.) Two scored tests come
out of that:

  * `test_mistaken_rebase_actually_happened` -- at some operation, `B` sat on
    `base`. That is requirement 1 of the task, checked against the commit the
    task names, so an unrelated rebase no longer counts.
  * `test_mistaken_rebase_was_reverted` -- the above, AND at the current
    operation `B` is back on `A` and is not conflicted. Deliberately a
    conjunction: this task's correct end state IS its bootstrap state, so every
    pure end-state assertion here is in the vacuity floor and cannot carry
    score. Requiring both halves in one test is what makes "the rebase happened
    and was then reverted" a scored claim.

Measured outcomes over the whole scored fraction (2 scored tests, 4 floored):
untouched bootstrap 0/2; `jj rebase` + `jj undo`, + `jj op undo`, + `jj op
revert`, + `jj op restore` all 2/2; the unrelated-rebase cheat 0/2; rebase
without an undo, and the snapshot-undo above, 1/2.

TWO THINGS THIS FILE DOES NOT CLAIM

  * **This is a consistency check, not an integrity check.** Replay
    authenticates a history against itself. A repository wiped and rebuilt by
    hand -- including one where the mistaken rebase was staged deliberately --
    agrees with itself and would pass. Anchoring that requires a value captured
    before the agent ran, which this benchmark does not yet carry.
  * **Operation counts are not asserted.** They are not a fair signal: the
    agent's first jj command can append a `snapshot working copy` operation on
    its own, so totals differ between equally correct solves. Every assertion
    below is about a transition or a state, never a total. For the same reason
    there is no assertion on how many commits are visible: a solve that creates
    a scratch commit on the way is not wrong, and the cheats above are already
    scored 0 and 0.5 without it.

The four end-state tests that follow are unchanged in substance. They pass on
the untouched bootstrap by design and are floored, so they earn nothing; they
exist to fail loudly if a solve destroys something on its way.
"""

import subprocess

REPO = "/home/user/repo"

# Bootstrap history: root() <- base <- A (main) <- B. These are the bootstrap's
# own commit messages, from environment/Dockerfile, not jj output.
COMMITS = ["base", "A", "B"]
PARENT_OF = {"base": "", "A": "base", "B": "A"}

# The commit the task rebases, and the destination it is rebased onto.
REBASED = "B"
WRONG_PARENT = "base"
RIGHT_PARENT = "A"


def jj(*args):
    """A read-only jj call.

    `--ignore-working-copy` on every call, always. Without it each read
    snapshots the working copy and, in a colocated repo, imports the underlying
    git repo -- appending operations to the log this verifier is reading, so the
    first run would change what the second run measures.
    """
    result = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"`jj {' '.join(args)}` failed: {result.stderr}"
    )
    return result.stdout


def at_op(op, *args):
    """The same read, against the repository as it stood after operation `op`."""
    return jj(f"--at-op={op}", *args)


def revset(description):
    # A bare string pattern is a glob in jj 0.38 and descriptions end in a
    # newline, so the pattern kind is always spelled out.
    return f'description(substring:"{description}")'


def operations():
    """Every operation id, newest first, full hex so no prefix can be ambiguous."""
    return jj("op", "log", "--no-graph", "-T", 'id ++ "\\n"').split()


def change_id_of(description, op=None):
    """The change id of the commit described `description`, or None if absent."""
    args = (
        "log", "-r", revset(description), "--no-graph",
        "-T", 'change_id.short(12) ++ "\\n"',
    )
    out = at_op(op, *args) if op else jj(*args)
    found = out.split()
    assert len(found) <= 1, (
        f"Expected at most one commit described {description!r}"
        f"{f' at operation {op[:12]}' if op else ''}, got {found}"
    )
    return found[0] if found else None


def parents_of(description, op=None):
    """Change ids of the parents of the commit described `description`.

    None when no such commit is visible at that operation (which is the case for
    every operation before the bootstrap created it).
    """
    args = (
        "log", "-r", revset(description), "--no-graph",
        "-T", 'parents.map(|p| p.change_id().short(12)).join(" ") ++ "\\n"',
    )
    out = at_op(op, *args) if op else jj(*args)
    lines = [line for line in out.splitlines() if line.strip()]
    if not lines:
        return None
    assert len(lines) == 1, (
        f"Expected at most one commit described {description!r}"
        f"{f' at operation {op[:12]}' if op else ''}, got {lines}"
    )
    return lines[0].split()


def operations_with_b_on(parent_description):
    """Operations at which `B` sat on exactly the given commit.

    Compared as change ids, which survive a rebase, so this is "the same commit
    on a different parent" and not "some commit that happens to be described B".
    """
    target = change_id_of(parent_description)
    assert target is not None, (
        f"No commit described {parent_description!r} is visible in the "
        f"repository, so where {REBASED!r} sits cannot be established."
    )
    return [
        op for op in operations()
        if parents_of(REBASED, op) == [target]
    ]


def test_mistaken_rebase_actually_happened():
    """Requirement 1: commit B was rebased onto base.

    Structural: at some operation in the log, the change described `B` had
    `base` as its only parent. The untouched bootstrap has no such operation,
    and neither does a rebase of some other commit -- which is what the previous
    English-matching version could not tell apart.
    """
    moved = operations_with_b_on(WRONG_PARENT)
    assert moved, (
        f"No operation in the log has commit {REBASED!r} sitting on "
        f"{WRONG_PARENT!r}, so the rebase named in requirement 1 never "
        f"happened to that commit. Replayed "
        f"{len(operations())} operation(s)."
    )


def test_mistaken_rebase_was_reverted():
    """Requirement 2: that rebase was undone, and the repo is back where it was.

    A conjunction on purpose. The correct end state of this task is identical to
    its bootstrap state, so an end-state assertion on its own passes with no
    agent (all four below are in the vacuity floor and earn nothing). Pairing
    "the rebase is in the log" with "and B is on A again now" is what makes the
    round trip scoreable. Any route qualifies -- `jj undo`, `jj op undo`,
    `jj op revert`, `jj op restore` -- because none of them is named here.
    """
    moved = operations_with_b_on(WRONG_PARENT)
    assert moved, (
        f"Commit {REBASED!r} never sat on {WRONG_PARENT!r} in any operation, so "
        f"there was no mistaken rebase to revert."
    )

    right = change_id_of(RIGHT_PARENT)
    now = parents_of(REBASED)
    assert now == [right], (
        f"Commit {REBASED!r} currently sits on {now}, not on {RIGHT_PARENT!r} "
        f"({right}). The rebase at operation {moved[0][:12]} was never "
        f"reverted."
    )

    conflicted = jj(
        "log", "-r", revset(REBASED), "--no-graph", "-T", 'conflict ++ "\\n"'
    ).split()
    assert conflicted == ["false"], (
        f"Commit {REBASED!r} is still in a conflicted state ({conflicted}), so "
        f"the rebase was not cleanly reverted."
    )


def test_commits_survived():
    for description in COMMITS:
        out = jj("log", "-r", revset(description), "--no-graph", "-T", 'change_id.short() ++ "\\n"')
        found = out.split()
        assert len(found) == 1, f"Expected exactly one commit described {description!r}, got {found}"


def test_topology_restored():
    """Every commit is back on its original parent, so the rebase was reverted."""
    for description, expected_parent in PARENT_OF.items():
        out = jj(
            "log", "-r", revset(description), "--no-graph",
            "-T", 'parents.map(|p| p.description().first_line()).join(",") ++ "\\n"',
        )
        assert out.strip() == expected_parent, (
            f"Commit {description!r} sits on parent {out.strip()!r}, expected {expected_parent!r}"
        )


def test_main_bookmark_restored():
    out = jj("log", "-r", revset("A"), "--no-graph", "-T", 'bookmarks.join(",") ++ "\\n"')
    assert out.strip() == "main", f"Expected bookmark 'main' on commit 'A', got {out.strip()!r}"


def test_file_contents_restored():
    for description in COMMITS:
        out = jj("file", "show", "f", "-r", revset(description))
        assert out == f"{description}\n", (
            f"File 'f' at commit {description!r} contains {out!r}, expected {description!r} + newline"
        )
