"""Verifier for the absorb_changes task.

WHAT CHANGED, AND WHY
=====================

_rev_of_description() resolved each absorb target with
`description(exact:"...")`, i.e. by attacker-writable text. An agent could
redescribe the bootstrap's commits (a `jj describe` preserves change ids, so the
session-scoped anchor fixture still holds), then fabricate a parallel stack from
`root()` whose commits carry the original descriptions AND the two fixes, and
destroy nothing. Measured: reward 1.

Each target is now resolved by the change id the BOOTSTRAP gave it, so "the
ancestor that last modified this file" means a specific commit the task handed
over rather than any commit currently wearing its description. The
description-based revset is kept as the FALLBACK, because bootstrap_anchor.json
is a per-build artifact -- gitignored, and absent in CI, which always builds cold
-- and when it is missing anchor.py's resolver prints that the identity claim is
NOT being made and hands the old revset back. The assertion is then exactly as
strong as it was before.

test_working_copy_empty is anchored by RELATION rather than by identity: this
task's tests/anchor_exemptions.json records that the handover `@` legitimately
disappears on the per-file `jj squash --into` route, so `@` cannot be required to
BE that change. It is instead required to be a descendant of the bootstrap's own
"Add feature A" commit, which both solve routes satisfy and a stack fabricated
from `root()` does not.

Test names and count are unchanged, so tests/vacuity_floor.json does not move.
"""

import os
import subprocess
import pytest

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/project"

# Where each working-copy fix has to end up.
#
# The bootstrap builds the stack with `jj new -m <message>` *before* writing the
# file, so every description is one commit ahead of the change it labels:
#
#   (no description)      adds feature_a.py and feature_b.py
#   "Initial commit"      last modified feature_a.py  -> print('Feature A')
#   "Add feature A"       last modified feature_b.py  -> print('Feature B')
#   "Add feature B"  (@)  holds both uncommitted fixes
#
# Distributing the working-copy changes to "the nearest mutable ancestors where
# the lines were last modified" therefore means the feature_a.py fix belongs in
# the commit the bootstrap described "Initial commit" and the feature_b.py fix in
# the commit it described "Add feature A" -- confirmed against jj 0.38.0, which
# reports exactly those two revisions as the ones it absorbed into. The
# descriptions below are ANCHOR KEYS, i.e. the description each commit had at
# handover; the commit is then addressed by its change id, not by whatever
# description it wears at grading time.
#
# (path, marker the fix introduces, handover description of the receiving commit)
ABSORB_TARGETS = (
    ("feature_a.py", "Feature A fixed", "Initial commit"),
    ("feature_b.py", "Feature B fixed", "Add feature A"),
)

_snapshotted = False


def _snapshot_working_copy():
    """Take the ONE working-copy snapshot this verifier is allowed, explicitly.

    The bootstrap writes both fixes without snapshotting them, so `@`'s STORED
    tree is empty on the untouched image and only reflects the checked-out files
    once jj snapshots. Every jj call below passes --ignore-working-copy, or the
    verifier would mutate the repository it is grading and could disagree with
    its own second run -- so the snapshot is taken here, once, deliberately. It
    preserves change ids and so cannot disturb the anchor, and it is the same
    single snapshot this file used to take implicitly on its first jj call.
    """
    global _snapshotted
    if not _snapshotted:
        subprocess.run(["jj", "status"], cwd=PROJECT_DIR,
                       capture_output=True, text=True)
        _snapshotted = True


def _jj(*args):
    """Run read-only jj in the task project and return the CompletedProcess."""
    return subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        capture_output=True, text=True, cwd=PROJECT_DIR,
    )


def _lines(result, what):
    assert result.returncode == 0, f"'jj {what}' failed: {result.stderr}"
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _commit_ids(revset):
    """Full commit ids for `revset`, newest first.

    --no-graph with an explicit template is the only shape of `jj log` worth
    parsing; the default graph output elides commits. A bare newline is
    whitespace in jj's template language, so the separator has to be an
    explicit "\\n" concatenated onto the value.
    """
    return _lines(
        _jj("log", "-r", revset, "--no-graph", "-T", 'commit_id ++ "\\n"'),
        f"log -r {revset}",
    )


def _one_commit_id(revset):
    ids = _commit_ids(revset)
    assert len(ids) == 1, f"Expected revset '{revset}' to name exactly 1 commit, got {ids}"
    return ids[0]


