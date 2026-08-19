# Known Limitations

A record of known limitations in the benchmark's integrity and floor machinery, and in
what the task images tell the agent, with the decisions taken on each.

Recording four things we know about and have decided not to fix right now, so they are
written down somewhere other than a review thread.

## 1. Three latent skip-handling holes in `scripts/vacuity_floor.py`

The guard added in #36 refuses a measurement that proves nothing. Three shapes still get
through it. Each was reproduced against `squash_range`, whose committed floor is 3 of 8.

**One skipped floor member writes 2/8 against a true 3/8, at exit 0.** This is an
otherwise normal run: bodies execute, nothing errors in setup, and only a minority of the
file is skipped, so no rule fires. But a skipped test is recorded exactly like a failing
one — it stays out of `passes_without_agent` — so skipping the genuine floor member
`test_target_commit_survived` drops the measured floor to 2 while the true floor is still
3, and `--write` records it and exits 0. Under-recording is the dangerous direction. The
floor is subtracted to form the scored denominator, so a floor that is too low means every
model is graded out of assertions a do-nothing agent already passes, and the task looks
harder than it is.

**Seven skips plus one non-skipped entry writes floor 0/8 when that entry fails and 1/8
when it passes, both at exit 0.** A single non-skipped entry is enough to defeat the
all-skipped rule, since that rule only fires when *every* entry is skipped, so the run is
accepted. When that entry fails, nothing passed, so the floor is written as 0 — the same
zero the all-skipped rule exists to refuse, reached by adding a single failure to the
report. When it passes, the result is the more dangerous of the two shapes: seven skips
plus one passing test — `test_target_commit_survived`, a genuine floor member — was
accepted and written as floor 1/8 at exit 0, against a true floor of 3. A floor of 0 at
least looks like nothing happened; 1 reads as a real measurement of a task with one test a
do-nothing agent passes, and nothing in the recorded file distinguishes it from one. The
two floor members that were skipped are dropped from `passes_without_agent`, and
`tests/test.sh` then scores `squash_range` out of 7 assertions instead of 5.

**A `pending` status entry bypasses the all-skip rule.** It is not that neither rule looks
at `pending`: `errored_in_setup()` looks at it deliberately, whitelisting it alongside
`passed` and `skipped` (`status in ("passed", "skipped", "pending")`), so a `pending` entry
with no `raw_status` is not treated as a body that never ran. The all-skip rule is the one
that does not consider it: it counts only `status == "skipped"`, so one `pending` entry
makes an otherwise all-skipped report fail the `len(skipped) == len(tests)` test and pass
through. Demonstrated with a hand-edited report — all skipped plus one `pending` wrote
floor 0/8 at exit 0. What is unreachable is the *producer*, not the bypass: in the pinned
`pytest-json-ctrf==0.3.5`, `TestStatus.PENDING` is only a transient initial value in
`TestObject.__init__`, overwritten by `set_status()` before the object is ever serialized,
so no report the pinned plugin emits carries it.

## 2. A docstring asymmetry worth resolving when someone next touches the file

The docstring argues that no fraction of non-executing tests makes the remainder a
measurement, and then sets the setup-error threshold at one but the skip threshold at
all. A skipped body did not run either, so the argument as written does not support the
two different thresholds. Either the argument or one of the thresholds should give. Not
urgent, but whoever is next in that file should pick one.

## 3. `jj op abandon` defeats the bootstrap integrity anchor

A correct solve followed by `jj op abandon` scores 0. The anchor looks for the handover
operation in the op log, does not find it, and declares the repository rebuilt.

The anchor's own message used to claim no agent can remove that entry. That is false on jj
0.44, and the message has since been corrected to say so.
Measured on the pinned 0.44.0 binary in a task image, abandoning the third entry of the
log, numbering `@` as the first, printed `Abandoned 1 operations and reparented 2
descendant operations.` The log is linear, so the descendant count is the number of entries
above the abandoned one. The two descendants came back with new operation ids while every
ancestor kept its own — so the survivors really are reparented, not merely relisted. Every
commit id in the repo was byte-identical before and after, so it does this with no commit
loss.

