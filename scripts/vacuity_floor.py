#!/usr/bin/env python3
"""Measure -- never hand-write -- the no-agent pass floor of every task verifier.

tests/test.sh awards partial credit as

    credit = (passed tests not in the floor) / (tests not in the floor)

where the *floor* is the SET OF TEST NAMES in
tasks/<task>/tests/test_final_state.py that pass on the *untouched bootstrap
image*, with no agent having run. Excluding them by name is what keeps a
do-nothing agent at exactly reward 0, structurally: 7 of the 14 tasks pass at
least one test with no agent, and undo_mistaken_rebase passes 4 of its 6 by
design, because its correct end state IS the bootstrap state and only the
operation log tells a real solve apart. Those are the only tests a nop agent
passes, so its numerator is empty. (Awarding the raw passed/tests fraction would
hand every model 0.667 there for doing nothing.)

A floor is therefore a *measurement of the verifier*, and a wrong floor is
silent score inflation -- every model gets the difference for free. So:

  * ``--write`` measures and writes tasks/<task>/tests/vacuity_floor.json.
  * ``--check`` measures and fails non-zero if the committed file disagrees.
    CI runs this, so weakening a verifier (or adding a test that happens to
    hold in the bootstrap state) fails the build instead of quietly raising
    everyone's score. The comparison is on the NAME SET, not the count: a
    verifier weakened so that a *different* test now passes on an untouched
    repo fails the check even though the count did not move.

A measurement is exactly what .github/workflows/tasks.yml already does for its
vacuity gate:

    docker build -t <img> tasks/<task>/environment
    docker run --rm --network none \
        -v .../tests:/tests:ro -v <tmp>:/logs <img> bash /tests/test.sh

and then reading which tests have status "passed" in /logs/verifier/ctrf.json.
When a caller already has that report -- the CI vacuity step does -- pass
``--ctrf <path>`` with ``--task <name>`` and no container is started.

A RUN THAT PROVES NOTHING IS NOT A FLOOR OF ZERO
================================================

"No test passed" and "no test ran" produce the same CTRF summary --
``{"tests": 8, "passed": 0}`` -- and only the first of them is a measurement.
This script refuses to record the second, because it already recorded it once:
squash_range was written down as floor 0 of 8 when in truth three of its tests
pass on the untouched image, and tests/test.sh excludes floored names from BOTH
sides of its fraction, so the task was scored out of 5 assertions instead of 8
until CI caught it (see ea80c334).

What had happened is worth stating exactly, because nothing about it looked
wrong at the time. A ``tests/bootstrap_anchor.json`` left in the tree from an
EARLIER build of the image names change ids that this build does not contain --
jj generates them randomly at commit creation, so two builds of one Dockerfile
are disjoint. The session-scoped autouse fixture in tests/conftest.py then
raises BOOTSTRAP_ANCHOR_VIOLATION, every test in the file errors during setup
before its body runs, and the report says 0 passed. Recording that is not a
conservative mistake: a floor that is too LOW shrinks the scored denominator and
makes the task read harder than it is.

So four refusals, each of which fails the task loudly rather than writing a
file (``--write``) or comparing against one (``--check``):

  * an anchor file is present in the tests/ directory about to be measured.
    The floor is a property of the untouched image and CI always builds cold
    with no anchor at all, so this is refused before a container starts. Pass
    ``--ignore-anchors`` to measure against a staged copy of tests/ with the
    anchor left out; the tree is never modified either way.
  * the CTRF report carries the BOOTSTRAP_ANCHOR_VIOLATION token -- the direct
    evidence that the anchor, not the verifier, decided this run.
  * ANY test in the report errored during setup, which is the general case:
    any fixture those tests request can stop a body running the same way the
    anchor fixture does, and a body that did not run is not evidence about what
    passes with no agent. (A failing module import does NOT arrive here: it is
    a collection error, so the report lists no tests at all and the "0 tests"
    check in read_ctrf rejects it first.) The threshold is one, not all. A test
    that never executed is recorded exactly like one that ran and failed -- it
    stays out of passes_without_agent -- so 7 of 8 erroring would have written
    a floor of 1/8 and quietly scored the task out of seven assertions it does
    not have. A partial wreck is a wreck; there is no fraction of non-executing
    tests that makes the remainder a measurement of the floor.
  * EVERY test in the report was SKIPPED, so no body ran at all. One skip among
    several is a decision the verifier made on purpose and leaves the rest a
    real measurement, which is why this one is phrased on all rather than any.
    A run that skipped the whole file is the squash_range wreck in different
    dress: a skipped test is recorded exactly like a failing one, absent from
    passes_without_agent, so the run reads as a floor of 0 -- and floor 0 out of
    8 clears the audit below, which only catches a floor that is too HIGH.

Pure stdlib. Requires a working docker daemon only when --ctrf is not given.

Examples:

    scripts/vacuity_floor.py --write                      # all 14, 4 at a time
    scripts/vacuity_floor.py --write --task squash_range
    scripts/vacuity_floor.py --check --jobs 4             # what nightly CI runs
    scripts/vacuity_floor.py --check --task squash_range \
        --ctrf "$logs/verifier/ctrf.json"                 # what per-task CI runs
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks"

FLOOR_NAME = "vacuity_floor.json"

# Gitignored, host-generated, and describes one image BUILD rather than a
# Dockerfile (scripts/bootstrap_anchor.py explains why). Its presence during a
# floor measurement is the corruption this script refuses to record.
ANCHOR_NAME = "bootstrap_anchor.json"

# The marker tests/anchor.py puts at the head of every violation report, and
# therefore in the `trace` field of every test entry when the fixture in
# tests/conftest.py fails. Kept in sync by name only -- this script must not
# import from a task's tests/ directory, which is mounted, not installed.
VIOLATION_TOKEN = "BOOTSTRAP_ANCHOR_VIOLATION"

# Written by scripts/vacuity_floor.py, read by tests/test.sh. Kept in this
# order so the file is diff-stable across regenerations.
FLOOR_KEYS = ("task", "tests", "floor", "passes_without_agent", "generated_by")
GENERATED_BY = "scripts/vacuity_floor.py"


class MeasureError(RuntimeError):
    """A task's floor could not be measured at all (build or verifier broke)."""


