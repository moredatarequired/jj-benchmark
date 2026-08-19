# 2026-08-19 arm G: a blind, well-written jj reference, forced, 24 tasks, haiku

Arm G fills arm D's slot in the 2026-08-16 six-arm design ([`results/2026-08-16-skill-ab.md`](2026-08-16-skill-ab.md), `main` @ `10be3545`) with one thing changed: the injected document. Arm D's reference was written by us with the failing tasks in view. Arm G's was written from the jj 0.44.0 binary, the v0.44.0 docs and the changelog alone, by an author who never saw the task suite, the fixtures, the verifiers, or any prior result. 24 tasks × 4 attempts = **96 trials**, `claude-haiku-4-5-20251001`, jj 0.44.0, harbor 0.20.0, task images built from `42273ba1ac`. Zero ERRORED-INFRA, 96/96 `verifier/ctrf.json`, 0 retries, 18 min 54 s wall, **$6.6841** harbor-recorded — haiku needs no rescale.

**Arm G scored 0.7292 against the control's 0.6563, and none of G − A, G − E or D − G clears 0.05.** The defensible statement is the null one: at n = 24 tasks this design cannot resolve an effect of the size a good blind document appears to produce. Three point estimates lean the expected way, which is weakly encouraging and is not evidence at the 0.05 level.

| arm | channel | content | mean | delivered / opened | anchor viol | cost |
|---|---|---|---:|---:|---:|---:|
| A | none | none (control) | 0.6563 | — | 10/96 | $9.7246 |
| B | elective `--skill` | decoy `jj-working-practices` | 0.6094 | 8/96 | 16/96 | $9.6908 |
| C | elective `--skill` | `schpet--toolbox--jj` | 0.6693 | 14/96 | 14/96 | $7.6871 |
| E | forced prompt | schpet `SKILL.md` | 0.6936 | 96/96 | 12/96 | $7.3343 |
| **G** | **forced prompt** | **blind reference, ours** | **0.7292** | **96/96** | **11/96** | **$6.6841** |
| F | elective `--skill` | informed reference, as a skill | 0.7557 | 63/96 | 9/96 | $6.6643 |
| D | forced prompt | informed reference | 0.8194 | 96/96 | 10/96 | $5.8428 |

Arms A–F are unchanged: the analysis script re-derives them in the same pass and **436 A–F cells were machine-compared against the pre-arm-G run with 0 mismatches** — per-arm means, arm intervals and DEFF, all 11 published contrasts, the permutation legs, the per-task table, the anchor and cost figures, and the channel/content block byte-identical. Adding arm G changed nothing about A–F, and **the published 42% channel / 58% content split does not move**: it is built from C, D and F only, and arm G is a term in neither its numerator nor its denominator.

## The three contrasts, and none of them clears 0.05

Paired by task, n = 24, t(23). The CI here is already the cluster-honest one — the contrast estimator pairs 24 task means and never treats the 96 trials as units, so there is no second, honest version to report.

| contrast | question | mean diff | t(23) | p | p (exact perm) | 95% CI | up/down/tied | Holm (family of 3) |
|---|---|---:|---:|---:|---:|---|---|---:|
| G − A | does a blind good document beat no document? | +0.0729 | +1.596 | 0.1241 | 0.1317 | [−0.0216, +0.1674] | 9/5/10 | 0.2482 |
| G − E | does it beat the best third-party skill, same channel? | +0.0356 | +0.882 | 0.3867 | 0.3988 | [−0.0478, +0.1190] | 9/5/10 | 0.3867 |
| D − G | what did knowing our failures add? | +0.0903 | +1.841 | 0.0786 | 0.0732 | [−0.0112, +0.1917] | 8/3/13 | 0.2358 |

Every one of those intervals contains zero, on every leg — uncorrected, exact permutation over all 2²⁴ sign vectors, and Holm. **G − A is not an effect; it is a positive point estimate with an interval that includes "the blind document made things slightly worse."** **G − E is nowhere near significance: the data do not distinguish our blind document from the third-party skill delivered the same way, so do not say arm G beat arm E.** **D − G is the closest and still does not clear 0.05, so the informed-content premium is suggestive and unproven.** Holm is conservative here because the contrasts share arms — but none of the uncorrected p-values was below 0.05 to begin with, so the correction changes no verdict.

