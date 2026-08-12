"""The commit that tracks app.log has to be the working copy that was handed over.

Both scored assertions used to be about the position `@-`: it tracks app.log, and
its description contains `Track log file`. Position is not identity. `jj new -r
'root()' -m "Track log file"` + `jj file track app.log` + `jj new` puts a commit
the agent built entirely from scratch at `@-`, and both assertions pass -- and
because nothing is removed, every anchored change id is still visible, so the
bootstrap anchor holds and the verifier grades the fabricated commit.

The task's own words are "finalize the CURRENT working copy by creating a new
commit", and `jj commit` finalizes a working-copy commit in place: the change id
survives, the description and content are added to it. So `@-` has to be the change
the bootstrap's working copy was sitting on -- named through the anchor's reserved
per-workspace working-copy key, because its description at handover was `""` (see
tests/anchor.py).
"""

import os
import subprocess

from anchor import working_copy_or_fallback

PROJECT_DIR = "/home/user/project"

# The revset the handover working copy is resolved by when the anchor cannot supply
# its change id -- CI always builds cold, and so does any sweep run without
# `scripts/bootstrap_anchor.py --write`. `@-` is the position both assertions
# already used, so the identity check collapses into a tautology and each test says
# exactly what it said before the anchor existed; working_copy_or_fallback() prints
# a line recording that the claim was not made.
WC_FALLBACK = "@-"


def jj(*args):
    """A read-only jj call. --ignore-working-copy on every one, without exception."""
    result = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=PROJECT_DIR, capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"`jj {' '.join(args)}` failed in {PROJECT_DIR} ({result.returncode}): "
        f"{result.stderr.strip()}"
    )
    return result.stdout


def change_ids(revset):
    return [
        line for line in
        jj("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\n"').splitlines()
        if line
    ]


def assert_parent_is_the_handover_working_copy():
    """THE anchored claim: `@-` is the change the bootstrap's working copy was on."""
    revset = working_copy_or_fallback(WC_FALLBACK, workspace="default",
                                     repo=PROJECT_DIR)
    wanted = change_ids(revset)
    assert len(wanted) == 1, (
        f"{revset!r} resolves to {len(wanted)} commit(s) in {PROJECT_DIR}: {wanted}"
    )
    parent = change_ids("@-")
    assert parent == wanted, (
        f"`@-` is {[c[:12] for c in parent]}, but the working copy this task handed "
        f"over is the change {wanted[0][:12]}. Finalizing the current working copy "
        "keeps its change id -- `jj commit` describes that very change and starts "
        "a new empty one on top. A different change at `@-` means the graded "
        "commit was built somewhere else rather than out of what was there."
    )


def test_app_log_is_tracked():
    result = subprocess.run(
        ["jj", "--ignore-working-copy", "file", "list", "-r", "@-"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        check=True
    )
    assert "app.log" in result.stdout, "Expected app.log to be tracked in the previous commit (@-)."
    assert_parent_is_the_handover_working_copy()


def test_gitignore_unchanged():
    gitignore_path = os.path.join(PROJECT_DIR, ".gitignore")
    assert os.path.isfile(gitignore_path), f".gitignore file {gitignore_path} does not exist."
    with open(gitignore_path) as f:
        content = f.read()
    assert "*.log" in content, "Expected .gitignore to contain '*.log'."


def test_commit_message():
    result = subprocess.run(
        ["jj", "--ignore-working-copy", "log", "-r", "@-", "--no-graph",
         "-T", "description"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        check=True
    )
    assert "Track log file" in result.stdout, f"Expected commit description to contain 'Track log file', got: {result.stdout}"
    assert_parent_is_the_handover_working_copy()
