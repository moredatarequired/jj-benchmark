#!/usr/bin/env python3
"""Capture -- never hand-write -- the bootstrap integrity anchor of every task.

WHAT THIS IS FOR
================

A jj-benchmark verifier grades whatever repository it finds at the task's
project path. Almost none of them check that it is *the repository the
bootstrap handed to the agent*. An agent that deletes the repo and rebuilds a
plausible-looking history by hand currently scores the same as one that did the
task, and four distinct routes to that have been observed in real sweeps --
including a pure-jj one (`jj new -r 'root()'` + `jj restore --from <rev>`), so
no blocklist of commands can close it.

The one invariant that all four routes break is the **change id**. jj generates
change ids RANDOMLY at commit creation and preserves them across a genuine
`rebase` / `squash` / `describe`; a rebuild cannot reproduce them. Commit ids
are content-derived (tree + parents + description + author/committer identity
and timestamp) and are therefore forgeable in principle, so they are recorded
here for diagnosis but are NOT what the assertion rests on.

So this script records, per task, for the *untouched bootstrap image*:

  * every visible non-root commit's change_id / commit_id / first description
    line, per repository found under /home/user;
  * the NEWEST operation id as of bootstrap -- the "handover op". Operations
    are append-only, so nothing the agent does can land before it, and op ids
    are content hashes including timestamps, so a rebuilt op log cannot
    reproduce one. (Deliberately NOT the *earliest* op: that is jj's root
    operation and carries no per-repo identity, exactly like the all-zeros
    root commit.)
  * `working_copies`: the handover `@` of EVERY workspace of the repository,
    keyed by workspace NAME. This is a reserved key and it exists because the
    commit keys are description first lines, and `""` is not a unique key --
    workspace_update_stale's bootstrap holds two commits described `""`, and
    before the cut to 14 tasks there were bootstraps holding three. A workspace
    name is unique by construction, so
    `anchored_working_copy(workspace="experiment")` can name a commit that
    `anchored_change_id("")` cannot, and an exemption entry can too.

It also *reads* one hand-written file per task, `tests/anchor_exemptions.json`
(optional), and cross-checks it against the measurement: every entry must name
exactly one bootstrap commit or one workspace, and must carry a reason. That
file is what lets a task whose asked-for work removes a bootstrap commit
(`abandon_commits`, `squash_range`, ...) still score. See tests/anchor.py for
the schema and for why the alternative -- relaxing the invariant to "resolved at
the handover operation" -- is unsound.

The measurement runs in a throwaway container of the built image and the result
is written on the HOST, into tasks/<task>/tests/bootstrap_anchor.json. That
placement is the load-bearing part: harbor mounts the whole tests/ directory
read-only at /tests, so the anchor arrives beside the verifier for free, the
same way vacuity_floor.json does -- while NOTHING is added to the image. No
Dockerfile changes, and no copy of the anchor exists inside the container for
the agent to read or rewrite. (Every task image runs as root -- not one
Dockerfile has a USER directive except the two ubuntu:22.04 ones -- so
anything baked into the image is agent-rewritable and would be worthless.)

THE ONE THING TO UNDERSTAND BEFORE RUNNING THIS
===============================================

**An anchor describes an IMAGE BUILD, not a Dockerfile.** Change ids are
random, so two builds of the same Dockerfile produce different ones (measured:
same bootstrap replayed twice gives completely disjoint change ids). Docker's
layer cache is what makes the anchor stable in practice -- rebuild with a warm
cache and the bootstrap layer is reused byte for byte, so the ids do not move.

Consequences, and they are not optional:

  * `--write` must run against the SAME image the sweep will use, and nothing
    may prune or `--no-cache` rebuild in between. This is the same class of
    operational constraint as the CA-patched base tags.
  * The anchor records a sha256 of the task's whole build context. `--check`
    re-measures and uses that to separate "the ids moved because the bootstrap
    layer was rebuilt from a cold cache" (staleness -- re-run --write) from "the
    ids moved because the Dockerfile's bootstrap changed" (a real change to
    review). It deliberately does NOT compare docker image ids: MEASURED,
    buildx mints a new image id on every build even when every layer is a cache
    hit and the change ids are byte-identical, so an image-id comparison cries
    wolf on every single run.
  * A missing or stale anchor must make the verifier's anchor assertion
    ABSTAIN, never fail. See tests/anchor.py: an anchor that cannot be trusted
    is an infrastructure condition, and turning it into a task failure would
    zero every trial the moment a cache got evicted.

`JJ_RANDOMNESS_SEED` is not an escape from this. Measured on jj 0.38.0: with
the seed set, every commit created by a separate `jj` invocation gets the
*same* change id (the seed is per-process, not a stream), which is worse than
random.

Because the anchor describes a build and not a Dockerfile, the file it writes is
**gitignored** (`tasks/*/tests/bootstrap_anchor.json`) and is deliberately NOT
in scripts/lint_tasks.py's REQUIRED_FILES. A committed anchor would be wrong for
every build except the one that produced it, and CI always builds cold, so it
would fail permanently.

THE PRE-SWEEP PROCEDURE -- follow it in this order
==================================================

The failure this ordering exists to prevent is a *catastrophic false negative*:
if a sweep runs against an image built cold AFTER the anchor was written, every
anchored change id is missing, the fixture fails in every trial, and the whole
sweep scores 0 while looking like a total model collapse rather than an
infrastructure fault.

    1. python3 scripts/bootstrap_anchor.py --write             # same docker daemon
    2. python3 scripts/bootstrap_anchor.py --check             # must be clean
    3. python3 scripts/bootstrap_anchor.py --verify-untouched  # pre-flight, see below
    4. harbor run ...                                          # the sweep

Between step 1 and step 4: **do not prune, do not `--no-cache`, do not build on
a different docker daemon, and do not `docker rmi` the task images.** Anything
that evicts a bootstrap layer re-randomises that task's change ids and silently
invalidates its anchor. Deleting the anchor file is always safe -- the verifier
abstains -- while a STALE anchor is the dangerous state, which is exactly what
`--check` and `--verify-untouched` are for.

`--verify-untouched` is the strongest of the three because it is an end-to-end
rehearsal rather than a comparison: for each task it builds the image, mounts the
real `tasks/<task>/tests` directory read-only at /tests exactly as harbor and CI
do, runs the real `tests/test.sh`, and asserts three things at once:

  * the anchor fixture reported that it HOLDS (so the anchor matches this image,
    and it did not silently abstain because the file was missing);
  * `reward.txt` says `0` -- the same vacuity property .github/workflows/tasks.yml
    asserts, i.e. the verifier still refuses to pay an agent that did nothing;
  * a `ctrf.json` was written and `test.sh` exited 0 -- so the run is a scorable
    verdict and not the ERRORED-INFRA path.

Because the anchor HOLDS on the untouched image is asserted rather than merely
"did not fail", `--verify-untouched` is also what catches a stale
`tests/anchor_exemptions.json`: an exemption entry that no longer resolves makes
tests/anchor.py abstain, and an abstain is reported as a problem.

For the three tasks whose bootstrap ships an empty directory it asserts the
opposite anchor verdict -- an explicit `anchored=false` abstain -- so "this task
has no repository" stays distinguishable from "the anchor was never generated".

CLI, deliberately shaped like scripts/vacuity_floor.py
======================================================

    scripts/bootstrap_anchor.py --write                    # all tasks, 4 at a time
    scripts/bootstrap_anchor.py --write --task rebase_branch
    scripts/bootstrap_anchor.py --check --jobs 4
    scripts/bootstrap_anchor.py --verify-untouched --jobs 4
    scripts/bootstrap_anchor.py --write --task squash_range --keep-images

Pure stdlib. Requires a working docker daemon.
"""

