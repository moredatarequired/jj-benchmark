#!/bin/bash
# Use this file to install test dependencies and run the tests.
# It will be copied to /tests/test.sh and run from the working directory.

# There is nothing to install. pytest==8.4.1 and pytest-json-ctrf==0.3.5 are
# baked into every task image at build time (see environment/Dockerfile), and
# task.toml sets [verifier] network_mode = "no-network", so this script runs
# with no route off the container at all.
#
# It used to bootstrap uv from astral.sh and resolve three packages out of pypi
# on every single trial. When that stalled -- and the pypi path out of these
# containers stalls often -- no ctrf.json was ever written and harbor recorded
# reward 0 with no error, which is indistinguishable from the agent genuinely
# failing the task. A verifier that needs the network in order to say "no"
# cannot be trusted when it says "no".
mkdir -p /logs/verifier

# From here on a reward file exists no matter what happens next. harbor reads
# /logs/verifier/reward.txt and nothing else; an absent or empty file raises
# out of harbor/verifier/verifier.py, and a *present* one is taken at face
# value. So the provisional value is written first and can only be improved on.
#
# verifier_error.txt is the flag that says "this 0 is not a measurement". The
# scorer below deletes it when it completes. If anything is still holding it at
# the end of this script, ctrf.json gets moved aside -- that absence is what
# scripts/check_run_results.py already classifies as ERRORED-INFRA rather than
# as a legitimate reward 0, which is the project rule for a verifier that
# never delivered a verdict.
echo 0 > /logs/verifier/reward.txt
echo "the verifier did not finish scoring, so reward 0 is not a measurement" \
  > /logs/verifier/verifier_error.txt

# CTRF produces a standard test report in JSON format which is useful for logging.
python3 -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_final_state.py -rA
pytest_status=$?

# Partial credit, read back out of the CTRF report pytest just wrote.
#
# The naive score -- summary.passed / summary.tests -- is NOT a measure of how
# much of the task the agent did. It is the fraction of assertions that happen
# to hold, and a good many of them hold in the untouched bootstrap image: 21 of
# the 53 tasks pass at least one test with no agent, and undo_mistaken_rebase
# passes 4 of its 6 by design (its correct end state IS the bootstrap state;
# only the operation log tells a real solve apart). Awarding the raw fraction
# would hand every model 0.667 there for doing nothing.
#
# So the tests that pass without an agent are excluded BY NAME, from both the
# numerator and the denominator:
#
#     credit = (passed tests not in the floor) / (tests not in the floor)
#
# The floor is the set of test names in tests/vacuity_floor.json, which rides
# along in the same tests/ directory harbor copies to /tests -- that is what
# lets this script stay byte-identical across all 53 tasks
# (scripts/lint_tasks.py enforces that). Those names are measured by
# scripts/vacuity_floor.py against the untouched image and re-measured in CI
# with --check; they are never hand-written.
#
# Excluding by name rather than subtracting a count is what makes a nop agent's
# 0 structural instead of arithmetic: the only tests it passes are the floored
# ones, so its numerator is empty by construction. It also means partial credit
# tracks the work actually done -- on undo_mistaken_rebase, an agent that
# performed the rebase but never undid it passes 1 of the 2 scored tests and
# earns 0.5, where subtracting the count of 4 would have called that zero.
python3 - "$pytest_status" <<'PY'
"""Turn the CTRF report into /logs/verifier/reward.txt. stdlib only, no network."""

import json
import os
import sys

REWARD = "/logs/verifier/reward.txt"
ERROR = "/logs/verifier/verifier_error.txt"
CTRF = "/logs/verifier/ctrf.json"
FLOOR = "/tests/vacuity_floor.json"

status = int(sys.argv[1])


def finish(reward, why):
    """Write the reward and clear the did-not-finish flag."""
    with open(REWARD, "w") as handle:
        handle.write(reward + "\n")
    print("reward %s: %s" % (reward, why))
    try:
        os.remove(ERROR)
    except OSError:
        pass
    raise SystemExit(0)


def unscorable(why):
    """Leave the provisional 0 and the flag in place; the shell escalates."""
    with open(ERROR, "w") as handle:
        handle.write(why + "\n")
    print("VERIFIER ERROR: %s" % why)
    raise SystemExit(0)


def short(name):
    """The test function name, which is the scoring key.

    CTRF records pytest's nodeid (ctrf/TestObject.py), e.g.
    "test_final_state.py::test_topology_restored", with any parametrize id
    stripped. The path part is relative to pytest's rootdir, so it can move if
    the verifier is ever invoked from a different directory; the function name
    cannot. There is exactly one test file per task, so the function name is
    unique on its own -- and this scorer checks that rather than assuming it.
    """
    return name.rsplit("::", 1)[-1]


# Exit 0 is the only thing that earns a full mark, and it is written as the
# exact integer 1 rather than 1.0. Every consumer that tests `reward >= 1.0`
# or `reward === 1.0` -- scripts/check_run_results.py, site/scripts/
# compute-tasks.ts, harbor's analyze/analyzer.py, harbor's pass@k -- sees
# byte-for-byte what the old script wrote.
if status == 0:
    finish("1", "pytest exited 0, every test passed")

# pytest exited non-zero. Either some tests failed (a real, scorable partial
# result) or pytest never got far enough to say (not scorable at all).
try:
    with open(CTRF) as handle:
        results = json.load(handle)["results"]
    reported = results["tests"]
    summary = results.get("summary") or {}
except (OSError, ValueError, KeyError, TypeError) as exc:
    unscorable(
        "pytest exited %d and left no readable CTRF report at %s (%s)"
        % (status, CTRF, exc)
    )

