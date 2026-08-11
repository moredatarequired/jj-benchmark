"""Verifier for next_prev_navigation.

The task asks for a three-step walk of the working copy through the commit
graph: from D's child position to C's, then to A's, then to B's. The old
verifier only checked the destination (`@-` describes "commit B", working copy
clean), which a single `jj new B` satisfies -- so the task scored full marks
without any navigation happening.

The route is recoverable state, not just narrative: every move of the working
copy is its own entry in the operation log, and `jj --at-op=<id>` can load the
repo as it stood after any one of them. So for each operation we ask the repo
what commit the working copy sat on at that point, and compare *commit ids* --
not jj's English operation descriptions ("prev: ... -> ...", "new empty
commit"), which are wording jj is free to change and which would also pin the
solution to one particular command. A single `jj new B` produces one operation
and therefore one position; it cannot fake three.
"""

import subprocess

PROJECT_DIR = "/home/user/myproject"

# Bootstrap history: root() <- A <- B <- C <- D, working copy an empty child of D.
COMMITS = ["commit A", "commit B", "commit C", "commit D"]
PARENT_OF = {
    "commit A": [],
    "commit B": ["commit A"],
    "commit C": ["commit B"],
    "commit D": ["commit C"],
}
# file.txt gains one line per commit.
FILE_AT = {
    "commit A": "A\n",
    "commit B": "A\nB\n",
    "commit C": "A\nB\nC\n",
    "commit D": "A\nB\nC\nD\n",
}
# The positions the working copy must pass through, oldest first.
REQUIRED_ROUTE = ["commit C", "commit A", "commit B"]

ROOT_COMMIT_ID = "0" * 40


def jj(*args, check=True):
    result = subprocess.run(
        ["jj", *args], cwd=PROJECT_DIR, capture_output=True, text=True
    )
    if check:
        assert result.returncode == 0, (
            f"`jj {' '.join(args)}` failed ({result.returncode}): {result.stderr}"
        )
    return result


def out(*args):
    return jj(*args).stdout


def revset(description):
    # jj 0.38 matches description() exactly by default, and descriptions end in
    # a newline, so substring: is what matches "commit A" against "commit A\n".
    return f'description(substring:"{description}")'


def commit_id(description):
    """The single commit with this description, as a full commit id."""
    found = out(
        "log", "-r", revset(description), "--no-graph", "-T",
        'commit_id ++ "\\n"',
    ).split()
    assert len(found) == 1, (
        f"Expected exactly one commit described {description!r}, found {len(found)}: {found}"
    )
    return found[0]


def working_copy_parents_at(op_id):
    """Commit ids of the working copy's parents just after operation `op_id`.

    Returns None if that operation had no working-copy commit at all (the root
    operation, and the operations before the workspace existed).
    """
    result = jj(
        f"--at-op={op_id}", "log", "-r", "@", "--no-graph", "-T",
        'parents.map(|p| p.commit_id()).join(" ") ++ "\\n"',
        check=False,
    )
    if result.returncode != 0:
        return None
    return tuple(result.stdout.split())


def route():
    """The working copy's positions after the bootstrap, oldest first.

    A "position" is the tuple of parent commit ids of the working copy.
    Consecutive repeats are collapsed, so operations that did not move the
    working copy (a snapshot of edited files, a description change) do not
    show up as extra steps.

    The bootstrap itself walks the working copy forward as it builds the four
    commits, so we start counting at the last bootstrap operation: the oldest
    one at which the working copy sat on D. Operations are append-only, so
    nothing an agent does can land before it.
    """
    # jj snapshots the working copy at the start of most commands. Force that
    # now, then read the operation log with --ignore-working-copy, so the log
    # we walk is the same regardless of which test ran first.
    jj("status", check=False)
    op_ids = out(
        "op", "log", "--ignore-working-copy", "--reversed", "--no-graph",
        "-T", 'id ++ "\\n"',
    ).split()

    d = (commit_id("commit D"),)
    positions = [(op_id, working_copy_parents_at(op_id)) for op_id in op_ids]
    start = next((i for i, (_, pos) in enumerate(positions) if pos == d), None)
    assert start is not None, (
        "Could not find the end of the bootstrap in the operation log: no "
        "operation leaves the working copy sitting on 'commit D'. The four "
        "original commits must have been rewritten."
    )

    steps = []
    previous = d
    for op_id, pos in positions[start + 1:]:
        if pos is None or pos == previous:
            continue
        steps.append((op_id, pos))
        previous = pos
    return steps


