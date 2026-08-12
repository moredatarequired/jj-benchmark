"""Assert that the repository being graded is the one the bootstrap handed over.

Read scripts/bootstrap_anchor.py's module docstring first; it explains what the
anchor is and why it has to be captured on the host.

The short version. A jj **change id** is generated RANDOMLY when a commit is
created, and is preserved by a genuine `jj rebase` / `jj squash` / `jj describe`.
It is therefore the one property of a bootstrap commit that survives every
legitimate solve and that a rebuilt repository cannot reproduce -- whether it
was rebuilt with `rm -rf .git .jj` + `git init` + `jj git init`, with raw git
plumbing (`hash-object` / `mktree` / `commit-tree` / `update-ref`), or with the
pure-jj route `jj new -r 'root()'` + `jj restore --from <rev>` that no
command blocklist can see. Commit ids are content-derived and so forgeable in
principle; descriptions are attacker-writable free text. Only the change id and
the operation log carry identity.

WHAT IT ASSERTS, AND WHY EACH ONE
=================================

1. **Every anchored change id still resolves to a visible commit.** This is the
   load-bearing check. All four known rebuild routes fail it, because every one
   of them creates fresh commits and therefore fresh random change ids.

2. **No anchored change id resolves to more than one visible commit.** A
   divergent change is two visible commits sharing one change id. Without this,
   an agent could satisfy (1) while ALSO leaving a hand-built duplicate around,
   and the topology assertions downstream would then have two candidates to
   choose from. It also gives a clear message for the legitimate-looking case
   (`concurrent_operations` deliberately produces divergence, so that task's
   verifier is the one place this may need relaxing).

3. **The handover operation id is still present in the operation log.** This is
   evidence about the op log itself rather than about commits: a rebuilt repo
   has a brand-new op log, and op ids are content hashes over the operation's
   contents and timestamps, so it cannot contain the bootstrap's newest
   operation. It closes the one gap (1) leaves open -- an attacker who somehow
   preserved the commits but replaced the op log -- and it is the check that
   makes `jj op restore`-based fabrication visible.

   Deliberately NOT the *earliest* operation: that is jj's root operation and
   is identical in every repository ever created, exactly like the all-zeros
   root commit.

3b. Operation ids are checked for PRESENCE, never for count or position.
   Operation counts are not a fair assertion: a bootstrap that ends with an
   un-snapshotted file means the agent's very first jj command -- even
   `jj status` -- appends a `snapshot working copy` operation, so totals move
   for reasons that have nothing to do with the solve.

WHAT IT DELIBERATELY DOES NOT ASSERT
====================================

* **Commit ids.** A genuine `jj rebase`, `squash`, `describe`, `abandon` or
  `restore` rewrites commit ids by design while preserving change ids -- that
  asymmetry is the whole point. Asserting commit ids would fail every correct
  solve. They are in the anchor file for diagnosis only, and this module reports
  them in failure messages so a human can see what moved.

* **Descriptions.** `describe_commit` and `edit_commit_message` exist to change
  them.

* **That the anchored commits are all that is visible.** Solving a task creates
  commits.

FAIL-SAFE, ON PURPOSE
=====================

If the anchor file is absent, unparseable, or says `anchored: false` (the three
tasks whose bootstrap ships an EMPTY directory -- `working_copy_as_commit`,
`template_formatting`, `git_remote_add` -- where creating the repo IS the task),
this module ABSTAINS: it reports the reason and passes. An anchor that is not
there is an infrastructure condition, and a rollout in which a missing file
zeroes every trial is worse than the vulnerability it closes. The
`--check` mode of scripts/bootstrap_anchor.py is what makes a missing or stale
anchor loud, and it runs on the host where it can be fixed.

Never raise at import time. A conftest.py that raises while being imported makes
pytest exit 4 having reported ZERO tests, and tests/test.sh then classifies the
whole trial as unscorable -> `verifier_error.txt` -> ERRORED-INFRA, which is
exactly the WRONG verdict for a cheat. Every failure path here goes through a
fixture body or an explicit call, so pytest always reports one entry per test.
"""

from __future__ import annotations

import json
import os
import subprocess

ANCHOR_PATH = "/tests/bootstrap_anchor.json"

# Ids are stored and compared FULL. Both sides come out of an explicit
# `change_id` / `commit_id` / `id` template with --no-graph, so there is no
# graph glyph to strip and no short-vs-full mismatch to normalise. This matters:
# comparing a short prefix against a full id never matches, which manufactures
# violations, and a glyph-stripping character class containing `x` truncates any
# change id that starts with one (`x` is a legal change-id character -- change
# ids use k-z).
DISPLAY = 12


class AnchorUnavailable(Exception):
    """The anchor cannot be evaluated. Not a verdict about the repository."""


