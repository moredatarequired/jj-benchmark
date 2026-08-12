# Suite redesign: cut to 24 tasks, ten of them new

**Recommendation.** Cut 24 of the 53 tasks outright, fold 7 into survivors, and keep 22.
Of those 22, only 14 belong in the shipping suite; the other 8 are structurally sound but
produced no separation across three model tiers. Build 10 new tasks against capabilities
nothing currently touches. **Target: 24 tasks — 14 kept, 10 new.**

*This target survived reconciliation against the binary-verified capability survey (§0), with
three amendments to how it is reached rather than to the number: author ~16 new tasks and ship the
10 that measurably discriminate; require at least six of the ten to compose five or more dependent
operations; and treat six of the 14 kept as provisional. §5.1 has the argument.*

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

---

## 0. Companion document: the capability survey

This proposal has a companion that it was **not** written against, and which has since been
reconciled into it: **`docs/task_redesign_survey.md`**, commit **`0a8aab1b`** on branch
**`claude/hearth-thread-zk1kgr`** (not on this branch — read it with
`git show 0a8aab1b:docs/task_redesign_survey.md`). Where the two documents once disagreed, this
one has been corrected; every such correction is marked in place as *corrected against the
binary-verified survey*.

**What it contains.** A 1,888-line research survey of what jj is for, written against the real
pinned `jj 0.38.0` binary rather than against documentation. Four parts matter to this proposal:

1. **A sixteen-area capability map** (its §2), each area labelled with the mental-model failure a
   git-fluent agent makes and whether the result is observable in end state.
2. **A "silent-success catalogue"** (its §3) — the cases where jj exits 0 having done nothing.
   This is the single most useful thing in it for task design; see §4.0 below.
3. **39 candidate task themes across five tiers** (its §5), each with a fixture, a one-line
   user-register prompt, an end state, and how it is graded from end state alone. **These 39 are
   the menu the "build 10 new" recommendation in §5 should be drawn from.** The N1–N10 sketches in
   §4 of this document predate the survey; they are retained as a statement of what the ten must
   *cover*, not as the shortlist, and where a survey theme covers the same ground with a verified
   fixture recipe, the survey's version wins.
4. **A corrections appendix** (its §9): 22 claims from jj's own documentation and from two
   tutorials **refuted** against the binary, plus 26 drifted. Several of them would poison a
   fixture or a verifier; the load-bearing ones are reproduced in §4.0 below.

**How to read its confidence.** Every behavioural claim in it is labelled `[verified]` (run on the
pinned binary, output quoted), `[docs-0.38]` (read from correctly-versioned docs, not executed) or
`[unverified]`. Only `[verified]` is safe to build a grader on. The survey states that a
fact-check pass over its own text was still running when it was written, so it is not
self-certified; §3 of this document's adjudication records the two places where its own tree-level
claims do not survive contact with our task files.

---

## 1. The design rules

Six rules. Each is stated as a rule, then the measurement that produced it.

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
| `workspace_update_stale` | `"stale" not in result.stderr.lower()` after `jj st` (`tests/test_final_state.py:86-90`) — jj's English, on a scored test |

*Corrected against the binary-verified survey.* The `workspace_update_stale` row is new. An
earlier draft of this document listed that task as sound on all four axes and put it in the
shipping 14; it is not. `vacuity_floor.json` reads 3 tests / 0 floor, so **all three of its tests
are scored**, and `test_no_stale_error` is an English assertion on jj's stderr. It also grades a
description substring (`test_commit_message`, `"Activate config" in result.stdout`, `:117`). The three
`assert_descends_from_the_handover` calls are properly anchored and are the reason the task is
worth repairing rather than cutting, but the English and description assertions have to go the way
`undo_mistaken_rebase`'s did. See §5 for what this does to its place in the target set.

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

### Keep — 22

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
| `workspace_update_stale` | Genuinely distinct (stale working copy); needs the `@-` positional relaxed — **and, corrected against the survey, needs `test_no_stale_error`'s English assertion and `test_commit_message`'s description grep removed too** (§1, R2). All three of its tests are scored |
| `git_fetch_remote` | Fetch + rebase onto a remote-only bookmark + push, graded by commit id, with an anti-cheat guard |
| `git_export` | `git rev-parse` compared to the resolved commit id |
| `obslog_view` | Recomputes the evolution with `jj evolog` at verification time; the answer cannot be hardcoded |
| `show_commit` | Each patch must carry the anchored commit's own id prefix, because a git diff of identical content is identical |
| `template_customize_log_output` | Renders the agent's alias and compares against a reference rendered by the verifier — quoting, config layer and authoring route agnostic |
| `undo_mistaken_rebase` | `--at-op` replay of parents by change id; `undo` / `op undo` / `op revert` / `op restore` all accepted |
| `operation_recovery` | 5 scored tests over files, tracked set, visible history and the op log |

