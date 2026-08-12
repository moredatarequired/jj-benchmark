"""The commit has to be built on the work the other workspace produced.

All three assertions used to be about a state that can be reached without ever
picking up the other workspace's commit: `jj st` runs, a file on disk has the
right JSON in it, and `@-` has a description containing `Activate config`. So an
agent could clear the stale flag, start a fresh commit from `root()`, write the
expected JSON by hand and commit that -- an additive fabrication that removes
nothing, so the bootstrap anchor holds and the verifier grades the fabricated
commit (measured: reward 1).

What the task is actually about is the commit the OTHER workspace rebased this
workspace's working copy onto. The anchor records the handover working copy of
every workspace by name (see tests/anchor.py), so that commit is nameable even
though it is undescribed -- `""` identifies two commits in this bootstrap and so
identifies nothing. Every test below therefore also asserts that the commit it is
looking at descends from (or is) that working copy.

Descends-from rather than is-exactly, because both routes an agent plausibly takes
are correct: editing the updated working copy and running `jj commit` describes
that very change, while `jj new` first puts the description on a child of it.
"""

import os
import subprocess
import json
import pytest

from anchor import working_copy_or_fallback

PROJECT_DIR = "/home/user/myproject"

# The revset the handover working copy is resolved by when the anchor cannot
# supply its change id -- CI always builds cold, and so does any sweep run without
# `scripts/bootstrap_anchor.py --write`. `@-` makes each ancestry claim below
# trivially true, so a missing anchor leaves every assertion exactly as strong as
# it was before the anchor existed; working_copy_or_fallback() prints a line
# recording that the identity claim was not made.
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


def handover_working_copy():
    """The change id this workspace's working copy sat on at handover."""
    revset = working_copy_or_fallback(WC_FALLBACK, workspace="default",
                                     repo=PROJECT_DIR)
    found = change_ids(revset)
    assert len(found) == 1, (
        f"{revset!r} resolves to {len(found)} commit(s) in {PROJECT_DIR}: {found}"
    )
    return found[0]


def assert_descends_from_the_handover(revset, what):
    """THE anchored claim: `revset` is, or descends from, the handover working copy."""
    handover = handover_working_copy()
    found = change_ids(f"{handover} & ::({revset})")
    assert found == [handover], (
        f"{what} does not descend from {handover[:12]}, the commit this "
        "workspace's working copy was sitting on when the task was handed over. "
        "That commit is where the other workspace's `update config` work landed, "
        "so anything built somewhere else in the repository is not this task's "
        "work -- it is a parallel history that only looks like it."
    )


def test_no_stale_error():
    result = subprocess.run(["jj", "st"], cwd=PROJECT_DIR, capture_output=True, text=True)
    assert result.returncode == 0, f"Expected 'jj st' to succeed, but it failed with: {result.stderr}"
    assert "stale" not in result.stderr.lower(), "The working copy is still stale."
    assert_descends_from_the_handover("@", "the working copy")


def test_config_json_content():
    config_path = os.path.join(PROJECT_DIR, "config.json")
    assert os.path.isfile(config_path), f"Config file {config_path} is missing."
    with open(config_path) as f:
        content = json.load(f)
    assert content.get("status") == "active", "Expected 'status' to be 'active' in config.json."
    assert content.get("new") is True, "Expected 'new' to be true in config.json (should be preserved from workspace_b)."

    assert_descends_from_the_handover("@-", "the committed change")
    committed = json.loads(jj("file", "show", "-r", "@-", "config.json"))
    assert committed.get("status") == "active", (
        f"config.json is right on disk but the committed copy at @- says "
        f"{committed!r}; the change was not committed."
    )
    assert committed.get("new") is True, (
        f"The committed config.json at @- is {committed!r}: the `new` field the "
        "other workspace added was not preserved."
    )


def test_commit_message():
    result = subprocess.run(["jj", "--ignore-working-copy", "log", "-T", "description", "-r", "@-",
                             "--no-graph"], cwd=PROJECT_DIR, capture_output=True, text=True)
    assert result.returncode == 0, "Failed to run 'jj log'"
    assert "Activate config" in result.stdout, "Expected commit message to contain 'Activate config'."
    assert_descends_from_the_handover("@-", "the commit described 'Activate config'")
