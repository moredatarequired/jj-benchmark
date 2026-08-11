"""Bootstrap check for next_prev_navigation.

The final-state verifier reconstructs the route the working copy took by
loading the repo at each operation (`jj --at-op=<id>`) and asking which commit
the working copy sat on. It finds the end of the bootstrap by looking for the
oldest operation at which the working copy sat on D. That is only a valid
boundary if the bootstrap reaches D's child position exactly once, at its very
last operation -- so this file asserts that too, and a future edit to the
Dockerfile that broke the assumption fails here instead of silently loosening
the verifier.
"""

import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/myproject"

COMMITS = ["commit A", "commit B", "commit C", "commit D"]
PARENT_OF = {
    "commit A": [],
    "commit B": ["commit A"],
    "commit C": ["commit B"],
    "commit D": ["commit C"],
}
FILE_AT = {
    "commit A": "A\n",
    "commit B": "A\nB\n",
    "commit C": "A\nB\nC\n",
    "commit D": "A\nB\nC\nD\n",
}

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
    return f'description(substring:"{description}")'


def commit_id(description):
    found = out(
        "log", "-r", revset(description), "--no-graph", "-T", 'commit_id ++ "\\n"'
    ).split()
    assert len(found) == 1, (
        f"Expected exactly one commit described {description!r}, found {len(found)}: {found}"
    )
    return found[0]


def test_jj_binary_available():
    assert shutil.which("jj") is not None, "jj binary not found in PATH."


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), f"Project directory {PROJECT_DIR} does not exist."


def test_initial_history_is_linear_A_to_D():
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


def test_initial_working_copy_is_an_empty_child_of_D():
    row = out(
        "log", "-r", "@", "--no-graph", "-T",
        'if(empty, "empty", "nonempty") ++ " "'
        ' ++ parents.map(|p| p.commit_id()).join(",") ++ "\\n"',
    ).split()
    assert len(row) == 2, f"Unexpected working-copy state: {row}"
    empty, parents = row[0], row[1].split(",")
    assert parents == [commit_id("commit D")], (
        f"The working copy has parents {parents}, expected exactly commit D"
    )
    assert empty == "empty", "The working copy commit is not empty"


def test_initial_state_has_no_extra_commits():
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
    assert not extra, f"The bootstrap left unexpected commits behind: {extra}"


def test_bootstrap_reaches_D_only_at_its_last_operation():
    """The verifier's route reconstruction depends on this.

    It treats the oldest operation at which the working copy sits on D as the
    handover point between the bootstrap and the agent. If the bootstrap parked
    the working copy on D earlier as well, everything the bootstrap did after
    that would be counted as part of the agent's route.
    """
    op_ids = out(
        "op", "log", "--ignore-working-copy", "--reversed", "--no-graph",
        "-T", 'id ++ "\\n"',
    ).split()
    d = (commit_id("commit D"),)
    positions = []
    for op_id in op_ids:
        result = jj(
            f"--at-op={op_id}", "log", "-r", "@", "--no-graph", "-T",
            'parents.map(|p| p.commit_id()).join(" ") ++ "\\n"',
            check=False,
        )
        positions.append(None if result.returncode else tuple(result.stdout.split()))
    on_d = [i for i, pos in enumerate(positions) if pos == d]
    assert on_d == [len(op_ids) - 1], (
        "The working copy should sit on commit D at exactly the last bootstrap "
        f"operation (index {len(op_ids) - 1} of {len(op_ids)}), but it sits there "
        f"at operation indices {on_d}"
    )
