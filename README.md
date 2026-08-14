# Archive: per-trial records, 2026-08-14 baseline (24 tasks, informed arm)

This is an **orphan branch**. It shares no history with `main` and carries no
project source — only the raw harbor job directory for one sweep, so that the
numbers in `results/2026-08-14-baseline-24.md` can be checked against the
records they were derived from.

`jobs/` is in the repository's `.gitignore` on every normal branch, which is
why these records live here rather than in the results PR. Nothing on this
branch is meant to be merged.

## What is here

`jobs/2026-08-14__21-17-36/` — the complete job directory, 327 trial
directories and 4152 files.

| | |
|---|---|
| Job id | `2026-08-14__21-17-36` |
| Suite | `repro/2026-08-14-informed-arm-images` @ `42273ba1ac`, 24 tasks |
| Models | `claude-haiku-4-5-20251001`, `claude-sonnet-5` |
| Designed | 552 trials; `config.json` records 480 (the opus 72 were a separate invocation that never launched) |
| Recorded | 326 — 273 scored, 53 ERRORED-INFRA |
| Trial directories | 327; the extra is `git_fetch_remote__mx2TCa5`, still running when the sweep died, so it has no `result.json` |
| jj | 0.44.0 in every image |
| harbor | 0.20.0 |

The suite pin is a reproduction branch, not `main`. It is `main` @ `9dc4ac6ae9`
plus exactly one commit, touching only the 24 task `environment/Dockerfile`s,
which adds the layer that writes `/home/user/AGENTS.md` and symlinks
`/home/user/CLAUDE.md` to it — that layer *is* the informed arm. Checking out
`9dc4ac6ae9` alone gives the **control** arm: no `AGENTS.md` and no `CLAUDE.md`
exist anywhere in that tree, so it cannot rebuild the images these trials ran on.

## Layout of one trial directory

```
<task>__<trial-id>/
  config.json                 agent name and model_name, per trial
  result.json                 harbor's record (absent on the one unfinished trial)
  trial.log                   harbor's log, including anchor verdicts
  agent/trajectory.json       the agent's tool calls and output
  agent/claude-code.txt       the raw adapter transcript
  verifier/ctrf.json          the pytest report; ABSENT => ERRORED-INFRA
  verifier/reward.txt         the scored reward
  verifier/test-stdout.txt    pytest stdout, including assertion text
```

The presence of `verifier/ctrf.json` is the scored/ERRORED-INFRA discriminator
used throughout the write-up; a trial without it is excluded rather than
scored 0.

## Re-deriving the headline numbers

Directory count, trial count, and the scored denominator. Note the job also has
its own top-level `result.json`, so a bare `find -name result.json` returns 327;
glob the trial directories instead.

```sh
J=jobs/2026-08-14__21-17-36
ls -d $J/*__*/ | wc -l                  # 327 directories
ls    $J/*__*/result.json | wc -l       # 326 trials (the stub has none)
ls    $J/*__*/verifier/ctrf.json | wc -l  # 273 scored; the other 53 are ERRORED-INFRA
```

The 27 trials carrying `BOOTSTRAP_ANCHOR_VIOLATION` (28 codes; one trial,
`restore_interactive__932AiA5`, carries two) all have a `ctrf.json`, which is
why the write-up reports them against 273 rather than 326. The codes are written
by the anchor fixture into the pytest report, i.e. `verifier/ctrf.json` and
`verifier/test-stdout.txt` — **not** into `trial.log`, which contains none of
them and which an earlier version of this recipe grepped, returning 0:

```sh
grep -rl BOOTSTRAP_ANCHOR_VIOLATION $J/*__*/verifier/ctrf.json | wc -l   # 27

# 28 codes across those 27 trials, deduplicated within each trial:
for f in $J/*__*/verifier/ctrf.json; do
  grep -o 'ANCHOR-[A-Z-]*[A-Z]' "$f" | sort -u
done | sort | uniq -c
#   4 ANCHOR-CHANGE-ID-DIVERGENT
#  23 ANCHOR-CHANGE-ID-MISSING
#   1 ANCHOR-HANDOVER-OP-GONE
```

## Provenance and integrity

Copied byte-for-byte from the sweep container's job directory; no file was
edited, redacted or removed. Scanned for credential material before pushing —
`ANTHROPIC_API_KEY` appears only as the string value of Claude Code's
`apiKeySource` field, never with a key attached.

Summary and analysis: `results/2026-08-14-baseline-24.md` on
`claude/baseline-24-informed` (PR #42).
