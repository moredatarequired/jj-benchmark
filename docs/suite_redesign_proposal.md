# Suite redesign: cut to 24 tasks, ten of them new

> **STATUS: both halves of this proposal have been executed. `tasks/` now holds 24
> directories, not 53.** Hugh approved the shipping-14 list in §5 and additionally
> dropped the seven-task smoke tier this document parks there — "I don't know that we
> really need to keep a smoke tier" — so all 39 non-shipping tasks were deleted in one
> commit: the 26 in §3's cut table, the 6 in its merge table, and the 7 §5 demotes. The
> "build 10 new" half is now done too: ten tasks were authored on top of the 14, so the
> target of 24 has been reached.
>
> Everything below is left as it was written, which means it reads as a proposal about a
> 53-task suite and cites `tasks/<name>/...` paths for tasks that no longer exist. Those
> citations still resolve at commit `73854f0b`, the last commit before the cut — the two
> the document itself flags as reference text for future work are
> `git show 73854f0b:tasks/git_import/tests/test_final_state.py` (the R3 docstring, §3's
> merge table) and `git show 73854f0b:tasks/concurrent_operations/tests/test_final_state.py`
> (the `change_id(X)`-on-a-divergent-change idiom, §4.0.2 #2, and the structural half N8
> is a re-scope of).
>
> Two things the cut did *not* do, both deliberately left for the new-task work and
> recorded here so they are not lost: `workspace_forget`'s add → list → forget lifecycle
> was not folded into `workspace_add` (it needs a second workspace in the fixture and a
> rewritten prompt — a new task, not an assertion), and `log_template_author`'s
> author-templating surface (`author.name()` / `author.email()`) was not folded into
> `template_customize_log_output` (its instruction specifies a template that has no
> author field in it; changing that changes the task). The suite now has **no bookmark
> task at all** — `bookmark_create_and_move`, `bookmark_rename`, `bookmark_push` and
> `bookmark_delete` all went — so `jj bookmark` survives only incidentally, inside
> `git_fetch_remote`'s fixture and `abandon_commits`' assertions.

**Recommendation.** Cut 24 of the 53 tasks outright, fold 7 into survivors, and keep 22.
Of those 22, only 14 belong in the shipping suite; the other 8 are structurally sound but
produced no separation across three model tiers. Build 10 new tasks against capabilities
nothing currently touches. **Target: 24 tasks — 14 kept, 10 new.**

*This target survived reconciliation against the binary-verified capability survey (§0), with
three amendments to how it is reached rather than to the number: author ~16 new tasks and ship the
10 that measurably discriminate; require at least six of the ten to compose five or more dependent
operations; and treat five of the 14 kept as provisional. §5.1 has the argument.*

*One arithmetic correction, from the retarget measurement: the cut/fold/keep split is now
**26 cut, 6 folded, 21 kept** (26 + 6 + 21 = 53), because `git_import` and `git_export` both move
to the cut list — `git_import` out of the fold column and `git_export` out of the keep column
(§3 — both are documented no-ops in a colocated repo, and every task image is colocated). **The
shipping target of 24 is unchanged**: `git_export` was one of the eight structurally-sound-but-
saturated keeps that §5 already demotes out of the shipping 14, so cutting it costs the target
nothing. The eight become seven.*

The case for cutting that hard is not that the tasks are badly written, though many are. It
is that the suite has almost stopped measuring anything:

- **36 of 53 tasks were 5/5 on all three models** in the 795-trial baseline
  (`results/2026-08-12-3model-baseline`, per `discrimination-table`). Opus lost one trial in
  265, and that loss is a grader artifact — the agent typed `jj -R <path> git import` and a
  substring check on argv broke (now fixed; see `tasks/git_import/tests/test_final_state.py:1-11`).
- **The sharpest separator in that baseline no longer separates.** `squash_range` was haiku
  0/5 vs sonnet 5/5 vs opus 5/5, entirely on `test_fixes_were_combined_in_a_single_operation`.
  That test was deleted on this branch and the prompt clause with it —
  `tasks/squash_range/tests/vacuity_floor.json` now reads 8 tests / 3 floor / 5 scored, and no
  op-log test asserts operation count. *Inferred* (from the trace in `overspec-audit` §6.1, not
  re-measured): the two-sequential-squash route that scored 0.833 now scores 1.0.
- **Two tasks are solvable without jj at all** (§2).

So the live count of tasks that separated the three models is 16, and one of the two
partial-credit tasks in that set (`template_customize_log_output`, 9/15) separates partly on a
grader artifact of its own. That is the instrument.

*Verification note.* Every `file:line` below I opened myself at `3060c420`. Tests/floor/scored
and the anchoring column were recomputed mechanically across all 58 task directories and match
the audit's table row for row. Anything marked *inferred* I did not run.

*Corrected against the binary-verified survey — a provenance caveat on the baseline.* The survey's
review pass records that the 795 trials were run at `68525335e6`, which **predates the 2026-08-12
hardening**, so they describe the same 53 task *names* under different graders and are not
comparable forward. Every baseline number in this document is therefore evidence about which tasks
*were* saturated, not a prediction of what a re-run scores. The `squash_range` bullet above is the
worked example of that gap, not the exception to it.

*Version provenance — read this before relying on any behavioural claim below.* **The suite is
being retargeted from jj 0.38.0 to jj 0.44.0.** That is decided, not pending; §5 prerequisite 4
records the decision and what it was measured to cost. Consequences for how to read this document:

- Every jj behaviour asserted below is either **0.44-verified** — re-run on
  `jj 0.44.0-af45d57de716` by the retargeted survey (§0) or by our own 58-task re-pin measurement —
  or **0.38-only**, measured on the old pin and not re-run. 0.38-only claims are hypotheses about
  0.44, not facts about it. Each is marked ***[0.38-only — re-check]*** where it appears, and R7
  forbids a new task depending on one until the probe has been re-run against the 0.44 binary.
- Every *number* — reward, delta, failure rate, noise floor, the 795-trial baseline — was measured
  on 0.38 and is not comparable forward. Hugh has ruled that this is not a cost worth weighing:
  *"in some sense we haven't yet measured even once the thing we actually care about."* Read the
  numbers as a description of the current suite's shape, never as a baseline.

---

## 0. Companion document: the capability survey

This proposal has a companion that it was **not** written against, and which has since been
reconciled into it: **`docs/task_redesign_survey.md`**, commit **`3ad91698`** on branch
**`claude/hearth-thread-zk1kgr`** (not on this branch — read it with
`git fetch origin claude/hearth-thread-zk1kgr` and then
`git show 3ad91698:docs/task_redesign_survey.md`). Where the two documents once disagreed, this
one has been corrected; every such correction is marked in place as *corrected against the
binary-verified survey*.

*Citation updated — twice now, and the second update matters more than the first.* Earlier
revisions cited **`0a8aab1b`** (pre-review), then **`dac8118b`** (post-adversarial-review, which
fixed 25 defects: four `[verified]` labels whose cited evidence did not contain the claim, eight
unlabelled behavioural claims, and eight defects in the 39 themes themselves — one grading HOW, one
pinning `@` positionally against the survey's own rules, one describing a conflict-child state 0.38
cannot produce, and one asking for the commit that *introduced* a line while grading
`jj file annotate`'s *last-changed* answer). **`3ad91698` is that document retargeted to jj 0.44.0**
— every behavioural claim re-run against `jj 0.44.0-af45d57de716`, twelve new themes authored
natively on it, and a new §9 cataloguing the version delta. Cite `3ad91698`. Three claims this
document had taken from the pre-review text remain corrected below: §4.0.2 #1 (the divergence
offsets), the N3 row in §4.2 (theme 3.6's actual solve) and prerequisite 4 in §5 (the 0.42/0.43
removals) — and prerequisite 4 has now moved from "unverified removal list" to "executed, and the
pin question is closed".

**What it contains.** A 3,157-line research survey of what jj is for, written against the real
**`jj 0.44.0-af45d57de716`** binary rather than against documentation — the build the suite is
being re-pinned to. The old pin survives in it only as the baseline it says what moved *from*.
Five parts matter to this proposal:

1. **A sixteen-area capability map** (its §2), each area labelled with the mental-model failure a
   git-fluent agent makes and whether the result is observable in end state.
2. **A "silent-success catalogue"** (its §3) — the cases where jj exits 0 having done nothing.
   This is the single most useful thing in it for task design; see §4.0 below.
3. **51 candidate task themes across five tiers** (its §5) — **6 / 11 / 15 / 10 / 9** across Tiers
   1–5 — each with a fixture, a one-line user-register prompt, an end state, and how it is graded
   from end state alone. **These 51 are the menu the "build 10 new" recommendation in §5 should be
   drawn from.** Sixteen of them carry an **execution warrant** (fixture stood up on the 0.44
   binary and the claimed solve run to the claimed end state); 35 are reasoned-only. The N1–N10
   sketches in §4 of this document predate the survey; they are retained as a statement of what the
   ten must *cover*, not as the shortlist, and where a survey theme covers the same ground with a
   verified fixture recipe, the survey's version wins. Theme numbering is stable across the
   retarget — every `N.M` this document cites still points at the same theme.
4. **A corrections appendix** (its §10, renumbered), now rewritten as a **0.44** correction list:
   claims from jj's own documentation and from two tutorials refuted or drifted against the binary,
   tagged `[same on 0.44]` / `[0.38-era]` / `[SUPERSEDED]`, plus nine corrections that did not exist
   on 0.38 at all. Several would poison a fixture or a verifier; the load-bearing ones are
   reproduced in §4.0 below.
