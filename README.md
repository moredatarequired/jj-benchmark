# Jujutsu Benchmark

This repository contains benchmarks for [Jujutsu (jj)](https://github.com/martinvonz/jj), a next-generation version control system.

This is a fork. We're reworking it to measure whether a jj skill makes Claude better at
jj — see [ROADMAP.md](ROADMAP.md) for what that involves and what's done so far.

You can view the upstream evaluation reports at [tabbyml.github.io/jj-benchmark](https://tabbyml.github.io/jj-benchmark/).

## Project Structure

- `tasks/`: Contains the benchmark tasks, each with its own instructions, bootstrap scripts, and tests.
  **There are 14 of them.** The suite was 53; `docs/suite_redesign_proposal.md` is the
  argument for cutting 39, and ROADMAP.md "What's done" #6 records the cut. New tasks are
  authored on top of these 14 rather than alongside the old set, so **no measurement taken
  before the cut describes the suite that exists now** — not the per-model baselines in
  `results/`, not the numbers in ROADMAP.md, not upstream's leaderboard.
- `jobs/`: Stores the results of benchmark runs.
- `scripts/`: Checks that run outside a benchmark run — task schema lint, post-run audit.
- `site/`: A Next.js application to visualize benchmark results.
- `docs/`: Longer-form write-ups. [`docs/known_limitations.md`](docs/known_limitations.md)
  records the known limitations in the integrity and floor machinery, and the decision
  taken on each.

## Contribution

This benchmark is evaluated with the [Harbor framework](https://github.com/harbor-framework/harbor)
and the [Pochi agent](https://github.com/TabbyML/pochi).

Here is an example of running the evaluation with a built-in agent (e.g., Codex) and Daytona:

```bash
harbor run \
    --agent codex \
    --model "gpt-5.2-codex" \
    --env daytona \
    --path ./tasks \
    --n-attempts 1 \
    --max-retries 5 \
    --n-concurrent 5 \
    --retry-include RuntimeError \
    --retry-include DaytonaError \
    --retry-include AgentTimeoutError
```

### The verifier runs without network access

There is no verifier environment to configure. Every task image installs
`pytest==8.4.1` and `pytest-json-ctrf==0.3.5` at build time, `tests/test.sh` installs
nothing, and each `task.toml` sets:

```toml
[verifier]
network_mode = "no-network"
```

so harbor denies the container egress for the whole verify phase. If verification ever
regrows a network dependency it fails immediately and visibly, instead of working on
your machine and flaking in a sweep.

This replaces the `--ve UV_NATIVE_TLS=1 --ve UV_HTTP_TIMEOUT=300` flags this README used
to require. Those configured `uv` inside the verifier container, and nothing in the
verifier uses `uv` any more, so both are now no-ops — drop them. `--ve` sets the
*verifier's* environment (`harbor/cli/jobs.py`), so it never affected anything else:
uv on the machine launching `harbor` reads its own ambient environment, and the four
task images that install `uv` for the *agent* to use are configured through `--ae`.

The network is still used to *build* the images — apt, the jj release tarball, and the
pip install above. That is a build-time cost paid once per image, not per trial, and a
build failure is loud.

After every run, audit the output before trusting the numbers:

```bash
python3 scripts/check_run_results.py jobs/<run-directory>
```

It reports any trial that produced no `verifier/ctrf.json` as `ERRORED-INFRA` — kept
separate from a genuine `reward: 0` — and exits non-zero if there are any. See
[ROADMAP.md](ROADMAP.md) for the canonical local invocation.

### The bootstrap integrity anchor

A verifier grades whatever repository it finds at the task's project path. On its own
that cannot tell a *solved* repository from a *wiped and rebuilt* one, and rebuilds have
been observed in real sweeps scoring full marks — including a pure-jj route
(`jj new -r 'root()'` then `jj restore --from <rev>`) that no blocklist of commands can
see. The anchor closes that.

**What it is.** `scripts/bootstrap_anchor.py --write` builds each task image, reads the
untouched bootstrap state out of a throwaway container, and writes
`tasks/<task>/tests/bootstrap_anchor.json` on the *host*: the `change_id` of every
bootstrap commit, plus the id of the last operation the bootstrap performed. Harbor
mounts the whole `tests/` directory read-only at `/tests`, so the anchor arrives beside
the verifier for free, exactly like `vacuity_floor.json` — nothing is added to the image,
and no copy exists inside the container for an agent to rewrite. `tests/conftest.py`
turns it into a session-scoped `autouse` fixture, so every task gets the check without a
per-task edit, and when it fails every test in the file fails and the trial scores 0.

**Why change ids and not commit ids.** A jj change id is generated *randomly* when a
commit is created and is *preserved* by a genuine `rebase`, `squash`, `describe`,
`abandon` or `restore`. So it is the one property that survives every legitimate solve
and that a rebuild cannot reproduce. Commit ids are content-derived — tree, parents,
description, author identity and timestamp — so they are forgeable in principle *and*
they change on every honest rewrite. Asserting them would both miss cheats and fail
correct solves. They are recorded for diagnosis only. Descriptions are attacker-writable
free text and are never the thing asserted.

**The anchor describes an image BUILD, not a Dockerfile.** Because change ids are random,
two builds of the same Dockerfile produce disjoint change id sets, and
`JJ_RANDOMNESS_SEED` is not an escape hatch — it is per-process, so it collapses every
commit in a bootstrap onto one change id. The anchor is therefore a **per-sweep build
artifact and is gitignored**; it is not in `scripts/lint_tasks.py`'s required files and CI
does not need it, because CI always builds cold. Run this immediately before a sweep,
against the same docker daemon the sweep will use:

```bash
python3 scripts/bootstrap_anchor.py --write             # measure the images
python3 scripts/bootstrap_anchor.py --check             # must be clean
python3 scripts/bootstrap_anchor.py --verify-untouched  # pre-flight, see below
harbor run ...                                          # then the sweep
```

Between `--write` and the sweep, **do not prune, do not `--no-cache`, and do not build
on a different daemon.** Anything that evicts a bootstrap layer re-randomises that task's
change ids. `--check` catches that by re-measuring and comparing; it reports a moved id
set with an unchanged `environment_sha256` (a content hash of the build context) as a
cold-cache rebuild, and a changed one as a real Dockerfile change to review. Docker image
ids are deliberately *not* the staleness key — buildx mints a new one on every build even
on a full cache hit.

`--verify-untouched` is the pre-flight, and it is the one that catches the dangerous
case: an anchor written before an image that was then rebuilt cold would make **every**
trial score 0, which reads as a model collapse rather than an infrastructure fault. For
each task it runs the real `tests/test.sh` against the untouched image with the real
`tests/` directory mounted at `/tests`, and asserts the anchor reports that it *holds*,
the reward is `0`, and a `ctrf.json` was written — the CI vacuity check plus the anchor,
end to end.

**A missing anchor abstains, it does not fail.** `tests/anchor.py` prints why and passes
when the file is absent, unparseable, or records `anchored: false`. That last case is for
a task whose bootstrap ships **no** jj repository, because creating it *is* the task; the
four tasks that were in that state (`git_remote_add`, `template_formatting`,
`working_copy_as_commit`, and `git_integration`, whose bootstrap shipped only a bare git
repo) were all cut when the suite was reduced to 14, so **every current task hands over a
real jj repository and every one of them is anchored.** The code path stays, because the
next task authored against a bare directory needs it. An anchor that is not there is an
infrastructure condition, and a rollout in which one missing file zeroes every trial is
worse than the vulnerability it closes. `--check` and `--verify-untouched` are what make
that loud, on the host, where it can be fixed.

### Commits a task is *allowed* to remove: `tests/anchor_exemptions.json`

Several jj operations legitimately make a change id stop resolving, so the strict check
above would score some **correct** solves 0. Measured on jj 0.38.0: `jj abandon` removes
the id; `jj squash --from B --into A` removes B's (and squashing the working copy into an
ancestor removes the working copy's, because jj abandons the emptied source and mints a
fresh working-copy commit); `jj new` / `jj edit` / `jj prev` / `jj next` moving off an
**empty, undescribed** working copy to anywhere that is not its descendant makes jj
auto-abandon it; `jj workspace forget` removes that workspace's working copy; and
`jj op restore` removes everything created after the operation restored to.

So `abandon_commits` is two abandons, `squash_range`'s own
`test_fix_commits_are_no_longer_visible` **asserts** those ids are gone, and
`rebase_branch` and `split_commit_interactive` both hand over an empty undescribed `@`
that the solve has to `jj edit` off, which auto-abandons it.

The escape hatch is a per-task, hand-written, committed file —
`tasks/<task>/tests/anchor_exemptions.json` — that names each such commit **with a
one-line reason**, so the file is its own review record:

```json
{
  "task": "abandon_commits",
  "may_disappear": [
    {"description": "commit B",
     "reason": "Requirement 1 IS `jj abandon` of this commit, so its change id necessarily stops resolving."}
  ],
  "may_be_divergent": [],
  "maintained_by": "hand-written, reviewed against instruction.md"
}
```

An entry names its commit by `description` (the same key `anchored_change_id()` uses) or
by `working_copy` (a workspace *name*, for an undescribed working-copy commit). An
exempted change id may be absent **or** present; nothing else about the anchor is
relaxed, and **the handover-operation check is never exempted on any task**, so
wipe-and-rebuild is still caught everywhere. `may_be_divergent` is the separate flag for a
task whose solve deliberately leaves one change divergent. No current task uses it —
`concurrent_operations`, the task it was written for, was cut when the suite was reduced
to 14 — but the divergence-shaped tasks on the roadmap will, so the schema keeps it.

The file is optional — absent means "nothing this task asks for removes a bootstrap
commit", which is true of 8 of the 14 tasks. `scripts/lint_tasks.py` enforces the schema
and prints every exemption and its reason on every CI run; `scripts/bootstrap_anchor.py
--write/--check` cross-checks each entry against the measured bootstrap, so an entry that
names nothing (or two things) fails on the host. A stale exemption file makes
`tests/anchor.py` *abstain* rather than fail, which `--verify-untouched` reports as a
problem because it asserts the anchor **holds**.

**Why not simply relax the invariant to "resolved at the handover operation".** Because
operations are append-only, so the pure-jj rebuild route (`jj new -r 'root()'` +
`jj restore --from <rev>`, then `jj abandon` the originals) leaves the handover operation
and all of its commits resolvable *at that operation*. That route has been observed
scoring reward 1.0 in a real sweep, and the weakened invariant passes it. Measured on
`abandon_commits`: reward 1.0 before the anchor, 0 with it. So the strict "resolves now"
check is kept everywhere, and weakened only for a named commit with a written reason.

### Telling an anchor failure from a task failure, out of `ctrf.json`

A missed exemption would produce a false zero that looks exactly like a model failing the
task. So every violation message starts with the token `BOOTSTRAP_ANCHOR_VIOLATION`
followed by `codes=` (`ANCHOR-CHANGE-ID-MISSING`, `ANCHOR-CHANGE-ID-DIVERGENT`,
`ANCHOR-HANDOVER-OP-GONE`, `ANCHOR-REPO-GONE`, `ANCHOR-REPO-UNREADABLE`), and
`pytest-json-ctrf` records the rendered message in the `trace` field of **every** test
entry. So one grep over a finished sweep finds every trial the anchor zeroed:

```bash
grep -l BOOTSTRAP_ANCHOR_VIOLATION */*/verifier/ctrf.json
```

A missed exemption shows up as `ANCHOR-CHANGE-ID-MISSING` on its own; a rebuild brings
`ANCHOR-HANDOVER-OP-GONE` with it. The token is never printed on the holds or abstain
paths.

### The mandatory idiom for per-task assertions

`anchored_change_id()` raises `AnchorUnavailable` when there is no anchor — and there is
none in CI, which always builds cold, nor in any sweep run without `--write`. A verifier
that calls it bare is therefore broken in CI. Use the fallback resolvers instead:

```python
from anchor import change_id_or_fallback, working_copy_or_fallback

TARGET = change_id_or_fallback("Base", 'description(substring:"Base")')
WC     = working_copy_or_fallback("@", workspace="default")
```

Each returns the anchored change id when the anchor can supply it and otherwise returns
the description-based revset the test used before, after printing a line that says the
identity claim was **not** made. The assertion is then exactly as strong as it was before
the anchor existed — never weaker, and never an error.

`working_copy_or_fallback` exists because anchor keys are description *first lines*, and
`""` is not a unique key: `workspace_update_stale`'s bootstrap holds two commits described
`""`, and before the cut to 14 there were bootstraps holding three. The anchor therefore records the handover `@` of
every workspace under a reserved `working_copies` key, addressed by workspace name.
`anchored_change_id("")` **fails loudly** on an ambiguous description and points at that
key rather than silently picking one of the candidates.

**One hard rule if you edit `tests/conftest.py`.** It must stay import-trivial. An
exception raised while pytest is *importing* conftest makes pytest exit 4 having reported
zero tests, `test.sh` then writes `verifier_error.txt`, and
`scripts/check_run_results.py` classifies the trial `ERRORED-INFRA` — recording a cheat
as broken infrastructure. Every failure path must go through the fixture body, where
`pytest-json-ctrf` still emits one entry per test with status `failed` and the trial
scores an honest 0.

**What the anchor does not close.** It proves the bootstrap commits still exist; it does
not prove they are the commits the verifier graded. An agent can fabricate a parallel
stack from `root()`, move the bookmarks onto it and destroy nothing — every anchored
change id is still visible, so the fixture holds. Closing that needs each task's scored
assertions to address the graded commit by its anchored change id, for which
`tests/anchor.py` exposes `anchored_change_id(description)` (through
`change_id_or_fallback`, per the idiom above).

Two smaller residuals, stated rather than hidden. On the 4 tasks whose handover working
copy is exempt (`absorb_changes`, `operation_recovery`, `rebase_branch`,
`split_commit_interactive`), that one empty undescribed commit is no longer evidence — it
carries no content, and jj discards it silently on any `jj new`/`jj edit`, so requiring it
would fail honest solves. And on the 2 tasks whose only bootstrap commit *is* an empty
undescribed working copy (`workspace_add`, `template_customize_log_output`) it is
deliberately **not** exempt, because it is the graded object — with the consequence that an
agent who solves such a task by creating a *new* commit instead of describing the one it
was handed now scores 0. That is a scoring-shape change, and it is intended.

### Evaluation Details

Before starting the evaluation, you should set the necessary environment variables.
For example, when using Codex, you should export `OPENAI_API_KEY` before running Harbor.
If using Pochi, you should export `POCHI_API_KEY`, etc.

Evaluation can be run locally with Docker, [Daytona.io](https://www.daytona.io/),
or other cloud services by using the `-e` or `--env` arguments with values like `docker` or `daytona` (`docker` is the default).

When running with Daytona, please note that Daytona blocks some network access for tier 1 and tier 2 users.
If you meet any network issues, please refer to
[Daytona network limits](https://www.daytona.io/docs/en/network-limits/).

People are welcome to contribute with built-in agents (e.g., supporting `claude-code`, `codex`, `gemini-cli`, etc.)
using the `--agent` or `-a` arguments, or other custom agents like the [Pochi agent](https://github.com/TabbyML/pochi).

For running the Pochi agent specifically,
you should use `--agent-import-path` to point to the path of the Pochi agent,
such as `agents.pochi:Pochi`, where `agents.pochi` is the import path and `Pochi` is the class name of the Pochi agent.