def describe(position, names):
    """Render a position as commit names where we know them."""
    if position is None:
        return "(no working copy)"
    return "+".join(names.get(cid, cid[:12]) for cid in position) or "(root)"


def test_original_commits_intact():
    """The four commits must still be the linear history A -> B -> C -> D.

    Without this, the route check below could be satisfied by renaming `@-`
    three times over instead of moving the working copy.
    """
    ids = {commit_id(description): description for description in COMMITS}
    ids[ROOT_COMMIT_ID] = "root()"
    for description, expected in PARENT_OF.items():
        parents = out(
            "log", "-r", revset(description), "--no-graph", "-T",
            'parents.map(|p| p.commit_id()).join(" ") ++ "\\n"',
        ).split()
        got = [ids.get(cid, cid[:12]) for cid in parents if cid != ROOT_COMMIT_ID]
        assert got == expected, (
            f"Commit {description!r} sits on parents {got}, expected {expected}"
        )
    for description, content in FILE_AT.items():
        shown = out("file", "show", "file.txt", "-r", revset(description))
        assert shown == content, (
            f"file.txt at {description!r} holds {shown!r}, expected {content!r}"
        )


def test_no_extra_commits_left_behind():
    """Only the four originals and the working copy may exist."""
    rows = out(
        "log", "-r", "all()", "--no-graph", "-T",
        'commit_id ++ " " ++ if(current_working_copy, "@", "-") ++ " "'
        ' ++ description.first_line() ++ "\\n"',
    ).splitlines()
    extra = []
    for row in rows:
        if not row.strip():
            continue
        cid, marker, description = (row.split(" ", 2) + [""])[:3]
        if cid == ROOT_COMMIT_ID or marker == "@" or description in COMMITS:
            continue
        extra.append(f"{cid[:12]} {description!r}")
    assert not extra, (
        "The repository holds commits other than the four originals and the "
        f"working copy: {extra}"
    )


def test_working_copy_is_an_empty_child_of_B():
    b = commit_id("commit B")
    row = out(
        "log", "-r", "@", "--no-graph", "-T",
        'if(empty, "empty", "nonempty") ++ " "'
        ' ++ parents.map(|p| p.commit_id()).join(",") ++ "\\n"',
    ).split()
    assert len(row) == 2, f"Unexpected working-copy state: {row}"
    empty, parents = row[0], row[1].split(",")
    assert parents == [b], (
        f"The working copy has parents {parents}, expected exactly commit B ({b})"
    )
    assert empty == "empty", "The working copy commit is not empty"


def test_route_was_walked_one_step_at_a_time():
    """C's child, then A's child, then B's child -- three separate operations.

    Each required position must be the result of its own operation, in order.
    One operation can only leave the working copy in one place, so a shortcut
    straight to B produces a single step here and fails.
    """
    steps = route()
    names = {commit_id(description): description for description in COMMITS}
    walked = [describe(pos, names) for _, pos in steps]

    assert len(steps) >= len(REQUIRED_ROUTE), (
        f"The working copy moved {len(steps)} time(s) after the initial state "
        f"({walked}); the required route has {len(REQUIRED_ROUTE)} separate "
        "moves: C's child, then A's child, then B's child"
    )

    tail = steps[-len(REQUIRED_ROUTE):]
    expected = [(commit_id(description),) for description in REQUIRED_ROUTE]
    assert [pos for _, pos in tail] == expected, (
        "The working copy did not arrive at B's child position by way of C's "
        f"and then A's. Positions it moved through, oldest first: {walked}; "
        f"the last three had to be {REQUIRED_ROUTE}"
    )

    op_ids = [op_id for op_id, _ in tail]
    assert len(set(op_ids)) == len(REQUIRED_ROUTE), (
        f"The three moves are not three distinct operations: {op_ids}"
    )