def floor_path(task: str) -> Path:
    return TASKS_DIR / task / "tests" / FLOOR_NAME


def all_tasks() -> list[str]:
    return sorted(p.name for p in TASKS_DIR.iterdir() if p.is_dir())


def short(name: str) -> str:
    """The test function name, which is the key tests/test.sh scores by.

    CTRF records pytest's nodeid, e.g.
    "test_final_state.py::test_topology_restored". The path part is relative to
    pytest's rootdir and could move if the verifier were invoked from elsewhere;
    the function name cannot, and with one test file per task it is unique.
    Floor files store the full nodeid because it is more readable in review;
    every comparison happens on this normalisation.
    """
    return name.rsplit("::", 1)[-1]


def anchor_path(task: str) -> Path:
    return TASKS_DIR / task / "tests" / ANCHOR_NAME


def errored_in_setup(test: dict) -> bool:
    """True if this CTRF entry never got as far as running its test body.

    pytest-json-ctrf==0.3.5 -- the version pinned into every task image -- does
    not label the phase directly, but it does leak it. ctrf/TestObject.py sets
    `raw_status` to f"{report.when}_{report.outcome}" inside set_status(), then
    __init__ clears it again right after constructing the object from the FIRST
    report for a nodeid, and set_status() returns early once the status is
    FAILED. So a test whose call phase failed keeps the raw_status "call_failed"
    written by the second report, while a test that failed in setup -- the only
    report it ever produces -- ends up with no raw_status at all.

    "No raw_status" alone is therefore not enough, because a SKIPPED test also
    produces one report and also ends up without one. A skip is a decision the
    verifier made on purpose and says something real ("not applicable here"), so
    it is excluded by status: only an entry that is neither passed nor skipped
    and carries no raw_status is a body that never ran. This predicate is read
    per test now -- untrustworthy() refuses on the FIRST one, not only when
    every test in the run errored -- so getting the skip case wrong here would
    refuse a perfectly good measurement.
    """
    if test.get("status") in ("passed", "skipped", "pending"):
        return False
    return not test.get("raw_status")


