# Why this fork exists

We want to know whether giving Claude a jj skill actually makes it better at jj, and
which of several skill variants is best. This benchmark is the closest thing that
exists to a measuring device for that. It is not usable for it as shipped.

This fork is where we turn it into an instrument. Upstream is `TabbyML/jj-benchmark`;
we're not currently sending changes back, though some of what's here is worth
contributing eventually.

Pushing to upstream is disabled locally on purpose:

```
upstream  https://github.com/TabbyML/jj-benchmark  (fetch)
upstream  DISABLED_NO_PUSH_TO_UPSTREAM             (push)
```

## The problem, measured

*Read this section as history.* Every number and every task name below describes the
**53-task** suite as it stood before the cut recorded in "What's done" #6. That suite no
longer exists: 39 of its tasks were deleted, 14 remained, and ten new ones have been
authored on top of those for a suite of 24 today, so nothing here — the 53/53
scores, the per-model failure lists, the "41 of 53 instructions" count — is a claim about
what the suite does now. Several of the tasks named below have been deleted outright.

Two things were wrong. Three tasks were broken outright, and the rest are too easy.

**Broken tasks.** `bookmark_push` and `undo_mistaken_rebase` built `FROM
pochi-browser-verification-base`, an image that isn't published anywhere, so nobody
outside TabbyML could build them. `rebase_branch` was worse: its commit-count
assertion used the template `"commit_id\n"`, and jj reads a bare newline as whitespace
between expressions rather than output, so every commit id concatenated onto one line
and `len(commits) == 2` was unreachable for any repo state. That's why all eight models
on the leaderboard score 0/8 on it. It isn't a hard task, it's an impossible one.

`undo_mistaken_rebase` also had a vacuous verifier — `assert "undo" in jj_op_log` —
which `jj undo` satisfies by writing its own operation description. We confirmed a
single bare `jj undo`, with no rebase at all, passed it. Free reward for every model
on the board.

**Saturation.** Post-fix, on all 53 tasks:

| model | score | cost | failures |
|---|---|---|---|
| Opus 5 | 53/53 | $6.09 | — |
| Sonnet 5 | 53/53 | $4.68 | — |
| Haiku 4.5 | 49/53 | $2.25 | `log_template_author`, `restore_specific_revision`, `root_commit`, `workspace_forget` |

Two of the three models are pinned at the ceiling. A skill A/B on either reads 53/53
against 53/53 no matter how good or bad the skill is. Haiku is the only model with any
signal, and it's the one to iterate against.

The tasks are easy for two specific reasons, both fixable:

