# 2026-08-12 three-model baseline

> **Superseded as a description of the suite.** This measured 53 tasks. The suite has
> since been cut to 14 (ROADMAP.md "What's done" #6), and 39 of the tasks scored below no
> longer exist — including most of the ones that were 5/5 everywhere, which is why they
> were cut. Nothing here is a baseline for the current instrument: the per-model means are
> averages over a task set that is gone, and the per-task rows for deleted tasks are the
> evidence *for* the cut rather than a measurement to compare against. Kept unedited as
> the record of what the old suite did.

Top-level results for the first full sweep against the merged hardening stack.

**What was run.** All 53 tasks, 5 attempts each, against 3 models — **795 trials** — on
2026-08-12, at `main` @ `68525335e6` (the merged hardening stack, PRs #17–#21). The run was
split into five shards over an alphabetical ordering of the tasks, sized 11/11/11/10/10, each
shard run independently. Errored trials were re-run until the errored count reached zero:
**zero errored trials and zero exclusions** across the whole sweep. Every figure below is the
aggregator's output over the five committed shard records, not a hand-sum.

Strict pass means `reward >= 1.0`.

## Per model

| Model | Strict passes | Mean reward | Cost recorded | Cost corrected | Turns | Tool calls |
|---|---|---|---:|---:|---:|---:|
| `claude-haiku-4-5-20251001` | 240/265 (90.6%) | 0.947170 | $19.0383 | $19.0383 | 3356 | 3465 |
| `claude-sonnet-5` | 254/265 (95.8%) | 0.964780 | $27.1964 | **$18.1309** | 1523 | 1258 |
| `claude-opus-5` | 264/265 (99.6%) | 0.996226 | $38.0803 | $38.0803 | 1519 | 1335 |
| **Sweep** | **758/795 (95.3%)** | **0.969392** | $84.3150 | **$75.2495** | 6398 | 6058 |

Only sonnet's cost needed correcting; haiku's and opus's recorded costs reproduce from token
counts to the cent.

## Per shard

Strict passes, haiku / sonnet / opus:

| Shard | Tasks | Trials | haiku-4.5 | sonnet-5 | opus-5 |
|---|---:|---:|---|---|---|
| 1 | 11 | 165 | 53/55 | 53/55 | 55/55 |
| 2 | 11 | 165 | 47/55 | 52/55 | 54/55 |
| 3 | 11 | 165 | 51/55 | 55/55 | 55/55 |
| 4 | 10 | 150 | 43/50 | 50/50 | 50/50 |
| 5 | 10 | 150 | 46/50 | 44/50 | 50/50 |
| **Total** | **53** | **795** | **240/265** | **254/265** | **264/265** |

## The 17 discriminating tasks

These are every task where any model scored below 5/5. **The other 36 tasks are 15/15 —
5/5 on all three models.**

| Task | haiku-4.5 | sonnet-5 | opus-5 |
|---|---:|---:|---:|
| `abandon_commits` | 4 | 3 | 5 |
| `diff_revisions` | 4 | 5 | 5 |
| `diffedit_interactive` | 4 | 5 | 5 |
| `duplicate_commit` | 4 | 2 | 5 |
| `edit_commit_message` | 3 | 5 | 5 |
| `git_import` | 4 | 5 | 4 |
| `log_template_author` | 2 | 5 | 5 |
| `next_prev_navigation` | 4 | 5 | 5 |
| `rebase_branch` | 3 | 5 | 5 |
| `restore_interactive` | 4 | 5 | 5 |
| `restore_specific_revision` | 4 | 5 | 5 |
| `split_commit_interactive` | 4 | 5 | 5 |
| `squash_range` | 0 | 5 | 5 |
| `template_customize_log_output` | 3 | 1 | 5 |
| `template_formatting` | 3 | 5 | 5 |
| `track_untracked_file` | 5 | 4 | 5 |
| `workspace_update_stale` | 5 | 4 | 5 |

## Read this before quoting any number

**A 5/5 is a ceiling, not proof of determinism.** Five attempts can demonstrate instability but
never stability; read every 5/5 as "no failure observed in five draws" and nothing stronger.

**The reward scale is new, so nothing pre-hardening back-compares.** `68525335e6` moved task
instructions, verifiers, tests and the reward scale together, and this data cannot separate their
contributions. Strict-pass count is the only metric even loosely comparable to older numbers, and
even that comparison crosses changed tests. A mean reward on this scale has no historical
counterpart at all — never place one beside a historical pass count.

**Strict passes are an upper bound on genuine solves.** Five confirmed false passes sit inside
these counts, all haiku-4.5: two in shard 1 on `conflict_resolution`, two in shard 2, one in
shard 3 on `new_insert`. The rows ship exactly as the harness scored them, with the corrections
in prose in each shard's `CAVEATS.md`, so a correction can never be mistaken for a measurement.

**Those false-pass counts are floors, not totals.** They come from a change-id divergence
detector that is blind to roughly half the corpus — trials using custom `-T` templates print no
change ids at all and cannot be assessed either way. In one shard that was 83 of 165 trials.

**There are corrections in the other direction too.** Opus's single loss, on `git_import`, is a
literal-substring grader artifact: the import succeeded, but the operation log recorded
`args: jj -R <path> git import` while the test substring-matches `args: jj git import`, so any
global flag before the subcommand scores a correct solve at zero. Opus is honestly 265/265.
Shard 5's sonnet 44/50 is 46/50 corrected, two losses being the `jj config set` artifact below.
No corrected sweep-wide total is quoted here, because the record does not support one — the
headline numbers are neither a floor nor a ceiling, and the net effect is unknown.

**42 of the 53 verifiers cannot tell a solved repository from a wiped-and-rebuilt one.** Five
distinct reconstruction routes were observed live in this sweep, all scoring or nearly scoring
1.0, including a plain `jj squash` collapse that involves no destructive-looking command at all.
Only 4 tasks are guarded, 5 weakly; 3 are not applicable by design.

**pass@k is computed outside the harness.** harbor 0.20.0 voids its own pass@k for any reward
that is not exactly 0 or 1, and every fractional reward here is, so strict pass is computed
externally as `reward >= 1.0`.

**Fractional rewards are floor-corrected and will not match a naive test fraction.**
`squash_range`'s eight-of-nine-passing trials score **0.833333, not 0.8889**, because the floor is
3 of 9 and the credit is (8-3)/(9-3) = 5/6. Carry that arithmetic wherever a reward is printed
beside a test count, or a reader will report it as a bug. Across all 795 rows the 37 non-passes
are 16 at 0.0, 13 at 0.5, 3 at 0.666667 and 5 at 0.833333; `relaxed_checks` is empty on every row.

**The agent CLI version is not pinned.** The harness reinstalls it per trial, so it floats with
whatever is current at run time. It measured uniform at 2.1.228 across every shard that reported,
but that was luck rather than design, and nothing in the artifacts would have said so otherwise.

**The sonnet cost correction is a measurement, not a choice.** The agent CLI's local price table
carries sonnet at a stale $3/$15 against the real gateway $2/$10. The recorded-to-token-derived
ratio was re-derived per shard and comes out at exactly **1.5000** for sonnet on all five shards
independently — and on all 265 sonnet rows individually — against 1.0000 for haiku and opus. The
2/3 rescale is already applied in the corrected column; do not apply it twice.

## What's worth acting on

**The `jj config set` penalty biases any skill A/B.** On `template_customize_log_output` the
grader penalises using jj's own `jj config set` over hand-editing the config file, for identical
correct behaviour. `config set` parses its value as a TOML fragment, which forces the agent into a
quoted string whose `\n` is then decoded at parse time — so the file holds a real newline and the
test's search for the literal two-character `\n` cannot match. Same intent scores 1.0 by hand-edit
and 0.5 through the documented interface. This is the sharpest item here: it would bias any future
skill A/B in whichever direction the skill happens to teach.

**Bootstrap replay is not the cheap fabrication check it looks like.** Re-running each task's
shipped `bootstrap/test_initial_state.py` after the agent is useful on about 9 tasks, safe on 19,
and *actively wrong on 32* — on those the bootstrap assertion is necessarily false after a correct
solve. `root_commit` and `abandon_commits` are direct logical negations of their own final-state
tests. Wiring it into `test.sh` would break 32 tasks to gain nine weak guards.

**The real follow-up is a verifier anchor.** Per-task invariants — change-id preservation,
operation-log ancestry, commit ids captured at bootstrap time and re-checked at verify — anchored
**outside the artifact under test**. Four tasks already assert id preservation and all four source
their reference ids from the repository they are grading, so a fabricated repository agrees with
itself. Written as a floored guard it passes on an untouched repository by construction, so it can
land without invalidating this baseline.

## Where the full record lives

Nothing below is in this PR; it is all reachable on branches.

- The 795 per-trial rows, the per-task rollups, and `scripts/aggregate_sweep.py` with its tests
  are on **`claude/hearth-thread-5ulj25-full-record`**.
- The per-shard originals, with each shard's `CAVEATS.md`, are on the shard branches at
  `a1eec50f` (shard 1), `2ef39ccb80` + `38deb19348` (shard 2), `695b568f` (shard 3),
  `70d7f4a` / `1d92842` (shard 4) and `643aa9fa7c` (shard 5).