Arm G's cluster-honest 95% interval is **[0.592, 0.867]** (DEFF 2.62; the trial-level [0.649, 0.810] must not be used). It overlaps all six other arms', A [0.510, 0.803] and D [0.708, 0.931] included. **The tidy ordering A < E < G < F < D is not a dose-response curve in document quality** — it is seven overlapping intervals, and arm G adds three more non-significant results rather than resolving anything. (G − A and D − G do sum to D − A = +0.1632 exactly. Bootstrapping a share from that identity gives a wider interval than the published split, with twice the mass outside [0, 1] and both components individually failing to clear 0.05, so no share is quoted from it here.)

## Authoring blindness, and the evidence for it

The author worked from the v0.44.0 release binary (`jj 0.44.0-af45d57de716…`), the v0.44.0 docs (`revsets.md`, `filesets.md`, `conflicts.md`, `working-copy.md`, `operation-log.md`, `bookmarks.md`, `glossary.md`, `git-compatibility.md`, `config.md`, `git-command-table.{md,yml}`, `cli-reference@.md.snap`) and `CHANGELOG.md`. They did not see `tasks/`, any Dockerfile or fixture, any verifier, any transcript, any prior arm's document, or any result.

Blindness is evidenced by what the document does **not** contain, and the omissions are exactly the ones an informed author could not afford:

- **`[template-aliases]` is absent.** The TOML config block defines `[aliases]`, `[revset-aliases]` and `[fileset-aliases]` and stops there; templating gets one line (`arms/armG-reference.md:259`), naming `templates.log` as a source of *defaults*. That section is precisely and only what `template_customize_log_output` needs. Arm D's document names `[template-aliases]` outright (`forced-reference.md:204`) and spends lines 197–200 on the rule that a per-commit template emits no line break of its own and must end `++ "\n"`.
- **`jj restore -i`/`--interactive` is absent**, although `jj squash -i` and `jj absorb -i` are both present — and `restore_interactive` is a task.
- **Divergent changes get nothing.** The word appears once in the whole document, at `arms/armG-reference.md:3`, inside a caution about mixing mutating Git commands; there is no account of what a divergent change is or how to resolve one, and `divergent_change` is a task.

Corroborating: section budgets track the upstream manual's shape rather than the suite's — Git interop, which no task tests beyond `git_fetch_remote`, gets the second-largest section, while workspaces (2 of 24 tasks) and config/aliases/templates together get 5.7% of the words. And every string that looked fixture-derived turned out to sit in the stated sources: `arms/armG-reference.md:253` is character-identical to `config.md:585`.

**Fixture-leak scan.** A 748-item corpus (24 task directory names and their tokens, every filename, absolute path, quoted string and `jj bookmark` argument in the 24 Dockerfiles, every quoted string and filename in the 24 `instruction.md`s, plus benchmark vocabulary) was matched against the draft: 115 items hit, and **two were fixed** — `src`/`src/…`, a real fixture directory in two tasks and a verbatim string in `fileset_rollback/instruction.md:1`, and the exact literal `"Your Name"`, present verbatim in three fixture images. Seven lines changed, all illustrative names, no jj command, flag, revset, fileset or semantic claim altered; word count unchanged. Everything else matched is one-word jj/VCS vocabulary any jj reference must contain. Exhaustively absent, before and after: all 54 fixture filenames, all 12 task-specific bookmark names, all 85 fixture commit descriptions, the entire payments/checkout fixture domain, all 17 benchmark words (verifier, grader, reward, anchor, floor, trial, sweep, arm, …), and `log_custom`. No grader-framing anywhere: every claim is stated as jj semantics.

**Adversarial fact-check against the binary.** Every command and flag was checked with `./jj <subcmd> --help` at v0.44.0 and the doubtful ones invoked in a throwaway repo. **7 fixes; 94 distinct claims confirmed** (71 binary-verified, 23 docs-only). The one outright error was a heading claiming that everything in its block "works on any revision (`-r`)" over a block containing `jj restore` and `jj absorb` — neither has `-r`; `jj restore -r @` errors with a hint to use `--from`, and `jj absorb -r @` fails to parse. That was the single error that would have made a reader type a command that fails. The other six were an experimental flag presented as stable (`jj op restore --what`), absorb's ancestors being *mutable* ancestors, tracked vs. tracking bookmarks on `jj git push`, a `--no-edit` removal scoped globally when it is only true of `describe`, an overstatement of what mixing Git commands costs, and a change-ID length the official glossary itself gets wrong relative to the shipped binary.

