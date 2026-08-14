#!/usr/bin/env python3
"""Schema lint for the task definitions under tasks/.

Pure stdlib, no containers, runs in about a second. It catches the cheap
structural mistakes that would otherwise only surface once a full benchmark
run has burned an hour of GPU-free-but-not-free CI time:

  * a task missing one of the seven files the harness expects
  * a task.toml that does not parse, or that omits a timeout / resource knob
  * a bootstrap/task.json whose task_description has drifted from instruction.md
  * a Dockerfile pinning a different jj version from every other task
  * a Dockerfile that does not bake in the pinned verifier dependencies
  * a tests/test.sh, tests/anchor.py or tests/conftest.py that has drifted out
    of sync with the identical copy each of the other 23 tasks carries
  * a tests/conftest.py that no longer applies the bootstrap integrity anchor
  * a tests/anchor_exemptions.json (optional, hand-written) that does not follow
    the schema, or that exempts a bootstrap commit without saying why
  * a tests/vacuity_floor.json that is missing, malformed, or stale with
    respect to the tests defined in tests/test_final_state.py

It also prints an inventory of things that are *policy*, not correctness --
which instruction files use "## Implementation" vs "## Implementation Guide"
vs neither, and the per-phase network_mode split. Those are not failures, but
printing them means a future change to the convention is visible in the CI log
as a diff in the numbers rather than silently spreading.

Exit status is 0 if every hard check passed, 1 otherwise.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tomllib
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks"

# Every task directory must contain exactly these, at these paths.
#
# tests/bootstrap_anchor.json is deliberately NOT here and is gitignored. jj
# generates change ids randomly at commit creation, so the anchor describes an
# image BUILD rather than a Dockerfile: two builds of the same Dockerfile
# produce disjoint change id sets. It is generated on the host immediately
# before a sweep (scripts/bootstrap_anchor.py --write) and tests/anchor.py
# abstains when it is absent, so requiring it here -- or in CI, which always
# builds cold -- would fail permanently.
REQUIRED_FILES = (
    "instruction.md",
    "task.toml",
    "bootstrap/task.json",
    "bootstrap/test_initial_state.py",
    "environment/Dockerfile",
    "tests/test.sh",
    "tests/test_final_state.py",
    "tests/anchor.py",
    "tests/conftest.py",
    "tests/vacuity_floor.json",
)

# Shared verifier infrastructure: copied verbatim into every task, because
# harbor mounts only one task's tests/ directory at /tests and there is nowhere
# else for a shared module to live. Divergence between copies is always a bug --
# it means one task is being verified by different code from all the others.
SHARED_TEST_FILES = ("tests/test.sh", "tests/anchor.py", "tests/conftest.py")

# tests/anchor_exemptions.json is OPTIONAL and per-task, so it is not in
# REQUIRED_FILES and not in SHARED_TEST_FILES. Absent means "nothing this task
# asks for removes a bootstrap commit", which is true of most tasks, and keeping
# it absent rather than shipping an empty file per task is what makes the set of tasks
# that DO claim an exemption reviewable at a glance. Unlike
# tests/bootstrap_anchor.json it IS committed: it describes the task, not one
# image build. The schema is enforced below; whether each entry actually names
# one bootstrap commit needs a measurement and is checked by
# scripts/bootstrap_anchor.py --write/--check.
EXEMPTIONS_FILE = "tests/anchor_exemptions.json"
EXEMPTION_LISTS = ("may_disappear", "may_be_divergent")
EXEMPTION_KEYS = ("task", "may_disappear", "may_be_divergent", "maintained_by")

# (table path, key) pairs that must be present in task.toml.
REQUIRED_TOML_KEYS = (
    ("verifier", "timeout_sec"),
    ("agent", "timeout_sec"),
    ("environment", "cpus"),
    ("environment", "memory_mb"),
    ("environment", "network_mode"),
    ("agent", "network_mode"),
    ("verifier", "network_mode"),
)

# Phases whose network_mode is tallied in the inventory, in report order.
NETWORK_MODE_PHASES = ("environment", "agent", "verifier")

# There is deliberately no required-sections rule for instruction.md.
#
# There used to be one -- every instruction had to carry "## Requirements" and
# "## Background" -- together with a named exemption list, REWRITTEN_PROMPT_TASKS,
# for the tasks whose prompts had been rewritten out of the specification
# register and into a request in a user's voice. That list said of itself that it
# was expected "to disappear once it covers every task and the section rule can
# go", and after the cut to 14 it did cover every task: the rule guarded nothing
# and could not fail. That is worse than no rule, because it reads like a live
# check -- an instruction.md was once replaced with a single character and the
# lint still passed. Both went together.
#
# If a check on instruction content comes back, it has to be one that holds for a
# one-sentence request, because that is the register the whole suite is written
# in now. A heading requirement is not that check.

# e.g. "jj-v0.38.0-x86_64-unknown-linux-musl.tar.gz" -> "0.38.0"
JJ_VERSION_RE = re.compile(r"jj-v(\d+\.\d+\.\d+)")

# tests/test.sh runs `python3 -m pytest --ctrf ...` and installs nothing, so
# every image has to carry these already. The pins live in one Dockerfile per task;
# this check is what stops one of them being bumped or dropped on its own and
# only surfacing as a task that mysteriously errors mid-sweep.
VERIFIER_DEPS = ("pytest==8.4.1", "pytest-json-ctrf==0.3.5")

# tests/vacuity_floor.json names the tests in tests/test_final_state.py that
# pass on the untouched bootstrap image, with no agent having run. tests/test.sh
# excludes those names from both sides of the partial-credit fraction, which is
# the only reason a nop agent still scores exactly 0 -- the only tests it passes
# are the floored ones. The file is a measurement, not an opinion: it comes from
# scripts/vacuity_floor.py --write and are re-measured in CI with --check.
# This lint cannot re-measure them (no containers), so it checks the cheap
# things -- shape, internal consistency, and staleness against the test count.
FLOOR_NAME = "tests/vacuity_floor.json"
FLOOR_KEYS = ("task", "tests", "floor", "passes_without_agent", "generated_by")
FLOOR_GENERATOR = "scripts/vacuity_floor.py"

# e.g. "def test_topology_restored():" at the start of a line.
TEST_FUNC_RE = re.compile(r"^\s*def (test_\w+)\s*\(", re.MULTILINE)


class Findings:
    """Collects per-task hard failures so we can report all of them at once."""

    def __init__(self) -> None:
        self.errors: dict[str, list[str]] = defaultdict(list)

    def fail(self, task: str, message: str) -> None:
        self.errors[task].append(message)

    @property
    def ok(self) -> bool:
        return not self.errors

    def report(self) -> None:
        if self.ok:
            return
        n = sum(len(v) for v in self.errors.values())
        print(f"\nFAIL: {n} problem(s) across {len(self.errors)} task(s)\n")
        for task in sorted(self.errors):
            print(f"  {task}")
            for message in self.errors[task]:
                print(f"    - {message}")


def check_required_files(task: str, task_dir: Path, findings: Findings) -> None:
    for rel in REQUIRED_FILES:
        if not (task_dir / rel).is_file():
            findings.fail(task, f"missing required file: {rel}")


def check_task_toml(task: str, task_dir: Path, findings: Findings) -> dict:
    path = task_dir / "task.toml"
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as fh:
            config = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        findings.fail(task, f"task.toml does not parse: {exc}")
        return {}

    for table, key in REQUIRED_TOML_KEYS:
        section = config.get(table)
        if not isinstance(section, dict):
            findings.fail(task, f"task.toml is missing the [{table}] table")
            continue
        if key not in section:
            findings.fail(task, f"task.toml is missing [{table}] {key}")

    # An allowlist with nothing on it is a silent no-network: the mode says
    # "some egress is expected" while the effective policy denies all of it.
    agent = config.get("agent")
    if isinstance(agent, dict) and agent.get("network_mode") == "allowlist":
        hosts = agent.get("allowed_hosts")
        if not isinstance(hosts, list) or not hosts:
            findings.fail(
                task,
                'task.toml sets [agent] network_mode = "allowlist" but '
                "[agent] allowed_hosts is missing or empty",
            )
    return config


def read_instruction(task_dir: Path) -> str:
    """The prompt text, for the drift check against bootstrap/task.json.

    Nothing about the instruction's own shape is asserted here -- see the note
    above JJ_VERSION_RE on why the required-sections rule was retired. A missing
    file is reported by check_required_files, and what the text has to match is
    checked by check_task_json.
    """
    path = task_dir / "instruction.md"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def check_task_json(task: str, task_dir: Path, instruction: str, findings: Findings) -> None:
    """bootstrap/task.json duplicates instruction.md in its task_description.

    That duplication is what the harness actually hands the agent, so a task
    can be edited, reviewed and merged while the agent keeps being prompted
    with the superseded text -- silently, because nothing else reads the JSON.
    Three files had already drifted this way before the check existed. The
    fix is never to hand-edit the JSON: regenerate the field from
    instruction.md.
    """
    path = task_dir / "bootstrap/task.json"
    if not path.is_file() or not (task_dir / "instruction.md").is_file():
        return  # already reported by check_required_files
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        findings.fail(task, f"bootstrap/task.json does not parse: {exc}")
        return
    if not isinstance(data, dict):
        findings.fail(task, "bootstrap/task.json is not a JSON object")
        return

    if data.get("task_name") != task:
        findings.fail(
            task,
            f"bootstrap/task.json task_name is {data.get('task_name')!r}, "
            f"expected {task!r}",
        )

    if "task_description" not in data:
        findings.fail(task, "bootstrap/task.json is missing task_description")
        return
    if data["task_description"] != instruction:
        findings.fail(
            task,
            "bootstrap/task.json task_description has drifted from "
            "instruction.md -- regenerate the field from the file rather than "
            "editing the JSON by hand",
        )


def check_dockerfile(task: str, task_dir: Path, findings: Findings) -> str | None:
    """Returns the jj version this task pins, or None if it could not be read."""
    path = task_dir / "environment/Dockerfile"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")

    if not re.search(r"^\s*FROM\s+\S+", text, re.MULTILINE | re.IGNORECASE):
        findings.fail(task, "environment/Dockerfile has no FROM instruction")

    for dep in VERIFIER_DEPS:
        if dep not in text:
            findings.fail(
                task,
                f"environment/Dockerfile does not install {dep}; tests/test.sh "
                "runs pytest straight out of the image and installs nothing",
            )

    versions = set(JJ_VERSION_RE.findall(text))
    if not versions:
        findings.fail(task, "environment/Dockerfile does not pin a jj-v<X.Y.Z> release")
        return None
    if len(versions) > 1:
        findings.fail(
            task,
            f"environment/Dockerfile pins multiple jj versions: {sorted(versions)}",
        )
        return None
    return versions.pop()


def check_jj_versions_agree(pinned: dict[str, str], findings: Findings) -> str | None:
    """All tasks must pin the same jj release; minority pins are the failure."""
    if not pinned:
        return None
    counts = Counter(pinned.values())
    if len(counts) == 1:
        return next(iter(counts))
    consensus, _ = counts.most_common(1)[0]
    for task, version in sorted(pinned.items()):
        if version != consensus:
            findings.fail(
                task,
                f"pins jj v{version} but {counts[consensus]} other task(s) pin "
                f"v{consensus} -- task environments must agree",
            )
    return consensus


def check_shared_file_identical(
    rel: str, digests: dict[str, str], findings: Findings
) -> bool:
    """A shared verifier file is copied to every task; drift is a bug.

    Returns True when every copy agrees (or there are none to compare).
    """
    if not digests:
        return True
    counts = Counter(digests.values())
    if len(counts) == 1:
        return True
    consensus, _ = counts.most_common(1)[0]
    for task, digest in sorted(digests.items()):
        if digest != consensus:
            findings.fail(
                task,
                f"{rel} differs from the shared copy used by "
                f"{counts[consensus]} other task(s) (sha256 {digest[:12]} vs "
                f"{consensus[:12]})",
            )
    return False


def check_vacuity_floor(task: str, task_dir: Path, findings: Findings) -> dict | None:
    """tests/vacuity_floor.json must be well formed and not stale.

    Returns the parsed record, or None if it could not be used. The named tests
    are excluded from both sides of the partial-credit fraction in tests/test.sh,
    so a floor naming too much shrinks the denominator and inflates every
    model's score, and one naming too little pays a nop agent. Only a container
    run can measure which names belong in it (scripts/vacuity_floor.py); what is
    checkable here is that the file is shaped right and still describes the test
    file next to it.
    """
    path = task_dir / FLOOR_NAME
    test_file = task_dir / "tests/test_final_state.py"
    if not path.is_file():
        return None  # already reported by check_required_files
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        findings.fail(task, f"{FLOOR_NAME} does not parse: {exc}")
        return None
    if not isinstance(record, dict):
        findings.fail(task, f"{FLOOR_NAME} is not a JSON object")
        return None

    missing = [key for key in FLOOR_KEYS if key not in record]
    if missing:
        findings.fail(task, f"{FLOOR_NAME} is missing key(s): {', '.join(missing)}")
        return None

    if record["task"] != task:
        findings.fail(
            task,
            f"{FLOOR_NAME} records task {record['task']!r}, expected {task!r} -- "
            "the file was copied from another task rather than measured",
        )

    if record["generated_by"] != FLOOR_GENERATOR:
        findings.fail(
            task,
            f"{FLOOR_NAME} generated_by is {record['generated_by']!r}, expected "
            f"{FLOOR_GENERATOR!r}. Floors are measured, never hand-written: run "
            f"{FLOOR_GENERATOR} --write --task {task}",
        )

    names = record["passes_without_agent"]
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        findings.fail(task, f"{FLOOR_NAME} passes_without_agent is not a list of strings")
        return None
    if len(set(names)) != len(names):
        findings.fail(task, f"{FLOOR_NAME} passes_without_agent has duplicate entries")

    total, floor = record["tests"], record["floor"]
    for key, value in (("tests", total), ("floor", floor)):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            findings.fail(task, f"{FLOOR_NAME} {key} is not a non-negative integer")
            return None

    if floor != len(names):
        findings.fail(
            task,
            f"{FLOOR_NAME} says floor {floor} but lists {len(names)} test(s) in "
            "passes_without_agent -- the two disagree, so one of them is edited "
            "by hand",
        )

    if floor >= total > 0:
        findings.fail(
            task,
            f"{FLOOR_NAME} says all {total} test(s) pass with no agent. No floor "
            "can rescue that: tests/test_final_state.py measures nothing the "
            "agent has to do.",
        )

    if not test_file.is_file():
        return record  # already reported by check_required_files
    defined = TEST_FUNC_RE.findall(test_file.read_text(encoding="utf-8"))
    if total != len(defined):
        findings.fail(
            task,
            f"{FLOOR_NAME} was measured against {total} test(s) but "
            f"tests/test_final_state.py now defines {len(defined)} -- the floor "
            f"is stale. Re-measure with {FLOOR_GENERATOR} --write --task {task}",
        )
    unknown = sorted(n for n in names if n.rsplit("::", 1)[-1] not in set(defined))
    if unknown:
        findings.fail(
            task,
            f"{FLOOR_NAME} lists test(s) that tests/test_final_state.py does not "
            f"define: {', '.join(unknown)} -- the floor is stale",
        )
    return record


def check_test_sh_reads_floor(task: str, task_dir: Path, findings: Findings) -> None:
    """The shared test.sh is what applies the floor; it must still read it.

    Without this, reverting test.sh to the old 0/1 script (or to a naive
    passed/tests fraction) leaves a floor file per task in the tree that
    nothing consults, and the lint stays green because all the copies still
    agree.
    """
    path = task_dir / "tests/test.sh"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if "vacuity_floor.json" not in text:
        findings.fail(
            task,
            "tests/test.sh does not read vacuity_floor.json, so the no-agent "
            "floor is not being excluded and partial credit would pay a nop "
            "agent",
        )


def check_conftest_applies_anchor(task: str, task_dir: Path, findings: Findings) -> None:
    """tests/conftest.py is what makes the anchor apply without a per-task edit.

    Same argument as check_test_sh_reads_floor: byte-identical copies of a
    conftest.py that no longer runs the check would leave the lint green while
    every verifier silently stopped detecting a rebuilt repository. So assert the
    two properties that make it work at all -- it calls the assertion, and it does
    so from an AUTOUSE fixture. Autouse is load-bearing: written as a test
    function the assertion would pass on the untouched image, land in
    tests/vacuity_floor.json, and then be excluded from both sides of the
    partial-credit fraction, so a detected cheat would still score
    (scored-1)/scored instead of 0.
    """
    path = task_dir / "tests/conftest.py"
    if not path.is_file():
        return  # already reported by check_required_files
    text = path.read_text(encoding="utf-8")
    if "assert_bootstrap_anchor" not in text:
        findings.fail(
            task,
            "tests/conftest.py does not call assert_bootstrap_anchor, so this "
            "task's verifier cannot tell a solved repository from a rebuilt one",
        )
    if "autouse=True" not in text:
        findings.fail(
            task,
            "tests/conftest.py has no autouse=True fixture, so the bootstrap "
            "anchor is not applied unless a test opts in",
        )


def check_anchor_exemptions(task: str, task_dir: Path,
                            findings: Findings) -> dict | None:
    """Validate tests/anchor_exemptions.json, the one hand-written anchor input.

    Every other anchor artefact is measured; this one is a human judgement about
    what a task's instruction.md asks for, and it WEAKENS the integrity check for
    the commits it names. So the schema is enforced hard, and above all the
    `reason` is: an exemption without a reason is an unreviewable hole, and the
    file exists to be read by the next person who wonders why a commit is allowed
    to vanish.

    Returns the parsed record for the inventory, or None when there is no file
    (the normal case) or it is unusable (already reported).
    """
    path = task_dir / EXEMPTIONS_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        findings.fail(task, f"{EXEMPTIONS_FILE} does not parse: {exc}")
        return None
    if not isinstance(data, dict):
        findings.fail(task, f"{EXEMPTIONS_FILE} is not a JSON object")
        return None

    for key in EXEMPTION_KEYS:
        if key not in data:
            findings.fail(task, f"{EXEMPTIONS_FILE} is missing the {key!r} key")
    unknown = sorted(set(data) - set(EXEMPTION_KEYS))
    if unknown:
        findings.fail(
            task,
            f"{EXEMPTIONS_FILE} has unknown key(s) {', '.join(unknown)}; "
            f"tests/anchor.py reads only {', '.join(EXEMPTION_KEYS)}",
        )
    if data.get("task") != task:
        findings.fail(
            task,
            f"{EXEMPTIONS_FILE} records task {data.get('task')!r}, not {task!r}",
        )
    if not isinstance(data.get("maintained_by"), str) or not data.get("maintained_by"):
        findings.fail(
            task, f"{EXEMPTIONS_FILE} needs a non-empty 'maintained_by' string"
        )

    total = 0
    for key in EXEMPTION_LISTS:
        entries = data.get(key, [])
        if not isinstance(entries, list):
            findings.fail(task, f"{EXEMPTIONS_FILE}: {key!r} is not a list")
            continue
        seen: set[tuple[str, str]] = set()
        for entry in entries:
            total += 1
            if not isinstance(entry, dict):
                findings.fail(
                    task, f"{EXEMPTIONS_FILE}: {key} contains a non-object entry"
                )
                continue
            named = [k for k in ("description", "working_copy") if k in entry]
            if len(named) != 1:
                findings.fail(
                    task,
                    f"{EXEMPTIONS_FILE}: an entry in {key} must have exactly one "
                    f"of 'description' or 'working_copy', not "
                    f"{named or 'neither'}",
                )
                continue
            value = entry[named[0]]
            if not isinstance(value, str):
                findings.fail(
                    task,
                    f"{EXEMPTIONS_FILE}: {key} entry {named[0]!r} is not a string",
                )
                continue
            if (named[0], value) in seen:
                findings.fail(
                    task,
                    f"{EXEMPTIONS_FILE}: {key} names {named[0]}={value!r} twice",
                )
            seen.add((named[0], value))
            reason = entry.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                findings.fail(
                    task,
                    f"{EXEMPTIONS_FILE}: the {key} entry for {named[0]}={value!r} "
                    "has no non-empty 'reason'. An exemption switches off the "
                    "integrity check for that commit, so it has to say in one "
                    "line why the task's asked-for work removes it.",
                )
    if total == 0:
        findings.fail(
            task,
            f"{EXEMPTIONS_FILE} exempts nothing. An empty file is not the same "
            "as no file to a reviewer, and tests/anchor.py treats an absent file "
            "as 'no exemptions' already -- delete it.",
        )
    return data


def print_inventory(
    instruction_sections: dict[str, str],
    network_modes: dict[str, Counter],
    jj_version: str | None,
    shared_uniform: dict[str, bool],
    floors: dict[str, dict],
    exemptions: dict[str, dict],
) -> None:
    """Non-fatal policy inventory. Drift here shows up as changed numbers."""
    buckets: dict[str, list[str]] = defaultdict(list)
    for task, kind in sorted(instruction_sections.items()):
        buckets[kind].append(task)

    print("\n" + "=" * 72)
    print("INVENTORY (informational -- these do not fail the lint)")
    print("=" * 72)

    print("\ninstruction.md implementation section:")
    print(f"  {'section':<26} {'count':>5}  tasks")
    for kind in ("## Implementation", "## Implementation Guide", "(neither)"):
        tasks = buckets.get(kind, [])
        listed = ", ".join(tasks) if tasks else "-"
        print(f"  {kind:<26} {len(tasks):>5}  {listed}")

    for phase in NETWORK_MODE_PHASES:
        counts = network_modes.get(phase, Counter())
        print(f"\n{phase}.network_mode:")
        if not counts:
            print(f"  {'(unset)':<26} {0:>5}")
            continue
        for value, count in sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0]))):
            print(f"  {str(value):<26} {count:>5}")

    # The no-agent floor is how much of each verifier is satisfied before the
    # agent does anything. Its distribution is the honest measure of how much
    # resolution partial credit actually buys: a task with tests - floor == 1
    # is still scored 0 or 1 no matter what the fraction says.
    print("\nno-agent floor (tests/vacuity_floor.json):")
    print(f"  {'scorable tests (tests - floor)':<32} {'tasks':>5}  tasks")
    buckets_by_width: dict[int, list[str]] = defaultdict(list)
    for task, record in sorted(floors.items()):
        buckets_by_width[record["tests"] - record["floor"]].append(task)
    for width in sorted(buckets_by_width):
        tasks = buckets_by_width[width]
        label = f"{width} (still 0/1)" if width <= 1 else str(width)
        print(f"  {label:<32} {len(tasks):>5}  {', '.join(tasks)}")
    nonzero = sorted(t for t, r in floors.items() if r["floor"])
    print(f"\n  tasks with a nonzero floor: {len(nonzero)}")
    for task in nonzero:
        record = floors[task]
        names = ", ".join(
            n.rsplit("::", 1)[-1] for n in record["passes_without_agent"]
        )
        print(f"    {task:<32} {record['floor']}/{record['tests']}  {names}")

    # Printed on every run for the same reason the floored tests are: an
    # exemption switches the integrity check off for one bootstrap commit, and a
    # hole nobody can see is a hole nobody reviews. The reasons are printed in
    # full -- they are one line each by construction.
    print("\nanchor exemptions (tests/anchor_exemptions.json, hand-written):")
    if not exemptions:
        print("  none -- every task's bootstrap commits are checked strictly")
    for task in sorted(exemptions):
        record = exemptions[task]
        for key in EXEMPTION_LISTS:
            for entry in record.get(key) or []:
                if not isinstance(entry, dict):
                    continue
                named = "description" if "description" in entry else "working_copy"
                print(f"  {task:<28} {key:<16} {named}="
                      f"{entry.get(named)!r}")
                print(f"    {str(entry.get('reason', '')).strip()}")
    print(f"  {len(exemptions)} of {len(floors)} task(s) claim an exemption")

    print("\npinned jj version: " + (f"v{jj_version}" if jj_version else "(unknown)"))
    print("shared verifier files:")
    for rel in SHARED_TEST_FILES:
        state = "identical across all tasks" if shared_uniform.get(rel, True) else "DRIFTED"
        print(f"  {rel:<26} {state}")


def main() -> int:
    if not TASKS_DIR.is_dir():
        print(f"error: {TASKS_DIR} does not exist", file=sys.stderr)
        return 1

    task_dirs = sorted(p for p in TASKS_DIR.iterdir() if p.is_dir())
    if not task_dirs:
        print(f"error: no task directories found under {TASKS_DIR}", file=sys.stderr)
        return 1

    findings = Findings()
    pinned_jj: dict[str, str] = {}
    shared_digests: dict[str, dict[str, str]] = {rel: {} for rel in SHARED_TEST_FILES}
    instruction_sections: dict[str, str] = {}
    network_modes: dict[str, Counter] = {p: Counter() for p in NETWORK_MODE_PHASES}
    floors: dict[str, dict] = {}
    exemptions: dict[str, dict] = {}

    for task_dir in task_dirs:
        task = task_dir.name
        check_required_files(task, task_dir, findings)

        config = check_task_toml(task, task_dir, findings)
        for phase in NETWORK_MODE_PHASES:
            section = config.get(phase)
            if isinstance(section, dict) and "network_mode" in section:
                network_modes[phase][section["network_mode"]] += 1

        text = read_instruction(task_dir)
        check_task_json(task, task_dir, text, findings)
        if "## Implementation Guide" in text:
            instruction_sections[task] = "## Implementation Guide"
        elif "## Implementation" in text:
            instruction_sections[task] = "## Implementation"
        else:
            instruction_sections[task] = "(neither)"

        version = check_dockerfile(task, task_dir, findings)
        if version:
            pinned_jj[task] = version

        record = check_vacuity_floor(task, task_dir, findings)
        if record is not None:
            floors[task] = record
        check_test_sh_reads_floor(task, task_dir, findings)
        check_conftest_applies_anchor(task, task_dir, findings)
        exempt = check_anchor_exemptions(task, task_dir, findings)
        if exempt is not None:
            exemptions[task] = exempt

        for rel in SHARED_TEST_FILES:
            path = task_dir / rel
            if path.is_file():
                shared_digests[rel][task] = hashlib.sha256(path.read_bytes()).hexdigest()

    consensus_jj = check_jj_versions_agree(pinned_jj, findings)
    shared_uniform = {
        rel: check_shared_file_identical(rel, shared_digests[rel], findings)
        for rel in SHARED_TEST_FILES
    }

    print(f"Linted {len(task_dirs)} task(s) under {TASKS_DIR.relative_to(REPO_ROOT)}/")
    print_inventory(
        instruction_sections,
        network_modes,
        consensus_jj,
        shared_uniform=shared_uniform,
        floors=floors,
        exemptions=exemptions,
    )

    findings.report()
    if findings.ok:
        print(f"\nOK: all {len(task_dirs)} task(s) passed the schema lint.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
