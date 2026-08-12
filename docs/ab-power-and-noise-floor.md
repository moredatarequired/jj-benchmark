# A/B power and the noise floor

How large a difference this benchmark can actually detect between two agent configurations, and how to size a sweep so the
answer means something. Written for planning a skill A/B, not for reading end to end.

Basis: 795 trials on disk — 53 tasks x 5 attempts x 3 model families, every cell full, one tree (`68525335e6`), 2026-08-12.
Strict pass means reward >= 1.0. The families appear below as **A** (240/265 strict passes, 90.6%), **B** (254/265, 95.8%) and
**C** (264/265, 99.6%). Every number comes from that data plus local simulation over it.

## 1. The decision rule

A/B here is a paired design: the same tasks in both arms, N attempts per task per arm. You read off the **net gap** G, total
strict passes in the skill arm minus total strict passes in the control arm. The recommended test is **exact McNemar** on (task,
attempt) pairs; its threshold depends on how many pairs disagree, so the rule is a function of the discordant count `n`:

| discordant pairs `n` | 6 | 10 | 15 | 25 | 38 | 50 | 76 | 100 | 153 |
|---|---|---|---|---|---|---|---|---|---|
| smallest significant net gap | 6 | 8 | 9 | 11 | 14 | 16 | 20 | 22 | 27 |

At 4 or fewer discordant pairs nothing is significant. At the discordance rate our fitted rates imply for family A (`E[n] = 2N x
sum_t p_t(1-p_t)`, that sum being 3.823 over 53 tasks and 2.501 over 15):

| N | 53 tasks: trials/arm | expected `n` | critical gap | as pp | 15 tasks: trials/arm | expected `n` | critical gap | as pp |
|---|---|---|---|---|---|---|---|---|
| 3 | 159 | 22.9 | **11** | 6.92 | 45 | 15.0 | **9** | 20.0 |
| 5 | 265 | 38.2 | **14** | 5.28 | 75 | 25.0 | **11** | 14.7 |
| 10 | 530 | 76.5 | **20** | 3.77 | 150 | 50.0 | **16** | 10.7 |
| 20 | 1060 | 152.9 | **27** | 2.55 | 300 | 100.1 | **22** | 7.33 |

Read the threshold off the discordant count you actually observe, not off this table: at N=5 on 53 tasks a realised `n` in 26-50
moves it across 12-16.

**If you prefer the paired sign-flip**, its equivalent on 53 tasks is a band, not a sharp threshold, because it weighs how the
gap is spread across tasks and not only its total. As null-q97.5 / half-the-time / nearly-always gaps that is 9 / 11 / 13 at
N=3, 12 / 13 / 17 at N=5, 17 / 19 / 23 at N=10 and 24 / 26 / 32 at N=20. McNemar's sharp 14 at N=5 sits inside that 13-to-17
band and is the stronger rule, firing deterministically where the sign-flip at 13 is a coin toss.

## 2. Recommended design for a K-arm skill sweep

Model family A, K skill arms plus one shared control, strict-pass endpoint, exact McNemar as the primary test, permutation max-T
across arms, run on the 15 tasks that discriminate for family A: `abandon_commits`, `diff_revisions`, `diffedit_interactive`,
`duplicate_commit`, `edit_commit_message`, `git_import`, `log_template_author`, `next_prev_navigation`, `rebase_branch`,
`restore_interactive`, `restore_specific_revision`, `split_commit_interactive`, `squash_range`, `template_customize_log_output`,
`template_formatting`.

N is the smallest value reaching 80% power against a skill that removes **half** the remaining per-attempt failures on those
tasks. The MDE is given as S, extra strict passes summed across the suite per attempt round, because a percentage gap is not
comparable across suite sizes: the same S reads much smaller on 53 tasks than on 15.

| K arms | N | total trials | MDE as S | on 15-task suite | on 53-task suite | cost | p95 worst | wall clock, 16-way |
|---|---|---|---|---|---|---|---|---|
| 1 | 15 | 450 | 1.58 | 10.5pp | 2.97pp | $32 | $113 | 0.3h |
| 3 | 15 | 900 | 1.72 | 11.5pp | 3.25pp | $65 | $227 | 0.7h |
| 5 | 15 | 1350 | 1.82 | 12.2pp | 3.44pp | $97 | $340 | 1.0h |
| 12 | 20 | 3900 | 1.76 | 11.7pp | 3.31pp | $280 | $983 | 2.8h |

