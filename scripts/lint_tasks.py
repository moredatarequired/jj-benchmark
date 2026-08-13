#!/usr/bin/env python3
"""Schema lint for the task definitions under tasks/.

Pure stdlib, no containers, runs in about a second. It catches the cheap
structural mistakes that would otherwise only surface once a full benchmark
run has burned an hour of GPU-free-but-not-free CI time:

  * a task missing one of the seven files the harness expects
  * a task.toml that does not parse, or that omits a timeout / resource knob
  * an instruction.md missing the sections agents are told to rely on
  * a bootstrap/task.json whose task_description has drifted from instruction.md
  * a Dockerfile pinning a different jj version from every other task
  * a Dockerfile that does not bake in the pinned verifier dependencies
  * a tests/test.sh, tests/anchor.py or tests/conftest.py that has drifted out
    of sync with its 52 identical siblings
  * a tests/conftest.py that no longer applies the bootstrap integrity anchor
  * a tests/anchor_exemptions.json (optional, hand-written) that does not follow
    the schema, or that exempts a bootstrap commit without saying why
  * a tests/vacuity_floor.json that is missing, malformed, or stale with
    respect to the tests defined in tests/test_final_state.py
  * a prompt-variant task (tasks/<base>_terse/) that has drifted from its base
    task anywhere other than instruction.md

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

# Shared verifier infrastructure: copied verbatim into all 53 tasks, because
# harbor mounts only one task's tests/ directory at /tests and there is nowhere
# else for a shared module to live. Divergence between copies is always a bug --
# it means one task is being verified by different code from the other 52.
SHARED_TEST_FILES = ("tests/test.sh", "tests/anchor.py", "tests/conftest.py")

# tests/anchor_exemptions.json is OPTIONAL and per-task, so it is not in
# REQUIRED_FILES and not in SHARED_TEST_FILES. Absent means "nothing this task
# asks for removes a bootstrap commit", which is true of most tasks, and keeping
# it absent rather than shipping 53 empty files is what makes the set of tasks
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

# Sections instructions must carry. Agents are prompted against these.
REQUIRED_INSTRUCTION_SECTIONS = ("## Requirements", "## Background")

# Tasks whose instruction.md has been rewritten out of the specification
# register and into a request in a user's voice -- the register the tasks/
# <base>_terse/ arms were built to try out, now adopted as the task itself.
#
# The section rule below exists to stop a task shipping with an instruction that
# forgets to say what is wanted. These prompts say it in one or two sentences,
# so a "## Requirements" heading over them would put back exactly the shape they
# were rewritten to remove -- the same reason variant_base() is exempted. The
# exemption is a NAMED LIST rather than a "short instructions are exempt" rule
# so that a task cannot fall out of the section check by accident: dropping the
# sections from any task not written here still fails CI.
#
# The list is expected to grow as the rest of the suite is rewritten, and to
# disappear once it covers every task and the section rule can go.
REWRITTEN_PROMPT_TASKS = frozenset({
    "abandon_commits",
    "absorb_changes",
    "edit_commit_message",
    "git_fetch_remote",
    "operation_recovery",
    "rebase_branch",
    "restore_interactive",
    "split_commit_interactive",
    "squash_range",
    "template_customize_log_output",
    "track_untracked_file",
    "undo_mistaken_rebase",
    "workspace_add",
    "workspace_update_stale",
})

# ---------------------------------------------------------------------------
# Prompt-variant arms
# ---------------------------------------------------------------------------
#
# tasks/<base>_terse/ is a second arm of tasks/<base>/ whose ONLY difference is
# instruction.md: a short request in a user's voice instead of a specification
# written against the verifier. It exists to measure how much of this suite's
# saturation comes from the prompt handing over the fixture and the
# discriminating hint, so the two arms have to share one fixture and one
# verifier exactly -- otherwise the comparison measures the copy as well as the
# prompt. check_variant_identity() is what makes that a property CI enforces
# rather than one a copy is hoped to have preserved, and it is also what makes
# it sound for .github/workflows/tasks.yml to keep the variants out of the
# nightly container matrix: their images and their tests are provably the base
# task's.
VARIANT_SUFFIX = "_terse"

# instruction.md is the variable under test, and bootstrap/task.json carries a
# byte copy of it (check_task_json).
VARIANT_FREE_FILES = ("instruction.md",)

# JSON files that must be identical apart from the keys that name the task.
# Every one of these values is checked against the directory name elsewhere in
# this file, so here it is only the REST of the object that has to agree.
VARIANT_RESTAMPED = {
    "bootstrap/task.json": ("task_name", "task_description"),
    "tests/vacuity_floor.json": ("task",),
    EXEMPTIONS_FILE: ("task",),
}

# Per-build artifact: gitignored, present only between a
# `scripts/bootstrap_anchor.py --write` and the sweep that consumes it, and
# different in every build by construction. Not part of the comparison.
VARIANT_IGNORED = ("tests/bootstrap_anchor.json",)

# e.g. "jj-v0.38.0-x86_64-unknown-linux-musl.tar.gz" -> "0.38.0"
JJ_VERSION_RE = re.compile(r"jj-v(\d+\.\d+\.\d+)")

# tests/test.sh runs `python3 -m pytest --ctrf ...` and installs nothing, so
# every image has to carry these already. The pins live in 53 Dockerfiles;
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


def variant_base(task: str) -> str | None:
    """The task a prompt variant is an arm of, or None if it is not one."""
    if task.endswith(VARIANT_SUFFIX) and len(task) > len(VARIANT_SUFFIX):
        return task[: -len(VARIANT_SUFFIX)]
    return None


def check_instruction(task: str, task_dir: Path, findings: Findings) -> str:
    path = task_dir / "instruction.md"
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    if variant_base(task) or task in REWRITTEN_PROMPT_TASKS:
        # The whole point of the variant arm -- and now of the rewritten base
        # tasks in REWRITTEN_PROMPT_TASKS -- is an instruction that is NOT
        # shaped like a specification. A "## Requirements" heading over a
        # one-sentence request would reintroduce the register they exist to
        # remove, so the section requirement does not apply to them. Nothing
        # else is relaxed: check_variant_identity() holds the rest of a
        # variant's directory to the base task byte for byte.
        return text
    for section in REQUIRED_INSTRUCTION_SECTIONS:
        # Match at line start so a mention in prose does not satisfy the check.
        if not re.search(rf"^{re.escape(section)}\s*$", text, re.MULTILINE):
            findings.fail(task, f"instruction.md is missing a '{section}' section")
    return text


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
    passed/tests fraction) leaves 53 floor files in the tree that nothing
    consults, and the lint stays green because all 53 copies still agree.
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
    """tests/conftest.py is what makes the anchor apply without 53 edits.

    Same argument as check_test_sh_reads_floor: 53 byte-identical copies of a
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


