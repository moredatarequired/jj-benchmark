# Known Limitations

A record of known limitations in the benchmark's integrity and floor machinery, with the
decisions taken on each.

Recording three things we know about and have decided not to fix right now, so they are
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

## Exposure

None of this is reachable from CI today. The bounding fact on the floor holes is that CI
only ever runs `vacuity_floor.py --check`, never `--write`:
`.github/workflows/tasks.yml:202` is the sole invocation in the workflow, and `--check`
compares against the committed floor rather than replacing it, so a corrupted measurement
fails the build instead of being recorded. (The `--write` that appears at line 194 is text
inside an error message, not a command.) Secondarily, on the floor cases CI's `reward == 0`
assertion at line 193 fires first, and no shipped verifier uses skip or xfail. The real
exposure is a human running `--write` by hand, or a future task that introduces skips.
