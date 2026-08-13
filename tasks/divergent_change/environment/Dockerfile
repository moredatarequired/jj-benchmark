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
LABEL Description="checkout-api: one change recorded twice, and a bookmark that cannot decide which one it means."

# The whole bootstrap as one shell script. BuildKit's heredoc support is what
# makes this legal in a Dockerfile; the inner heredocs all terminate on `F`, so
# no line of file content may be exactly `BOOTSTRAP`.
#
# THE FIXTURE INVARIANTS THE PROMPT RESTS ON. The prompt is one line -- "one
# commit is showing twice -- keep the copy with the tests, drop the other, and
# repoint idempotency at it" -- and it names neither the commit, nor the file,
# nor either version. Each of those is a definite description of exactly one
# thing only because the fixture is built this way.
#
#  1. EXACTLY ONE DIVERGENT CHANGE in the whole repository. That is what lets
#     the prompt say "one commit is showing twice" and mean something. A second
#     divergent change makes the request ambiguous, and this is checked in
#     bootstrap/test_initial_state.py rather than trusted.
#
#  2. BOTH SIDES CARRY THE SAME DESCRIPTION, `add idempotency key to charge
#     requests`. They are two versions of ONE change, which is what jj is
#     saying when it prints the change id twice with `(divergent)` on both. If
#     the descriptions differed the log would read as two commits rather than
#     one commit twice, and the prompt would be describing something else.
#
#  3. tests/test_charge.py IS THE REPOSITORY'S ONLY TEST FILE, and exactly one
#     of the two versions has it. That is what "the copy with the tests"
#     identifies, and it identifies the same side the verifier grades. The
#     other version differs in one further way -- it does not carry the
#     CHANGELOG line either -- so a solve cannot pass by keeping the right side
#     for the wrong reason.
#
#  4. THE OFFSETS ARE THE TRAP WAY ROUND. `X/N` indexes every version ever
#     recorded for change id X, hidden ones included, NEWEST FIRST -- so the
#     version built LAST is `/0`. Here that is the version WITHOUT the tests.
#     An agent that reasons "mine is /0, theirs is /1", or that hard-codes
#     either offset, keeps the wrong copy. This is asserted in
#     bootstrap/test_initial_state.py so that a rebuild which flips the order
#     fails loudly at build time instead of quietly removing the trap.
#     Nothing in tests/test_final_state.py mentions an offset: it grades by
#     `change_id(X)` and by content.
#
#  5. RESOLVING THE DIVERGENCE DOES NOT RESOLVE THE BOOKMARK. Measured on jj
#     0.44.0: after `jj abandon <the other version>` the `idempotency` bookmark
#     is still conflicted, because one of its recorded targets is the
#     now-hidden common ancestor. `jj bookmark set idempotency -r <survivor>`
#     is a second, separate act -- which is why the prompt asks for it and why
#     the verifier scores it separately.
#
#  6. THE HANDOVER `@` IS A DESCRIBED, NON-EMPTY COMMIT on an unrelated head
#     (`rate-limit`). This is a D11 guard, not decoration: jj 0.44 silently
#     abandons an empty, undescribed working-copy commit the moment you
#     `jj edit` or `jj new` elsewhere, printing nothing at all, and inspecting
#     the two versions is the first thing a solve does. `@` is also NOT one of
#     the two divergent versions, so a solve never has to move it and the
#     verifier never reads its position.
#
# HOW THE DIVERGENCE IS MADE. Two concurrent operations rewrite the same change:
# one on the live operation chain (adding the test file), one replayed against
# an earlier operation with `--at-op` (dropping the CHANGELOG line). jj merges
# the two operation heads on the next command and reports
# `Concurrent modification detected, resolving automatically.`, leaving two
# visible commits under one change id and a bookmark with two `+` targets. This
# is the only mechanism that produces divergence without a second machine: a
# git-side rewrite fetched into a colocated repo arrives with a DIFFERENT change
# id and is therefore not divergent at all.
#
# The `--at-op` step prints a git-export warning -- git cannot represent a
# bookmark with two targets, so `refs/heads/idempotency` is left where the live
# side put it. That is expected, exits 0, and clears itself the moment the agent
# resolves the bookmark.
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
cat >CHANGELOG.md <<'F'
# Changelog

