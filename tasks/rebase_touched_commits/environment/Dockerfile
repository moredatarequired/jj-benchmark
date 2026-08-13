FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl ca-certificates git python3 python3-pip bash && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Verifier dependencies, pinned and installed at build time so that
# tests/test.sh needs no network access at all. scripts/lint_tasks.py checks
# these pins against the ones tests/test.sh expects.
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip && \
    rm -rf /var/lib/apt/lists/* && \
    ( python3 -m pip install --break-system-packages --no-cache-dir \
          pytest==8.4.1 pytest-json-ctrf==0.3.5 || \
      python3 -m pip install --no-cache-dir \
          pytest==8.4.1 pytest-json-ctrf==0.3.5 )

RUN curl -fsSL https://github.com/jj-vcs/jj/releases/download/v0.44.0/jj-v0.44.0-x86_64-unknown-linux-musl.tar.gz | \
    tar -xz -C /usr/local/bin ./jj && \
    chmod +x /usr/local/bin/jj

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="any-task-builder"
LABEL Description="checkout-api: an operation log holding one multi-commit rebase among later, smaller operations."

# The whole bootstrap as one shell script. BuildKit's heredoc support is what
# makes this legal in a Dockerfile; the inner heredocs all terminate on `F`, so
# no line of file content may be exactly `BOOTSTRAP`.
#
# The task is to report which commits one past operation changed. Nothing is
# rewritten by the agent; the whole difficulty is that the answer is a property
# of the OPERATION LOG and is not readable off the current graph.
#
# THE FIXTURE INVARIANTS THE PROMPT AND THE VERIFIER REST ON:
#
#  1. EXACTLY ONE OPERATION IN THE BOOTSTRAP REPARENTS A COMMIT. That is the
#     structural signature of a rebase -- some surviving commit's set of PARENT
#     CHANGE IDS changes -- and it is how tests/test_final_state.py finds the
#     operation at verification time, rather than by matching jj's English
#     ("rebase commit ... and descendants").
#
#     Measured on jj 0.44.0, and the reason the signature is reparenting rather
#     than "the operation that rewrote the most commits": the `jj describe`
#     below rewrites THREE commits, because describing a commit rewrites all of
#     its descendants too. Four against three is a uniqueness this fixture
#     would be relying on by luck. Reparenting separates them outright -- the
#     describe reparents nothing.
#
#  2. THE REBASE MOVED FOUR COMMITS, which is more than a plausible guess
#     produces by accident, and it is NOT the most recent entry: six operations
#     follow it.
#
#  3. THE ANSWER IS NOT READABLE OFF THE CURRENT GRAPH. This is the invariant
#     that makes the task about the operation log at all, and it is the one a
#     careless edit removes. After the rebase the bootstrap makes a FIFTH commit
#     on the branch and moves `retry-backoff` onto it, so:
#         main..retry-backoff   -> 5 commits
#         main..@               -> 5 commits
#         main..                -> 5 commits
#         what the rebase changed -> 4 commits
#     Every cheap current-graph revset therefore over-answers by exactly one,
#     and the commit it wrongly includes is one that did not exist when the
#     rebase ran. If a future edit makes the branch and the rebase set coincide,
#     the task stops measuring anything.
#
#  4. THE REBASE IS CLEAN -- main only touches src/generated/, which the branch
#     never touches. A conflict here would change what the task is about.
#
#  5. THE HANDOVER `@` IS DESCRIBED AND NON-EMPTY. jj 0.44 silently abandons an
#     empty, undescribed working-copy commit when you leave it (the D11 case),
#     printing nothing. Writing the answer file into a described, non-empty `@`
#     cannot lose a bootstrap commit, which is why this task ships with no
#     anchor exemption file.
#
# ONE OPERATION IN THE BOOTSTRAP DOES REMOVE A COMMIT -- the `jj new fork-point`
# below leaves an empty, undescribed `@` behind and jj abandons it, silently.
# That is harmless here BECAUSE the verifier keys on reparenting rather than on
# disappearance; it is recorded so that nobody later "fixes" it and assumes the
# log is disappearance-free.
RUN <<'BOOTSTRAP' bash -euo pipefail
mkdir -p /home/user/checkout-api
cd /home/user/checkout-api
git init .
git config user.name "Priya Raman"
git config user.email "priya@checkout.example"
jj git init --colocate
jj config set --user user.name "Priya Raman"
jj config set --user user.email "priya@checkout.example"

mkdir -p src/api src/client src/generated

cat >src/api/charge.py <<'F'
from decimal import Decimal

from client.http import post


def charge(account_id, amount, currency="USD"):
    payload = {
        "account_id": account_id,
        "amount": str(Decimal(amount)),
        "currency": currency,
    }
    return post("/v1/charges", payload)
F
cat >CHANGELOG.md <<'F'
# Changelog

## Unreleased
- charge endpoint
F
jj commit -m "add the charge endpoint"

cat >src/client/http.py <<'F'
import json
import urllib.request

BASE_URL = "https://api.checkout.example"


def post(path, payload):
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)
F
cat >src/generated/api_types.py <<'F'
# Generated from schema 2.3. Do not edit by hand.

CHARGE_FIELDS = ("account_id", "amount", "currency")
F
jj commit -m "extract the http client"
# Scaffolding handle for the branch point; deleted before handover.
jj bookmark create fork-point -r @-

# ---- main moves underneath the branch. Only src/generated/, so the rebase
# ---- that follows is clean -- invariant 4.
cat >src/generated/api_types.py <<'F'
# Generated from schema 2.4. Do not edit by hand.

CHARGE_FIELDS = ("account_id", "amount", "currency", "request_id")
REFUND_FIELDS = ("charge_id", "amount")
F
jj commit -m "regenerate the api client from the 2.4 schema"
jj bookmark create main -r @-
jj bookmark create release/2.4 -r 'description(substring:"extract the http client")'

# ---- the retry-backoff branch: four commits off the fork point ----
jj new fork-point -m "retry failed charges with backoff"
cat >src/client/retry.py <<'F'
import time

MAX_ATTEMPTS = 4


def with_backoff(call, attempts=MAX_ATTEMPTS, sleep=time.sleep):
    delay = 0.2
    for attempt in range(attempts):
        try:
            return call()
        except OSError:
            if attempt == attempts - 1:
                raise
            sleep(delay)
            delay *= 2
F
jj new -m "cap the retry budget per charge"
python3 - <<'PY'
p = "src/client/retry.py"
s = open(p).read().replace("MAX_ATTEMPTS = 4", "MAX_ATTEMPTS = 4\nRETRY_BUDGET = 30.0")
open(p, "w").write(s)
PY
jj new -m "surface retry counts in the charge response"
python3 - <<'PY'
p = "src/api/charge.py"
s = open(p).read().replace('    return post("/v1/charges", payload)',
                           '    response = post("/v1/charges", payload)\n'
                           '    response["retries"] = 0\n    return response')
open(p, "w").write(s)
PY
jj new -m "note the retry behaviour in the changelog"
python3 - <<'PY'
c = open("CHANGELOG.md").read()
open("CHANGELOG.md", "w").write(c + "- failed charges are retried with exponential backoff\n")
PY
jj bookmark create retry-backoff -r @
jj status >/dev/null

# ---- THE OPERATION THE TASK IS ABOUT: four commits move onto main ----
jj rebase -b retry-backoff -d main
jj bookmark delete fork-point

# ---- and then smaller work, so the rebase is not the last entry.
# A describe (which rewrites the described commit AND its two descendants --
# see invariant 1), a fifth commit on the branch, a bookmark move onto it
# (invariant 3), and a second describe.
jj describe -r 'description(substring:"cap the retry budget per charge")' \
    -m "cap the retry budget at 30 seconds per charge"
jj new -m "start on the settlement report"
cat >src/api/settlement.py <<'F'
def summarise(charges):
    return {"count": len(charges), "total": sum(c["amount"] for c in charges)}
F
jj status >/dev/null
jj bookmark set retry-backoff -r @
jj describe -m "start on the daily settlement report"
BOOTSTRAP

# Container contents:
#   - jj installed in /usr/local/bin/jj.
#   - /home/user/checkout-api -- colocated jj repo:
#       add the charge endpoint
#       extract the http client                              <- release/2.4
#       regenerate the api client from the 2.4 schema        <- main
#       retry failed charges with backoff                    <- moved by the rebase
#       cap the retry budget at 30 seconds per charge        <- moved by the rebase
#       surface retry counts in the charge response          <- moved by the rebase
#       note the retry behaviour in the changelog            <- moved by the rebase
#       start on the daily settlement report                 <- made AFTER it; @, retry-backoff
#   - the rebase sits six operations back from the head of the operation log.

WORKDIR /home/user/checkout-api

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