The range spelling takes the whole log, not one entry. `jj op abandon ..@-` is the form
jj's own `jj util gc --help` recommends — "To garbage-collect old operations and the
commits/objects referenced by them, run `jj op abandon ..<some old operation>` before `jj
util gc`." — so it is the spelling in front of an agent reaching for the op log at all.
Measured on the `operation_recovery` image, whose log carries 12 entries including root,
`jj op abandon ..@-` left a two-entry log with `@` sitting directly on root, printing
`Abandoned 10 operations and reparented 1 descendant operations.` Every commit id was
byte-identical before and after, so the entire history stays and only the record of how it
got there goes. Two single-operation forms behave the same way, each leaving 11 of the 12
entries standing. `jj op abandon @-` printed `Abandoned 1 operations and reparented 1
descendant operations.` The form `jj op abandon <id>`, aimed at the fifth entry, printed
`Abandoned 1 operations and reparented 4 descendant operations.`

Abandoning delists an operation rather than deleting it. After `jj op abandon <id>` that id
is gone from `jj op log`, and `jj op show <id>` still resolves it at exit 0 and prints its
full diff. Removal from disk is `jj util gc`'s job: `jj util gc --expire=now` — `now` is
the only value `--expire` accepts — writes nothing to either stream and exits 0, and after
it the same `jj op show <id>` exits 1 with `Error: No operation ID matching "<id>"`. The
silence is worth knowing: nothing in the output marks the removal as having happened. The
anchor's failure is exact about what it checks — `tests/anchor.py` builds its operation set
from `jj op log` and asserts membership, and the handover entry is no longer listed there —
and "remove that entry" is wrong read as gone from the repository.

**Decision recorded: accept as a known limitation rather than loosen the check.** The
handover-operation check is the one assertion that is never exemptable, and — the part
that forces the decision — a change-id-only exemption list *cannot express* this escape.
Every entry in `anchor_exemptions.json` resolves to a change id at load time
(`Exemptions.may_disappear` and `.may_be_divergent` are both change id → reason maps), but
the thing that vanishes here is an operation-log entry, not a change id. There is no
exemption that could permit `jj op abandon` without permitting a wipe-and-rebuild
wholesale, which is a worse failure than a legitimate solve being scored 0 after an
unusual command.

It is most reachable on the two operation-log tasks, `operation_recovery` and
`undo_mistaken_rebase`: both ask the agent to put the repository back to an earlier state,
so both invite operating on the op log directly, and `jj op abandon` is a plausible thing
to reach for there in a way it is not on the other twenty-two.

The anchor's message text has been corrected: it no longer claims the operation log is
append-only or that no agent can remove the handover entry, and it now names `jj op
abandon` as the other way this check can fail. What the check does is unchanged — the
limitation above stands. The correction landed as its own small PR rather than riding
along with a task change, because the file is byte-identical across every task.

## 4. What the `/home/user/AGENTS.md` note in every task image costs

Every task image now writes `/home/user/AGENTS.md` and delivers it to the agent under the
name `CLAUDE.md`, one directory above the project. The whole of it is a `# Contributing`
heading and two sentences: the project uses Jujutsu; `git` should not be used for it.
Five things go with it that no run artifact records, so they are written down here at more
length than the note itself.

**`main` now builds informed images, so the uninformed sweep is no longer on `main`.**
`results/2026-08-12-3model-baseline.md` is the one sweep with a file of its own here that
was measured with no such note in the tree, and no future sweep from `main` is comparable to
it. Little turns on that particular file — its own header already retires it, because it
measured 53 tasks and the suite is 24 — but the informed/uninformed difference is now a
second reason on top of the task-set difference, and it applies to every sweep after this
one, not just to that one. It also settles a decision that was left open in writing:
`results/2026-08-14-baseline-24.md:21-22` says "whether the informed arm ships as a change to
the suite is a separate and still-open decision". This change is that decision, taken, and
the baselines the current tree is comparable to are the informed ones —
`results/2026-08-14-baseline-24.md` and arm A of `results/2026-08-16-skill-ab.md`.

