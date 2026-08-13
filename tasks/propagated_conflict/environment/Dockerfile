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
LABEL Description="checkout-api: a rebased branch carrying one conflict that started in the middle of the stack."

# The whole bootstrap as one shell script. BuildKit's heredoc support is what
# makes this legal in a Dockerfile; the inner heredocs all terminate on `F`, so
# no line of file content may be exactly `BOOTSTRAP`.
#
# THE FIXTURE INVARIANTS THE PROMPT RESTS ON. The prompt is one line --
# "resolve the retry-backoff conflict where it started, keeping both sides, and
# leave the stack as the same four commits" -- and it names neither the file,
# nor the commit, nor the two symbols. Each of those is a definite description
# of exactly one thing only because the fixture is built this way. Changing any
# of the five below changes the task, not just its scenery:
#
#  1. EXACTLY ONE CONFLICTED PATH in the whole repository:
#     src/client/retry.py, a 2-sided conflict. That is what lets the prompt say
#     "the conflict" and mean something. Adding a second conflicted path
#     anywhere makes the request ambiguous.
#
#  2. THE CONFLICT HAS ONE ORIGIN, and it is not the first commit of the stack.
#     `make the retry budget configurable` is the second of the four; its own
#     diff is what collides with main. The two commits above it and the working
#     copy render conflicted purely by inheritance -- they add nothing to the
#     collision. So "where it started" names one commit while `jj log` shows
#     three conflicted ones, which is the whole discrimination.
#
#  3. THE UNION IS THE ONLY DEFENSIBLE RESOLUTION, and its line order is
#     forced. main RENAMES `TIMEOUT` to `REQUEST_TIMEOUT` in place; the stack
#     commit INSERTS `RETRY_BUDGET` on the line immediately after it. Measured
#     on jj 0.44.0: those two hunks abut and therefore conflict textually, while
#     being semantically disjoint -- so "keeping both sides" has exactly one
#     satisfying file content, with the renamed line first because that is the
#     line main edited in place. This is what pays for the prompt not naming
#     the two symbols, and it is the invariant most easily broken by editing
#     the fixture: separate the two edits by even one line of context and the
#     merge succeeds silently, leaving a task with no conflict in it.
#
#  4. NEITHER `:ours` NOR `:theirs` IS ACCIDENTALLY CORRECT. `:ours` keeps the
#     rename and drops `RETRY_BUDGET`, which additionally leaves the file
#     referring to an undefined name in `with_backoff`'s signature; `:theirs`
#     keeps the budget and reverts main's rename, breaking the call site main
#     updated. Both exit 0 and clear every conflict, so only the content
#     assertions can tell them from a real resolution.
#
#  5. THE HANDOVER `@` IS THE STACK TIP -- described and non-empty. This is a
#     D11 guard, not decoration. jj 0.44 silently abandons an empty, undescribed
#     working-copy commit the moment you `jj edit` or `jj new` elsewhere, and
#     printing nothing while doing it; `jj edit <the origin commit>` is the
#     most likely first move in a correct solve. A described, non-empty `@`
#     cannot be lost that way, which is why this task needs no
#     tests/anchor_exemptions.json at all.
#
# Each of the four stack commits also changes a DISJOINT set of paths, so
# "each still carries its own diff" is checkable without reading any content.
RUN <<'BOOTSTRAP' bash -euo pipefail
mkdir -p /home/user/checkout-api
cd /home/user/checkout-api
git init .
git config user.name "Priya Raman"
git config user.email "priya@checkout.example"
jj git init --colocate
jj config set --user user.name "Priya Raman"
jj config set --user user.email "priya@checkout.example"

mkdir -p src/api src/client tests

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
cat >config.toml <<'F'
[http]
base_url = "https://api.checkout.example"

[charges]
default_currency = "USD"
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


def post(path, payload, timeout=None):
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)
F
jj commit -m "extract the http client"

# The file the conflict will land in. `TIMEOUT` here is the name main renames
# and the line the stack commit inserts after -- invariant 3.
cat >src/client/retry.py <<'F'
import time

MAX_ATTEMPTS = 4
TIMEOUT = 5.0
BACKOFF_BASE = 0.2


def with_backoff(call, attempts=MAX_ATTEMPTS, sleep=time.sleep):
    delay = BACKOFF_BASE
    for attempt in range(attempts):
        try:
            return call(timeout=TIMEOUT)
        except OSError:
            if attempt == attempts - 1:
                raise
            sleep(delay)
            delay *= 2
F
cat >tests/test_retry.py <<'F'
from client.retry import with_backoff


def test_gives_up_after_max_attempts():
    calls = []

    def flaky(timeout=None):
        calls.append(timeout)
        raise OSError("connection reset")

    try:
        with_backoff(flaky, attempts=2, sleep=lambda _: None)
    except OSError:
        pass
    assert len(calls) == 2