from __future__ import annotations

import argparse
import json
import os
import hashlib
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks"

ANCHOR_NAME = "bootstrap_anchor.json"

# Written by scripts/bootstrap_anchor.py, read by tests/anchor.py. Kept in this
# order so the file is diff-stable across regenerations.
ANCHOR_KEYS = (
    "task", "anchored", "jj_version", "environment_sha256", "image_id",
    "repos", "generated_by",
)
REPO_KEYS = ("path", "handover_operation_id", "operations", "working_copies",
             "commits")
COMMIT_KEYS = ("change_id", "commit_id", "description", "bookmarks")
WORKING_COPY_KEYS = ("workspace", "path", "change_id", "commit_id")
GENERATED_BY = "scripts/bootstrap_anchor.py"

# Hand-written, committed, and read by tests/anchor.py at verification time.
# Unlike the anchor it describes the TASK rather than one image build, so it is
# not gitignored. This script only cross-checks it.
EXEMPTIONS_NAME = "anchor_exemptions.json"
EXEMPTION_LISTS = ("may_disappear", "may_be_divergent")

# The three verdicts tests/anchor.py can reach, as they appear in the verifier's
# own output. --verify-untouched reads them out of tests/test.sh's stdout rather
# than re-implementing the check on the host: the point of a pre-flight is to
# exercise the code path the sweep will actually take, and a second host-side
# implementation could agree with the anchor while the container's disagreed.
# pytest attaches a session fixture's stdout to the first test's report and
# tests/test.sh always passes -rA, so the note is present whether the tests
# passed or failed (verified in a real container, both ways).
#
# Matched per LINE and anchored at its start, never as a substring of the whole
# output. pytest echoes the source of anchor.py in a traceback, so a bare
# substring search finds the string literal `return f"bootstrap anchor not
# evaluated: {exc}"` and reports an ABSTAIN for a run that actually FAILED --
# measured, and it is the difference between "you forgot to run --write" and
# "your anchor does not match this image".
ANCHOR_HOLDS = "bootstrap anchor holds"
ANCHOR_ABSTAINED = "bootstrap anchor not evaluated"
# The token tests/anchor.py puts at the front of the AssertionError, which is
# also what a human greps out of ctrf.json to tell an anchor failure from a task
# failure. anchor.py's raise site references a function rather than this literal,
# so a traceback through that module cannot forge it.
ANCHOR_FAILED = "BOOTSTRAP_ANCHOR_VIOLATION"

# Ids are stored FULL -- 32 chars for a change id, 40 for a commit id, 128 for
# an operation id -- and compared full-to-full, because both sides of every
# comparison are produced by this file's explicit templates. Storing a prefix
# would import the whole full-vs-short false-positive class for nothing: an
# 8-char prefix compared against a 32-char id never matches, and that mistake
# alone fabricated 18 false positives in an earlier audit.
#
# DISPLAY_PREFIX is used ONLY in human-readable messages. 12 rather than 8
# because jj's own abbreviated ids are length-adaptive: 8 is what `jj log`
# happens to print for a small repo and gets longer as the repo grows, so a
# hardcoded 8 reads like a real id while silently being a different thing.
# Nothing ever compares on it.
DISPLAY_PREFIX = 12

# Change ids use only the letters k-z. Never strip "graph glyphs" from jj
# output with a character class containing `x` -- `x` is a legal change-id
# character and such a class eats the first character of any id starting with
# one. Every jj call below passes --no-graph so there are no glyphs at all.
CHANGE_ID_ALPHABET = set("klmnopqrstuvwxyz")

# Field separator for the log template. \x1f (ASCII unit separator) cannot
# occur in a commit description line, which a tab or a space can.
SEP = "\x1f"