def _jj(cwd: str, *args: str) -> str:
    """Run a read-only jj command.

    --ignore-working-copy on EVERY call, without exception. A plain jj read
    snapshots the working copy first, which appends an operation and creates a
    new version of @ -- so a verifier without it mutates the repository it is
    grading, and can disagree with its own second run.
    """
    proc = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AnchorUnavailable(
            "`jj %s` failed in %s (exit %d): %s"
            % (" ".join(args), cwd, proc.returncode, proc.stderr.strip()[-400:])
        )
    return proc.stdout


def load(path: str = ANCHOR_PATH) -> dict:
    """The anchor, or AnchorUnavailable with a reason a human can act on."""
    if not os.path.isfile(path):
        raise AnchorUnavailable(
            f"there is no {path}. It is produced by "
            "`scripts/bootstrap_anchor.py --write` on the host and arrives on "
            "the read-only /tests mount; without it this verifier cannot tell a "
            "solved repository from a rebuilt one."
        )
    try:
        with open(path) as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise AnchorUnavailable(f"{path} is not readable JSON ({exc})") from exc
    if not isinstance(data, dict) or "repos" not in data:
        raise AnchorUnavailable(f"{path} is not a bootstrap anchor document")
    if not data.get("anchored"):
        raise AnchorUnavailable(
            f"{path} records anchored=false: this task's bootstrap ships no jj "
            "repository, so there is no bootstrap identity to preserve and "
            "nothing to check."
        )
    return data


def _visible_change_ids(repo: str) -> dict[str, list[dict]]:
    """change_id -> the visible commits carrying it, from ONE jj call.

    One call rather than one revset lookup per anchored id: resolving an id that
    is GONE makes jj exit non-zero, which would have to be told apart from jj
    being broken, and a divergent id resolves to several commits which a
    per-id lookup would quietly collapse. Reading the whole visible set and
    comparing in Python has neither problem.

    `all() ~ root()` excludes jj's root commit, which is the all-zeros virtual
    commit (change id z*32) present in every repository ever created and so
    carries no identity at all.
    """
    template = (
        'change_id ++ "\x1f" ++ commit_id ++ "\x1f" '
        '++ description.first_line() ++ "\n"'
    )
    found: dict[str, list[dict]] = {}
    for line in _jj(repo, "log", "-r", "all() ~ root()", "--no-graph",
                    "-T", template).splitlines():
        if not line:
            continue
        parts = line.split("\x1f")
        if len(parts) < 3:
            raise AnchorUnavailable(f"unparseable jj log line {line!r} in {repo}")
        found.setdefault(parts[0], []).append(
            {"commit_id": parts[1], "description": "\x1f".join(parts[2:])}
        )
    return found


def _operation_ids(repo: str) -> set[str]:
    return {
        line.strip()
        for line in _jj(repo, "op", "log", "--no-graph", "-T", 'id ++ "\n"').splitlines()
        if line.strip()
    }


def violations(anchor: dict) -> list[str]:
    """Every way this repository is not the one the bootstrap handed over.

    Returns a list of human-readable findings; empty means the anchor holds.
    """
    found: list[str] = []
    for repo in anchor["repos"]:
        path = repo["path"]
        if not os.path.isdir(os.path.join(path, ".jj")):
            found.append(
                f"{path} is no longer a jj repository (there is no {path}/.jj). "
                "The bootstrap handed over a jj repository at that path, so it "
                "has been deleted or replaced."
            )
            continue

        # A jj failure INSIDE a repository the anchor says exists is a finding,
        # not an abstain. Abstaining here would hand an agent a way out: corrupt
        # the store until jj errors and the integrity check declines to answer.
        # (The task's own assertions would fail too, but the check must not be
        # the thing that gives way.)
        try:
            visible = _visible_change_ids(path)
            operations = _operation_ids(path)
        except AnchorUnavailable as exc:
            found.append(
                f"{path} is a jj repository the bootstrap created, but jj cannot "
                f"read it: {exc}. A repository that has become unreadable is not "
                "the repository the task started from."
            )
            continue

        missing = [c for c in repo["commits"] if c["change_id"] not in visible]
        if missing:
            found.append(
                "%s: %d of the %d commit(s) the bootstrap created no longer "
                "exist in this repository. A jj change id is generated randomly "
                "when a commit is created and is PRESERVED by rebase, squash and "
                "describe, so a commit whose change id is gone was not rewritten "
                "-- it was replaced by a different commit that was created "
                "afresh. This repository is not the one the task started from. "
                "Missing: %s"
                % (
                    path,
                    len(missing),
                    len(repo["commits"]),
                    "; ".join(
                        "the commit described %r carried change id %s "
                        "(commit id %s at bootstrap) and nothing visible carries "
                        "that change id now"
                        % (
                            c["description"],
                            c["change_id"][:DISPLAY],
                            c["commit_id"][:DISPLAY],
                        )
                        for c in missing
                    ),
                )
            )

        duplicated = [
            c for c in repo["commits"] if len(visible.get(c["change_id"], ())) > 1
        ]
        if duplicated:
            found.append(
                "%s: anchored change id(s) resolve to more than one visible "
                "commit, i.e. the change is divergent. The bootstrap created "
                "exactly one commit per change id, so a second one was "
                "fabricated rather than the original rewritten. %s"
                % (
                    path,
                    "; ".join(
                        "change id %s (described %r at bootstrap) now resolves to "
                        "%d commits: %s"
                        % (
                            c["change_id"][:DISPLAY],
                            c["description"],
                            len(visible[c["change_id"]]),
                            ", ".join(
                                v["commit_id"][:DISPLAY]
                                for v in visible[c["change_id"]]
                            ),
                        )
                        for c in duplicated
                    ),
                )
            )

        handover = repo.get("handover_operation_id")
        if handover and handover not in operations:
            found.append(
                "%s: the operation log no longer contains the operation the "
                "bootstrap ended on (%s...). Operations are append-only and an "
                "operation id is a content hash over what the operation did and "
                "when, so nothing an agent does can remove that entry or "
                "reproduce it -- an operation log without it is a NEW operation "
                "log. This repository's history was rebuilt, not edited."
                % (path, handover[:DISPLAY])
            )
    return found