### Merge — 7

| Task | Into | What survives, what does not |
|---|---|---|
| `bookmark_rename` | `bookmark_create_and_move` | Its change-id comparison (`:70-84`) is the only thing distinguishing rename from delete+create; it survives as an assertion in a create → move → rename lifecycle task. Its 1-test pass/fail shape does not |
| `bookmark_push` | `git_fetch_remote` | `git_fetch_remote` already requires the pushed ref to equal the commit the anchored change resolves to *at verification time*. `bookmark_push`'s describe → bookmark → push adds only the describe |
| `git_import` | `git_export` | One colocated-git task grading both directions. `git_export` survives because it compares ids; `git_import` is unanchored by design (target found by git message). Its docstring (`:1-11`) is the reference text for R3 and should move with it |
| `workspace_forget` | `workspace_add` | Add → list → forget as one graded lifecycle, every step anchored by the project's change id. `workspace_forget`'s stdout-substring assertions do not survive |
| `log_template_author` | `template_customize_log_output` | `test_output_follows_the_repository_identity` (`:142-221`) survives — it mutates `@`'s author via `JJ_USER`/`JJ_EMAIL`, re-runs the script, requires the output to follow, then `jj op restore`s. `test_script_contains_a_jj_log_command` does not |
| `concurrent_operations` | new divergence task (N8) | The structural half survives: at some recorded operation the anchored change resolved to more than one visible commit (`:141-150`). The English `"reconcile divergent operations"` assertion (`:152-155`) does not |
| `duplicate_commit` | new duplicate-a-range task (N9) | Its children-of-anchored + content-compared-at-test-time + own-diff assertions generalise to a range. Its single scored test does not |

### Cut — 24

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

Four capabilities leave with the cuts and are not picked up elsewhere: `jj bookmark delete`,
`jj workspace root`, `jj git remote add`, and `jj show`/`jj diff` piped to a file. All four are
single-flag surfaces with no wrong solve worth catching.

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
| A | **Merge commits** | Zero tasks. No `jj new A B`, no assertion anywhere on `parents.len() > 1`; `jj merge` does not exist on 0.38 |
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
member below is `[verified]` against the pinned binary:

- **Empty revsets are silent per *flag*, not per command.** `jj rebase -r <empty> -o X` →
  `Nothing changed.` at **exit 0**, while `-s`/`-b` with the same empty revset error at 1.
  `jj squash --from <empty>` → exit 0; `--into <empty>` → exit 1. `jj abandon <empty>` and
  `jj describe -r <empty> -m X` → exit 0. Combine with the string-pattern trap — a bare string in
  `description()` is a whole-string `glob:` and jj stores descriptions with a trailing newline, so
  `description("Add feature A")` matches **nothing** — and the canonical false success is
  `jj squash --from 'description("Add feature A")' --into 'description("Add base")'` printing
  `Nothing changed.` at exit 0.
- **`jj file track <ignored-path>` without `--include-ignored` exits 0 and tracks nothing.** No
  error, no warning. This is already in the suite as `track_untracked_file`, which is why that
  task is the one kept item with a measured non-zero failure rate on sonnet.
- **Pushing an untracked new bookmark.** `jj bookmark create newb && jj git push` →
  `Warning: Refusing to create new remote bookmark newb@origin` + `Nothing changed.` at **exit 0**.
  A second, distinct exit-0 path exists when nothing is in the default push revset.
- **`jj next -n 2` flips edit semantics.** On 0.38 `-n` is `--no-edit` (a boolean) and the count is
  a positional; `--amount` does not exist. So `-n 2` parses as `--no-edit` **plus** `OFFSET=2` —
  the agent gets the right offset by accident while silently flipping whether `@` lands on a new
  child or edits the target in place. That changes the graded end state.

