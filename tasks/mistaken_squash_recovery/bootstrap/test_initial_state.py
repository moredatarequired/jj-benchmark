"""Bootstrap check for the mistaken_squash_recovery task.

Asserts the starting state the request depends on: a repository in which two
commits have already been squashed into one, with two further commits made on
top since, so the mistake is buried in the operation log rather than being the
most recent thing that happened.

The load-bearing assertion here is test_exactly_one_operation_removed_a_commit.
Both the one-line prompt and the verifier depend on it -- the prompt says "the
squash I did by mistake" and means one findable operation, and the verifier
LOCATES that operation by differencing the visible change-id set across every
operation and taking the one where an id left. A second disappearance anywhere
in the bootstrap breaks both, and jj 0.44 will add one silently if the fixture
ever ends a step with `jj commit` and then moves `@` elsewhere.
"""

import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/checkout-api"

COMBINED = "add idempotency keys to charge requests"
LATER = ("raise the retry budget for charges",
         "note the 409 behaviour in the changelog")


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
    """[(op id, parent op id)] oldest-first."""
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
                "-T", 'change_id ++ " " ++ commit_id ++ "\\n"')
    return dict(line.split() for line in out.splitlines() if line.strip())


def disappearances():
    """[(op id, parent op id, {change ids that left})] over the whole log."""
    found = []
    for op, parent in operations():
        if parent is None:
            continue
        gone = set(visible_at(parent)) - set(visible_at(op))
        if gone:
            found.append((op, parent, gone))
    return found


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
    """Five commits: the squash already happened, and two landed on top."""
    out = jj_ok("log", "-r", "::@ ~ root()", "--no-graph", "--reversed",
                "-T", '"[" ++ description.first_line() ++ "]\\n"')
    lines = [line for line in out.splitlines() if line]
    assert lines == [
        "[add the charge endpoint]",
        "[retry failed charges with backoff]",
        f"[{COMBINED}]",
        f"[{LATER[0]}]",
        f"[{LATER[1]}]",
    ], f"Unexpected starting history: {lines}"


def test_the_mistake_is_already_in_the_repository():
    """One commit carries both commits' work, and the second message is gone."""
    changed = {line for line in
               jj_ok("diff", "-r", f'description(substring:"{COMBINED}")',
                     "--name-only").splitlines() if line}
    assert changed == {"src/api/charge.py", "src/api/handlers.py"}, (
        f"`{COMBINED}` should carry both commits' paths after the squash; it "
        f"changes {sorted(changed)}"
    )
    described = jj_ok("log", "-r", 'description(substring:"return 409")',
                      "--no-graph", "-T", 'change_id ++ "\\n"')
    assert not described.strip(), (
        "a commit described `return 409 on duplicate keys` is still visible, "
        "so the squash the task is about did not swallow it."
    )
    body = jj_ok("file", "show", "-r", f'description(substring:"{COMBINED}")',
                 "src/api/charge.py")
    assert "request_id=None" in body, (
        "the swallowed commit's edit to charge.py is not in the combined "
        "commit."
    )
    assert "def idempotency_key" in body, (
        "the surviving commit's own edit to charge.py is not in the combined "
        "commit."
    )


def test_exactly_one_operation_removed_a_commit():
    """Invariant 1, and the one the verifier's discovery rests on.

    The mistaken operation is found by what it did -- a change id left the
    visible set -- and not by jj's English description of it. That only works
    while exactly one operation in the log does it.
    """
    found = disappearances()
    assert len(found) == 1, (
        "expected exactly one operation in the bootstrap to remove a commit "
        f"(the squash); {len(found)} do: "
        + ", ".join(f"{op[:12]} removed {sorted(c[:8] for c in gone)}"
                    for op, _, gone in found)
        + ". A second one is most easily introduced by ending a step with "
        "`jj commit` and then moving `@` elsewhere, which makes jj 0.44 "
        "auto-abandon the empty commit it left behind, printing nothing."
    )
    _, _, gone = found[0]
    assert len(gone) == 1, (
        f"the squash should have removed exactly one commit; it removed "
        f"{len(gone)}."
    )


def test_the_mistake_is_neither_the_first_nor_the_last_operation():
    """Invariant 2: `jj undo` reverses the wrong thing, so it has to be found."""
    ops = [op for op, _ in operations()]
    squash_op = disappearances()[0][0]
    index = ops.index(squash_op)
    assert index > 0, "the squash is the first operation in the log."
    following = len(ops) - index - 1
    assert following >= 3, (
        f"only {following} operation(s) follow the squash; the mistake is "
        "supposed to be buried, so that reaching for the most recent operation "
        "is a distinguishable wrong answer."
    )


def test_the_two_later_commits_are_independent_of_the_squash():
    """Invariant 4: their paths are disjoint from the squashed commits'."""
    expected = {
        LATER[0]: {"src/client/retry.py"},
        LATER[1]: {"CHANGELOG.md"},
    }
    for description, paths in expected.items():
        changed = {line for line in
                   jj_ok("diff", "-r", f'description(substring:"{description}")',
                         "--name-only").splitlines() if line}
        assert changed == paths, (
            f"`{description}` should change {sorted(paths)}; it changes "
            f"{sorted(changed)}"
        )


def test_both_squashed_commits_touched_the_same_file():
    """Invariant 3: no split by path can put the pieces back.

    Read out of the repository as it stood before the squash, which is also how
    the verifier reads it.
    """
    op, parent, _ = disappearances()[0]
    before = visible_at(parent)
    after = visible_at(op)
    gone = (set(before) - set(after)).pop()
    rewritten = [c for c in set(before) & set(after) if before[c] != after[c]]
    assert len(rewritten) == 1, (
        f"expected the squash to rewrite exactly one commit; it rewrote "
        f"{len(rewritten)}"
    )
    for cid in (gone, rewritten[0]):
        changed = {line for line in
                   jj_ok("--at-op", parent, "diff", "-r", f"change_id({cid})",
                         "--name-only").splitlines() if line}
        assert "src/api/charge.py" in changed, (
            f"before the squash, {cid[:8]} changed {sorted(changed)}; both "
            "commits must touch src/api/charge.py so that the combined commit "
            "cannot be taken apart again by path."
        )


def test_the_working_copy_is_described_and_not_empty():
    """Invariant 5: the D11 guard on the handover side.

    jj 0.44 silently abandons an empty, undescribed `@` when you leave it. A
    described, non-empty `@` cannot be lost that way, which is what lets this
    task ship with no anchor exemption file.
    """
    out = jj_ok("log", "-r", "@", "--no-graph", "-T",
                'description.first_line() ++ "|" ++ if(empty, "empty", "nonempty")')
    assert out.strip() == f"{LATER[1]}|nonempty", (
        f"Expected `@` to be the described, non-empty `{LATER[1]}`; got "
        f"{out.strip()!r}"
    )


def test_main_bookmark():
    out = jj_ok("bookmark", "list")
    names = {line.split(":")[0] for line in out.splitlines() if ":" in line}
    assert names == {"main"}, f"Expected only a `main` bookmark; got {sorted(names)}"
