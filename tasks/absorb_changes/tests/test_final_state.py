import os
import subprocess
import pytest

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
# the commit described "Initial commit" and the feature_b.py fix in the commit
# described "Add feature A" -- confirmed against jj 0.38.0, which reports
# exactly those two revisions as the ones it absorbed into. Naming the target by
# description rather than by position keeps the check stable if the agent leaves
# an extra empty commit behind.
#
# (path, marker the fix introduces, description of the commit that must receive it)
ABSORB_TARGETS = (
    ("feature_a.py", "Feature A fixed", "Initial commit"),
    ("feature_b.py", "Feature B fixed", "Add feature A"),
)


def _jj(*args):
    """Run jj in the task project and return the CompletedProcess."""
    return subprocess.run(
        ["jj", *args], capture_output=True, text=True, cwd=PROJECT_DIR
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
    """The single commit whose description is exactly `description`.

    A bare string in `description()` is a glob, not an exact match, and jj
    appends a trailing newline to every description -- so the pattern kind and
    the newline are both spelled out here rather than left to the default.
    """
    return _one_commit_id(f'description(exact:"{description}\\n")')


def _changed_paths(revset):
    """Paths in a revision's own diff against its parent."""
    return _lines(_jj("diff", "-r", revset, "--name-only"), f"diff -r {revset}")


def _file_content(revset, path):
    result = _jj("file", "show", "-r", revset, path)
    assert result.returncode == 0, f"'jj file show -r {revset} {path}' failed: {result.stderr}"
    return result.stdout


def _assert_absorbed(path, marker, target_description):
    """The fix to `path` must live in the commit described `target_description`.

    Three assertions, all structural: that commit's own diff touches `path`,
    its content carries the fix, and nothing between it and the working copy
    touches `path` again. The last one is what rejects a working copy that was
    simply squashed wholesale into its parent -- there the fix sits in one
    commit for both files instead of in the ancestor that last modified each.
    """
    target = _rev_of_description(target_description)

    assert path in _changed_paths(target), (
        f"The commit described {target_description!r} ({target}) does not modify {path}; "
        f"its diff touches {_changed_paths(target)}. The {path} fix was not absorbed "
        "into the ancestor that last modified it."
    )
    assert marker in _file_content(target, path), (
        f"{path} at the commit described {target_description!r} ({target}) does not "
        f"contain {marker!r}; it contains:\n{_file_content(target, path)}"
    )
    stragglers = _commit_ids(f'{target}..@ & files(root-file:"{path}")')
    assert not stragglers, (
        f"{path} is still modified by {len(stragglers)} commit(s) after the commit "
        f"described {target_description!r}: {stragglers}. The fix has not been "
        f"absorbed into the ancestor that last modified {path}."
    )


def test_working_copy_empty():
    """The working copy must carry no changes once the fixes have been absorbed.

    Asked structurally: the `empty` template keyword and the working copy's own
    diff, rather than matching jj's English "The working copy has no changes".
    """
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
    apart from a plain squash. It now checks placement.
    """
    _assert_absorbed(*ABSORB_TARGETS[0])


def test_feature_b_absorbed():
    """The feature_b.py fix must land in the ancestor that last modified it.

    The old version of this test passed on the untouched image: it read
    feature_b.py at the commit described "Add feature B", which *is* the working
    copy holding the un-absorbed fix, so "Feature B fixed" was there before the
    operation as well as after. It asserted nothing.

    See ABSORB_TARGETS for why the commit that must receive this fix is the one
    described "Add feature A".
    """
    _assert_absorbed(*ABSORB_TARGETS[1])