F
jj commit -m "retry failed charges with backoff"
# A scaffolding handle for the branch point. Deleted before handover, so the
# repository the agent sees carries no bookmark that is not part of the story.
jj bookmark create fork-point -r @-

# ---- main moves underneath the branch: the rename ----
python3 - <<'PY'
p = "src/client/retry.py"
s = open(p).read()
s = s.replace("TIMEOUT = 5.0", "REQUEST_TIMEOUT = 5.0")
s = s.replace("call(timeout=TIMEOUT)", "call(timeout=REQUEST_TIMEOUT)")
open(p, "w").write(s)
PY
jj commit -m "give the http client an explicit request timeout"
jj bookmark create main -r @-

# ---- the retry-backoff stack, built on the pre-rename fork point ----

# 1 of 4. Touches neither retry.py nor anything main touched, so it rebases
# cleanly and stays clean: the stack's first commit is NOT the origin.
jj new fork-point -m "count retry attempts in the charge metrics"
cat >src/api/metrics.py <<'F'
RETRIES = {}


def record_retry(account_id):
    RETRIES[account_id] = RETRIES.get(account_id, 0) + 1
F

# 2 of 4. THE ORIGIN. `RETRY_BUDGET` goes in on the line directly after the
# one main renamed -- see invariant 3 for why the adjacency is the whole point.
jj new -m "make the retry budget configurable"
python3 - <<'PY'
p = "src/client/retry.py"
s = open(p).read()
s = s.replace("TIMEOUT = 5.0\n", "TIMEOUT = 5.0\nRETRY_BUDGET = 30.0\n")
s = s.replace(
    "def with_backoff(call, attempts=MAX_ATTEMPTS, sleep=time.sleep):",
    "def with_backoff(call, attempts=MAX_ATTEMPTS, budget=RETRY_BUDGET, sleep=time.sleep):",
)
open(p, "w").write(s)
c = open("config.toml").read()
open("config.toml", "w").write(c + '\n[retries]\nbudget_seconds = 30.0\n')
PY

# 3 of 4. Edits retry.py too, but down in the function body, well away from the
# constants. It therefore inherits the conflict without contributing to it --
# which is what stops "the commit that touches the conflicted file" from being
# a shortcut to the answer.
jj new -m "stop retrying once the budget is spent"
python3 - <<'PY'
p = "src/client/retry.py"
s = open(p).read()
s = s.replace(
    "    delay = BACKOFF_BASE\n    for attempt in range(attempts):\n",
    "    delay = BACKOFF_BASE\n    started = time.monotonic()\n    for attempt in range(attempts):\n"
    "        if time.monotonic() - started > budget:\n            raise TimeoutError(\"retry budget exhausted\")\n",
)
open(p, "w").write(s)
t = open("tests/test_retry.py").read()
t += '''

def test_stops_when_the_budget_is_spent():
    def slow(timeout=None):
        raise OSError("connection reset")

    try:
        with_backoff(slow, attempts=8, budget=0, sleep=lambda _: None)
    except TimeoutError:
        return
    raise AssertionError("expected the budget to stop the loop")
'''
open("tests/test_retry.py", "w").write(t)
PY

# 4 of 4, and the handover `@`: described and non-empty -- invariant 5.
jj new -m "note the retry budget in the changelog"
python3 - <<'PY'
c = open("CHANGELOG.md").read()
open("CHANGELOG.md", "w").write(c + "- retry budget, configurable per deployment\n")
PY
jj bookmark create retry-backoff -r @
jj status >/dev/null

# ---- the rebase that produced the state the agent is handed ----
# Measured: this reports "New conflicts appeared in 3 commits" and leaves
# src/client/retry.py 2-sided-conflicted in the second, third and fourth.
jj rebase -b retry-backoff -d main
jj bookmark delete fork-point
BOOTSTRAP

# Container contents:
#   - jj installed in /usr/local/bin/jj.
#   - /home/user/checkout-api -- colocated jj repo:
#       add the charge endpoint
#       extract the http client
#       retry failed charges with backoff
#       give the http client an explicit request timeout      <- main
#       count retry attempts in the charge metrics            <- stack 1/4, clean
#       make the retry budget configurable                    <- stack 2/4, CONFLICTED (origin)
#       stop retrying once the budget is spent                <- stack 3/4, conflicted by inheritance
#       note the retry budget in the changelog                <- stack 4/4, @, retry-backoff

# Where the agent starts: standing in the repository the task is about, which is
# the state a developer is actually in. The verifier names the absolute path, so
# nothing depends on this.
WORKDIR /home/user/checkout-api

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