# The capture program, run inside a throwaway container of the built image.
#
# Every jj call passes --ignore-working-copy. Without it a plain jj read
# snapshots the working copy first, which would append an operation and create
# a new version of @ -- i.e. the measurement would change the thing it is
# measuring, and the handover op id it recorded would be the id of its own
# snapshot. (Measured elsewhere: ops 12 -> 13, evolog 1 -> 2 on one plain
# `jj log`.) That matters more here than in a verifier: this runs on the
# pristine image.
CAPTURE = r'''
import json, os, subprocess, sys

SEP = "\x1f"
HOME = "/home/user"


def jj(cwd, *args):
    proc = subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=cwd, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "jj %s failed in %s (exit %d): %s"
            % (" ".join(args), cwd, proc.returncode, proc.stderr.strip()[-500:])
        )
    return proc.stdout


def workspace_roots():
    """Every jj workspace root under /home/user, two levels deep."""
    found = []
    if not os.path.isdir(HOME):
        return found
    for name in sorted(os.listdir(HOME)):
        top = os.path.join(HOME, name)
        if not os.path.isdir(top):
            continue
        if os.path.exists(os.path.join(top, ".jj")):
            found.append(top)
            continue
        try:
            children = sorted(os.listdir(top))
        except OSError:
            continue
        for child in children:
            deeper = os.path.join(top, child)
            if os.path.isdir(deeper) and os.path.exists(os.path.join(deeper, ".jj")):
                found.append(deeper)
    return found


def store_key(root):
    """Identity of the underlying repo, so two workspaces of one repo dedupe.

    An added workspace's .jj/repo is a FILE holding the path of the primary
    workspace's .jj/repo; the primary's is a directory. Resolving that
    indirection is what makes workspace_update_stale (two roots, one repo)
    record one anchor instead of two identical ones.
    """
    repo = os.path.join(root, ".jj", "repo")
    if os.path.isfile(repo):
        with open(repo) as handle:
            target = handle.read().strip()
        if not os.path.isabs(target):
            target = os.path.join(root, ".jj", target)
        return os.path.realpath(target)
    return os.path.realpath(repo)


def working_copies(root, roots):
    """The handover @ of every workspace of this repository, by workspace NAME.

    From ONE `jj workspace list` in any workspace of the repo, which is the
    authoritative source for the names: a workspace name is unique within a
    repository, which is exactly the property the description keys lack (`""`
    identifies two commits in workspace_update_stale's bootstrap).

    `jj workspace list` does not print the workspace ROOT PATH, so the path is
    filled in by matching against the roots discovered on disk -- and is left
    null rather than guessed when two workspaces sit on the same commit, because
    the path is diagnostic and the NAME is the key.

    Template note for jj 0.38: in a workspace template `name` is a bare keyword
    while `target` needs its methods called -- `target.change_id()`, not
    `target.change_id`. Both spellings of the other form are parse errors.
    """
    template = 'name ++ "\x1f" ++ target.change_id() ++ "\x1f" ++ target.commit_id() ++ "\n"'
    by_change = {}
    for other in roots:
        try:
            change_id = jj(other, "log", "-r", "@", "--no-graph",
                           "-T", 'change_id').strip()
        except RuntimeError:
            continue
        by_change.setdefault(change_id, []).append(other)
    found = []
    for line in jj(root, "workspace", "list", "-T", template).splitlines():
        if not line:
            continue
        parts = line.split(SEP)
        if len(parts) != 3:
            raise RuntimeError("unparseable workspace line %r in %s" % (line, root))
        candidates = by_change.get(parts[1]) or []
        found.append({
            "workspace": parts[0],
            "path": candidates[0] if len(candidates) == 1 else None,
            "change_id": parts[1],
            "commit_id": parts[2],
        })
    return sorted(found, key=lambda w: w["workspace"])


def capture(root, roots):
    # all() ~ root() -- the root commit is the all-zeros virtual commit present
    # in EVERY jj repo (change id z*32), so it is identity-free and anchoring on
    # it would be the same mistake as anchoring on the earliest operation.
    # bookmarks last-but-one and description LAST, because a description can
    # contain anything and a bookmark name cannot contain \x1f either way.
    template = (
        'change_id ++ "\x1f" ++ commit_id ++ "\x1f" '
        '++ bookmarks.join(",") ++ "\x1f" ++ description.first_line() ++ "\n"'
    )
    # A DIVERGENT change is recorded ONCE. Two visible commits can share one
    # change id -- that is what jj calls divergence -- and the anchor is a map
    # from a CHANGE to the fact that it still exists, so a divergent change is
    # one entry with several commit ids and not two entries.
    #
    # Recording it twice broke three things at once, all of them measured while
    # building tasks/divergent_change: validate() below rejects a repeated
    # change id outright; anchored_change_id() refuses a description that names
    # two anchor entries, so every graded revset silently fell back to
    # description matching and the identity claim was never made; and an
    # exemption entry could not name the change either, for the same reason. A
    # fixture that SHIPS a divergence -- which is the only way to hand an agent
    # one to work with -- was therefore unanchorable. Collapsing here fixes all
    # three and changes nothing for the other tasks, where no change id repeats.
    #
    # The kept commit id is the smallest of the versions', so the entry does not
    # depend on jj's log order, and the bookmarks are the union. Commit ids in
    # the anchor are diagnostic only -- nothing compares them -- so choosing one
    # loses nothing. tests/anchor.py asks how many VISIBLE commits carry the
    # change id at verification time, which is the question it actually needs
    # answered, and `may_be_divergent` in the task's exemption file is what says
    # whether more than one is allowed.
    by_change = {}
    order = []
    for line in jj(root, "log", "-r", "all() ~ root()", "--no-graph",
                   "-T", template).splitlines():
        if not line:
            continue
        parts = line.split(SEP)
        if len(parts) < 4:
            raise RuntimeError("unparseable log line %r in %s" % (line, root))
        change_id = parts[0]
        record = {
            "change_id": change_id,
            "commit_id": parts[1],
            # Recorded so a per-task assertion can say "the bookmark the task
            # grades still points at a commit the BOOTSTRAP created". NOT
            # asserted globally: plenty of correct solves legitimately move or
            # remove a bootstrap bookmark -- git_fetch_remote's rebase moves
            # `feature`, and the four dedicated bookmark tasks that made this
            # unarguable (create_and_move, push, delete, rename) were cut with
            # the suite, not disproved -- so a global check would fail correct
            # solves.
            "bookmarks": [b for b in parts[2].split(",") if b],
            "description": SEP.join(parts[3:]),
        }
        if change_id in by_change:
            by_change[change_id].append(record)
        else:
            by_change[change_id] = [record]
            order.append(change_id)

    commits = []
    for change_id in order:
        versions = sorted(by_change[change_id], key=lambda c: c["commit_id"])
        entry = dict(versions[0])
        entry["bookmarks"] = sorted({b for v in versions for b in v["bookmarks"]})
        commits.append(entry)

    # -n 1 is the NEWEST operation; jj op log is newest-first.
    handover = jj(root, "op", "log", "-n", "1", "--no-graph",
                  "-T", 'id ++ "\n"').strip()
    operations = len([
        l for l in jj(root, "op", "log", "--no-graph", "-T", '"x\n"').splitlines()
        if l
    ])
    return {
        "path": root,
        "handover_operation_id": handover,
        "operations": operations,
        "working_copies": working_copies(root, roots),
        # Sorted by change id so the file is diff-stable: jj log's order is
        # topological and would churn on unrelated Dockerfile edits.
        "commits": sorted(commits, key=lambda c: c["change_id"]),
    }


def main():
    version = subprocess.run(
        ["jj", "--version"], capture_output=True, text=True
    ).stdout.strip()
    # Primary workspaces first, so that when two workspaces share one repo the
    # anchor records the PRIMARY one rather than whichever sorted first. A
    # primary workspace's .jj/repo is a directory; an added workspace's is a
    # file holding the primary's path. workspace_update_stale is the task where
    # this matters (workspace_add's second workspace is created by the agent,
    # so the untouched image it is measured on has only the primary).
    roots = sorted(
        workspace_roots(),
        key=lambda r: (os.path.isfile(os.path.join(r, ".jj", "repo")), r),
    )
    seen, repos = {}, []
    for root in roots:
        key = store_key(root)
        if key in seen:
            continue
        seen[key] = root
        repos.append(capture(root, roots))
    json.dump({"jj_version": version, "repos": repos}, sys.stdout)


main()
'''


