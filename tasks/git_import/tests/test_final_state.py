"""Grade the EFFECT of an explicit Git import, never the spelling of the command.

The previous verifier was a single `assert "args: jj git import" in stdout`
against `jj op log`. That is a literal substring match on how the agent happened
to type the command, and jj records the argv verbatim: a correct solve run as
`jj -R /home/user/project git import` records
`args: jj -R /home/user/project git import`, which does not contain the literal
`args: jj git import`. A verifiably correct repository therefore scored 0. (This
is the same class of failure as grepping jj's English operation descriptions --
see the operation-description note in tasks/undo_mistaken_rebase.)

What is checked instead is repository state, expressed as commit ids:

  1. the Git commit the task is about is part of jj's visible commit set, and
  2. jj's working copy now sits on top of it -- which is the half of the import
     that carries Git HEAD over rather than just the refs.

Neither holds in the untouched bootstrap image, where jj knows only about
`initial commit`.

TWO THINGS THIS FILE HAS TO BE CAREFUL ABOUT
--------------------------------------------

**The verifier must not perform the import it is grading.** The repository is
colocated, so *every* ordinary jj command imports the underlying Git repo before
it answers -- a plain `jj op log` in a verifier manufactures exactly the state
the verifier is looking for, and the second run of the same verifier then grades
what the first run did. Measured on jj 0.38.0 against the untouched bootstrap:

    $ jj --at-op=@ op log ...
    Reset the working copy parent to the new Git HEAD.
    Done importing changes from the underlying Git repo.        <- it imported

    $ jj --ignore-working-copy op log ...
    a699eaa470b1 import git head                                <- nothing new

Note that `--at-op=@` is NOT sufficient: jj imports during command startup and
only then resolves `@`, so the read still lands after an import of its own
making. `--ignore-working-copy` does suppress it, and leaves `.jj/repo/op_heads`
byte-identical. So every jj call below goes through jj() below, which passes
`--ignore-working-copy` first, and the file is idempotent by construction.

**The anchor is the Git commit's own message, not whatever Git HEAD is now.**
Reading the target commit as `git rev-parse HEAD` would let a `git reset --hard
HEAD~1` pass: HEAD would then be `initial commit`, which jj has known about
since the bootstrap, so both assertions would hold without an import ever having
happened. Looking the commit up by the message the Dockerfile gave it means
destroying it fails the task instead of trivialising it.

WHAT IS DELIBERATELY *NOT* CHECKED
----------------------------------

instruction.md also tells the agent not to run other jj commands that would
trigger the import implicitly. That is not gradeable, and pretending otherwise
is what produced the bug above:

  * jj records nothing structural that distinguishes an explicit `jj git import`
    from the automatic import performed by `jj status`. Both write operations
    described `import git refs` / `import git head`; the only difference lives
    in the `args:` line, i.e. in the argv spelling this rewrite exists to stop
    depending on.
  * The end states are byte-identical apart from commit ids.

So the constraint stays in the instruction as guidance about how to work, and
the grade rests on the import having actually happened. Any solve that leaves
the repository in the imported state passes, however it was spelled.
"""

import subprocess

PROJECT_DIR = "/home/user/project"

# The message environment/Dockerfile gives the Git commit that has not been
# imported yet. This is the bootstrap's own text, not jj output, so nothing here
# depends on jj's wording.
NEW_COMMIT_MESSAGE = "new commit"


def run(*args):
    result = subprocess.run(
        args, cwd=PROJECT_DIR, capture_output=True, text=True
    )
    assert result.returncode == 0, (
        f"`{' '.join(args)}` failed with status {result.returncode}: {result.stderr}"
    )
    return result.stdout


def git(*args):
    return run("git", *args)


def jj(*args):
    """A read-only jj call.

    `--ignore-working-copy` comes first and is not optional: without it jj
    snapshots the working copy *and* imports the colocated Git repo before
    answering, so the verifier would create the state it is grading and would
    not agree with itself on a second run.
    """
    return run("jj", "--ignore-working-copy", *args)


def new_git_commit():
    """The commit id of the Git commit that the agent has to import.

    Looked up by message rather than as `git rev-parse HEAD`, so that removing
    the commit from Git fails this task rather than making it vacuous.
    """
    out = git("log", "--all", "--format=%H%x00%s")
    matches = [
        line.split("\0", 1)[0]
        for line in out.splitlines()
        if line.split("\0", 1)[1:] == [NEW_COMMIT_MESSAGE]
    ]
    assert len(matches) == 1, (
        f"Expected exactly one Git commit whose message is "
        f"{NEW_COMMIT_MESSAGE!r}, found {matches}. The Git commit that was to "
        f"be imported is no longer in the repository."
    )
    return matches[0]


def test_new_git_commit_is_visible_to_jj():
    """The import happened: jj can see the commit Git made.

    Untouched, jj's visible set holds only `initial commit` (plus its own
    working-copy commit and the root commit), because nothing has imported the
    Git commit yet.
    """
    target = new_git_commit()
    visible = jj(
        "log", "-r", "all()", "--no-graph", "-T", 'commit_id ++ "\\n"'
    ).split()
    assert target in visible, (
        f"The Git commit {target} (message {NEW_COMMIT_MESSAGE!r}) is not in "
        f"jj's visible commit set {visible}, so it was never imported."
    )


def test_working_copy_follows_the_imported_git_head():
    """`jj git import` carries Git HEAD over too, not just the refs.

    After the import jj's working copy sits on top of the imported commit, so
    the imported commit is an ancestor of `@`. Ancestry rather than "is exactly
    the parent of `@`" so that a solve which goes on to create further commits
    is not punished for it.
    """
    target = new_git_commit()
    ancestors = jj(
        "log", "-r", f"::@ & {target}", "--no-graph", "-T", 'commit_id ++ "\\n"'
    ).split()
    assert ancestors == [target], (
        f"The imported Git commit {target} is not an ancestor of jj's working "
        f"copy (`::@ & {target}` resolved to {ancestors}). jj's view of Git "
        f"HEAD was not updated, so the Git repo was not imported."
    )
