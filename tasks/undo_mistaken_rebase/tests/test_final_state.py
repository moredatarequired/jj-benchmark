import subprocess

REPO = "/home/user/repo"

# Bootstrap history: root() <- base <- A (main) <- B
COMMITS = ["base", "A", "B"]
PARENT_OF = {"base": "", "A": "base", "B": "A"}


def jj(*args):
    result = subprocess.run(["jj", *args], cwd=REPO, capture_output=True, text=True)
    assert result.returncode == 0, f"`jj {' '.join(args)}` failed: {result.stderr}"
    return result.stdout


def revset(description):
    # jj 0.38 matches description() exactly by default, and descriptions end in a newline.
    return f'description(substring:"{description}")'


def op_descriptions():
    """Operation descriptions, newest first."""
    out = jj("op", "log", "--no-graph", "-T", 'description ++ "\\n"')
    return [line for line in out.splitlines() if line.strip()]


def test_rebase_was_performed():
    """An agent that did nothing at all leaves the repo in the correct final state."""
    ops = op_descriptions()
    assert any("rebase" in op.lower() for op in ops), (
        f"No rebase operation found in the operation log: {ops}"
    )


def test_undo_came_after_rebase():
    """`jj undo` must have reverted the rebase, not run before it."""
    ops = op_descriptions()  # newest first
    undo = next((i for i, op in enumerate(ops) if "undo" in op.lower()), None)
    rebase = next((i for i, op in enumerate(ops) if "rebase" in op.lower()), None)
    assert undo is not None, f"No undo operation found in the operation log: {ops}"
    assert rebase is not None, f"No rebase operation found in the operation log: {ops}"
    assert undo < rebase, f"The undo predates the rebase, so it did not revert it: {ops}"


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
