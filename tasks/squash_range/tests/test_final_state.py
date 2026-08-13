"""Verifier for the squash_range task.

The task asks for two `fix` commits to be folded into their parent, `feat:
initial structure`. HOW that happens is not graded. One range squash and two
sequential squashes reach a byte-for-byte identical end state, and this file no
longer tries to tell them apart: it used to, via a scored test requiring both
source commits to have stopped being visible in the SAME operation, and that
test has been removed. It graded method rather than outcome -- an agent that
squashed twice produced exactly the history the request asks for and was marked
down for the route it took there.

What survives from the operation-log replay is one assertion, and it is a
FABRICATION DETECTOR rather than a method check: the operation in which the fix
commits finally stopped being visible must also be the operation in which their
content arrived in the target. Without it, hand-editing structure.txt inside the
target and then `jj abandon`-ing both fixes -- no squash anywhere -- produces a
byte-perfect end state and scores full marks. That check cannot fail an honest
solve however many operations it took: one range squash, two sequential squashes
and a squash-undo-retry all put the content and the disappearance in the same
step, because that step IS a squash.

Three deliberate choices:

  * Nothing here reads jj's human-readable operation descriptions. A previous
    task in this benchmark lost all of its signal when jj renamed the "undo"
    operation to "revert"; asserting on `op log` prose is asserting on release
    notes. The signal used instead is structural: which change ids are visible
    at each operation, and what the target commit's file content was there.

  * The four change ids every assertion below is phrased in come from the
    BOOTSTRAP ANCHOR -- a measurement taken from the untouched image before the
    agent ran (see tests/anchor.py) -- and no longer from this repository's own
    operation log. The replay stays, because "were both fixes still visible one
    operation earlier" is a question only the operation log can answer. But a
    replay authenticates a history against ITSELF: a repository that was rebuilt
    and then squashed properly agrees with its own record, which is why the
    reference values have to come from outside the artifact being graded. When
    the anchor is not available -- cold CI builds have no anchor file, by
    construction -- the derivation from this repository's operation log is still
    the fallback, and it says out loud that no identity claim was made.

  * The replay looks only at the *last* transition in which the fix commits
    disappeared, not at the total number of operations, and never at how many
    operations it took. An agent that squashes, undoes, and squashes again is
    graded on the step that stuck. Counting operations was never possible
    anyway: the working-copy snapshot jj adds on an agent's very first command,
    and any further snapshot its file edits produce, make the absolute count
    unpredictable.

NOTHING IN THIS FILE GRADES METHOD
==================================

Every assertion here is about the end state, except the fabrication detector
described above -- and that one is satisfied by every honest route to the end
state, so there is no requirement the agent has to be told beyond "fold the two
fixes into their parent". That is deliberate and it is the point of the change
that removed test_fixes_were_combined_in_a_single_operation: a verifier that can
fail a correct history because of the sequence of commands that produced it is
measuring conformance to an unwritten rubric, not the task.

Every jj call passes --ignore-working-copy so that verification itself never
writes an operation to the repository it is inspecting.
"""

import subprocess
from functools import lru_cache

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/myproject"

# Bootstrap history: root() <- "initial commit" (main) <- TARGET (feature)
#   <- "fix: syntax error" <- "fix: logic error" <- DESCENDANT
ORIGIN = "initial commit"
TARGET = "feat: initial structure"
FIXES = ("fix: syntax error", "fix: logic error")
DESCENDANT = "feat: add more stuff"
ROOT_AND = (ORIGIN, TARGET, DESCENDANT)

# The bootstrap commits every assertion here is phrased in.
GRADED = (ORIGIN, TARGET) + FIXES + (DESCENDANT,)

# What change_id_or_fallback() is asked to return when the anchor cannot supply
# an id. It is a marker, not a revset: it never reaches jj. Its only job is to
# tell bootstrap_change_ids() to use the operation-log derivation instead, which
# is what this file did before the anchor existed.
NO_ANCHOR = ""

# The file both fixes rewrote. "fix: logic error" wrote last, so a target commit
# carrying both fixes ends up with the second fix's content.
SQUASHED_FILE = "structure.txt"
SQUASHED_CONTENT = "logic fixed\n"


def jj(*args, check=True):
    """Run a read-only jj command in the project and return its stdout."""
    result = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )
    if check:
        assert result.returncode == 0, (
            f"`jj {' '.join(args)}` failed with status {result.returncode}: "
            f"{result.stderr.strip()}"
        )
    return result.stdout


def lines(text):
    return [line for line in text.splitlines() if line.strip()]


