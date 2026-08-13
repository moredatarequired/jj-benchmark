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
LABEL Description="checkout-api: uncommitted hand edits under src/ alongside a regenerated src/generated tree."

# The whole bootstrap as one shell script. BuildKit's heredoc support is what
# makes this legal in a Dockerfile; the inner heredocs all terminate on `F`, so
# no line of file content may be exactly `BOOTSTRAP`.
#
# WHAT MAKES THIS A FILESET TASK RATHER THAN A RESTORE TASK: `src/generated` is
# NESTED INSIDE `src`. Every path the rollback must undo and every path it must
# leave alone are under one prefix, so no single path argument separates them --
# `jj restore src` takes the generated tree with it, and that is the wrong solve
# the verifier is written against.
#
# The uncommitted work is deliberately of four kinds, so that each half of the
# request is scored on more than a content diff:
#   * modified under src/, outside generated  (charge.py, handlers.py, http.py)
#   * ADDED under src/, outside generated     (src/api/refunds.py)   -- must go
#   * modified AND ADDED under src/generated  (models, openapi_client, webhooks)
#   * modified outside src/ entirely          (tests/test_charge.py, CHANGELOG.md)
# The last group is what fails a blanket `jj restore`.
RUN <<'BOOTSTRAP' bash -euo pipefail
mkdir -p /home/user/checkout-api
cd /home/user/checkout-api
git init .
git config user.name "Priya Raman"
git config user.email "priya@checkout.example"
jj git init --colocate
jj config set --user user.name "Priya Raman"
jj config set --user user.email "priya@checkout.example"

mkdir -p src/api src/client src/generated tests

cat >config.toml <<'F'
[server]
host = "0.0.0.0"
port = 8080

[codegen]
spec = "openapi/checkout-2.3.yaml"
output = "src/generated"
F
cat >src/api/charge.py <<'F'
from client.http import post


def charge(account_id, amount, currency="USD"):
    return post("/v1/charges", {
        "account_id": account_id,
        "amount": amount,
        "currency": currency,
    })
F
cat >src/api/handlers.py <<'F'
from api.charge import charge


def handle(request):
    return charge(request["account_id"], request["amount"])
F
cat >src/client/http.py <<'F'
import json
import urllib.request

BASE_URL = "https://api.checkout.example"
TIMEOUT_SECONDS = 10


def post(path, payload):
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.load(response)
F
cat >src/generated/models.py <<'F'
# GENERATED FILE -- do not edit by hand.
# openapi-generator 6.2.0 from openapi/checkout-2.3.yaml

CHARGE_FIELDS = ("account_id", "amount", "currency")
REFUND_FIELDS = ("charge_id", "amount")
F
cat >src/generated/openapi_client.py <<'F'
# GENERATED FILE -- do not edit by hand.
# openapi-generator 6.2.0 from openapi/checkout-2.3.yaml

PATHS = {
    "create_charge": "/v1/charges",
    "get_charge": "/v1/charges/{charge_id}",
}
F
cat >tests/test_charge.py <<'F'
from api.charge import charge


def test_charge_posts_the_amount(fake_post):
    charge("acct_1", "12.50")
    assert fake_post.last["amount"] == "12.50"
F
cat >CHANGELOG.md <<'F'
# Changelog

## Unreleased
- charge endpoint
F
jj commit -m "add the charge endpoint"

cat >>src/client/http.py <<'F'


def get(path):
    with urllib.request.urlopen(BASE_URL + path, timeout=TIMEOUT_SECONDS) as response:
        return json.load(response)
F
jj commit -m "let the http client read as well as write"

# --- the uncommitted work the task is about ---

# Hand edits under src/, outside the generated tree.
cat >>src/api/charge.py <<'F'


def charge_with_retry(account_id, amount, attempts=3):
    for _ in range(attempts - 1):
        try:
            return charge(account_id, amount)
        except OSError:
            continue
    return charge(account_id, amount)
F
cat >src/api/handlers.py <<'F'
from api.charge import charge, charge_with_retry


def handle(request):
    if request.get("retry"):
        return charge_with_retry(request["account_id"], request["amount"])
    return charge(request["account_id"], request["amount"])
F
cat >src/client/http.py <<'F'
import json
import urllib.request

BASE_URL = "https://api.checkout.example"
TIMEOUT_SECONDS = 30


def post(path, payload):
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.load(response)


def get(path):
    with urllib.request.urlopen(BASE_URL + path, timeout=TIMEOUT_SECONDS) as response:
        return json.load(response)
F
cat >src/api/refunds.py <<'F'
from client.http import post


def refund(charge_id, amount):
    return post("/v1/refunds", {"charge_id": charge_id, "amount": amount})
F

# The regeneration under src/generated: two files rewritten, one file added.
cat >src/generated/models.py <<'F'
# GENERATED FILE -- do not edit by hand.
# openapi-generator 6.2.0 from openapi/checkout-2.4.yaml

CHARGE_FIELDS = ("account_id", "amount", "currency", "idempotency_key")
REFUND_FIELDS = ("charge_id", "amount", "reason")
WEBHOOK_FIELDS = ("event", "created_at")
F
cat >src/generated/openapi_client.py <<'F'
# GENERATED FILE -- do not edit by hand.
# openapi-generator 6.2.0 from openapi/checkout-2.4.yaml

PATHS = {
    "create_charge": "/v1/charges",
    "get_charge": "/v1/charges/{charge_id}",
    "create_refund": "/v1/refunds",
    "list_webhooks": "/v1/webhooks",
}
F
cat >src/generated/webhooks.py <<'F'
# GENERATED FILE -- do not edit by hand.
# openapi-generator 6.2.0 from openapi/checkout-2.4.yaml

EVENTS = ("charge.succeeded", "charge.failed", "refund.created")
F

# Edits outside src/ that a blanket rollback would take with it.
cat >>tests/test_charge.py <<'F'


def test_refund_posts_the_charge_id(fake_post):
    refund("ch_1", "5.00")
    assert fake_post.last["charge_id"] == "ch_1"
F
cat >>CHANGELOG.md <<'F'
- refunds endpoint
- regenerated api client from the 2.4 spec
F
BOOTSTRAP

# Container contents:
#   - jj in /usr/local/bin/jj (v0.44.0).
#   - /home/user/checkout-api -- jj repo, colocated, two commits above the root:
#       add the charge endpoint
#       let the http client read as well as write
#     and an undescribed working copy holding nine uncommitted changes:
#       M CHANGELOG.md
#       M src/api/charge.py       M src/api/handlers.py     A src/api/refunds.py
#       M src/client/http.py
#       M src/generated/models.py M src/generated/openapi_client.py
#       A src/generated/webhooks.py
#       M tests/test_charge.py
#     The files are written but NOT snapshotted; the first jj command snapshots
#     them, exactly as in tasks/restore_interactive.

WORKDIR /home/user/checkout-api

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