class MeasureError(RuntimeError):
    """A task's anchor could not be measured at all (build or capture broke)."""


def environment_sha256(env_dir: Path) -> str:
    """A content hash of the task's whole build context.

    This is the staleness key, and it is NOT the docker image id. MEASURED:
    buildx/BuildKit mints a NEW image id on every `docker build` even when every
    layer is a cache hit and the image's own Created timestamp is unchanged --
    two consecutive fully-cached builds of one task's environment gave
    sha256:0bda71ea... and sha256:ed408284... while the bootstrap's change ids
    were byte-identical. So an image-id comparison reports staleness on every
    run and is worse than useless: it would train whoever runs --check to
    ignore it.

    Hashing the build context instead separates the two cases that matter:

      * ids moved, environment_sha256 UNCHANGED -> the bootstrap layer was
        rebuilt from a cold cache. Change ids are random, so every id moved at
        once. STALE: re-run --write.
      * ids moved, environment_sha256 CHANGED -> the Dockerfile's bootstrap
        creates different commits now. A real change to review.
    """
    digest = hashlib.sha256()
    for path in sorted(p for p in env_dir.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(env_dir)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def anchor_path(task: str) -> Path:
    return TASKS_DIR / task / "tests" / ANCHOR_NAME


def all_tasks() -> list[str]:
    return sorted(p.name for p in TASKS_DIR.iterdir() if p.is_dir())


def validate(task: str, raw: dict) -> None:
    """Reject a measurement that could not do its job, loudly."""
    for repo in raw["repos"]:
        if not repo["commits"]:
            raise MeasureError(
                f"{task}: {repo['path']} is a jj repo with no visible non-root "
                "commit, so there is nothing to anchor on"
            )
        if not repo["handover_operation_id"]:
            raise MeasureError(f"{task}: {repo['path']} reported no operation id")
        ids = [c["change_id"] for c in repo["commits"]]
        if len(set(ids)) != len(ids):
            raise MeasureError(
                f"{task}: {repo['path']} reports the same change id twice in the "
                "bootstrap state; the anchor could not tell a duplicate apart "
                "from the original. A DIVERGENT change is not this: capture() "
                "collapses a change id carrying several visible commits into a "
                "single entry, so reaching here means the collapse itself is "
                "broken."
            )
        for change_id in ids:
            if len(change_id) != 32 or set(change_id) - CHANGE_ID_ALPHABET:
                raise MeasureError(
                    f"{task}: {change_id!r} is not a full 32-character jj change "
                    "id over the k-z alphabet; the capture template or the "
                    "parsing is wrong"
                )
        # The reserved working-copy key. Without it an undescribed working-copy
        # commit is unaddressable whenever a bootstrap leaves more than one, so
        # a measurement that produced none is a broken measurement rather than a
        # repository with no workspaces.
        copies = repo.get("working_copies") or []
        if not copies:
            raise MeasureError(
                f"{task}: {repo['path']} reported no workspaces, so no handover "
                "working copy could be recorded; `jj workspace list` returned "
                "nothing usable"
            )
        names = [wc["workspace"] for wc in copies]
        if len(set(names)) != len(names):
            raise MeasureError(
                f"{task}: {repo['path']} reports the workspace name(s) "
                f"{sorted(n for n in names if names.count(n) > 1)} twice, so a "
                "workspace name is not a unique anchor key here"
            )


def build_image(task: str) -> tuple[str, Path]:
    """Build the task image the way CI does; return its tag and build context.

    Shared by --write/--check (which then reads the anchor out of a throwaway
    container) and by --verify-untouched (which then runs the real tests/test.sh
    in one). Both must look at the SAME image, which is the whole point of the
    pre-flight.
    """
    env_dir = TASKS_DIR / task / "environment"
    if not (env_dir / "Dockerfile").is_file():
        raise MeasureError(f"no {env_dir.relative_to(REPO_ROOT)}/Dockerfile")

    image = f"bootstrap-anchor-{task}"
    build_env = dict(os.environ)
    # The task images are all linux/amd64 (they curl an x86_64 jj tarball).
    build_env.setdefault("DOCKER_DEFAULT_PLATFORM", "linux/amd64")
    build = subprocess.run(
        ["docker", "build", "-t", image, str(env_dir)],
        capture_output=True, text=True, env=build_env,
    )
    if build.returncode != 0:
        raise MeasureError(
            f"docker build failed for {task}:\n{build.stderr.strip()[-2000:]}"
        )
    return image, env_dir


def measure(task: str, keep_image: bool, quiet: bool) -> dict:
    """Build the task image and read the anchor out of the untouched bootstrap."""
    image, env_dir = build_image(task)

    env_digest = environment_sha256(env_dir)
    inspect = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
        capture_output=True, text=True,
    )
    image_id = inspect.stdout.strip() if inspect.returncode == 0 else ""

    # The capture program is handed over on a read-only mount rather than
    # baked in, for the same reason the anchor is not baked in. A read-only
    # mount is readable by the non-root USER the two ubuntu:22.04 images end
    # on, and /logs is chmod 777 for the same reason .github/workflows/
    # tasks.yml chmods it.
    work = Path(tempfile.mkdtemp(prefix=f"anchor-{task}-"))
    try:
        work.chmod(0o777)
        (work / "capture.py").write_text(CAPTURE, encoding="utf-8")
        (work / "capture.py").chmod(0o644)
        run = subprocess.run(
            [
                "docker", "run", "--rm", "--network", "none",
                "-v", f"{work}:/anchor:ro",
                image, "python3", "/anchor/capture.py",
            ],
            capture_output=True, text=True,
        )
        if run.returncode != 0:
            raise MeasureError(
                f"{task}: the in-container capture exited {run.returncode}\n"
                f"{(run.stdout + run.stderr).strip()[-2000:]}"
            )
        try:
            raw = json.loads(run.stdout)
        except ValueError as exc:
            raise MeasureError(
                f"{task}: the capture wrote no usable JSON ({exc}): "
                f"{run.stdout.strip()[-500:]}"
            ) from exc
    finally:
        shutil.rmtree(work, ignore_errors=True)
        if not keep_image:
            subprocess.run(["docker", "rmi", "-f", image],
                           capture_output=True, text=True)

    validate(task, raw)
    if not quiet:
        found = ", ".join(
            f"{r['path']} ({len(r['commits'])} commit(s))" for r in raw["repos"]
        )
        print(f"  measured {task}: {found or 'NO jj REPOSITORY -- not anchorable'}")
    return build_record(task, raw, image_id, env_digest)


