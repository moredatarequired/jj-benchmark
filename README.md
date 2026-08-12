# Jujutsu Benchmark

This repository contains benchmarks for [Jujutsu (jj)](https://github.com/martinvonz/jj), a next-generation version control system.

This is a fork. We're reworking it to measure whether a jj skill makes Claude better at
jj — see [ROADMAP.md](ROADMAP.md) for what that involves and what's done so far.

You can view the upstream evaluation reports at [tabbyml.github.io/jj-benchmark](https://tabbyml.github.io/jj-benchmark/).

## Project Structure

- `tasks/`: Contains the benchmark tasks, each with its own instructions, bootstrap scripts, and tests.
- `jobs/`: Stores the results of benchmark runs.
- `scripts/`: Checks that run outside a benchmark run — task schema lint, post-run audit.
- `site/`: A Next.js application to visualize benchmark results.

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
turns it into a session-scoped `autouse` fixture, so all 53 tasks get the check without
53 edits, and when it fails every test in the file fails and the trial scores 0.

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
when the file is absent, unparseable, or records `anchored: false` — the last being the
three tasks whose bootstrap ships an empty directory, where creating the repository *is*
the task (`git_remote_add`, `template_formatting`, `working_copy_as_commit`). An anchor
that is not there is an infrastructure condition, and a rollout in which one missing file
zeroes every trial is worse than the vulnerability it closes. `--check` and
`--verify-untouched` are what make that loud, on the host, where it can be fixed.

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
`tests/anchor.py` exposes `anchored_change_id(description)`.

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