**Delivery is coupled to two things nothing tests.** The first is the `WORKDIR`. No
`task.toml` sets `[environment] workdir`, so the agent inherits the image's working
directory, and all 24 Dockerfiles set that to the project directory inside `/home/user` —
the layout the capture below was taken against. A working directory of `/`, which is what
these images had before the `WORKDIR` lines were added, is not that layout, and nothing has
been measured about what reaches the agent from there. No verifier and no lint check asserts
where the `WORKDIR` points; the check added alongside this section asserts only that the
block writing the note is present and identical across the 24. The second is one harness's
file-discovery rules. The filename is what makes the note arrive: captured on Claude Code
2.1.235 inside the built task image, `/home/user/CLAUDE.md` arrives in the assembled system
prompt under `Contents of /home/user/CLAUDE.md (project instructions, checked into the
codebase):`, while a bare `AGENTS.md` is not delivered at either position — so an adapter
that looks for `AGENTS.md` only at the project root receives nothing. Reproduced on Claude
Code 2.1.42 against a replica of the layout. *How* the harness locates the file was not
measured, only that it arrives; the capture is recorded at
`results/2026-08-14-baseline-24.md:44-52`. Two versions of one harness is the whole of the
evidence.

**The note does not buy compliance.** `results/2026-08-16-skill-ab.md:97` records
`fileset_rollback` taking the git route in 4 of 4 arm-A attempts — `git restore` / `git
checkout HEAD --` plus `rm`, invoking jj zero times, verified command by command — in
exactly this informed condition, with three of the four still scoring 1.0. Being told which
tool the project uses is not the same as using it.

**The one substantive sentence is discriminating information for the tasks whose designed
trap is the git route.** Two tasks are specifically exposed. On `bookmark_left_behind`, the
A/B's own notes have it losing one of its two traps by fiat; that job was never archived, so
that claim is *not* reproducible from this repository and is recorded here as testimony
rather than measurement. What this repository does record is adjacent and checkable: the
verifier deliberately grades the colocated-git push route as a full solve
(`tasks/bookmark_left_behind/tests/test_final_state.py:47`), so a categorical "do not use
`git`" steers the agent off a route the task itself treats as correct. On
`git_fetch_remote`, the solve is spelled `jj git …` — `jj git fetch` and `jj git push`, in a
repository the bootstrap made with `jj git clone`
(`tasks/git_fetch_remote/environment/Dockerfile:51`) — which sits awkwardly against a
sentence saying `git` should not be used. Nothing measured shows it being hurt: it is a
ceiling task in four of the A/B's six arms (1.000 in A, B, D and E;
`results/2026-08-16-skill-ab.md:116`).

**No trial record says the note was there.** The graded prompt is the `task_description` in
`bootstrap/task.json`, byte-identical to `instruction.md` and checked as such by
`scripts/lint_tasks.py`; the note is in neither, and in no per-trial artifact. It exists
only in the image, which means a reader comparing two run records cannot tell an informed
arm from an uninformed one from the artifacts. Where it is written down at all, it is
because a person put it into a run's provenance paragraph by hand
(`results/2026-08-16-skill-ab.md:149`, which records the note's sha256 and the symlink).

**Decision recorded: ship the note and carry these five costs rather than drop it.** The
measurement that motivates it is in `results/2026-08-14-baseline-24.md:54-56`: the informed
images ran `jj` at least once in 261 of 273 scored trials, against 12 of 48 in the
uninformed control of a one-trial-per-cell A/B run the same day, and a jj benchmark whose
agents mostly use git measures something else. What is closed is only the drift mode. The
note is duplicated by hand into all 24 Dockerfiles with no shared base image, so
`scripts/lint_tasks.py` (`check_conventions_block`, `check_conventions_identical`) now
requires the block exactly once per task and byte-identical across the 24 — a half-applied
edit would otherwise leave the suite silently split into informed and uninformed halves with
green CI. Nothing above is closed by that check.

## Exposure

None of the first three above is reachable from CI today; section 4 states its own exposure
inline. The bounding fact on the floor holes is that CI only ever runs
`vacuity_floor.py --check`, never `--write`:
`.github/workflows/tasks.yml:243` is the sole invocation in the workflow, and `--check`
compares against the committed floor rather than replacing it, so a corrupted measurement
fails the build instead of being recorded. (The `--write` that appears at line 235 is text
inside an error message, not a command.) Secondarily, on the floor cases CI's `reward == 0`
assertion at line 234 fires first, and no shipped verifier uses skip or xfail. The real
exposure is a human running `--write` by hand, or a future task that introduces skips.