Total trials is `(K+1) x 15 x N`. Cost uses the measured mean of $0.0718 per trial; the p95 column prices every trial at the
measured p95 of $0.252; wall clock uses the measured mean duration of 41.4s at 16-way concurrency. Both cost columns are lower
bounds, since a skill arm ships extra prompt text every turn: budget 10-30% above.

Nothing here is budget-limited. For more resolution, N=30 costs $65 / $129 / $194 / $420 for K = 1 / 3 / 5 / 12 and detects a
skill removing 31% / 34% / 36% / 39% of remaining failures. Below roughly 30% nothing on the simulated grid reaches 80% power,
so treat that as the practical floor.

Add a regression check on the 38 saturated tasks at N=2 (152 trials at K=1 rising to 988 at K=12, $11 to $71). Dropping those
tasks is what makes the design affordable, and this is the one thing it costs: a skill that breaks something previously working
would otherwise be invisible.

## 3. Recommendations, each with its reason

- **Strict pass as the primary endpoint.** At matched intervention strength mean reward needs 1.3-1.5x the trials for the same
  power: where a cell's rewards take only two values, reward is an exact affine function of the pass indicator and carries
  identical information, and that covers 158 of 159 cells. Relative efficiency of reward against strict pass is 0.61 / 0.88 /
  1.00 for A / B / C.
- **Mean reward as a pre-registered secondary.** It is the only endpoint that can see an improvement which does not flip a test
  from fail to pass. Against that, strict pass has literally zero power, flat at alpha for every N and effect size, while reward
  reaches 80% power at a 43% lift. Power the design on strict pass; do not treat the pair as two shots at significance.
- **Exact McNemar on (task, attempt) pairs as the test.** Never anti-conservative here (realised alpha median 0.029, never above
  0.047 over 162 null cells), and it beat the paired sign-flip in 182 of 185 design cells, by 1.57x when the effect is
  concentrated in a few tasks, the most plausible model of a real skill.
- **Not the paired sign-flip or signed-rank at small task counts.** With T informative tasks their smallest attainable two-sided
  p is `2^(1-T)`: 0.0625 at T=5, 1.0 at T=1. On the small discriminating subsets they cannot reject at any N.
- **Not an unpaired comparison of pooled rates.** Anti-conservative in 5 of 162 null cells (realised alpha up to 0.072), and the
  only test that saturated tasks actively harm.
- **Not a reward-endpoint cluster bootstrap over tasks, for deciding.** Realised alpha ran up to 0.175 against a nominal 0.05.
  Show the interval if you like the picture; do not test on it.
- **Permutation max-T for multiplicity.** Uncorrected, K=12 arms give a 29-31% chance per sweep of crowning a useless arm.
  Bonferroni and Holm run conservative (0.024-0.050); max-T alone tracks nominal (0.038-0.056). Cheaper still: pre-register one
  primary arm, which makes K=1 and the question disappears.

## 4. The noise model behind those numbers

**Task identity is the dominant variance component, so pair on it.** The intraclass correlation of strict pass is 0.277 (A) and
0.437 (B), so pairing on task removes 41.7% and 54.5% of trial-level variance for free. For C it is 0.000, not because pairing
is wrong but because at a 99.6% pass rate there is no per-task structure left to pair on. The heterogeneity is real: against the
null that all 53 tasks share one pass probability, the dispersion ratio is 2.125 for A (p = 4.2e-06) and 2.776 for B (p =
1.3e-10); for C, 1.004 (p = 0.466).

**Do not use `p = k/5` as the per-task rate.** It assigns zero variance to every task that went 5/5, and it is falsified out of
sample: fitted to the previous day's sweep of family A it gives the observed next sweep a log-likelihood of exactly minus
infinity, assigning probability zero on 8 tasks. 17 of 53 tasks changed their pass count between those sweeps, and 7 of the 39
at 5/5 stopped being 5/5. A fitted beta-binomial is best calibrated of the three tried (log-likelihood -52.88 against -57.24 for
Jeffreys), so all planning numbers use it: Beta(2.6965, 0.2881) for A, Beta(1.2215, 0.0502) for B. For C the fit is degenerate
on the boundary, so C falls back to Jeffreys.

**Five attempts is not much.** An exact 95% interval for a cell at 5/5 is [0.478, 1.0], so a task that looks deterministic is
consistent with a 52% per-attempt failure rate. Paired, a single task can never be significant: the best possible outcome, all 5
pairs discordant in one direction, gives a two-sided p of 0.0625. All power comes from aggregating across tasks.

