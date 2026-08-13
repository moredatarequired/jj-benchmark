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

    passing = sorted(
        str(test.get("name")) for test in tests if test.get("status") == "passed"
    )
    return total, passing


def measure(task: str, keep_image: bool, quiet: bool) -> tuple[int, list[str]]:
    """Build the task image and run its real verifier against the bootstrap state."""
    env_dir = TASKS_DIR / task / "environment"
    tests_dir = TASKS_DIR / task / "tests"
    if not (env_dir / "Dockerfile").is_file():
        raise MeasureError(f"no {env_dir.relative_to(REPO_ROOT)}/Dockerfile")

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
        try:
            if args.ctrf:
                total, passing = read_ctrf(Path(args.ctrf))
            else:
                total, passing = measure(task, args.keep_images, args.quiet)
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

    if args.write:
        for task in sorted(measurements):
            path = floor_path(task)
            path.parent.mkdir(parents=True, exist_ok=True)
            text = serialize(measurements[task])
            changed = not path.is_file() or path.read_text(encoding="utf-8") != text
            path.write_text(text, encoding="utf-8")
            if not args.quiet:
                rel = path.relative_to(REPO_ROOT)
                state = "wrote" if changed else "unchanged"
                print(
                    f"  {state} {rel} "
                    f"(floor {measurements[task]['floor']}/"
                    f"{measurements[task]['tests']})"
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