def build_record(task: str, raw: dict, image_id: str, env_digest: str) -> dict:
    # anchored=false is a first-class, well-defined answer, not an error. A task
    # can ship an EMPTY directory on purpose -- creating the repo IS the task --
    # so there is no bootstrap identity to preserve and tests/anchor.py must
    # abstain rather than fail. No current task is in that state (the three that
    # were, working_copy_as_commit / template_formatting / git_remote_add, were
    # cut with the suite), and this path is kept for the next one that is.
    # Writing the file anyway (with anchored=false) is what makes
    # "no anchor" distinguishable from "the anchor was never generated".
    repos = [
        {
            "path": repo["path"],
            "handover_operation_id": repo["handover_operation_id"],
            "operations": repo["operations"],
            "working_copies": [
                {key: wc.get(key) for key in WORKING_COPY_KEYS}
                for wc in repo.get("working_copies") or []
            ],
            "commits": [
                {key: commit[key] for key in COMMIT_KEYS}
                for commit in repo["commits"]
            ],
        }
        for repo in raw["repos"]
    ]
    return {
        "task": task,
        "anchored": bool(repos),
        "jj_version": raw.get("jj_version", ""),
        "environment_sha256": env_digest,
        # Recorded for the record only -- NEVER compared. See
        # environment_sha256() for why an image id cannot be a staleness key.
        "image_id": image_id,
        "repos": repos,
        "generated_by": GENERATED_BY,
    }


def serialize(record: dict) -> str:
    ordered = {key: record[key] for key in ANCHOR_KEYS}
    ordered["repos"] = [
        {
            **{key: repo[key] for key in REPO_KEYS
               if key not in ("commits", "working_copies")},
            "working_copies": [
                {key: wc.get(key) for key in WORKING_COPY_KEYS}
                for wc in repo.get("working_copies") or []
            ],
            "commits": [
                {key: commit[key] for key in COMMIT_KEYS} for commit in repo["commits"]
            ],
        }
        for repo in record["repos"]
    ]
    return json.dumps(ordered, indent=2) + "\n"


def load_committed(task: str) -> dict | None:
    path = anchor_path(task)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def compare(task: str, fresh: dict) -> list[str]:
    """Differences between the committed anchor and a fresh measurement."""
    rel = anchor_path(task).relative_to(REPO_ROOT)
    committed = load_committed(task)
    if committed is None:
        return [
            f"{rel} does not exist. tests/anchor.py needs it to tell a solved "
            f"repository from a rebuilt one; run scripts/bootstrap_anchor.py "
            f"--write --task {task}."
        ]
    if not committed:
        return [f"{rel} is not a JSON object / does not parse."]

    problems = [f"{rel} is missing the {key!r} key." for key in ANCHOR_KEYS
                if key not in committed]
    if problems:
        return problems

    if committed["task"] != task:
        problems.append(f"{rel} records task {committed['task']!r}, not {task!r}.")
    if committed["anchored"] != fresh["anchored"]:
        problems.append(
            f"{rel} records anchored = {committed['anchored']!r} but a fresh "
            f"measurement gives {fresh['anchored']!r}: the bootstrap either "
            "gained or lost its repository."
        )

    # Reported FIRST, and on its own terms, because it is the benign
    # explanation for everything below it and has a different fix. Change ids
    # are random per build, so a rebuilt bootstrap layer moves every id at once
    # -- that is staleness, not tampering.
    rebuilt = committed.get("environment_sha256") != fresh["environment_sha256"]
    ids_moved = False
    stale = False
    if rebuilt:
        problems.append(
            f"{rel} was measured from a build context hashing "
            f"{str(committed.get('environment_sha256'))[:19]} but "
            f"tasks/{task}/environment now hashes "
            f"{fresh['environment_sha256'][:19]}. The task's Dockerfile or build "
            "context changed, so different bootstrap commits are expected; "
            f"review the diff, then re-run scripts/bootstrap_anchor.py --write "
            f"--task {task}."
        )

    was = {repo["path"]: repo for repo in committed.get("repos") or []}
    now = {repo["path"]: repo for repo in fresh["repos"]}
    for path in sorted(set(was) ^ set(now)):
        side = "no longer" if path in was else "now"
        problems.append(f"{rel}: {path} is {side} a jj repository in the bootstrap.")

    for path in sorted(set(was) & set(now)):
        old, new = was[path], now[path]
        if old.get("handover_operation_id") != new["handover_operation_id"]:
            problems.append(
                f"{rel}: the handover operation id for {path} moved"
                + (" (expected: the build context changed, see above)."
                   if rebuilt else
                   ". The bootstrap layer was rebuilt from a cold cache, or the "
                   "bootstrap performed a different number of operations.")
            )
        old_ids = {c["change_id"] for c in old.get("commits") or []}
        new_ids = {c["change_id"] for c in new["commits"]}
        added, removed = sorted(new_ids - old_ids), sorted(old_ids - new_ids)
        if added or removed:
            ids_moved = True
            problems.append(
                f"{rel}: the anchored change id set for {path} changed "
                f"(+{len(added)} / -{len(removed)})"
                + (" (expected: the build context changed, see above)."
                   if rebuilt else
                   ". The build context did NOT change, so this is a COLD-CACHE "
                   "REBUILD of the bootstrap layer, not a content change: jj "
                   "generates change ids randomly, so every id moved at once. "
                   "Re-run scripts/bootstrap_anchor.py --write and make sure "
                   "nothing prunes or --no-cache rebuilds between --write and "
                   "the sweep.")
            )
        old_desc = {c["change_id"]: c["description"] for c in old.get("commits") or []}
        moved = sorted(
            c["change_id"] for c in new["commits"]
            if c["change_id"] in old_desc and old_desc[c["change_id"]] != c["description"]
        )
        if moved:
            problems.append(
                f"{rel}: {path} change id(s) "
                f"{', '.join(m[:DISPLAY_PREFIX] for m in moved)} now carry a "
                "different description."
            )
    return problems