def first_trace_line(tests: list[dict]) -> str:
    """The one line out of the report that names the real cause.

    Given only the entries the refusal is about -- the anchored ones, the ones
    that errored -- never the whole report: a test that ran and failed on its
    own merits carries a trace too, and if it is listed first, quoting it points
    the diagnostic at a healthy part of the run instead of at the wreck.

    pytest prefixes the raised exception with "E " in a longrepr, so the first
    such line is the exception itself ("AssertionError: BOOTSTRAP_ANCHOR_
    VIOLATION codes=...") rather than the source of the fixture that raised it,
    which is what the trace opens with.
    """
    for test in tests:
        lines = [line.rstrip() for line in (test.get("trace") or "").splitlines()]
        errors = [line[1:].strip() for line in lines if line.startswith("E ")]
        for line in [*errors, *(line.strip() for line in lines)]:
            if line:
                return line[:200]
    return "(no trace recorded)"


def untrustworthy(path: Path, tests: list[dict]) -> str | None:
    """Why this report is not a measurement of the floor, or None if it is.

    The first two conditions describe tests the verifier never got to express an
    opinion about, and both are phrased on ANY test rather than on all of them.
    That matters: a test that did not execute is written down the same way as one
    that ran and failed -- absent from passes_without_agent -- so even one of
    them drags the floor DOWN, and too low is not the safe direction. tests/test.sh
    drops floored names from both sides of its fraction, so a floor that is too
    low silently scores the task out of more assertions than it really has, for
    every model. Refusing the whole report is right even when most of it ran:
    the tests that did run are still a fine measurement of themselves, but the
    FLOOR is a property of the whole file and cannot be assembled from a subset.

    The third condition is the one shape a skip can take that is not a decision
    worth trusting, and it is phrased on EVERY test for the reason the other two
    are not: a skip says something real about the tests around it, so a report
    with some skips still measures its file, and only a report with nothing but
    skips measures nothing at all.
    """
    anchored = [test for test in tests if VIOLATION_TOKEN in (test.get("trace") or "")]
    if anchored:
        return (
            f"REFUSING TO RECORD A FLOOR FROM {path}: this run was zeroed by the "
            f"bootstrap anchor, not by the verifier. {len(anchored)} of "
            f"{len(tests)} test(s) carry {VIOLATION_TOKEN} in their trace, which "
            "the session-scoped fixture in tests/conftest.py raises when "
            "/tests/bootstrap_anchor.json describes a DIFFERENT build of this "
            "image (jj change ids are random per build, so an anchor from an "
            "earlier build never matches). That fixture is session-scoped and "
            "autouse, so every test errored before its body ran and this run "
            "says nothing about what passes with no agent -- "
            "and recording it would set the floor to 0 and shrink the task's "
            "scored denominator for every model. Remedy: delete "
            f"tasks/*/tests/{ANCHOR_NAME} and measure again (regenerate with "
            "scripts/bootstrap_anchor.py --write before your next sweep), or "
            "re-run with --ignore-anchors, which measures against a staged copy "
            "of tests/ that leaves the anchor out.\n"
            f"    first trace line: {first_trace_line(anchored)}"
        )

    errored = [test for test in tests if errored_in_setup(test)]
    if errored:
        return (
            f"REFUSING TO RECORD A FLOOR FROM {path}: {len(errored)} of "
            f"{len(tests)} test(s) errored during setup, so their bodies never "
            "ran. A test that did not execute is not evidence that it fails on "
            "the untouched image, and it is counted as one here: it stays out "
            "of passes_without_agent, so the floor comes out too LOW and "
            "tests/test.sh then scores the task out of more assertions than it "
            "really has -- for every model. Something those tests depend on is "
            "failing before their bodies: a fixture in tests/conftest.py, or one "
            "in tests/test_final_state.py itself. Fix that and measure again.\n"
            f"    first trace line: {first_trace_line(errored)}"
        )

    skipped = [test for test in tests if test.get("status") == "skipped"]
    if skipped and len(skipped) == len(tests):
        return (
            f"REFUSING TO RECORD A FLOOR FROM {path}: all {len(tests)} test(s) "
            "were SKIPPED, so not one body ran and the verifier said nothing "
            "about the untouched image. A skipped test is recorded exactly like "
            "a failing one -- it stays out of passes_without_agent -- so this "
            "run would be written down as a floor of 0, and tests/test.sh would "
            "then score the task out of every assertion it has, including any a "
            "do-nothing agent already passes. (Some skips are fine: they leave "
            "the tests that did run a real measurement, and only a run that "
            "skipped everything measures nothing.) Something is skipping the "
            "whole file: a module-level pytest.skip or skipif in "
            "tests/test_final_state.py, or a fixture that opts out on this "
            "image. Make it run on the bootstrap image and measure again.\n"
            f"    first trace line: {first_trace_line(skipped)}"
        )

    return None