**Make this a selection criterion for the ten.** A task whose wrong solve *errors* is testing
discoverability; a task whose wrong solve *succeeds* is testing the mental model, which is R1.
Every one of the four above is rated excellent for gradeability because the wrong end state is
trivially distinguishable from the target one.

### 4.0.2 Verified facts that constrain these fixtures and verifiers

From the survey's §9 corrections appendix — 22 documentation and tutorial claims refuted against
the binary. These six would poison a fixture or a verifier in the set proposed below, and none of
them was known when §4 was first drafted:

1. **`??` marks a CONFLICTED BOOKMARK, not divergence.** Divergence renders as `X/0` / `X/1` plus a
   `(divergent)` marker. Both tutorials get this wrong and they can appear on the same log line.
   A divergence verifier that greps `??` grades the wrong thing.
2. **A bare change-id revset ERRORS on a divergent change**, and a bare bookmark-name revset
   ERRORS on a conflicted bookmark — `Error: Change ID 'x' is divergent` / `Error: Name 'main' is
   conflicted`, both exit 1. `present(X)` does not help. Verifiers must spell `change_id(X)` and
   `bookmarks(name)`. A verifier for N8 or for a conflicted-bookmark task **can be broken by the
   exact trap it tests**. `tasks/concurrent_operations/tests/test_final_state.py:26-31` already
   gets this right and is the in-tree reference.
3. **The `all:` revset prefix is a parse error on 0.38** (`Error: Failed to parse revset: Syntax
   error`). The arity guard survives in genuinely single-revision positions, but the bulk-rebase
   idiom is spelled without a prefix, and a multi-revision revset needs none in `-s`/`-r`/`-o`.
   Do not put `all:` in a reference solution or an instruction.
4. **`jj git init` is colocated by default on 0.38** — `--colocate` is an accepted no-op. All 53
   bootstraps use plain `jj git init`, so **every existing task image is already colocated**, and
   `git` is present in every image. That is a live unintended false-pass route in tasks that never
   meant to be about git, and it is what makes the `git_import`/`git_export` merge in §3 coherent
   rather than a stretch. A task that wants a *non*-colocated repo must pass `--no-colocate`.
5. **`jj backout` does not exist** (`error: unrecognized subcommand`); only `jj revert`, and its
   destination flag is **mandatory** — a bare `jj revert -r X` is a clap error at exit 2.
6. **`--allow-new` is hidden but fully functional** on 0.38: absent from `-h` and `--help`, emits
   one deprecation warning, and **succeeds**. A verifier must not fail a solve that uses it, and it
   cannot be used as a version discriminator. The same hidden-but-functional shape holds for
   `jj op undo`, `jj git fetch --tag` and `jj tag list --tracked/--remote`.
7. **Repo config is NOT at `.jj/repo/config.toml`.** On 0.38 it lives at
   `$HOME/.config/jj/repos/<20-hex>/config.toml`, keyed by `.jj/repo/config-id`, and a hand-placed
   `.jj/repo/config.toml` is **ignored**. Any fixture that sets repo config must go through
   `jj config set --repo`, and any verifier that wants to know what an agent configured must
   *evaluate* the setting rather than read a file. N6 below already specifies evaluation; this is
   the reason it must.

One more, for the anchor rather than the fixture: `jj config set --repo <key> <value>` does not
validate key names — nonsense keys are accepted silently at exit 0. "The agent set a config key"
is never evidence the key does anything.

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
  `squash -i` / `split -i` / `commit -i` / `diffedit` print `Error: Failed to edit diff` and exit 1
  within seconds, so an agent that reaches for `-i` loses a turn, not the trial — there is nothing
  to protect the suite from. Second, every interactive route has a verified non-interactive
  substitute (`jj squash <paths>` or `--from`/`--into`, `jj split -r X <paths> -m`,
  `jj describe --stdin`, `jj resolve --tool :ours`/`:theirs`), so a verifier cannot tell the routes
  apart from end state and must not try. The salvageable ask is "move exactly one hunk, leave the
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

### 4.2 N1–N10 against the survey's 39-theme menu

*Added during reconciliation.* The ten below are a statement of coverage, not a shortlist. Where a
survey theme covers the same ground, it ships with a verified fixture recipe and a prompt already
written in a user's voice, and it wins. Survey tiers: 1 = single operation, 2 = two-to-three steps,
3 = five-plus dependent operations, 4 = collaborative / colocated, 5 = diagnosis.