@lru_cache(maxsize=None)
def operation_ids():
    """Full operation ids, newest first."""
    return tuple(lines(jj("op", "log", "--no-graph", "-T", 'id ++ "\\n"')))


@lru_cache(maxsize=None)
def visible_commits(operation_id):
    """{change_id: first line of description} for commits visible at an operation.

    change_id is a hex-ish string with no spaces, so a single space separates it
    from the description unambiguously, and a first line cannot contain \\n.
    """
    out = jj(
        "log",
        "--at-op",
        operation_id,
        "--no-graph",
        "-r",
        "all()",
        "-T",
        'change_id ++ " " ++ description.first_line() ++ "\\n"',
    )
    commits = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        change_id, _, first_line = line.partition(" ")
        commits[change_id] = first_line
    return commits


@lru_cache(maxsize=None)
def change_ids_from_this_repositorys_own_operation_log():
    """THE FALLBACK ONLY. Recover the change ids from this repo's own op log.

    Scanning oldest-first takes each description from the operation that first
    made such a commit visible, i.e. from the bootstrap -- so it survives an
    agent rewording the commits, which is the reason it was written this way.

    What it cannot do is establish that those commits are the ones the task
    handed over: the operation log it reads belongs to the repository being
    graded, so a repository that was rebuilt and then squashed properly agrees
    with itself here. bootstrap_change_ids() prefers the anchor for exactly that
    reason and only reaches this when there is no anchor to prefer.
    """
    found = {}
    for operation_id in reversed(operation_ids()):
        for change_id, first_line in visible_commits(operation_id).items():
            if first_line in GRADED:
                found.setdefault(first_line, change_id)
        # The bootstrap operations are the oldest ones, so this stops after a
        # dozen operations however many the agent went on to add.
        if len(found) == len(GRADED):
            break
    missing = [d for d in GRADED if d not in found]
    assert not missing, (
        "The operation log has no operation in which commits described "
        f"{missing} were visible. The bootstrap created them, so the "
        "repository's operation log is not the one this task started from."
    )
    return found


@lru_cache(maxsize=None)
def bootstrap_change_ids():
    """Map the bootstrap descriptions to the change ids the BOOTSTRAP gave them.

    A jj change id is generated randomly at commit creation and preserved by
    rebase, squash and describe, so it is the one handle on a bootstrap commit
    that a correct solve keeps and a rebuild cannot reproduce. These come from
    the anchor -- captured on the host from the untouched image, before the agent
    ran -- so every assertion below is about the commits this task handed over
    rather than about whatever now carries the right description.

    In cold CI there is no anchor file (it is a per-build artifact: change ids
    are random per image build, so no committed file could hold them). Then this
    degrades to the operation-log derivation above, which is exactly what this
    verifier did before, and change_id_or_fallback() prints that the identity
    claim was not made.
    """
    anchored = {d: change_id_or_fallback(d, NO_ANCHOR, repo=PROJECT_DIR)
                for d in GRADED}
    if all(anchored.values()):
        return anchored
    return change_ids_from_this_repositorys_own_operation_log()