def anchor_refusal(task: str, path: Path, from_report: bool) -> str:
    """Refuse before a container starts: the tree carries a bootstrap anchor."""
    rel = path.relative_to(REPO_ROOT)
    measured = (
        "the run behind the CTRF report you passed most likely mounted it -- "
        "this script cannot see what that run mounted, so it will not assume"
        if from_report
        else "measuring it would mount that file at /tests/bootstrap_anchor.json"
    )
    return (
        f"REFUSING TO MEASURE {task}: {rel} exists, and {measured}.\n"
        "    The floor is a property of the UNTOUCHED image with NO anchor -- "
        "that is the condition CI measures in, because CI always builds cold. "
        "An anchor written for an earlier build names change ids this build does "
        "not have, so the fixture in tests/conftest.py fails, every test errors "
        "during setup, and the run reports 0 passed. That reads exactly like a "
        "floor of 0 and is not one.\n"
        f"    Remedy: rm tasks/*/tests/{ANCHOR_NAME} (regenerate them with "
        "scripts/bootstrap_anchor.py --write when you next run a sweep), or pass "
        "--ignore-anchors to measure against a staged copy of tests/ with the "
        "anchor left out. Neither this script nor --ignore-anchors ever deletes "
        "the file for you: it is a host artifact you generated on purpose."
    )


