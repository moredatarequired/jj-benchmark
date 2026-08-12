"""Verifier for squash_commits.

The task squashes the commit described "add feature B" into its parent
"add feature A", gives the result the description "add feature A and B", and
leaves "add feature C" intact and rebased.

WHERE THE REFERENCE VALUES COME FROM
====================================

The squashed commit is addressed by the change id the BOOTSTRAP gave it, taken
from the anchor (tests/anchor.py) -- a measurement made on the host, from the
untouched image, before the agent ran. This file used to read the list of
descriptions out of `jj log` and check which strings were in it, which is a claim
about text: rewording the three originals and adding a commit described
"add feature A and B" satisfied it while destroying nothing, so the integrity
fixture held too.

Measured on jj 0.38.0: `jj squash --from B --into A` keeps A's change id and
retires B's. So "the squash happened" is exactly: the change the bootstrap
described "add feature A" is still there and now carries the combined
description, and the change it described "add feature B" is gone. Both of those
are recorded in this task's anchor_exemptions.json as expected -- `add feature B`
is named there because its removal is the asked-for work.

In cold CI there is no anchor file -- change ids are random per image build -- and
the description-list check this file used before is the fallback, printing that no
identity claim was made.
"""

import os
import subprocess

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/myproject"

SOURCE = "add feature B"        # squashed away
DESTINATION = "add feature A"   # keeps its change id, gains the new description
COMBINED = "add feature A and B"
DESCENDANT = "add feature C"

# Marker asking the resolver for "nothing", so the test can tell the anchored
# path from the fallback path. It never reaches jj.
NO_ANCHOR = ""

_SNAPSHOTTED = []


def snapshot_once():
    """One deliberate working-copy snapshot per run, then read-only calls only.

    Every jj call this file used to make snapshotted implicitly (a plain jj
    command records the working copy before answering). Doing it once and then
    passing --ignore-working-copy everywhere keeps that behaviour while making
    the reads repeatable.
    """
    if not _SNAPSHOTTED:
        _SNAPSHOTTED.append(subprocess.run(
            ["jj", "status"], cwd=PROJECT_DIR, capture_output=True, text=True))
    return _SNAPSHOTTED[0]


def jj(*args):
    snapshot_once()
    result = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=PROJECT_DIR, capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"`jj {' '.join(args)}` failed ({result.returncode}): {result.stderr.strip()}"
    )
    return result.stdout


def anchored(description):
    return change_id_or_fallback(description, NO_ANCHOR, repo=PROJECT_DIR)


def descriptions_in_log():
    """The description first lines of every visible commit."""
    return [line.strip() for line in jj(
        "log", "-r", "all()", "--no-graph", "-T",
        'description.first_line() ++ "\\n"').splitlines() if line.strip()]


def test_commits_squashed():
    ids = {d: anchored(d) for d in (DESTINATION, SOURCE, DESCENDANT)}
    if not all(ids.values()):
        # No anchor: exactly the check this file made before.
        lines = descriptions_in_log()
        assert COMBINED in lines, f"Exact description {COMBINED!r} not found."
        assert DESCENDANT in lines, f"Exact description {DESCENDANT!r} not found."
        assert DESTINATION not in lines, (
            f"The original commit {DESTINATION!r} is still present.")
        assert SOURCE not in lines, (
            f"The original commit {SOURCE!r} is still present.")
        return

    def described(change_id):
        found = jj("log", "-r", f"present({change_id})", "--no-graph", "-T",
                   'description.first_line() ++ "\\n"').splitlines()
        return [line.strip() for line in found if line.strip()]

    # The squash destination keeps its change id and takes the new description.
    assert described(ids[DESTINATION]) == [COMBINED], (
        f"The commit the bootstrap described {DESTINATION!r} "
        f"({ids[DESTINATION][:12]}) is now described "
        f"{described(ids[DESTINATION])}, expected [{COMBINED!r}]. Requirement 2 "
        "gives the combined commit that description, and a squash into an "
        "existing commit keeps that commit's change id."
    )

    # The squash source is retired by the squash.
    assert described(ids[SOURCE]) == [], (
        f"The commit the bootstrap described {SOURCE!r} ({ids[SOURCE][:12]}) is "
        f"still visible as {described(ids[SOURCE])}. Requirement 1 squashes it "
        "into its parent, which leaves it behind."
    )

    # ...and the descendant is intact, still on top of the combined commit.
    assert described(ids[DESCENDANT]) == [DESCENDANT], (
        f"The commit the bootstrap described {DESCENDANT!r} "
        f"({ids[DESCENDANT][:12]}) is now {described(ids[DESCENDANT])}; "
        "requirement 3 leaves it intact."
    )
    parents = jj("log", "-r", ids[DESCENDANT], "--no-graph", "-T",
                 'parents.map(|p| p.change_id()).join(",") ++ "\\n"').strip()
    assert parents == ids[DESTINATION], (
        f"{DESCENDANT!r} sits on parent change {parents[:12]!r}, expected the "
        f"combined commit ({ids[DESTINATION][:12]}). Requirement 3 has jj rebase "
        "it onto the squash result."
    )


def test_file_contents():
    # Verify that app.py contains all features
    app_py_path = os.path.join(PROJECT_DIR, "app.py")
    with open(app_py_path, "r") as f:
        content = f.read()

    assert "def feature_a(): pass" in content, "feature_a is missing from app.py"
    assert "def feature_b(): pass" in content, "feature_b is missing from app.py"
    assert "def feature_c(): pass" in content, "feature_c is missing from app.py"
