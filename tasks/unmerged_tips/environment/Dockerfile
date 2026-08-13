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
LABEL Description="checkout-api: a branching history where some heads are already in main and some are not."

# The whole bootstrap as one shell script. BuildKit's heredoc support is what
# makes this legal in a Dockerfile; the inner heredocs all terminate on `F`, so
# no line of file content may be exactly `BOOTSTRAP`.
#
# THE FIXTURE INVARIANTS THE PROMPT RESTS ON:
#
#  1. Two bookmarks are ALREADY ancestors of main -- `retry-backoff` and
#     `release/2.4`, both on `retry failed charges with backoff`. Listing
#     bookmark tips instead of unmerged heads therefore gives a wrong answer.
#  2. One unmerged head carries NO bookmark at all -- `spike: batch settlement
#     into one payout`. Listing bookmarks instead of heads therefore also gives
#     a wrong answer, in the other direction.
#  3. `main` is itself a head, so `heads(all())` -- the other cheap wrong
#     revset -- returns one commit too many.
#  4. The handover `@` IS the `idempotency` tip: described, non-empty, and
#     already one of the four correct answers. That placement is deliberate.
#     Writing unmerged.txt into the working copy rewrites that commit's commit
#     id and preserves its change id, so the answer set does not move while the
#     agent is producing it. An `@` parked on a fresh child of main would have
#     been a fifth tip that only exists because the fixture put it there.
RUN <<'BOOTSTRAP' bash -euo pipefail
mkdir -p /home/user/checkout-api
cd /home/user/checkout-api
git init .
git config user.name "Priya Raman"
git config user.email "priya@checkout.example"
jj git init --colocate
jj config set --user user.name "Priya Raman"
jj config set --user user.email "priya@checkout.example"

mkdir -p src/api src/client

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
# Scaffolding handles only. Both are deleted before handover, so the repo the
# agent sees has no bookmark that is not part of the story.
jj bookmark create scaffold-first -r @-

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
jj commit -m "extract the http client"
jj bookmark create scaffold-http -r @-

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
jj commit -m "retry failed charges with backoff"
# Both of these end up INSIDE ::main, which is the point of them.
jj bookmark create retry-backoff -r @-
jj bookmark create release/2.4 -r @-

cat >>CHANGELOG.md <<'F'
- retry failed charges with exponential backoff
F
jj commit -m "note the retry behaviour in the changelog"
jj bookmark create main -r @-

# Unmerged head 1: rate-limit, off the http-client commit.
jj new scaffold-http -m "cap charges per account"
cat >src/api/limits.py <<'F'
WINDOW_SECONDS = 60


def over_limit(account_id, seen, limit):
    return seen.get(account_id, 0) >= limit
F
jj bookmark create rate-limit -r @

# Unmerged head 2: oauth-refresh, two commits off the http-client commit.
jj new scaffold-http -m "read the oauth client credentials from config"
cat >src/client/oauth.py <<'F'
import time


class Token:
    def __init__(self, value, expires_at):
        self.value = value
        self.expires_at = expires_at
F
jj new -m "refresh oauth tokens before they expire"
cat >>src/client/oauth.py <<'F'


def refresh_if_needed(token, margin, fetch):
    if token.expires_at - time.time() <= margin:
        return fetch()
    return token
F
jj bookmark create oauth-refresh -r @

# Unmerged head 3: an abandoned-looking spike with NO bookmark on it.
jj new scaffold-first -m "spike: batch settlement into one payout"
cat >src/api/settlement.py <<'F'
def batch(charges):
    total = 0
    for charge in charges:
        total += charge["amount"]
    return {"count": len(charges), "total": total}
F

# Unmerged head 4: idempotency, off retry-backoff -- and where the user stands.
jj new retry-backoff -m "add idempotency keys to charge requests"
cat >>src/api/charge.py <<'F'


def idempotency_key(account_id, request_id):
    return "%s/%s" % (account_id, request_id)
F
jj new -m "return 409 on duplicate keys"
cat >src/api/handlers.py <<'F'
from api.charge import charge, idempotency_key

SEEN = {}


def handle(request):
    key = idempotency_key(request["account_id"], request["request_id"])
    if key in SEEN:
        return {"status": 409, "error": "duplicate idempotency key"}
    SEEN[key] = True
    return charge(request["account_id"], request["amount"])
F
jj bookmark create idempotency -r @

jj bookmark delete scaffold-first
jj bookmark delete scaffold-http
# Deleting a bookmark moves nothing and hides nothing on 0.44 (measured), so
# both spikes stay visible heads.
jj status
BOOTSTRAP

# Container contents:
#   - jj in /usr/local/bin/jj (v0.44.0).
#   - /home/user/checkout-api -- jj repo, colocated, ten commits above the root:
#
#       add the charge endpoint
#       |  extract the http client
#       |  |  retry failed charges with backoff        <- retry-backoff, release/2.4
#       |  |  `- note the retry behaviour in the changelog   <- main
#       |  |  `- add idempotency keys to charge requests
#       |  |     `- return 409 on duplicate keys       <- idempotency, @
#       |  `- cap charges per account                  <- rate-limit
#       |  `- read the oauth client credentials from config
#       |     `- refresh oauth tokens before they expire  <- oauth-refresh
#       `- spike: batch settlement into one payout     <- no bookmark
#
#     Four heads are outside ::main: rate-limit, oauth-refresh, idempotency and
#     the spike. No unmerged.txt anywhere.

WORKDIR /home/user/checkout-api

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
