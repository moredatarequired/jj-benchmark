"""Verifier for commit_splitting.

The task splits the commit described `Combined changes` into two sequential
commits: `Modify fileA` carrying only the fileA.txt change, then `Modify fileB`
carrying only the fileB.txt change.

WHERE THE REFERENCE VALUES COME FROM
====================================

The two commits are located by their position relative to the BOOTSTRAP's own
`Base commit`, and the split is required to have actually consumed the
bootstrap's own `Combined changes` -- both addressed by anchored change ids
(tests/anchor.py), captured on the host from the untouched image before the agent
ran.

This file used to resolve them with `description("Modify fileA*")` globs. That is
a claim about text: two new commits with those descriptions and one-file diffs,
plus a reword of the original, satisfied every assertion here while destroying
nothing -- so the integrity fixture held as well.

Deliberately agnostic about WHICH half keeps the original change id. Measured on
jj 0.38.0, the non-interactive `jj split -r X <paths>` gives it to the older half;
the interactive and `--insert-after`/`--insert-before` forms are not measured. So
the requirement is that exactly one of the two commits carries it, which is true
of every faithful split and false of a fabrication.

In cold CI there is no anchor file -- change ids are random per image build -- and
each resolver falls back to the description revset, printing that no identity
claim was made.
"""

import subprocess

from anchor import change_id_or_fallback

PROJECT_DIR = "/home/user/project"

BASE = "Base commit"
ORIGINAL = "Combined changes"
FIRST = "Modify fileA"
SECOND = "Modify fileB"

# Marker asking the resolver for "nothing", so a caller can tell the anchored
# path from the fallback path. It never reaches jj.
NO_ANCHOR = ""

_SNAPSHOTTED = []


def snapshot_once():
    """One deliberate working-copy snapshot per run, then read-only calls only.

    Every jj call this file used to make snapshotted implicitly; doing it once
    keeps that behaviour and makes every later read repeatable.
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


def glob(description):
    return f'description("{description}*")'


def lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def field(revset, template):
    return lines(jj("log", "-r", revset, "--no-graph", "-T",
                    template + ' ++ "\\n"'))


def split_commits():
    """(first, second) as change ids: the child of `Base commit`, then its child.

    Falls back to the description globs when there is no anchor, which is what
    this file resolved before.
    """
    base = anchored(BASE)
    if not base:
        first = field(glob(FIRST), "change_id")
        second = field(glob(SECOND), "change_id")
        assert len(first) == 1, (
            f"Expected exactly one commit described {FIRST!r}, got {first}")
        assert len(second) == 1, (
            f"Expected exactly one commit described {SECOND!r}, got {second}")
        return first, second
    first = field(f"children({base})", "change_id")
    assert len(first) == 1, (
        f"The bootstrap's {BASE!r} ({base[:12]}) has {len(first)} child "
        f"commit(s), expected exactly one -- the first half of the split: {first}"
    )
    second = field(f"children({first[0]})", "change_id")
    assert len(second) == 1, (
        f"The first commit on top of {BASE!r} has {len(second)} child "
        f"commit(s), expected exactly one -- the second half of the split: "
        f"{second}"
    )
    return first, second


def assert_the_split_consumed_the_original(first, second):
    """Exactly one of the two split commits must BE the bootstrap's commit.

    A split rewrites the original commit; it does not leave it standing beside
    the results. This is the assertion an additive fabrication cannot satisfy,
    and it is repeated in both scored tests on purpose: partial credit is
    per-test, so a check that lives in only one of them still pays half.
    """
    original = anchored(ORIGINAL)
    if not original:
        return
    carriers = [c for c in first + second if c == original]
    assert len(carriers) == 1, (
        f"Neither of the two commits on top of {BASE!r} is the commit the "
        f"bootstrap described {ORIGINAL!r} (change {original[:12]}); they are "
        f"{[c[:12] for c in first + second]}. Splitting a commit rewrites it into "
        "the halves, so one of them has to be it. Commits that merely carry the "
        "right descriptions are not a split of that commit."
    )


def test_combined_commit_absent():
    """No commit is described `Combined changes` any more.

    Plus: the bootstrap's own commit by that name must now be described as one of
    the halves, rather than being reworded and left whole.
    """
    assert ORIGINAL not in field("all()", "description.first_line()"), (
        f"Expected {ORIGINAL!r} commit to be split and removed."
    )

    original = anchored(ORIGINAL)
    if not original:
        return
    described = field(f"present({original})", "description.first_line()")
    assert described in ([FIRST], [SECOND]), (
        f"The commit the bootstrap described {ORIGINAL!r} ({original[:12]}) is "
        f"now described {described}, expected [{FIRST!r}] or [{SECOND!r}]. The "
        "split rewrites that commit into the two halves."
    )


def test_modify_fileA_commit_exists_and_contains_fileA():
    first, second = split_commits()
    assert_the_split_consumed_the_original(first, second)

    described = field(f"present({first[0]})", "description.first_line()")
    assert described == [FIRST], (
        f"The first commit on top of {BASE!r} is described {described}, expected "
        f"[{FIRST!r}]."
    )
    changed = sorted(lines(jj("diff", "--name-only", "-r", first[0])))
    assert changed == ["fileA.txt"], (
        f"The first commit of the split changes {changed}, expected only "
        "['fileA.txt']."
    )


def test_modify_fileB_commit_exists_and_contains_fileB():
    first, second = split_commits()
    assert_the_split_consumed_the_original(first, second)

    described = field(f"present({second[0]})", "description.first_line()")
    assert described == [SECOND], (
        f"The second commit of the split is described {described}, expected "
        f"[{SECOND!r}]."
    )
    changed = sorted(lines(jj("diff", "--name-only", "-r", second[0])))
    assert changed == ["fileB.txt"], (
        f"The second commit of the split changes {changed}, expected only "
        "['fileB.txt']."
    )