**Saturated tasks contribute exactly zero.** Padding a 15-task design out to 53 with all-pass tasks leaves the summed effect
(1.5), the variance (1.056 at N=5) and every paired test's reject decision bit-identical, while burning 10 trials per added task
per attempt round. At fixed budget the squared noncentrality is `(B/2) x (mean E)^2 / (mean Var)`, in which the task count
cancels: N against T is a wash, and only *which* tasks are in the suite matters. Dropping the saturated tasks is worth
1.74-1.88x, an order of magnitude more than the 22-32% multiplicity costs. Select them on failure rate, not on variance:
`squash_range` under family A is the most informative task on the suite (information 0.667 against 0.024-0.12 for the rest) yet
has zero within-cell variance, so a `p(1-p)` criterion scores it zero and discards it.

**The ceiling binds before the noise floor does.** If a skill fixed every failure we observed, the 53-task suite mean would move
9.43pp for A, 4.15pp for B and 0.38pp for C, against smallest detectable gaps at 5 attempts per task of 6.17 / 3.57 / 6.02pp.
For C the ceiling is 16x below its own noise floor, so no N and no test reaches 80% power: C is saturated, not underpowered.
Measure on A, or add harder tasks.

**Selecting tasks on the data you then analyse will fool you.** Screening family A on 2 of 5 attempts picks 8.3 tasks against
the 15 that fail somewhere in all 5; only 51% of those fail again in the held-out attempts, the selected set covers 28% of the
held-out shortfall, and its estimated failure rate is overstated 2.2x (3.6x on the reward scale). For C the precision is 0.00,
pure noise-chasing. At equal budget the screened design still wins by about 2.2x, so the budget argument survives but the
inference does not. Treat these 795 trials as the screening set and the next sweep as the confirmation.

## 5. Re-deriving an MDE for a design not tabulated here

For the mean-gap statistic with per-task effects `delta_t` and per-task rates `p_t`:

```
S = sum_t delta_t                     total extra passes across the suite, per attempt round
V = (2/N) * sum_t p_t * (1 - p_t)     variance of that total
z = S / sqrt(V)
```

80% power at two-sided 0.05 needs `S >= 2.8016 * sqrt(V)`; in suite-mean units, `Delta_MDE = 2.8016 * sqrt(V) / T`. For a K-arm
design multiply the resulting S by the max-T inflation factor: 1.05 at K=2, 1.09 at K=3, 1.16 at K=5, 1.26 at K=12.

Accuracy against simulation: within 5-10% for diffuse effects on any test, mildly conservative because it evaluates V at the
null. Two failure modes. At N=2 or 3 the local-alternative premise is void and it over-predicts by 15-25%. For effects
concentrated in a few tasks it *understates* the needed effect by 1.8-2.2x for the sign-flip and rank tests, which calibrate
against observed cross-task dispersion, but stays good to about 1.1x for McNemar, which does not: plan with it only alongside a
trial-pooling test. On the recommended design the simulated-to-analytic S ratio runs 0.93 at N=5 and 1.00 at N=20 and above.

## 6. Cost, measured

Per-trial cost over the 265 trials per family already run: **A $0.0718** (median $0.042, p95 $0.252, max $0.672), **B $0.0684**,
**C $0.1437**. A costs more per trial than B despite the cheaper token price, because it takes 12.7 turns against B's 5.7, so
optimising a sweep for model price is the wrong optimisation. A also has the worst tail: its most expensive 5% of trials are 26%
of spend and its p95 duration is 132s against a 41s mean, so pricing at p95 is not paranoia.

## 7. Caveats, with the direction each one pushes

- **The swept tree predates the hardening merges.** These 795 trials ran at `68525335e6`; `main` is now several hardening
  changes ahead, one of which deliberately changes scoring on `describe_commit` and six siblings so a solve that only matches a
  description now scores 0. Post-hardening failure counts will be higher, so variance will be higher and the MDEs above are
  **slightly optimistic** on the affected tasks.
- **Known false passes push the same way.** They inflate estimated pass rates toward the ceiling, which understates the effect
  you can detect. The false-pass detector has roughly a 50% blind spot, so any count of them is a floor, not a total.
- **Five attempts per cell is small, and 5/5 is a ceiling rather than proof of determinism.** Two tasks sat at 4/4, looked
  deterministic, and dropped to 4/5 on a fifth attempt.
- **All of this is specific to these models and this suite as of 2026-08-12.** Re-estimate the variance after any verifier or
  scoring change: a grader fix moves per-task pass rates by more than sampling noise does.