**Re-scan after the fact-check.** The leak scan ran on the pre-fact-check bytes, so the corpus was re-run against the final document: 128 hits, all one-word jj/VCS vocabulary; **0 of 54 fixture filenames, 0 of 17 benchmark words, 0 of 15 payments-domain terms**; the only fixture-bookmark hits are `main` and `feature`, the two most generic branch names in existence. The seven fact-check edits introduced no distinctive token — the one substantive change is the word "divergent" at line 3, noted above.

The document was then frozen and not edited again: **sha256 `6075fc63ded87a305f143fbd471ee18b2a6782845f204fb6add56657ebe61440`, 14,360 bytes, 2,147 words, 280 lines.**

## Comparability with arm D

Images were built from the pinned tree `42273ba1ac3f17cd6d3122c1442258b995498858`, the same pin arms A–F used. Arm G's resolved `config.json` matches arm D's archived `config.json` field-for-field on all ten scoring-relevant knobs — attempts 4, concurrency 8, setup-timeout multiplier 2.5, `max_retries` 3, the same three-exception retry set, docker environment, 2048 MB memory cap, `claude-code`, `claude-haiku-4-5-20251001`, dataset path `informed/tasks`. Three fields differ: `job_name`, the injected path (`arms/armG-reference.md` vs `arms/forced-reference.md`) — the one manipulated variable — and `jobs_dir`, absent from arm G because harbor omits defaults (`harbor/cli/jobs.py:1519`, `harbor/models/job/config.py:320`) while arm D's non-default absolute path was collapsed to `"jobs"` by the 2026-08-16 archive's path rewriting, an artifact of archiving rather than a run difference. **Only the document bytes differ.**

The recorded per-task `task.digest` is *not* comparable across builds — it hashes the task directory including the per-build, gitignored `tests/bootstrap_anchor.json` — so comparability rests on the git pin, not on the digest.

## Delivery is proven, 96/96, on two independent layers

**Layer 1, the lock digest:** every one of the 96 `lock.json` files carries exactly one `extra_instructions` entry, path `arms/armG-reference.md`, digest `sha256:6075fc63…1440`. Harbor content-digests the file into the lock (`harbor/models/job/lock.py:288-290`, `:374-382`), so this is immune to transcript elision. **96/96.**

**Layer 2, the transcript:** every one of the 96 `agent/trajectory.json` files has `steps[0].source == "user"` and `steps[0].message` ending in the document's exact 14,360 bytes, which is what harbor's `instruction.md` + `"\n\n"` + document join produces (`harbor/models/task/task.py:184-185`). **96/96.** Anything less than 96/96 on both would have been a failed manipulation, not a null result.

> **`agent/claude-code.txt` must not be used for this check.** It reads **0/96 even for a genuinely delivered, un-elided forced document** — measured here on a distinctive sentence from the document: 0/96 in `claude-code.txt` against 96/96 in `trajectory.json`. Harbor feeds the prompt on stdin (`claude_code.py:1512-1530`) and that file is only the `--output-format=stream-json` stream, which never echoes the prompt. The same probe returns 0/96 for arm D. `results/2026-08-16-skill-ab.md:147` records the symptom for arm E and attributes it to elision; elision is not the cause, and the delivery script on the archive branch refuses to read that file.

## Anchor violations: 11/96, and they hide inside the mean

**11 trials of 96, all `ANCHOR-CHANGE-ID-MISSING`, zero `ANCHOR-*-DIVERGENT`** (counted one code per trial from `verifier/ctrf.json`; `test-stdout.txt` agrees at 11). By task: `operation_recovery` 4/4, `abandon_commits` 2/4, `propagated_conflict` 2/4, `mistaken_squash_recovery` 1/4, `rebase_branch` 1/4, `split_commit_interactive` 1/4.

**A violation forces reward to exactly 0.0, so it is invisible in an average.** Of the 18 arm-G trials at reward 0.0, **11 are anchor violations and 7 are genuine zeros**. Report the split alongside the mean, never the mean alone. `trial.log` reads falsely clean and did again here: grepping it for the violation string returns 0 files against the true 11.

96/96 trials invoked `jj`. Strict passes (reward exactly 1.0) 62/96; reward histogram `0.0 × 18 · 0.25 × 4 · 0.5 × 6 · 0.667 × 6 · 1.0 × 62`. The arm mean re-derives to 0.729167 three ways — harbor's `stats.evals[*].metrics[0].mean`, the 96 `result.json` rewards, and the 96 `verifier/reward.txt` scalars — with 0 disagreements.

## `template_customize_log_output` in arm G is a real failure, not the grader artifact

