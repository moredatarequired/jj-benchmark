"""Grade the commit the bootstrap handed over, wherever the agent left it.

WHAT IS GRADED, AND WHY IT IS NOT A POSITION
============================================

Both scored assertions used to be about the position `@-`: it tracks app.log,
and its description contains `Track log file`. Position is not identity, and it
is not even a stable position:

  * `jj new -r 'root()' -m "Track log file"` + `jj file track app.log` + `jj new`
    puts a commit the agent built entirely from scratch at `@-`, and both
    assertions pass on it.
  * `jj describe -m "Track log file"` finalises the working copy without
    starting a new one, so the commit that carries the tracked file and the
    message is `@` -- and `@-` is `Initial commit`. Both scored tests failed, for
    a repository in which the graded work is done and done correctly.

So the graded commit is now named directly, through the anchor's reserved
per-workspace working-copy key: the change the bootstrap's `@` was sitting on
(its description at handover was `""`, so the workspace name is the only key it
has -- see tests/anchor.py). Every assertion below is made about that change, and
nothing is asserted about where it now sits relative to `@`.

`jj commit` finalises a working-copy commit IN PLACE -- the change id survives,
the description and the tracked content are added to it, and a new empty child
becomes `@`. `jj describe` does the same thing minus the empty child. Both put
the tracked file and the message on the same change, which is the artifact the
task is about; the empty successor is an implementation detail of `jj commit`,
not something the user can observe. Grading the change rather than the position
is therefore both stronger (a fabricated commit at `@-` is never looked at) and
fairer (the `jj describe` finish is no longer a zero).

The bootstrap's `@` is not exempted in any anchor_exemptions.json, so a route
that abandons it instead of finalising it fails the session-scoped fixture in
conftest.py outright, and a wipe-and-rebuild fails it on the handover operation
id. Neither can reach the assertions below.

In cold CI there is no anchor file -- change ids are random per image build --
and the resolver ABSTAINS: it returns the `@-` this file used before and prints
that no identity claim was made, leaving each test exactly as strong as it was.
A missing anchor never fabricates a failure.
"""

import os
import subprocess

from anchor import working_copy_or_fallback

PROJECT_DIR = "/home/user/project"

# The revset the graded commit is resolved by when the anchor cannot supply its
# change id -- CI always builds cold, and so does any sweep run without
# `scripts/bootstrap_anchor.py --write`. `@-` is the position every assertion
# already used, so each test then says exactly what it said before the anchor
# existed; working_copy_or_fallback() prints a line recording that the claim was
# not made.
WC_FALLBACK = "@-"

# Exactly what the bootstrap wrote (`echo "*.log" > .gitignore`). Compared byte
# for byte: the instruction says not to modify the ignore rules, and the old
# `"*.log" in content` check was satisfied by a file with `!app.log` appended --
# which is the one route the constraint exists to rule out.
GITIGNORE = "*.log\n"


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


def graded_commit():
    """THE anchored claim: the change the bootstrap's working copy was sitting on.

    Returns the revset naming it. Callers assert about that revset, so the
    identity claim is in the addressing rather than in a separate check -- a
    commit built somewhere else cannot be the thing that gets graded.
    """
    revset = working_copy_or_fallback(WC_FALLBACK, workspace="default",
                                      repo=PROJECT_DIR)
    found = change_ids(revset)
    assert len(found) == 1, (
        f"{revset!r} resolves to {len(found)} commit(s) in {PROJECT_DIR}: "
        f"{found}. The working copy this task handed over is one change; "
        "finalizing it -- `jj commit` or `jj describe` -- keeps its change id."
    )
    return revset


def test_app_log_is_tracked():
    graded = graded_commit()
    tracked = jj("file", "list", "-r", graded).splitlines()
    assert "app.log" in tracked, (
        f"`app.log` is not tracked in the commit this task handed over "
        f"({graded}); it lists {sorted(tracked)}. Tracking the file adds it to "
        "the working copy that was there, which is the commit that gets graded "
        "however the agent finalizes it."
    )


def test_gitignore_unchanged():
    """The ignore rules are byte-for-byte the ones the bootstrap wrote.

    Checked both on disk and in the graded commit's tree. The old version only
    asserted that `*.log` was still somewhere in the file, so appending
    `!app.log` -- which auto-tracks app.log and is exactly what the instruction
    forbids -- passed it.
    """
    gitignore_path = os.path.join(PROJECT_DIR, ".gitignore")
    assert os.path.isfile(gitignore_path), f".gitignore file {gitignore_path} does not exist."
    with open(gitignore_path) as f:
        content = f.read()
    assert content == GITIGNORE, (
        f"`.gitignore` on disk is {content!r}; the bootstrap wrote {GITIGNORE!r} "
        "and the task says not to modify it. `app.log` has to be tracked "
        "explicitly, not un-ignored."
    )
    graded = graded_commit()
    committed = jj("file", "show", "-r", graded, ".gitignore")
    assert committed == GITIGNORE, (
        f"`.gitignore` in the commit this task handed over ({graded}) is "
        f"{committed!r}; the bootstrap committed {GITIGNORE!r}."
    )


def test_commit_message():
    graded = graded_commit()
    description = jj("log", "-r", graded, "--no-graph", "-T", "description")
    assert "Track log file" in description, (
        f"Expected the description of the commit this task handed over "
        f"({graded}) to contain 'Track log file', got: {description!r}"
    )