def exemptions_path(task: str) -> Path:
    return TASKS_DIR / task / "tests" / EXEMPTIONS_NAME


def check_exemptions(task: str, fresh: dict) -> list[str]:
    """Cross-check tests/anchor_exemptions.json against the measured bootstrap.

    tests/anchor.py resolves each entry to a change id at verification time and
    ABSTAINS if an entry does not resolve -- which is the fail-safe answer, but a
    silent one: a stale exemption file would turn the integrity check off for
    that task without failing anything. This is where that becomes loud, on the
    host, next to the measurement that can settle it.

    Checked here rather than in scripts/lint_tasks.py because only a measurement
    knows what the bootstrap actually contains. lint_tasks.py still enforces the
    parts that need no image: the schema, and that every entry has a reason.
    """
    path = exemptions_path(task)
    rel = path.relative_to(REPO_ROOT)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [f"{rel} does not parse ({exc})"]
    if not isinstance(data, dict):
        return [f"{rel} is not a JSON object"]

    problems: list[str] = []
    if data.get("task") != task:
        problems.append(f"{rel} records task {data.get('task')!r}, not {task!r}")
    if not fresh["anchored"]:
        problems.append(
            f"{rel} exists, but this task's bootstrap ships no jj repository "
            "(anchored=false), so tests/anchor.py abstains and the file can "
            "never apply. Delete it."
        )
        return problems

    described: dict[str, int] = {}
    workspaces: dict[str, int] = {}
    for repo in fresh["repos"]:
        for commit in repo["commits"]:
            described[commit["description"]] = described.get(
                commit["description"], 0) + 1
        for wc in repo.get("working_copies") or []:
            workspaces[wc["workspace"]] = workspaces.get(wc["workspace"], 0) + 1

    for key in EXEMPTION_LISTS:
        entries = data.get(key, [])
        if not isinstance(entries, list):
            problems.append(f"{rel}: {key!r} is not a list")
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                problems.append(f"{rel}: {key} contains {entry!r}, not an object")
                continue
            reason = entry.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                problems.append(
                    f"{rel}: an entry in {key} has no non-empty 'reason'; every "
                    "exemption has to say why the task's asked-for work removes "
                    "that commit"
                )
            named = [k for k in ("description", "working_copy") if k in entry]
            if len(named) != 1:
                problems.append(
                    f"{rel}: an entry in {key} must have exactly one of "
                    f"'description' or 'working_copy', not {named or 'neither'}"
                )
                continue
            if "description" in entry:
                count = described.get(entry["description"], 0)
                if count != 1:
                    problems.append(
                        f"{rel}: {key} names the description "
                        f"{entry['description']!r}, which matches {count} "
                        "bootstrap commit(s) in this image. An exemption must "
                        "name exactly one commit -- use "
                        '{"working_copy": "<workspace>"} for an undescribed '
                        "working-copy commit."
                    )
            else:
                count = workspaces.get(entry["working_copy"], 0)
                if count != 1:
                    problems.append(
                        f"{rel}: {key} names workspace "
                        f"{entry['working_copy']!r}, which matches {count} "
                        f"workspace(s) in this image (known: "
                        f"{', '.join(sorted(workspaces)) or 'none'})"
                    )
    return problems


def audit(task: str, fresh: dict) -> list[str]:
    """Problems with the measurement itself, committed file or not."""
    # anchored=false is not a failure. The empty-directory tasks are supposed to
    # land there; anything else landing there is a Dockerfile that stopped
    # creating a repo, which the --check path reports as an anchored flip.
    return check_exemptions(task, fresh)


