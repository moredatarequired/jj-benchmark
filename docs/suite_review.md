# The 24-task jj suite: prompts and grading

Every task in the suite: the exact prompt handed to the agent, and precisely how the run is scored. **14 shipping** · **10 proposed, none built** · **7 demoted**. Generated from `docs/suite_review_data_built.json` and `docs/suite_review_data_proposed.json` by `docs/build_suite_review.py`, which writes this file and `docs/suite_review.html` in the same run.

## Contents

**[Shipping now — 14 built](#shipping-now--14-built)**

- [abandon_commits](#abandon_commits) — rewrite pending
- [edit_commit_message](#edit_commit_message) — rewrite pending
- [rebase_branch](#rebase_branch) — prompt rewritten
- [restore_interactive](#restore_interactive) — prompt rewritten
- [split_commit_interactive](#split_commit_interactive) — prompt rewritten
- [squash_range](#squash_range) — prompt rewritten
- [template_customize_log_output](#template_customize_log_output) — rewrite pending
- [track_untracked_file](#track_untracked_file) — prompt rewritten
- [workspace_update_stale](#workspace_update_stale) — rewrite pending
- [absorb_changes](#absorb_changes) — rewrite pending, provisional
- [undo_mistaken_rebase](#undo_mistaken_rebase) — rewrite pending, provisional
- [operation_recovery](#operation_recovery) — rewrite pending, provisional
- [git_fetch_remote](#git_fetch_remote) — rewrite pending, provisional
- [workspace_add](#workspace_add) — rewrite pending, provisional

**[Proposed — 10, none built](#proposed--10-none-built)**

- [N1 — a conflict that propagates instead of being resolved on the spot](#n1--a-conflict-that-propagates-instead-of-being-resolved-on-the-spot) — not built
- [N2 — a merge commit the agent creates](#n2--a-merge-commit-the-agent-creates) — not built
- [N3 — evolog as recovery](#n3--evolog-as-recovery) — not built
- [N4 — revsets the agent writes](#n4--revsets-the-agent-writes) — not built
- [N5 — filesets](#n5--filesets) — not built
- [N6 — immutable revsets](#n6--immutable-revsets) — not built
- [N7 — the operation-log surface beyond undo](#n7--the-operation-log-surface-beyond-undo) — not built
- [N8 — divergence as a thing to work with](#n8--divergence-as-a-thing-to-work-with) — not built
- [N9 — duplicate a range](#n9--duplicate-a-range) — not built
- [N10 — a configured non-interactive diff editor (STRUCK as written)](#n10--a-configured-non-interactive-diff-editor-struck-as-written) — struck, slot unassigned, not built

**[Demoted — 7 kept but not shipping](#demoted--7-kept-but-not-shipping)**

- [bookmark_create_and_move](#bookmark_create_and_move) — rewrite pending
- [new_commit](#new_commit) — rewrite pending
- [new_insert](#new_insert) — rewrite pending
- [obslog_view](#obslog_view) — rewrite pending
- [revert_file](#revert_file) — rewrite pending
- [show_commit](#show_commit) — rewrite pending
- [status_ignored](#status_ignored) — rewrite pending

---

## Shipping now — 14 built

Fourteen tasks that exist, run and score today. Everything below is read off the built task: the prompt is the file the agent is handed, and the grading is what the verifier actually asserts.

### abandon_commits

`built` · `prompt still spec-style, rewrite pending` · `separated models: yes`

**The prompt, verbatim — `instruction.md`.** Still spec-style — rewrite pending.

```markdown
# Abandoning Commits in Jujutsu

## Background
You are working in a `jj` repository and have created a stack of commits. You've realized that some of the intermediate commits are false starts and need to be removed from the history. Removing a commit from the middle of a stack leaves its descendants in place, rebased onto the removed commit's parent.

## Repository State
- `commit A`: adds `a.txt`. Bookmark: `feature-a`.
- `commit B`: adds `b.txt`. Bookmark: `experiment`.
- `commit C`: adds `c.txt`. Bookmark: `draft`.
- `commit D`: adds `d.txt`. Working copy is here.

## Requirements
1. Abandon the commit pointed to by the `experiment` bookmark, but **retain** the bookmark: afterwards it must still exist and point at the abandoned commit's parent.
2. Abandon the commit pointed to by the `draft` bookmark. Do **not** retain this bookmark (it should be deleted).
3. Set the description of the current working-copy commit to `cleanup complete`.

## Constraints
- Project path: `/home/user/myproject`
- Use only `jj` commands.
```

**How success is graded.** Four assertions, all against repository state. On disk: a.txt and d.txt present, b.txt and c.txt gone; and the anchored handover working-copy commit must track exactly ['a.txt', 'd.txt'], so the two abandons really took their files with them. The `experiment` bookmark must resolve to exactly the change id the bootstrap gave `commit A`, and the `draft` bookmark must no longer resolve at all while the bootstrap's `commit C` change is no longer visible anywhere. Commits are identified by anchored change id (`change_id_or_fallback`) and by the anchor's per-workspace working-copy key (`working_copy_or_fallback`), never by position — except that the last test additionally requires `@` to still BE the anchored handover change. No assertion reads jj's English: the only text read is the working copy's description, which is substring-checked for 'cleanup complete', text the instruction itself mandates the agent write. The fabrication guard is the shared session-scoped anchor fixture (every bootstrap change id still visible and non-divergent, and the handover operation id still in the op log), relaxed by an anchor_exemptions.json naming `commit B` and `commit C` as commits the asked-for work removes.

**Scoring.** 4 tests total / 0 floored / 4 scored · anchored: **yes** · anchor exemptions: **yes**

4 tests, 0 floored, 4 scored. Partial credit is k/4 for k scored tests passed, with a hard cap of 0.75 whenever pytest exits non-zero — a full 1.0 requires every test to pass. A no-agent run on the untouched image scores 0: nothing is floored, so its numerator is empty by construction.

**Known holes.** test_working_copy_description still requires `@` to be exactly the handover change, so a correct solve that ends with a fresh `jj new` on top loses a quarter of the reward.

**Repair queued.** §3 keep table: the incidental `@` pin at tests/test_final_state.py:186-190 needs the mechanical relaxation (prerequisite 1).

[↑ contents](#contents)

### edit_commit_message

`built` · `prompt still spec-style, rewrite pending` · `separated models: yes`

**The prompt, verbatim — `instruction.md`.** Still spec-style — rewrite pending.

```markdown
# Edit Commit Message in Jujutsu

## Background
Jujutsu (`jj`) is a modern VCS that makes it easy to modify the history of a repository. It allows editing the commit message (description) of any commit in the history without checking it out, and automatically rebases descendants.

## Requirements
- Find the commit with the description "Add file B" in the repository history.
- Change its description to "Add second file".
- Create a new commit on top of the current working copy with the description "Add file D" and add a new file `d.txt` containing the text "d".

## Constraints
- Project path: /home/user/repo
```

**How success is graded.** Three scored assertions. The renamed commit is the one the bootstrap described 'Add file B', resolved by its anchored change id, and its description must contain 'Add second file'. The new commit has no anchored id of its own — the agent creates it — so it is anchored by relation: `@`'s parent change ids must be exactly the anchored 'Add file C' change, and only then is `@`'s description required to contain 'Add file D'. The third test repeats that parent claim and then reads d.txt off disk, requiring the content 'd'. So commits are identified by anchored change id and by parent relation to an anchored commit; `@` itself is used positionally as 'the new commit', which is the one position the task fixes. Nothing reads jj's English output; the only substrings matched are the descriptions the instruction tells the agent to write. The guard is the shared anchor fixture with no exemption file — every bootstrap commit must still resolve — plus the anchored-parent claim, which the docstring records as what killed a measured `jj new -r 'root()'` rebuild that had scored 1.0.

**Scoring.** 4 tests total / 1 floored / 3 scored · anchored: **yes** · anchor exemptions: **none**

4 tests, 1 floored (test_commit_c_still_exists, which resolves by `files("c.txt")` and is unanchored), 3 scored. Partial credit is 0, 0.333333 or 0.666667; 1.0 requires all four to pass. A no-agent run scores 0 — the floored test passes but is excluded from both sides of the fraction.

*Floored — must pass, earns nothing:*

- `test_final_state.py::test_commit_c_still_exists`

**Known holes.** `@` must literally be the new 'Add file D' commit, so a correct solve that finishes with an extra `jj new` fails two of the three scored tests.

**Repair queued.** §3 keep table: the `@` pin is incidental and is one of the ten to relax under prerequisite 1.

[↑ contents](#contents)

### rebase_branch

`built` · `prompt rewritten` · `separated models: yes`

**The prompt — two versions, verbatim.**

*Current — `instruction.md`, spec-style:*

````markdown
# Rebase a Bookmark and Resolve Conflicts in jj

## Background
Jujutsu (`jj`) is a Git-compatible VCS that treats the working copy as a permanent commit and has first-class conflict management. In this task, you will rebase a bookmark (branch) onto `main` and resolve a conflict.

## Requirements
- You have an initialized `jj` repository at `/home/user/repo`.
- The `main` bookmark has been updated with a new commit modifying `data.txt`.
- You have a bookmark `feature-branch` with 2 commits. The first commit modifies `data.txt` in a way that conflicts with `main`.
- Rebase `feature-branch` onto `main`.
- Resolve the conflict in `data.txt` by keeping both lines (the line from `main` followed by the line from `feature-branch`), so that the final file contains exactly:
  ```
  Line from main
  Line from feature
  ```
- The `feature-branch` bookmark must point to the head of the rebased commits.

## Constraints
- Project path: `/home/user/repo`
- Do not create any new bookmarks.
- The final `data.txt` in the `feature-branch` must have exactly the two lines specified.
````

*Rewritten — one line, user voice (arm `rebase_branch_terse`):*

```text
rebase feature-branch onto main, resolving the conflict in the commit that has it: both lines, main's first
```

**How success is graded.** The rebase is graded as topology, not as a count. `main` must be an ancestor of `feature-branch`; `main..feature-branch` must hold exactly two commits; `feature-branch` must be the head of them; the root of that stack must have `main` as its only parent and `feature-branch` must have the stack root as its only parent, i.e. a linear chain planted directly on main. When the anchor is available it then requires that `main` is the bootstrap's 'main commit' change and that the two stack commits are the bootstrap's 'feature commit 2' and 'feature commit 1', in that order. The conflict resolution is read with `jj file show data.txt` at the anchored 'feature commit 2' and compared as a list of lines against ['Line from main', 'Line from feature'], deliberately line-wise rather than byte-wise so a missing trailing newline does not fail a correct answer. Commits are identified by anchored change id plus bookmarks and revsets — no `@` position anywhere. No English is read: conflict-freedom comes from the `conflict` boolean template keyword rather than from `jj resolve --list`'s prose. The guard is the shared anchor fixture plus an anchor_exemptions.json blessing the disappearance of the bootstrap's empty `@`, which jj auto-abandons when the agent runs `jj edit` on the conflicted commit.

**Scoring.** 3 tests total / 1 floored / 2 scored · anchored: **yes** · anchor exemptions: **yes**

3 tests, 1 floored (test_no_unresolved_conflicts), 2 scored. So the reward is effectively 0, 0.5 or 1.0, and 1.0 additionally requires the floored conflict test to pass. A no-agent run scores 0.

*Floored — must pass, earns nothing:*

- `test_final_state.py::test_no_unresolved_conflicts`

**Known holes.** The identity half of the topology test is wrapped in `if all(wanted.values())`, so with no anchor file it silently drops to bookmark-and-ancestry only; and the conflict-freedom check is floored, so it earns nothing.

**Repair queued.** None — no repair queued against this task.

[↑ contents](#contents)

### restore_interactive

`built` · `prompt rewritten` · `separated models: yes`

**The prompt — two versions, verbatim.**

*Current — `instruction.md`, spec-style:*

```markdown
# Recover a File Dropped by a Commit in the Middle of a Stack

## Background
In Jujutsu (`jj`), a commit is not a sealed record: any commit in the history can be
rewritten in place after the fact, and its descendants are carried along
automatically. That means a mistake buried in the middle of a stack of commits can
be corrected where it happened, so the history ends up in the shape it should have
had, rather than being patched over by a later commit that puts the mistake right.

## Requirements
The repository at `/home/user/myproject` has four commits above the root, oldest
first:

1. `Initial commit` — adds `main.py`, `legacy.py` and `settings.toml`.
2. `remove legacy module` — deletes `legacy.py` and rewrites `main.py` so it no
   longer uses that module. It also deletes `settings.toml`, and that part was a
   mistake: `settings.toml` is still needed.
3. `add logging` — rewrites `main.py` again.
4. The working copy, which has no description and adds `notes.txt`.

Bring the repository to this end state:

- The `remove legacy module` commit must no longer delete `settings.toml`. That
  commit must contain `settings.toml` with exactly the content it has in
  `Initial commit`.
- Everything else that commit does must be untouched: it must still delete
  `legacy.py`, and its change to `main.py` must be exactly as it is now.
- `settings.toml` must also be present, with that same content, in the
  `add logging` commit and in the working copy — including on disk at
  `/home/user/myproject/settings.toml`.
- `legacy.py` must stay absent from `remove legacy module` onwards.
- `add logging` must still record only its own change to `main.py`.
- The only change in the working copy relative to its parent must still be the
  addition of `notes.txt`.
- The history must still consist of exactly those four commits, in that order. Do
  not add, remove or reorder commits, and do not change any description.

## Constraints
- Project path: `/home/user/myproject`
- The repository must remain a valid `jj` repository.
```

*Rewritten — one line, user voice (arm `restore_interactive_terse`):*

```text
the commit that removed the legacy module also deleted a config file we need — restore it there, not on top
```

**How success is graded.** Six scored assertions, every one about a commit's tree or its own diff, compared byte-for-byte against the bootstrap's literal file contents. The commit the bootstrap described 'remove legacy module' must now contain settings.toml with the original bytes, must no longer list settings.toml among the paths it changes, and must still change exactly {legacy.py, main.py} with main.py at its original post-cleanup content; 'Initial commit' must be byte-identical to the bootstrap's; 'add logging' must still change only main.py and still carry the right settings.toml and no legacy.py; the handover working copy must change only notes.txt and carry the right trees; and settings.toml must be back on disk with the original bytes. The three named commits are identified by anchored change id and the working copy by the anchor's per-workspace key; the only positional element is a deliberately relaxed ancestry check — the handover change must be `@` or an ancestor of it — which replaced an `@ == handover` equality that had been failing correct solves that ran `jj new`. Nothing reads jj prose; `jj diff --name-only` and templated `jj log` output are parsed as data. The guard is the shared anchor fixture (no exemption file, so no bootstrap commit may disappear) plus resolving every graded commit through the anchor, which the docstring records as what killed a fabricated four-commit chain that had scored 6 of 6.

**Scoring.** 7 tests total / 1 floored / 6 scored · anchored: **yes** · anchor exemptions: **none**

7 tests, 1 floored (test_history_shape), 6 scored. Partial credit is k/6, capped at 5/6 = 0.833333 whenever anything fails — the finest-grained reward in the suite. A no-agent run scores 0.

*Floored — must pass, earns nothing:*

- `test_final_state.py::test_history_shape`

**Known holes.** None recorded.

**Repair queued.** §3 'Where the better task has the weaker prompt': keep the verifier, rewrite the prompt — it is the most verifier-shaped prompt in the repo, enumerating the end state as seven bullets that map one-to-one onto assertions.

[↑ contents](#contents)

### split_commit_interactive

`built` · `prompt rewritten` · `separated models: yes`

**The prompt — two versions, verbatim.**

*Current — `instruction.md`, spec-style:*

```markdown
# Split a Commit in Jujutsu

## Background
You are working on a project using `jj` (Jujutsu). You have a single commit that introduces two features at once, but you realize they should be separated into two distinct commits for a cleaner history.

## Requirements
- The repository is located at `/home/user/myproject`.
- The parent of the current working copy (`@-`) contains two files: `feature_a.py` and `feature_b.py`, and has the description "Add feature A and feature B".
- You must split this commit into two separate commits.
- The first commit (older) must contain ONLY `feature_a.py` and have the description exactly "Add feature A".
- The second commit (newer, child of the first) must contain ONLY `feature_b.py` and have the description exactly "Add feature B".
- The current working copy (`@`) should remain empty and be a child of the "Add feature B" commit.

## Constraints
- Project path: `/home/user/myproject`
- Use only `jj` commands.
```

*Rewritten — one line, user voice (arm `split_commit_interactive_terse`):*

```text
split the last commit in two, "Add feature A" then "Add feature B"
```

**How success is graded.** The two halves are located from the bootstrap's own commit rather than by position. The anchored change id of 'Add feature A and feature B' is resolved; if that change still has a non-root parent the split gave the id to the newer half and the older half is that parent, otherwise the anchored commit is the older half and the newer half is its single child. Each half must resolve to exactly one commit, and the anchored commit must be one of the two. The older half's description must equal 'Add feature A' exactly and its `jj diff -s` output must mention feature_a.py and not feature_b.py; the newer half is the mirror image. Both scored tests re-run that resolution, so a fabrication cannot collect half the reward. Nothing is identified by position — the old `@`-position test was deleted after it scored a textbook `jj edit` + `jj split -i` solve 0.5 — and nothing reads jj's English; the only substring matching is on filenames in `jj diff -s` output. The guard is the shared anchor fixture plus an anchor_exemptions.json blessing the empty `@` that jj auto-abandons on the interactive route.

**Scoring.** 2 tests total / 0 floored / 2 scored · anchored: **yes** · anchor exemptions: **yes**

2 tests, 0 floored, 2 scored. The reward is 0, 0.5 or 1.0 — one grader artifact halves the task. A no-agent run scores 0.

**Known holes.** Only which filenames each half touches is graded, never file contents, and `jj diff -s` is substring-matched — so a split that moves the right paths with the wrong bytes inside them still passes.

**Repair queued.** None — no repair queued against this task.

[↑ contents](#contents)

### squash_range

`built` · `prompt rewritten` · `separated models: yes`

**The prompt — two versions, verbatim.**

*Current — `instruction.md`, spec-style:*

```markdown
# Squash a Range of Commits

## Background
In Jujutsu (`jj`), the changes recorded in several commits can be combined into a single commit, after which the source commits no longer appear in the log. Revsets let one operation name a whole range of source commits rather than one at a time.

## Requirements
- You have a `jj` repository at `/home/user/myproject`.
- It contains a commit with the description `feat: initial structure`.
- It has two child commits with descriptions `fix: syntax error` and `fix: logic error`.
- There is a descendant commit `feat: add more stuff`.
- Combine the two `fix` commits into the `feat: initial structure` commit. Afterwards exactly four commits must remain in the log (the root commit, `initial commit`, `feat: initial structure`, and `feat: add more stuff`), and `feat: initial structure` must carry both fixes.

## Constraints
- Project path: `/home/user/myproject`
```

*Rewritten — one line, user voice (arm `squash_range_terse`):*

```text
merge the two fix commits into their parent (leave the current commit alone)
```

**How success is graded.** Five scored assertions plus an anti-fabrication replay. The bootstrap's 'initial commit', 'feat: initial structure' and 'feat: add more stuff' changes must still be visible, and any other visible commit must render `empty == true` — a scratch commit is free, a commit still carrying content is not. The two fix changes must be gone, checked by anchored change id rather than by searching the log for their text (squashing folds their descriptions into the target, so a text search would flag a correct solve). The target's structure.txt must be exactly 'logic fixed\\n', and parents are compared as change ids: target on origin, descendant on target. The anti-fabrication guard is an `--at-op` replay: the last operation transition at which the fix change ids stopped being visible must also be the one at which the target's structure.txt became the final content, which fails hand-edit-then-`jj abandon` and cannot fail any honest route however many operations it took. Nothing is positional and nothing reads jj's operation descriptions or any other English — the previous suite lost a task's signal when jj renamed 'undo' to 'revert'. On top of that sits the shared anchor fixture, with an anchor_exemptions.json naming the two fix commits.

**Scoring.** 8 tests total / 3 floored / 5 scored · anchored: **yes** · anchor exemptions: **yes**

8 tests, 3 floored (target survived, target still described as the target, `feature` bookmark on the target or an ancestor), 5 scored. Partial credit is k/5, capped at 4/5 = 0.8 whenever anything fails. A no-agent run scores 0. Note the doc's own finding: the op-count test that made this the sharpest separator in the 795-trial baseline was deleted on this branch, so the two-sequential-squash route is now believed to score 1.0.

*Floored — must pass, earns nothing:*

- `test_final_state.py::test_feature_bookmark_still_points_at_the_target`
- `test_final_state.py::test_target_commit_still_described_as_the_target`
- `test_final_state.py::test_target_commit_survived`

**Known holes.** The op-log replay authenticates the history against itself — a repository rebuilt and then squashed properly agrees with its own record — so it is only the anchor that makes it an integrity check.

**Repair queued.** §1 R1 corollary: the prompt leaks the technique — it opens 'Revsets let one operation name a whole range of source commits rather than one at a time' — and enumerates the post-state commit count. Rewrite the prompt; the verifier is sound.

[↑ contents](#contents)

### template_customize_log_output

`built` · `prompt still spec-style, rewrite pending` · `separated models: yes`

**The prompt, verbatim — `instruction.md`.** Still spec-style — rewrite pending.

```markdown
# Customize jj log output with Templates

## Background
Jujutsu (`jj`) supports a powerful functional templating language to customize the output of commands like `jj log`. You can define template aliases in your config to reuse custom formats.

## Requirements
You have a jj repository initialized at `/home/user/repo`.
Your task is to configure a new template alias named `log_custom` for the `jj` CLI.
The alias must output the short change ID (`change_id.short()`), followed by `" | "`, followed by the first line of the commit description (`description.first_line()`), and ending with a newline (`"\n"`).

## Constraints
- Project path: `/home/user/repo`
- The alias must be named exactly `log_custom`.
```

**How success is graded.** Two assertions, and neither grades a commit. First, `jj config get template-aliases.log_custom` must exit 0, and its value — after a real newline is normalised back to the two characters `\n`, so TOML-escaped and hand-written forms compare equal — must contain `change_id.short()`, `description.first_line()`, a quoted ' | ' separator and a quoted newline. Second, and this is the real assertion, `jj log -r all() --no-graph -T log_custom` must render byte-identically to the verifier rendering the reference template over the same revisions, so the check is indifferent to quoting, to which config layer the alias lives in and to whether it was written by `jj config set` or by hand. No commit is identified at all — not by anchored change id, not by position, not by description — because the task is about a config value and its rendering; the task carries no anchored claim of its own. The first test is a set of literal substring checks over the config value (jj's data, not its prose); the second compares rendered bytes on both sides. The only fabrication guard is the shared session-scoped anchor fixture, which still requires every bootstrap change id and the handover operation id to be present.

**Scoring.** 2 tests total / 0 floored / 2 scored · anchored: **no** · anchor exemptions: **none**

2 tests, 0 floored, 2 scored. The reward is 0, 0.5 or 1.0. A no-agent run scores 0. The doc records this as the second-sharpest discriminator in the baseline at 9/15, and separately as one of three measured grader artifacts — identical correct behaviour scored 1.0 hand-edited and 0.5 through `jj config set`, which is what the current tolerant normalisation was written to fix.

**Known holes.** Nothing anchors the graded object, and on jj 0.44 a template runtime error renders `<Error: …>` inline at exit 0 — both sides of the byte comparison would render it identically, so the render test can pass on garbage until an explicit `<Error:` rejection is added.

**Repair queued.** §1 R1 corollary: the prompt hands over the template expression (`change_id.short()`, `description.first_line()`, `"\n"`) verbatim, so it tests reading comprehension. §4.0.2 #10 adds a verifier repair for jj 0.44: a template runtime error renders `<Error: …>` inline at exit 0, so any graded artifact containing that substring must be rejected before comparison.

[↑ contents](#contents)

### track_untracked_file

`built` · `prompt rewritten` · `separated models: yes`

**The prompt — two versions, verbatim.**

*Current — `instruction.md`, spec-style:*

```markdown
# Track an Ignored File in Jujutsu (jj)

## Background
In `jj` (Jujutsu), new files are automatically tracked and included in the working copy commit. However, files that match patterns in `.gitignore` are ignored and not automatically tracked. Sometimes, you may need to explicitly track a specific file that is otherwise ignored, without modifying the `.gitignore` rules.

## Requirements
- Explicitly track the ignored file `app.log` in the repository.
- Do not modify the existing `.gitignore` file.
- Finalize the current working copy by creating a new commit with the message "Track log file".

## Constraints
- Project path: `/home/user/project`
```

*Rewritten — one line, user voice (arm `track_untracked_file_terse`):*

```text
app.log is ignored but I need it tracked, commit as "Track log file", don't touch the ignore rules
```

**How success is graded.** Everything is asserted about one commit: the change the bootstrap's working copy was sitting on, resolved through the anchor's reserved per-workspace key because its handover description was empty. That change must track app.log in `jj file list`, and its description must contain 'Track log file'. The floored third test byte-compares .gitignore against the bootstrap's exact '\*.log\\n' both on disk and in that commit's tree. Nothing is positional — the previous version graded `@-`, which scored a correct `jj describe` finish 0 and a fabricated commit at `@-` a full 1.0 — and nothing reads jj's English. The guard is the shared anchor fixture with deliberately no exemption file, so a route that abandons the handover working copy instead of finalising it fails outright, and a wipe-and-rebuild fails on the handover operation id.

**Scoring.** 3 tests total / 1 floored / 2 scored · anchored: **yes** · anchor exemptions: **none**

3 tests, 1 floored (test_gitignore_unchanged), 2 scored. The reward is 0, 0.5 or 1.0, and the full mark additionally requires the floored .gitignore check to pass. A no-agent run scores 0. This is the one kept task with a measured non-zero failure rate on sonnet.

*Floored — must pass, earns nothing:*

- `test_final_state.py::test_gitignore_unchanged`

**Known holes.** The byte-exact .gitignore check that catches the `!app.log` cheat is floored, so that cheat still passes both scored tests and is only capped below 1.0 rather than zeroed.

**Repair queued.** None — no repair queued against this task.

[↑ contents](#contents)

### workspace_update_stale

`built` · `prompt still spec-style, rewrite pending` · `separated models: yes`

**The prompt, verbatim — `instruction.md`.** Still spec-style — rewrite pending.

```markdown
# Update Stale Workspace

## Background
You are working in a `jj` repository at `/home/user/myproject`. Another user (or process) recently modified the repository from another workspace (`/home/user/workspace_b`), which caused your current workspace's working copy to become stale. A stale working copy means the commit your workspace is sitting on was changed by an operation run elsewhere, so your working copy files no longer match it.

## Requirements
1. Update the stale working copy in `/home/user/myproject` so that it is no longer stale.
2. After updating, you will see that `config.json` has been modified by the other workspace (the `status` field is now `"pending"` and `new` is `true`).
3. Modify `config.json` by changing the `"status"` field from `"pending"` to `"active"`.
4. Commit the change with the exact description `"Activate config"`.

## Constraints
- Project path: `/home/user/myproject`
```

**How success is graded.** Three assertions, all of which additionally require the commit they inspect to be — or to descend from — the change this workspace's working copy was sitting on at handover, which is where the other workspace's work landed; that change is resolved through the anchor's per-workspace key. First, `jj st` must exit 0 in the project (a stale working copy exits 1 on the pinned jj) and its stderr must not contain 'stale'. Second, config.json on disk must parse as JSON with status == 'active' and new == true, and the committed copy at `@-` must say the same, so the other workspace's field was preserved rather than overwritten. Third, the commit at `@-` must have a description containing 'Activate config'. So identity is anchored but the graded commit itself is addressed positionally as `@-`. One assertion does read jj's English — the stderr substring 'stale' — though it sits behind the exit-code check and can only produce a false negative; 'Activate config' is a substring check on a `-T description` render of agent-authored text the instruction mandates. The guard is the shared anchor fixture plus the descends-from-the-handover claim, which the docstring records as what killed a measured fabricate-from-`root()` solve that had scored 1.0.

**Scoring.** 3 tests total / 0 floored / 3 scored · anchored: **yes** · anchor exemptions: **none**

3 tests, 0 floored, 3 scored. Partial credit is 0, 0.333333 or 0.666667, capped at 0.666667 whenever anything fails. Measured in a real container on the pinned image: the untouched image scores 0 (all three scored tests fail) and a genuine `update-stale` → edit → `jj commit` solve scores 1.

**Known holes.** The graded commit is `@-` by position, so a correct solve that finishes by describing the updated working copy in place (leaving it at `@`) fails two of the three scored tests.

**Repair queued.** §2/§5.1 (corrected): delete the redundant stderr grep at tests/test_final_state.py:89 as hygiene — the exit-code assertion on the line above already discriminates — and relax the `@-` positional. The doc explicitly withdraws the claim that this task grades English and restores it to a full keep.

[↑ contents](#contents)

### absorb_changes

`built` · `provisional` · `prompt still spec-style, rewrite pending` · `separated models: no`

**The prompt, verbatim — `instruction.md`.** Still spec-style — rewrite pending.

```markdown
# Absorb Changes into Appropriate Commits

## Background
You are working on a project tracked with `jj` (Jujutsu) at `/home/user/project`. 
You have been developing two distinct features in a stack of commits:
1. A commit that modifies `feature_a.py`.
2. A child commit that modifies `feature_b.py`.

While testing the latest state, you found bugs in both features and fixed them directly in your current working copy (`@`). Instead of manually splitting these changes and squashing them into their respective commits, you want to use a single `jj` command to automatically distribute these bug fixes to the appropriate mutable ancestors where the lines were last modified.

## Requirements
- Distribute the changes in your working copy to the nearest mutable ancestors using the appropriate `jj` command.
- After the operation, the working copy (`@`) should be empty (no changes).

## Constraints
- Project path: `/home/user/project`
```

**How success is graded.** The task is graded as per-file placement, which is what distinguishes absorb from a wholesale squash. For feature_a.py: the commit the bootstrap described 'Initial commit', resolved by anchored change id, must touch feature_a.py in its own diff (`jj diff --name-only`), its content there must carry the marker 'Feature A fixed', and `{target}..@ & files(root-file:"feature_a.py")` must be empty — no later commit may still be modifying that path. feature_b.py is the same test against the anchored 'Add feature A' commit. The third test requires `@` to be, or descend from, the anchored 'Add feature A' commit, to render `empty == true` and to have no changed paths. Commits are identified by anchored change id, with the working copy anchored by relation rather than identity; nothing is positional. No English is read — emptiness comes from the template keyword rather than from jj's 'The working copy has no changes.' The guard is the shared anchor fixture plus an anchor_exemptions.json permitting the handover `@` to disappear, since the per-file `jj squash --into` route empties it and jj abandons an emptied squash source.

**Scoring.** 3 tests total / 0 floored / 3 scored · anchored: **yes** · anchor exemptions: **yes**

3 tests, 0 floored, 3 scored. Partial credit is 0, 0.333333 or 0.666667; 1.0 requires all three. A no-agent run scores 0 — and note the docstring's record that the old version of test_feature_b_absorbed passed on the untouched image because it read the file at the very commit holding the un-absorbed fix.

**Known holes.** The content check is a substring of the fix marker, so hand-placing the right line into the right ancestor passes without `jj absorb` ever running — correct under R3, but it means the task cannot distinguish absorb from a careful manual squash.

**Repair queued.** §5.1 amendment 3: held for capability coverage alone, so it contributes nothing to a paired comparison. It leaves when survey theme 3.3 (absorb review feedback) lands and screens well.

[↑ contents](#contents)

### undo_mistaken_rebase

`built` · `provisional` · `prompt still spec-style, rewrite pending` · `separated models: no`

**The prompt, verbatim — `instruction.md`.** Still spec-style — rewrite pending.

```markdown
# Undo a Mistaken Rebase in jj

## Background
Jujutsu (`jj`) records every repository operation in an operation log, so any change to the
repository can be reverted after the fact — including a rebase that has already completed.

The repository at `/home/user/repo` has the linear history `base` -> `A` -> `B`, with the
bookmark `main` on `A`.

## Requirements
1. Rebase commit `B` onto `base`. This is the mistake you are going to revert.
2. Undo that rebase, returning the repository to the state it was in beforehand.

## Constraints
- Project path: `/home/user/repo`
- Both steps must actually be performed: the operation log must show the rebase, and then the
  undo that reverted it.
- Afterwards the history must be exactly `base` -> `A` -> `B` again, with `main` on `A` and the
  file `f` holding `base`, `A`, and `B` in those respective commits.
```

**How success is graded.** The whole operation log is replayed with `jj --at-op`, and at each operation the verifier asks where the bootstrap's `B` change was sitting, as change ids. The first scored test requires that at some recorded operation `B`'s only parent was the bootstrap's `base` change — the mistaken rebase happened, and happened to that commit. The second requires that plus, at the current operation, `B` sitting on the bootstrap's `A` with the `conflict` template keyword false. It is a conjunction on purpose: this task's correct end state IS its bootstrap state, so every pure end-state assertion here is in the vacuity floor and earns nothing. All three commits are identified by anchored change id, wrapped as `present(change_id(<id>))` so an operation predating a commit does not error; the floored tests still resolve by `description(substring:…)` and one compares parents by description first line. Nothing matches jj's English operation descriptions — the previous version did, and the docstring records three measured mis-scores from it, including reward 1.0 for a throwaway rebase that never touched `B` and reward 0.5 for a repository that was never fixed. The guard is the shared anchor fixture, which is what makes the replay an integrity check rather than a self-consistency one.

**Scoring.** 6 tests total / 4 floored / 2 scored · anchored: **yes** · anchor exemptions: **none**

6 tests, 4 floored (commits survived, topology restored, main bookmark restored, file contents restored — all of which pass on the untouched bootstrap by design), 2 scored. The reward is 0, 0.5 or 1.0. A no-agent run scores 0/2. The docstring records the measured spread: rebase + any of undo / op undo / op revert / op restore all score 2/2; the unrelated-rebase cheat 0/2; rebase-without-undo and the snapshot-undo 1/2.

*Floored — must pass, earns nothing:*

- `test_final_state.py::test_commits_survived`
- `test_final_state.py::test_file_contents_restored`
- `test_final_state.py::test_main_bookmark_restored`
- `test_final_state.py::test_topology_restored`

**Known holes.** Only 2 scored tests, so a single grader artifact halves the task; and the replay cannot tell a deliberately staged rebase-and-revert from a genuine mistake — only the anchor rules that out.

**Repair queued.** §5.1 amendment 3: capability-coverage keep only; survey theme 3.6 (recover from your own mistake) is its deeper replacement.

[↑ contents](#contents)

### operation_recovery

`built` · `provisional` · `prompt still spec-style, rewrite pending` · `separated models: no`

**The prompt, verbatim — `instruction.md`.** Still spec-style — rewrite pending.

```markdown
# Return a Repository to an Earlier State

## Background
Jujutsu (`jj`) keeps a record of every step it has taken in a repository — each commit, each rebase, each snapshot of the working copy. That record holds the complete repository state as it was after each step, so a repository can be put back the way it was at an earlier point, and the states in between are never thrown away.

## Requirements
The repository at `/home/user/project` holds five commits, described `Commit 1` through `Commit 5`, each adding one file, with an empty working-copy commit on top. The last three commits were a mistake. Put the repository back exactly as it was immediately after `Commit 2` was created — the point at which `Commit 2` existed and the working copy was the new empty commit sitting on top of it. The end state must satisfy all of the following:

1. `/home/user/project` holds `file1.txt` (containing `C1`) and `file2.txt` (containing `C2`); `file3.txt`, `file4.txt` and `file5.txt` are gone from it. Those two files are the whole content of the working copy — nothing else is recorded in it.
2. Exactly four commits are visible: the root commit, `Commit 1`, `Commit 2`, and the empty working-copy commit on top of `Commit 2`. Nothing described `Commit 3`, `Commit 4` or `Commit 5` is visible any more.
3. `Commit 1` and `Commit 2` are still the same two commits they are now — same commit IDs, same parents. Do not rewrite them or rebuild equivalents of them.
4. The working copy is the same empty, undescribed commit that was the working copy immediately after `Commit 2` was created: the same change ID, with `Commit 2` as its parent. Creating a fresh empty commit on top of `Commit 2` produces a different commit and does not satisfy this.
5. Nothing is erased. The discarded work must still be reachable through the repository's record of past steps, so do not delete, re-initialise, or prune anything.

## Constraints
- Project path: `/home/user/project`.
```

**How success is graded.** The recovered state is asserted commit by commit. file3/4/5.txt must be off disk and absent from the tree of the anchored change the bootstrap went on to describe 'Commit 3'; that change must track exactly file1.txt and file2.txt; no commit may be described 'Commit 3', 'Commit 4' or 'Commit 5', and the anchored 'Commit 4' and 'Commit 5' changes must not resolve at all. Then `@` must BE that anchored 'Commit 3' change, must render `empty`, must be undescribed, and its parent must be the anchored 'Commit 2' — which is what separates going back to the earlier state from editing history forward into a similar shape. Finally exactly four commits may be visible and the three anchored changes must be among them. Commits are identified by anchored change id throughout (falling back to values read at the operation that first created 'Commit 2'); `@` is used, but pinned by equality to an anchored change rather than by offset. No English is read — descriptions are matched with explicit `description(exact:…)`/`substring` pattern kinds. The guard is the shared anchor fixture plus an anchor_exemptions.json naming Commit 4, Commit 5 and the handover `@`; 'Commit 3''s change is deliberately not exempted, because requirement 4 asks for it back.

**Scoring.** 8 tests total / 3 floored / 5 scored · anchored: **yes** · anchor exemptions: **yes**

8 tests, 3 floored (kept files' contents on disk, kept commits' commit ids against the reference operation, and 'some operation still records Commit 5'), 5 scored. Partial credit is k/5, capped at 0.8 whenever anything fails. A no-agent run scores 0.

*Floored — must pass, earns nothing:*

- `test_final_state.py::test_earlier_operations_are_still_recorded`
- `test_final_state.py::test_kept_commits_are_the_original_commits`
- `test_final_state.py::test_kept_files_present_with_original_contents`

**Known holes.** `@` must be exactly the recovered change, so a correct recovery that ends standing somewhere else loses a fifth of the reward; and the commit-id equality check that would catch a rebuild-then-`op restore` is floored, so it earns nothing.

**Repair queued.** §5.1 amendment 3: capability-coverage keep only; survey theme 3.6 is its deeper replacement.

[↑ contents](#contents)

### git_fetch_remote

`built` · `provisional` · `prompt still spec-style, rewrite pending` · `separated models: no`

**The prompt, verbatim — `instruction.md`.** Still spec-style — rewrite pending.

```markdown
# Fetch and Rebase with jj

## Background
`jj` (Jujutsu) allows you to seamlessly interact with Git remotes. In this task, you need to fetch new changes from a remote repository, rebase your local work onto the updated main branch, and push your changes back.

## Requirements
- Fetch the latest changes from the `origin` remote.
- Rebase the `feature` bookmark onto the updated `main` branch, which exists in this repo only as the remote bookmark `main@origin`.
- Push the `feature` bookmark to the `origin` remote.

## Constraints
- Project path: `/home/user/repo`
```

**How success is graded.** Both assertions are made in the bare remote at /home/user/remote.git with git plumbing, against a commit id computed from the working repository at verification time. The bootstrap's 'Feature commit' change is resolved by anchored change id, and the commit id it resolves to \*now\* is read from jj — because the rebase the task asks for preserves the change id and rewrites the commit id, so the expected value cannot be stored anywhere. `git rev-parse refs/heads/feature` in the remote must equal that commit id. The second test repeats that and adds: the remote must have a `main`, `feature` must not be the same commit as `main`, and `git merge-base --is-ancestor main feature` must succeed. Commits are identified by anchored change id resolved to a live commit id — never by position and never by description on the remote side. One assertion reads text ('feature' in `git branch --list` stdout), but the decisive comparison beside it is the rev-parse equality. The guard is the shared anchor fixture plus that equality, which kills both the measured `git branch feature main` cheat (reward 1.0 without running jj at all) and an additive fabrication; the explicit `pushed != main` assertion closes the trivially-true `merge-base` case.

**Scoring.** 2 tests total / 0 floored / 2 scored · anchored: **yes** · anchor exemptions: **none**

2 tests, 0 floored, 2 scored. The reward is 0, 0.5 or 1.0. A no-agent run scores 0. This is the longest chain in the current suite at three dependent steps.

**Known holes.** The two scored tests overlap heavily — both assert `pushed == wanted` — so the reward is close to pass/fail, and nothing asserts that a fetch happened at all.

**Repair queued.** §5.1 amendment 3: capability-coverage keep only; survey themes 4.1 and 4.4 (fetch and reconcile) are its replacements. §3 also folds `bookmark_push` into it.

[↑ contents](#contents)

### workspace_add

`built` · `provisional` · `prompt still spec-style, rewrite pending` · `separated models: no`

**The prompt, verbatim — `instruction.md`.** Still spec-style — rewrite pending.

```markdown
# Add a new jj workspace

## Background
You have a Jujutsu repository initialized at `/home/user/myproject`. You want to work on a different feature simultaneously without disturbing your current working copy. You can do this by adding a new workspace.

## Requirements
- Create a new workspace for the repository at `/home/user/myproject-workspace2`.

## Constraints
- Project path: `/home/user/myproject`
- Workspace path: `/home/user/myproject-workspace2`
```

**How success is graded.** The load-bearing claim, re-run in all three tests, is that the new directory is backed by the project's repository: the change id the anchor recorded for the project's handover working copy must resolve from inside /home/user/myproject-workspace2, which a separately-created repository cannot do whatever it is named. Around that: the directory exists, `jj workspace root` there exits 0 and prints that path, it has a .jj, `jj workspace list` in the project reports at least two workspaces with the anchored working copy among their targets, the new directory's own `@` is one of those listed targets, and a plain `jj status` (deliberately without --ignore-working-copy) succeeds there. Commits are identified by the anchor's per-workspace key, not by position or description. Two reads are textual but not English: `jj workspace root`'s stdout is compared against a literal path, and `jj workspace list` is parsed through an explicit `-T` template. The guard is the shared anchor fixture plus the resolve-from-inside check, which the docstring records as what closes the measured `jj git init /home/user/myproject-workspace2` cheat that had scored 1.0.

**Scoring.** 3 tests total / 0 floored / 3 scored · anchored: **yes** · anchor exemptions: **none**

3 tests, 0 floored, 3 scored. Partial credit is 0, 0.333333 or 0.666667; 1.0 requires all three. A no-agent run scores 0.

**Known holes.** With no anchor file the identity claim degrades to 'the project's current `@` resolves inside the workspace', and one assertion compares `jj workspace root` stdout against a hardcoded path literal.

**Repair queued.** §5.1 amendment 3: capability-coverage keep only — and the one of the five with no replacement, because the survey's 51-theme menu contains no workspace theme at all. §3 also folds `workspace_forget` into it as an add → list → forget lifecycle.

[↑ contents](#contents)

---

## Proposed — 10, none built

Ten tasks at design stage. Nothing here has been built, run or measured.

### N1 — a conflict that propagates instead of being resolved on the spot

`proposed` · `nothing built`

> **Design stage — nothing built.** None of these ten tasks exist yet — every prompt, fixture and grading rule below is a design sketch from docs/suite_redesign_proposal.md, not a built task: no bootstrap has been stood up on jj 0.44, no verifier has been written, and the proposal's own R7 forbids writing any of these verifiers until a genuine solve has been run against the pinned binary first.

**The proposed prompt.** Wording as the proposal states it.

```text
I rebased onto main and the middle commit blew up. Don't unpick the stack — fix it where it broke and make sure everything above comes out clean.
```

**How success would be graded.**

The verifier asserts that the anchored middle change has `conflict == false`, that every anchored descendant also has `conflict == false` and still carries its own changes, and that the head's tree contains the resolved file with the pinned content. Graded commits are identified by anchored change id from `bootstrap_anchor.json` (never by `@` position and never by description), so the same assertions hold whichever route the agent took. Per the survey's executed run of this fixture the assertion must be `conflicts()` is empty across the whole repo rather than 'the three stack commits are clean', because `@` is conflicted too. The plausible-wrong-solve guard is structural rather than incidental: a fixup commit stacked on top leaves the anchored middle change conflicted and fails, which is the R4 test this task exists for. The fabrication guard is that every graded commit resolves through its anchored change id, so rebuilding an equivalent clean stack from `root()` and moving bookmarks onto it fails — the proposal records reward 1.0 for exactly that rebuild route on two existing tasks that skipped the anchor. Nothing here may grade jj's advice block, which changes wording between versions.

**Scoring, anchoring, known holes.** Not recorded — no verifier exists, so there is no test count, no floored set, no anchor decision and no measured weaknesses for this task. Risks below are the proposal's, not measurements.

**Capability.** First-class conflicts as a state you carry rather than a stop-the-world event: resolve once at the commit where the conflict was introduced and let jj propagate the resolution through every descendant. The current suite has four conflict tasks and they are all the same shape — one file, two sides, textual, resolved on the spot — so nothing reaches jj's actual differentiator, that a conflicted commit is a normal commit you can build on.

**Fixture.** A four-commit stack that conflicts in its second commit when rebased onto a moved `main`, with a fifth commit already sitting on top of the conflict. The survey's executed version of the same ground (theme 3.5) is a three-commit feature stack rebased onto a divergent trunk, which left four commits `conflict=true` — the three stack commits plus `@` itself. The prompt must pin the intended resolution ('everything above comes out clean' / 'keeping both sides' behaviour') and the fixture must make exactly one file content satisfy it, because conflict resolution is not auto-gradeable unless the intent is pinned.

**What it discriminates.** The git-shaped model in which a conflict halts work and must be cleared before anything else can happen — so the agent either unpicks the stack commit by commit or lands a fixup on top, leaving the commit that actually broke still conflicted. The correct model is that the rebase succeeded at exit 0, the conflict lives in the commit, and one resolution at the source clears the whole subtree.

**Risks.** The proposal folds N1 into the survey's themes 3.5 and 2.4 and says N1 conflates them — 'resolve the propagated conflict once' (Tier 3) and 'leave a conflict and build on it' (Tier 2) are better as two tasks, and the survey's warranted fixture recipe wins where they overlap. Conflict resolution is ungradeable unless the fixture admits exactly one satisfying content. `jj resolve --tool :ours`/`:theirs` map to destination/rebased-revision respectively, so the fixture must not let a `:ours` shortcut be accidentally correct.

**Needs verification on 0.44.** Nothing flagged for 0.44 verification on this task.

[↑ contents](#contents)

### N2 — a merge commit the agent creates

`proposed` · `nothing built`

> **Design stage — nothing built.** None of these ten tasks exist yet — every prompt, fixture and grading rule below is a design sketch from docs/suite_redesign_proposal.md, not a built task: no bootstrap has been stood up on jj 0.44, no verifier has been written, and the proposal's own R7 forbids writing any of these verifiers until a genuine solve has been run against the pinned binary first.

**The proposed prompt.** Wording as the proposal states it.

```text
Merge feature-a and feature-b and sort out the clash in config.toml — keep both settings.
```

**How success would be graded.**

The verifier asserts `@`'s parents are exactly the two anchored changes, order-insensitive, using `parents.len()` and `parents.map(|p| p.change_id())` (the grading instrument the proposal takes from survey theme 1.5, which is recorded as verified working); that the merge has `conflict == false`; that the merged `config.toml` contains both settings; and that neither anchored parent change was rewritten — same change ids and same commit ids as the bootstrap recorded. Graded commits resolve through anchored change ids, and the two parents' surviving commit ids are themselves the fabrication guard: a solve that rebuilds either side, or that fakes a merge by hand-writing a combined `config.toml` into a single-parent commit, fails on `parents.len()` and on the parent commit-id check together. Note the proposal says merge with \*ordered\* parents is theme 1.5's shape while N2's is order-insensitive; the hybrid N2 keeps is 'a merge the agent creates AND resolves', which the survey menu lacks. Nothing about jj's merge output text is graded.

**Scoring, anchoring, known holes.** Not recorded — no verifier exists, so there is no test count, no floored set, no anchor decision and no measured weaknesses for this task. Risks below are the proposal's, not measurements.

**Capability.** Creating an n-parent merge and resolving the clash inside it. Hole A in the proposal: zero tasks create a merge, there is no `jj new A B` anywhere and no assertion anywhere on `parents.len() > 1`; `resolve_tool`'s bootstrap contains a merge the agent only resolves, never one it builds.

**Fixture.** Two bookmarks whose tips both changed `config.toml`, with no merge present in the repo. Both tips must be anchored so the verifier can require they were not rewritten, and the two edits must be arranged so that 'keep both settings' has exactly one satisfying file content.

**What it discriminates.** Looking for a `jj merge` subcommand (it does not exist) and the assumption that a merge is an exotic operation, versus knowing `jj new A B` is the ordinary way to build one. The wrong-but-plausible solve is a single-parent commit that just contains the union of both files' contents, which passes a content check and fails `parents.len()`.

**Risks.** The proposal notes theme 1.5 'saturates fast once a model knows `jj new A B C`' and should be floor-only in its Tier 1 form; N2 earns its slot only because the agent must also resolve the clash inside the merge it made. It is also a two-to-three step task, and amendment 2 wants at least six of the ten to compose five or more dependent operations — N2 is not one of those six.

**Needs verification on 0.44.** The proposal marks 'jj merge does not exist' as [0.38-only — re-check] in its provenance roster (§4.0.3): the probe is `jj merge -h` on `jj 0.44.0-af45d57de716`, and both N2 and theme 1.5 assume `jj new A B` is the only route.

[↑ contents](#contents)

### N3 — evolog as recovery

`proposed` · `nothing built`

> **Design stage — nothing built.** None of these ten tasks exist yet — every prompt, fixture and grading rule below is a design sketch from docs/suite_redesign_proposal.md, not a built task: no bootstrap has been stood up on jj 0.44, no verifier has been written, and the proposal's own R7 forbids writing any of these verifiers until a genuine solve has been run against the pinned binary first.

**The proposed prompt.** Wording as the proposal states it.

```text
I described over the wrong commit and then restored a file I shouldn't have. The old version is still in there — put that content back on the same change.
```

**How success would be graded.**

The verifier asserts the anchored change id still resolves; that its tree equals the tree of a commit id that appears in its own evolog and is not the evolog head; and that the recovered file's content matches that predecessor byte for byte — all recomputed at verification time, so no tree hash or commit id is hardcoded. Under the theme 3.6 shape the assertion relocates: grade 'does the later work still exist' plus the change-id set and descriptions, with an `--at-op` replay confirming the recovered commits are the originals rather than reconstructions. The fabrication guard is exactly that replay plus the anchored change ids — end state alone cannot distinguish 'restored' from 'rebuilt identically', which is why change-id preservation is the load-bearing assertion. No string matching anywhere: `undo_mistaken_rebase` lost 100% of its scored signal to an operation-description rename, and 0.44 added a new leading stdout line to `undo`/`revert`/`restore` that would have done it again. Divergence must be addressed through `change_id(X)` — never a bare change-id revset (it errors on a divergent change) and never the literal offsets `X/0`/`X/1`.

**Scoring, anchoring, known holes.** Not recorded — no verifier exists, so there is no test count, no floored set, no anchor decision and no measured weaknesses for this task. Risks below are the proposal's, not measurements.

**Capability.** Using the evolution log to recover a clobbered version of a change — the point of `jj evolog`, as opposed to reading it. `obslog_view` only prints the evolog and grades that it printed; nothing in the suite tests recovery, and the wider op-log recovery surface (`op revert` out of the middle of the log) is untouched.

**Fixture.** A change whose current version was clobbered by the bootstrap — description overwritten and a file restored away — with the good version still reachable in that change's evolog. The proposal directs that where survey theme 3.6 ('recover from your own mistake') covers the same ground it wins, and that fixture instead ships a mistake already made (a wrong squash) plus two commits of subsequent work, so the agent must go back without discarding the later work.

**What it discriminates.** Reaching for `jj undo` or `jj op restore <pre-mistake op>`, both of which also discard the later work — `op restore` is time travel, not an inverse patch. The proposal records this as the single most expensive design error it caught: an earlier draft named `op restore` as the correct route, and on a measured `A→B→C→D` stack it left only `A,B`. Only `jj op revert <the squash operation>` reaches the stated end state, and the tempting contrast 'restore removes C and D, revert removes only C' is itself wrong — a verifier written on it fails the correct solve.

**Risks.** The highest grader-artifact risk in its tier. The correct route leaves a residual divergent change (measured at offsets X/0 and X/4, not /0 and /1), so the design must decide deliberately whether residual divergence is acceptable end state and say so in the prompt if it is not. The solve is `jj op revert` and op-recovery is on the list of operations that legitimately drop a change id, so this task probably needs an `anchor_exemptions.json` — and a green pre-sweep pass cannot tell you it is missing, because the untouched image never does the work that breaks the assertion.

**Needs verification on 0.44.** Two items, both in the proposal's provenance roster. (1) That `jj evolog` on the surviving side of a divergence does not carry the divergent sibling (it is a sibling, not a predecessor) is [0.38-only — re-check]; N3's verifier reads the evolog for a predecessor tree, so if that changed, 'not the evolog head' stops meaning what it means here — re-run an evolog on either side of a 0.44 divergence before authoring. (2) Theme 3.6's full fixture — squash, two commits of later work, `jj op revert` — was executed on 0.38 only; the restore-vs-revert mechanism was re-run on 0.44 but the residual divergence and its offsets were not. The proposal calls this the cheapest remaining warrant gap on the menu.

[↑ contents](#contents)

### N4 — revsets the agent writes

`proposed` · `nothing built`

> **Design stage — nothing built.** None of these ten tasks exist yet — every prompt, fixture and grading rule below is a design sketch from docs/suite_redesign_proposal.md, not a built task: no bootstrap has been stood up on jj 0.44, no verifier has been written, and the proposal's own R7 forbids writing any of these verifiers until a genuine solve has been run against the pinned binary first.

**The proposed prompt.** Wording as the proposal states it.

```text
Give me the change ids of every tip that isn't merged into main yet — one per line in unmerged.txt.
```

**How success would be graded.**

The verifier evaluates the reference revset in the repo at verification time and requires `unmerged.txt` to equal that set of change ids exactly — set comparison, with the expected answer never appearing as a constant in the verifier. Every jj read in the verifier must pass `--ignore-working-copy` (or go through `--at-op`, which implies it) so the verifier does not snapshot and mutate the repo it is grading. A hand-listed file passes only if it is right, which is the deliberate R3 concession: the revset is the cheap route, not the graded one. The fabrication guard is that the answer is recomputed from the repository the agent was handed, so a guessed or copied list cannot match, and the anchored change ids let the verifier additionally assert the history was not restructured to make a wrong answer true.

**Scoring, anchoring, known holes.** Not recorded — no verifier exists, so there is no test count, no floored set, no anchor decision and no measured weaknesses for this task. Risks below are the proposal's, not measurements.

**Capability.** Composing a non-trivial revset as the agent's own work. Hole B: one revset task exists (`revset_querying_bob`, 43 lines, substring-graded, the weakest verifier in the set), and `roots()`, `heads()`, the `..`/`::` distinction, `mutable()`/`immutable()`, `latest(n)`, `divergent()` and `at_operation()` are untested; `glob:` appears nowhere in any prompt or verifier.

**Fixture.** A branching history with several heads, some already merged into `main`. It must be big enough that eyeballing the log is not a viable route — hole G records that every current bootstrap is at most six commits and three files, never large enough to make a revset the only practical answer.

**What it discriminates.** Eyeballing `jj log` and hand-transcribing what looks like a tip — which produces a plausible, nearly-right list — versus composing `heads()`/`::`-style ancestry into a query. It also catches the git-shaped `..` reading: in jj revsets `..` and `::` differ, and an agent that carries git's range semantics over produces a confidently wrong set.

**Risks.** The proposal prefers survey theme 3.7 ('messy history → mergeable') over N4 as written, because 3.7 makes the revset the \*route\* to an action rather than the deliverable and so dodges the zero-tool-call confound — an answer-file task invites guessing, and some fraction of zero-tool-call trials measures agency rather than jj skill. Mitigate with scale if it ships in answer-file form.

**Needs verification on 0.44.** Nothing flagged for 0.44 verification on this task.

[↑ contents](#contents)

### N5 — filesets

`proposed` · `nothing built`

> **Design stage — nothing built.** None of these ten tasks exist yet — every prompt, fixture and grading rule below is a design sketch from docs/suite_redesign_proposal.md, not a built task: no bootstrap has been stood up on jj 0.44, no verifier has been written, and the proposal's own R7 forbids writing any of these verifiers until a genuine solve has been run against the pinned binary first.

**The proposed prompt.** Wording as the proposal states it.

```text
Roll back my changes under src/ but leave the generated tree exactly as it is.
```

**How success would be graded.**

The verifier asserts that `changed_paths` of the anchored change is exactly the non-generated set, that every generated file's content equals the bootstrap's, and that the anchored change id survives the rewrite. The graded commit is found by anchored change id, and the change-id-survives/commit-id-changed pair distinguishes a genuine in-place rewrite from a rebuilt commit. Doing it file-by-file also passes — the fileset is the cheap route, not the graded one (R3). The fabrication guard is the anchored change id plus the byte-exact generated tree: fabricating a fresh commit with the right final tree fails the anchor, and over-restoring and then re-adding the generated files fails byte-equality only if the fixture's generated content is not trivially reproducible, so the fixture must make it non-reconstructible (machine-looking content with a recorded hash).

**Scoring, anchoring, known holes.** Not recorded — no verifier exists, so there is no test count, no floored set, no anchor decision and no measured weaknesses for this task. Risks below are the proposal's, not measurements.

**Capability.** Writing a fileset — path-scoped selection with `glob:`/`root-file:` patterns — to scope a rewrite. Verifiers in the suite \*use\* `files(root-file:"…")`, but no prompt has ever asked an agent to write one, and `glob:` appears nowhere in the tree.

**Fixture.** A commit that changed both `src/**/*.py` and a `src/generated/**` tree, so that the generated subtree is nested inside the directory the user names — the whole difficulty is that the obvious path selector over-selects. The fixture records the bootstrap contents of every generated file so the verifier can require them byte-identical.

**What it discriminates.** Reaching for a whole-directory restore (`jj restore src/`) or a git-shaped `checkout -- src/`, which silently takes the generated subtree with it — the end state looks right at the top level and the generated tree is quietly clobbered. The correct model is a fileset that subtracts the nested tree.

**Risks.** The proposal notes there is no dedicated fileset theme on the survey's 51-theme menu (2.1, split-by-path, is the nearest), so N5 is additive and ships without a survey-verified fixture recipe — meaning R7's stand-it-up-and-solve-it step is the first authoring action, not a later check. It is also a short task and does not help satisfy amendment 2's five-plus-operations requirement.

**Needs verification on 0.44.** Nothing flagged for 0.44 verification on this task.

[↑ contents](#contents)

### N6 — immutable revsets

`proposed` · `nothing built`

> **Design stage — nothing built.** None of these ten tasks exist yet — every prompt, fixture and grading rule below is a design sketch from docs/suite_redesign_proposal.md, not a built task: no bootstrap has been stood up on jj 0.44, no verifier has been written, and the proposal's own R7 forbids writing any of these verifiers until a genuine solve has been run against the pinned binary first.

**The proposed prompt.** Wording as the proposal states it.

```text
Set this repo up so nothing at or below main can be rewritten by accident, then fix the typo in the message just above it.
```

**How success would be graded.**

The verifier \*evaluates\* the configured `immutable_heads()` alias in the repo and requires the anchored `main` change to be inside it — never a string match on the config value, because `jj config set --repo` accepts nonsense keys silently at exit 0 and 'the agent set a config key' is never evidence the key does anything. It then asserts the anchored commit below `main` is byte-identical to the bootstrap's (protection actually took effect), and that the anchored change above `main` carries the corrected description under the same change id (the permitted rewrite actually happened). Graded commits resolve through anchored change ids; the change-id-preserved / commit-id-new pair on the fixed commit is the fabrication guard against a rebuilt commit with the right message, and the byte-identical below-main commit closes the 'rewrote everything and then reconstructed it' route. Both halves must be scored so the task cannot be passed by doing only the configuration or only the edit.

**Scoring, anchoring, known holes.** Not recorded — no verifier exists, so there is no test count, no floored set, no anchor decision and no measured weaknesses for this task. Risks below are the proposal's, not measurements.

**Capability.** Immutability: configuring `revset-aliases."immutable_heads()"` and living with jj's refusal to rewrite protected history. Hole C — zero coverage. `immutable_heads()`, `immutable()`, the refusal itself and `--ignore-immutable` are untouched across all 53 tasks; `immutable_heads()` appears exactly once in the tree, in a docstring comment.

**Fixture.** `main` with two commits below it and two above, and no immutability configured at the start. The fixture must not hand-place `.jj/repo/config.toml` — repo config actually lives at `$HOME/.config/jj/repos/<20-hex>/config.toml`, keyed by `.jj/repo/config-id`, and a hand-placed file there is ignored, so any config the bootstrap sets must go through `jj config set --repo`.

**What it discriminates.** Two wrong models at once. First, that protection is a string you write into a config file — an agent that writes a plausible TOML key that jj does not read exits 0, sees no error, and reports done; the evaluate-the-alias rule is what catches it. Second, that 'set it up so nothing can be rewritten' and 'now rewrite this commit' are in conflict, leading the agent either to skip the config or to reach for `--ignore-immutable` on a commit that was never supposed to be protected.

**Risks.** The proposal flags that the 'evaluate the alias, don't string-match the config' design is now mandatory rather than merely preferable (§4.0.2 #7), and warns that 0.44 silently accepts five config keys it removed — `git.auto-local-bookmark`, `git.push-new-bookmarks`, `ui.revsets-use-glob-by-default`, `core.fsmonitor`, `core.watchman.register-snapshot-trigger` — all exit 0, print nothing, list back happily, and do nothing. A bootstrap that sets one hands over a repo that behaves differently from the one its author designed, and nothing in the build, lint, anchor pass or verifier reports it.

**Needs verification on 0.44.** The survey ships no immutability theme at all (the proposal's §4.2 table records 'none dedicated'), so N6 has no verified fixture recipe behind it and no execution warrant — it is additive and reasoned-only. Related and worth probing before authoring: a fixture built by `jj git clone` sets `trunk()` to `main@origin` and makes everything up to `main` immutable whether you meant it or not.

[↑ contents](#contents)

### N7 — the operation-log surface beyond undo

`proposed` · `nothing built`

> **Design stage — nothing built.** None of these ten tasks exist yet — every prompt, fixture and grading rule below is a design sketch from docs/suite_redesign_proposal.md, not a built task: no bootstrap has been stood up on jj 0.44, no verifier has been written, and the proposal's own R7 forbids writing any of these verifiers until a genuine solve has been run against the pinned binary first.

**The proposed prompt.** Wording as the proposal states it.

```text
Which commits did that big rebase actually touch? Put the change ids in touched.txt.
```

**How success would be graded.**

The verifier recomputes the operation's effect at verification time by `--at-op` differencing — reading the repo at the operation and at its predecessor and taking the change-id delta — and compares `touched.txt` as a set. Whether the agent used `jj op diff`, `op show` or worked it out by hand is not graded (R3). `--at-op` implies `--ignore-working-copy`, which is required so the verifier does not perturb what it grades. The fabrication guard is that the expected set is never a constant: it is derived from the repository the agent was handed, so a guessed list of plausible-looking ids cannot match, and the anchored change ids let the verifier confirm the history it is differencing is the one the bootstrap produced. No English is matched — recorded operation descriptions are stable across the retarget but stdout formatting is not.

**Scoring, anchoring, known holes.** Not recorded — no verifier exists, so there is no test count, no floored set, no anchor decision and no measured weaknesses for this task. Risks below are the proposal's, not measurements.

**Capability.** The operation log as a diagnosable object: `jj op diff`, `op show`, `op abandon`. Only `op log` and `op restore`/`undo` appear anywhere in the suite; hole H adds that five tasks make the agent write a script but none make it diagnose and report a conclusion.

**Fixture.** A repo whose op log contains one multi-commit rebase among several small operations, so the target operation must be identified rather than assumed to be the last one. The survey's equivalent (theme 5.3) uses a rebase of a four-commit stack as the most recent operation and asks for `touched.txt`, one change id per line, sorted.

**What it discriminates.** Guessing the touched set from `jj log` — which shows the current graph, not what the operation changed — instead of reading the operation diff. It also catches the assumption that `Operation` templates expose a working-copy commit; they do not, so op metadata alone cannot answer the question.

**Risks.** Two 0.44 caveats the proposal calls load-bearing for N7 and for every other `--at-op` verifier in the suite. First, `jj op show`/`op diff`/`op log -p` now filter changed revisions by default (`revsets.op-diff-changes-in = "mutable() | immutable_heads()"`); in a constructed mid-stack rebase both versions printed identical lists, so practical impact is narrow, but it bites when an operation touches hidden or non-head immutable revisions, and `--show-changes-in` overrides. Second and larger: `--no-integrate-operation` plus `jj op integrate` are real on 0.44 (the command was inert on 0.38), so an agent can now produce side effects that leave no op-log entry — any verifier reconstructing truth by `--at-op` differencing is reasoning over a log that is no longer guaranteed complete.

**Needs verification on 0.44.** The proposal explicitly says the `op integrate` / `--no-integrate-operation` hazard 'is a hazard for N7 specifically and worth a probe before N7 is authored'.

[↑ contents](#contents)

### N8 — divergence as a thing to work with

`proposed` · `nothing built`

> **Design stage — nothing built.** None of these ten tasks exist yet — every prompt, fixture and grading rule below is a design sketch from docs/suite_redesign_proposal.md, not a built task: no bootstrap has been stood up on jj 0.44, no verifier has been written, and the proposal's own R7 forbids writing any of these verifiers until a genuine solve has been run against the pinned binary first.

**The proposed prompt.** Wording drafted here, not fixed — the proposal does not state it.

```text
jj is showing this change twice and complaining — keep the copy that has the file I named in it and get rid of the other one.
```

**How success would be graded.**

The verifier counts commits matching `change_id(X)` and requires exactly one visible, asserts `divergent == false` on it, and asserts it is the side carrying the named file. Every revset must spell `change_id(X)` and `bookmarks(name)`: a bare change-id revset errors on a divergent change and a bare bookmark-name revset errors on a conflicted bookmark, so this is a task whose own verifier can be broken by the exact trap it tests — `tasks/concurrent_operations/tests/test_final_state.py:26-31` is the in-tree reference that gets it right. The literal offsets `X/0` and `X/1` must never be matched: `X/N` indexes every commit that has ever carried the change id, hidden ones included, newest first, so any rewrite renumbers what the hint prints. Keep the structural half of `concurrent_operations`'s verifier and delete its English assertion, which currently requires jj's literal phrase 'reconcile divergent operations'. Because the solve removes a change id, the task needs an `anchor_exemptions.json`, and a green pre-sweep pass cannot tell you it is missing — only a correct solve reveals it.

**Scoring, anchoring, known holes.** Not recorded — no verifier exists, so there is no test count, no floored set, no anchor decision and no measured weaknesses for this task. Risks below are the proposal's, not measurements.

**Capability.** Divergent change ids: two visible commits sharing one change id, which must be addressed by commit id or through `change_id()` because the bare change-id revset errors. The proposal is explicit that this is a re-scope of `concurrent_operations`, not new capability coverage — that task already builds and resolves a divergence — but nothing hands divergence over pre-made and asks the agent to work with it.

**Fixture.** A repo handed over with the divergence already made — two visible commits sharing one change id, one of them containing a named file. The single-actor route is `jj describe -m A` then `jj --at-op=<older> describe -m B`, which prints `Concurrent modification detected, resolving automatically.` and leaves two `(divergent)` commits. If the two-actor version ships instead (survey theme 4.3), the local-bare-remote rig produces a divergent change and a conflicted bookmark on the same log lines, which is the version with genuinely new content.

**What it discriminates.** Treating `??` as the divergence marker — it marks a conflicted \*bookmark\*, and divergence renders as numbered `X/N` offsets plus `(divergent)`; the two markers can appear on the same log line, and both tutorials get this wrong. The concrete wrong solve is addressing the sides by a bare change id (which errors), or abandoning by change id (ambiguous), instead of by commit id or `X/0`-style offset. In the two-actor version, an agent that reads a conflicted bookmark as divergence abandons a side and loses work.

**Risks.** The proposal's own correction: N8 is not new coverage and neither its original framing nor the survey's 'absent: a divergent change' is right about that. If one ships, ship the two-actor version (theme 4.3), which pairs divergence with a conflicted bookmark. The proposal also warns the prompt must name which side survives — in the single-actor route both sides have the same author, so 'keep my version' does not identify one; the surviving side should be named by something the verifier also asserts (a description or a file).

**Needs verification on 0.44.** The list of operations that legitimately drop a change id — `abandon`, `squash --from/--into`, `new`/`edit`/`prev`/`next` off an empty undescribed `@`, `workspace forget`, `op restore` — was measured on 0.38 and has not been re-measured on 0.44. The proposal calls this the highest-value re-check on its roster, because a wrong entry is a task-arm-destroying missing exemption, and N8 is one of the tasks that needs the exemption.

[↑ contents](#contents)

### N9 — duplicate a range

`proposed` · `nothing built`

> **Design stage — nothing built.** None of these ten tasks exist yet — every prompt, fixture and grading rule below is a design sketch from docs/suite_redesign_proposal.md, not a built task: no bootstrap has been stood up on jj 0.44, no verifier has been written, and the proposal's own R7 forbids writing any of these verifiers until a genuine solve has been run against the pinned binary first.

**The proposed prompt.** Wording drafted here, not fixed — the proposal does not state it.

```text
Copy that run of commits over onto the release branch as well — I want them in both places, so leave the originals exactly where they are.
```

**How success would be graded.** *Grading reconstructed here, not stated by the proposal.*

The verifier asserts each duplicate's own diff individually — one new commit per source commit, each carrying exactly its source's change, in the right order under the named destination — and that both anchored originals are intact: same change ids, same commit ids, same parents. Duplicates cannot be identified by anchored change id (they are new changes minted by the solve), so they must be located structurally, as the set `({destination}..{new head})` or by parent edges from the anchored destination, and then matched to sources by diff rather than by description. The fabrication guard is double: the originals' commit ids must be unchanged (so a solve that \*moved\* the range and then rebuilt it in place fails), and each duplicate's diff must equal its source's diff (so hand-written approximations fail). Anti-fabrication checks of this shape are not method checks and stay unannounced, per R3.

**Scoring, anchoring, known holes.** Not recorded — no verifier exists, so there is no test count, no floored set, no anchor decision and no measured weaknesses for this task. Risks below are the proposal's, not measurements.

**Capability.** `jj duplicate` over a revset range with a placement flag (`-r A::B -d X`, `--insert-after`) — copying a run of commits without moving or rewriting the originals. Absorbs `duplicate_commit`; nothing in the suite duplicates more than a single commit, and the survey's 51-theme menu has no duplicate theme at all, so N9 is one of two additive tasks with no menu backing.

**Fixture.** A stack containing a contiguous run of commits (A::B) plus a separate destination — a release bookmark or a second line of history — where the copies must land. Both endpoints of the range and the destination should be anchored, and the run should be long enough that duplicating one commit or the wrong span is a detectably different end state.

**What it discriminates.** The git mental model in which copying commits means cherry-picking them one at a time, which reaches a similar end state by many more operations and is easy to get wrong in the middle — and, more sharply, the model in which 'move these over' is a rebase, which relocates the originals instead of copying them. A solve that rebases and then re-creates the originals fails on the originals' commit ids.

**Risks.** The proposal records one measured grader artifact on the task it absorbs — `duplicate_commit`'s refusals were one of the three known artifacts in the current suite — so the replacement must not inherit whatever provoked them. Beyond that the proposal says only that N9 is additive with no survey theme behind it, which under R7 means the fixture must be stood up and solved on the binary before any verifier is written.

**Needs verification on 0.44.** Nothing flagged for 0.44 verification on this task.

[↑ contents](#contents)

### ~~N10 — a configured non-interactive diff editor (STRUCK as written)~~

`proposed` · `nothing built` · `struck · slot unassigned`

> **Struck by the proposal.** The proposal strikes N10 as a rule violation — requiring ‑i is a method constraint and an R3 violation — and its slot in the target set is unassigned. The proposal's own answer is to fill that slot from the survey's Tier 3 (2.1 split-by-path or 3.3 absorb-into-a-stack cover the salvageable ask). It is shown here rather than hidden because the ask is salvageable; the wording below is a reconstruction, not a design the proposal states.

> **Design stage — nothing built.** None of these ten tasks exist yet — every prompt, fixture and grading rule below is a design sketch from docs/suite_redesign_proposal.md, not a built task: no bootstrap has been stood up on jj 0.44, no verifier has been written, and the proposal's own R7 forbids writing any of these verifiers until a genuine solve has been run against the pinned binary first.

**The proposed prompt.** Wording drafted here, not fixed — the proposal does not state it.

```text
Move just the logging hunk out of that commit and leave everything else in it exactly where it is.
```

**How success would be graded.** *Grading reconstructed here, not stated by the proposal.*

The salvageable version grades the two resulting trees and nothing else: the anchored source change retains exactly the hunk that was meant to stay, the destination carries exactly the hunk that moved, both change ids survive, and no other file in either commit differs from the bootstrap. It must be route-agnostic — every interactive route has a verified non-interactive substitute (`jj squash <paths>` or `--from`/`--into`, `jj split -r X <paths> -m`, `jj describe --stdin`, `jj resolve --tool :ours`/`:theirs`), so a verifier cannot tell the routes apart from end state and must not try. Nothing may be graded on `-i` being used, on `ui.diff-editor` being configured, or on the interactive failure text — 0.44 reworded that error, so grade the exit code, or better, nothing at all. Fabrication guard: both commits resolve through anchored change ids and their change-id-preserved/commit-id-new pairs, which closes the rebuild-the-pair-from-scratch route.

**Scoring, anchoring, known holes.** Not recorded — no verifier exists, so there is no test count, no floored set, no anchor decision and no measured weaknesses for this task. Risks below are the proposal's, not measurements.

**Capability.** Moving a single hunk between commits — partial-content surgery below the file level. Intended to replace `diffedit_interactive` and to reach `ui.diff-editor`, which is untested because all three 'interactive' tasks can be, and by their verifiers' design should be, solved non-interactively.

**Fixture.** A commit containing two independent hunks in one file, one of which must move and one of which must stay — the fixture must make the two halves separable by content so the end state is checkable without reference to how the split was performed. If a scripted diff editor ships as part of the fixture, place it outside the repo: a stray `editor.sh` left behind by a solve already breaks floored working-copy guards on `diffedit_interactive` and `split_commit_interactive`.

**What it discriminates.** As restated, the file-granular model: an agent that treats 'move that change' as a whole-file operation moves both hunks, or moves the file and re-adds the part that should have stayed, producing a plausible-looking but wrong per-commit diff. The original design's intended discrimination — that the agent must drive an interactive command — is exactly what the proposal rules out of bounds.

**Risks.** The proposal strikes N10 and says it must not ship in this form: requiring `-i` is a method constraint and an R3 violation, and the argument for it is gone from both ends. The interactive commands fail fast rather than hang (with stdin closed, `squash -i`/`split -i`/`commit -i`/`diffedit` exit 1 in tens of milliseconds), so an agent that reaches for `-i` loses a turn, not the trial — there is nothing to protect the suite from. Its slot in the target set goes to a Tier 3 composition theme (the survey's 2.1 split-by-path or 3.3 absorb-into-a-stack cover the salvageable ask), per amendment 2. A scripted diff editor via `--tool` is now proven to work headlessly on 0.44, which makes such a fixture possible but does not make grading the route legitimate.

**Needs verification on 0.44.** The whole task is unresolved rather than merely unverified: the proposal leaves the replacement unspecified beyond 'a Tier 3 theme', so the prompt, fixture and grading above are a reconstruction of the salvageable ask rather than a design the proposal states.

[↑ contents](#contents)

---

## Demoted — 7 kept but not shipping

Seven built tasks kept as a smoke tier: they still run and still score, they are just not part of the shipping fourteen.

### bookmark_create_and_move

`built` · `prompt still spec-style, rewrite pending` · `separated models: no`

**The prompt, verbatim — `instruction.md`.** Still spec-style — rewrite pending.

```markdown
# Manage Bookmarks in Jujutsu

## Background
In Jujutsu (`jj`), bookmarks are named pointers to revisions (similar to Git branches). They are used to mark specific commits, especially when integrating with Git remotes. This task tests your ability to create a bookmark and then move it to a different revision.

## Requirements
- You have a Jujutsu repository initialized at `/home/user/my-project`.
- Create a new bookmark named `feature-x` pointing to the initial working copy commit.
- Create a new commit on top of it with the description `add feature y`.
- Move the `feature-x` bookmark to point to this new commit.

## Constraints
- Project path: `/home/user/my-project`
- Use only `jj` commands.
```

**How success is graded.** Two assertions plus one anchored claim repeated in both. `feature-x` must appear in `jj bookmark list` output, and the commit `feature-x` resolves to must have a description containing 'add feature y'. In each test, the commit `feature-x` points at must also be — or descend from — the working copy the bootstrap handed over, resolved through the anchor's per-workspace key. The commit carrying 'add feature y' is created by the agent so it has no anchored id of its own; it is anchored purely by that ancestry relation. Ancestor-of rather than equal-to is deliberate, so that both the `jj new` + `jj bookmark move` route and the `jj commit` route pass. Two assertions are substring reads of jj output: 'feature-x' in `jj bookmark list`'s human-readable listing, and 'add feature y' in a `-T description` render of agent-authored text. The guard is the shared anchor fixture plus the ancestry claim, which the docstring records as what killed a measured `jj new -r 'root()' -m "add feature y"` fabrication that had scored 1.0.

**Scoring.** 2 tests total / 0 floored / 2 scored · anchored: **yes** · anchor exemptions: **none**

2 tests, 0 floored, 2 scored. The reward is 0, 0.5 or 1.0. A no-agent run scores 0.

**Known holes.** The bookmark-list check is a bare substring, so any line mentioning feature-x satisfies it, and nothing asserts the bookmark ever sat on the initial commit first — the 'create then move' half of the task is not separately graded.

**Repair queued.** §5: 'structurally sound and 5/5 on all three models — they belong in a smoke tier or nowhere.' §3 also folds `bookmark_rename` into it as a create → move → rename lifecycle.

[↑ contents](#contents)

### new_commit

`built` · `prompt still spec-style, rewrite pending` · `separated models: no`

**The prompt, verbatim — `instruction.md`.** Still spec-style — rewrite pending.

```markdown
# Create a chain of commits in Jujutsu

## Background
In Jujutsu (`jj`), the working copy is always a commit. There is no staging area and no separate commit step: file edits land in the current commit as you make them.

## Requirements
You have an initialized Jujutsu repository at `/home/user/myproject`.
Your task is to create a linear chain of 3 commits starting from the current working copy.

1. Modify the **current** working copy commit to have the description `commit 1`, and create a file `file1.txt` containing `first`.
2. Create a child commit with the description `commit 2`. In this commit, create a file `file2.txt` containing `second`.
3. Create another child commit with the description `commit 3`. In this commit, create a file `file3.txt` containing `third`.

At the end of the task, your working copy should be on the commit with description `commit 3`.

## Constraints
- Project path: `/home/user/myproject`
- Start command: `cd /home/user/myproject`
- Port: N/A
- Do not create any bookmarks, just use the anonymous commits.
```

**How success is graded.** The stack is graded positionally with an anchored floor. `@` must be described exactly 'commit 3' and hold file3.txt containing 'third'; `@-` exactly 'commit 2' with file2.txt containing 'second'; `@--` exactly 'commit 1' with file1.txt containing 'first'. All three tests additionally require `@--` to BE the change the bootstrap handed over as its single working copy, resolved through the anchor's per-workspace key — because requirement 1 says to modify the current working copy rather than create a new commit, so the bottom of the stack is not the agent's to invent. So identification is by position relative to `@`, with only the bottom pinned by anchored change id. Nothing reads jj's English; descriptions are compared exactly and file contents by substring. The guard is the shared anchor fixture — this task deliberately ships no exemption file, since its one bootstrap commit is the graded object — plus the `@--` identity claim, which defeats a three-commit stack fabricated from `root()` and left beside the original.

**Scoring.** 3 tests total / 0 floored / 3 scored · anchored: **yes** · anchor exemptions: **none**

3 tests, 0 floored, 3 scored. Partial credit is 0, 0.333333 or 0.666667; 1.0 requires all three. A no-agent run scores 0.

**Known holes.** Everything above the anchor is positional: a correct three-commit stack that the agent finishes with one extra `jj new` fails all three scored tests.

**Repair queued.** §5: smoke tier or nowhere — 5/5 on all three models.

[↑ contents](#contents)

### new_insert

`built` · `prompt still spec-style, rewrite pending` · `separated models: no`

**The prompt, verbatim — `instruction.md`.** Still spec-style — rewrite pending.

```markdown
# Insert a New Commit in a jj Stack

## Background
You have a `jj` repository with a stack of commits at `/home/user/myproject`. The commit graph looks like this: `A` -> `B` -> `C`. You need to insert a new commit between `A` and `B` without breaking the descendants.

## Requirements
- Insert a new commit that is a child of the commit with the description "commit A" and a parent of the commit with the description "commit B".
- The new commit must contain a new file named `feature.txt` with the exact text `new feature\n`.
- The descendants (`B` and `C`) must be rebased on top of this new commit.
- The working copy should be left at the tip of the stack (the new version of `C`).

## Constraints
- Project path: `/home/user/myproject`
- Do not modify the contents of the existing commits `A`, `B`, or `C`.
- The final stack should be `A` -> `New Commit` -> `B'` -> `C'`.
```

**How success is graded.** The inserted commit is the agent's, so it has no anchored id; it is addressed as the single commit in `({commit A}..{commit B}) ~ {commit B}` where both endpoints are anchored change ids — i.e. by its position between two commits that cannot be forged. feature.txt must equal 'new feature\\n' both on disk and at that inserted commit, and the inserted commit's own diff (`jj diff --name-only`) must be exactly ['feature.txt']. Separately the ancestry of the anchored 'commit C' must contain A, B and C in the order C below B below A, with exactly one commit between A and B — which is how the auto-rebase of B and C is asserted. Commits are identified by anchored change id and by relation between anchored commits, never by `@`. Nothing reads jj's English; `jj diff --name-only` is a path list. The guard is the shared anchor fixture plus the between-two-anchored-commits addressing, which the docstring records as what killed a reworded parallel A → new → B → C stack built from `root()` that had scored full marks.

**Scoring.** 3 tests total / 0 floored / 3 scored · anchored: **yes** · anchor exemptions: **none**

3 tests, 0 floored, 3 scored. Partial credit is 0, 0.333333 or 0.666667; 1.0 requires all three. A no-agent run scores 0.

**Known holes.** Nothing asserts the inserted commit's description, and nothing asserts that B's and C's own contents survived the rebase — only their order and their change ids.

**Repair queued.** §5: smoke tier or nowhere — 5/5 on all three models.

[↑ contents](#contents)

### obslog_view

`built` · `prompt still spec-style, rewrite pending` · `separated models: no`

**The prompt, verbatim — `instruction.md`.** Still spec-style — rewrite pending.

```markdown
# Record the Evolution of the Working-Copy Change

## Background
In Jujutsu (`jj`), a change keeps its identity while the commit it points to is replaced every time the change is described, amended, or rebased. The superseded commits are not thrown away: the repository still remembers every commit a change has ever pointed to, even though those versions no longer show up in the ordinary log.

## Requirements
- The repository is at `/home/user/repo`. Its working-copy change has already gone through several revisions.
- Write a report of that change's complete evolution to `/home/user/obslog.txt`: every version the change has pointed to, from the commit it points to now all the way back to the version that first created it, each version identified by its commit ID and carrying its description.
- Leave the repository itself unchanged while you do it: no new commits, no edits to `file.txt`, no description changes. Anything that alters the working-copy change adds a further version to its evolution, which would make a report saved earlier incomplete.

## Constraints
- Project path: `/home/user/repo`
- Output file: `/home/user/obslog.txt`
- Exact formatting is not checked. The report is inspected for the commit ID and description of every version of the change, so any faithful rendering is accepted. Commit IDs may appear abbreviated (at least the first 8 characters) or in full.
```

**How success is graded.** The verifier recomputes the answer instead of storing it. It runs `jj evolog` at the change the bootstrap handed over — resolved by anchored change id from its 'v2' description, not at whatever `@` is — and collects every version's commit id and description first line. The saved report at /home/user/obslog.txt must exist, be non-empty, and (after ANSI escapes are stripped) contain the 8-character prefix of every one of those commit ids, plus every non-empty description they carry. Most of those versions are hidden from an ordinary log, so the ids cannot be produced without actually reading the evolution, and nothing is hardcoded. A fourth, floored test asserts the repository was left alone: file.txt still 'v2\\n', `@` still described 'v2', exactly two commits visible. Identification is by anchored change id; nothing positional. The report is matched by literal substring, but every substring is computed from the repository at verification time rather than written into the verifier. The guard is the shared anchor fixture plus grading the evolution of the anchored change, which the docstring records as what killed a `jj new -r 'root()'; jj describe; jj evolog >` fabrication that had passed every assertion.

**Scoring.** 4 tests total / 1 floored / 3 scored · anchored: **yes** · anchor exemptions: **none**

4 tests, 1 floored (test_repository_left_unchanged), 3 scored. Partial credit is 0, 0.333333 or 0.666667; 1.0 requires the floored test to pass too. A no-agent run scores 0.

*Floored — must pass, earns nothing:*

- `test_final_state.py::test_repository_left_unchanged`

**Known holes.** The report only has to \*contain\* the ids and descriptions, so any superset — dumping a wider log or the whole op log — passes; and the 'leave the repository alone' requirement is floored, so violating it caps rather than zeroes the score.

**Repair queued.** §5: smoke tier or nowhere — 5/5 on all three models.

[↑ contents](#contents)

### revert_file

`built` · `prompt still spec-style, rewrite pending` · `separated models: no`

**The prompt, verbatim — `instruction.md`.** Still spec-style — rewrite pending.

```markdown
# Revert and Restore Files in Jujutsu

## Background
You are working on a Python project managed with Jujutsu (`jj`). You've made several changes in your current working copy, but you realize that some of these changes were a mistake. You need to selectively revert and restore specific files to earlier states while keeping your other work intact.

## Requirements
1. You must discard the uncommitted changes to `config.py`, reverting it to its exact state in the parent commit.
2. You must restore the file `utils.py` to its state from a previous commit marked with the bookmark `v1.0`.
3. You must keep the uncommitted changes to `app.py` exactly as they are in the current working copy.
4. You must set the description of the current working-copy commit to exactly: `Restore configuration and utilities`

## Constraints
- Project path: `/home/user/myproject`
- Do not create any new commits or branches; modify only the current working-copy commit.
- Do not modify any other files in the repository.
```

**How success is graded.** All three scored tests first require `@` to still BE the working-copy commit the bootstrap handed over, resolved through the anchor's per-workspace key, because the task says to modify only the current working copy and create no new commits. Against that commit: config.py must contain 'DEBUG = False' and utils.py must equal exactly 'def helper(): return "v1"', each checked both at the commit via `jj file show` and on disk; and the commit's description must equal exactly 'Restore configuration and utilities'. The fourth, floored test checks that app.py on disk still holds the untouched working-copy change. Identification is by anchored change id (with `@` as the cold-CI fallback), never by offset. Nothing reads jj's English; contents are compared against literals. The guard is the shared anchor fixture plus the `@ == handover change` claim, which the docstring records as what killed a measured `jj new -r 'root()' -m "Restore configuration and utilities"` plus write-the-files solve that had scored 1.0.

**Scoring.** 4 tests total / 1 floored / 3 scored · anchored: **yes** · anchor exemptions: **none**

4 tests, 1 floored (test_app_py_unchanged), 3 scored. Partial credit is 0, 0.333333 or 0.666667; 1.0 requires all four. A no-agent run scores 0.

*Floored — must pass, earns nothing:*

- `test_final_state.py::test_app_py_unchanged`

**Known holes.** `@` must be exactly the handover change, so an otherwise-correct solve that leaves a fresh empty commit on top scores 0; and config.py is substring-checked rather than compared exactly.

**Repair queued.** §5: smoke tier or nowhere — 5/5 on all three models. §3 notes it subsumes `restore_file_from_parent`, which is cut.

[↑ contents](#contents)

### show_commit

`built` · `prompt still spec-style, rewrite pending` · `separated models: no`

**The prompt, verbatim — `instruction.md`.** Still spec-style — rewrite pending.

```markdown
# Inspecting Commits with Jujutsu

## Background
You have a Jujutsu (jj) repository at `/home/user/project` with a few commits. You need to create a script to easily show the Git-format diff of specific commits and use it to extract patches for two specific commits.

## Requirements
1. Create a bash script at `/home/user/project/show_commit.sh`.
2. The script must take a single argument: a Jujutsu revset.
3. Given a revset, the script must print that revision's details together with its diff, and the diff must be in Git patch format — the output must contain a `diff --git a/<path> b/<path>` header for each changed file.
4. Make the script executable.
5. Run your script for the revset `description(substring:"Add configuration file")` and redirect the output to `/home/user/project/add_config.patch`.
6. Run your script for the revset `description(substring:"Update configuration file")` and redirect the output to `/home/user/project/update_config.patch`.

## Constraints
- Project path: `/home/user/project`
- The script must be executable.
- The output files must contain the Git-format diff.
```

**How success is graded.** Four assertions over a script and two patch files, tied to commits by identity rather than by content. show_commit.sh must exist and be executable; run with the anchored change id of the bootstrap's 'Add configuration file' commit as its single argument it must exit 0 and print a `diff --git a/config.txt b/config.txt` header, a `+key=value` line, and the 8-character prefix of either that commit's anchored change id or its current commit id. add_config.patch and update_config.patch must exist, carry the expected diff header and +/- lines, and likewise carry the identity of the anchored commit they claim to describe — which is the whole point, because a git diff of identical content is byte-identical, blob hashes included, so text alone cannot tie a patch to a commit. Commits are identified by anchored change id, with the commit id resolved at verification time; nothing positional. Several assertions are literal substring matches, but over git diff text and jj id prefixes rather than jj prose. The guard is the shared anchor fixture plus that id requirement.

**Scoring.** 4 tests total / 0 floored / 4 scored · anchored: **yes** · anchor exemptions: **none**

4 tests, 0 floored, 4 scored. Partial credit is k/4 with a 0.75 cap on any failure. A no-agent run scores 0 — but the verifier's own docstring states the residual: test_script_exists_and_executable cannot be anchored, so an additive fabrication (or a bare `touch` + `chmod +x`) still collects 1 of 4, i.e. 0.25.

**Known holes.** One of the four scored tests asks only whether an executable file exists, so 0.25 is collectable without any repository work at all — stated deliberately in the verifier rather than papered over.

**Repair queued.** §5: smoke tier or nowhere — 5/5 on all three models.

[↑ contents](#contents)

### status_ignored

`built` · `prompt still spec-style, rewrite pending` · `separated models: no`

**The prompt, verbatim — `instruction.md`.** Still spec-style — rewrite pending.

```markdown
# Ignore and Untrack a File in Jujutsu

## Background
In Jujutsu (`jj`), files in the working copy are automatically tracked. If you create a file that should be ignored (like a build artifact or log file) and it gets tracked, simply adding it to `.gitignore` is not enough to remove it from the working-copy commit. You must also explicitly untrack it.

## Requirements
You have a Jujutsu repository at `/home/user/project`. It contains a file named `build.log` which is currently tracked by `jj`.

Your task is to:
1. Add `build.log` to the `.gitignore` file in the repository root so it is ignored.
2. Untrack `build.log` in Jujutsu so it is no longer tracked by the version control system.

## Constraints
- Project path: `/home/user/project`
- **Do not delete** the `build.log` file from the filesystem. It must remain in the `/home/user/project` directory.
```

**How success is graded.** The task is graded as the difference between untracking a file and never having tracked it. After one deliberate `jj status` snapshot: build.log must be absent from `jj file list -r @`; `::@ & files(root-file:"build.log")` must hold at least two commits; the most recent of them must not track build.log while its parent still does — i.e. it is the commit that removed it; build.log must still be on disk; and .gitignore must mention build.log both on disk and as recorded in the working-copy commit. Every scored test also requires the \*oldest\* build.log-touching ancestor to be the anchored 'initial commit' change, so the add-and-remove pair cannot both be the agent's. Identification is by anchored change id for the adding commit and by revset for the removing one; `@` is used only as 'the working copy now', which is what the task is about. Nothing reads jj's English — the old version scanned `jj status` lines and, on a clean working copy, its loop body never ran, so the test asserted nothing. The guard is the shared anchor fixture plus the anchored-adder claim, which the docstring records as what killed an add-then-untrack history fabricated from `root()` that had scored 1.0.

**Scoring.** 4 tests total / 1 floored / 3 scored · anchored: **yes** · anchor exemptions: **none**

4 tests, 1 floored (test_build_log_exists), 3 scored. Partial credit is 0, 0.333333 or 0.666667; 1.0 requires all four. A no-agent run scores 0.

*Floored — must pass, earns nothing:*

- `test_final_state.py::test_build_log_exists`

**Known holes.** `.gitignore` is only substring-checked for 'build.log', so an over-broad or negated rule passes, and the ≥2-commits check counts any two commits touching the path rather than the specific pair.

**Repair queued.** §5: smoke tier or nowhere — 5/5 on all three models, though the doc adds that if a second ignore-surface task is wanted this is the one to bring back, its verifier being the strongest of the three.

[↑ contents](#contents)