- 41 of the 53 `instruction.md` files had an `## Implementation` section listing the
  commands to run. A jj skill cannot help with a prompt that already contains the
  answer. Those sections were deleted, and the instructions have since been rewritten
  down to one end-state sentence apiece naming no jj command (see "What's done" #7), so
  the "21 tasks still name their answer command" count is history too.
- All 53 tasks set `allow_internet = true`, so the agent can read the jj docs — which
  is the thing the skill is supposed to supply. The benchmark competes with what we're
  trying to measure.

Historically, 36 of 52 tasks were passed by all eight models, and the frontier spread
was 87–98%, about six tasks of resolution across the whole leaderboard.

## What's done

| | |
|---|---|
| #1 | `bookmark_push`, `undo_mistaken_rebase` → `FROM ubuntu:24.04`. 51 runnable tasks → 53 |
| #2 | Real state assertions for `undo_mistaken_rebase`. nop agent scores 0.0, real agent 1.0 |
| #3 | Dropped the Pages deploy workflow — we're not publishing a leaderboard |
| #4 | `rebase_branch` template separator. 0/8 across every model → 3/3 at k=3 |
| #5 | Deleted the `## Implementation` section from all 41 tasks that had one. Task data the tests assert on was migrated into Requirements first |
| #6 | **Cut the suite from 53 tasks to 14** (`docs/suite_redesign_proposal.md`). 39 deleted: duplicates of a survivor, tasks grading HOW rather than WHAT, two that were passable without running jj at all, and the 7 that were structurally sound but 5/5 on all three models — a saturated task contributes nothing to a paired comparison and still costs an image build and a verifier run per sweep. New tasks are authored on top of the 14, not alongside the old set |
| #7 | **Roadmap item 2, all three levers.** The agent's network is `network_mode = "allowlist"` with `gateway-us.pydantic.dev` as the only host, on all 24 tasks — no jj docs (#10), with (#12) replacing the deprecated `allow_internet` key. Every `instruction.md` is one end-state sentence naming no jj command (#15) and (#16). Reward is floor-corrected partial credit off the CTRF per-test report, not a collapsed 1 or 0 (#20) |
| open | Shared base image so harbor stops reinstalling Claude Code per trial. Still unbuilt: all 24 task images are `FROM ubuntu:24.04` and none carries Claude Code |

Sweep write-ups live in `results/`; the per-trial records do not. `jobs/` is gitignored
since (#7), so trial directories go whole to an orphan `archive/…` branch cited by commit
— `973a3827c1` for the 24-task baseline, `b7746772c4` for the A/B. Whether our numbers
should also sit on the site beside the Pochi runs is still undecided.

## Roadmap

**1. Make iteration fast.** Still open, and the measured constraint has moved: the
2026-08-14 sweep managed 326 trials in 59 minutes at `-n 8` and died on **disk**, not on
concurrency — usable disk was about 40 GB, harbor rebuilds the task image per trial
(`pull_policy: build`, `delete: true`), and BuildKit cache runs about 40 MB per trial, so
a 480-trial sweep needs roughly 19 GB of headroom at launch. Two more causes, both silly:

- `agent_setup` is 45% of all trial-seconds — harbor installing Claude Code into every
  container, downloading the same binary every time. Baking it into a shared base
  image removes the phase; the adapter skips its install when `claude` is on PATH.
  (The cut to 14 tasks shrinks the sweep in the same direction, but it does not fix
  this: the phase is per *trial*, so it comes straight back as `-k` goes up.)
- Docker Desktop is capped at 7.75 GiB on a 64 GiB machine, the reason given for
  concurrency 3. Raise it, drop `--override-memory-mb` to 512 (`task.toml` asks for 8192,
  which is fantasy), and we're CPU-bound at 16 instead. Untested since: the one sweep on
  record ran at `-n 8` in an agent container elsewhere, and died on disk, not memory.

Target is 2–4 minutes per sweep. Separately, every one of the 24 Dockerfiles hardcodes
the x86_64 jj tarball, so everything runs under Rosetta on Apple Silicon; jj ships an
aarch64 build.

**2. Create headroom — done.** All three levers landed; see "What's done" #7.

**3. Re-baseline** all three models. Half done: `results/2026-08-14-baseline-24.md` covers
haiku and sonnet on the 24 tasks, informed arm, with **no opus arm** and 326 of a designed
552 trials, so n is 5–7 per cell. It answers what the item was for — sonnet is 1.000 on 20
of 24 (mean 0.9173), haiku has 19 tasks off ceiling (0.6002), so **measure on haiku**; a
sonnet A/B would rest on three tasks, one of them with a known-broken grader.

All three of `plan.md` §4's friction points are now touched, not none: pushing without a
bookmark is `bookmark_left_behind`, and `..` versus `::` is `unmerged_tips`, which grades
`heads(main..)` against `heads(all())` and `::main` (`rebase_touched_commits` also grades
revset output). Conflict markers are covered in substance by `propagated_conflict`, though
§4's own case — accidentally *committing* markers — is graded nowhere.

**4. Build the A/B harness — built, and run.** `results/2026-08-16-skill-ab.md` is six
arms on the 24-task suite at haiku, 576 trials, at `k=4` rather than the `k=5` asked for
here; read the numbers there. On this item's own stopping condition — a decoy scoring like
the real skill would mean the tasks aren't sensitive to skill content — the answer split:
the published third-party skill did not separate from control (C − A +0.013, p = 0.745) and
beat the decoy by only +0.060, while our hand-written document did (F − B +0.146,
p = 0.0095).

**5. Score efficiency, not just pass/fail.** Partly answered, as analysis rather than an
endpoint: the A/B reports turns and Bash calls per arm, cost tracks turns almost exactly
(log-log slope 0.94 over 576 trials), and the best-scoring arm was also the cheapest —
23.1 turns against the control's 38.6. Harbor records per-trial tokens and phase
latencies already, and job config has a `metrics` hook; nothing here configures one yet.

## Things worth knowing

**Cost doesn't track the rate card.** Weaker models burn more tokens, so the spread
compresses hard: Opus used 5.6M input / 59k output, Sonnet 9.8M / 54k, Haiku 13.0M /
118k. Actual costs were $6.09 / $4.68 / $2.25, not the 5× and 15× ratios the pricing
implies. Budget from those numbers.

**And harbor's sonnet figure is wrong by exactly 1.5×.** Sonnet 5 is on introductory
pricing ($2/$10 per MTok) against harbor's list ($3/$15), so take two-thirds of any
harbor-reported sonnet cost — haiku and opus need none, so do not rescale twice. For
sizing: $39.53 harbor / $31.24 corrected bought 326 baseline trials, $46.94 the A/B.

**Don't run two agents in one checkout.** We did, and it cost real cleanup — one
session stalled for two hours because another had rewritten a file under it. Give each
its own worktree up front:

```bash
git worktree add .worktrees/<name> -b <branch> origin/main
```

**Running it locally.** Needs `DOCKER_DEFAULT_PLATFORM=linux/amd64` (x86_64 jj
tarball), `POCHI_API_KEY=dummy` (every `task.toml` substitutes it even for other
agents), and a memory override. `claude-code` is a built-in harbor adapter, so no
Pochi dependency. This is the canonical invocation:

```bash
DOCKER_DEFAULT_PLATFORM=linux/amd64 POCHI_API_KEY=dummy \
uvx --from harbor==0.20.0 harbor run \
  --agent claude-code --model claude-opus-5 --env docker \
  --path ./tasks --override-memory-mb 2048 --n-concurrent 3 -y
```

One thing that line leaves out: **haiku needs its dated id**, `claude-haiku-4-5-20251001`
and not a bare `claude-haiku-4-5` — and haiku is the model everything is measured on.

**Don't `docker system prune -a` to free space in an agent container.** A cold `docker
build` cannot succeed there at all — the pip layer dies with `CERTIFICATE_VERIFY_FAILED`
against the proxy's re-terminated chain (`results/2026-08-14-baseline-24.md`) — so
pruning the cache destroys the ability to build rather than recovering room to run.

Then, before you believe any of the numbers:

```bash
python3 scripts/check_run_results.py jobs/<the-run-you-just-did>
```

**The verifier no longer touches the network, and is no longer allowed to.** Each
task image installs `pytest==8.4.1` and `pytest-json-ctrf==0.3.5` at build time,
`tests/test.sh` runs `python3 -m pytest` straight out of the image, and every
`task.toml` sets `[verifier] network_mode = "no-network"`, which the docker
environment enforces by denying the container egress for the verify phase.

This closes a failure mode that had no error signal. `tests/test.sh` used to bootstrap
`uv` from astral.sh and resolve three packages from pypi on every trial. When that
failed, harbor still wrote `reward: 0.0`, with `n_errors: 0` and `exception_stats: {}`
— a broken verifier scored exactly like a task the agent genuinely failed, and the run
looked clean. Two trials of one haiku sweep were lost that way; a TLS chain the
bundled `uv` did not trust could take out a whole sweep the same way.

The `--ve UV_NATIVE_TLS=1` and `--ve UV_HTTP_TIMEOUT=300` flags this section used to
insist on are therefore obsolete. `--ve` sets the *verifier's* environment
(`harbor/cli/jobs.py` merges it into `config.verifier.env`), and nothing in the
verifier uses `uv` any more. They are not harmful, just inert — drop them. Note this
is a separate concern from `uv` on the machine launching `harbor`, which reads its own
ambient environment, and from the one remaining task image that installs `uv` for the
*agent* (`template_customize_log_output`), which is configured through `--ae`.

The network is still needed to *build* the images: apt, the jj release tarball, and
that pip install. That is per-image and cached, not per-trial, and a build failure is
loud rather than silent.

Keep running `check_run_results.py` afterwards. It asserts every trial wrote
`verifier/ctrf.json` — the file `pytest --ctrf` produces — and reports any trial
without one as `ERRORED-INFRA` rather than as a failure, exiting non-zero. A trial
whose `verifier/test-stdout.txt` never reaches `test session starts` is the
corroborating tell. Hermetic verification removes the biggest cause of a missing
report; it does not make "no report" impossible, and a run with a missing report is
still a run whose number is wrong.

**The site is built from the repo.** `site/scripts/compute-tasks.ts` walks
`jobs/*/*/result.json` at build time and reads prompts from `tasks/*/instruction.md`.
Drop a job directory into `jobs/` and it shows up — but `jobs/` is gitignored, so it shows
up only for you. The leaderboard keys rows on model + agent, and every upstream row is the
Pochi scaffold, so our claude-code numbers aren't apples-to-apples with theirs.

**Our task set and upstream's no longer overlap enough to compare.** Upstream's runs
show 52 tasks; ours showed 53 (`revset_querying_bob` was added after their last job) and
now show 24, of which several have had their verifiers rewritten. Any comparison against
an upstream number is a comparison against a different instrument, task names in common
notwithstanding.