The template-alias grader artifact is live and unfixed: `tests/test_final_state.py` hardcodes the bare keyword (`:56`) and looks it up as `template-aliases.log_custom` (`:93`) and as `jj log -T log_custom` (`:126`), so a correct *function*-alias solve scores 0. **It did not fire in arm G, and this cell carries 32% of D − G, so the distinction matters.** All four arm-G trial records were read end to end:

| trial | what the agent actually did |
|---|---|
| `2fwkSUE` | wrote into `[template-aliases]` **correctly**, but used `try(description.lines().first(), …)` and no trailing newline |
| `C7zcZMe` | wrote the alias under **`[aliases]`**, the command-alias section |
| `NicunXK` | wrote the alias under **`[aliases]`** |
| `QvwcDeF` | wrote the alias under **`[templates]`** |

Three of four fail with `Config error: Value not found for template-aliases.log_custom` **and** ``Failed to parse template: Keyword `log_custom` doesn't exist`` — the alias is in the wrong TOML section and genuinely does not work. None used the function-alias form the artifact mis-scores. **That is a real failure with a visible mechanism**: arm D's document names `[template-aliases]` and the no-implicit-newline rule explicitly (`forced-reference.md:204`, `:197-200`); arm G's document names neither. This is evidence *for* the informed-content story, not an artifact to be discounted from it — and it is still one task out of 24, and it does not turn p = 0.079 into significance.

`operation_recovery` is the genuinely inherited zero: 0.0000 in **all seven arms A–G**, contributing an exactly tied 0 to all three arm-G contrasts. `fileset_rollback` is passable without jj, which normally inflates a forced arm's contrast against the control; here it is a −0.188 cell for G − A, so it works against arm G.

## Limitations

**1. D − G is a confounded comparison, because arm G differs from arm D on two axes at once.** Not just what the author knew, but how the document is formatted: arm G has **17 fenced code blocks against arm D's 0** — 34 fence delimiter lines, 104 of its 280 lines (37%) inside a fence — and **2,147 words against D's 2,345** (14,360 vs 16,143 bytes). If heavy fencing helps a coding agent, which is plausible since fenced commands are directly copyable, then arm G's blind-authorship handicap is partly offset by a format advantage and D − G **understates** informed content; if dense fencing crowds out prose, D − G **overstates** it. The design cannot separate them. **A format-matched G′ — the same blind facts, prose-formatted like arm D — is the experiment that fixes this, and it is not the experiment we ran.**

**2. D − G's significance verdict flips on the deletion of a single task.** Leave-one-task-out over the 24 tasks moves its p from **0.032 to 0.152** (it falls to 0.032 without `edit_commit_message` and rises to 0.152 without `template_customize_log_output`, which alone carries 32% of the contrast). A contrast that fragile should not be reported as established in either direction. G − A and G − E are stable non-results by the same test: G − A ranges 0.069–0.244 and G − E 0.136–0.600, never reaching 0.05 under any single deletion. Their point estimates are concentrated too — `absorb_changes` alone is 35% of G − A, and `rebase_touched_commits` is 58% of G − E.

**3. n = 24 tasks is too few for an effect this size.** Arm G's point estimate sits a third of the way from A to D and is equally consistent with "blind quality buys about half of arm D's gain" and with "blind quality buys nothing and +0.073 is noise". The single-arm intervals are far too wide at 24 clusters to separate arms at all; the paired contrasts are the primary analysis and the single-arm intervals are context only.

**4. Arm D remains an upper bound, and arm G does not convert it into an unbiased estimate.** It bounds what content selected against a known failure set can do. Arm G is the unbiased attempt, and what it returns is that this benchmark cannot resolve the difference.

## Per task, all seven arms (n = 4 per cell)

