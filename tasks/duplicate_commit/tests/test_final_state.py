"""A duplicate has to be a copy of the commit that was there, on the commit that was there.

The scored assertion used to be: some child of the bookmark `feature-b` has a
description containing `Feature A changes`. Two different things get past that.

  * `jj new feature-b -m "Feature A changes"` -- an EMPTY commit. It duplicates
    nothing; only its description says otherwise. (Measured: reward 1.)
  * an additive fabrication: build a parallel `Feature B changes` from `root()`,
    move the `feature-b` bookmark onto it, and put a content-carrying commit on
    top. Nothing is destroyed, so the bootstrap anchor holds, and the verifier
    grades a commit stacked on a commit the task never created. (Measured:
    reward 1.)

Both are closed by asking the question the task actually asks. The parent is
named by the change id the anchor recorded for the bootstrap's own
`Feature B changes` commit rather than by the bookmark, which the agent can move;
and the child has to CARRY the content of the bootstrap's `Feature A changes`
commit -- compared against that commit at verification time rather than against a
literal -- and to introduce it in its own diff.

The duplicate itself is created by the agent, so it has no bootstrap change id.
That is why it is anchored by relation: whose child it is, and whose content it
copies.
"""

import os
import subprocess

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/repo"

# The bootstrap's descriptions for the two commits this task relates, and the
# revsets they fall back to when the anchor cannot supply their change ids -- CI
# always builds cold, and so does any sweep run without
# `scripts/bootstrap_anchor.py --write`. The fallbacks are the bookmarks the old
# assertion went through, so a missing anchor drops the identity claim and leaves
# the rest of the check (real content, real diff) in place;
# change_id_or_fallback() prints a line recording that.
SOURCE = "Feature A changes"
SOURCE_FALLBACK = "feature-a"
DESTINATION = "Feature B changes"
DESTINATION_FALLBACK = "feature-b"


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


def lines(text):
    return [line for line in text.splitlines() if line]


def one(revset):
    found = lines(jj("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\n"'))
    assert len(found) == 1, (
        f"{revset!r} resolves to {len(found)} commit(s) in {PROJECT_DIR}: {found}"
    )
    return found[0]


def test_duplicate_commit_exists_on_feature_b():
    source = one(change_id_or_fallback(SOURCE, SOURCE_FALLBACK, repo=PROJECT_DIR))
    destination = one(
        change_id_or_fallback(DESTINATION, DESTINATION_FALLBACK, repo=PROJECT_DIR)
    )

    children = [
        line.split("\x1f", 1) for line in
        lines(jj("log", "-r", f"children({destination})", "--no-graph",
                 "-T", 'change_id ++ "\x1f" ++ description.first_line() ++ "\n"'))
    ]
    named = [child for child, description in children if SOURCE in description]
    assert named, (
        "No child of the commit this task duplicates onto "
        f"({destination[:12]}, the bootstrap's {DESTINATION!r}) is described "
        f"{SOURCE!r}. Its children are {children}. The duplicated commit was not "
        "found as a child of feature-b."
    )

    # The content the original carries, read off the original at verification
    # time rather than hardcoded, so this asks "the same as that commit" rather
    # than "the same as what the task author typed".
    expected = jj("file", "show", "-r", source, "a.txt")
    failures = []
    for child in named:
        content = subprocess.run(
            ["jj", "--ignore-working-copy", "file", "show", "-r", child, "a.txt"],
            cwd=PROJECT_DIR, capture_output=True, text=True,
        )
        if content.returncode != 0:
            failures.append(
                f"{child[:12]} does not contain a.txt at all "
                f"({content.stderr.strip()}), so it is an EMPTY commit that only "
                "claims to be a duplicate in its description"
            )
            continue
        if content.stdout != expected:
            failures.append(
                f"{child[:12]} holds a.txt = {content.stdout!r} where "
                f"{source[:12]} holds {expected!r}"
            )
            continue
        introduced = lines(jj("diff", "--name-only", "-r", child))
        if "a.txt" not in introduced:
            failures.append(
                f"{child[:12]} does not introduce a.txt in its own diff "
                f"(it changes {introduced}), so it inherited the file rather "
                "than duplicating the commit that adds it"
            )
            continue
        return

    raise AssertionError(
        "A child of %s is described %r, but none of them is a copy of the "
        "bootstrap's %r commit (%s): %s. Duplicating a commit copies its "
        "content, not just its description."
        % (destination[:12], SOURCE, SOURCE, source[:12], "; ".join(failures))
    )


def test_original_feature_a_intact():
    # feature-a should still exist and have its original parent (base)
    result = subprocess.run(
        ["jj", "--ignore-working-copy", "log", "-r", "parents(feature-a)",
         "-T", "bookmarks", "--no-graph"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        check=True
    )
    assert "base" in result.stdout, "The original feature-a commit seems to have been modified or moved."
