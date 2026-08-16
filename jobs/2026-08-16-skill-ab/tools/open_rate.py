#!/usr/bin/env python3
"""Measure per-arm SKILL OPEN RATE from a harbor job directory.

An arm is not a skill arm until you prove the agent OPENED the skill
(see memory: skill-arms-and-open-rate). This script measures that.

Transcript location (host side, NOT the in-container /logs/... path):

    <job-dir>/<task>__<trial-id>/agent/claude-code.txt

STRICT detector -- a trial counts as an OPEN only if the transcript contains
EITHER:

  (a) a `Skill` tool call naming the slug, shape
          "name":"Skill","input":{"skill":"<slug>"}
      (matched whitespace-tolerantly, and tolerant of extra keys in `input`)

  (b) a read under the skill's OWN bundle path
          sessions/skills/<slug>/

NAIVE detector (reported alongside, as a built-in self-test): a bare string
match on the slug anywhere in the transcript. This is WRONG and it fails
silently in the direction that flatters you -- the slug appears exactly twice
per trial in the system/init event's `slash_commands` and `skills`
AVAILABILITY arrays, on the same line as "model":...,"permissionMode":...
So the naive count returns a false 100% for every arm, including arms whose
true open rate is zero.

  => If STRICT == NAIVE on a real job, treat that as SUSPICIOUS, not as
     confirmation. The script says so explicitly.

Missing transcripts are their own bucket ("no transcript"), never counted as
not-open, because a missing transcript is a harness failure and a decision not
to read the skill is a finding -- those license different conclusions.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

TRANSCRIPT_RELPATH = Path("agent") / "claude-code.txt"


# ---------------------------------------------------------------- detectors


def build_patterns(slug: str) -> dict[str, re.Pattern[str]]:
    """Compile the strict detector patterns for *slug*."""
    s = re.escape(slug)

    # (a) A Skill tool call naming the slug.
    #     Canonical shape: "name":"Skill","input":{"skill":"<slug>"}
    #     Tolerate arbitrary whitespace, and any other keys inside `input`
    #     before the "skill" key (harbor/Claude Code have varied this).
    skill_call = re.compile(
        r'"name"\s*:\s*"Skill"\s*,\s*"input"\s*:\s*\{[^{}]*?"skill"\s*:\s*"' + s + r'"',
    )

    # (b) A read under the skill's own bundle path.
    #     Anchored on the slug being a full path segment, so slug "jj" does not
    #     match "sessions/skills/jj-workspaces/".
    bundle_read = re.compile(r"sessions/skills/" + s + r"/")

    # NAIVE (deliberately wrong; reported for contrast only).
    naive = re.compile(s)

    return {"skill_call": skill_call, "bundle_read": bundle_read, "naive": naive}


# ---------------------------------------------------------------- data model


@dataclass
class TrialResult:
    trial_dir: str
    task: str
    trial_id: str
    has_transcript: bool
    opened: bool | None  # None when there is no transcript
    skill_call_hits: int
    bundle_read_hits: int
    naive_hits: int
    transcript_bytes: int

    @property
    def evidence(self) -> str:
        if not self.has_transcript:
            return "NO TRANSCRIPT"
        bits = []
        if self.skill_call_hits:
            bits.append(f"Skill-call x{self.skill_call_hits}")
        if self.bundle_read_hits:
            bits.append(f"bundle-read x{self.bundle_read_hits}")
        if not bits:
            bits.append(f"none (naive x{self.naive_hits})")
        return ", ".join(bits)


def split_trial_dirname(name: str) -> tuple[str, str]:
    """Split `<task>__<trial-id>` -> (task, trial_id).

    Task names may themselves contain single underscores, so split on the LAST
    '__'. A directory with no '__' is reported wholesale as the task with an
    empty trial id rather than silently dropped.
    """
    if "__" in name:
        task, _, trial_id = name.rpartition("__")
        return task, trial_id
    return name, ""


def scan_trial(trial_dir: Path, pats: dict[str, re.Pattern[str]]) -> TrialResult:
    task, trial_id = split_trial_dirname(trial_dir.name)
    transcript = trial_dir / TRANSCRIPT_RELPATH

    if not transcript.is_file():
        return TrialResult(
            trial_dir=str(trial_dir),
            task=task,
            trial_id=trial_id,
            has_transcript=False,
            opened=None,
            skill_call_hits=0,
            bundle_read_hits=0,
            naive_hits=0,
            transcript_bytes=0,
        )

    text = transcript.read_text(encoding="utf-8", errors="replace")

    skill_call_hits = len(pats["skill_call"].findall(text))
    bundle_read_hits = len(pats["bundle_read"].findall(text))
    naive_hits = len(pats["naive"].findall(text))

    return TrialResult(
        trial_dir=str(trial_dir),
        task=task,
        trial_id=trial_id,
        has_transcript=True,
        opened=bool(skill_call_hits or bundle_read_hits),
        skill_call_hits=skill_call_hits,
        bundle_read_hits=bundle_read_hits,
        naive_hits=naive_hits,
        transcript_bytes=len(text),
    )


def find_trial_dirs(job_dir: Path) -> list[Path]:
    """Trial dirs are the immediate child directories of the job dir."""
    return sorted(
        (c for c in job_dir.iterdir() if c.is_dir() and not c.name.startswith(".")),
        key=lambda c: c.name,
    )


# ---------------------------------------------------------------- reporting


def build_report(job_dir: Path, slug: str, results: list[TrialResult]) -> dict:
    scored = [r for r in results if r.has_transcript]
    missing = [r for r in results if not r.has_transcript]

    opened = [r for r in scored if r.opened]
    naive_opened = [r for r in scored if r.naive_hits > 0]

    per_task: dict[str, dict] = {}
    for r in results:
        t = per_task.setdefault(
            r.task,
            {"task": r.task, "total": 0, "scored": 0, "opened": 0,
             "naive_opened": 0, "no_transcript": 0},
        )
        t["total"] += 1
        if r.has_transcript:
            t["scored"] += 1
            if r.opened:
                t["opened"] += 1
            if r.naive_hits > 0:
                t["naive_opened"] += 1
        else:
            t["no_transcript"] += 1

    strict_n, naive_n, denom = len(opened), len(naive_opened), len(scored)

    if denom == 0:
        suspicion = "NO SCORABLE TRIALS -- every trial is missing its transcript."
    elif strict_n == naive_n and naive_n > 0:
        suspicion = (
            "SUSPICIOUS: strict == naive. The naive matcher hits the init-event "
            "availability arrays in EVERY trial, so it should normally be >= "
            "strict and usually equal to the trial count. Equality here means "
            "either a genuinely 100%-consumed arm, or a broken strict matcher. "
            "Verify by hand before reporting."
        )
    elif naive_n == denom and strict_n < denom:
        suspicion = (
            "OK: naive = 100% (availability arrays, as expected) while strict = "
            f"{strict_n}/{denom}. The strict detector is discriminating."
        )
    else:
        suspicion = (
            f"OK: strict {strict_n}/{denom} vs naive {naive_n}/{denom}; "
            "the two detectors disagree, as they should."
        )

    return {
        "job_dir": str(job_dir),
        "slug": slug,
        "transcript_relpath": str(TRANSCRIPT_RELPATH),
        "totals": {
            "trials": len(results),
            "scored": denom,
            "no_transcript": len(missing),
            "opened_strict": strict_n,
            "opened_naive": naive_n,
            "open_rate": f"{strict_n}/{denom}" if denom else "0/0",
            "open_rate_pct": round(100.0 * strict_n / denom, 1) if denom else None,
            "naive_rate": f"{naive_n}/{denom}" if denom else "0/0",
        },
        "self_test": {
            "strict_equals_naive": strict_n == naive_n,
            "verdict": suspicion,
        },
        "per_task": sorted(per_task.values(), key=lambda t: t["task"]),
        "per_trial": [asdict(r) for r in results],
    }


def print_table(report: dict, results: list[TrialResult]) -> None:
    slug = report["slug"]
    print(f"\nSKILL OPEN RATE  --  slug: {slug}")
    print(f"job dir: {report['job_dir']}")
    print(f"transcript: <trial>/{report['transcript_relpath']}")

    print("\n--- per trial " + "-" * 62)
    w = max([20] + [len(Path(r.trial_dir).name) for r in results]
                 + [len(t["task"]) for t in report["per_task"]])
    print(f"{'trial':<{w}}  {'open':<6}  evidence")
    for r in results:
        name = Path(r.trial_dir).name
        if not r.has_transcript:
            mark = "n/a"
        else:
            mark = "OPEN" if r.opened else "-"
        print(f"{name:<{w}}  {mark:<6}  {r.evidence}")

    print("\n--- per task " + "-" * 63)
    print(f"{'task':<{w}}  {'open/scored':>12}  {'naive':>8}  {'no-transcript':>14}")
    for t in report["per_task"]:
        print(
            f"{t['task']:<{w}}  {str(t['opened']) + '/' + str(t['scored']):>12}  "
            f"{str(t['naive_opened']) + '/' + str(t['scored']):>8}  {t['no_transcript']:>14}"
        )

    tot = report["totals"]
    print("\n--- arm total " + "-" * 62)
    print(f"  STRICT open rate : {tot['open_rate']}"
          + (f"  ({tot['open_rate_pct']}%)" if tot["open_rate_pct"] is not None else ""))
    print(f"  NAIVE  (WRONG)   : {tot['naive_rate']}   <- bare string match, for contrast only")
    print(f"  no transcript    : {tot['no_transcript']}")
    print(f"\n  SELF-TEST: {report['self_test']['verdict']}\n")


# ---------------------------------------------------------------- entrypoint


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Measure skill open rate from a harbor job directory.",
    )
    ap.add_argument("job_dir", type=Path, help="harbor job directory")
    ap.add_argument(
        "--slug",
        required=True,
        help="the skill's DIRECTORY BASENAME as harbor uploaded it "
             "(NOT the frontmatter name:), e.g. schpet--toolbox--jj",
    )
    ap.add_argument("--json-out", type=Path, help="write the JSON report here")
    ap.add_argument("--quiet", action="store_true", help="suppress the table")
    args = ap.parse_args(argv)

    if not args.job_dir.is_dir():
        print(f"error: job dir not found: {args.job_dir}", file=sys.stderr)
        return 2

    pats = build_patterns(args.slug)
    trial_dirs = find_trial_dirs(args.job_dir)
    if not trial_dirs:
        print(f"error: no trial directories under {args.job_dir}", file=sys.stderr)
        return 2

    results = [scan_trial(d, pats) for d in trial_dirs]
    report = build_report(args.job_dir, args.slug, results)

    if not args.quiet:
        print_table(report, results)

    blob = json.dumps(report, indent=2)
    if args.json_out:
        args.json_out.write_text(blob + "\n")
        print(f"json -> {args.json_out}")
    else:
        print(blob)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
