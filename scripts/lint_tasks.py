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
  * a tests/test.sh that has drifted out of sync with its 52 identical siblings

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
REQUIRED_FILES = (
    "instruction.md",
    "task.toml",
    "bootstrap/task.json",
    "bootstrap/test_initial_state.py",
    "environment/Dockerfile",
    "tests/test.sh",
    "tests/test_final_state.py",
)

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

# e.g. "jj-v0.38.0-x86_64-unknown-linux-musl.tar.gz" -> "0.38.0"
JJ_VERSION_RE = re.compile(r"jj-v(\d+\.\d+\.\d+)")

# tests/test.sh runs `python3 -m pytest --ctrf ...` and installs nothing, so
# every image has to carry these already. The pins live in 53 Dockerfiles;
# this check is what stops one of them being bumped or dropped on its own and
# only surfacing as a task that mysteriously errors mid-sweep.
VERIFIER_DEPS = ("pytest==8.4.1", "pytest-json-ctrf==0.3.5")


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


def check_instruction(task: str, task_dir: Path, findings: Findings) -> str:
    path = task_dir / "instruction.md"
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
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


def check_test_sh_identical(digests: dict[str, str], findings: Findings) -> None:
    """tests/test.sh is boilerplate copied to every task; drift is a bug."""
    if not digests:
        return
    counts = Counter(digests.values())
    if len(counts) == 1:
        return
    consensus, _ = counts.most_common(1)[0]
    for task, digest in sorted(digests.items()):
        if digest != consensus:
            findings.fail(
                task,
                "tests/test.sh differs from the shared copy used by "
                f"{counts[consensus]} other task(s) (sha256 {digest[:12]} vs "
                f"{consensus[:12]})",
            )


def print_inventory(
    instruction_sections: dict[str, str],
    network_modes: dict[str, Counter],
    jj_version: str | None,
    test_sh_uniform: bool,
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

    print("\npinned jj version: " + (f"v{jj_version}" if jj_version else "(unknown)"))
    print(
        "tests/test.sh:     "
        + ("identical across all tasks" if test_sh_uniform else "DRIFTED")
    )


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
    test_sh_digests: dict[str, str] = {}
    instruction_sections: dict[str, str] = {}
    network_modes: dict[str, Counter] = {p: Counter() for p in NETWORK_MODE_PHASES}

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

        test_sh = task_dir / "tests/test.sh"
        if test_sh.is_file():
            test_sh_digests[task] = hashlib.sha256(test_sh.read_bytes()).hexdigest()

    consensus_jj = check_jj_versions_agree(pinned_jj, findings)
    check_test_sh_identical(test_sh_digests, findings)

    print(f"Linted {len(task_dirs)} task(s) under {TASKS_DIR.relative_to(REPO_ROOT)}/")
    print_inventory(
        instruction_sections,
        network_modes,
        consensus_jj,
        test_sh_uniform=len(set(test_sh_digests.values())) <= 1,
    )

    findings.report()
    if findings.ok:
        print(f"\nOK: all {len(task_dirs)} task(s) passed the schema lint.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
