---
name: jj-working-practices
description: The working discipline behind competent use of Jujutsu (jj) - an account of method rather than a command reference. It covers the rhythm that experienced jj work settles into, why the phases of that rhythm which produce nothing visible are the ones that decide whether the result is right, why a piece of work drifts from what was originally asked for, what a surprise partway through is worth, and the case for holding to a routine uniformly rather than case by case. No command listings or flag syntax; the part that transfers between repositories and versions is the method. Use this when you are working in a jj repository and want the judgement that underlies a steady working routine rather than trial and error.
---

# Working practices for a jj repository

This skill is about **method**, not about individual commands. It describes the routine
that makes work in a Jujutsu repository predictable: orient, plan, act in one small step,
confirm, repeat.

It is deliberately written without command listings. Invocations are specific to a
repository, a version, and a moment; the routine is the part that transfers. Treat what
follows as a description of a working temperament rather than as a procedure to execute.

---

## The loop

Every piece of work, however small, goes through the same four phases.

1. **Re-read the request.** Write down, in your own words, what the finished repository
   should look like.
2. **Orient.** Understand the current state before changing anything.
3. **Act once.** Make one change, not three.
4. **Confirm.** Look at the state again and compare it against what you wrote down in
   step 1.

Then repeat. The loop is short on purpose. A long stretch of unverified work is the
single most common way a straightforward piece of work goes wrong.

The four phases are not equally tempting. Phases 1 and 4 are the ones that get skipped,
because they produce nothing visible and they feel like delay. They are also the two that
determine whether the work is right, which is a fair summary of why the loop is written
down at all.

---

## Phase 1 - Re-read the request

Before starting, restate the request as a description of the **end state**. "The
repository should end up like this" is a target you can check yourself against later. A
restatement in terms of activity - "I will work on this area" - is not a target; it tells
you nothing about whether you have arrived.

Write the restatement down somewhere you will actually re-read. The value is not in the
composing, which is quick, but in having a fixed record that cannot drift while you work.
A remembered intention quietly reshapes itself to match whatever happened. A written one
does not.

Keep it short. One or two plain sentences is the right size: long enough to be specific,
short enough that re-reading it costs nothing and so actually happens.

---

## Phase 2 - Orient before you touch anything

Orientation is the habit of establishing what is true right now, rather than proceeding
from what was true earlier or what you assume is true. It is the cheapest phase and the
one most often skipped, because at the moment you skip it you are usually right.

Two ideas make it worth the time.

**Assumptions age badly.** A picture of the repository formed a few steps ago has been
invalidated by those very steps. Working from a stale picture feels identical, from the
inside, to working from a current one - which is precisely the problem.

**Observation is cheaper than repair.** Looking costs seconds. Undoing a change made on a
wrong premise costs considerably more, and costs most when the wrong premise is not
noticed until later.

Orient at the start of a piece of work, and again whenever you notice you are reasoning
about the repository from memory rather than from something you have just seen. That
second trigger is the one worth cultivating; the first is easy to remember and rarely the
one that saves you.

---

## Phase 3 - Act in one small step

### Prefer many small steps to one large one

A sequence of small steps has two properties a single large step does not: each step can
be checked on its own, and when something goes wrong you know exactly which step did it.
The overhead of the extra steps costs far less than the debugging you avoid.

Largeness is not only a matter of how much changes. A step is also large when it depends
on several things being simultaneously true, because then a failure gives you a set of
candidate causes rather than one.

### One intent per step

If you find yourself describing a single step with the word "and" - "this will do X *and*
Y" - that is usually two steps wearing one coat. Separating them costs a few seconds and
makes both halves checkable.

### Say what you are doing and why

Before each step that changes something, state the intent in one line: what you expect to
be true afterwards. This is not ceremony - it is the thing you will compare against in
Phase 4, and writing it down before you see the result stops you from rationalising
whatever happened.

Stating an expectation in advance has a second effect worth having. Expectations that are
vague survive contact with any outcome at all. Being made to write one down tends to
sharpen it, and a sharp expectation is one that a surprising result can actually
contradict.

---

## Phase 4 - Confirm the end state

Confirmation means looking, not assuming. Inspection is cheap enough to do after every
step, so there is no reason to skip it.

Compare what you find against the sentence you wrote in Phase 1. Not against your memory
of it, and not against a general sense that things went fine. The comparison is the whole
point; looking without comparing is a habit that feels like diligence and is not.

Be alert to the moment where you have looked at the result and are deciding what it
means. That is where a genuine surprise gets quietly reclassified as an expected outcome.
The defence is the written record from Phase 1: it was fixed before you had any stake in
the answer.

---

## When something does not go as expected

1. **Stop.** Surprise means your model of the situation is wrong somewhere. Continuing at
   speed from a wrong model adds distance between where you are and where you understand
   yourself to be.
2. **Look.** Establish what the state actually is now. Distinguish carefully between what
   you have **observed** and what you have **inferred** - under time pressure these feel
   the same, and confident inference is what produced the surprise.
3. **Read the message in full.** jj's diagnostics are specific and usually name both the
   problem and a way forward. Read the whole thing, including anything at the end that
   looks like a footnote; the hint is often the useful part.
4. **Re-plan.** Only once you know the current state, and why the previous step did not
   produce what you expected. A plan made before those two things are settled is a guess
   with better posture.

The instinct to be resolved here is the urge to recover speed - to make up for the
setback by moving faster afterwards. The setback is information, and it has already been
paid for; going faster mostly ensures it was paid for nothing.

---

## Finishing

Before declaring the work done:

- [ ] Re-read the original request one more time, in full.
- [ ] The repository state matches the end state you described in Phase 1.
- [ ] You have looked at that state, rather than concluded it from the steps you took.
- [ ] You can summarise the end state in one or two plain sentences.

That last point is the most useful check. If you cannot say plainly what the repository
now looks like, you do not yet know whether it is right, and the fluency of a summary is
a surprisingly good indicator of whether the underlying picture is clear.

---

## A note on the routine itself

The routine costs something. It asks for a written sentence before starting, a look
before acting, a stated expectation, and a look afterwards - on every step, including the
ones that obviously do not need it.

Applying it only to steps that look risky does not work, and not because risky steps are
hard to spot. It is that the judgement is made with exactly the confidence the routine
exists to check. Work that goes wrong rarely announces itself in advance; it is
characteristically the step that seemed too small to be worth confirming.

So the routine is worth following uniformly, and the cost is best understood as the price
of not having to decide, each time, whether this is one of the occasions that warrants
care.
