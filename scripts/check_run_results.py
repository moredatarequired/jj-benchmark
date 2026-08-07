#!/usr/bin/env python3
"""Post-run audit of a harbor run: separate real failures from broken verifiers.

Usage:

    python3 scripts/check_run_results.py <dir> [<dir> ...]
    python3 scripts/check_run_results.py jobs/2026-08-07__10-11-12
    python3 scripts/check_run_results.py jobs/            # every job at once
    python3 scripts/check_run_results.py jobs/ --quiet    # only the bad trials

Point it at a job directory (the one holding the per-trial directories), at the
jobs/ root, or at any directory above them -- it walks down looking for
trials, so all three work. Exit status is 0 when every trial produced a real
verdict, 1 when any trial errored, and 2 when no trials were found at all.

Why this exists
---------------

`reward: 0.0` in a trial's result.json means two very different things and
harbor does not distinguish them:

  1. the agent tried and the verifier said no -- a real, countable failure;
  2. the verifier never ran, because its own `uv` dependency install could not
     reach pypi.

In case 2 harbor still writes `reward: 0.0`, and it writes it with
`n_errors: 0`, `exception_stats: {}` and `n_errored_trials: 0` -- the run looks
clean. Two trials of one of our haiku sweeps were lost this way. A sweep with
that in it does not just lose a data point, it reports a wrong number and gives
no sign that it did.

The tell is in the artifacts rather than the result: a verifier that actually
ran writes `verifier/ctrf.json`, and one that got as far as pytest has
`test session starts` in `verifier/test-stdout.txt`. So:

  PASS          reward 1.0, ctrf.json present.
  FAIL          reward 0.0, ctrf.json present. The agent really did fail.
  ERRORED-INFRA no ctrf.json (or no result.json, or harbor recorded an
                exception). The verifier did not deliver a verdict, so the
                reward on this trial means nothing. Fatal.

A `verifier/test-stdout.txt` with no `test session starts` in it is reported as
corroborating evidence, but on its own it is only a warning -- some harbor
configurations do not capture that file at all, and a missing log is much
weaker evidence than a missing report.

Pure stdlib, reads only. Safe to run against a directory with mixed results,
partially-written trials, or no trials at all.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Written by `pytest --ctrf` in tests/test.sh. Its absence is the assertion.
CTRF_NAME = "verifier/ctrf.json"

# Captured pytest stdout, and the banner pytest prints once collection starts.
STDOUT_NAME = "verifier/test-stdout.txt"
PYTEST_BANNER = "test session starts"

PASS = "PASS"
FAIL = "FAIL"
ERRORED = "ERRORED-INFRA"

# reward is a float; harbor writes 1.0 for a clean pass.
PASS_REWARD = 1.0


@dataclass
class Trial:
    """One <job>/<trial>/ directory."""

    path: Path
    task: str = "?"
    model: str = "?"
    reward: float | None = None
    verdict: str = ERRORED
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def errored(self) -> bool:
        return self.verdict == ERRORED

    @property
    def reward_str(self) -> str:
        return "-" if self.reward is None else f"{self.reward:g}"


def is_trial_result(path: Path) -> bool:
    """True if this result.json is a trial's, not a job's.

    Harbor writes a result.json at the job root too, holding only aggregate
    counters (`n_total_trials`, `stats`). It has no verifier section, so
    treating it as a trial reports the whole job as one errored trial and hides
    the real ones. A trial's result.json always names its trial.
    """
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        # Unreadable or truncated: let classify() report it properly.
        return True
    if not isinstance(data, dict):
        return True
    return "trial_name" in data or "verifier_result" in data


def find_trials(root: Path) -> list[Path]:
    """Every trial directory at or under `root`.

    A trial is a directory holding a trial-shaped result.json, or -- so that a
    trial which died before writing one is counted rather than silently
    skipped -- one holding a verifier/ directory. Walking rather than globbing
    a fixed depth is what lets the same command take a single job, the jobs/
    root, or a run directory that nests them.
    """
    if not root.is_dir():
        return []
    if (root / "result.json").is_file() and is_trial_result(root / "result.json"):
        return [root]
    found = {
        p.parent
        for p in root.rglob("result.json")
        if p.is_file() and is_trial_result(p)
    }
    found |= {p.parent for p in root.rglob("verifier") if p.is_dir()}
    return sorted(found)


def load_result(trial_dir: Path) -> tuple[dict, str | None]:
    """Parse result.json. Returns ({}, reason) if it cannot be used."""
    result_path = trial_dir / "result.json"
    try:
        data = json.loads(result_path.read_text())
    except FileNotFoundError:
        return {}, "no result.json -- the trial did not finish"
    except json.JSONDecodeError as exc:
        return {}, f"result.json is not valid JSON ({exc.msg}) -- trial truncated?"
    except OSError as exc:
        return {}, f"result.json is unreadable ({exc.strerror})"
    if not isinstance(data, dict):
        return {}, "result.json is not an object"
    return data, None


def read_model(data: dict) -> str:
    """Model name, from either of the two places harbor records it."""
    config = data.get("config") or {}
    agent = config.get("agent") or {}
    model = agent.get("model_name")
    if model:
        return str(model)
    agent_info = data.get("agent_info") or {}
    model_info = agent_info.get("model_info") or {}
    return str(model_info.get("name") or "?")


def read_reward(data: dict) -> float | None:
    rewards = ((data.get("verifier_result") or {}).get("rewards")) or {}
    reward = rewards.get("reward")
    if isinstance(reward, (int, float)) and not isinstance(reward, bool):
        return float(reward)
    return None


def stdout_evidence(trial_dir: Path) -> str | None:
    """Corroborating note about test-stdout.txt, or None if it looks normal."""
    stdout_path = trial_dir / STDOUT_NAME
    if not stdout_path.is_file():
        return f"no {STDOUT_NAME}"
    try:
        text = stdout_path.read_text(errors="replace")
    except OSError as exc:
        return f"{STDOUT_NAME} is unreadable ({exc.strerror})"
    if PYTEST_BANNER not in text:
        return f"{STDOUT_NAME} never reaches {PYTEST_BANNER!r} -- pytest never started"
    return None


def classify(trial_dir: Path) -> Trial:
    """Decide PASS / FAIL / ERRORED-INFRA for one trial directory."""
    trial = Trial(path=trial_dir)

    data, load_error = load_result(trial_dir)
    if load_error:
        trial.reasons.append(load_error)
    else:
        trial.task = str(data.get("task_name") or trial_dir.parent.name or "?")
        trial.model = read_model(data)
        trial.reward = read_reward(data)

    has_ctrf = (trial_dir / CTRF_NAME).is_file()
    if not has_ctrf:
        trial.reasons.append(
            f"no {CTRF_NAME} -- the verifier never produced a report, so its "
            "reward is not a measurement"
        )

    # Harbor's own error channel. Present it, but do not rely on it: the whole
    # point of this script is that it stays empty for the failure we care about.
    if data.get("exception_info"):
        trial.reasons.append("harbor recorded exception_info for this trial")

    note = stdout_evidence(trial_dir)
    if note:
        # Evidence, not an assertion -- see the module docstring.
        (trial.reasons if not has_ctrf else trial.warnings).append(note)

    if trial.reasons:
        trial.verdict = ERRORED
    elif trial.reward is None:
        trial.verdict = ERRORED
        trial.reasons.append("result.json carries no verifier_result.rewards.reward")
    elif trial.reward >= PASS_REWARD:
        trial.verdict = PASS
    else:
        trial.verdict = FAIL

    return trial


def report(trials: list[Trial], root: Path, quiet: bool) -> None:
    """Per-trial table, then the reasons for anything that errored."""
    shown = [t for t in trials if not quiet or t.verdict != PASS]

    if shown:
        task_w = max(len("TASK"), *(len(t.task) for t in shown))
        model_w = max(len("MODEL"), *(len(t.model) for t in shown))
        print(f"{'TASK':<{task_w}}  {'MODEL':<{model_w}}  {'REWARD':>6}  VERDICT")
        print(f"{'-' * task_w}  {'-' * model_w}  {'-' * 6}  {'-' * len(ERRORED)}")
        for trial in sorted(shown, key=lambda t: (t.task, t.model, t.path.name)):
            print(
                f"{trial.task:<{task_w}}  {trial.model:<{model_w}}  "
                f"{trial.reward_str:>6}  {trial.verdict}"
            )

    errored = [t for t in trials if t.errored]
    warned = [t for t in trials if t.warnings and not t.errored]

    if errored:
        print("\n" + "=" * 72)
        print(f"ERRORED TRIALS ({len(errored)}) -- these are NOT failures")
        print("=" * 72)
        for trial in sorted(errored, key=lambda t: (t.task, t.path.name)):
            rel = relative(trial.path, root)
            print(f"\n  {trial.task} [{trial.model}] ({rel})")
            print(f"    recorded reward: {trial.reward_str}")
            for reason in trial.reasons:
                print(f"    - {reason}")

    if warned:
        print(f"\nWARNINGS ({len(warned)} trial(s) with a report but a thin log)")
        for trial in sorted(warned, key=lambda t: (t.task, t.path.name)):
            for note in trial.warnings:
                print(f"  {trial.task} [{trial.model}]: {note}")

    n_pass = sum(1 for t in trials if t.verdict == PASS)
    n_fail = sum(1 for t in trials if t.verdict == FAIL)
    scored = n_pass + n_fail
    print(f"\n{len(trials)} trial(s) under {root}")
    print(f"  PASS          {n_pass}")
    print(f"  FAIL          {n_fail}   (genuine reward 0 -- the agent failed)")
    print(f"  {ERRORED} {len(errored)}   (no verdict -- the reward is meaningless)")
    if scored:
        print(f"\nScore over trials that actually ran: {n_pass}/{scored}")


def relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit a harbor run: assert every trial produced verifier/ctrf.json, "
            "so an unreachable-pypi verifier cannot masquerade as reward 0."
        )
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="job directory, jobs/ root, or any directory containing them",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="omit PASS rows from the table (errors and the summary still print)",
    )
    args = parser.parse_args()

    exit_code = 0
    found_any = False

    for root in args.paths:
        root = root.expanduser()
        if not root.is_dir():
            print(f"error: {root} is not a directory", file=sys.stderr)
            exit_code = max(exit_code, 2)
            continue

        trial_dirs = find_trials(root)
        if not trial_dirs:
            print(f"warning: no trials (no result.json) found under {root}")
            continue

        found_any = True
        if len(args.paths) > 1:
            print(f"\n### {root}")
        trials = [classify(d) for d in trial_dirs]
        report(trials, root, args.quiet)

        if any(t.errored for t in trials):
            exit_code = max(exit_code, 1)

    if not found_any and exit_code == 0:
        print("error: no trials found in any of the given paths", file=sys.stderr)
        return 2

    if exit_code == 0:
        print("\nOK: every trial produced a verifier report.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
