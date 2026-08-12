"""Verifier for obslog_view.

The task asks for the complete evolution of the working-copy change -- every
commit that change has ever pointed to -- written to /home/user/obslog.txt.
This verifier recomputes that evolution from the repository itself and requires
the saved report to account for every version, so a file that merely contains
the right words cannot pass.

Two deliberate design choices:

  * Format-agnostic. A correct answer may render the evolution as a graph or as
    a flat list, colourised or not, abbreviated or full IDs. So the assertions
    are on the invariants of any faithful rendering -- the commit ID and
    description of each version -- never on layout, and ANSI escapes are
    stripped before matching (jj colours the unique prefix of a commit ID
    differently from the rest, which splits the ID in the raw bytes).

  * `evolog`, not the deprecated `obslog` alias. What the *agent* used is not
    inspected and either name is fine, but the verifier's own calls must not
    depend on an alias a future jj release can drop.

WHICH CHANGE'S EVOLUTION
========================

The evolution is read at the change the BOOTSTRAP handed over, addressed by its
anchored change id (tests/anchor.py), not at whatever `@` happens to be. A bare
`jj evolog` asks about the working copy, so `jj new -r 'root()' -m x;
jj describe -m y; jj evolog > /home/user/obslog.txt` produced a change with two
versions and a report that faithfully described it -- destroying nothing, so the
integrity fixture held, and passing every assertion here. Naming the bootstrap's
own change is what makes the report be about the change the task is about.

In cold CI there is no anchor file (change ids are random per image build, so it
cannot be a committed constant) and the resolver falls back to `@`, printing that
no identity claim was made.
"""

import os
import re
import subprocess

from anchor import change_id_or_fallback

REPO_DIR = "/home/user/repo"

# The bootstrap's working-copy change, by its description first line. The
# bootstrap describes it "v1" and then "v2", so "v2" is the description the
# anchor recorded and it names exactly one commit.
GRADED_CHANGE = "v2"
REPORT_FILE = "/home/user/obslog.txt"

# Any CSI escape sequence, which covers the SGR colour codes jj emits.
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

# jj abbreviates commit IDs to 8 hex characters by default, and a full ID has
# that as its prefix, so 8 characters is what the report is required to carry.
ID_PREFIX_LEN = 8

# Separator between the two template fields. NUL cannot occur in a description,
# and it has to reach jj as the two-character escape -- a real NUL byte cannot be
# passed in an argv element.
FIELD_SEP = "\x00"
EVOLOG_TEMPLATE = (
    r'commit.commit_id() ++ "\0" ++ commit.description().first_line() ++ "\n"'
)


def jj(*args):
    """Run jj in the task repo and return stdout, failing the test on error.

    `--ignore-working-copy` keeps every call read-only: jj otherwise snapshots
    the working copy first, which would let the check mutate the very state it
    is inspecting (and make a second run see something different from the
    first).
    """
    result = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"`jj {' '.join(args)}` failed with status {result.returncode}: "
        f"{result.stderr.strip()}"
    )
    return result.stdout


def graded_change():
    """The bootstrap's working-copy change, as a revset."""
    return change_id_or_fallback(GRADED_CHANGE, "@", repo=REPO_DIR)


def evolution():
    """[(commit_id, description_first_line)] for the bootstrap's change.

    Newest version first, read straight out of the repository -- at the anchored
    change id, so it is the evolution of the change the task handed over.
    """
    out = jj("evolog", "-r", graded_change(), "--no-graph", "--color=never",
             "-T", EVOLOG_TEMPLATE)
    entries = []
    for line in out.splitlines():
        if not line:
            continue
        commit_id, _, description = line.partition(FIELD_SEP)
        entries.append((commit_id, description))
    return entries


def report_text():
    """The saved report with colour codes removed."""
    assert os.path.isfile(REPORT_FILE), (
        f"Expected the evolution report at {REPORT_FILE}, but no such file exists."
    )
    with open(REPORT_FILE, encoding="utf-8", errors="replace") as handle:
        return ANSI_RE.sub("", handle.read())


def test_report_file_exists():
    """There is a report, and it is a report about the bootstrap's change.

    Existence and non-emptiness on their own are satisfied by any file at all,
    which left a third of this task's credit collectable by a report of a
    fabricated change. So it also has to identify the current version of the
    anchored change -- the one thing every faithful rendering contains, and the
    weakest claim that is still about the right change.
    """
    assert os.path.isfile(REPORT_FILE), (
        f"Expected the evolution report at {REPORT_FILE}, but no such file exists."
    )
    assert os.path.getsize(REPORT_FILE) > 0, f"{REPORT_FILE} is empty."

    entries = evolution()
    assert entries, (
        "The repository's graded change has no versions at all, so the "
        "repository is not in its expected starting shape."
    )
    newest = entries[0][0]
    assert newest[:ID_PREFIX_LEN] in report_text(), (
        f"{REPORT_FILE} does not mention {newest[:ID_PREFIX_LEN]}, the commit "
        f"the bootstrap's own change points at now. The report has to be about "
        f"that change; a report about some other change is not this task."
    )


def test_report_covers_every_version_of_the_change():
    """Every commit in the change's evolution must be identified in the report.

    This is the assertion the task turns on: the IDs are computed here rather
    than hardcoded, and there are several of them, most belonging to versions
    that are hidden from the ordinary log -- so they cannot be produced without
    actually reading the change's evolution.
    """
    entries = evolution()
    assert len(entries) >= 2, (
        "The repository's working-copy change has fewer than two versions, so "
        "the repository is not in its expected starting shape."
    )

    text = report_text()
    missing = [
        commit_id for commit_id, _ in entries
        if commit_id[:ID_PREFIX_LEN] not in text
    ]
    assert not missing, (
        f"{REPORT_FILE} does not account for "
        f"{len(missing)} of the {len(entries)} versions of the working-copy "
        f"change. Missing commit IDs: {', '.join(i[:ID_PREFIX_LEN] for i in missing)}. "
        "The report must cover the change's whole evolution, not just its "
        "current version. (If the repository was changed after the report was "
        "written, the change gained versions the report cannot contain; see "
        "test_repository_left_unchanged.)"
    )


def test_report_carries_each_version_description():
    """The descriptions the change has carried must appear in the report."""
    text = report_text()
    descriptions = sorted({d for _, d in evolution() if d})
    missing = [d for d in descriptions if d not in text]
    assert not missing, (
        f"{REPORT_FILE} is missing the description(s) {missing} that versions "
        "of the working-copy change carry."
    )


def test_repository_left_unchanged():
    """The change and its history must be left as they were found.

    The check above is what protects the report's completeness; these are the
    stated end-state conditions, checked structurally so that a repository that
    was rewritten instead of merely read fails with a clear reason.
    """
    content = jj("file", "show", "-r", "@", "file.txt")
    assert content == "v2\n", (
        f"file.txt should still contain {'v2'!r}, but the working-copy commit "
        f"has {content!r}. The repository was modified."
    )

    description = jj("log", "-r", "@", "--no-graph", "-T", "description").strip()
    assert description == "v2", (
        f"The working-copy commit's description should still be 'v2', but it is "
        f"{description!r}. The repository was modified."
    )

    visible = [line for line in jj(
        "log", "-r", "all()", "--no-graph", "-T", '"c\\n"'
    ).splitlines() if line]
    assert len(visible) == 2, (
        f"The repository should still hold just the working-copy commit and the "
        f"root commit, but {len(visible)} commits are visible. New commits were "
        "created."
    )
