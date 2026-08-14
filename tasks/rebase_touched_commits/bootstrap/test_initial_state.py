"""Bootstrap check for the rebase_touched_commits task.

Asserts the starting state the request depends on: an operation log holding one
multi-commit rebase among smaller operations made after it, and -- the invariant
the whole task rests on -- a repository whose CURRENT graph does not answer the
question.

test_the_answer_is_not_readable_off_the_current_graph is the load-bearing one.
The branch carries five commits and the rebase changed four, because a fifth was
made after the rebase ran. If a future edit makes those two sets coincide, the
task can be solved by `jj log -r 'main..'` without ever opening the operation
log, and it stops measuring anything at all.
"""

import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/checkout-api"

BRANCH = (
    "retry failed charges with backoff",
    "cap the retry budget at 30 seconds per charge",
    "surface retry counts in the charge response",
    "note the retry behaviour in the changelog",
)
MADE_AFTER = "start on the daily settlement report"


def jj(*args):
    return subprocess.run(
        ["jj", *args], cwd=PROJECT_DIR, capture_output=True, text=True
    )


def jj_ok(*args):
    result = jj(*args)
    assert result.returncode == 0, (
        f"`jj {' '.join(args)}` failed: {result.stderr.strip()}"
    )
    return result.stdout


def operations():
    out = jj_ok("op", "log", "--no-graph", "-T",
                'id ++ " " ++ parents.map(|p| p.id()) ++ "\\n"')
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        rows.append((parts[0], parts[1] if len(parts) > 1 else None))
    return list(reversed(rows))


def visible_at(op):
    out = jj_ok("--at-op", op, "log", "-r", "all() ~ root()", "--no-graph",
                "-T", 'change_id ++ " " ++ commit_id ++ " [" '
                      '++ parents.map(|p| p.change_id()).join(",") ++ "]\\n"')
    state = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        cid, commit, parents = line.split(" ", 2)
        state[cid] = (commit,
                      frozenset(p for p in parents.strip("[]").split(",") if p))
    return state


def reparenting_operations():
    """[(op id, index, {change ids whose commit id moved})] -- the rebases."""
    found = []
    ops = operations()
    for index, (op, parent) in enumerate(ops):
        if parent is None:
            continue
        before, after = visible_at(parent), visible_at(op)
        both = set(before) & set(after)
        if any(before[c][1] != after[c][1] for c in both):
            found.append(
                (op, index, {c for c in both if before[c][0] != after[c][0]})
            )
    return found


def change_ids(revset):
    return {line for line in
            jj_ok("log", "-r", revset, "--no-graph",
                  "-T", 'change_id ++ "\\n"').splitlines() if line}


def test_jj_binary_available():
    assert shutil.which("jj") is not None, "jj binary not found in PATH."


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), f"{PROJECT_DIR} does not exist."


def test_jj_repo_initialized():
    result = jj("status")
    assert result.returncode == 0, (
        f"jj status failed, not a jj repository. Error: {result.stderr}"
    )


def test_history_shape():
    out = jj_ok("log", "-r", "::@ ~ root()", "--no-graph", "--reversed",
                "-T", '"[" ++ description.first_line() ++ "]\\n"')
    lines = [line for line in out.splitlines() if line]
    assert lines == [
        "[add the charge endpoint]",
        "[extract the http client]",
        "[regenerate the api client from the 2.4 schema]",
        *[f"[{d}]" for d in BRANCH],
        f"[{MADE_AFTER}]",
    ], f"Unexpected starting history: {lines}"


def test_the_answer_file_is_not_already_there():
    assert not os.path.exists(os.path.join(PROJECT_DIR, "touched.txt")), (
        "touched.txt already exists; the task is to produce it."
    )


def test_exactly_one_operation_reparented_a_commit():
    """Invariant 1, and the signature the verifier's discovery rests on.

    A rebase changes some commit's parents; a describe does not, however many
    commits it rewrites. That is what makes this a signature rather than a
    heuristic.
    """
    found = reparenting_operations()
    assert len(found) == 1, (
        f"expected exactly one operation to reparent a commit (the rebase); "
        f"{len(found)} do: "
        + ", ".join(f"{op[:12]} changed {len(changed)}" for op, _, changed in found)
    )


def test_the_rebase_moved_four_commits_and_is_not_the_last_operation():
    """Invariant 2: four is more than a plausible guess, and it is buried."""
    op, index, changed = reparenting_operations()[0]
    assert len(changed) == 4, (
        f"the rebase should have changed four commits; it changed "
        f"{len(changed)}"
    )
    following = len(operations()) - index - 1
    assert following >= 3, (
        f"only {following} operation(s) follow the rebase; it is supposed to "
        "be buried, so that taking the most recent entry is a distinguishable "
        "wrong answer."
    )
    described = {line for line in
                 jj_ok("log", "-r",
                       " | ".join(f"change_id({c})" for c in sorted(changed)),
                       "--no-graph", "-T",
                       'description.first_line() ++ "\\n"').splitlines() if line}
    assert described == set(BRANCH), (
        f"the rebase should have moved exactly the four branch commits; it "
        f"moved {sorted(described)}"
    )


def test_the_answer_is_not_readable_off_the_current_graph():
    """Invariant 3, and the reason this task is about the operation log.

    Every cheap current-graph revset returns five commits where the answer is
    four, because a fifth commit was made after the rebase ran.
    """
    _, _, changed = reparenting_operations()[0]
    for revset in ("main..retry-backoff", "main..@", "main.."):
        found = change_ids(revset)
        assert found != changed, (
            f"`{revset}` returns exactly the set the rebase changed, so this "
            "task can be solved without ever reading the operation log."
        )
        assert len(found) == 5 and len(changed) == 4, (
            f"`{revset}` returns {len(found)} commits and the rebase changed "
            f"{len(changed)}; the fixture is built so those are 5 and 4."
        )
        assert changed < found, (
            f"the commits the rebase changed should be a strict subset of "
            f"`{revset}`; they are not."
        )


def test_the_rebase_was_clean():
    """Invariant 4: main only touched src/generated/, so nothing conflicted."""
    assert not change_ids("conflicts()"), (
        "the repository holds conflicted commits; this task's rebase is "
        "supposed to have been clean."
    )


def test_the_working_copy_is_described_and_not_empty():
    """Invariant 5: the D11 guard.

    Writing touched.txt into a described, non-empty `@` cannot silently lose a
    bootstrap commit, which is why this task ships with no anchor exemption.
    """
    out = jj_ok("log", "-r", "@", "--no-graph", "-T",
                'description.first_line() ++ "|" ++ if(empty, "empty", "nonempty")')
    assert out.strip() == f"{MADE_AFTER}|nonempty", (
        f"Expected `@` to be the described, non-empty `{MADE_AFTER}`; got "
        f"{out.strip()!r}"
    )


def test_bookmarks():
    out = jj_ok("bookmark", "list")
    names = {line.split(":")[0] for line in out.splitlines() if ":" in line}
    assert names == {"main", "release/2.4", "retry-backoff"}, (
        f"Expected main, release/2.4 and retry-backoff; got {sorted(names)}"
    )
    assert "fork-point" not in names, (
        "the scaffolding bookmark `fork-point` should have been deleted before "
        "handover."
    )
