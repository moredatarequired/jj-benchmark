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

1. **Every anchored change id still resolves to a visible commit**, unless the
   task's own tests/anchor_exemptions.json says that commit's removal is part of
   the asked-for work. This is the load-bearing check. All four known rebuild
   routes fail it, because every one of them creates fresh commits and therefore
   fresh random change ids. See "THE EXEMPTIONS" below -- the invariant is
   "resolves NOW", not "resolved at some past operation", and that is
   deliberate.

2. **No anchored change id resolves to more than one visible commit**, unless
   the exemption file lists it as `may_be_divergent`. A divergent change is two
   visible commits sharing one change id. Without this, an agent could satisfy
   (1) while ALSO leaving a hand-built duplicate around, and the topology
   assertions downstream would then have two candidates to choose from.

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

   **This check is never exempted.** No exemption in any task's
   anchor_exemptions.json can switch it off, so wipe-and-rebuild is caught on
   every task including the exempted ones.

3b. Operation ids are checked for PRESENCE, never for count or position.
   Operation counts are not a fair assertion: a bootstrap that ends with an
   un-snapshotted file means the agent's very first jj command -- even
   `jj status` -- appends a `snapshot working copy` operation, so totals move
   for reasons that have nothing to do with the solve.

THE EXEMPTIONS, AND THE WEAKER INVARIANT THAT WAS REJECTED
==========================================================

Several jj operations legitimately make a change id stop resolving. Measured on
jj 0.38.0:

  * `jj abandon <id>` -- the change id is gone.
  * `jj squash --from B --into A` -- A keeps its id; B's is gone. Squashing the
    WORKING COPY into an ancestor is the same thing: the emptied source is
    abandoned and a fresh working-copy commit is created with a NEW change id.
  * `jj new` / `jj edit` / `jj prev` / `jj next` moving OFF an empty,
    undescribed working-copy commit to anywhere that is not its descendant --
    jj auto-abandons it, so its change id is gone. (Moving to a CHILD keeps it:
    it is then an ancestor and is still needed.)
  * `jj workspace forget <name>` with an empty working copy -- gone.
  * `jj op restore <older op>` -- every commit created after that operation
    stops resolving.

So on some tasks the CORRECT solve necessarily removes a bootstrap commit:
`abandon_commits` is two abandons, `squash_range`'s own
`test_fix_commits_are_no_longer_visible` asserts those ids are gone, and
`next_prev_navigation` is entirely about walking the working copy off an empty
commit. Without an escape hatch this file would score every one of those solves
0 -- exactly the false-negative class it exists to remove.

The escape hatch is a per-task, hand-written, human-reviewable file at
`/tests/anchor_exemptions.json` (see the SCHEMA below). It names bootstrap
commits whose removal is part of the asked-for work, **with a one-line reason
each**, so the file documents itself and a reviewer can check every entry
against the task's instruction.md. An exempted commit's change id is allowed to
be absent OR present; everything else about the anchor still applies to it.

**The rejected alternative, recorded so nobody proposes it again.** The obvious
fix is to relax (1) from "resolves NOW" to "resolved at the handover operation"
-- and it is WRONG. Operations are append-only, so the pure-jj rebuild route
(`jj new -r 'root()'` + `jj restore --from <rev>`, then `jj abandon` the
originals) leaves the handover operation and all its commits intact *at that
operation*. That route has been observed scoring reward 1.0 in a real sweep. The
weakened invariant passes it. So the strict "resolves NOW" check is kept
everywhere it is safe, and weakened only where a named commit is named, with a
reason, in a committed file.

SCHEMA of /tests/anchor_exemptions.json
=======================================