def read_ctrf(path: Path) -> tuple[int, list[str]]:
    """Return (total tests, sorted nodeids of the tests that passed)."""
    try:
        results = json.loads(path.read_text(encoding="utf-8"))["results"]
        tests = results["tests"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise MeasureError(f"unusable CTRF report at {path}: {exc}") from exc

    names = [test.get("name") for test in tests]
    if any(not isinstance(name, str) or not name for name in names):
        raise MeasureError(f"{path} contains a test with no name")
    if len({short(name) for name in names}) != len(names):
        raise MeasureError(
            f"{path} contains two tests with the same function name; the name "
            "is the scoring key, so it has to be unique"
        )

    total = (results.get("summary") or {}).get("tests")
    if not isinstance(total, int) or isinstance(total, bool):
        total = len(tests)
    if total != len(tests):
        raise MeasureError(
            f"{path} is inconsistent: summary.tests is {total} but it lists "
            f"{len(tests)} test(s)"
        )
    if total <= 0:
        raise MeasureError(f"{path} reports 0 tests, so there is nothing to measure")

    # Checked here rather than at the call sites so that BOTH paths into a
    # measurement -- the container this script starts, and the report CI hands
    # it with --ctrf -- are covered by the same refusal.
    broken = untrustworthy(path, tests)
    if broken:
        raise MeasureError(broken)

    passing = sorted(
        str(test.get("name")) for test in tests if test.get("status") == "passed"
    )
    return total, passing


def stage_without_anchor(task: str, tests_dir: Path) -> Path:
    """A copy of tests/ with the anchor left out, for --ignore-anchors.

    Copied rather than deleted in place: tests/bootstrap_anchor.json is a host
    artifact somebody generated on purpose (scripts/bootstrap_anchor.py --write
    before a sweep), and a measuring tool has no business destroying it. What
    gets mounted is then exactly the CI condition -- every other file byte for
    byte, and no anchor.
    """
    staged = Path(tempfile.mkdtemp(prefix=f"vacuity-tests-{task}-")) / "tests"
    shutil.copytree(
        tests_dir,
        staged,
        ignore=shutil.ignore_patterns(ANCHOR_NAME, "__pycache__"),
    )
    # Same reason /logs is chmodded below: two task images end on a non-root
    # USER, and mkdtemp is 0700, so the container could not read its own tests.
    staged.parent.chmod(0o755)
    for path in [staged, *staged.rglob("*")]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    return staged


def measure(
    task: str, keep_image: bool, quiet: bool, ignore_anchors: bool = False
) -> tuple[int, list[str]]:
    """Build the task image and run its real verifier against the bootstrap state."""
    env_dir = TASKS_DIR / task / "environment"
    tests_dir = TASKS_DIR / task / "tests"
    if not (env_dir / "Dockerfile").is_file():
        raise MeasureError(f"no {env_dir.relative_to(REPO_ROOT)}/Dockerfile")

    # By the time this runs, main() has already refused unless --ignore-anchors.
    staged_root = None
    if ignore_anchors and anchor_path(task).is_file():
        tests_dir = stage_without_anchor(task, tests_dir)
        staged_root = tests_dir.parent
        if not quiet:
            print(
                f"  {task}: measuring against a staged copy of tests/ with "
                f"{ANCHOR_NAME} left out (--ignore-anchors); the file in the "
                "tree is untouched"
            )

    image = f"vacuity-floor-{task}"
    build_env = dict(os.environ)
    # The task images are all linux/amd64 (they curl an x86_64 jj tarball).
    build_env.setdefault("DOCKER_DEFAULT_PLATFORM", "linux/amd64")
    build = subprocess.run(
        ["docker", "build", "-t", image, str(env_dir)],
        capture_output=True,
        text=True,
        env=build_env,
    )
    if build.returncode != 0:
        raise MeasureError(
            f"docker build failed for {task}:\n{build.stderr.strip()[-2000:]}"
        )

    logs = Path(tempfile.mkdtemp(prefix=f"vacuity-{task}-"))
    try:
        # Two task images end on a non-root USER, so /logs must be writable by
        # anyone -- the same reason .github/workflows/tasks.yml chmods 777.
        logs.chmod(0o777)
        run = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "-v",
                f"{tests_dir}:/tests:ro",
                "-v",
                f"{logs}:/logs",
                image,
                "bash",
                "/tests/test.sh",
            ],
            capture_output=True,
            text=True,
        )
        ctrf = logs / "verifier" / "ctrf.json"
        if not ctrf.is_file():
            unscored = logs / "verifier" / "ctrf.json.unscored"
            detail = (
                "the verifier moved it aside as unscorable"
                if unscored.is_file()
                else "the verifier never wrote one"
            )
            raise MeasureError(
                f"{task}: no /logs/verifier/ctrf.json ({detail}); "
                f"test.sh exited {run.returncode}\n"
                f"{(run.stdout + run.stderr).strip()[-2000:]}"
            )
        if not quiet:
            print(f"  measured {task} (test.sh exited {run.returncode})")
        return read_ctrf(ctrf)
    finally:
        shutil.rmtree(logs, ignore_errors=True)
        if staged_root is not None:
            shutil.rmtree(staged_root, ignore_errors=True)
        if not keep_image:
            subprocess.run(
                ["docker", "rmi", "-f", image],
                capture_output=True,
                text=True,
            )


def build_record(task: str, total: int, passing: list[str]) -> dict:
    return {
        "task": task,
        "tests": total,
        "floor": len(passing),
        "passes_without_agent": passing,
        "generated_by": GENERATED_BY,
    }


def serialize(record: dict) -> str:
    ordered = {key: record[key] for key in FLOOR_KEYS}
    return json.dumps(ordered, indent=2) + "\n"


