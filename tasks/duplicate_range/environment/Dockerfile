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
LABEL Description="checkout-api: a run of three commits on main that a release branch needs a copy of."

# The whole bootstrap as one shell script. BuildKit's heredoc support is what
# makes this legal in a Dockerfile; the inner heredocs all terminate on `F`, so
# no line of file content may be exactly `BOOTSTRAP`.
#
# THE FIXTURE INVARIANTS THE PROMPT RESTS ON. The prompt is one line -- "copy the
# three duplicate-key commits onto release/2.4 in the same order, and leave the
# originals on main alone" -- and it names neither endpoint of the run. The run
# names itself, and only because the fixture is built this way.
#
#  1. EXACTLY THREE COMMITS MENTION DUPLICATE KEYS, they are contiguous, and no
#     other commit in the repository does. That is what lets "the three
#     duplicate-key commits" pick out a span without naming its endpoints. There
#     are unrelated commits both BELOW the run (`add a client-side rate limiter`)
#     and ABOVE it (`start the 2.5 changelog`, `sketch the refund endpoint`), so
#     copying one commit too many or too few is a detectably different end state.
#
#  2. release/2.4 IS A REAL BRANCH, not a point on main. It forks at
#     `route charges through handlers` and carries its own commit
#     (`pin the 2.4 dependency set`). That is what makes "onto release/2.4" a
#     destination rather than a rewind, and it is what lets the verifier find
#     the copies structurally: they are exactly the commits that descend from
#     the anchored release tip, and at handover nothing does.
#
#  3. THE THREE COMMITS APPLY CLEANLY ON THE RELEASE BRANCH. Two of them create
#     files that do not exist there; the third appends to `src/api/handlers.py`,
#     which the release branch has not touched since the fork. So a correct copy
#     produces no conflict, and a conflicted result is a real failure rather
#     than an artefact of the fixture.
#
#  4. THE HANDOVER `@` IS A DESCRIBED, NON-EMPTY COMMIT above main
#     (`sketch the refund endpoint`). This is a D11 guard, not decoration: jj
#     0.44 silently abandons an empty, undescribed working-copy commit the
#     moment you `jj edit` or `jj new` elsewhere, printing nothing at all, and
#     `jj new release/2.4` is a plausible first move for a hand-built copy.
#     It is also the reason this task needs no tests/anchor_exemptions.json.
#
#  5. EVERY COMMIT IN THE RUN TOUCHES A DISTINCT PATH SET, so the copies can be
#     matched to their sources by what they change and by the content they
#     leave behind -- which is the only way to grade them. The copies are NEW
#     changes with change ids the anchor has never seen; nothing about them can
#     be anchored, so they are identified by their position in the destination's
#     ancestry and by their content, and never by a description.
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

## 2.4
- charge endpoint
F
jj commit -m "add the charge endpoint"

cat >src/api/handlers.py <<'F'
from api.charge import charge

ROUTES = {}


def handle_charge(request):
    return charge(
        request["account_id"], request["amount"], request.get("currency", "USD")
    )
F
jj commit -m "route charges through handlers"
FORK=$(jj log --no-graph -r @- -T 'change_id')

# ---- the release branch: its own commit, off the fork point (invariant 2) ----
cat >config.toml <<'F'
[http]
base_url = "https://api.checkout.example"

[release]
version = "2.4.0"
pinned = true
F
jj describe -m "pin the 2.4 dependency set"
jj bookmark create 'release/2.4' -r @
jj status >/dev/null

# ---- main: an unrelated commit, then the run of three, then more ----
jj new "$FORK" -m "add a client-side rate limiter"
cat >src/client/limits.py <<'F'
import time

PER_MINUTE = 600


class TokenBucket:
    def __init__(self, per_minute=PER_MINUTE):
        self.capacity = per_minute
        self.tokens = per_minute
        self.updated = time.monotonic()
F

# 1 of 3.
jj new -m "validate the duplicate-key format"
cat >src/api/keys.py <<'F'
import re

KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def valid(key):
    return bool(key) and bool(KEY_PATTERN.match(key))
F

# 2 of 3.
jj new -m "return 409 on duplicate keys"
python3 - <<'PY'
p = "src/api/handlers.py"
s = open(p).read()
s = s.replace(
    "from api.charge import charge\n",
    "from api.charge import charge\nfrom api.keys import valid\n",
)
s += '''

SEEN = set()


def handle_charge_with_key(request, key):
    if not valid(key):
        return {"status": 400, "error": "malformed idempotency key"}
    if key in SEEN:
        return {"status": 409, "error": "duplicate key"}
    SEEN.add(key)
    return handle_charge(request)
'''
open(p, "w").write(s)
PY

# 3 of 3.
jj new -m "add tests for duplicate keys"
cat >tests/test_duplicate_keys.py <<'F'
from api.handlers import handle_charge_with_key


def test_second_use_of_a_key_is_rejected(monkeypatch):
    monkeypatch.setattr("api.handlers.handle_charge", lambda request: {"status": 200})
    request = {"account_id": "acct_1", "amount": "10.00"}
    assert handle_charge_with_key(request, "key-abcdefgh")["status"] == 200
    assert handle_charge_with_key(request, "key-abcdefgh")["status"] == 409
F

# ---- unrelated work above the run, and main ----
jj new -m "start the 2.5 changelog"
python3 - <<'PY'
c = open("CHANGELOG.md").read()
open("CHANGELOG.md", "w").write(c + "\n## 2.5 (unreleased)\n- duplicate key handling\n")
PY
jj bookmark create main -r @

# The handover `@`: described and non-empty -- invariant 4.
jj new -m "sketch the refund endpoint"
cat >src/api/refund.py <<'F'
from client.http import post


def refund(charge_id, amount=None):
    payload = {"charge_id": charge_id}
    if amount is not None:
        payload["amount"] = amount
    return post("/v1/refunds", payload)
F
jj status >/dev/null
BOOTSTRAP

# Container contents:
#   - jj installed in /usr/local/bin/jj.
#   - /home/user/checkout-api -- colocated jj repo:
#       add the charge endpoint
#       route charges through handlers                <- the fork point
#         |- pin the 2.4 dependency set               <- release/2.4
#         `- add a client-side rate limiter
#            validate the duplicate-key format        <- run 1/3
#            return 409 on duplicate keys             <- run 2/3
#            add tests for duplicate keys             <- run 3/3
#            start the 2.5 changelog                  <- main
#            sketch the refund endpoint               <- @

WORKDIR /home/user/checkout-api

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