| task | A | B | C | D | E | F | **G** | **G−A** | **D−G** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `abandon_commits` | 0.312 | 0.250 | 0.562 | 0.625 | 0.375 | 0.750 | **0.125** | −0.188 | +0.500 |
| `absorb_changes` | 0.333 | 0.500 | 0.750 | 1.000 | 1.000 | 1.000 | **1.000** | +0.667 | +0.000 |
| `bookmark_left_behind` | 1.000 | 0.750 | 1.000 | 1.000 | 1.000 | 1.000 | **1.000** | +0.000 | +0.000 |
| `divergent_change` | 1.000 | 1.000 | 0.917 | 1.000 | 1.000 | 0.917 | **1.000** | +0.000 | +0.000 |
| `duplicate_range` | 0.750 | 0.917 | 0.750 | 1.000 | 0.667 | 1.000 | **1.000** | +0.250 | +0.000 |
| `edit_commit_message` | 0.833 | 0.667 | 1.000 | 0.583 | 0.750 | 0.750 | **0.917** | +0.083 | −0.333 |
| `fileset_rollback` | 0.812 | 0.438 | 1.000 | 1.000 | 0.812 | 0.812 | **0.625** | −0.188 | +0.375 |
| `git_fetch_remote` | 1.000 | 1.000 | 0.625 | 1.000 | 1.000 | 0.875 | **1.000** | +0.000 | +0.000 |
| `immutable_stack` | 0.750 | 0.500 | 0.667 | 0.750 | 0.750 | 0.667 | **0.750** | +0.000 | +0.000 |
| `merge_bookmarks` | 1.000 | 1.000 | 1.000 | 1.000 | 0.750 | 1.000 | **1.000** | +0.000 | +0.000 |
| `mistaken_squash_recovery` | 0.000 | 0.000 | 0.000 | 0.583 | 0.250 | 0.500 | **0.500** | +0.500 | +0.083 |
| `operation_recovery` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | **0.000** | +0.000 | +0.000 |
| `propagated_conflict` | 0.750 | 0.500 | 0.250 | 0.250 | 0.250 | 0.500 | **0.500** | −0.250 | −0.250 |
| `rebase_branch` | 1.000 | 1.000 | 1.000 | 0.750 | 0.750 | 0.750 | **0.750** | −0.250 | +0.000 |
| `rebase_touched_commits` | 0.500 | 0.500 | 0.500 | 0.750 | 0.875 | 0.500 | **0.438** | −0.062 | +0.312 |
| `restore_interactive` | 0.583 | 0.333 | 0.667 | 0.750 | 0.583 | 0.833 | **0.833** | +0.250 | −0.083 |
| `split_commit_interactive` | 0.500 | 0.500 | 0.500 | 1.000 | 0.750 | 0.875 | **0.625** | +0.125 | +0.375 |
| `squash_range` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.950 | **1.000** | +0.000 | +0.000 |
| `template_customize_log_output` | 0.000 | 0.000 | 0.000 | 0.750 | 0.250 | 0.250 | **0.000** | +0.000 | +0.750 |
| `track_untracked_file` | 0.250 | 0.375 | 0.625 | 1.000 | 0.250 | 1.000 | **0.625** | +0.375 | +0.375 |
| `undo_mistaken_rebase` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | **1.000** | +0.000 | +0.000 |
| `unmerged_tips` | 0.625 | 0.562 | 0.500 | 0.875 | 0.750 | 0.625 | **0.812** | +0.188 | +0.062 |
| `workspace_add` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | **1.000** | +0.000 | +0.000 |
| `workspace_update_stale` | 0.750 | 0.833 | 0.750 | 1.000 | 0.833 | 0.583 | **1.000** | +0.250 | +0.000 |
| **arm mean** | **0.656** | **0.609** | **0.669** | **0.819** | **0.694** | **0.756** | **0.729** | **+0.073** | **+0.090** |

## Records

Per-trial records, the injected document, the delivery proof and the statistics script are on the orphan branch **`archive/2026-08-19-armG-trials` @ `9e097b73cec039a64a9d79eff5d1bfe0408b7276`** (1,353 files). Its README carries the resolved config, the pins, and the commands to reproduce every number above; the delivery proof reruns from that branch alone, because nothing in it is elided. Statistics: `armG_stats.py`, permutation 200,000 draws seed 20260819 plus exact enumeration of all 2²⁴ sign vectors, bootstrap 200,000 resamples seed 20260820; it reproduces the published A–F figures with the same code that produces arm G's. Arm D's document is on `archive/2026-08-16-skill-ab-trials` @ `b7746772c4` at `jobs/2026-08-16-skill-ab/arms/FINAL/forced-reference.md`, sha256 `a22214c6…908b`. No third-party skill text is vendored in either branch.

## Next

The unbiased-authoring question is answered only in the negative: a well-written blind jj reference, delivered to all 96 contexts, did not produce a detectable improvement over no document at all in this design, and did not separate from a third-party skill delivered the same way. Two things would change that, and they are separable. **A format-matched G′** — the same blind facts, prose-formatted like arm D, run in the same slot — removes the one confound that makes D − G uninterpretable, and costs one arm. **More tasks** is the other, and it is the binding constraint: at 24 clusters, effects of ±0.09 sit inside the noise, so every arm added to this design buys a point estimate and no verdict.