def load_committed(task: str) -> dict | None:
    path = floor_path(task)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def compare(task: str, fresh: dict) -> list[str]:
    """Differences between the committed floor file and a fresh measurement."""
    rel = floor_path(task).relative_to(REPO_ROOT)
    committed = load_committed(task)
    if committed is None:
        return [
            f"{rel} does not exist. tests/test.sh needs it to award partial "
            f"credit; run scripts/vacuity_floor.py --write --task {task}."
        ]
    if not committed:
        return [f"{rel} is not a JSON object / does not parse."]

    problems = []
    for key in FLOOR_KEYS:
        if key not in committed:
            problems.append(f"{rel} is missing the {key!r} key.")
    if problems:
        return problems

    for key in ("task", "tests"):
        if committed[key] != fresh[key]:
            problems.append(
                f"{rel} records {key} = {committed[key]!r} but a fresh "
                f"measurement of the untouched image gives {fresh[key]!r}."
            )

    # The floor is a SET OF NAMES, so that is what gets compared. Comparing
    # counts alone leaves a hole: a verifier weakened so that a different test
    # now passes on the untouched image keeps the count and changes the meaning.
    committed_names = committed["passes_without_agent"]
    if not isinstance(committed_names, list) or not all(
        isinstance(name, str) and name for name in committed_names
    ):
        problems.append(f"{rel} passes_without_agent is not a list of test names.")
        return problems

    was, now = {short(n) for n in committed_names}, {short(n) for n in fresh["passes_without_agent"]}
    added, removed = sorted(now - was), sorted(was - now)
    if added:
        problems.append(
            f"{rel} does not list test(s) that DO pass on the untouched image: "
            f"{', '.join(added)}. Every model would be paid for those for free. "
            "Either the verifier was weakened, or a new test holds in the "
            "bootstrap state and should assert something the agent has to do."
        )
    if removed:
        problems.append(
            f"{rel} lists test(s) that no longer pass on the untouched image: "
            f"{', '.join(removed)}. They are being excluded from scoring for "
            "nothing, which makes the task harder than it reads."
        )
    if not added and not removed and committed_names != fresh["passes_without_agent"]:
        problems.append(
            f"{rel} names the right tests but not in the form a measurement "
            f"produces: {committed_names!r} vs {fresh['passes_without_agent']!r}. "
            "Regenerate it rather than editing it."
        )
    if committed["floor"] != len(committed_names):
        problems.append(
            f"{rel} says floor {committed['floor']} but lists "
            f"{len(committed_names)} test name(s); it has been edited by hand."
        )
    return problems