| here | survey theme(s) | tier | verdict |
|---|---|---|---|
| N1 conflict propagates | 3.5 *resolve a propagated conflict once*, 2.4 *leave a conflict, build on it* | 3, 2 | Use the survey's. N1 conflates the two; they are better as one Tier 3 task, and 2.4 is a distinct and sharper Tier 2 |
| N2 merge the agent creates | 1.5 *merge with ordered parents*, 4.2 *conflicted bookmark repair* | 1, 4 | N2 is a hybrid the menu lacks — a merge the agent **creates** *and* resolves. Keep N2's shape, take 1.5's `parents.map(...)` grading |
| N3 evolog as recovery | 3.6 *recover from your own mistake*, 5.5 *which operation lost this file* | 3, 5 | Use 3.6. It is the deeper composition and the survey flags it as the tier's highest grader-artifact risk, with the mitigation (change-id replay, no string matching) |
| N4 revsets the agent writes | 5.3, 5.4, 5.6; 3.7 *messy history → mergeable* | 5, 3 | Prefer 3.7: it makes the revset the *route* to an action rather than the deliverable, which dodges the zero-tool-call confound |
| N5 filesets | 2.1 *split by path* is the nearest | 2 | No dedicated fileset theme in the menu. N5 is additive; keep it |
| N6 immutability | none dedicated (5.4 uses `immutable()` as a query only) | — | **Additive.** The survey names immutability as hole C but ships no theme for it. N6 stands, and its "evaluate the alias, don't string-match the config" design is now mandatory (§4.0.2 #7) |
| N7 op log beyond undo | 5.3 *what did the last operation do* | 5 | Same task. Use the survey's phrasing and its `--at-op` differencing rule |
| N8 divergence | 2.7 *clear a divergent change*, 4.3 *divergent change repair* | 2, 4 | Neither is new (see N8 above). If one ships, ship 4.3 — the two-actor version pairs divergence with a conflicted bookmark |
| N9 duplicate a range | none | — | **Additive.** No duplicate theme in the menu; keep it |
| N10 configured diff editor | none; superseded by 2.1 / 3.3 | 2, 3 | **Do not ship as written** — R3 violation, see above |

Two gaps run the other way, and both are this document's to fill rather than the survey's:

- **The menu has no workspace theme at all.** None of the 39 touches `jj workspace`, even though
  the survey's own capability map covers it. `workspace_add` and `workspace_update_stale` are
  therefore not replaceable from the menu, which is part of why they stay in §5.
- **The menu has no immutability theme and no duplicate theme**, per the table. N6 and N9 are the
  only routes to holes C and to `jj duplicate` respectively.

---

## 5. The target set

**24 tasks: 14 kept, 10 new.**

The second filter on the keep list is discrimination. Of the 22 tasks that survive §3, nine
separated the three models in the baseline (`abandon_commits`, `edit_commit_message`,
`rebase_branch`, `restore_interactive`, `split_commit_interactive`, `squash_range`,
`template_customize_log_output`, `track_untracked_file`, `workspace_update_stale`); five more hold
a capability nothing else covers (`absorb_changes`, `undo_mistaken_rebase`, `operation_recovery`,
`git_fetch_remote`, `workspace_add`). That is the 14.

The other eight — `bookmark_create_and_move`, `git_export`, `new_commit`, `new_insert`,
`obslog_view`, `revert_file`, `show_commit`, `status_ignored` — are structurally sound and were
5/5 on all three models. They belong in a smoke tier or nowhere. If a second ignore-surface task
is wanted, `status_ignored` is the one to bring back: its verifier is the strongest of the three.

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
sketches are exactly that kind of paper pick. Author ~16 from the survey's 39-theme menu, run one
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

**Amendment 3 — the tier row "Query, config, immutability" loses N10 and the five saturated keeps
are provisional.** N10 does not ship as written (§4). Its slot goes to a Tier 3 theme. Separately,
five of the 14 kept — `absorb_changes`, `undo_mistaken_rebase`, `operation_recovery`,
`git_fetch_remote`, `workspace_add` — were **not** among the nine that separated; they are held for
capability coverage alone, which means by the survey's finding they contribute exactly zero to any
paired comparison, the same as the eight this document already demotes to a smoke tier. The
distinction that justifies keeping them is coverage, not power, and it is temporary: four of the
five have a deeper replacement on the survey's menu (3.3 for absorb, 3.6 for op-log recovery, 4.1
and 4.4 for fetch-and-reconcile). Only `workspace_add` has none, because the menu has no workspace
theme at all. **They leave when their replacements land and screen well, and not before.**
`workspace_update_stale` is the sixth question mark and a different one: it did separate, but a
third of its scored credit rides on an English assertion (§1, R2), so part of the separation it
shows may be a grader artifact. Repair it before the screening sweep, then re-measure; if the
separation was the English, it belongs in the smoke tier too.