# name -> status, keyed by test function name. Anything other than "passed"
# counts against the agent, including "skipped" and "pending".
outcome = {}
for test in reported:
    name = test.get("name")
    if not isinstance(name, str) or not name:
        unscorable("the CTRF report contains a test with no name; names are the scoring key")
    key = short(name)
    if key in outcome:
        unscorable(
            "the CTRF report contains two tests named %r; names are the scoring "
            "key, so they have to be unique" % key
        )
    outcome[key] = test.get("status")

total = len(outcome)
if total <= 0:
    unscorable(
        "pytest exited %d having reported 0 tests, so nothing was verified" % status
    )

# summary.tests is derived from the same list, so a disagreement means the
# report itself is inconsistent and neither number can be trusted.
reported_total = summary.get("tests")
if isinstance(reported_total, int) and not isinstance(reported_total, bool):
    if reported_total != total:
        unscorable(
            "the CTRF report is inconsistent: summary.tests is %d but it lists "
            "%d test(s)" % (reported_total, total)
        )

# The floor file. A missing, stale or inconsistent one is NOT treated as an
# empty floor -- that would silently award vacuous credit, which is the whole
# failure this scheme exists to prevent. It falls back to the strict
# pre-partial-credit verdict instead, and says so loudly.
try:
    with open(FLOOR) as handle:
        floor_data = json.load(handle)
    floor_names = floor_data["passes_without_agent"]
    floor_total = floor_data["tests"]
except (OSError, ValueError, KeyError, TypeError) as exc:
    finish(
        "0",
        "no usable %s (%s), so this trial is scored strictly: pytest failed, "
        "so reward 0 with no partial credit. Regenerate the floor file with "
        "scripts/vacuity_floor.py --write." % (FLOOR, exc),
    )

if not isinstance(floor_names, list) or not all(
    isinstance(name, str) and name for name in floor_names
):
    finish(
        "0",
        "%s passes_without_agent is not a list of test names; scored strictly"
        % FLOOR,
    )

floor = set(short(name) for name in floor_names)
if len(floor) != len(floor_names):
    finish("0", "%s lists the same test twice; scored strictly" % FLOOR)

if floor_total != total:
    finish(
        "0",
        "%s was measured against %r tests but this run reported %d, so the "
        "floor is stale and partial credit is not trustworthy; scored "
        "strictly. Re-run scripts/vacuity_floor.py --write."
        % (FLOOR, floor_total, total),
    )

# A floored name that the report does not contain would silently shrink the
# denominator by less than intended -- the count check above cannot see it,
# because a renamed test keeps the count the same. Refuse to score instead.
absent = sorted(floor - set(outcome))
if absent:
    finish(
        "0",
        "%s names test(s) this run never reported: %s. The floor does not "
        "describe this verifier any more, so partial credit would be scored "
        "against the wrong denominator; scored strictly. Re-run "
        "scripts/vacuity_floor.py --write." % (FLOOR, ", ".join(absent)),
    )

scored = sorted(set(outcome) - floor)
if not scored:
    finish(
        "0",
        "the floor covers all %d test(s): nothing here distinguishes a solve "
        "from the untouched bootstrap state. Fix the verifier, do not score "
        "it." % total,
    )

passed = [name for name in scored if outcome[name] == "passed"]
credit = len(passed) / float(len(scored))

# A floored test that FAILED is not penalised by the fraction -- it is not in
# the denominator. That is the deliberate trade of scoring by name, so say it
# out loud in the log rather than leaving it to be discovered.
broke = sorted(name for name in floor if outcome.get(name) != "passed")
note = ""
if broke:
    note = ". NOTE: floored test(s) %s failed, which this score does not " \
        "penalise -- see the CTRF report" % ", ".join(broke)

if credit <= 0:
    finish(
        "0",
        "none of the %d scored test(s) passed (%d floored test(s) excluded)%s"
        % (len(scored), len(floor), note),
    )

# pytest exited non-zero, so this is not a pass however the arithmetic lands --
# every scored test can pass while a floored guard test fails. Cap strictly
# below 1 so that can never be mistaken for a solve by a `>= 1.0` consumer.
credit = min(credit, (len(scored) - 1) / float(len(scored)))
if credit <= 0:
    finish(
        "0",
        "%d of %d scored test(s) passed, but pytest failed, so this is not a "
        "solve and there is no partial credit left to award%s"
        % (len(passed), len(scored), note),
    )

finish(
    "%.6f" % credit,
    "%d of %d scored test(s) passed (%s); %d test(s) excluded as passing with "
    "no agent (%s)%s"
    % (
        len(passed),
        len(scored),
        ", ".join(passed) or "none",
        len(floor),
        ", ".join(sorted(floor)) or "none",
        note,
    ),
)
PY

# The scorer clears verifier_error.txt on every path where it reached a
# verdict, including the deliberately conservative ones. A surviving flag means
# it crashed or was killed -- so make that unmistakable instead of leaving a 0
# that reads like an honest failure.
if [ -f /logs/verifier/verifier_error.txt ]; then
  echo "VERIFIER DID NOT SCORE THIS TRIAL: $(cat /logs/verifier/verifier_error.txt)"
  # scripts/check_run_results.py keys ERRORED-INFRA off the absence of
  # verifier/ctrf.json. Move the unusable report aside rather than deleting it,
  # so the evidence still lands in the trial directory for a human.
  if [ -f /logs/verifier/ctrf.json ]; then
    mv /logs/verifier/ctrf.json /logs/verifier/ctrf.json.unscored
  fi
  # harbor ignores this exit status (harbor/verifier/verifier.py discards the
  # ExecResult), but CI runs this script directly and must fail on it.
  exit 1
fi
exit 0
