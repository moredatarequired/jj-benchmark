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
  answer. Those sections are now deleted (see "What's done"), but 21 tasks still name
  their answer command in Background or Requirements.
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
| in flight | Shared base image so harbor stops reinstalling Claude Code per trial |

Baseline job results for all three models are in `/tmp/jjjobs/` and not committed yet —
dropping them into `jobs/` makes them show up on the site, which is worth doing once we
decide whether we want our numbers sitting in the same table as the Pochi runs.

## Roadmap

**1. Make iteration fast.** A full sweep is 26 minutes at concurrency 3, which is too
slow to tune skill variants against. Two causes, both silly:

- `agent_setup` is 45% of all trial-seconds — harbor installing Claude Code into all
  53 containers, downloading the same binary every time. Baking it into a shared base
  image removes the phase; the adapter skips its install when `claude` is on PATH.
- Docker Desktop is capped at 7.75 GiB on a 64 GiB machine, which is the only reason
  concurrency is 3. Raise it, drop `--override-memory-mb` to 512 (`task.toml` asks for
  8192, which is fantasy), and we're CPU-bound at 16 instead.

Target is 2–4 minutes per sweep. Separately, all 53 Dockerfiles hardcode the x86_64 jj
tarball, so everything runs under Rosetta on Apple Silicon; jj ships an aarch64 build.

**2. Create headroom.** In order of leverage: set `allow_internet = false`; strip the
remaining command names out of the 21 instructions that still give the answer away in
Background or Requirements (the `## Implementation` sections themselves are already
gone); award partial credit from the CTRF per-test results instead of collapsing
pytest to 1 or 0.

**3. Re-baseline** all three models. If a frontier model still scores near 53/53, the
tasks are too easy to measure skills with regardless of scoring, and the answer is new
tasks rather than more knobs. `plan.md` §4 lists jj friction points — pushing an
anonymous commit with no bookmark, committing conflict markers, undo after a push —
and none are implemented. Those are the cases where the Git-shaped answer is wrong,
which is exactly where a skill should earn its keep.

**4. Build the A/B harness.** Harbor already has skill injection: `--skill` takes a
local path or a git source and mounts `SKILL.md` directories into the agent
environment, so variants are just different `--skill` values on otherwise identical
jobs. Run three arms — no skill, the real skill, and a deliberately generic or wrong
one. If the decoy scores the same as the real skill, the task set isn't sensitive to
skill content and no amount of variant tuning will show anything. Run that check
before building variants. Use `-k 5` at minimum; with `k=1` a two-task difference is
indistinguishable from noise.

**5. Score efficiency, not just pass/fail.** A good skill should show up as fewer
turns and fewer wrong commands even where everyone passes. Harbor records per-trial
tokens and phase latencies already, and job config has a `metrics` hook.

## Things worth knowing

**Cost doesn't track the rate card.** Weaker models burn more tokens, so the spread
compresses hard: Opus used 5.6M input / 59k output, Sonnet 9.8M / 54k, Haiku 13.0M /
118k. Actual costs were $6.09 / $4.68 / $2.25, not the 5× and 15× ratios the pricing
implies. Budget from those numbers.

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
ambient environment, and from the four task images that install `uv` for the *agent*,
which is configured through `--ae`.

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
Drop a job directory into `jobs/` and it shows up. The leaderboard keys rows on
model + agent, and every upstream row is the Pochi scaffold, so our claude-code
numbers aren't apples-to-apples with theirs.

**`revset_querying_bob` has never been run upstream.** It was added after their last
job, which is why their runs show 52 tasks and ours show 53.