*One place the survey is wrong, recorded so this document does not propagate it.* The survey lists
a stale working copy as **NOT REPRODUCED** against the binary and marks the staleness error text
`[unverified]`, on the strength of one probe that mutated the default workspace's working-copy
commit from a second workspace. Our tree contradicts that: `workspace_update_stale`'s fixture
produces a stale working copy at `environment/Dockerfile:45-49` by running `jj rebase -r default@
-d @` **from the second workspace**, and `bootstrap/test_initial_state.py:20-23` asserts that
`jj st` in the project then exits non-zero with `stale` in its output. That bootstrap test is part
of the image build. The survey's probe evidently used a different mutation or read `jj st` from the
wrong workspace; the correct statement is that the route is `jj rebase -r <workspace>@`, not that
staleness cannot be reproduced. This does not rescue the English assertion in the *verifier* —
grading jj's stderr text is wrong for the reason `undo_mistaken_rebase` is the reference case —
but it does mean the task's premise is sound and the task is worth repairing rather than cutting.

Net effect on the headline: **24 shipping tasks, 14 kept and 10 new, drawn from ~16 authored** —
and of the 14, five (six counting `workspace_update_stale`) carry an explicit expiry condition.

**What it costs.** *Revised: sixteen* new bootstraps, verifiers, floor files and a measured
no-agent run each, of which ten ship — and six of the sixteen are Tier 3 fixtures, which are the
expensive ones. The 24 cuts and 7 merges are deletions. Prerequisites, all precedented in-tree:

1. The mechanical `@`-relaxation on the ten incidental pins, reusing
   `restore_interactive:199-201`'s `({handover}) & ::@` pattern. This is the single
   highest-leverage method-neutrality change available and it is not a judgment call.
2. `scripts/lint_tasks.py:102` requires every `instruction.md` to carry `## Requirements` and
   `## Background`. The exemption at `:239-247` covers `_terse` arms only, so a *base* task
   written in a user's voice fails the lint today. The rule has to change with the prompts, or
   the format keeps two token headings and re-invites the spec voice.
3. *Added during reconciliation:* an `anchor_exemptions.json` decision for every new task whose
   asked-for work legitimately removes a change id. On the current menu that is N8/theme 4.3
   (abandon a divergent side) and theme 4.8 (withdraw an experiment), and the general list of
   id-dropping operations measured on 0.38 is `jj abandon`, `jj squash --from B --into A`,
   `jj new`/`edit`/`prev`/`next` off an empty undescribed `@`, `jj workspace forget` and
   `jj op restore`. A green pre-sweep pass **cannot** detect a missing exemption, because the
   untouched image never does the work that breaks the assertion — only a correct solve reveals it,
   and one absent file already made `git_import` unpassable in all 11 arms of a sweep, control
   included.
4. *Added during reconciliation:* a decision on the pin. The survey argues for re-pinning off
   0.38.0 (six releases stale) before authoring, on the grounds that the authoring cost is near
   zero now and enormous once sixteen fixtures exist, and that several things it documents as
   hidden-but-functional on 0.38 — `--allow-new`, `jj op undo`, `git_head()`, `git_refs()`,
   `diff_contains()`, `ui.revsets-use-glob-by-default` — are **removed** by 0.42/0.43. Its sharpest
   case is `jj next -n 2` (§4.0.1): the newer spelling *succeeds with different semantics* on 0.38,
   so a task built on it discriminates on version drift rather than on jj understanding. This
   proposal takes no position on re-pinning, but the choice has to be made **before** authoring,
   and if we stay at 0.38 we should decide explicitly whether version-drift traps are features of
   the suite or noise in it. Note that comparability is not the deciding factor: the pending
   `WORKDIR` and grading relaxation is expected to saturate `squash_range` and void the existing
   power figures regardless, so nothing new is comparable to the 795-trial baseline either way.

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