def verify_untouched(task: str, keep_image: bool, quiet: bool) -> list[str]:
    """Pre-flight: run the REAL tests/test.sh against the untouched image.

    This is the check that closes the operational hole `--check` cannot: `--check`
    proves the anchor matches a FRESH measurement, but a sweep is not a fresh
    measurement -- it is the real verifier, mounting the real tests/ directory,
    inside the real image. If the anchor and the image the sweep will use have
    drifted apart, every trial scores 0 and the sweep looks like a total model
    collapse rather than an infrastructure fault. So rehearse it once, per task,
    against the untouched bootstrap:

      * the anchor fixture must report that it HOLDS -- not that it abstained,
        which is what a missing anchor file looks like and is invisible in the
        reward;
      * reward.txt must be exactly `0` -- the vacuity property
        .github/workflows/tasks.yml asserts, i.e. the verifier still refuses to
        pay an agent that did nothing. If the anchor were somehow paying credit
        on an untouched repo, this is where that shows up;
      * ctrf.json must exist and test.sh must exit 0, so the trial is a scorable
        verdict rather than the ERRORED-INFRA path.

    Returns a list of human-readable problems; empty means the task is ready.
    """
    tests_dir = TASKS_DIR / task / "tests"
    anchor_file = anchor_path(task)
    rel = anchor_file.relative_to(REPO_ROOT)
    if not anchor_file.is_file():
        return [
            f"{rel} does not exist, so the sweep would run with the anchor "
            "abstaining and no rebuild detection at all. Run "
            f"scripts/bootstrap_anchor.py --write --task {task} first."
        ]
    try:
        expected = json.loads(anchor_file.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [f"{rel} does not parse ({exc}); re-run --write."]
    if not isinstance(expected, dict) or "anchored" not in expected:
        return [f"{rel} is not a bootstrap anchor document; re-run --write."]

    image, _ = build_image(task)
    logs = Path(tempfile.mkdtemp(prefix=f"anchor-preflight-{task}-"))
    try:
        # 0o777 for the same reason .github/workflows/tasks.yml chmods it: two
        # task images end on a non-root USER directive and still have to write
        # /logs/verifier.
        logs.chmod(0o777)
        run = subprocess.run(
            [
                "docker", "run", "--rm", "--network", "none",
                "-v", f"{tests_dir}:/tests:ro",
                "-v", f"{logs}:/logs",
                image, "bash", "/tests/test.sh",
            ],
            capture_output=True, text=True,
        )
        output = run.stdout + run.stderr
        verifier = logs / "verifier"
        reward = (verifier / "reward.txt").read_text(encoding="utf-8").strip() \
            if (verifier / "reward.txt").is_file() else None
        has_ctrf = (verifier / "ctrf.json").is_file()
        has_unscored = (verifier / "ctrf.json.unscored").is_file()
        error_note = (verifier / "verifier_error.txt").read_text(encoding="utf-8").strip() \
            if (verifier / "verifier_error.txt").is_file() else ""
    finally:
        shutil.rmtree(logs, ignore_errors=True)
        if not keep_image:
            subprocess.run(["docker", "rmi", "-f", image],
                           capture_output=True, text=True)

    problems: list[str] = []
    if reward is None:
        problems.append(
            f"tasks/{task}/tests/test.sh wrote no /logs/verifier/reward.txt, so "
            "the verifier never ran at all"
        )
    elif reward != "0":
        problems.append(
            f"the untouched bootstrap image scores reward {reward!r}, not 0. A "
            "verifier that pays an agent who did nothing measures nothing; this "
            "is the same check .github/workflows/tasks.yml makes."
        )
    if run.returncode != 0 or has_unscored or error_note:
        problems.append(
            f"tests/test.sh exited {run.returncode} without reaching a verdict "
            f"(ctrf.json {'present' if has_ctrf else 'ABSENT'}, unscored report "
            f"{'present' if has_unscored else 'absent'})"
            + (f": {error_note}" if error_note else "")
            + ". A trial in this state is ERRORED-INFRA, not a reward -- the "
            "usual cause is something raising at conftest import time, which "
            "makes pytest exit 4 having reported zero tests."
        )
    elif not has_ctrf:
        problems.append(
            "tests/test.sh wrote no /logs/verifier/ctrf.json, so "
            "scripts/check_run_results.py would classify every trial of this "
            "task ERRORED-INFRA"
        )

    holds, abstain_line, failed = anchor_verdict(output)
    if expected.get("anchored"):
        if not holds or abstain_line or failed:
            if failed:
                why = (
                    "It FAILED: the anchor does not describe this image. Either "
                    "the image was rebuilt from a cold cache after --write -- "
                    "change ids are random per build, so re-run --write and do "
                    "not prune or --no-cache in between -- or the anchor was "
                    "measured against a different build entirely."
                )
            elif abstain_line:
                why = (
                    f"It ABSTAINED instead: {abstain_line}. Re-run --write, then "
                    "--check."
                )
            else:
                why = (
                    f"Neither {ANCHOR_HOLDS!r} nor {ANCHOR_ABSTAINED!r} appears "
                    "on a line of the verifier output, so the autouse fixture in "
                    "tests/conftest.py may not be running at all."
                )
            problems.append(
                "the anchor did not report that it HOLDS against this image. " + why
            )
    else:
        # The three empty-directory tasks. An abstain is the CORRECT verdict
        # here, and asserting it is what keeps "this task has no repository"
        # distinguishable from "the anchor was never generated".
        if holds or not abstain_line:
            problems.append(
                f"{rel} records anchored=false, so tests/anchor.py should have "
                f"abstained, but the verifier output "
                + ("says the anchor holds" if holds else
                   f"contains neither {ANCHOR_HOLDS!r} nor {ANCHOR_ABSTAINED!r}")
                + ". Either the bootstrap gained a jj repository (re-run "
                "--write) or the fixture is not running."
            )

    if not quiet and not problems:
        state = "anchor holds" if expected.get("anchored") else "abstains (no repo)"
        print(f"  pre-flight {task}: reward 0, ctrf.json written, {state}")
    return problems


def anchor_verdict(output: str) -> tuple[bool, str, bool]:
    """(holds, abstain line or "", failed) as reported by the verifier itself.

    Line-anchored on purpose -- see the ANCHOR_* constants for the false ABSTAIN
    a whole-output substring search produces on a run that actually failed.
    """
    holds = False
    abstain = ""
    for raw in output.splitlines():
        line = raw.strip()
        # startswith, not ==: the note now carries the exemption summary when a
        # task has one ("bootstrap anchor holds (2 commit(s) may be absent ...)").
        # Still line-anchored, so pytest echoing anchor.py's source in a
        # traceback cannot match -- those lines start with `return`.
        if line.startswith(ANCHOR_HOLDS):
            holds = True
        elif line.startswith(ANCHOR_ABSTAINED) and not abstain:
            abstain = line
    return holds, abstain, ANCHOR_FAILED in output


def run_preflight(tasks: list[str], args: argparse.Namespace) -> int:
    problems: dict[str, list[str]] = {}

    def one(task: str) -> None:
        try:
            found = verify_untouched(task, args.keep_images, args.quiet)
        except MeasureError as exc:
            found = [str(exc)]
        if found:
            problems[task] = found

    if not args.quiet:
        print(f"Pre-flighting {len(tasks)} task(s) with {args.jobs} job(s): "
              "the real tests/test.sh against the untouched image")
    if args.jobs <= 1:
        for task in tasks:
            one(task)
    else:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            list(pool.map(one, tasks))

    if problems:
        print(f"\nFAIL: {sum(len(v) for v in problems.values())} problem(s) across "
              f"{len(problems)} task(s)\n")
        for task in sorted(problems):
            print(f"  {task}")
            for message in problems[task]:
                print(f"    - {message}")
        print("\nDO NOT START THE SWEEP. Every trial of a task listed above "
              "would score 0 for infrastructure reasons.")
        return 1
    print(f"\nOK: {len(tasks)} task(s) pre-flighted: the untouched image scores "
          "0 and the anchor agrees with it. Start the sweep without pruning or "
          "rebuilding.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture the bootstrap integrity anchor of task images.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--write", action="store_true",
        help="measure and write tasks/<task>/tests/bootstrap_anchor.json",
    )
    mode.add_argument(
        "--check", action="store_true",
        help="measure and exit non-zero if a committed anchor disagrees",
    )
    mode.add_argument(
        "--verify-untouched", action="store_true",
        help="pre-flight: run the real tests/test.sh on the untouched image and "
             "assert the anchor holds, the reward is 0, and a ctrf.json was "
             "written. Run this immediately before a sweep.",
    )
    parser.add_argument(
        "--task", action="append", metavar="NAME",
        help="task to measure (repeatable; default every task under tasks/)",
    )
    parser.add_argument(
        "--jobs", type=int, default=4, metavar="N",
        help="parallel measurements (default 4; image builds are CPU-bound)",
    )
    parser.add_argument(
        "--keep-images", action="store_true",
        help="do not docker rmi the images this script builds",
    )
    parser.add_argument("--quiet", action="store_true", help="only print problems")
    args = parser.parse_args()

    if not TASKS_DIR.is_dir():
        print(f"error: {TASKS_DIR} does not exist", file=sys.stderr)
        return 1

    tasks = args.task or all_tasks()
    unknown = [t for t in tasks if not (TASKS_DIR / t).is_dir()]
    if unknown:
        print(f"error: no such task(s): {', '.join(unknown)}", file=sys.stderr)
        return 1

    if args.verify_untouched:
        return run_preflight(tasks, args)

    measurements: dict[str, dict] = {}
    failures: dict[str, list[str]] = {}

    def one(task: str) -> None:
        try:
            measurements[task] = measure(task, args.keep_images, args.quiet)
        except MeasureError as exc:
            failures[task] = [str(exc)]

    if not args.quiet:
        print(f"Measuring the bootstrap anchor of {len(tasks)} task(s) "
              f"with {args.jobs} job(s)")

    if args.jobs <= 1:
        for task in tasks:
            one(task)
    else:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            list(pool.map(one, tasks))

    problems: dict[str, list[str]] = dict(failures)
    for task in sorted(measurements):
        found = audit(task, measurements[task])
        if args.check:
            found += compare(task, measurements[task])
        if found:
            problems.setdefault(task, []).extend(found)

    if args.write:
        for task in sorted(measurements):
            path = anchor_path(task)
            path.parent.mkdir(parents=True, exist_ok=True)
            text = serialize(measurements[task])
            changed = not path.is_file() or path.read_text(encoding="utf-8") != text
            path.write_text(text, encoding="utf-8")
            if not args.quiet:
                state = "wrote" if changed else "unchanged"
                print(f"  {state} {path.relative_to(REPO_ROOT)}")

    if not args.quiet:
        print(f"\n{'task':<34} {'repos':>5} {'commits':>7}  handover op / paths")
        for task in sorted(measurements):
            record = measurements[task]
            if not record["anchored"]:
                print(f"{task:<34} {'-':>5} {'-':>7}  "
                      "NO REPOSITORY IN BOOTSTRAP (anchor abstains)")
                continue
            total = sum(len(r["commits"]) for r in record["repos"])
            detail = "; ".join(
                f"{r['path']}@{r['handover_operation_id'][:DISPLAY_PREFIX]}"
                for r in record["repos"]
            )
            print(f"{task:<34} {len(record['repos']):>5} {total:>7}  {detail}")
        unanchorable = sorted(t for t in measurements if not measurements[t]["anchored"])
        print(f"\n{len(measurements)} task(s) measured; "
              f"{len(measurements) - len(unanchorable)} anchorable; "
              f"{len(unanchorable)} with no bootstrap repository:")
        print("  " + (", ".join(unanchorable) or "-"))

        # The exemption inventory. Printed on every run so a commit whose
        # removal is allowed can never become invisible infrastructure -- the
        # same reason scripts/lint_tasks.py prints every floored test.
        print("\nper-task anchor exemptions (tests/anchor_exemptions.json):")
        exempted = 0
        for task in sorted(measurements):
            path = exemptions_path(task)
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                print(f"  {task:<32} UNPARSEABLE")
                continue
            counts = " ".join(
                f"{key}={len(data.get(key) or [])}" for key in EXEMPTION_LISTS
            )
            print(f"  {task:<32} {counts}")
            exempted += 1
        print(f"  {exempted} task(s) claim an exemption; the other "
              f"{len(measurements) - exempted} are checked strictly.")

    if problems:
        print(f"\nFAIL: {sum(len(v) for v in problems.values())} problem(s) across "
              f"{len(problems)} task(s)\n")
        for task in sorted(problems):
            print(f"  {task}")
            for message in problems[task]:
                print(f"    - {message}")
        return 1

    if args.check:
        print(f"\nOK: {len(measurements)} task anchor(s) match a fresh measurement.")
    else:
        print(f"\nOK: wrote {len(measurements)} measured task anchor(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