def task_files(task_dir: Path) -> set[str]:
    """Every file in a task directory, as a path relative to it."""
    return {
        str(p.relative_to(task_dir))
        for p in task_dir.rglob("*")
        if p.is_file() and str(p.relative_to(task_dir)) not in VARIANT_IGNORED
    }


def check_variant_identity(task: str, task_dir: Path, findings: Findings) -> str | None:
    """A prompt variant must be its base task plus a different instruction.md.

    This is the scientific control of the two-arm comparison, so it is a hard
    check rather than a convention. If the arms' environment/ directories drift
    apart they are no longer the same fixture (the bootstrap change ids are per
    image build, and identical build contexts are what makes the variant's build
    a cache hit off the base's); if their tests/ drift apart the two arms are
    graded by different code and the difference in scores is not the prompt.
    Both would be invisible in the results.

    Returns the base task name for the inventory, or None when this is not a
    variant.
    """
    base = variant_base(task)
    if base is None:
        return None
    base_dir = TASKS_DIR / base
    if not base_dir.is_dir():
        findings.fail(
            task,
            f"is named as a prompt variant of {base!r} but tasks/{base}/ does "
            "not exist. A variant that is not an arm of anything is just a task "
            f"with a {VARIANT_SUFFIX!r} suffix.",
        )
        return None

    here, there = task_files(task_dir), task_files(base_dir)
    for rel in sorted(there - here):
        findings.fail(task, f"is missing {rel}, which tasks/{base}/ has")
    for rel in sorted(here - there):
        findings.fail(
            task,
            f"has {rel}, which tasks/{base}/ does not. A variant differs from "
            "its base task in instruction.md and nothing else.",
        )

    for rel in sorted(here & there):
        if rel in VARIANT_FREE_FILES:
            continue
        mine, theirs = task_dir / rel, base_dir / rel
        if rel in VARIANT_RESTAMPED:
            try:
                a = json.loads(mine.read_text(encoding="utf-8"))
                b = json.loads(theirs.read_text(encoding="utf-8"))
            except ValueError:
                continue  # already reported by the per-file checks
            if not isinstance(a, dict) or not isinstance(b, dict):
                continue
            for key in VARIANT_RESTAMPED[rel]:
                a.pop(key, None)
                b.pop(key, None)
            if a != b:
                findings.fail(
                    task,
                    f"{rel} differs from tasks/{base}/{rel} in more than "
                    f"{', '.join(VARIANT_RESTAMPED[rel])}. Only the fields that "
                    "name the task may be re-stamped in a variant.",
                )
            continue
        if mine.read_bytes() != theirs.read_bytes():
            findings.fail(
                task,
                f"{rel} is not byte-identical to tasks/{base}/{rel}. The two "
                "arms must share one fixture and one verifier, or the "
                "difference between their scores is not the prompt.",
            )
    return base


def print_inventory(
    instruction_sections: dict[str, str],
    network_modes: dict[str, Counter],
    jj_version: str | None,
    shared_uniform: dict[str, bool],
    floors: dict[str, dict],
    exemptions: dict[str, dict],
    variants: dict[str, str],
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

    # The prompt-variant arms. Printed because "which tasks exist in two
    # prompt registers" is exactly the kind of thing that should be visible in
    # the CI log rather than inferred from directory names.
    print(f"\nprompt variants ({VARIANT_SUFFIX}, verified identical to their base "
          "task apart from instruction.md):")
    if not variants:
        print("  none")
    for task in sorted(variants):
        print(f"  {task:<36} arm of {variants[task]}")

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
    variants: dict[str, str] = {}

    for task_dir in task_dirs:
        task = task_dir.name
        check_required_files(task, task_dir, findings)

        config = check_task_toml(task, task_dir, findings)
        for phase in NETWORK_MODE_PHASES:
            section = config.get(phase)
            if isinstance(section, dict) and "network_mode" in section:
                network_modes[phase][section["network_mode"]] += 1

        text = check_instruction(task, task_dir, findings)
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
        base = check_variant_identity(task, task_dir, findings)
        if base is not None:
            variants[task] = base

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
        variants=variants,
    )

    findings.report()
    if findings.ok:
        print(f"\nOK: all {len(task_dirs)} task(s) passed the schema lint.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
