"""Verifier for new_insert.

The task inserts a new commit between the bootstrap's `commit A` and `commit B`,
carrying feature.txt, and lets jj rebase `B` and `C` on top of it.

WHERE THE REFERENCE VALUES COME FROM
====================================

`commit A`, `commit B` and `commit C` are resolved through the BOOTSTRAP ANCHOR
(tests/anchor.py) -- change ids captured on the host from the untouched image,
before the agent ran -- and not by `description("commit A\\n")`. A description is
free text: rewording the three originals and building a parallel
A -> new -> B -> C stack from `root()` satisfied every assertion here, destroyed
nothing (so the integrity fixture in conftest.py held), and scored full marks.

The inserted commit itself has no anchored id -- creating it is the task -- so it is
addressed by its position between two anchored commits: the single commit in
`A..B` that is not `B`. That is also where feature.txt's content is now read from,
instead of off the working-copy disk, which is whatever commit happens to be
checked out.

In cold CI there is no anchor file -- change ids are random per image build -- and
each id falls back to the description revset this file used before, printing that
no identity claim was made.
"""

import os
import subprocess

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/myproject"

FEATURE_CONTENT = "new feature\n"

_SNAPSHOTTED = []


def snapshot_once():
    """One deliberate working-copy snapshot per run, then read-only calls only.

    Every jj call this file used to make snapshotted implicitly; doing it once
    keeps that behaviour and makes the later reads repeatable.
    """
    if not _SNAPSHOTTED:
        _SNAPSHOTTED.append(subprocess.run(
            ["jj", "status"], cwd=PROJECT_DIR, capture_output=True, text=True))
    return _SNAPSHOTTED[0]


def jj(*args, check=True):
    snapshot_once()
    result = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=PROJECT_DIR, capture_output=True, text=True,
    )
    if check:
        assert result.returncode == 0, (
            f"`jj {' '.join(args)}` failed ({result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return result.stdout


def graded(description):
    """A revset naming the BOOTSTRAP's commit described `description`."""
    return change_id_or_fallback(
        description, 'description("' + description + '\\n")', repo=PROJECT_DIR)


def change_ids(revset):
    """Change ids of every commit in `revset`, newest first."""
    return [line.strip() for line in jj(
        "log", "-r", revset, "-T", 'change_id ++ "\\n"', "--no-graph"
    ).splitlines() if line.strip()]


def one_change_id(revset):
    found = change_ids(revset)
    assert len(found) == 1, (
        f"Expected revset {revset!r} to name exactly one commit, got {found}")
    return found[0]


def inserted_commit():
    """The commit inserted between `commit A` and `commit B`.

    `A..B` is the commits after A up to and including B, so removing B leaves
    exactly the inserted one. Addressed by its relation to two anchored commits
    because the agent creates it and it therefore has no anchored id of its own.
    """
    id_a, id_b = graded("commit A"), graded("commit B")
    found = change_ids(f"({id_a}..{id_b}) ~ {id_b}")
    assert len(found) == 1, (
        f"Expected exactly one commit between the bootstrap's 'commit A' and "
        f"'commit B', found {len(found)}: {found}. The new commit has to be "
        "inserted between them, with B and C rebased on top of it."
    )
    return found[0]


def test_feature_file_exists():
    feature_path = os.path.join(PROJECT_DIR, "feature.txt")
    assert os.path.isfile(feature_path), "feature.txt does not exist in the working directory."
    with open(feature_path, "r") as f:
        content = f.read()
    assert content == FEATURE_CONTENT, f"Expected 'new feature\\n', got {repr(content)}"

    # ...and the same file, read at the commit that was inserted between the
    # bootstrap's own A and B rather than off the working-copy disk.
    at_commit = jj("file", "show", "feature.txt", "-r", inserted_commit())
    assert at_commit == FEATURE_CONTENT, (
        f"feature.txt at the inserted commit holds {at_commit!r}, expected "
        f"{FEATURE_CONTENT!r}."
    )


def test_commit_stack_order():
    # The lineage has to be A -> new commit -> B -> C, with B and C the
    # bootstrap's own commits: a rebase preserves their change ids, so they are
    # what identifies them however their commit ids moved.
    id_a = one_change_id(graded("commit A"))
    id_b = one_change_id(graded("commit B"))
    id_c = one_change_id(graded("commit C"))

    lines = change_ids(f"::{id_c}")

    for name, change_id in (("commit A", id_a), ("commit B", id_b), ("commit C", id_c)):
        assert change_id in lines, (
            f"The bootstrap's {name!r} ({change_id[:12]}) is not an ancestor of "
            f"its 'commit C'. Output was: {[c[:12] for c in lines]}"
        )
    idx_a, idx_b, idx_c = lines.index(id_a), lines.index(id_b), lines.index(id_c)

    assert idx_c < idx_b, "'commit C' should be a descendant of 'commit B'"
    assert idx_b < idx_a, "'commit B' should be a descendant of 'commit A'"

    # There should be exactly one commit between A and B
    assert idx_a - idx_b == 2, (
        f"Expected exactly one commit between 'commit A' and 'commit B', but "
        f"found {idx_a - idx_b - 1}."
    )


def test_new_commit_adds_feature_txt():
    # The inserted commit must be the one that introduces feature.txt -- checked
    # against its own diff, not against the whole tree it happens to carry.
    changed = [line.strip() for line in jj(
        "diff", "--name-only", "-r", inserted_commit()).splitlines() if line.strip()]
    assert changed == ["feature.txt"], (
        f"The inserted commit changes {changed}, expected only ['feature.txt']: "
        "it must introduce feature.txt and leave the existing commits' contents "
        "alone."
    )