def anchored_change_id(description: str, path: str = ANCHOR_PATH,
                       repo: str | None = None) -> str:
    """The change id the BOOTSTRAP gave the commit with this description line.

    This is the primitive a verifier needs in order to stop resolving graded
    commits by `description(substring:...)`. A description is free text the
    agent can write; the anchored change id came off the untouched image before
    the agent ran, so a revset built on it addresses THE bootstrap commit and
    not merely something that looks like it.

    Why that matters even when assert_bootstrap_anchor() passes: the anchor is a
    NECESSARY condition, not a sufficient one. It proves the bootstrap commits
    still exist -- it does not prove they are the commits the verifier graded.
    Measured on history_rewriting: an agent that builds a fabricated stack from
    `root()` and leaves the ORIGINAL stack untouched beside it satisfies the
    anchor (every anchored id is still visible) and still passes a verifier
    that greps `jj log` output or resolves by description. Addressing the graded
    commit by its anchored change id is what closes that.

    Use it as a revset symbol:

        cid = anchored_change_id("Base")
        content = jj(repo, "file", "show", "-r", cid, "base.txt")

    Raises AnchorUnavailable (never AssertionError) when the anchor cannot
    supply the id, so a caller can decide whether that is an abstain or a
    failure.
    """
    anchor = load(path)
    repos = anchor["repos"]
    if repo is not None:
        repos = [r for r in repos if r["path"] == repo]
        if not repos:
            raise AnchorUnavailable(f"{path} records no repository at {repo}")
    matches = [
        (r["path"], c)
        for r in repos
        for c in r["commits"]
        if c["description"] == description
    ]
    if not matches:
        raise AnchorUnavailable(
            f"{path} records no bootstrap commit whose first description line is "
            f"{description!r}. Either the Dockerfile changed or the anchor is "
            "stale; re-run scripts/bootstrap_anchor.py --write."
        )
    if len(matches) > 1:
        raise AnchorUnavailable(
            f"{path} records {len(matches)} bootstrap commits described "
            f"{description!r}, so the description does not identify one commit. "
            "Anchor this assertion on the change id directly."
        )
    return matches[0][1]["change_id"]


def assert_bootstrap_anchor(path: str = ANCHOR_PATH) -> str:
    """Raise AssertionError if this is not the repository the task started from.

    Returns a one-line note on the abstain paths so a caller can surface why
    nothing was checked.
    """
    try:
        anchor = load(path)
        found = violations(anchor)
    except AnchorUnavailable as exc:
        return f"bootstrap anchor not evaluated: {exc}"

    if found:
        raise AssertionError(
            "THE REPOSITORY BEING GRADED IS NOT THE ONE THE BOOTSTRAP HANDED "
            "OVER.\n\n"
            + "\n\n".join(f"  * {finding}" for finding in found)
            + "\n\nThe anchor was captured from the untouched task image before "
            "the agent ran (see scripts/bootstrap_anchor.py) and records the "
            "change id of every bootstrap commit plus the id of the last "
            "operation the bootstrap performed. Nothing a correct solve does "
            "can break it: rebase, squash, describe, abandon and restore all "
            "preserve change ids, and the operation log is append-only. A "
            "failure here means the repository was recreated rather than "
            "worked on."
        )
    return "bootstrap anchor holds"