## Unreleased
- charge endpoint
F
# A real Python project ships one of these, and this fixture needs it because jj
# 0.44 AUTO-TRACKS new files. Measured on this image before the file existed: a
# perfect solve that also imported a project module while `@` was on the
# handover commit scored 0.667, because the resulting
# `src/api/__pycache__/charge.cpython-312.pyc` landed in `start the rate-limit
# middleware` -- which the floored no-collateral-damage test grades by path set.
# Note that the import does not have to SUCCEED: CPython writes the bytecode
# cache after compiling and before executing, so the failing
# `import api.charge` (there is no `client.http` here) leaves the .pyc anyway.
#
# Editor leftovers are the same exposure: a `src/api/charge.py~` or a vim swap
# file left next to a file the agent read auto-tracks into whatever `@` is
# sitting on, and lands in the same path-set assertion the .pyc did. Measured
# on the sibling fixtures in this set, an otherwise perfect solve that left a
# `~` backup scored 0.667.
#
# `__pycache__/` and `*~` are the load-bearing lines here; `*.pyc` covers the
# bytecode `python3 -m compileall -b` writes beside the source instead of into
# `__pycache__/`, and `*.swp`/`*.swo` cover vim. `.pytest_cache/` writes its own
# `.gitignore` containing `*` and so already ignores itself; it is listed for
# the same reason a real project lists it, and nothing rests on it.
#
# THE SIX LINES AND THEIR ORDER ARE SHARED with the other three fixtures in
# this task set. Keep them identical; there is nothing task-specific here.
cat >.gitignore <<'F'
__pycache__/
*.pyc
.pytest_cache/
*~
*.swp
*.swo
F
# THE PLACEMENT IS LOAD-BEARING, not just tidy: `add the charge endpoint` is the
# only commit below every path-set assertion in the verifier, so the .gitignore
# is in force everywhere the grading looks. bootstrap/test_initial_state.py
# asserts the file is present in this commit's tree so that a move fails loudly
# in the bootstrap check rather than quietly in the verifier.
jj commit -m "add the charge endpoint"

cat >src/api/handlers.py <<'F'
from api.charge import charge


def handle_charge(request):
    return charge(
        request["account_id"], request["amount"], request.get("currency", "USD")
    )
F
jj commit -m "route charges through handlers"
jj bookmark create main -r @-

# ---- the change that will end up recorded twice ----
jj new main -m "add idempotency key to charge requests"
python3 - <<'PY'
p = "src/api/charge.py"
s = open(p).read()
s = s.replace(
    "def charge(account_id, amount, currency=\"USD\"):",
    "IDEMPOTENCY_HEADER = \"Idempotency-Key\"\n\n\n"
    "def charge(account_id, amount, currency=\"USD\", idempotency_key=None):",
)
s = s.replace(
    "    return post(\"/v1/charges\", payload)",
    "    headers = {IDEMPOTENCY_HEADER: idempotency_key} if idempotency_key else {}\n"
    "    return post(\"/v1/charges\", payload, headers=headers)",
)
open(p, "w").write(s)
c = open("CHANGELOG.md").read()
open("CHANGELOG.md", "w").write(c + "- idempotency keys on charge requests\n")
PY
jj bookmark create idempotency -r @
jj status >/dev/null
IDEMPOTENCY_CHANGE=$(jj log --no-graph -r @ -T 'change_id')

# ---- the unrelated head the working copy sits on, so that `@` is described,
# ---- non-empty and not one of the two versions (invariant 6) ----
jj new main -m "start the rate-limit middleware"
cat >src/client/limits.py <<'F'
import time

PER_MINUTE = 600


class TokenBucket:
    def __init__(self, per_minute=PER_MINUTE):
        self.capacity = per_minute
        self.tokens = per_minute
        self.updated = time.monotonic()
F
jj bookmark create rate-limit -r @
jj status >/dev/null

# The operation the second version is replayed against. Everything the fixture
# needs already exists here; only the two rewrites come after it.
FORK_OP=$(jj op log --no-graph --no-pager -n 1 -T 'id')

# ---- version one, on the live operation chain: the tests go in ----
cat >tests/test_charge.py <<'F'
from api.charge import charge


def test_charge_sends_the_idempotency_key(monkeypatch):
    sent = {}

    def fake_post(path, payload, headers=None):
        sent["headers"] = headers or {}
        return {"id": "ch_1"}

    monkeypatch.setattr("api.charge.post", fake_post)
    charge("acct_1", "10.00", idempotency_key="key-1")
    assert sent["headers"]["Idempotency-Key"] == "key-1"
F
jj squash --into "$IDEMPOTENCY_CHANGE" tests/test_charge.py

# ---- version two, replayed against FORK_OP: the CHANGELOG line comes back out.
# ---- This is the version that ends up at offset /0, and it is the wrong one.
jj --at-op "$FORK_OP" --ignore-working-copy \
   restore --from main --into "$IDEMPOTENCY_CHANGE" CHANGELOG.md

# Force the operation-log merge now, so the repository is handed over already
# reconciled and the anchor records the merged operation as the handover.
jj --ignore-working-copy log -r 'all()' --no-graph -T '""' >/dev/null
jj status >/dev/null
BOOTSTRAP

# Container contents:
#   - jj installed in /usr/local/bin/jj.
#   - /home/user/checkout-api -- colocated jj repo:
#       add the charge endpoint
#       route charges through handlers                     <- main
#       add idempotency key to charge requests   /0        <- idempotency??, NO tests
#       add idempotency key to charge requests   /1        <- idempotency??, HAS tests
#       start the rate-limit middleware                    <- rate-limit, @
#
# `jj log -r <the change id>` refuses with
#   Error: Change ID `<id>` is divergent
#   Hint: Use change offset to select single revision: <id>/0, <id>/1
#   Hint: Use `change_id(<id>)` to select all revisions
# which is where the two visible offsets can be read at runtime. They are not
# stable across rewrites and must never be hard-coded.

WORKDIR /home/user/checkout-api

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
