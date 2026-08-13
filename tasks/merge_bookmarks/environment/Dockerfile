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
LABEL Description="checkout-api: two unmerged bookmarks whose tips each add one block to config.toml."

# The whole bootstrap as one shell script, because the fixture is a sequence of
# file writes and jj commands and reads as one. BuildKit's heredoc support is
# what makes this legal in a Dockerfile; the inner heredocs all terminate on `F`,
# which is why no line of file content may be exactly `BOOTSTRAP`.
#
# THE ONE FIXTURE INVARIANT TO PRESERVE (proposed-prompts-v3, N2): each
# bookmark's tip adds EXACTLY ONE block to config.toml -- `rate-limit` adds
# `[ratelimit]` and nothing else, `oauth-refresh` adds `[oauth]` and nothing
# else. The prompt says "both bookmarks' blocks" rather than naming the two
# blocks, so it has exactly one satisfying content only while that holds. If a
# tip ever touches a second block, the block names have to go back in the
# prompt.
#
# The two blocks are appended to the same end-of-file region on purpose: the
# merge is a real 2-sided conflict in config.toml (measured on jj 0.44.0), so
# "keeping both bookmarks' blocks" is work rather than a side effect.
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

cat >config.toml <<'F'
[server]
host = "0.0.0.0"
port = 8080

[database]
url = "postgres://localhost/checkout"
pool_size = 10
F
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
jj commit -m "extract the http client"
jj bookmark create main -r @-

# rate-limit: two commits off main. Only the tip touches config.toml.
jj new main -m "count charges per account in redis"
cat >src/api/limits.py <<'F'
import time

WINDOW_SECONDS = 60


def bucket_for(account_id, now=None):
    now = time.time() if now is None else now
    return "%s:%d" % (account_id, int(now // WINDOW_SECONDS))
F
jj new -m "reject charges over the per-account rate limit"
cat >>src/api/limits.py <<'F'


def over_limit(account_id, seen, limit):
    return seen.get(bucket_for(account_id), 0) >= limit
F
cat >>config.toml <<'F'

[ratelimit]
per_account_per_minute = 60
burst = 10
F
jj bookmark create rate-limit -r @

# oauth-refresh: two commits off main. Only the tip touches config.toml.
jj new main -m "read the oauth client credentials from config"
cat >src/client/oauth.py <<'F'
import time


class Token:
    def __init__(self, value, expires_at):
        self.value = value
        self.expires_at = expires_at

    def expired(self, now=None):
        return (time.time() if now is None else now) >= self.expires_at
F
jj new -m "refresh oauth tokens before they expire"
cat >>src/client/oauth.py <<'F'


def refresh_if_needed(token, margin, fetch):
    if token.expires_at - time.time() <= margin:
        return fetch()
    return token
F
cat >>config.toml <<'F'

[oauth]
token_url = "https://auth.example.com/oauth/token"
refresh_margin_seconds = 120
F
jj bookmark create oauth-refresh -r @

# Where the user is standing: a fresh empty change on main. Nothing in the task
# is about it, and `jj new rate-limit oauth-refresh` auto-abandons it (D11 in
# scratch's change-id-ops-0.44 table) -- hence the working-copy entry in
# tests/anchor_exemptions.json.
jj new main
BOOTSTRAP

# Container contents:
#   - jj in /usr/local/bin/jj (v0.44.0).
#   - /home/user/checkout-api -- jj repo, colocated, six commits above the root:
#       add the charge endpoint
#       extract the http client                          <- main
#         count charges per account in redis
#         reject charges over the per-account rate limit  <- rate-limit, adds [ratelimit]
#         read the oauth client credentials from config
#         refresh oauth tokens before they expire         <- oauth-refresh, adds [oauth]
#       @  empty, undescribed, on main
#     No merge commit anywhere, and no commit has more than one parent.

WORKDIR /home/user/checkout-api

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