Optional. Absent means "nothing about this task's asked-for work removes a
bootstrap commit", which is true of most tasks. Hand-written and reviewed
against instruction.md; unlike bootstrap_anchor.json it IS committed, because it
describes the task rather than one image build.

    {
      "task": "operation_recovery",
      "may_disappear": [
        {"description": "Commit 4",
         "reason": "Requirement 2 says nothing described Commit 4 may be visible."},
        {"working_copy": "experiment",
         "reason": "`jj workspace forget experiment` removes that workspace's
                    empty working-copy commit."}
      ],
      "may_be_divergent": [
        {"description": "Feature X - variant 1", "reason": "..."}
      ],
      "maintained_by": "hand-written, reviewed against instruction.md"
    }

An entry names its commit either by `description` (the same key
`anchored_change_id()` uses -- the bootstrap commit's first description line) or
by `working_copy` (a workspace NAME, e.g. "default" or "experiment"), which is
how an UNDESCRIBED working-copy commit is named unambiguously when several
bootstrap commits share the description "".

`reason` is required and must be non-empty. `scripts/lint_tasks.py` enforces the
schema in CI; `scripts/bootstrap_anchor.py --write/--check` cross-checks every
entry against the measured bootstrap, so an entry that names nothing (or names
two things) is reported on the host.

A malformed exemption file, or one whose entries do not resolve against this
image's anchor, makes this module ABSTAIN rather than fail: a stale exemption
file is an infrastructure condition like a stale anchor, and `--check` /
`--verify-untouched` are what make it loud where it can be fixed.

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

TELLING AN ANCHOR FAILURE APART FROM A TASK FAILURE, FROM ctrf.json ALONE
=========================================================================

Every violation message begins with the literal token

    BOOTSTRAP_ANCHOR_VIOLATION

followed by a `codes=` list of the specific checks that failed (see the CODE_*
constants). The fixture raises AssertionError from a session-scoped autouse
fixture, and pytest-json-ctrf records the rendered message in the `trace` field
of EVERY test entry -- measured with the pinned pytest==8.4.1 /
pytest-json-ctrf==0.3.5. So:

    grep -l BOOTSTRAP_ANCHOR_VIOLATION */verifier/ctrf.json

finds every trial that was zeroed by the anchor rather than by the task's own
assertions, with no re-run and without reading test-stdout.txt. That matters
because a MISSED exemption produces a false zero that is otherwise
indistinguishable from a model that simply failed the task.

The token is never printed on the abstain or holds paths, and the raise site
references a function rather than the literal, so a traceback through this
module cannot put the token into a report that did not actually fail.

THE SAFE IDIOM FOR PER-TASK VERIFIERS
=====================================

`anchored_change_id()` and `anchored_working_copy()` raise AnchorUnavailable
when the anchor is absent -- and it IS absent in CI, which always builds cold,
and in any sweep run without `scripts/bootstrap_anchor.py --write`. A verifier
that calls them bare therefore breaks in CI. Every per-task assertion must go
through the fallback resolvers instead:

    from anchor import change_id_or_fallback

    TARGET = change_id_or_fallback("Base", 'description(substring:"Base")',
                                   repo=PROJECT_DIR)
    content = jj("file", "show", "-r", TARGET, "base.txt")

`change_id_or_fallback` returns the anchored change id when the anchor can
supply it, and otherwise returns `fallback` -- the description-based revset the
test used before -- after printing a line that says the identity claim was NOT
made. The assertion is then exactly as strong as it was before the anchor
existed: never weaker, and never an error. `working_copy_or_fallback` is the
same thing for the handover working copy of a workspace.

FAIL-SAFE, ON PURPOSE
=====================

If the anchor file is absent, unparseable, or says `anchored: false` (the tasks
whose bootstrap ships an EMPTY directory -- `working_copy_as_commit`,
`template_formatting`, `git_remote_add`, and `git_integration`, where creating
the repository IS the task), this module ABSTAINS: it reports the reason and
passes. An anchor that is not there is an infrastructure condition, and a
rollout in which a missing file zeroes every trial is worse than the
vulnerability it closes. The `--check` and `--verify-untouched` modes of
scripts/bootstrap_anchor.py are what make a missing or stale anchor loud, and
they run on the host where it can be fixed.

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
EXEMPTIONS_PATH = "/tests/anchor_exemptions.json"

# Ids are stored and compared FULL. Both sides come out of an explicit
# `change_id` / `commit_id` / `id` template with --no-graph, so there is no
# graph glyph to strip and no short-vs-full mismatch to normalise. This matters:
# comparing a short prefix against a full id never matches, which manufactures
# violations, and a glyph-stripping character class containing `x` truncates any
# change id that starts with one (`x` is a legal change-id character -- change
# ids use k-z).
DISPLAY = 12

# The machine-readable marker a human greps out of ctrf.json to tell "the anchor
# zeroed this trial" from "the agent failed the task". Present in the rendered
# AssertionError, and therefore in every test's `trace` field. Never printed on
# the holds or abstain paths.
VIOLATION_TOKEN = "BOOTSTRAP_ANCHOR_VIOLATION"

# One code per distinct check, so `codes=` in the first line of the report says
# WHICH invariant broke without reading the prose. A missed exemption always
# shows up as ANCHOR-CHANGE-ID-MISSING alone; a wipe-and-rebuild brings
# ANCHOR-HANDOVER-OP-GONE (and usually ANCHOR-CHANGE-ID-MISSING) with it, so the
# two are distinguishable at a glance.
CODE_REPO_GONE = "ANCHOR-REPO-GONE"
CODE_REPO_UNREADABLE = "ANCHOR-REPO-UNREADABLE"
CODE_CHANGE_ID_MISSING = "ANCHOR-CHANGE-ID-MISSING"
CODE_CHANGE_ID_DIVERGENT = "ANCHOR-CHANGE-ID-DIVERGENT"
CODE_HANDOVER_OP_GONE = "ANCHOR-HANDOVER-OP-GONE"

# Printed by the fallback resolvers. A verifier that logs this line made its
# assertion by DESCRIPTION, i.e. exactly as strong as before the anchor existed
# -- it did not claim that the commit it graded is the bootstrap's commit.
IDENTITY_NOT_CLAIMED = "anchor unavailable, identity NOT claimed"

DEFAULT_WORKSPACE = "default"


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


def _repos(anchor: dict, repo: str | None, path: str) -> list[dict]:
    repos = anchor["repos"]
    if repo is None:
        return repos
    selected = [r for r in repos if r["path"] == repo]
    if not selected:
        raise AnchorUnavailable(f"{path} records no repository at {repo}")
    return selected


def _working_copies(repo: dict) -> list[dict]:
    """The handover working copy of every workspace of this repository.

    A reserved key, written by scripts/bootstrap_anchor.py from
    `jj workspace list`. It exists because anchor keys are description first
    lines and `""` is not a unique key: workspace_forget's bootstrap holds TWO
    commits described `""` (the default workspace's working copy and the
    experiment workspace's), and restore_file_from_parent, resolve_tool and
    workspace_update_stale have the same problem. A workspace NAME is unique by
    construction, so it is the key that works.
    """
    found = repo.get("working_copies")
    return found if isinstance(found, list) else []


class Exemptions:
    """The per-task, hand-reviewed set of commits whose removal is asked for.

    Resolved to CHANGE IDS at load time against this image's anchor, so
    violations() compares ids and never descriptions -- and so a stale
    exemption file is detected here, once, rather than silently matching
    nothing later.
    """

    def __init__(self) -> None:
        self.may_disappear: dict[str, str] = {}   # change id -> reason
        self.may_be_divergent: dict[str, str] = {}
        self.source = "(none)"

    def __bool__(self) -> bool:
        return bool(self.may_disappear or self.may_be_divergent)

    def describe(self) -> str:
        parts = []
        if self.may_disappear:
            parts.append(
                "%d commit(s) may be absent" % len(self.may_disappear))
        if self.may_be_divergent:
            parts.append(
                "%d commit(s) may be divergent" % len(self.may_be_divergent))
        return ", ".join(parts) or "no exemptions"


def _resolve_entry(entry: dict, anchor: dict, path: str, where: str) -> str:
    """One exemption entry -> the change id it names. Raises on ambiguity."""
    if not isinstance(entry, dict):
        raise AnchorUnavailable(
            f"{path}: {where} contains {entry!r}, which is not an object with a "
            "'description' or 'working_copy' key and a 'reason'"
        )
    reason = entry.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise AnchorUnavailable(
            f"{path}: an entry in {where} has no non-empty 'reason'. Every "
            "exemption has to say, in one line, why the task's asked-for work "
            "removes that commit -- the file is the review record."
        )
    keys = [k for k in ("description", "working_copy") if k in entry]
    if len(keys) != 1:
        raise AnchorUnavailable(
            f"{path}: an entry in {where} must have exactly one of "
            f"'description' or 'working_copy'; this one has {keys or 'neither'}"
        )
    if "working_copy" in entry:
        name = entry["working_copy"]
        matches = [
            wc for repo in anchor["repos"] for wc in _working_copies(repo)
            if wc.get("workspace") == name
        ]
        if len(matches) != 1:
            raise AnchorUnavailable(
                f"{path}: {where} names workspace {name!r}, which matches "
                f"{len(matches)} workspace(s) in the anchor. Either the "
                "bootstrap changed or the anchor predates the working_copies "
                "key; re-run scripts/bootstrap_anchor.py --write."
            )
        return matches[0]["change_id"]

    description = entry["description"]
    matches = [
        commit for repo in anchor["repos"] for commit in repo["commits"]
        if commit["description"] == description
    ]
    if len(matches) != 1:
        raise AnchorUnavailable(
            f"{path}: {where} names the description {description!r}, which "
            f"matches {len(matches)} bootstrap commit(s). An exemption has to "
            "name exactly one commit; use {\"working_copy\": \"<workspace>\"} "
            "for an undescribed working-copy commit."
        )
    return matches[0]["change_id"]


def load_exemptions(anchor: dict, path: str = EXEMPTIONS_PATH) -> Exemptions:
    """The task's exemption file, resolved against this image's anchor.

    An ABSENT file is the normal case and means "no exemptions": most tasks do
    not remove any bootstrap commit. A file that is present but malformed, or
    whose entries do not resolve, raises AnchorUnavailable -- which makes the
    whole check abstain, because a stale exemption file cannot be told apart
    from a stale anchor and both are host-side problems.
    """
    found = Exemptions()
    if not os.path.isfile(path):
        return found
    found.source = path
    try:
        with open(path) as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise AnchorUnavailable(
            f"{path} exists but is not readable JSON ({exc}). It names the "
            "bootstrap commits this task is allowed to remove, so it cannot be "
            "ignored -- fix it on the host."
        ) from exc
    if not isinstance(data, dict):
        raise AnchorUnavailable(f"{path} is not a JSON object")
    for key, target in (("may_disappear", found.may_disappear),
                        ("may_be_divergent", found.may_be_divergent)):
        entries = data.get(key, [])
        if not isinstance(entries, list):
            raise AnchorUnavailable(f"{path}: {key!r} is not a list")
        for entry in entries:
            change_id = _resolve_entry(entry, anchor, path, key)
            target[change_id] = entry["reason"].strip()
    return found


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


def violations(anchor: dict, exemptions: Exemptions | None = None) -> list[str]:
    """Every way this repository is not the one the bootstrap handed over.

    Returns a list of human-readable findings, each prefixed with its CODE_*;
    empty means the anchor holds.
    """
    exempt = exemptions if exemptions is not None else Exemptions()
    found: list[str] = []
    for repo in anchor["repos"]:
        path = repo["path"]
        if not os.path.isdir(os.path.join(path, ".jj")):
            found.append(
                f"[{CODE_REPO_GONE}] {path} is no longer a jj repository (there "
                f"is no {path}/.jj). The bootstrap handed over a jj repository "
                "at that path, so it has been deleted or replaced."
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
                f"[{CODE_REPO_UNREADABLE}] {path} is a jj repository the "
                f"bootstrap created, but jj cannot read it: {exc}. A repository "
                "that has become unreadable is not the repository the task "
                "started from."
            )
            continue

        missing = [
            c for c in repo["commits"]
            if c["change_id"] not in visible
            and c["change_id"] not in exempt.may_disappear
        ]
        if missing:
            found.append(
                "[%s] %s: %d of the %d commit(s) the bootstrap created no "
                "longer exist in this repository. A jj change id is generated "
                "randomly when a commit is created and is PRESERVED by rebase, "
                "squash and describe, so a commit whose change id is gone was "
                "not rewritten -- it was replaced by a different commit that "
                "was created afresh. This repository is not the one the task "
                "started from. Missing: %s. (If one of these is in fact removed "
                "by this task's asked-for work, that is a MISSING EXEMPTION in "
                "%s, not a cheat -- see tests/anchor.py.)"
                % (
                    CODE_CHANGE_ID_MISSING,
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
                    exempt.source,
                )
            )

        duplicated = [
            c for c in repo["commits"]
            if len(visible.get(c["change_id"], ())) > 1
            and c["change_id"] not in exempt.may_be_divergent
        ]
        if duplicated:
            found.append(
                "[%s] %s: anchored change id(s) resolve to more than one "
                "visible commit, i.e. the change is divergent. The bootstrap "
                "created exactly one commit per change id, so a second one was "
                "fabricated rather than the original rewritten. %s"
                % (
                    CODE_CHANGE_ID_DIVERGENT,
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

        # Never exempted, on any task. This is what still catches a
        # wipe-and-rebuild on a task whose commits are all exempt.
        handover = repo.get("handover_operation_id")
        if handover and handover not in operations:
            found.append(
                "[%s] %s: the operation log no longer contains the operation "
                "the bootstrap ended on (%s...). Operations are append-only and "
                "an operation id is a content hash over what the operation did "
                "and when, so nothing an agent does can remove that entry or "
                "reproduce it -- an operation log without it is a NEW operation "
                "log. This repository's history was rebuilt, not edited."
                % (CODE_HANDOVER_OP_GONE, path, handover[:DISPLAY])
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

    Use it as a revset symbol -- but through change_id_or_fallback(), never
    bare, or the verifier breaks in cold CI where there is no anchor file:

        cid = change_id_or_fallback("Base", 'description(substring:"Base")')
        content = jj(repo, "file", "show", "-r", cid, "base.txt")

    Raises AnchorUnavailable (never AssertionError) when the anchor cannot
    supply the id, so a caller can decide whether that is an abstain or a
    failure. In particular it raises -- rather than picking one -- when the
    description does not identify exactly ONE bootstrap commit, which is the
    normal case for the empty description `""`: use anchored_working_copy()
    there instead.
    """
    anchor = load(path)
    matches = [
        (r["path"], c)
        for r in _repos(anchor, repo, path)
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
            "AMBIGUOUS ANCHOR KEY: %s records %d bootstrap commits whose first "
            "description line is %r, so that description does not identify one "
            "commit and this call refuses to pick one of them. They are %s. "
            "Anchor keys are description FIRST LINES, so %r is not a unique key "
            "whenever a bootstrap leaves several undescribed commits (several "
            "workspaces' working copies, or an empty commit under a bookmark). "
            "If you meant a workspace's handover working copy, call "
            "anchored_working_copy(workspace=...) / "
            "working_copy_or_fallback(...) instead; otherwise address the "
            "commit by its relation to a uniquely described neighbour."
            % (
                path,
                len(matches),
                description,
                ", ".join(
                    "%s in %s" % (commit["change_id"][:DISPLAY], repo_path)
                    for repo_path, commit in matches
                ),
                description,
            )
        )
    return matches[0][1]["change_id"]


def anchored_working_copy(workspace: str = DEFAULT_WORKSPACE,
                          path: str = ANCHOR_PATH,
                          repo: str | None = None) -> str:
    """The change id of `@` in `workspace` at the HANDOVER operation.

    The reserved key that makes an undescribed working-copy commit addressable.
    Anchor keys are description first lines, so `""` is not a unique key: it
    identifies two commits in workspace_forget's bootstrap, three in
    resolve_tool's, and two in restore_file_from_parent's and
    workspace_update_stale's. A workspace name is unique by construction.

    `workspace` is the jj workspace NAME as `jj workspace list` prints it --
    "default" for a repository that never had `jj workspace add` run in it.
    """
    anchor = load(path)
    matches = [
        (r["path"], wc)
        for r in _repos(anchor, repo, path)
        for wc in _working_copies(r)
        if wc.get("workspace") == workspace
    ]
    if not matches:
        known = sorted(
            wc.get("workspace", "?")
            for r in _repos(anchor, repo, path)
            for wc in _working_copies(r)
        )
        raise AnchorUnavailable(
            f"{path} records no workspace named {workspace!r}"
            + (f" (it knows: {', '.join(known)})" if known else
               " and records no working copies at all, so it predates the "
               "working_copies key; re-run scripts/bootstrap_anchor.py --write")
        )
    if len(matches) > 1:
        raise AnchorUnavailable(
            f"{path} records {len(matches)} workspaces named {workspace!r}, "
            "which cannot happen in one repository; pass repo= to choose one."
        )
    return matches[0][1]["change_id"]


def change_id_or_fallback(description: str, fallback: str,
                          path: str = ANCHOR_PATH,
                          repo: str | None = None) -> str:
    """The bootstrap's change id for `description`, or `fallback`.

    THE IDIOM EVERY PER-TASK VERIFIER MUST USE. The anchor is a per-sweep build
    artifact: it is gitignored, absent in CI (which always builds cold) and
    absent in any sweep run without `scripts/bootstrap_anchor.py --write`. When
    it is not there the identity claim cannot be made, so this abstains from it
    and returns the description-based revset the test used before. The assertion
    is then exactly as strong as it was -- never weaker, and never an error.

    Calling anchored_change_id() bare instead makes the test raise
    AnchorUnavailable in cold CI, which is a broken verifier rather than a
    weaker one.
    """
    try:
        return anchored_change_id(description, path=path, repo=repo)
    except AnchorUnavailable as exc:
        print("%s: resolving %r by description instead (%s)"
              % (IDENTITY_NOT_CLAIMED, description, exc))
        return fallback


def working_copy_or_fallback(fallback: str,
                             workspace: str = DEFAULT_WORKSPACE,
                             path: str = ANCHOR_PATH,
                             repo: str | None = None) -> str:
    """The handover `@` of `workspace`, or `fallback`. See change_id_or_fallback."""
    try:
        return anchored_working_copy(workspace=workspace, path=path, repo=repo)
    except AnchorUnavailable as exc:
        print("%s: resolving the %s workspace's working copy positionally "
              "instead (%s)" % (IDENTITY_NOT_CLAIMED, workspace, exc))
        return fallback


def _codes(found: list[str]) -> list[str]:
    order = (
        CODE_REPO_GONE, CODE_REPO_UNREADABLE, CODE_CHANGE_ID_MISSING,
        CODE_CHANGE_ID_DIVERGENT, CODE_HANDOVER_OP_GONE,
    )
    return [code for code in order if any(f"[{code}]" in f for f in found)]


def _violation_report(anchor: dict, found: list[str], exempt: Exemptions) -> str:
    """The AssertionError text. Machine-greppable first line, prose after."""
    return (
        "%s codes=%s task=%s\n\n"
        "THE REPOSITORY BEING GRADED IS NOT THE ONE THE BOOTSTRAP HANDED "
        "OVER.\n\n"
        % (VIOLATION_TOKEN, ",".join(_codes(found)) or "-",
           anchor.get("task") or "?")
        + "\n\n".join(f"  * {finding}" for finding in found)
        + "\n\nThe anchor was captured from the untouched task image before "
        "the agent ran (see scripts/bootstrap_anchor.py) and records the "
        "change id of every bootstrap commit plus the id of the last "
        "operation the bootstrap performed. Nothing a correct solve does "
        "can break it -- rebase, squash-into-an-existing-commit, describe and "
        "restore all preserve change ids, the operation log is append-only, "
        "and any commit this task's asked-for work legitimately removes is "
        "named with a reason in tests/anchor_exemptions.json (%s). A failure "
        "here means either that the repository was recreated rather than worked "
        "on, or that an exemption is missing -- and the first line above says "
        "which checks broke."
        % exempt.describe()
    )


def assert_bootstrap_anchor(path: str = ANCHOR_PATH,
                            exemptions_path: str = EXEMPTIONS_PATH) -> str:
    """Raise AssertionError if this is not the repository the task started from.

    Returns a one-line note on the abstain paths so a caller can surface why
    nothing was checked.
    """
    try:
        anchor = load(path)
        exempt = load_exemptions(anchor, exemptions_path)
        found = violations(anchor, exempt)
    except AnchorUnavailable as exc:
        return f"bootstrap anchor not evaluated: {exc}"

    if found:
        raise AssertionError(_violation_report(anchor, found, exempt))
    return "bootstrap anchor holds" + (
        f" ({exempt.describe()} per {exempt.source})" if exempt else ""
    )