5. **New with the retarget: its §9, the seventeen breaking changes B1–B17** between 0.38 and 0.44,
   split into *what changes what a fixture produces* and *what changes what a verifier sees*, every
   one A/B'd on both binaries in the same repo. This is the section to read before authoring
   anything. The three that fail *quietly* are B6 (the empty-revset widening, §4.0.1 below), B9
   (removed config keys accepted in silence) and B17 (template runtime errors rendered inline at
   exit 0, §4.0.2 #10 below).

**How to read its confidence — the labels changed meaning at the retarget, and that is the single
most important thing to know about `3ad91698`.** `[verified]` **now means "executed on 0.44.0 and
the output quoted"**, and a 0.38 verdict is never silently carried forward as a 0.44 one. The
labels are: `[verified]` and `[verified — this retarget]` (0.44, output quoted — safe to build a
grader on); **`[verified-on-0.38-only]`** (measured on the old pin and *not* re-run — a hypothesis
about 0.44, and every one says what probe would settle it); `[docs-0.38]` (read from 0.38 docs,
never executed, and now doubly stale); `[unverified]`. The 0.38-era sub-labels
(`[verified, recon §1.4]`, `[verified — this survey]`, `[verified — this review]`) survive only
*inside* `[verified-on-0.38-only]` citations, as provenance for which 0.38 pass produced the
number. **Execution warrants are a separate axis from fact labels**: a theme built entirely out of
`[verified]` facts still has no warrant until someone stands its fixture up — which is R7, and
which the survey re-earned at the new pin (of the sixteen themes executed, six needed correction
and three would have shipped broken). The survey is now self-certified at 0.44 but still not
tree-certified, and §3 of this document's adjudication records the two places where its own
tree-level claims do not survive contact with our task files.

---

## 1. The design rules

Seven rules. Each is stated as a rule, then the measurement that produced it.

### R1 — The task must have a mental-model failure in it, not a flag to recall

*Why.* Two-thirds of the suite is at ceiling. The tasks that still move are the ones where a
git-shaped instinct produces a confidently wrong answer: sonnet's single `track_untracked_file`
zero was `jj describe` instead of `jj commit` after correctly working out `--include-ignored` on
its own (`failure-modes` §2, quoting the shard write-up) — right model of the file, wrong model
of what finalises a change. That is the shape to build.

The counter-example is instructive. `squash_range`'s haiku failures were pure discoverability:
three of five tried the correct single-operation route, hit jj's arity rule on `-r`, and fell
back to two squashes; none read `jj squash --help` (`failure-modes` §1). That produced a sharp
number but it is flag recall, and it is exactly the assertion that has now been removed.

Corollary on prompts: a prompt that names the technique is testing reading comprehension.
`tasks/squash_range/instruction.md` opens "Revsets let one operation name a whole range of source
commits rather than one at a time" — that sentence is the task.
`tasks/template_customize_log_output/instruction.md` hands over the template expression
(`change_id.short()`, `description.first_line()`, `"\n"`) verbatim.

### R2 — Grade repository structure. Never English, never position

*Why.* Every task that grades prose or position has a demonstrated hole.

| Task | What it actually asserts |
|---|---|
| `workspace_root` | No jj call anywhere in the file; `EXPECTED_ROOT` is a literal at `tests/test_final_state.py:4` |
| `diff_revisions` | Imports `os` only (`tests/test_final_state.py:1`); greps a text file |
| `working_copy_as_commit` | `test_parent_commit_contains_hello` asserts `returncode == 0` (`tests/test_final_state.py:14-21`) |
| `concurrent_operations` | Requires jj's literal English `"reconcile divergent operations"` (`tests/test_final_state.py:152-155`) |
| `git_integration` | `git show-ref --verify refs/heads/my-feature` inside `remote.git` (`tests/test_final_state.py:29-35`) — `git branch my-feature` satisfies it |
| `git_remote_add` | `"origin" not in stdout` of `jj git remote list` (`tests/test_final_state.py:27`) |
| `diffedit_interactive` | Greps `jj show` stdout for `def foo():` / `def bar():` (`tests/test_final_state.py:51-54`) |

*Corrected against a container measurement — the `workspace_update_stale` row that stood here is
withdrawn.* A prior revision of this document added that task to the table on the strength of
`test_no_stale_error`'s stderr grep and called `test_commit_message`'s description check a second
English dependency. Both claims were overstated, and the task has now been measured in a real
container built from its own `environment/Dockerfile` on the pinned jj 0.38.0.

- `vacuity_floor.json` does read 3 tests / 0 floor, so all three tests are scored, and
  `test_final_state.py:89` does read jj's stderr for `stale`. But `:88` already asserts that
  `jj st` exited 0, and on 0.38 a stale working copy makes `jj st` exit **1**. The prose read
  therefore sits behind the exit code: it cannot let a wrong solve through, and its only reachable
  failure mode is a **false negative** — some future jj printing "stale" on an exit-0 `jj st`
  (an advisory about a *sibling* workspace, say) would fail a correct answer. The recommendation is
  to **delete `:89` and keep the exit-code assertion**. That is verifier hygiene, not the repair of
  a hole, and it does not make the task suspect.
- `test_final_state.py:117` (`"Activate config" in result.stdout` out of `-T description`) is **not**
  an English-grading dependency and should not have been listed as one. `-T description` is a
  template field rather than prose, and `Activate config` is text the *instruction mandates the
  agent write* (`instruction.md:4`, "the exact description"). It is a data check on agent-authored
  content. The only tightening available is exact-match instead of substring.
- Measured on the untouched image: `bootstrap/test_initial_state.py` passes 5/5; `tests/test.sh`
  scores the untouched image **0** (all three scored tests fail) and a genuine
  `update-stale` → edit → `jj commit` solve **1**.

The three `assert_descends_from_the_handover` calls are properly anchored. The task is sound on all
four axes and keeps its place in the shipping 14; see §5. ***[0.38-only — re-check]*** for the
container measurements in this block: they were taken on a 0.38 image and this task's bootstrap has
not been re-run on 0.44. Its **vacuity floor** was, along with the other 57, and did not move — so
the scored/floored split is 0.44-confirmed even though the solve and the staleness route are not.

Position is the same failure in a different costume, and the suite has already paid for it three
times, each with the measurement recorded in the verifier's own docstring:

- `restore_interactive` relaxed `@ == handover` to `({handover}) & ::@`
  (`tests/test_final_state.py:199-201`) — an agent running `jj new` at any point lost two of six
  scored tests.
- `track_untracked_file` replaced the position `@-` with the anchored change
  (`tests/test_final_state.py:6-30`) — `jj describe` instead of `jj commit` had been scoring a
  correct solve 0.
- `split_commit_interactive` deleted its `@`-position test (`tests/test_final_state.py:9-13`) —
  `jj edit @-` + `jj split -i`, the route the task is named for, had been scoring 0.5.

Ten tasks still carry an incidental `@` pin that has not had that treatment.

*Counting note, not a correction.* The survey reports "12 verifiers on `main` still resolve a
graded commit through `@-`". That is not this number and neither is wrong: the survey counts
verifier files containing the token `@-`; this document counts **tasks whose scored tests** turn
on `@`-position after the three de-positionalisations above. A file can contain `@-` only inside a
fallback constant or a floored test. Do not reconcile them into one figure.

### R3 — Grade WHAT, not HOW

*Why.* Hugh's rule, and the suite is already converging on it. `squash_range` dropped its
single-operation requirement from prompt and verifier together on this branch. Two route-graded
scored tests remain:

- `next_prev_navigation::test_route_was_walked_one_step_at_a_time`
  (`tests/test_final_state.py:229-256`) requires three *distinct operations* leaving `@` at three
  *specified positions* in a *specified order* — 1 of its 2 scored tests.
- `log_template_author::test_script_contains_a_jj_log_command` regex-matches
  `\bjj\b[^\n]*\blog\b` against the script's source text (`tests/test_final_state.py:51,136`). A
  correct solution using `jj show -T` fails.

The line to hold: an **anti-fabrication** check is not a method check.
`squash_range::test_the_operation_that_removed_the_fixes_is_what_moved_the_content` only fires on
hand-edit-then-abandon and cannot fail an honest solve of any shape. Those stay, and stay
unannounced.

### R4 — The plausible wrong solve must be caught by name

*Why.* A task earns its place by having one specific wrong answer a competent git user would
produce, and one test that fails exactly that. The good verifiers all have one, and each records
the cheat it was written against:

| Task | The wrong solve it catches |
|---|---|
| `restore_interactive` | Patching the file back on top instead of into the commit that dropped it |
| `status_ignored` | Never having tracked the file — requires `::@ & files(root-file:"build.log")` to hold ≥2 commits (`tests/test_final_state.py:181-182`) |
| `git_fetch_remote` | `git branch feature main` in the remote — explicit `pushed != main` guard (`tests/test_final_state.py:109-111`) |
| `workspace_add` | `jj git init` at the right path — the project's anchored change must resolve from inside (`tests/test_final_state.py:82`) |
| `show_commit` | A hand-written patch — the output must carry the anchored commit's own id (`tests/test_final_state.py:119,134`) |
| `absorb_changes` | A wholesale squash — `{target}..@ & files(root-file:"<path>")` must be empty (`tests/test_final_state.py:167-170`) |
| `new_insert` | A fabricated commit — the graded commit is found as `({A}..{B}) ~ {B}` (`tests/test_final_state.py:93`) |

And the counter-example: `resolve_tool` claims to test `jj resolve --tool :ours/:theirs`, but its
verifier compares file bytes at the anchored merge and reads the `conflict` keyword
(`tests/test_final_state.py:75-108`). Hand-editing both files passes identically. There is no
wrong solve it catches that `resolve_conflict_marker` does not.

### R5 — A no-agent run scores 0, and the floor is measured, not assumed

*Why.* The harness already enforces this: `tests/test.sh` computes credit as
`(passed tests not in the floor) / (tests not in the floor)` (`tasks/*/tests/test.sh:50`), the
floor is measured against the untouched image, and `tasks/*/tests/conftest.py:55-63` runs the
bootstrap anchor as a session-scoped autouse fixture so a rebuilt repository errors every test
into an empty numerator.

The design consequence is the part that gets missed: **a floored assertion earns nothing and can
still cost a full mark**, because any pytest failure caps credit at `(scored-1)/scored`. So
floored tests must be deleted or rewritten to be about state the agent changed. Two tasks are
hollow for exactly this reason:

- `squash_commits`: its only content check, `test_file_contents`, is floored
  (`tests/vacuity_floor.json`). Its single scored test never verifies that the squashed content
  merged.
- `history_rewriting`: its descendants check, `test_jj_log`, is floored. Nothing scored verifies
  auto-rebase at all.

### R6 — More than one scored test

*Why.* With one scored test a task is pass/fail, and a single grader artifact zeroes it. Ten
tasks are in that state. Partial credit is also what makes failures legible: haiku's uniform
0.833 across five `squash_range` trials identified the failing assertion uniquely and told us it
was a near-miss, not a collapse. The sweep's 37 non-passes were 16 zeros and 21 partials; without
the partials, 21 of them would have been indistinguishable from a refusal.

### R7 — Stand the fixture up on the real binary and solve it *before* writing the verifier

*Hugh's rule, carried into this proposal.* For every new task: build the fixture, run at least one
genuine solve against the real pinned binary — **which is now `jj 0.44.0`, not 0.38** (§5,
prerequisite 4); a solve run on the old binary is not evidence about the new one — record what the
repository actually looks like
afterwards, and write the verifier against **that** observed end state. Never the other way round —
a verifier drafted from the design sketch and a fixture built to satisfy it afterwards is the
inverted order this rule exists to forbid.

*Why.* A verifier written against an *imagined* end state encodes the imagination. It does not
grade the task; it grades the author's mental model of the task, which means it passes that model
and **fails correct solves that the model did not anticipate**. This is not a hypothetical: it is
what the adversarial review of the survey found when it stopped desk-checking and started
executing. Four of the 39 candidate themes on the menu at that time were actually run, and one
failed outright:

- Theme 3.6 named **`jj op restore <pre-mistake op>`** as the solve for recovering from a
  self-inflicted mistake. Measured on a `base → A → B` stack that was squashed and then built on
  twice, that route **deletes both later commits** — precisely the failure the theme attributed to
  `jj undo` and wrote itself to avoid. Only **`jj op revert <squash-op>`** reaches the stated end
  state: `B` restored with its original change id *and* both later commits kept.
- That correct route leaves a **divergent change**, and its offsets are **`X/0` and `X/4`**, not
  `/0` and `/1`. A verifier hardcoding the latter — as a desk-written one naturally would, since
  `/0` and `/1` is what every divergence example in the survey showed — breaks on the correct
  solve. `X/N` indexes **every** commit that has ever carried the change id, hidden ones included,
  newest first; the hint prints only the visible members. §4.0.2 #1 has the rule.
- Six of the eight theme defects the review found were desk-checkable from the text. **That one was
  reachable only by running it.** No amount of re-reading produces it, because the whole error is a
  gap between what the author believed the binary does and what it does.

*The retarget re-earned this rule at the new pin, at a higher rate.* Sixteen of the survey's 51
themes have now been stood up on the 0.44 binary and their claimed solves run: **six needed
correction and three would have shipped broken.** Two independent lessons come with that number.
First, the count of desk-checks does not help — the survey's capability map had been fact-checked
against a binary *twice* before its themes were still only *reasoned* from it, and a twice-verified
input does not make a derived claim verified. Second, the 0.44 changelog was **wrong or misleading
three times** and the mechanical CLI diff twice during the retarget; each was caught only by
executing the claim. Grade claims one at a time, and never grade the reporter.

**A green pre-sweep pass cannot catch this**, and it fails for exactly the structural reason a
missing `anchor_exemptions.json` is not caught (§5, prerequisite 3): the pre-sweep runs the
verifier against the *untouched* image, and the untouched image never does the work. Only a correct
solve walks the path where the imagined and the real end state diverge. A task can therefore be
green on the floor measurement, green on the no-agent run, internally consistent on every desk
check — and still fail every competent agent that solves it correctly.

The rule is cheap relative to what it prevents. One solve per task, executed once at authoring
time, is the only evidence that the thing being graded exists.

---

## 2. What the current 53 are worth

Four axes, as defined in the audit. **Struct**: every scored test's decisive assertion is
repository state read through jj or git plumbing. **Anch**: graded commits are resolved through
`change_id_or_fallback` / `working_copy_or_fallback`, so an additive fabrication cannot be graded.
**Neut**: no scored test requires a command spelling, an operation count, or a position for `@`.
**NonVac**: more than one scored test.

| Axis | Pass | Fail |
|---|---:|---:|
| Struct | 41 | 12 |
| Anch | 40 | 13 (5 of them n/a — the agent creates the repo) |
| Neut | 36 | 17 |
| NonVac | 43 | 10 |

The Anch and NonVac columns I recomputed mechanically for all 53. Neut = 17, not the 18 the audit
states in prose — its own three sub-lists union to 17, and the discrepancy is arithmetic in the
audit, not a disagreement about any task.

**Failing two or more axes — 16 tasks.**

| Task | Axes | The load-bearing defect |
|---|---|---|
| `bookmark_delete` | S, A, V | One stdout substring, `"feature-x" not in jj bookmark list` (`:7-15`). Nothing ties it to this repository |
| `log_template_author` | S, A, N | Scores the script's *spelling* alongside a genuinely good behavioural probe (`:51,136`) |
| `template_formatting` | S, A, N | Three regexes over `jj log --no-graph` lines (`:26-29`); `lines[0]` must be `Second commit`, so an empty commit on top fails it |
| `working_copy_as_commit` | S, A, N | `test_parent_commit_contains_hello` verifies nothing (`:14-21`) |
| `concurrent_operations` | S, N | Requires jj's literal English (`:152-155`) |
| `describe_commit` | N, V | One test; `@` must still *be* the anchored working copy (`:59`) |
| `diff_revisions` | S, A | Zero jj calls (`:1-21`) |
| `diffedit_interactive` | S, V | One scored test, a grep of `jj show` (`:51-54`) |
| `git_integration` | S, A | Four existence checks; `git branch` in `remote.git` passes the push test (`:29-35`) |
| `git_remote_add` | S, A | `"origin" not in stdout` (`:27`) |
| `restore_specific_revision` | N, V | One scored test; strict subset of `restore_file_from_parent` |
| `revset_querying_bob` | S, A | Five tests, all stdout substrings or file reads (`:6-43`); the revset is only checked by "the file has 2 ids and both are Bob's" |
| `root_commit` | A, N | Unanchored; a fabricated `root()`-child repo passes (`:36`) |
| `stacking_changes` | N, V | One scored test; pins `@`/`@-` to the anchored tip (`:123`) |
| `workspace_forget` | S, A | Stdout substring + `os.path.exists` (`:15-20`) |
| `workspace_root` | S, A | The answer is printed in its own prompt |

### The two that need no jj at all

Both verified against the files, not taken from the audit.

**`workspace_root`.** `tasks/workspace_root/tests/test_final_state.py` imports `os` and nothing
else. `EXPECTED_ROOT = "/home/user/repo"` is a literal on line 4; the two tests check that
`/home/user/root_path.txt` exists and that its stripped content equals that literal (`:7`, `:13`).
`tasks/workspace_root/instruction.md:11` reads ``- Project path: `/home/user/repo` ``. So
`echo /home/user/repo > /home/user/root_path.txt` scores 1.0, and the repository need not exist.

**`working_copy_as_commit`.** `test_parent_commit_contains_hello`
(`tasks/working_copy_as_commit/tests/test_final_state.py:14-21`) runs `jj log -r @-` and asserts
only `result.returncode == 0`. It never checks that `hello.txt` is in `@-`, which is the entire
stated requirement (`instruction.md`: "The file `hello.txt` must be committed in the parent of the
current working copy"). Of its other three tests, one is `os.path.isdir(".jj")`, one reads a file
off disk, and `test_working_copy_is_empty` (`:23-31`) matches jj's English
`"The working copy has no changes."` — so an empty `jj git init` plus one file and one `jj new`
scores 4/4 with no understanding of anything.

---

## 3. Keep / merge / cut

All 53 base tasks. The five `*_terse` arms carry byte-identical verifiers to their base arms
(confirmed by `md5sum`) and follow whatever happens to those.

*Counting note, not a disagreement.* This document says **53** and the survey says **58** in
places; both are right and neither should be reconciled away. 53 is the number of base tasks; 58 is
the number of **task directories**, i.e. 53 plus the five `*_terse` arms. Anything mechanical —
the lint, the anchors, the vacuity floors, the jj pin in `environment/Dockerfile` — counts 58,
because each arm ships its own directory. Anything about task *design* counts 53. A cut takes the
arm with its base: `check_variant_identity()` requires a variant's `environment/Dockerfile` to be
byte-identical to its base's, so an orphaned arm is a lint failure, not a leftover.

### Keep — 21 *(was 22; `git_export` moved to the cut list — see the correction after the cut table)*

Sound on all four axes, or sound once the mechanical `@`-relaxation is applied. §5 then applies a
second filter.

| Task | Why it survives |
|---|---|
| `restore_interactive` | Strongest verifier in the suite; 6 scored tests on the target's tree, its own diff paths, its parent, its descendant, and disk |
| `squash_range` | 5 scored; anchored; op-log replay as anti-fabrication |
| `absorb_changes` | Per-file routing into the ancestor that last touched each file, plus the no-stragglers check. Nothing else tests per-hunk placement |
| `split_commit_interactive` | Position-free; agnostic about which half keeps the change id |
| `rebase_branch` | Rebase + conflict; asserts the stack is exactly the two anchored changes, linear, planted on anchored `main` |
| `status_ignored` | The only untrack verifier that distinguishes untracking from never-tracking |
| `track_untracked_file` | Byte-compares `.gitignore` (`:63,128`), catching the `!app.log` cheat a substring check accepted |
| `new_insert` | Grades a commit that has no anchored id of its own, correctly, by position between two that do |
| `new_commit` | `assert_is_the_bootstrap_commit("@--")` (`:78,106`); a stack fabricated from `root()` fails |
| `abandon_commits` | 4 scored, anchored; needs the `@` pin at `:186-190` relaxed |
| `edit_commit_message` | 3 scored; the parent claim at `:80-96` is anchored and correct; the `@` pin is incidental |
| `revert_file` | Three files, two source revisions, one left alone, plus a description — the strongest plain-restore fixture |
| `bookmark_create_and_move` | Ancestor-of rather than equals (`:71`), so both the `jj new` + `bookmark move` and `jj commit` routes pass |
| `workspace_add` | `assert_backed_by_the_project_repo` (`:82`) closes the `jj git init` cheat |
| `workspace_update_stale` | Genuinely distinct (stale working copy); needs the `@-` positional relaxed, and `test_no_stale_error:89`'s redundant stderr grep deleted as hygiene — the exit-code assertion above it already does the discriminating (R2, corrected). All three of its tests are scored; measured 0 on the untouched image, 1 on a genuine solve |
| `git_fetch_remote` | Fetch + rebase onto a remote-only bookmark + push, graded by commit id, with an anti-cheat guard |
| ~~`git_export`~~ | ~~`git rev-parse` compared to the resolved commit id~~ — **cut instead**; the verifier is fine, the premise is not (see below) |
| `obslog_view` | Recomputes the evolution with `jj evolog` at verification time; the answer cannot be hardcoded |
| `show_commit` | Each patch must carry the anchored commit's own id prefix, because a git diff of identical content is identical |
| `template_customize_log_output` | Renders the agent's alias and compares against a reference rendered by the verifier — quoting, config layer and authoring route agnostic |
| `undo_mistaken_rebase` | `--at-op` replay of parents by change id; `undo` / `op undo` / `op revert` / `op restore` all accepted |
| `operation_recovery` | 5 scored tests over files, tracked set, visible history and the op log |

### Merge — 6 *(was 7; the `git_import` → `git_export` merge is withdrawn — both are cut)*

| Task | Into | What survives, what does not |
|---|---|---|
| `bookmark_rename` | `bookmark_create_and_move` | Its change-id comparison (`:70-84`) is the only thing distinguishing rename from delete+create; it survives as an assertion in a create → move → rename lifecycle task. Its 1-test pass/fail shape does not |
| `bookmark_push` | `git_fetch_remote` | `git_fetch_remote` already requires the pushed ref to equal the commit the anchored change resolves to *at verification time*. `bookmark_push`'s describe → bookmark → push adds only the describe |
| ~~`git_import`~~ | ~~`git_export`~~ | **Withdrawn — both are cut.** The merge was coherent as long as `git_export` survived; it does not. `git_import`'s docstring (`:1-11`) is still the reference text for R3 and should move to whichever git-interop task replaces them |
| `workspace_forget` | `workspace_add` | Add → list → forget as one graded lifecycle, every step anchored by the project's change id. `workspace_forget`'s stdout-substring assertions do not survive |
| `log_template_author` | `template_customize_log_output` | `test_output_follows_the_repository_identity` (`:142-221`) survives — it mutates `@`'s author via `JJ_USER`/`JJ_EMAIL`, re-runs the script, requires the output to follow, then `jj op restore`s. `test_script_contains_a_jj_log_command` does not |
| `concurrent_operations` | new divergence task (N8) | The structural half survives: at some recorded operation the anchored change resolved to more than one visible commit (`:141-150`). The English `"reconcile divergent operations"` assertion (`:152-155`) does not |
| `duplicate_commit` | new duplicate-a-range task (N9) | Its children-of-anchored + content-compared-at-test-time + own-diff assertions generalise to a range. Its single scored test does not |

### Cut — 26 *(was 24; `git_import` arrives from the merge column and `git_export` from the keep column)*

| Task | Reason |
|---|---|
| `squash_commits` | Subsumed by `squash_range`; its only content check is floored, so nothing scored verifies the merge happened |
| `history_rewriting` | Its descendants check is floored; the one scored test only reads `base.txt` |
| `stacking_changes` | 1 scored test; pins `@`/`@-`; subsumed by `squash_range` + `restore_interactive` |
| `commit_splitting` | Near-identical to `split_commit_interactive`, which additionally survives the `jj edit` + `jj split -i` route |
| `rebase_destination` | 1 test; strict subset of `rebase_branch` |
| `restore_specific_revision` | 1 scored test; strict subset of `restore_file_from_parent` |
| `restore_file_from_parent` | Subsumed by `revert_file` |
| `untrack_file` | `status_ignored` with different filenames and weaker assertions |
| `ignore_patterns` | Same; its only real difference (glob `*.log` vs literal path) is not graded by any assertion |
| `conflict_resolution` | Strict subset of `rebase_branch`, which keeps the cheaper fixture's claims and adds the stack shape |
| `resolve_conflict_marker` | The bootstrap hands over an already-conflicted `@`; the only work is editing a file |
| `resolve_tool` | The verifier cannot detect whether `jj resolve` was used at all |
| `bookmark_delete` | One stdout substring; unanchored; 1 test |
| `git_integration` | Four existence checks; the push test passes on `git branch` in the remote |
| `diff_revisions` | Zero jj calls |
| `workspace_root` | Zero jj calls; the answer is printed in its own prompt |
| `template_formatting` | Regexes over default log output; bundles four sub-tasks; forbids an empty commit above `@` |
| `working_copy_as_commit` | One test verifies nothing; the rest is English prose and `isdir` |
| `root_commit` | Unanchored; a fabricated `root()`-child repo passes; the capability is the first two lines of `new_commit` |
| `git_remote_add` | Substring over `jj git remote list` |
| `revset_querying_bob` | Five stdout/file assertions; replaced by a real revset task (N4) |
| `next_prev_navigation` | The only task whose *deliverable* is the route. It cannot be made outcome-graded without becoming a different task, so under R3 it goes; the op-log surface it exercises is better served by N7 |
| `describe_commit` | 1 scored test; pins `@`; the capability sits inside `edit_commit_message` |
| `diffedit_interactive` | 1 scored test, a grep of `jj show`; replaced by N10, which grades the same capability structurally |
| `git_import` | The premise is a documented no-op. In a colocated repo *any* jj command performs the import, so the explicit `jj git import` reported it had nothing to do on 0.38 too; 0.44 says so out loud (`No import needed in colocated workspaces.`). See the correction below |
| `git_export` | Same premise from the other side, and the same reason. Its verifier is genuinely good — `git rev-parse` against the resolved commit id — but a good verifier over a vacuous ask is still a vacuous task |

*Added from the retarget measurement — `git_import` and `git_export` are cut, not merged.* Both
were already near-vacuous on 0.38 and are documented no-ops on 0.44. §4.0.2 #4 records that
`jj git init` is colocated by default and that **all 53 bootstraps use plain `jj git init`, so
every existing task image is colocated**; in a colocated repo the import happens automatically on
every jj command, and the export likewise. Executed side by side on both binaries: the explicit
`jj git import` after a `git`-CLI commit prints `Reset the working copy parent to the new Git
HEAD. / Done importing changes…` followed by `Nothing changed.` on 0.38 and `No import needed in
colocated workspaces.` on 0.44 — **the message moved, the behaviour did not, and in both versions
the commit was already visible to jj before the command ran** [0.44-verified, both binaries].
Nothing breaks either way; the point is that neither task ever graded the capability it names.
This also removes one of §3's four "capabilities that leave with the cuts" arguments in reverse:
the colocated-git *direction* pair is not a capability the suite loses, because it was never
testing it. What the suite genuinely lacks in this area is the survey's hole J — jj rewriting a
commit git `HEAD` points at, detached-HEAD recovery, a `git commit` racing jj's snapshot — which is
theme 4.6 on the menu and carries an execution warrant.

Four capabilities leave with the cuts and are not picked up elsewhere: `jj bookmark delete`,
`jj workspace root`, `jj git remote add`, and `jj show`/`jj diff` piped to a file. All four are
single-flag surfaces with no wrong solve worth catching. (`jj git import`/`export` are a fifth and
sixth, but as just argued they were never covered in the first place.)

### Where the better task has the weaker prompt

Four cases, and in each the verifier is what to keep:

- **`template_customize_log_output` over `template_formatting`.** Its prompt hands over the whole
  template expression; its verifier is the best in the suite at being route-agnostic, and it is
  the second-sharpest discriminator in the baseline (9/15).
- **`restore_interactive` over `restore_file_from_parent`.** Its prompt is the most
  verifier-shaped in the repo — the history is transcribed commit by commit and the end state is
  enumerated as seven bullets that map one-to-one onto assertions. It is also the strongest
  verifier there is. Keep the verifier, rewrite the prompt.
- **`status_ignored` over `untrack_file` / `ignore_patterns`.** Its prompt is the most spec-shaped
  of the three ("Your task is to: 1… 2…") and its verifier is the only one that proves untracking
  rather than never-tracking.
- **`squash_range` over `squash_commits`.** `squash_commits` has the cleaner prompt;
  `squash_range` leaks the technique in its Background and enumerates the post-state commit count.
  The verifier gap runs the other way by a wide margin.

---

## 4. What's missing

### 4.0 What "missing" means here — corrected against the binary-verified survey

Two framings of this section, and the second is the one that matters.

**The capability-token framing (this document's original, and still true).** Capabilities with no
task at all. I confirmed the absences by grepping all 53 prompts and all 53 verifiers:
`parallelize`, `simplify-parents`, `sparse`, `annotate`, `op diff`, `op show`, `op abandon`,
`file chmod`, `--restore-descendants`, `bookmark track`, `divergent()`, `jj fix`, `metaedit`,
`merges()`, `parents.len` and `glob:` appear nowhere. `conflicts()` appears only as substrings of
test *function names* (`test_no_unresolved_conflicts` and friends); `immutable_heads()` appears
once, in a docstring comment in `operation_recovery`. (Re-verified at `dd85164d` while
reconciling; every one of those greps still returns zero.)

**The coverage framing, which corrects a common assumption — including one this proposal's cut
list could be read as endorsing.** The survey (its §4.1) measured area coverage across all 53 and
found the received wisdom wrong: **workspaces (4 tasks), templates (3), absorb (1), git interop
(5) and conflicts (4) are all already covered.** I re-counted these against `tasks/` and they are
exact. Nothing in this document should be read as claiming any of those five areas has no
coverage — §3 cuts *into* four of them, which is only defensible because the survivors keep the
area. The hole in each is **variety and depth, not presence**: all four conflict tasks are the
same shape (one file, two sides, textual, resolved on the spot), the one revset task is
substring-graded, and the whole suite tops out at three dependent operations.

**So the real holes, restated in the survey's terms and in priority order:**

| # | hole | current state |
|---|---|---|
| A | **Merge commits** | Zero tasks. No `jj new A B`, no assertion anywhere on `parents.len() > 1`; `jj merge` does not exist ***[0.38-only — re-check]*** |
| B | **Revset depth** | One task (`revset_querying_bob`), 43 lines, substring-graded, and the weakest verifier in the set |
| C | **Immutability** | Zero. `immutable_heads()`, `immutable()`, the refusal, `--ignore-immutable` all untouched |
| D | **Author/committer surgery** | Zero. No `jj metaedit --update-author`/`--author`, despite this being the exact fact that broke `revset_querying_bob` and let `log_template_author` pass by accident |
| E | **Conflict variety** | Four tasks, one shape. Absent: a conflict deliberately *left* conflicted and carried through descendants, a conflicted bookmark, a delete/modify or file-type conflict, `jj resolve --list` |
| F | **Composition** | The longest chain in the suite is `git_fetch_remote` at **three** steps. Nothing composes five or more dependent operations, and nothing requires an intermediate decision that changes the rest of the plan |
| G | **Scale** | Every bootstrap is ≤ 6 commits and ≤ 3 files — never big enough that eyeballing fails and a revset or template becomes the only viable route |
| H | **Diagnosis** | Five tasks make the agent write a script; none make it diagnose and report a conclusion |

**F is the one that changes what the ten new tasks should be.** The survey's power finding is
blunt: opus's maximum attainable Δ on this suite is 0.38pp against a 6.02pp noise floor — 16×
below its own noise — and a *perfect* skill moves sonnet's 53-task mean by 4.15pp. The ceiling is
a property of the task set, and a suite of one-to-three-command tasks cannot discriminate a
frontier model no matter how many of them there are. The N1–N10 sketches below were written as
one-capability-per-task and are mostly two-to-three steps; **capability coverage alone does not
lift the ceiling.** §5 amends the target set accordingly.

### 4.0.1 The silent-success family — the richest vein, and it was missing from this section

*Corrected against the binary-verified survey.* This document's original §4 organised the new
tasks by capability. The better organising principle is the survey's §3: the cases where **jj
exits 0 having done nothing**, or something other than what was asked. There is no error to read,
no non-zero status to notice, and no prompt to reconsider — so a git-shaped agent finishes
confidently and reports done, and a verifier that grades end state catches it perfectly. Every
member below is `[verified]` against the pinned binary — **and every one was re-run on 0.44, where
the vein got *wider*, not narrower**:

- **Empty revsets: the source side is silent, the destination side is loud.** *Corrected at
  `3ad91698` — this bullet used to say "silent per flag, not per command", which was the 0.38 rule
  and is now wrong.* On 0.38 the asymmetry sat *inside* `jj rebase`: `-r <empty>` printed
  `Nothing changed.` at exit 0 while `-s` and `-b` errored at 1. **On 0.44 all three exit 0** with
  `No revisions to rebase.` (B6), and so do `jj squash --from <empty>`, `jj abandon <empty>`,
  `jj describe -r <empty> -m X`, `jj duplicate <empty> -o X` and `jj absorb -t <empty>`. What still
  errors is the *destination*: `rebase -r X -o <empty>`, `squash --from X --into <empty>`,
  `jj new <empty>` and `bookmark set zz -r <empty>` all exit 1, unchanged. So the live distinction
  is **what you are selecting (silent) versus where you are putting it (loud)** — which is a real
  jj concept rather than a per-flag quirk, and it makes the trap *uniform* across the whole source
  side. Two consequences for task design: any task premised on "`-s` will error and catch the
  agent" is **void on 0.44**, and any task premised on "an empty revset silently does nothing" is
  **stronger than it was**. Combine with the string-pattern trap — a bare string in `description()`
  is a whole-string `glob:` and jj stores descriptions with a trailing newline, so
  `description("Add feature A")` matches **nothing** — and the canonical false success is
  `jj squash --from 'description("Add feature A")' --into 'description("Add base")'` printing
  `Nothing changed.` at exit 0. Both halves 0.44-verified.
- **`jj file track <ignored-path>` without `--include-ignored` exits 0 and tracks nothing.** No
  error, no warning. This is already in the suite as `track_untracked_file`, which is why that
  task is the one kept item with a measured non-zero failure rate on sonnet.
- **Pushing an untracked new bookmark.** `jj bookmark create newb && jj git push` →
  `Warning: Refusing to create new remote bookmark newb@origin` + `Nothing changed.` at **exit 0**.
  A second, distinct exit-0 path exists when nothing is in the default push revset.
- **`jj next -n 2` flips edit semantics.** On 0.38 `-n` is `--no-edit` (a boolean) and the count is
  a positional; `--amount` does not exist. So `-n 2` parses as `--no-edit` **plus** `OFFSET=2` —
  the agent gets the right offset by accident while silently flipping whether `@` lands on a new
  child or edits the target in place. That changes the graded end state. **Unchanged on 0.44**,
  both branches re-measured — this trap survives the retarget intact, and it is the one place where
  the newer spelling still succeeds-with-different-semantics rather than erroring.

*Two membership changes at the retarget, both worth knowing before porting a 0.38 task idea.*

- **One member left.** `jj file search` pattern kinds were **fixed on 0.44**: kinds are parsed,
  the default flipped `glob:` → `regex:`, an unknown kind is a hard error at exit 2, and
  `-n`/`--name-only` were added. On 0.38 every kind prefix matched nothing at exit 0 with empty
  output. **It no longer discriminates** and must not be used as a trap. Note the sting: the
  0.38-*correct* spelling `-p '*TODO*'` is now a hard error, so a fixture or reference solve
  carried across versions fails loudly rather than silently — which is the good direction.
- **One member arrived, and it is aimed at us rather than at the agent.** A **template runtime
  error renders `<Error: …>` inline and exits 0** on 0.44. It is a verifier hazard, not a task, so
  it is written up in §4.0.2 #10 below rather than here.

**Make this a selection criterion for the ten.** A task whose wrong solve *errors* is testing
discoverability; a task whose wrong solve *succeeds* is testing the mental model, which is R1.
Every one of the four above is rated excellent for gradeability because the wrong end state is
trivially distinguishable from the target one.

### 4.0.2 Verified facts that constrain these fixtures and verifiers

From the survey's corrections appendix (its §10, now rewritten as a **0.44** list) and its new §9.
These would poison a fixture or a verifier in the set proposed below, and none of them was known
when §4 was first drafted. Each carries its provenance: **0.44-verified** unless marked
***[0.38-only — re-check]***.

1. **`??` marks a CONFLICTED BOOKMARK, not divergence.** Divergence renders as numbered `X/N`
   offsets plus a `(divergent)` marker. Both tutorials get this wrong and the two markers can
   appear on the same log line. A divergence verifier that greps `??` grades the wrong thing — *and
   so does one that hardcodes the offsets.* **The offset rule, now established by execution rather
   than inferred from examples:** `X/N` indexes **every commit that has ever carried change id
   `X` — visible *and* hidden alike — in reverse-chronological order of creation**, so `/0` is the
   most recently created version and visibility does not reorder the list. The divergence hint
   prints only the **visible** members, so the numbers you see are wherever the visible sides happen
   to land. Two sides read `/0` and `/1` **only** when neither has been rewritten since the fork;
   rewriting one side three times pushes the other to `/4` — which is exactly how the measured case
   that gave **`X/0` and `X/4`** arose, and it is no longer a mystery. **Never match the literal
   strings `X/0` or `X/1` in a verifier.** Resolve by `change_id(X)` (which selects every visible
   member regardless of offset), by commit id, or by parsing the
   `Hint: Use change offset to select single revision: …` line at verification time. `(divergent)`
   and `??` are themselves stable and safe to match; the digits after the slash are not. The whole
   divergence and conflicted-bookmark story is **byte-identical** between 0.38 and 0.44 — only our
   understanding of the offsets changed. Every theme touching divergence (2.7, 3.6, 4.3) inherits
   this.
2. **A bare change-id revset ERRORS on a divergent change**, and a bare bookmark-name revset
   ERRORS on a conflicted bookmark — `Error: Change ID 'x' is divergent` / `Error: Name 'main' is
   conflicted`, both exit 1. `present(X)` does not help. Verifiers must spell `change_id(X)` and
   `bookmarks(name)`. A verifier for N8 or for a conflicted-bookmark task **can be broken by the
   exact trap it tests**. `tasks/concurrent_operations/tests/test_final_state.py:26-31` already
   gets this right and is the in-tree reference.
3. **The `all:` revset prefix is a parse error on both versions.** The message moved — 0.38 said
   `Error: Failed to parse revset: Syntax error`, 0.44 says ``` `:` is not an infix operator ```
   plus a `::` hint — so **do not match on the text**; the fact to rely on is that it fails. The
   arity guard survives in genuinely single-revision positions, but the bulk-rebase idiom is spelled
   without a prefix, and a multi-revision revset needs none in `-s`/`-r`/`-o`. Do not put `all:` in
   a reference solution or an instruction.
4. **`jj git init` is colocated by default** — `--colocate` is an accepted no-op — and this is
   **unchanged on 0.44**, along with all four opt-in/opt-out paths. All 53 bootstraps use plain
   `jj git init`, so **every existing task image is already colocated**, and `git` is present in
   every image. That is a live unintended false-pass route in tasks that never meant to be about
   git, and it is why `git_import` and `git_export` are now both **cut** (§3) rather than merged:
   in a colocated repo the import and the export happen automatically on every jj command, so
   neither task's headline command ever did the work it is named for. A task that wants a
   *non*-colocated repo must pass `--no-colocate`.
5. **`jj backout` does not exist** (`error: unrecognized subcommand`); only `jj revert`, and its
   destination flag is **mandatory** — a bare `jj revert -r X` is a clap error at exit 2. Unchanged
   on 0.44, which additionally now requires `-r/--revision` on `jj revert` as well.
6. **`--allow-new` is GONE on 0.44 — and so are six other things this document once relied on being
   merely deprecated.** *This item is inverted from what it said at `dac8118b`.* On 0.38
   `--allow-new` was hidden but fully functional: absent from `-h`, one deprecation warning, and it
   **succeeded**, so a verifier could not fail a solve that used it. On 0.44 it is
   `error: unexpected argument '--allow-new' found` at exit 2 and the agent sees it. The full
   removal list, every entry executed on the 0.44 binary: **`jj git push --allow-new`, `jj op
   undo`, the `jj undo <OPERATION>` positional, `jj describe --reset-author` (with `--author`,
   `--no-edit`, `--edit`, and `commit --author`/`--reset-author` alongside it), the revsets
   `git_head()` and `git_refs()`, `jj git clone --fetch-tags` (replaced by `--tag=PATTERN`), and
   the setting `ui.revsets-use-glob-by-default`.** `diff_contains()` **survives, still deprecated**
   — do not assume it went with them. Four of these were *deprecated-but-functional* on 0.38, so
   the retarget **fixes three live measurement bugs**: an agent reaching for `jj op undo`,
   `--allow-new` or `--reset-author` on 0.38 silently succeeds and the suite scores it correct.
   One deprecation ran the other way, and it is easy to get backwards: **`jj bookmark track
   <name>@<remote>` warned on 0.38 and is the canonical documented spelling on 0.44**, with empty
   stderr, and jj's own push hint now recommends it.
7. **Repo config is NOT at `.jj/repo/config.toml`.** It lives at
   `$HOME/.config/jj/repos/<20-hex>/config.toml`, keyed by `.jj/repo/config-id`, and a hand-placed
   `.jj/repo/config.toml` is **ignored**. Unchanged on 0.44. Any fixture that sets repo config must
   go through `jj config set --repo`, and any verifier that wants to know what an agent configured
   must *evaluate* the setting rather than read a file. N6 below already specifies evaluation; this
   is the reason it must. **A 0.44-specific sharpening of the same point:** `jj config set --repo`
   accepts nonsense keys silently *and* accepts the keys 0.44 **removed** —
   `git.auto-local-bookmark`, `git.push-new-bookmarks`, `ui.revsets-use-glob-by-default`,
   `core.fsmonitor`, `core.watchman.register-snapshot-trigger` all exit 0, print nothing, and list
   back happily while doing nothing. Nothing reports it: not the build, not the lint, not the anchor
   pass, not the verifier. **Grep every bootstrap for those five keys as part of the re-pin**; a
   `RUN` that sets one still exits 0 and hands over a repo that behaves differently from the one its
   author designed.

Four more that are not from the appendix, and that bite the *authoring* of a fixture rather than a
claim in it. All four are cheap to hit and expensive to diagnose; #10 and #11 are new at the
retarget and are the two that bite *quietly*:

8. **`jj squash --from/--into` opens the editor when BOTH commits carry a description**, to let you
   combine them — so with no TTY it exits 1 rather than doing the squash. Unchanged on 0.44
   [0.44-verified; first measured in the survey's 0.38 review pass, its §2.6 and theme 1.2]. Any
   non-interactive fixture
   step, and any scripted reference solve, must pass `-u`/`--use-destination-message` or `-m`.
   This repo has already been bitten: `squash_range`'s
   `test_target_commit_still_described_as_the_target` is a containment check rather than an
   equality check precisely because the description-combining and the `-u` routes end up with
   different descriptions (`tasks/squash_range/tests/test_final_state.py:320-336`).
9. **Do NOT use `GIT_CONFIG_GLOBAL=/dev/null` for hermeticity.** A `git config --global` run under
   that setting **rename-replaces the device node** — git writes a temp file and renames it over
   the target, so the image ends up with a regular file where `/dev/null` was, and everything
   downstream in that build that redirects to `/dev/null` silently accumulates into it instead.
   Point `GIT_CONFIG_GLOBAL` at a scratch path inside the build. (The survey's hermetic harness now
   bans `/dev/null` outright for the same reason.)
10. **A template runtime error renders `<Error: …>` INLINE and exits 0 — so a template task can
    silently grade garbage.** New on 0.44 and aimed squarely at us rather than at the agent. On
    0.38 a bad template failed at **parse** time at a nonzero exit, which was loud; the constructs
    that produce *runtime* errors (`List.get()`, `Timestamp.since()`) are 0.44-only, so this
    failure mode did not previously exist. Measured:
    `jj log … -T '… ++ parents.get(9).change_id().short(8) ++ "\n"'` writes
    `nrlwrrmw <Error: Index 9 out of bounds>` into the output file and exits **0**. It was hit live
    during a fixture pass where a conflicted commit rendered `<Error: Out-of-range date>` mid-report
    at exit 0. **`try(expr, fallback)` is the fix and this is its real purpose.** The verifier rule
    is not "diff the report field by field more carefully" — it is: **any graded artifact
    containing the substring `<Error:` must be rejected outright**, before any comparison. Without
    that, the task grades garbage and records it as a wrong answer, which in a trial log is
    indistinguishable from a model failure. This lands directly on
    `template_customize_log_output` — the one template task in the shipping 14 — and on every
    Tier 5 theme that emits a report.
11. **The bookmark/tag tracking asymmetry is `fetch`-only, so a two-actor fixture must pin which it
    uses.** On 0.44 tags are fetched, tracked and pushed like bookmarks, and a **fetch** brings
    *bookmarks in untracked and tags in tracked*. But `jj git clone` **tracks the bookmark too**:

    ```
    $ jj git fetch   (existing repo)          $ jj git clone remote.git clone
    bookmark: main@origin [new] untracked     bookmark: main@origin [new] tracked
    tag:      v1.0@origin [new] tracked       tag:      v1.0@origin [new] tracked
    ```

    So a fixture built with `jj git clone` and one built with `init` + `remote add` + `fetch` hand
    the agent **different bookmark tracking state**, and every push-related silent success (§4.0.1)
    hangs off exactly that state. Pick one and write it down in the fixture recipe. Related, and
    also new: `jj git push --all` now pushes tags, git's `tagOpt` is ignored (the knob is
    `remotes.<name>.fetch-tags`), and running a 0.44 fetch in a 0.38-built repo re-fetches every
    tag to initialise tracking state — so a bare remote carrying tags produces a jj-side state a
    0.38 author would not predict.

One more, for the anchor rather than the fixture: `jj config set --repo <key> <value>` does not
validate key names — nonsense keys are accepted silently at exit 0, as are the five config keys
0.44 removed (#7). "The agent set a config key" is never evidence the key does anything, and "the
bootstrap set a config key" is never evidence the repo behaves as designed.

### 4.0.3 Provenance roster — what is 0.44-verified, and what must be re-checked first

*Added at the retarget.* Everything above and below carries one of two provenances (see the note in
the preamble). This is the short list of what is **not** yet 0.44-verified, so that nobody has to
reconstruct it by reading for the italic marks. **R7 forbids a new task depending on any of these
until the named probe has been re-run on `jj 0.44.0-af45d57de716`.**

| claim in this document | where | what would settle it |
|---|---|---|
| The list of operations that legitimately drop a change id (`abandon`, `squash --from/--into`, `new`/`edit`/`prev`/`next` off an empty undescribed `@`, `workspace forget`, `op restore`) | §5 prereq 3 | Re-run each against a 0.44 image and diff the anchor codes. This is the highest-value re-check on the list: a wrong entry here is a task-arm-destroying missing exemption, and it is the one blind spot a green pre-sweep cannot cover |
| `jj merge` does not exist | §4.0 hole A | `jj merge -h` on the 0.44 binary. N2 and theme 1.5 both assume `jj new A B` is the only route |
| `jj evolog` does not carry a divergent sibling | §4.1 N3 | An `evolog` on either side of a 0.44 divergence. N3's verifier turns on it |
| Theme 3.6's residual divergence and its `X/0`/`X/4` offsets | §4.2 N3 row | The *mechanism* (restore-is-time-travel vs revert-is-an-inverse-patch) **was** re-run on 0.44; the full fixture — squash, two commits of later work, `jj op revert` — was executed on 0.38. Re-run the whole fixture and record whether the divergence still appears and at which offsets. Cheapest remaining warrant gap on the menu |
| `workspace_update_stale`'s bootstrap reproduces staleness by `jj rebase -r default@ -d @` from the second workspace | §5.1 | Rebuild that one image on 0.44 and run its `bootstrap/test_initial_state.py`. The byte-identical floor result makes this near-certain, but "near-certain" is what R7 exists to forbid |

**Everything else behavioural in this document is 0.44-verified**, either by the survey's V44/N44
passes or by our own 58-task re-pin measurement. That specifically includes: the whole
silent-success family (§4.0.1), all eleven fixture gotchas (§4.0.2), the divergence and
conflicted-bookmark story, colocation by default, the repo-config path, the `all:` prefix failing,
the `next -n` trap, `jj squash --from/--into` opening the editor, the interactive commands failing
fast, and the removal list. **Every *number* in this document remains 0.38-only by construction**
and is not comparable forward — that is the accepted cost of the retarget, not an item on this list.

### 4.1 The six to lead with

Fixture / the request in a user's voice / what the verifier asserts. Each is cross-referenced to
the survey theme that covers the same ground with a verified fixture recipe; where a survey theme
exists, prefer it.

**N1 — a conflict that propagates instead of being resolved on the spot.** All four current
conflict tasks resolve immediately, so nothing tests jj's actual differentiator: a conflicted
commit is a normal commit you can build on.
*Fixture:* a four-commit stack that conflicts in its second commit when rebased onto a moved
`main`, with a fifth commit already sitting on top of the conflict.
*Request:* "I rebased onto main and the middle commit blew up. Don't unpick the stack — fix it
where it broke and make sure everything above comes out clean."
*Verifier:* the anchored middle change has `conflict == false`, every anchored descendant has
`conflict == false` and still resolves, and the head's tree carries the resolved file. A fixup
commit on top leaves the middle one conflicted and fails.

**N2 — a merge commit the agent creates.** No task ever asks for one; `resolve_tool`'s bootstrap
contains a merge the agent only resolves.
*Fixture:* two bookmarks whose tips both changed `config.toml`, no merge present.
*Request:* "Merge feature-a and feature-b and sort out the clash in config.toml — keep both
settings."
*Verifier:* `@`'s parents are exactly the two anchored changes (order-insensitive), `conflict ==
false`, the merged tree contains both settings, and neither anchored change was rewritten.

**N3 — `evolog` as recovery.** `obslog_view` only prints the evolog; nothing tests the point of
the feature.
*Fixture:* a change whose current version was clobbered by the bootstrap — description overwritten
and a file restored away — with the good version still in its evolog.
*Request:* "I described over the wrong commit and then restored a file I shouldn't have. The old
version is still in there — put that content back on the same change."
*Verifier:* the anchored change id still resolves; its tree equals the tree of a commit id that
appears in its own evolog and is not the evolog head; the recovered file's content matches that
predecessor byte for byte. Recomputed at verification time, so nothing is hardcoded.
*One input to this design is ***[0.38-only — re-check]***:* that `jj evolog` on the surviving side
of a divergence does **not** carry the divergent sibling (it is a sibling, not a predecessor). N3's
verifier reads the evolog for a predecessor tree, so if that changed, "not the evolog head" stops
meaning what it means here. Re-run an `evolog` on either side of a 0.44 divergence before authoring.

**N4 — revsets the agent writes.** Only `revset_querying_bob` asks for one, and it is
`author() & ~::main & ::@`. Untested: `roots()`, `heads()`, the `..`/`::` distinction,
`mutable()`/`immutable()`, `latest(n)`, `divergent()`, `at_operation()`.
*Fixture:* a branching history with several heads, some already merged into `main`.
*Request:* "Give me the change ids of every tip that isn't merged into main yet — one per line in
unmerged.txt."
*Verifier:* evaluate the reference revset in the repo at verification time and require the file to
equal that set of change ids exactly. A hand-listed file passes only if it is right, and the
expected answer is never a constant in the verifier.

**N5 — filesets.** Verifiers *use* `files(root-file:"…")`; no prompt asks an agent to write a
fileset, and `glob:` appears nowhere.
*Fixture:* a commit that changed both `src/**/*.py` and a `src/generated/**` tree.
*Request:* "Roll back my changes under src/ but leave the generated tree exactly as it is."
*Verifier:* `changed_paths` of the anchored change is exactly the non-generated set; every
generated file's content equals the bootstrap's; the anchored change id survives. Doing it
file-by-file also passes — the fileset is the cheap route, not the graded one (R3).

**N6 — immutable revsets.** Nothing configures `revset-aliases."immutable_heads()"`, and nothing
tests jj refusing a rewrite.
*Fixture:* `main` with two commits below it and two above; no immutability configured.
*Request:* "Set this repo up so nothing at or below main can be rewritten by accident, then fix
the typo in the message just above it."
*Verifier:* the verifier *evaluates* the configured `immutable_heads()` alias and requires the
anchored `main` change to be inside it (not a string match on the config value); the anchored
commit below `main` is byte-identical to the bootstrap's; the anchored change above it carries the
corrected description and the same change id.

**N7 — the operation-log surface beyond `undo`.** Only `op log` and `op restore`/`undo` appear;
`op diff`, `op show` and `op abandon` are untouched.
*Fixture:* a repo whose op log contains one multi-commit rebase among several small operations.
*Request:* "Which commits did that big rebase actually touch? Put the change ids in touched.txt."
*Verifier:* recompute the operation's effect at verification time (by `--at-op` differencing) and
require the file to match. Whether the agent used `jj op diff` or worked it out by hand is not
graded.
*0.44 caveats, both load-bearing for this task and for every other `--at-op` verifier in the suite.*
First, `jj op show` / `op diff` / `op log -p` now **filter changed revisions by default**
(`revsets.op-diff-changes-in = "mutable() | immutable_heads()"`); in a constructed mid-stack rebase
both versions printed identical lists, so the practical impact is narrow, but it bites when an
operation touches hidden or non-head immutable revisions, and `--show-changes-in` overrides.
Second, and larger: **`--no-integrate-operation` plus `jj op integrate` are real on 0.44** (the
command was inert on 0.38), which means an agent can now produce side effects that leave **no
op-log entry**. Any verifier that reconstructs truth by `--at-op` differencing is reasoning over a
log that is no longer guaranteed complete. That is a hazard for N7 specifically and worth a probe
before N7 is authored.

The remaining four in the target set:

- **N8 — divergence as a thing to work with.** Absorbs `concurrent_operations`. Hand over a repo
  with two visible commits sharing one change id; keep the one containing a named file and abandon
  the other, addressed by commit id since the change id is ambiguous.
  *Corrected against the binary-verified survey — and against the tree.* This is **not** new
  capability coverage, and neither this document's original framing nor the survey's "absent: a
  divergent change" (its §4.2 F) is right about that. `concurrent_operations` already builds a
  divergent change and resolves it: its `instruction.md:9-11` asks for exactly the survey's own
  single-actor divergence route (`describe`, then `describe` again `--at-operation` an earlier op),
  and its verifier already spells `change_id(<id>)`, already reads the `divergent` template keyword
  (`:124-125`), and already documents that the abandoned side is a divergent *sibling* rather than
  a predecessor (`:26-31`). What N8 actually is, therefore, is a **re-scope** of that task: keep
  the structural half (`:141-150`), delete the English assertion (`:152-155`), and hand the
  divergence over pre-made instead of asking the agent to manufacture it — which is what makes the
  prompt writable in a user's voice. The survey's themes 2.7 and 4.3 are the same task at Tier 2
  and Tier 4; 4.3's two-actor version is the one with genuinely new content, because it pairs
  divergence with a conflicted bookmark on the same log lines. Note the solve removes a change id,
  so N8 needs an `anchor_exemptions.json` — and a green pre-sweep pass **cannot** tell you it is
  missing, because the untouched image never does the work that breaks the assertion.
- **N9 — duplicate a range.** Absorbs `duplicate_commit`. `jj duplicate -r A::B -d X` /
  `--insert-after`, with each duplicate's own diff asserted and both anchored originals intact.
- **N10 — a configured non-interactive diff editor.** Replaces `diffedit_interactive`. All three
  "interactive" tasks can be, and by their verifiers' design should be, solved non-interactively,
  so `ui.diff-editor` is untested. Configure a scripted tool and use `jj squash -i` to move exactly
  one hunk; grade the resulting trees.
  *Corrected against the binary-verified survey: N10 as written violates R3 and should not ship in
  this form.* Requiring `-i` is a method constraint, and the survey removes the argument for it
  from both ends. First, the interactive commands **fail fast rather than hang**: with stdin closed
  `squash -i` / `split -i` / `commit -i` / `diffedit` exit 1 in tens of milliseconds, so an agent
  that reaches for `-i` loses a turn, not the trial — there is nothing to protect the suite from.
  **This survives the retarget, but the error *text* does not** — 0.44 says `Error: Failed to edit
  diff / Caused by: 1: Failed to record changes / 2: failed to set up terminal: No such device or
  address (os error 6)` where 0.38 said `Error: Failed to edit diff`, so do not grade on the
  string; grade on the exit code, or better, on nothing at all. Second, every interactive route has
  a verified non-interactive substitute (`jj squash <paths>` or `--from`/`--into`,
  `jj split -r X <paths> -m`, `jj describe --stdin`, `jj resolve --tool :ours`/`:theirs`), so a
  verifier cannot tell the routes apart from end state and must not try. *One thing that did change
  in N10's favour, and it does not rescue the design:* a **scripted diff editor via `--tool` is now
  proven to work** (the 0.44 fixture pass drove `jj absorb -i --tool`), so the interactive family is
  reachable headlessly. That makes a scripted-editor *fixture* possible; it does not make grading
  the route legitimate. The salvageable ask is "move exactly one hunk, leave the
  rest of the commit alone", graded on the two resulting trees and route-agnostic — which is
  essentially the survey's theme 2.1 (split by path) or 3.3 (absorb into a stack). If a task does
  ship a scripted editor, note the in-tree operational caveat: a stray `editor.sh` left behind by a
  solve already breaks floored working-copy guards on `diffedit_interactive` and
  `split_commit_interactive`, so the verifier must tolerate it or the fixture must place it outside
  the repo.
- **N11 is not in the set.** Held in reserve, in rough priority order: conflicted bookmarks from a
  remote (`jj bookmark track`/`untrack`, local and remote both moved), config-layer precedence
  (`--user` vs `--repo`, `--include-overridden`), `jj fix` across a stack, `jj parallelize`,
  `jj simplify-parents`, `jj sparse`, `jj file annotate`, executable bits and symlinks,
  `jj op abandon`, `jj abandon --restore-descendants`, colocated HEAD races.

### 4.2 N1–N10 against the survey's theme menu — now 51 themes, not 39

*Added during reconciliation; theme count updated at the retarget.* The ten below are a statement of
coverage, not a shortlist. Where a survey theme covers the same ground, it ships with a verified
fixture recipe and a prompt already written in a user's voice, and it wins. Survey tiers:
1 = single operation, 2 = two-to-three steps, 3 = five-plus dependent operations, 4 = collaborative
/ colocated, 5 = diagnosis. **The menu grew from 39 to 51 at `3ad91698`** — twelve themes authored
natively against 0.44 — distributed **6 / 11 / 15 / 10 / 9** across the five tiers, with **16
carrying an execution warrant** (8 of them in Tier 3, which is exactly where amendment 2 wants
them). Theme numbers did not shift, so every citation in the table below still resolves.

| here | survey theme(s) | tier | verdict |
|---|---|---|---|
| N1 conflict propagates | 3.5 *resolve a propagated conflict once*, 2.4 *leave a conflict, build on it* | 3, 2 | Use the survey's. N1 conflates the two; they are better as one Tier 3 task, and 2.4 is a distinct and sharper Tier 2 |
| N2 merge the agent creates | 1.5 *merge with ordered parents*, 4.2 *conflicted bookmark repair* | 1, 4 | N2 is a hybrid the menu lacks — a merge the agent **creates** *and* resolves. Keep N2's shape, take 1.5's `parents.map(...)` grading |
| N3 evolog as recovery | 3.6 *recover from your own mistake*, 5.5 *which operation lost this file* | 3, 5 | Use 3.6. Deeper composition; the tier's highest grader-artifact risk, mitigated by change-id replay and no string matching. **Take the `3ad91698` version:** the adversarial review ran this theme and found its named solve wrong — `jj op restore` is time travel and deletes the later work, only `jj op revert <squash-op>` reaches the end state, and the correct route leaves a divergent change at offsets `X/0`/`X/4`, so grade through `change_id()` and decide whether the residual divergence is acceptable end state. It also needs an anchor-exemption decision. **Sharpened on 0.44:** the *mechanism* was re-run (`op restore` on `A→B→C→D` left `A,B` only; `op revert` of the op that made `C` kept all four commits and merely stripped `C`'s description), which relocates the assertion — grade **"does `D` still exist"**, not "is `C` back". The tempting contrast "restore removes C and D, revert removes only C" is wrong and a verifier written on it fails the correct solve. The full fixture is still ***[0.38-only — re-check]*** (§4.0.3) |
| N4 revsets the agent writes | 5.3, 5.4, 5.6; 3.7 *messy history → mergeable* | 5, 3 | Prefer 3.7: it makes the revset the *route* to an action rather than the deliverable, which dodges the zero-tool-call confound |
| N5 filesets | 2.1 *split by path* is the nearest | 2 | No dedicated fileset theme in the menu. N5 is additive; keep it |
| N6 immutability | none dedicated (5.4 uses `immutable()` as a query only) | — | **Additive.** The survey names immutability as hole C but ships no theme for it. N6 stands, and its "evaluate the alias, don't string-match the config" design is now mandatory (§4.0.2 #7) |
| N7 op log beyond undo | 5.3 *what did the last operation do* | 5 | Same task. Use the survey's phrasing and its `--at-op` differencing rule |
| N8 divergence | 2.7 *clear a divergent change*, 4.3 *divergent change repair* | 2, 4 | Neither is new (see N8 above). If one ships, ship 4.3 — the two-actor version pairs divergence with a conflicted bookmark |
| N9 duplicate a range | none | — | **Additive.** No duplicate theme in the menu; keep it |
| N10 configured diff editor | none; superseded by 2.1 / 3.3 | 2, 3 | **Do not ship as written** — R3 violation, see above |

Two gaps run the other way, and both are this document's to fill rather than the survey's:

- **The menu has no workspace theme at all**, and the retarget did not add one — **none of the 51**
  touches `jj workspace` as a subject, even though
  the survey's own capability map covers it. `workspace_add` and `workspace_update_stale` are
  therefore not replaceable from the menu, which is part of why they stay in §5.
- **The menu has no immutability theme and no duplicate theme**, per the table. N6 and N9 are the
  only routes to holes C and to `jj duplicate` respectively.

*Added at the retarget — what the twelve new themes add, and the one that is a genuinely new task
family.* The 0.44-native additions are worth reading before the ten are chosen, because three of
them cover ground no 0.38 theme could:

- **`jj run` fully works on 0.44.** On 0.38 it is an explicit stub that errors; on 0.44 it is a
  real command, and it opens a task family this suite has no equivalent of: *"apply this mechanical
  change to every commit in the stack"* (theme 3.11, executed). It measured cleanly on the property
  that matters most to us — a `jj run` over a 4-commit stack **preserved all four change ids and
  replaced all four commit ids**, which is exactly the invariant the bootstrap anchor rests on, so
  a `run` task is anchorable without an exemption. It is also a **new verifier instrument**:
  `--ignore-changes` sweeps read-only (theme 3.13). One warning attaches: a stated end state no
  longer implies a particular per-commit command sequence, which is a feature under R3 and a
  hazard for anyone writing a route-shaped verifier.
- **Tags are a whole new capability area at zero coverage** (`jj tag track/untrack`, `push -t`,
  `list -t/-c`), adjacent to the conflicted-bookmark artifact the two-actor rig already produces —
  themes 3.15 and 4.10. This is hole K, and it did not exist to be missed on 0.38.
- **`jj git push --allow-conflicts`** makes publishing a conflict possible (theme 4.9, executed),
  which is both a new theme and a route *around* a check a task might have assumed was closed.

Also new and smaller: `jj bookmark advance` (so the "bookmarks don't follow `jj commit`" trap now
has a one-command answer, and existing bookmark-movement tasks get easier), `jj absorb -i/--tool`
(theme 3.14, executed), `rebase --simplify-parents`, template `try()`/`List`/`.since()`/`replace()`
and the revsets `merge_point()` / `forks()` / `diff_lines_added|removed()` (two diagnosis themes
that cannot be solved by `files()` or by eyeballing). Two additions are hazards rather than surface:
`jj arrange` and `jj config gc` are TTY-gated with no headless path at all.

---

## 5. The target set

**24 tasks: 14 kept, 10 new.**

The second filter on the keep list is discrimination. Of the 21 tasks that survive §3, nine
separated the three models in the baseline (`abandon_commits`, `edit_commit_message`,
`rebase_branch`, `restore_interactive`, `split_commit_interactive`, `squash_range`,
`template_customize_log_output`, `track_untracked_file`, `workspace_update_stale`); five more hold
a capability nothing else covers (`absorb_changes`, `undo_mistaken_rebase`, `operation_recovery`,
`git_fetch_remote`, `workspace_add`). That is the 14.

The other seven — `bookmark_create_and_move`, `new_commit`, `new_insert`, `obslog_view`,
`revert_file`, `show_commit`, `status_ignored` — are structurally sound and were 5/5 on all three
models. They belong in a smoke tier or nowhere. If a second ignore-surface task is wanted,
`status_ignored` is the one to bring back: its verifier is the strongest of the three. *(Was eight;
`git_export` is now cut outright rather than demoted — §3. The shipping 14 is unaffected, because
`git_export` was never in it.)*

| Tier | Tasks |
|---|---|
| Rewriting history in place (7) | `squash_range`, `split_commit_interactive`, `restore_interactive`, `absorb_changes`, `edit_commit_message`, `abandon_commits`, **N9** |
| Conflicts and merges (3) | `rebase_branch`, **N1**, **N2** |
| Recovery, divergence, the op log (5) | `undo_mistaken_rebase`, `operation_recovery`, **N3**, **N7**, **N8** |
| Query, config, immutability (5) | `template_customize_log_output`, **N4**, **N5**, **N6**, ~~**N10**~~ → a Tier 3 theme |
| Files, remotes, workspaces (4) | `track_untracked_file`, `git_fetch_remote`, `workspace_add`, `workspace_update_stale` |

*Corrected against the binary-verified survey.* N10 is struck (§4 — it grades HOW, and the
interactive commands it was designed around fail fast rather than hang, so there is nothing to
protect against). Its slot goes to a Tier 3 composition theme per amendment 2 below. Read every
**N** in this table as "the survey theme that covers this ground", not as the sketch in §4.

**Why 24 and not 20 or 40.** At five attempts per task per model, 24 tasks is 120 trials per
model — each task worth about 4% of the headline. That matters because grader artifacts are not
hypothetical here: we have three measured ones (`git_import`'s argv contiguity,
`template_customize_log_output` scoring identical correct behaviour 1.0 hand-edited and 0.5
through `jj config set`, `duplicate_commit`'s refusals). At 20 tasks a single artifact moves a
model comparison by 5%+ and can invert a skill A/B. Above roughly 30 the marginal task buys
nothing: 36 of the current 53 produced no separation at all, so headroom comes from difficulty,
not count. 24 is the smallest number at which one bad task cannot dominate.

### 5.1 The headline survives the reconciliation. Three amendments to how it is reached

**24 tasks — 14 kept, 10 new — stands, and stands unchanged as the *shipping* target.** The
survey's §8.2 recommends 30–40 instead, weighted 15/25/30/20/10 across its five tiers. I am not
adopting that number, and the reason is the survey's own strongest measurement: **at fixed budget,
N versus T is a wash** — the trial count T cancels in the non-centrality parameter, so only *which*
tasks are in the design matters, and saturated tasks contribute **exactly zero**, verified equality
rather than an approximation. If count is not the power lever, then 30–40 is not a power argument;
it is an insurance argument about not knowing in advance which tasks will discriminate. That is a
real concern and it is answered below by authoring a superset, not by shipping one. Meanwhile the
argument *for* 24 is about a different failure mode — a single grader artifact dominating a model
comparison — which the survey does not address and which its own data makes more pressing, not
less, since it documents a fourth measured artifact (opus's single loss in 265 trials was a
literal-substring test rejecting a correct `jj -R <dir> git import`).

What the survey's evidence *does* change is everything about how the ten are chosen and what shape
they are.

**Amendment 1 — author sixteen, ship the ten that discriminate.** The survey measures held-out
precision of task screening at **0.51 on haiku and 0.00 on opus**, with selected tasks' failure
rates inflated **2.18×**. Nobody can pick the ten winners on paper, and this document's §4
sketches are exactly that kind of paper pick. Author ~16 from the survey's 51-theme menu, run one
screening sweep, and ship the ten with the highest *observed* failure rates — selecting on failure
rate, not on p(1−p), because a p(1−p) criterion scores `squash_range` (the most informative task in
the current suite, per-task information 0.667 against 0.024–0.12 for everything else) at zero and
throws it away. Confirm the survivors on fresh trials, since screening precision on opus was
measured at zero. The six that do not ship are not wasted: they are the reserve when a shipped task
saturates.

**Amendment 2 — at least six of the ten must compose five or more dependent operations.** This is
the substantive change. §4.0's hole F is where the ceiling lives, and the N1–N10 sketches are
mostly two-to-three-step, one-capability-per-task designs that do not touch it. Adding capability
coverage to a suite of short tasks produces a broader suite with the same ceiling. Concretely, draw
those six from the survey's Tier 3: 3.1 (working copy → reviewable stack), 3.2 (mid-stack bug fix),
3.3 (absorb review feedback), 3.5 (resolve a propagated conflict once), 3.6 (recover from your own
mistake), 3.7 (messy history → mergeable), 3.10 (extract a commit into its own branch). Budget for
Tier 3 trials costing **2–3× the current suite mean** — the showcase five already cost haiku 1.94×,
so sizing off the suite mean underestimates by roughly half.

*Updated at the retarget, and it makes amendment 2 easier to satisfy.* Tier 3 is now **15 themes,
8 of them carrying an execution warrant** — fixture stood up on the 0.44 binary, claimed solve run
to the claimed end state. **Prefer warranted themes when drawing the six.** The base rate says why:
of the sixteen themes executed across all tiers, **six needed correction and three would have
shipped broken**. A warranted theme is materially closer to shippable under R7, and for an
unwarranted one, executing the fixture is the *first* authoring step rather than a later check.
The 0.44-native Tier 3 additions are 3.11 (`jj run` over a stack), 3.12 (preview a destructive edit
with `op integrate`), 3.13 (bisect by hand with a read-only sweep) and 3.14 (absorb only half a
working copy); the survey recommends **3.11, 3.14 and 4.9** first, on the strength of having been
executed exactly as designed *and* having a measured opposite end state for the naive route — which
is precisely the R4 property this document asks of every task.

**Amendment 3 — the tier row "Query, config, immutability" loses N10 and the five saturated keeps
are provisional.** N10 does not ship as written (§4). Its slot goes to a Tier 3 theme. Separately,
five of the 14 kept — `absorb_changes`, `undo_mistaken_rebase`, `operation_recovery`,
`git_fetch_remote`, `workspace_add` — were **not** among the nine that separated; they are held for
capability coverage alone, which means by the survey's finding they contribute exactly zero to any
paired comparison, the same as the seven this document already demotes to a smoke tier. The
distinction that justifies keeping them is coverage, not power, and it is temporary: four of the
five have a deeper replacement on the survey's menu (3.3 for absorb, 3.6 for op-log recovery, 4.1
and 4.4 for fetch-and-reconcile). Only `workspace_add` has none, because the menu has no workspace
theme at all. **They leave when their replacements land and screen well, and not before.**

*Corrected against a container measurement.* A prior revision made `workspace_update_stale` a sixth
question mark here, on the theory that a third of its scored credit rode on an English assertion and
that part of its separation might therefore be a grader artifact. That is withdrawn (R2). None of
its scored credit turns on jj's prose: the stderr grep at `test_final_state.py:89` is redundant
behind the exit-code assertion at `:88`, and the `Activate config` check at `:117` grades
agent-authored text the instruction mandates. The task separated, it is anchored, and the untouched
image scores 0 against a genuine solve's 1. It is a full keep, not a provisional one — delete `:89`
as hygiene and leave it in the sweep.

*One place the survey was wrong — now resolved from both ends, and recorded because the resolution
is itself a fixture recipe.* The survey used to list a stale working copy as **NOT REPRODUCED**
against the binary and marked the staleness error text `[unverified]`, on the strength of one probe
that mutated the default workspace's working-copy commit from a second workspace. That claim
survived unchanged through `dac8118b`, so this document carried the correction by hand. **At
`3ad91698` the survey reproduces staleness itself**, by a different and 0.44-only route:
`jj op integrate` of an operation that rewrote `@` leaves the working copy stale, and recovering
with `jj workspace update-stale` then produces a **divergent change** — worth knowing before any
new workspace fixture is built on that route. Our correction below stands unchanged and is still
the cheaper recipe: staleness reproduces **deterministically** on 0.38.0 in this repo's own fixture.
***[0.38-only — re-check]*** for the *route*: `workspace_update_stale`'s bootstrap has not been
re-run on 0.44, and it is one of the 58 that must be, though the byte-identical floor result above
is strong evidence it behaves the same. The error text itself is 0.44-verified — it is the string
the survey's own `op integrate` reproduction printed.
`workspace_update_stale`'s bootstrap produces it at `environment/Dockerfile:49` by running
`jj rebase -r default@ -d @` **from the second workspace**, and `jj st` in the project then exits 1
with, verbatim on 0.38.0:

```
Error: The working copy is stale (not updated since operation <id>).
Hint: Run `jj workspace update-stale` to update it.
```

All of that goes to stderr (as does the docs link jj prints after it); stdout is empty.
`bootstrap/test_initial_state.py:20-23` asserts exactly
this and passes as part of the image build. The survey's probe evidently used a different mutation
or read `jj st` from the wrong workspace; the correct statement is that the route is
`jj rebase -r <workspace>@`, not that staleness cannot be reproduced, and the error text is
verified rather than `[unverified]`. Note that this also settles the verifier question rather than
leaving it open: because a stale working copy exits non-zero, the exit-code assertion at
`test_final_state.py:88` is the discriminator and the stderr grep on the line below it is dead
weight to be deleted, not a prose dependency to be engineered around (R2, corrected).

Net effect on the headline: **24 shipping tasks, 14 kept and 10 new, drawn from ~16 authored** —
and of the 14, five carry an explicit expiry condition (`workspace_update_stale` no longer among
them — see the correction above).

**What it costs.** *Revised: sixteen* new bootstraps, verifiers, floor files, a measured no-agent
run each and — per R7 — at least one genuine solve executed against the pinned binary (**0.44**,
and the re-pin must therefore land before authoring starts — prerequisite 4) before the
verifier is written, of which ten ship; six of the sixteen are Tier 3 fixtures, which are the
expensive ones on every one of those lines. The 24 cuts and 7 merges are deletions. Prerequisites,
all precedented in-tree:

1. The mechanical `@`-relaxation on the ten incidental pins, reusing
   `restore_interactive:199-201`'s `({handover}) & ::@` pattern. This is the single
   highest-leverage method-neutrality change available and it is not a judgment call.
2. `scripts/lint_tasks.py:102` requires every `instruction.md` to carry `## Requirements` and
   `## Background`. The exemption at `:239-247` covers `_terse` arms only, so a *base* task
   written in a user's voice fails the lint today. The rule has to change with the prompts, or
   the format keeps two token headings and re-invites the spec voice.
3. *Added during reconciliation:* an `anchor_exemptions.json` decision for every new task whose
   asked-for work legitimately removes a change id. On the current menu that is N8/themes 2.7 and
   4.3 (clear or abandon a divergent side), theme 4.8 (withdraw an experiment) and — added at
   `dac8118b` — theme 3.6, whose solve is `jj op revert` and whose op-recovery route is on the
   id-dropping list; the survey says measure it rather than assume. The general list of
   id-dropping operations is `jj abandon`, `jj squash --from B --into A`,
   `jj new`/`edit`/`prev`/`next` off an empty undescribed `@`, `jj workspace forget` and
   `jj op restore` — ***[0.38-only — re-check]***: that list was measured on the old pin and has
   **not** been re-measured on 0.44, so treat it as the set to check rather than the answer. Two of
   the 0.44-native themes join the candidate list: 3.12 abandons a commit, and 3.11/3.13 rewrite
   whole stacks with `jj run` (change ids measured preserved, so probably safe — but *probably* is
   what this prerequisite exists to forbid). The diagnostic is unchanged and is worth writing on the
   wall: `ANCHOR-CHANGE-ID-MISSING` **alone**, with the handover op still present, is a missed
   exemption; `MISSING` **plus `ANCHOR-HANDOVER-OP-GONE`** is a rebuild, not an exemption problem
   (see prerequisite 4's false alarm). A green pre-sweep pass **cannot** detect a missing exemption, because the
   untouched image never does the work that breaks the assertion — only a correct solve reveals it,
   and one absent file already made `git_import` unpassable in all 11 arms of a sweep, control
   included. This is the same structural blind spot R7 is written against, and the R7 solve is
   where the measurement gets taken.
4. **The pin — SETTLED. The target is jj 0.44.0.** *This prerequisite recorded an open question
   through `dac8118b`; it is now closed, and the rest of this document has been brought into line
   with the answer.* Hugh decided it: *"I assumed that we were aiming for 0.38.0 because that was
   the latest. Absolutely retarget to 0.44.0."* He also disposed of the one standing objection —
   comparability with everything measured on 0.38 — as *"a bad argument; in some sense we haven't
   yet measured even once the thing we actually care about."* The re-baseline is a real cost and it
   is accepted; it is not a reason to weigh.

   **What the earlier revisions got wrong, and what replaced it.** At `dac8118b` the removal list
   (`--allow-new`, `jj op undo`, `git_head()`, `git_refs()`, `diff_contains()`,
   `ui.revsets-use-glob-by-default`) was labelled `[unverified]` — read from the later releases'
   docs, with no 0.42+ binary run — and this document said "treat it as a reason to re-pin *and
   check*". All six have now been checked on the binary — and the list itself was wrong about one
   of them: `diff_contains()` **survives, still deprecated**. The full executed removal list is in
   §4.0.2 #6. Three of the removals kill *live measurement bugs*, which is the strongest positive
   argument for the retarget: `jj op undo`, `--allow-new` and `--reset-author` are
   deprecated-but-functional on 0.38, so an agent typing a stale idiom silently succeeds and the
   suite scores it **correct** today.

   **What the re-pin was measured to cost — all 58 task directories, not a sample.** Every task was
   re-pinned in a scratch tree and every image rebuilt from scratch on 0.44:

   | gate, run against 0.44 images built from scratch | result |
   |---|---|
   | `scripts/lint_tasks.py` | **58/58 pass**, pinned version reported as `v0.44.0` |
   | `scripts/bootstrap_anchor.py --write` | **58/58** anchors written |
   | `scripts/bootstrap_anchor.py --verify-untouched` (real `test.sh`, real image, no agent) | **58/58: reward 0, anchor holds** |
   | `scripts/vacuity_floor.py --write`, diffed against the committed 0.38 baseline | **0 of 58 changed — every floor byte-identical** |

   The floor result is the strongest single piece of evidence available, and it is worth being
   explicit about why: a vacuity floor is exactly the set of assertions that hold on an untouched
   bootstrap, so if *any* verifier's behaviour had shifted under 0.44 — a template rendering
   differently, a revset matching differently, an output format moving — that task's floor would
   have moved. None moved, for any of the 58. Reference solves were also run for the five showcase
   tasks: **four of five score 1.0**, and the fifth (`rebase_branch`) scored **0.5 on 0.44 and
   0.500000 on 0.38 with the same script** — a bad solve script, identical on both versions, not a
   regression.

   **Where the pin actually lives — 58 load-bearing lines and nothing else.** 152 lines in the repo
   mention `0.38`; only **58 are functional**: the jj release-tarball URL in each
   `tasks/<task>/environment/Dockerfile`, one per task, identical string, at a *varying* line
   number — so match on the string, never on the line. `scripts/lint_tasks.py` **hardcodes no
   version at all** (`check_jj_versions_agree()` is a pure consensus check that fails the minority,
   whatever the majority is), and **CI names none**. No `task.toml` mentions a version. The rest is
   prose: 58 identical `jj 0.38.0:` docstrings in `tests/anchor.py` (all-or-nothing, because the
   lint requires that file byte-identical across all 58), six Dockerfile comments and ten comment
   blocks recording measurements. A complete re-pin is one `sed` plus three script runs, with zero
   linter, CI or `task.toml` edits.

   **Two operational constraints that change the order of work in this section.** Both were
   measured, not argued, and whoever executes the migration needs them before they start:

   - **A partial re-pin is impossible.** A mixed tree fails the lint on **two independent checks**:
     `check_jj_versions_agree()` fails every minority-pinned task, *and* `check_variant_identity()`
     fails each `_terse` arm whose `environment/Dockerfile` is no longer byte-identical to its
     base's. Verified by running the linter on a 5-on-0.44 / 53-on-0.38 tree. So "re-pin only the
     survivors" is expressible **only** as *cut first, then re-pin everything that remains, in one
     commit*. No other ordering avoids a mixed-pin state, and re-pinning a task you are about to
     delete is wasted work either way. **This is the sequencing constraint for the whole §3 cut
     list.**
   - **The first 0.44 run will report `BOOTSTRAP_ANCHOR_VIOLATION` on every task, and it is not a
     0.44 bug.** It is a rebuild artifact: jj change ids are minted randomly at commit creation, so
     *any* genuine image rebuild produces a new set and invalidates `bootstrap_anchor.json`, which
     pins those ids plus the handover operation id. The control experiment settles it — a
     `docker build --no-cache` of the **unmodified 0.38** image fails **identically**, same codes,
     same count. The fix is the already-automated step: run `bootstrap_anchor.py --write` *before*
     `--verify-untouched` and it never appears. This is the finding most likely to cause a false
     alarm mid-migration and to get the retarget blamed for breaking the suite.

   **The order of work, then:**

   1. Land the §3 cuts and folds — 26 cut plus 6 merge sources, and the `_terse` arm of any task
      that goes. As it happens all five arms (`rebase_branch`, `restore_interactive`,
      `split_commit_interactive`, `squash_range`, `track_untracked_file`) belong to *kept* tasks, so
      none is orphaned: the tree goes from **58 directories to 26** — 21 keeps plus their 5 arms.
      Re-check that against the final cut list before running it, because an orphaned arm fails
      `check_variant_identity()` and an orphaned base fails nothing until the sweep.
   2. Re-pin every survivor in one commit:
      ```
      find tasks -name Dockerfile -exec sed -i 's|v0.38.0/jj-v0.38.0|v0.44.0/jj-v0.44.0|g' {} +
      python3 scripts/bootstrap_anchor.py --write --jobs 4
      python3 scripts/vacuity_floor.py   --write
      python3 scripts/bootstrap_anchor.py --verify-untouched --jobs 4
      ```
      Also grep every surviving bootstrap for the five config keys 0.44 removed (§4.0.2 #7) — they
      are accepted in silence and nothing else will catch them.
   3. Fix the prose comments opportunistically, never as a gate. The 58× `anchor.py` docstring is
      all-or-nothing under the byte-identity lint; leaving it is the safer default.
   4. Re-baseline. This is the schedule driver, not steps 1–3.
   5. **Author every new task natively against 0.44.** This is the step the decision most affects,
      and it is the argument for re-pinning *before* authoring rather than after: the authoring cost
      of the retarget is near zero today and enormous once sixteen fixtures exist.

   **One trap this retires and one it keeps.** Retired: the version-drift question this
   prerequisite used to leave open — whether a task built on a stale-idiom trap is measuring jj
   understanding or version drift — no longer needs answering in the abstract, because the stale
   idioms now hard-error. Kept: `jj next -n 2` (§4.0.1) is **unchanged on 0.44**; `-n` is still
   `--no-edit` with the count as a positional, so the newer spelling still succeeds with different
   semantics. It remains a genuine mental-model trap rather than a drift artifact, and it is safe
   to build on at the new pin.

**What it buys.** Every task in the set either separated three model tiers or holds a capability
nothing else reaches. The ten new ones sit where git habits actively mislead — conflicts you carry
rather than resolve, recovery through the evolog, rewrites the repo refuses — which is where the
measured failures already cluster. And the sweep halves: 265 trials per model becomes 120, so the
new tasks are paid for out of the saving.

*Corrected against the binary-verified survey — one claim in that paragraph is now weaker and one
is stronger.* Weaker: "either separated or holds a capability" is doing more work than it should,
because six of the 14 kept are in the second category and the second category contributes exactly
zero to a paired comparison (amendment 3). Stronger: "where git habits actively mislead" now has a
verified catalogue behind it rather than an intuition — the silent-success family in §4.0.1, where
jj exits 0 having done nothing and the wrong agent finishes confidently. Prefer new tasks that sit
on a silent-success path over new tasks that merely cover an uncovered command; the first tests the
mental model, the second tests discoverability, and R1 says only the first is worth a slot.

**One thing this proposal does not fix.** Prompt voice is orthogonal to all of the above. The
terse arms exist to measure it and carry byte-identical verifiers, which is the right design; but
three of the five would have failed correct solves under a terse prompt before they were
de-positionalised (`split_commit_interactive` 100% of scored credit, `track_untracked_file` 100%
on the `jj describe` route, `rebase_branch` 50% on the resolve-on-top route — all from
`overspec-audit` §7.1, *inferred*, not re-measured here). Rewriting prompts in a user's voice is
safe only after R2 is applied everywhere, and the ten new tasks should be written in that voice
from the start rather than converted later.
