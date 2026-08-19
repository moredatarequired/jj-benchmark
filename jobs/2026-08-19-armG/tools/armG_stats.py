#!/usr/bin/env python3
"""
armG_stats.py -- statistical analysis for the jj-benchmark skill-delivery A/B.

Re-implements the estimator used by `results/2026-08-16-skill-ab.md` (the six-arm
2026-08-16 sweep) so that any new arm -- specifically arm G -- is analysed by
exactly the same code that reproduces the published A-F numbers.

The statistics tooling for the published run was never archived (only
`tools/extract_arm.py` and `tools/open_rate.py` were), so this file is a
from-scratch re-implementation of the recipe recorded in recon-armG.md section 6.

ESTIMATOR (all of this is deliberate; see recon-armG.md section 6)
------------------------------------------------------------------
* Per-trial reward  = result.json -> verifier_result.rewards.reward
                      (equivalently verifier/reward.txt; both are checked and
                      any disagreement is reported).
* Per-arm mean      = arithmetic mean over the arm's trials.
* Per-task mean     = arithmetic mean over that task's attempts (4).
* Contrasts         = PAIRED BY TASK, n = 24 clusters, t(23).
                      mean diff, t, two-sided p, 95% CI, up/down/tied counts.
* Arm intervals     = cluster-honest: sd of the 24 task means / sqrt(24), t(23).
                      The trial-level normal interval (sd of 96 trials /
                      sqrt(96), z = 1.96) is printed only, marked "do not use".
                      DEFF = (SE_cluster / SE_trial)^2.
* Multiplicity      = Holm across the primary contrast family; uncorrected and
                      adjusted p both shown.
* Robustness        = sign-flip permutation test on the 24 paired differences,
                      200,000 draws, fixed recorded seed.
* Channel/content   = task-level bootstrap over the 24 tasks, 200,000
  share               resamples, fixed recorded seed; percentile CI plus the
                      fraction of resamples falling outside [0, 1].

No third-party dependencies (no numpy / scipy): the t distribution, the
permutation test and the bootstrap are all implemented here in pure Python so
the script runs in the sweep container as-is. RNG is `random.Random(seed)`, so
results are byte-reproducible for a given seed.

USAGE
-----
  # reproduce the published six-arm analysis
  python3 armG_stats.py A B C D E F

  # once arm G lands (its three contrasts are wired in by default)
  python3 armG_stats.py A B C D E F G

  # explicit paths override the built-in registry
  python3 armG_stats.py A=/path/to/armA-control G=/root/scratch/armG/jobs/armG-blind-forced

  # options
  --contrasts D-A,F-C,...   contrast set to report (default: published 11, plus
                            the three G contrasts when G is present)
  --primary D-A,...         Holm family (default: published 7 for A-F only;
                            the three G contrasts when G is present)
  --share NUM/DEN           channel-share bootstrap, e.g. D-F/D-C (default when
                            C, D, F are all present)
  --draws N                 permutation draws (default 200000)
  --boot N                  bootstrap resamples (default 200000)
  --perm-seed N             default 20260819
  --boot-seed N             default 20260820
  --table-diffs F-C,F-D     extra diff columns in the per-task table
  --exact-perm              also enumerate all 2^n sign vectors (exact p)
  --no-aux                  skip anchor-violation and cost reporting
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import random
import re
import sys
from collections import Counter, OrderedDict

# ---------------------------------------------------------------------------
# Fixed, recorded seeds. Do not change these without re-recording them in the
# write-up: every permutation / bootstrap figure this script prints is
# conditional on them.
# ---------------------------------------------------------------------------
PERM_SEED_DEFAULT = 20260819
BOOT_SEED_DEFAULT = 20260820
PERM_DRAWS_DEFAULT = 200_000
BOOT_DRAWS_DEFAULT = 200_000

SCRATCH = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_JOBS = os.path.join(SCRATCH, "archive", "jobs", "2026-08-16-skill-ab")

# label -> directory holding one subdirectory per trial
ARM_REGISTRY = OrderedDict(
    [
        ("A", os.path.join(ARCHIVE_JOBS, "armA-control")),
        ("B", os.path.join(ARCHIVE_JOBS, "armB-decoy")),
        ("C", os.path.join(ARCHIVE_JOBS, "armC-schpet")),
        ("D", os.path.join(ARCHIVE_JOBS, "armD-forced")),
        ("E", os.path.join(ARCHIVE_JOBS, "armE-schpet-forced")),
        ("F", os.path.join(ARCHIVE_JOBS, "armF-ref-as-skill")),
        # Arm G: the blind forced arm, run in arm D's slot.
        ("G", "/root/scratch/armG/jobs/armG-blind-forced"),
    ]
)

# The published contrast set (results/2026-08-16-skill-ab.md:31-43).
PUBLISHED_CONTRASTS = [
    ("B", "A"),
    ("C", "A"),
    ("E", "A"),
    ("F", "A"),
    ("D", "A"),
    ("F", "C"),
    ("E", "D"),
    ("F", "B"),
    ("D", "F"),
    ("E", "C"),
    ("D", "C"),
]

# The seven primary contrasts Holm was applied across (":59").
PUBLISHED_PRIMARY = [
    ("D", "A"),
    ("F", "A"),
    ("D", "C"),
    ("F", "C"),
    ("D", "F"),
    ("E", "D"),
    ("E", "C"),
]

# Arm G's three contrasts of interest.
#   G - A : does a blind well-written skill beat no skill at all?
#   G - E : does it beat the best published third-party skill delivered the
#           same way (forced --extra-instruction-path)?
#   D - G : how much of arm D's +0.163 was informed-by-our-failures content
#           rather than skill quality?
G_CONTRASTS = [("G", "A"), ("G", "E"), ("D", "G")]

TOL = 1e-9  # tie tolerance on paired task-mean differences


# ---------------------------------------------------------------------------
# Statistics primitives (pure Python)
# ---------------------------------------------------------------------------
def mean(xs):
    return sum(xs) / len(xs)


def sd(xs, ddof=1):
    n = len(xs)
    if n - ddof <= 0:
        return float("nan")
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - ddof))


def _betacf(a, b, x, itmax=300, eps=3e-16, fpmin=1e-300):
    """Continued fraction for the incomplete beta function (Lentz's method)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            break
    return h


def betainc(a, b, x):
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - math.exp(
        lbeta + b * math.log(1.0 - x) + a * math.log(x)
    ) * _betacf(b, a, 1.0 - x) / b


def t_sf_two_sided(t, df):
    """Two-sided p-value for Student's t."""
    t = abs(float(t))
    if df <= 0:
        return float("nan")
    if math.isinf(t):
        return 0.0
    x = df / (df + t * t)
    return betainc(df / 2.0, 0.5, x)


def t_ppf_975(df):
    """Two-sided 95% critical value for t(df), by bisection on t_sf_two_sided."""
    lo, hi = 0.0, 100.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if t_sf_two_sided(mid, df) > 0.05:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def percentile(sorted_xs, q):
    """Linear-interpolation percentile, q in [0, 100]. Input must be sorted."""
    n = len(sorted_xs)
    if n == 0:
        return float("nan")
    if n == 1:
        return sorted_xs[0]
    pos = (q / 100.0) * (n - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_xs[lo] * (1.0 - frac) + sorted_xs[hi] * frac


def holm(pvals):
    """Holm-Bonferroni step-down adjusted p-values, order preserved."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        val = (m - rank) * pvals[i]
        running = max(running, val)
        adj[i] = min(1.0, running)
    return adj


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
class Arm:
    def __init__(self, label, path):
        self.label = label
        self.path = path
        self.trials = []            # list of (task, trial_dir_name, reward)
        self.errored_infra = []     # trial dirs with no verifier/ctrf.json
        self.reward_mismatch = []   # result.json vs reward.txt disagreement
        self.missing_reward = []    # trial dirs with no reward at all
        self.task_rewards = OrderedDict()
        self.cost_usd = None
        self.harbor_mean = None
        self.anchor_codes = {}      # trial -> first ANCHOR-* code

    # -- derived ---------------------------------------------------------
    @property
    def rewards(self):
        return [r for (_, _, r) in self.trials]

    @property
    def tasks(self):
        return list(self.task_rewards.keys())

    def task_mean(self, task):
        return mean(self.task_rewards[task])

    @property
    def task_means(self):
        return [self.task_mean(t) for t in self.tasks]

    @property
    def trial_mean(self):
        return mean(self.rewards)

    @property
    def n_trials(self):
        return len(self.trials)

    @property
    def anchor_violations(self):
        return len(self.anchor_codes)


ANCHOR_RE = re.compile(r"ANCHOR-[A-Z0-9-]+")


def load_arm(label, path, want_aux=True):
    arm = Arm(label, path)
    if not os.path.isdir(path):
        raise SystemExit(
            "arm %s: directory does not exist: %s\n"
            "  (if arm G has not finished yet, run without G)" % (label, path)
        )

    trial_dirs = sorted(
        d for d in glob.glob(os.path.join(path, "*")) if os.path.isdir(d)
    )
    for tdir in trial_dirs:
        name = os.path.basename(tdir)
        rj = os.path.join(tdir, "result.json")
        rtxt = os.path.join(tdir, "verifier", "reward.txt")
        if not os.path.isfile(rj):
            continue  # not a trial directory (e.g. a vendored bundle)

        with open(rj) as fh:
            res = json.load(fh)
        task = res.get("task_name") or name.rsplit("__", 1)[0]

        reward = None
        vr = res.get("verifier_result") or {}
        rewards = vr.get("rewards") or {}
        if "reward" in rewards:
            reward = float(rewards["reward"])

        reward_txt = None
        if os.path.isfile(rtxt):
            with open(rtxt) as fh:
                raw = fh.read().strip()
            if raw:
                try:
                    reward_txt = float(raw)
                except ValueError:
                    reward_txt = None

        # ERRORED-INFRA: a missing ctrf.json is an infrastructure failure, never
        # a reward of 0 (recon section 4b; scripts/check_run_results.py).
        if not os.path.isfile(os.path.join(tdir, "verifier", "ctrf.json")):
            arm.errored_infra.append(name)

        if reward is None and reward_txt is None:
            arm.missing_reward.append(name)
            continue
        if reward is None:
            reward = reward_txt
        elif reward_txt is not None and abs(reward - reward_txt) > 1e-9:
            arm.reward_mismatch.append((name, reward, reward_txt))

        arm.trials.append((task, name, reward))
        arm.task_rewards.setdefault(task, []).append(reward)

        if want_aux:
            code = None
            for probe in (
                os.path.join(tdir, "verifier", "ctrf.json"),
                os.path.join(tdir, "verifier", "test-stdout.txt"),
            ):
                if os.path.isfile(probe):
                    with open(probe, errors="replace") as fh:
                        m = ANCHOR_RE.search(fh.read())
                    if m:
                        code = m.group(0)
                        break
            if code:
                arm.anchor_codes[name] = code

    # sort tasks alphabetically so every arm's task vector lines up
    arm.task_rewards = OrderedDict(sorted(arm.task_rewards.items()))

    # arm-level harbor record: cost and harbor's own mean, for cross-checking
    arm_result = os.path.join(path, "result.json")
    if os.path.isfile(arm_result):
        try:
            with open(arm_result) as fh:
                top = json.load(fh)
            stats = top.get("stats") or {}
            arm.cost_usd = stats.get("cost_usd")
            evals = stats.get("evals") or {}
            for _k, v in evals.items():
                metrics = v.get("metrics") or []
                if metrics and "mean" in metrics[0]:
                    arm.harbor_mean = metrics[0]["mean"]
                    break
        except Exception:
            pass
    return arm


# ---------------------------------------------------------------------------
# Contrasts
# ---------------------------------------------------------------------------
class Contrast:
    def __init__(self, hi, lo, tasks, diffs):
        self.hi, self.lo = hi, lo
        self.name = "%s - %s" % (hi, lo)
        self.tasks = tasks
        self.d = diffs
        self.n = len(diffs)
        self.mean = mean(diffs)
        self.sd = sd(diffs)
        self.se = self.sd / math.sqrt(self.n) if self.n else float("nan")
        self.df = self.n - 1
        self.t = self.mean / self.se if self.se else float("nan")
        self.p = t_sf_two_sided(self.t, self.df)
        tc = t_ppf_975(self.df)
        self.tcrit = tc
        self.ci = (self.mean - tc * self.se, self.mean + tc * self.se)
        self.up = sum(1 for x in diffs if x > TOL)
        self.down = sum(1 for x in diffs if x < -TOL)
        self.tied = self.n - self.up - self.down
        self.perm_p = None
        self.exact_p = None
        self.perm_draws = None
        self.perm_seed = None
        self.holm_p = None


def paired_diffs(arms, hi, lo):
    a, b = arms[hi], arms[lo]
    ta, tb = a.tasks, b.tasks
    common = [t for t in ta if t in b.task_rewards]
    if ta != tb:
        missing_hi = [t for t in tb if t not in a.task_rewards]
        missing_lo = [t for t in ta if t not in b.task_rewards]
        sys.stderr.write(
            "WARNING: %s vs %s task sets differ; pairing on the %d common tasks "
            "(missing in %s: %s; missing in %s: %s)\n"
            % (hi, lo, len(common), hi, missing_hi or "-", lo, missing_lo or "-")
        )
    diffs = [a.task_mean(t) - b.task_mean(t) for t in common]
    return common, diffs


def sign_flip_permutation(diffs, draws, seed):
    """Two-sided sign-flip permutation p on the paired differences.

    Under the null the sign of each paired difference is exchangeable, so we
    resample the 2^n sign vectors and compare |mean| to the observed |mean|.
    """
    n = len(diffs)
    obs = abs(mean(diffs))
    target = obs * n - 1e-12  # compare sums; avoid FP ties dropping the equality
    total = sum(diffs)
    rng = random.Random(seed)
    getrandbits = rng.getrandbits
    ge = 0
    for _ in range(draws):
        bits = getrandbits(n)
        # s = sum(+d_i if bit set else -d_i) = total - 2 * sum(d_i where bit=0)
        neg = 0.0
        b = bits
        i = 0
        while i < n:
            if not (b >> i) & 1:
                neg += diffs[i]
            i += 1
        s = total - 2.0 * neg
        if abs(s) >= target:
            ge += 1
    return ge / float(draws), ge


def sign_flip_exact(diffs):
    """EXACT two-sided sign-flip p: enumerate all 2^n sign vectors.

    Feasible up to n ~= 26 (2^24 = 16.7M takes about 7 s here). Walks the sign
    vectors in Gray-code order so each step flips exactly one term, which makes
    the running sum an O(1) update. Use it to check that a Monte-Carlo
    permutation p is not doing something structurally different: at n = 24 the
    200k-draw estimate carries an MC se of ~5e-4, which is the whole size of the
    difference between two runs with different seeds.
    """
    n = len(diffs)
    if n > 26:
        return None
    obs = abs(mean(diffs)) * n - 1e-9  # compare sums
    two = [2.0 * x for x in diffs]
    s = -sum(diffs)  # all-negative sign vector = Gray code 0
    cnt = 1 if abs(s) >= obs else 0
    for k in range(1, 1 << n):
        i = (k & -k).bit_length() - 1
        g = k ^ (k >> 1)
        if (g >> i) & 1:
            s += two[i]
        else:
            s -= two[i]
        if s >= obs or -s >= obs:
            cnt += 1
    return cnt / float(1 << n), cnt, 1 << n


# ---------------------------------------------------------------------------
# Channel / content share bootstrap
# ---------------------------------------------------------------------------
def share_bootstrap(num_diffs, den_extra_diffs, draws, seed):
    """Task-level bootstrap for a share = num / (num + extra), both paired
    per-task difference vectors over the same 24 tasks.

    For the published split this is share = (D-F) / ((D-F) + (F-C)) = (D-F)/(D-C),
    which is exactly the identity the write-up uses ("summing to D - C by
    construction").  Resampling tasks with replacement keeps the numerator and
    denominator on the same resampled task set, which is what makes the interval
    honest about the shared arms.
    """
    n = len(num_diffs)
    assert len(den_extra_diffs) == n
    rng = random.Random(seed)
    rnd = rng.random
    shares = []
    n_outside = 0
    n_below = 0
    n_above = 0
    n_undef = 0
    for _ in range(draws):
        s_num = 0.0
        s_ext = 0.0
        for _k in range(n):
            i = int(rnd() * n)
            s_num += num_diffs[i]
            s_ext += den_extra_diffs[i]
        den = s_num + s_ext
        if den == 0.0:
            n_undef += 1
            continue
        sh = s_num / den
        shares.append(sh)
        if sh < 0.0:
            n_below += 1
            n_outside += 1
        elif sh > 1.0:
            n_above += 1
            n_outside += 1
    shares.sort()
    return {
        "shares": shares,
        "median": percentile(shares, 50),
        "lo": percentile(shares, 2.5),
        "hi": percentile(shares, 97.5),
        "frac_outside": n_outside / float(draws),
        "frac_below": n_below / float(draws),
        "frac_above": n_above / float(draws),
        "n_undef": n_undef,
        "draws": draws,
        "seed": seed,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def fmt_p(p):
    if p != p:
        return "nan"
    if p >= 0.1:
        return "%.3f" % p
    if p >= 0.01:
        return "%.4f" % p
    return "%.4f" % p


def hr(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def report(arms, contrasts, primary_keys, share_spec, args):
    labels = list(arms.keys())

    # ---- 0. data integrity -------------------------------------------
    hr("0. DATA LOADED")
    print("arm   dir                                              trials tasks  "
          "attempts/task")
    for lab in labels:
        a = arms[lab]
        counts = sorted({len(v) for v in a.task_rewards.values()})
        print("%-5s %-48s %6d %5d  %s"
              % (lab, a.path[-48:], a.n_trials, len(a.tasks),
                 ",".join(str(c) for c in counts)))
    for lab in labels:
        a = arms[lab]
        if a.errored_infra:
            print("  !! arm %s: %d trial(s) with NO verifier/ctrf.json -- "
                  "ERRORED-INFRA, never reward 0: %s"
                  % (lab, len(a.errored_infra), ", ".join(a.errored_infra[:6])))
        if a.reward_mismatch:
            print("  !! arm %s: %d trial(s) where result.json and reward.txt "
                  "disagree: %s" % (lab, len(a.reward_mismatch),
                                    a.reward_mismatch[:4]))
        if a.missing_reward:
            print("  !! arm %s: %d trial(s) with no reward at all: %s"
                  % (lab, len(a.missing_reward), a.missing_reward[:6]))
    clean = all(
        not arms[l].errored_infra and not arms[l].reward_mismatch
        and not arms[l].missing_reward for l in labels
    )
    if clean:
        print("  all arms clean: every trial has a ctrf.json and result.json "
              "and reward.txt agree")

    # ---- 1. arm means ------------------------------------------------
    hr("1. PER-ARM MEANS  (mean over trials of verifier_result.rewards.reward)")
    print("| arm | n | mean (trials) | mean (of task means) | harbor stats.evals mean |")
    print("|---|---:|---:|---:|---:|")
    for lab in labels:
        a = arms[lab]
        hm = "-" if a.harbor_mean is None else "%.6f" % a.harbor_mean
        print("| %s | %d | %.6f | %.6f | %s |"
              % (lab, a.n_trials, a.trial_mean, mean(a.task_means), hm))
    print()
    print("(balanced design => the trial mean and the mean of task means agree)")

    # ---- 2. cluster-honest intervals ---------------------------------
    hr("2. ARM INTERVALS -- CLUSTERING HONORED  (24 clusters of 4, not 96 units)")
    print("| arm | mean | trial-level 95% (DO NOT USE) | cluster-honest 95% | "
          "DEFF | width ratio |")
    print("|---|---:|---|---|---:|---:|")
    for lab in labels:
        a = arms[lab]
        m = a.trial_mean
        tm = a.task_means
        k = len(tm)
        se_cluster = sd(tm) / math.sqrt(k)
        tc = t_ppf_975(k - 1)
        cl = (m - tc * se_cluster, m + tc * se_cluster)
        se_trial = sd(a.rewards) / math.sqrt(a.n_trials)
        z = 1.959963985  # trial-level NORMAL approximation, as published
        tl = (m - z * se_trial, m + z * se_trial)
        deff = (se_cluster / se_trial) ** 2 if se_trial else float("nan")
        ratio = (tc * se_cluster) / (z * se_trial) if se_trial else float("nan")
        print("| %s | %.4f | [%.3f, %.3f]  <-- do not use | **[%.3f, %.3f]** | "
              "%.2f | %.2f |"
              % (lab, m, tl[0], tl[1], cl[0], cl[1], deff, ratio))
    print()
    print("trial-level = sd(all trials)/sqrt(n_trials), z = 1.96  -- DO NOT USE:")
    print("  it treats 4 attempts on one task as 4 independent units.")
    print("cluster-honest = sd(the %d task means)/sqrt(%d), t(%d).  DEFF = "
          "(SE_cluster/SE_trial)^2." % (len(arms[labels[0]].tasks),
                                        len(arms[labels[0]].tasks),
                                        len(arms[labels[0]].tasks) - 1))

    # ---- 3. paired contrasts -----------------------------------------
    n_pairs = contrasts[0].n if contrasts else 0
    hr("3. PAIRED-BY-TASK CONTRASTS  (n = %d tasks, t(%d))"
       % (n_pairs, n_pairs - 1 if n_pairs else 0))
    print("| contrast | mean diff | t(%d) | p | 95%% CI | up/down/tied |"
          % (n_pairs - 1 if n_pairs else 0))
    print("|---|---:|---:|---:|---|---|")
    for c in contrasts:
        print("| %s | %+.4f | %+.3f | %s | [%+.3f, %+.3f] | %d/%d/%d |"
              % (c.name, c.mean, c.t, fmt_p(c.p), c.ci[0], c.ci[1],
                 c.up, c.down, c.tied))

    # ---- 4. Holm -----------------------------------------------------
    hr("4. MULTIPLICITY -- HOLM ACROSS THE PRIMARY FAMILY")
    fam = [c for c in contrasts if (c.hi, c.lo) in primary_keys]
    if not fam:
        print("no primary-family contrasts present")
    else:
        adj = holm([c.p for c in fam])
        for c, a in zip(fam, adj):
            c.holm_p = a
        print("family of %d: %s" % (len(fam), ", ".join(c.name for c in fam)))
        print()
        print("| contrast | mean diff | p (uncorrected) | p (Holm) | survives 0.05 |")
        print("|---|---:|---:|---:|---|")
        for c in fam:
            print("| %s | %+.4f | %.4f | %.4f | %s |"
                  % (c.name, c.mean, c.p, c.holm_p,
                     "YES" if c.holm_p < 0.05 else "no"))
        print()
        print("The contrasts share arms and are strongly correlated, so Holm is")
        print("conservative -- but the uncorrected p-values are not %d "
              "independent findings." % len(fam))

    # ---- 5. permutation ----------------------------------------------
    hr("5. ROBUSTNESS -- SIGN-FLIP PERMUTATION ON THE %d PAIRED DIFFERENCES"
       % n_pairs)
    print("draws = %d, seed = %d (fixed and recorded)"
          % (args.draws, args.perm_seed))
    print()
    hdr = "| contrast | mean diff | p (t-test) | p (permutation) | MC se |"
    sep = "|---|---:|---:|---:|---:|"
    if args.exact_perm:
        hdr = hdr + " p (EXACT, all 2^n) |"
        sep = sep + "---:|"
    print(hdr)
    print(sep)
    for c in contrasts:
        p, cnt = sign_flip_permutation(c.d, args.draws, args.perm_seed)
        c.perm_p, c.perm_draws, c.perm_seed = p, args.draws, args.perm_seed
        mcse = math.sqrt(max(p * (1 - p), 0.0) / args.draws)
        row = ("| %s | %+.4f | %s | %s | %.5f |"
               % (c.name, c.mean, fmt_p(c.p), "%.4f" % p, mcse))
        if args.exact_perm:
            ex = sign_flip_exact(c.d)
            if ex is None:
                row = row + " n too large |"
            else:
                c.exact_p = ex[0]
                row = row + " %.6f |" % ex[0]
        print(row)
    print()
    print("Two-sided: fraction of sign-flipped resamples with |mean| >= "
          "|observed mean|.")
    print("The >= (not >) tie convention is load-bearing at this n: the paired")
    print("differences are coarse rationals, so exact ties carry real mass "
          "(F - C moves")
    print("from 0.0464 to 0.0438 under >).")
    print("A permutation p differs from a published one by up to ~2 MC se even "
          "with identical")
    print("code, because the published run used its own (unrecorded) seed. Pass")
    print("--exact-perm to remove Monte-Carlo noise entirely (enumerates all "
          "2^%d sign" % n_pairs)
    print("vectors; ~7 s per contrast at n = 24).")

    # ---- 6. share bootstrap ------------------------------------------
    if share_spec:
        (nh, nl), (dh, dl) = share_spec
        by = {(c.hi, c.lo): c for c in contrasts}
        cn = by.get((nh, nl))
        cd = by.get((dh, dl))
        if cn is None or cd is None:
            print("\n(share bootstrap skipped: contrast not in the reported set)")
        else:
            hr("6. CHANNEL / CONTENT SHARE -- TASK-LEVEL BOOTSTRAP")
            # decompose the denominator into num + extra so the identity holds
            extra = [cd.d[i] - cn.d[i] for i in range(cd.n)]
            print("share = (%s) / (%s),  with (%s) = (%s) + residual by "
                  "construction" % (cn.name, cd.name, cd.name, cn.name))
            print("point estimate: %s = %+.4f, %s = %+.4f  =>  share = %.4f "
                  "(%.0f%% / %.0f%%)"
                  % (cn.name, cn.mean, cd.name, cd.mean, cn.mean / cd.mean,
                     100 * cn.mean / cd.mean, 100 * (1 - cn.mean / cd.mean)))
            print("residual term (%s minus %s) = %+.4f"
                  % (cd.name, cn.name, mean(extra)))
            print("resamples = %d, seed = %d (fixed and recorded)"
                  % (args.boot, args.boot_seed))
            b = share_bootstrap(cn.d, extra, args.boot, args.boot_seed)
            print()
            print("  median share           %.4f" % b["median"])
            print("  95%% percentile CI      [%.4f, %.4f]  (raw)"
                  % (b["lo"], b["hi"]))
            _z = lambda v: 0.0 if abs(v) < 5e-3 else v
            print("  95%% percentile CI      [%.2f, %.2f]  (2 dp, as published)"
                  % (_z(b["lo"]), _z(b["hi"])))
            print("  outside [0, 1]         %.3f%%   (below 0: %.3f%%, "
                  "above 1: %.3f%%)"
                  % (100 * b["frac_outside"], 100 * b["frac_below"],
                     100 * b["frac_above"]))
            if b["n_undef"]:
                print("  undefined (den == 0)   %d" % b["n_undef"])
            print()
            print("The share is barely identified: the %s denominator can change"
                  % cd.name)
            print("sign under resampling, which is why resamples fall outside "
                  "[0, 1].")
            print("Quote the split with this interval or not at all.")

    # ---- 7. per-task table -------------------------------------------
    hr("7. PER-TASK TABLE  (means to 3 dp, n = %s per cell)"
       % ",".join(str(c) for c in sorted(
           {len(v) for l in labels for v in arms[l].task_rewards.values()})))
    diffcols = []
    for spec in args.table_diffs:
        hi, lo = spec
        if hi in arms and lo in arms:
            diffcols.append((hi, lo))
    tasks = arms[labels[0]].tasks
    header = "| task | " + " | ".join(labels)
    if diffcols:
        header += " | " + " | ".join("%s-%s" % (h, l) for h, l in diffcols)
    header += " |"
    print(header)
    print("|---|" + "---:|" * (len(labels) + len(diffcols)))
    for t in tasks:
        cells = []
        for lab in labels:
            a = arms[lab]
            cells.append("%.3f" % a.task_mean(t) if t in a.task_rewards else "-")
        for h, l in diffcols:
            if t in arms[h].task_rewards and t in arms[l].task_rewards:
                cells.append("%+.3f" % (arms[h].task_mean(t)
                                        - arms[l].task_mean(t)))
            else:
                cells.append("-")
        print("| `%s` | %s |" % (t, " | ".join(cells)))
    cells = ["**%.3f**" % arms[lab].trial_mean for lab in labels]
    for h, l in diffcols:
        cells.append("**%+.3f**" % (arms[h].trial_mean - arms[l].trial_mean))
    print("| **arm mean** | %s |" % " | ".join(cells))
    print()
    print("(The published table's trailing `F opens` column is an open-rate "
          "figure, not a")
    print(" statistic -- it comes from the strict-open detector in "
          "tools/open_rate.py and is")
    print(" deliberately out of scope here.)")

    # ---- 8. aux: anchor violations and cost ---------------------------
    if not args.no_aux:
        hr("8. AUXILIARY -- ANCHOR VIOLATIONS AND COST")
        print("Anchor violation = an ANCHOR-* code in verifier/ctrf.json or")
        print("verifier/test-stdout.txt (NEVER trial.log, which reads falsely "
              "clean).")
        print("Counted ONE CODE PER TRIAL (the fixture is session-scoped autouse,")
        print("so the message repeats once per failing test). A violation forces")
        print("reward to exactly 0.0, so it is invisible in a mean.")
        print()
        print("| arm | anchor viol | breakdown | cost_usd (harbor-recorded) |")
        print("|---|---:|---|---:|")
        for lab in labels:
            a = arms[lab]
            br = Counter(a.anchor_codes.values())
            brs = ", ".join("%s %d" % (k, v) for k, v in sorted(br.items())) or "-"
            cost = "-" if a.cost_usd is None else "$%.4f" % a.cost_usd
            print("| %s | %d/%d | %s | %s |"
                  % (lab, a.anchor_violations, a.n_trials, brs, cost))
        total = sum(a.cost_usd for a in arms.values() if a.cost_usd is not None)
        print()
        print("total cost across the arms loaded: $%.2f  (haiku needs no "
              "rescale -- the 2/3" % total)
        print("correction and the 1.5x over-report are sonnet-only)")

    hr("SEEDS AND SETTINGS -- RECORD THESE WITH ANY QUOTED FIGURE")
    print("permutation: %d draws, seed %d" % (args.draws, args.perm_seed))
    print("bootstrap:   %d resamples, seed %d" % (args.boot, args.boot_seed))
    print("RNG: python random.Random (Mersenne Twister), stdlib")
    print("t distribution: exact, via the regularized incomplete beta")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_contrast_list(s):
    out = []
    for tok in s.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if "-" not in tok:
            raise SystemExit("bad contrast %r (want HI-LO, e.g. D-A)" % tok)
        hi, lo = tok.split("-", 1)
        out.append((hi.strip(), lo.strip()))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Paired-by-task analysis of jj-benchmark skill A/B arms.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("arms", nargs="+", metavar="ARM",
                    help="arm label (A..G, resolved from the built-in registry) "
                         "or LABEL=PATH")
    ap.add_argument("--contrasts", default=None,
                    help="comma-separated HI-LO list; default = the published "
                         "set (plus G's three when G is present)")
    ap.add_argument("--primary", default=None,
                    help="Holm family, comma-separated HI-LO; default = the "
                         "published seven, or G's three when G is present")
    ap.add_argument("--share", default=None,
                    help="share bootstrap as NUM/DEN, e.g. D-F/D-C; "
                         "'none' disables")
    ap.add_argument("--draws", type=int, default=PERM_DRAWS_DEFAULT)
    ap.add_argument("--boot", type=int, default=BOOT_DRAWS_DEFAULT)
    ap.add_argument("--perm-seed", type=int, default=PERM_SEED_DEFAULT)
    ap.add_argument("--boot-seed", type=int, default=BOOT_SEED_DEFAULT)
    ap.add_argument("--table-diffs", default=None,
                    help="extra diff columns for the per-task table")
    ap.add_argument("--exact-perm", action="store_true",
                    help="also enumerate all 2^n sign vectors for an EXACT\n"
                         "permutation p (n <= 26; ~7 s per contrast at n = 24)")
    ap.add_argument("--no-aux", action="store_true",
                    help="skip anchor-violation and cost reporting")
    args = ap.parse_args(argv)

    # resolve arms
    arms = OrderedDict()
    for spec in args.arms:
        if "=" in spec:
            lab, path = spec.split("=", 1)
            lab = lab.strip()
        else:
            lab = spec.strip()
            path = ARM_REGISTRY.get(lab)
            if path is None:
                raise SystemExit(
                    "unknown arm label %r; known: %s (or pass LABEL=PATH)"
                    % (lab, ", ".join(ARM_REGISTRY)))
        arms[lab] = load_arm(lab, path, want_aux=not args.no_aux)

    present = set(arms)

    # contrast set
    if args.contrasts:
        wanted = parse_contrast_list(args.contrasts)
    else:
        wanted = [c for c in PUBLISHED_CONTRASTS if set(c) <= present]
        wanted += [c for c in G_CONTRASTS if set(c) <= present]
    wanted = [c for c in wanted if set(c) <= present]
    if not wanted:
        raise SystemExit("no contrasts are computable from the arms given")

    # Holm family
    if args.primary:
        primary = parse_contrast_list(args.primary)
    elif "G" in present:
        # arm G's three contrasts are their own family: they are the questions
        # this arm was run to answer.
        primary = [c for c in G_CONTRASTS if set(c) <= present]
    else:
        primary = [c for c in PUBLISHED_PRIMARY if set(c) <= present]
    primary_keys = set(primary)

    # share bootstrap
    if args.share == "none":
        share_spec = None
    elif args.share:
        try:
            num, den = args.share.split("/", 1)
        except ValueError:
            raise SystemExit("--share wants NUM/DEN, e.g. D-F/D-C")
        share_spec = (parse_contrast_list(num)[0], parse_contrast_list(den)[0])
    elif {"C", "D", "F"} <= present:
        share_spec = (("D", "F"), ("D", "C"))
    else:
        share_spec = None

    # table diff columns
    if args.table_diffs:
        args.table_diffs = parse_contrast_list(args.table_diffs)
    else:
        cols = []
        if {"C", "F"} <= present:
            cols.append(("F", "C"))
        if {"D", "F"} <= present:
            cols.append(("F", "D"))
        if "G" in present:
            for c in G_CONTRASTS:
                if set(c) <= present:
                    cols.append(c)
        args.table_diffs = cols

    contrasts = []
    for hi, lo in wanted:
        tasks, diffs = paired_diffs(arms, hi, lo)
        contrasts.append(Contrast(hi, lo, tasks, diffs))
    # make sure the share's contrasts exist even if not in the reported set
    if share_spec:
        by = {(c.hi, c.lo) for c in contrasts}
        for pair in share_spec:
            if pair not in by and set(pair) <= present:
                tasks, diffs = paired_diffs(arms, pair[0], pair[1])
                contrasts.append(Contrast(pair[0], pair[1], tasks, diffs))

    print("armG_stats.py -- jj-benchmark skill A/B, paired-by-task estimator")
    print("arms: %s" % ", ".join(arms))
    report(arms, contrasts, primary_keys, share_spec, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
