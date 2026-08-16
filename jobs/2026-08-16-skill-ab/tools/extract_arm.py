#!/usr/bin/env python3
"""Per-trial extraction for one benchmark arm.

Usage:
    python3 extract_arm.py <job-dir> <arm-label> [--outdir DIR]

Writes <outdir>/<label>_trials.json and <outdir>/<label>_table.md.

Design notes (these are the load-bearing bits, do not "simplify" them away):

  * A trial with NO verifier/ctrf.json is ERRORED, not reward 0. Harbor writes
    reward 0.0 either way, so the file's presence is the only discriminator.
    Errored trials are excluded from the arm mean and from per-task scoring.
  * The arm mean is the mean of verifier_result.rewards.reward over SCORED
    trials. It is NOT passed/total: tests/test.sh floor-corrects, so a naive
    pass rate runs several points high.
  * BOOTSTRAP_ANCHOR_VIOLATION codes live in verifier/ctrf.json and
    verifier/test-stdout.txt. They are NOT in trial.log -- grepping trial.log
    returns zero and silently reads as "no violations".
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

CTRF = "verifier/ctrf.json"
STDOUT = "verifier/test-stdout.txt"
TRANSCRIPT = "agent/claude-code.txt"

ANCHOR_TOKEN = "BOOTSTRAP_ANCHOR_VIOLATION"
CODES_RE = re.compile(r"BOOTSTRAP_ANCHOR_VIOLATION\s+codes=([A-Z0-9,\-]+)")
BRACKET_CODE_RE = re.compile(r"\[(ANCHOR-[A-Z0-9-]+)\]")

# A real jj invocation at the start of a command or after a shell separator,
# not the word "jj" inside prose. Also catches `jj` after env prefixes.
JJ_RE = re.compile(r"(?:^|[;&|(]|&&|\|\||\bthen\b|\bdo\b|\s)\s*jj\s+[a-z]", re.M)


def is_trial_dir(p: Path) -> bool:
    if not p.is_dir():
        return False
    if (p / "verifier").is_dir():
        return True
    rj = p / "result.json"
    if not rj.is_file():
        return False
    try:
        d = json.loads(rj.read_text())
    except Exception:
        return False
    return isinstance(d, dict) and ("trial_name" in d or "verifier_result" in d)


def find_trials(job: Path) -> list[Path]:
    return sorted(c for c in job.iterdir() if is_trial_dir(c))


def read_json(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def read_text(p: Path) -> str:
    try:
        return p.read_text(errors="replace")
    except Exception:
        return ""


def anchor_codes(trial: Path) -> tuple[bool, list[str]]:
    """(violated, sorted unique codes) from ctrf.json + test-stdout.txt."""
    blob = ""
    ctrf = trial / CTRF
    if ctrf.is_file():
        blob += read_text(ctrf)
    so = trial / STDOUT
    if so.is_file():
        blob += "\n" + read_text(so)
    if ANCHOR_TOKEN not in blob:
        return False, []
    codes: set[str] = set()
    for m in CODES_RE.finditer(blob):
        codes.update(c for c in m.group(1).split(",") if c)
    codes.update(BRACKET_CODE_RE.findall(blob))
    return True, sorted(codes)


def ran_jj(trial: Path) -> bool:
    """True if the agent actually invoked jj in a Bash tool call."""
    tp = trial / TRANSCRIPT
    if not tp.is_file():
        return False
    for line in read_text(tp).splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        msg = ev.get("message")
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            if block.get("name") != "Bash":
                continue
            cmd = (block.get("input") or {}).get("command") or ""
            if JJ_RE.search(cmd):
                return True
    return False


def extract(job: Path, label: str) -> dict:
    rows = []
    for t in find_trials(job):
        res = read_json(t / "result.json")
        has_ctrf = (t / CTRF).is_file()
        reward = None
        task = t.name.rsplit("__", 1)[0]
        exc = None
        if isinstance(res, dict):
            task = res.get("task_name") or task
            rw = ((res.get("verifier_result") or {}).get("rewards")) or {}
            v = rw.get("reward")
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                reward = float(v)
            ei = res.get("exception_info")
            if ei:
                exc = ei if isinstance(ei, str) else json.dumps(ei)[:300]
        violated, codes = anchor_codes(t)
        # ctrf summary, when present
        summ = {}
        c = read_json(t / CTRF) if has_ctrf else None
        if isinstance(c, dict):
            summ = ((c.get("results") or {}).get("summary")) or {}
        rows.append({
            "arm": label,
            "trial": t.name,
            "task": task,
            "has_ctrf": has_ctrf,
            "errored": (not has_ctrf) or res is None,
            "reward": reward,
            "exception_info": exc,
            "anchor_violation": violated,
            "anchor_codes": codes,
            "ran_jj": ran_jj(t),
            "ctrf_tests": summ.get("tests"),
            "ctrf_passed": summ.get("passed"),
            "ctrf_failed": summ.get("failed"),
        })

    scored = [r for r in rows if not r["errored"] and r["reward"] is not None]
    errored = [r for r in rows if r not in scored]
    mean = sum(r["reward"] for r in scored) / len(scored) if scored else None

    by_task: dict[str, list] = defaultdict(list)
    for r in scored:
        by_task[r["task"]].append(r)
    per_task = []
    for task in sorted(by_task):
        rs = by_task[task]
        n_err = sum(1 for r in rows if r["task"] == task and r["errored"])
        per_task.append({
            "task": task,
            "n_scored": len(rs),
            "n_errored": n_err,
            "strict_passes": sum(1 for r in rs if r["reward"] >= 1.0),
            "mean_reward": sum(r["reward"] for r in rs) / len(rs),
            "n_ran_jj": sum(1 for r in rs if r["ran_jj"]),
            "n_anchor_violation": sum(1 for r in rs if r["anchor_violation"]),
        })

    code_counter: Counter = Counter()
    for r in rows:
        for c in r["anchor_codes"]:
            code_counter[c] += 1

    job_res = read_json(job / "result.json") or {}
    stats = job_res.get("stats") or {}

    ctrf_passed = sum(r["ctrf_passed"] or 0 for r in rows)
    ctrf_total = sum(r["ctrf_tests"] or 0 for r in rows)

    return {
        "arm": label,
        "job_dir": str(job),
        "n_trial_dirs": len(rows),
        "n_with_ctrf": sum(1 for r in rows if r["has_ctrf"]),
        "n_without_ctrf": sum(1 for r in rows if not r["has_ctrf"]),
        "n_scored": len(scored),
        "n_errored": len(errored),
        "arm_mean_reward": mean,
        "n_strict_passes": sum(1 for r in scored if r["reward"] >= 1.0),
        # Both of these are WRONG as an arm score; kept only to show the gap.
        "naive_trial_pass_rate_do_not_use": (
            sum(1 for r in scored if r["reward"] >= 1.0) / len(scored) if scored else None
        ),
        "naive_test_pass_rate_do_not_use": (
            ctrf_passed / ctrf_total if ctrf_total else None
        ),
        "reward_histogram": {
            str(k): v for k, v in
            sorted(Counter(r["reward"] for r in scored).items())
        },
        "n_ran_jj": sum(1 for r in rows if r["ran_jj"]),
        "n_anchor_violation_trials": sum(1 for r in rows if r["anchor_violation"]),
        "anchor_code_breakdown": dict(code_counter.most_common()),
        "harbor_cost_usd": stats.get("cost_usd"),
        "harbor_stats": stats and {k: v for k, v in stats.items() if k != "evals"},
        "finished_at": job_res.get("finished_at"),
        "per_task": per_task,
        "trials": rows,
    }


def to_md(rep: dict) -> str:
    L = []
    L.append(f"# Arm {rep['arm']} — per-task results\n")
    L.append(f"Job dir: `{rep['job_dir']}`\n")
    L.append(
        f"Trial dirs: {rep['n_trial_dirs']} | with ctrf.json: {rep['n_with_ctrf']} | "
        f"without (ERRORED): {rep['n_without_ctrf']} | scored: {rep['n_scored']}\n"
    )
    m = rep["arm_mean_reward"]
    L.append(f"**Arm mean reward: {m:.4f}**" if m is not None else "**Arm mean reward: n/a**")
    L.append("")
    L.append("| task | n scored | n errored | strict passes (>=1.0) | mean reward | ran jj |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for t in rep["per_task"]:
        L.append(
            f"| {t['task']} | {t['n_scored']} | {t['n_errored']} | {t['strict_passes']} | "
            f"{t['mean_reward']:.4f} | {t['n_ran_jj']} |"
        )
    L.append("")
    L.append(f"Trials that ran `jj`: {rep['n_ran_jj']} / {rep['n_trial_dirs']}")
    L.append("")
    L.append(f"BOOTSTRAP_ANCHOR_VIOLATION trials: {rep['n_anchor_violation_trials']}")
    if rep["anchor_code_breakdown"]:
        L.append("")
        L.append("| anchor code | trials |")
        L.append("|---|---:|")
        for c, n in rep["anchor_code_breakdown"].items():
            L.append(f"| {c} | {n} |")
    L.append("")
    L.append("## Scoring sanity")
    L.append("")
    L.append("| statistic | value |")
    L.append("|---|---:|")
    L.append(f"| **arm mean reward (USE THIS)** | **{m:.4f}** |" if m is not None else "| arm mean | n/a |")
    ntp = rep["naive_trial_pass_rate_do_not_use"]
    nte = rep["naive_test_pass_rate_do_not_use"]
    if ntp is not None:
        L.append(f"| naive strict trial pass rate (do not use) | {ntp:.4f} |")
    if nte is not None:
        L.append(f"| naive per-test passed/total (do not use) | {nte:.4f} |")
    L.append(f"| harbor-recorded cost_usd | {rep['harbor_cost_usd']} |")
    if rep["reward_histogram"]:
        L.append("")
        L.append("Reward histogram: " + ", ".join(
            f"{k}×{v}" for k, v in rep["reward_histogram"].items()))
    b = rep.get("baseline")
    if b:
        L.append("")
        L.append("## Comparison to published baseline")
        L.append("")
        L.append(f"- baseline mean: **{b['mean']:.4f}** over {b['n']} scored trials")
        L.append(f"- this arm:      **{m:.4f}** over {rep['n_scored']} scored trials")
        L.append(f"- difference:    **{b['delta']:+.4f}** ({b['pct']:+.2f}% relative)")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("job_dir")
    ap.add_argument("label")
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--baseline", type=float, default=None,
                    help="published baseline mean to compare against")
    ap.add_argument("--baseline-n", type=int, default=None,
                    help="n scored trials behind --baseline")
    a = ap.parse_args()
    job = Path(a.job_dir).resolve()
    if not job.is_dir():
        print(f"no such job dir: {job}", file=sys.stderr)
        return 2
    out = Path(a.outdir) if a.outdir else Path(__file__).resolve().parent
    out.mkdir(parents=True, exist_ok=True)
    rep = extract(job, a.label)
    if a.baseline is not None and rep["arm_mean_reward"] is not None:
        d = rep["arm_mean_reward"] - a.baseline
        rep["baseline"] = {
            "mean": a.baseline,
            "n": a.baseline_n,
            "delta": d,
            "pct": 100.0 * d / a.baseline if a.baseline else 0.0,
        }
    (out / f"{a.label}_trials.json").write_text(json.dumps(rep, indent=2))
    (out / f"{a.label}_table.md").write_text(to_md(rep))
    print(to_md(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