def _rev_of_description(description):
    """The change id the BOOTSTRAP gave the commit described `description`.

    Falls back to the old revset -- `description(exact:...)`, with the pattern
    kind and jj's trailing newline both spelled out, because a bare string is a
    glob -- when there is no anchor file to consult.
    """
    return change_id_or_fallback(
        description, f'description(exact:"{description}\\n")', repo=PROJECT_DIR)


def _changed_paths(revset):
    """Paths in a revision's own diff against its parent."""
    return _lines(_jj("diff", "-r", revset, "--name-only"), f"diff -r {revset}")


def _file_content(revset, path):
    result = _jj("file", "show", "-r", revset, path)
    assert result.returncode == 0, f"'jj file show -r {revset} {path}' failed: {result.stderr}"
    return result.stdout


def _assert_absorbed(path, marker, target_description):
    """The fix to `path` must live in the commit the bootstrap described so.

    Three assertions, all structural: that commit's own diff touches `path`,
    its content carries the fix, and nothing between it and the working copy
    touches `path` again. The last one is what rejects a working copy that was
    simply squashed wholesale into its parent -- there the fix sits in one
    commit for both files instead of in the ancestor that last modified each.
    """
    _snapshot_working_copy()
    target = _rev_of_description(target_description)
    assert _commit_ids(target), (
        f"The commit the bootstrap described {target_description!r} ({target}) "
        "does not resolve."
    )

    assert path in _changed_paths(target), (
        f"The commit the bootstrap described {target_description!r} ({target}) does "
        f"not modify {path}; its diff touches {_changed_paths(target)}. The {path} "
        "fix was not absorbed into the ancestor that last modified it."
    )
    assert marker in _file_content(target, path), (
        f"{path} at the commit the bootstrap described {target_description!r} "
        f"({target}) does not contain {marker!r}; it contains:\n"
        f"{_file_content(target, path)}"
    )
    stragglers = _commit_ids(f'{target}..@ & files(root-file:"{path}")')
    assert not stragglers, (
        f"{path} is still modified by {len(stragglers)} commit(s) after the commit "
        f"the bootstrap described {target_description!r}: {stragglers}. The fix has "
        f"not been absorbed into the ancestor that last modified {path}."
    )


def test_working_copy_empty():
    """The working copy must carry no changes once the fixes have been absorbed.

    Asked structurally: the `empty` template keyword and the working copy's own
    diff, rather than matching jj's English "The working copy has no changes".

    The working copy is anchored by RELATION, not identity: `jj absorb` keeps the
    handover `@`, but the per-file `jj squash --into` route empties it and jj
    abandons an emptied squash source, so tests/anchor_exemptions.json allows it
    to disappear. What both routes DO guarantee is that `@` ends up at or above
    the bootstrap's own "Add feature A" commit -- which a stack fabricated from
    `root()` cannot.
    """
    _snapshot_working_copy()
    above = _rev_of_description("Add feature A")
    assert _commit_ids(f"descendants({above}) & @"), (
        f"`@` is not the bootstrap's own 'Add feature A' commit ({above}) nor a "
        "descendant of it, so the working copy whose changes were supposedly "
        "distributed is not the one the task handed over."
    )

    assert _lines(
        _jj("log", "-r", "@", "--no-graph", "-T", 'empty ++ "\\n"'), "log -r @"
    ) == ["true"], "The working copy commit (@) is not empty; it still has changes."
    changed = _changed_paths("@")
    assert not changed, f"The working copy (@) still has changes to: {changed}"


def test_feature_a_absorbed():
    """The feature_a.py fix must land in the ancestor that last modified it.

    The old version only checked that feature_a.py *reads* "Feature A fixed" at
    the commit described "Add feature A". Because `jj file show` shows the whole
    tree at a revision, not that revision's own diff, squashing the working copy
    straight into its parent satisfied that too -- so it could not tell absorb
    apart from a plain squash. It now checks placement, in the commit the
    BOOTSTRAP created.
    """
    _assert_absorbed(*ABSORB_TARGETS[0])


def test_feature_b_absorbed():
    """The feature_b.py fix must land in the ancestor that last modified it.

    The old version of this test passed on the untouched image: it read
    feature_b.py at the commit described "Add feature B", which *is* the working
    copy holding the un-absorbed fix, so "Feature B fixed" was there before the
    operation as well as after. It asserted nothing.

    See ABSORB_TARGETS for why the commit that must receive this fix is the one
    the bootstrap described "Add feature A".
    """
    _assert_absorbed(*ABSORB_TARGETS[1])