def audit(task: str, fresh: dict) -> list[str]:
    """Problems with the measurement itself, committed file or not."""
    if fresh["floor"] >= fresh["tests"]:
        return [
            f"tasks/{task}/tests/test_final_state.py passes ALL "
            f"{fresh['tests']} of its tests on the untouched bootstrap image. "
            "The task measures nothing an agent has to do; no floor can fix "
            "that. Fix the verifier."
        ]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure the no-agent pass floor of task verifiers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--write",
        action="store_true",
        help="measure and write tasks/<task>/tests/vacuity_floor.json",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="measure and exit non-zero if a committed floor file disagrees",
    )
    parser.add_argument(
        "--task",
        action="append",
        metavar="NAME",
        help="task to measure (repeatable; default every task under tasks/)",
    )
    parser.add_argument(
        "--ctrf",
        metavar="PATH",
        help=(
            "score an existing /logs/verifier/ctrf.json from a no-agent run "
            "instead of building and running the image. Requires exactly one "
            "--task."
        ),
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=4,
        metavar="N",
        help="parallel measurements (default 4; image builds are CPU-bound)",
    )
    parser.add_argument(
        "--keep-images",
        action="store_true",
        help="do not docker rmi the images this script builds",
    )
    parser.add_argument(
        "--ignore-anchors",
        action="store_true",
        help=(
            f"measure a task whose tests/ carries a {ANCHOR_NAME}, against a "
            "staged copy of tests/ with that file left out (the tree is never "
            "modified). Without this, such a task is refused unmeasured."
        ),
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
    if args.ctrf and len(tasks) != 1:
        print("error: --ctrf takes exactly one --task", file=sys.stderr)
        return 1

    measurements: dict[str, dict] = {}
    failures: dict[str, list[str]] = {}

    def one(task: str) -> None:
        # Before anything is built or read: a floor measured with a bootstrap
        # anchor in the tests/ directory is the corruption this guard exists
        # for, and it is cheaper and clearer to say so than to run the image
        # and diagnose the wreckage out of the report afterwards.
        anchor = anchor_path(task)
        if anchor.is_file() and not args.ignore_anchors:
            failures[task] = [anchor_refusal(task, anchor, bool(args.ctrf))]
            return
        try:
            if args.ctrf:
                total, passing = read_ctrf(Path(args.ctrf))
            else:
                total, passing = measure(
                    task, args.keep_images, args.quiet, args.ignore_anchors
                )
        except MeasureError as exc:
            failures[task] = [str(exc)]
            return
        measurements[task] = build_record(task, total, passing)

    if not args.quiet:
        how = f"from {args.ctrf}" if args.ctrf else f"with {args.jobs} job(s)"
        print(f"Measuring the no-agent floor of {len(tasks)} task(s) {how}")

    if args.ctrf or args.jobs <= 1:
        for task in tasks:
            one(task)
    else:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            list(pool.map(one, tasks))

    problems: dict[str, list[str]] = dict(failures)
    for task in sorted(measurements):
        fresh = measurements[task]
        found = audit(task, fresh)
        if args.check:
            found += compare(task, fresh)
        if found:
            problems.setdefault(task, []).extend(found)

    # Persist LAST, and only what survived both gates above. An untrustworthy
    # report never reaches `measurements` at all (read_ctrf raises and `one`
    # files it under `failures`), and a task whose measurement failed its audit
    # is in `problems` -- writing that to disk would leave a floor the run is
    # about to exit non-zero over, and the next reader has no way to tell it
    # from a good one. The clean tasks are still written: they were measured
    # independently, in their own container, and one broken task is no reason
    # to throw away thirteen good measurements.
    if args.write:
        for task in sorted(measurements):
            path = floor_path(task)
            rel = path.relative_to(REPO_ROOT)
            record = measurements[task]
            if task in problems:
                if not args.quiet:
                    print(
                        f"  NOT writing {rel}: this measurement did not pass "
                        "its audit (see below); the file on disk is left "
                        "exactly as it was"
                    )
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            text = serialize(record)
            changed = not path.is_file() or path.read_text(encoding="utf-8") != text
            if changed:
                path.write_text(text, encoding="utf-8")
            if not args.quiet:
                state = "wrote" if changed else "unchanged"
                print(
                    f"  {state} {rel} "
                    f"(floor {record['floor']}/{record['tests']})"
                )

    if not args.quiet:
        print(f"\n{'task':<34} {'floor':>5} {'tests':>5}  passes with no agent")
        for task in sorted(measurements):
            record = measurements[task]
            names = ", ".join(
                name.rsplit("::", 1)[-1] for name in record["passes_without_agent"]
            )
            print(
                f"{task:<34} {record['floor']:>5} {record['tests']:>5}  "
                f"{names or '-'}"
            )
        # tests - floor is the denominator partial credit actually gets to work
        # with. Where it is 1, the reward is still only ever 0 or 1.
        binary = sorted(
            t
            for t in measurements
            if measurements[t]["tests"] - measurements[t]["floor"] <= 1
        )
        print(
            f"\n{len(measurements)} task(s) measured; "
            f"{sum(1 for t in measurements if measurements[t]['floor'])} with a "
            f"nonzero floor; {len(binary)} left with a single scorable test, so "
            "still scored 0 or 1:"
        )
        print("  " + (", ".join(binary) or "-"))

    if problems:
        print(
            f"\nFAIL: {sum(len(v) for v in problems.values())} problem(s) across "
            f"{len(problems)} task(s)\n"
        )
        for task in sorted(problems):
            print(f"  {task}")
            for message in problems[task]:
                print(f"    - {message}")
        return 1

    if args.check:
        print(f"\nOK: {len(measurements)} task floor(s) match a fresh measurement.")
    else:
        print(f"\nOK: wrote {len(measurements)} measured task floor(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