def file_content(operation_id, change_id, path):
    """Content of `path` in commit `change_id` as of `operation_id`, or None."""
    result = subprocess.run(
        [
            "jj", "--ignore-working-copy", "--at-op", operation_id,
            "file", "show", path, "-r", change_id,
        ],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 else None


def latest():
    return operation_ids()[0]


@lru_cache(maxsize=None)
def root_change_id():
    """The change id of jj's virtual root commit.

    It is visible in `all()` and belongs to no bootstrap description, so it has
    to be named explicitly wherever the visible set is compared against the
    commits the task is about.
    """
    return jj("log", "-r", "root()", "--no-graph",
              "-T", 'change_id ++ "\\n"').strip()


def is_empty(change_id):
    """True when the commit records no change against its parent.

    `empty` is a boolean keyword on every commit in jj's template language, so
    this asks the same question `jj diff --name-only` would without parsing a
    file list.
    """
    out = jj("log", "-r", change_id, "--no-graph", "-T", 'empty ++ "\\n"')
    return out.strip() == "true"


# --------------------------------------------------------------------------
# End state
# --------------------------------------------------------------------------

def test_only_the_expected_commits_remain():
    """The three bootstrap survivors are still here, and nothing else carries work.

    This was `len(visible) == 4` -- the instruction's own "afterwards exactly
    four commits must remain". A count is not what the task is about, and it
    rejected an end state that is correct on the merits: an agent that parks
    itself off the stack first (`jj new -r <descendant>`, the git-shaped habit
    of getting off the commit you are about to rewrite) leaves a fifth, empty
    commit and every real property of the squash intact. Nothing in the request
    speaks against that, so failing it was a false failure -- and the count
    never carried the identity claim anyway, which comes from the change ids.

    What is asserted instead: the three commits that must survive are the
    BOOTSTRAP's own commits, and any additional visible commit must be EMPTY. A
    scratch commit costs nothing; a commit carrying content means work ended up
    somewhere other than the target, which is a reshaped history rather than a
    squash. Together with test_fix_commits_are_no_longer_visible (the two
    sources are gone, by change id) and test_topology_preserved (the survivors
    still sit on each other), this states everything the count did except the
    number.
    """
    ids = bootstrap_change_ids()
    visible = visible_commits(latest())
    absent = [d for d in ROOT_AND if ids[d] not in visible]
    assert not absent, (
        "The commit(s) the bootstrap created and described "
        f"{absent} are no longer visible, so what remains is not the history "
        "this task started from."
    )
    expected = {ids[d] for d in ROOT_AND} | {root_change_id()}
    extra = sorted(set(visible) - expected)
    carrying = [c for c in extra if not is_empty(c)]
    assert not carrying, (
        "Commit(s) other than the root commit, "
        f"{', '.join(repr(d) for d in ROOT_AND)} are still visible and still "
        "carry changes: "
        f"{[(c[:12], visible[c]) for c in carrying]}. The fixes have to be "
        "folded INTO the target commit, so no other commit may be left holding "
        "their content."
    )


def test_fix_commits_are_no_longer_visible():
    """The two source commits are gone -- checked by change id, not by text.

    Squashing folds the source descriptions into the target's, so searching the
    log for the string "fix: syntax error" would flag a *correct* solve. The
    change ids are what identify the commits themselves.
    """
    ids = bootstrap_change_ids()
    visible = visible_commits(latest())
    for description in FIXES:
        change_id = ids[description]
        assert change_id not in visible, (
            f"The commit described {description!r} ({change_id[:12]}) is still a "
            "visible commit, so its changes were not squashed away."
        )


def test_target_commit_survived():
    ids = bootstrap_change_ids()
    visible = visible_commits(latest())
    assert ids[TARGET] in visible, (
        f"The commit described {TARGET!r} ({ids[TARGET][:12]}) is no longer "
        "visible. The fixes must be squashed *into* it, leaving it in the log."
    )
    assert ids[DESCENDANT] in visible, (
        f"The descendant commit described {DESCENDANT!r} is no longer visible; "
        "it must survive the squash."
    )


def test_target_commit_still_described_as_the_target():
    """The instruction names the surviving commit `feat: initial structure`.

    A squash that combines descriptions makes this the first paragraph rather
    than the whole description, and `--use-destination-message` leaves it as the
    whole description; both satisfy a containment check. What it rejects is the
    target's description being replaced outright.
    """
    ids = bootstrap_change_ids()
    description = jj(
        "log", "-r", ids[TARGET], "--no-graph", "-T", "description",
    )
    assert TARGET in description, (
        f"The surviving commit's description is {description!r}, which does not "
        f"mention {TARGET!r}. The instruction requires {TARGET!r} to be one of "
        "the four remaining commits."
    )


def test_target_commit_carries_both_fixes():
    """Both fixes rewrote structure.txt; carrying both means the later content."""
    ids = bootstrap_change_ids()
    content = file_content(latest(), ids[TARGET], SQUASHED_FILE)
    assert content is not None, (
        f"{SQUASHED_FILE} does not exist in the commit described {TARGET!r}."
    )
    assert content == SQUASHED_CONTENT, (
        f"{SQUASHED_FILE} in the commit described {TARGET!r} contains "
        f"{content!r}, expected {SQUASHED_CONTENT!r} -- the squashed commit does "
        "not carry both fixes."
    )


def test_topology_preserved():
    """The squash must not reshape the rest of the history.

    Parents are compared as CHANGE IDS, not as parent descriptions. A
    description is free text: `jj describe` can put "initial commit" on any
    commit, so a fabricated stack carrying the bootstrap's descriptions
    satisfied the description form of this check. A change id cannot be written
    by hand.
    """
    ids = bootstrap_change_ids()
    for description, parent_description in (
        (TARGET, ORIGIN),
        (DESCENDANT, TARGET),
    ):
        change_id, expected = ids[description], ids[parent_description]
        out = jj(
            "log", "-r", change_id, "--no-graph",
            "-T", 'parents.map(|p| p.change_id()).join(",") ++ "\\n"',
        )
        assert out.strip() == expected, (
            f"The bootstrap commit described {description!r} ({change_id[:12]}) "
            f"sits on parent change id(s) {out.strip()[:12]!r}, expected the "
            f"bootstrap commit described {parent_description!r} "
            f"({expected[:12]})."
        )


def test_feature_bookmark_still_points_at_the_target():
    """The `feature` bookmark was not carried forward onto new history.

    Bookmarks follow rewritten commits, so a squash leaves `feature` exactly
    where it was. It used to be asserted that way -- equality with the target --
    which is the one assertion in this file that no bullet of the request ever
    licensed: the instruction does not mention a bookmark at all. It is floored,
    so it earns nothing, and per tests/test.sh a failing floored test still caps
    the trial below a full mark; an agent penalised here would be penalised for
    a requirement it was never given.

    "It is floored" is a MEASUREMENT, and this repository has already been wrong
    about it once, in a way worth writing down because the same mistake silently
    inflates any task's score. `tests/vacuity_floor.json` briefly read 8 tests /
    0 floor, which would have made this test scored. That number came from a
    floor run with a STALE `tests/bootstrap_anchor.json` sitting in the tree: an
    anchor written for an earlier build of the image fails the session-scoped
    fixture in tests/conftest.py, so every test in this file ERRORS before its
    body runs, and "no test passed on the untouched image" is then recorded as a
    floor of zero for the whole task. Re-measured with no stale anchor present,
    the floor is 3 -- this test, test_target_commit_survived and
    test_target_commit_still_described_as_the_target -- which is what CI
    measures too, since CI always builds cold and has no anchor at all. Remove
    tasks/*/tests/bootstrap_anchor.json before running scripts/vacuity_floor.py.

    Relaxed to `feature` pointing at the target OR at an ancestor of it. That
    still rejects the failure this is here for -- a bookmark dragged forward
    onto a fabricated or reshaped head -- while tolerating a bookmark left
    behind, which nothing about the task asks the agent to think about.
    """
    ids = bootstrap_change_ids()
    out = jj("log", "-r", f"feature & ::({ids[TARGET]})", "--no-graph",
             "-T", 'change_id ++ "\\n"')
    assert out.strip(), (
        f"The `feature` bookmark points at "
        f"{jj('log', '-r', 'feature', '--no-graph', '-T', 'change_id').strip()[:12]!r}"
        f", which is neither the commit described {TARGET!r} "
        f"({ids[TARGET][:12]}) nor an ancestor of it."
    )


# --------------------------------------------------------------------------
# Anti-fabrication: the fixes' content moved when the fixes went away
# --------------------------------------------------------------------------

def test_the_operation_that_removed_the_fixes_is_what_moved_the_content():
    """The operation that removed the fixes is the one that carried their changes.

    Without this, an agent could edit structure.txt by hand in the target commit
    and then make both fix commits vanish with `jj abandon`: commits gone,
    correct final content, no squash anywhere. Requiring the content to change
    *in the same operation that removed them* rules that out, because the hand
    edit lands in an earlier operation and leaves the target already holding the
    final content when the fixes disappear.

    This is the only assertion in this file that reads the operation log, and it
    is not a method check. It passes for one range squash (both fixes vanish in
    the squash that carries their content), for two sequential squashes (the
    last one removes the second fix and carries the content that ends up in the
    target), and for a squash-undo-retry (only the step that stuck is examined).
    What it fails is a history in which the content did not travel with the
    commits -- which is not a way of doing the task, it is a way of faking it.
    """
    ids = bootstrap_change_ids()
    fix_ids = {ids[d] for d in FIXES}
    ops = operation_ids()

    index = next(
        (i for i, op in enumerate(ops) if fix_ids & set(visible_commits(op))),
        None,
    )
    assert index is not None, (
        "No operation in the log ever had the fix commits visible, so this is "
        "not the repository the bootstrap created."
    )
    assert index != 0, (
        "The fix commits are still visible at the latest operation: they were "
        "never folded into the target commit."
    )

    before, after = ops[index], ops[index - 1]
    content_before = file_content(before, ids[TARGET], SQUASHED_FILE)
    content_after = file_content(after, ids[TARGET], SQUASHED_FILE)

    assert content_after == SQUASHED_CONTENT, (
        f"After operation {after[:12]} removed the fix commits, {SQUASHED_FILE} "
        f"in the target commit contains {content_before!r} -> {content_after!r}, "
        f"expected {SQUASHED_CONTENT!r}. That operation dropped the fix commits "
        "instead of squashing their changes into the target."
    )
    assert content_before != SQUASHED_CONTENT, (
        f"The target commit already contained the final {SQUASHED_FILE} content "
        f"before operation {after[:12]} removed the fix commits, so that "
        "operation did not move the fixes' changes -- the content got there some "
        "other way."
    )
