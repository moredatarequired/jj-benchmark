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
