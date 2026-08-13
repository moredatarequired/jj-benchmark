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
LABEL Description="checkout-api: three commits of work and a bookmark that never followed them."

# The whole bootstrap as one shell script. BuildKit's heredoc support is what
# makes this legal in a Dockerfile; the inner heredocs all terminate on `F`, so
# no line of file content may be exactly `BOOTSTRAP`.
#
# THE FIXTURE INVARIANTS THE PROMPT RESTS ON. The prompt is one line -- "push
# everything I've done on rate-limit to origin" -- and it says nothing about the
# obstacle, because the obstacle is not visible until the agent tries.
#
#  1. THE BOOKMARK IS THREE COMMITS BEHIND THE WORK, and that is not a mistake
#     anybody made: in jj a bookmark does not move when you commit. `rate-limit`
#     was set when the branch was one commit long, three more commits were
#     written on top, and the bookmark stayed exactly where it was put. This is
#     the whole task. A git-fluent agent believes the branch is wherever the
#     last commit landed, and everything that follows from that belief is wrong.
#
#  2. THE OBVIOUS COMMAND EXITS 0 HAVING DONE NOTHING. Measured on jj 0.44.0,
#     with the fixture exactly as built here:
#
#       $ jj git push
#       Warning: No bookmarks/tags found in the default push revset:
#         remote_bookmarks(remote=origin)..@
#       Nothing changed.
#       $ echo $?
#       0
#
#       $ jj git push -b rate-limit
#       Bookmark rate-limit@origin already matches rate-limit
#       Nothing changed.
#       $ echo $?
#       0
#
#     Two different spellings of "push my branch", both successful, both
#     silently publishing nothing. There is no error to read and no flag to
#     recall; the only way through is to know that the bookmark has to be moved
#     first.
#
#  3. `rate-limit` AND `main` ARE ALREADY ON THE REMOTE AND TRACKED, so nothing
#     here turns on --all or on jj's new-bookmark handling. (`--allow-new` does
#     not exist on 0.44 at all: `jj git push -b <name>` tracks an untracked
#     bookmark by itself.) This task is about the bookmark not moving, and the
#     fixture is built so that no other bookmark question can be confused with
#     it.
#
#  4. THE REMOTE IS A BARE REPOSITORY ON DISK at /home/user/checkout-api.git,
#     so the task needs no network and the verifier can read the ground truth
#     out of it with git plumbing rather than trusting jj's view of what it
#     pushed. That also keeps the task method-neutral: a solve that pushes from
#     the colocated git side is graded the same as one that uses jj.
#
#  5. THE HANDOVER `@` IS THE DESCRIBED, NON-EMPTY TIP of the work. This is a
#     D11 guard, not decoration: jj 0.44 silently abandons an empty, undescribed
#     working-copy commit the moment you `jj edit` or `jj new` elsewhere,
#     printing nothing at all. It also means the commit the bookmark has to
#     reach is `@` itself -- measured, jj pushes a bookmark pointing at the
#     working-copy commit without complaint, so no `jj new` is needed first.
#
#  6. THE THREE COMMITS TOUCH DISJOINT PATHS, so "everything I've done" is
#     checkable commit by commit rather than as one blob, and squashing them
#     into one before pushing is visible in the end state.
RUN <<'BOOTSTRAP' bash -euo pipefail
git init --bare /home/user/checkout-api.git

mkdir -p /home/user/checkout-api
cd /home/user/checkout-api
git init .
git config user.name "Priya Raman"
git config user.email "priya@checkout.example"
jj git init --colocate
jj config set --user user.name "Priya Raman"
jj config set --user user.email "priya@checkout.example"
jj git remote add origin /home/user/checkout-api.git

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

# ---- the branch, one commit long, and the bookmark put on it ----
jj new main -m "add a token bucket to the client"
cat >src/client/limits.py <<'F'
import time

PER_MINUTE = 600


class TokenBucket:
    def __init__(self, per_minute=PER_MINUTE):
        self.capacity = per_minute
        self.tokens = per_minute
        self.updated = time.monotonic()

    def take(self):
        if self.tokens < 1:
            return False
        self.tokens -= 1
        return True
F
jj bookmark create rate-limit -r @
jj status >/dev/null

# Both bookmarks go up to the remote here, so they are tracked and neither is
# new by the time the agent arrives -- invariant 3.
jj git push -b main -b rate-limit

# ---- three more commits, and the bookmark does not follow (invariant 1) ----
jj new -m "read the rate limit from config"
cat >config.toml <<'F'
[http]
base_url = "https://api.checkout.example"

[ratelimit]
per_minute = 600
burst = 60
F

jj new -m "refill the bucket between attempts"
python3 - <<'PY'
p = "src/client/limits.py"
s = open(p).read()
s = s.replace(
    "    def take(self):\n",
    "    def refill(self):\n"
    "        now = time.monotonic()\n"
    "        elapsed = now - self.updated\n"
    "        self.tokens = min(\n"
    "            self.capacity, self.tokens + elapsed * self.capacity / 60.0\n"
    "        )\n"
    "        self.updated = now\n"
    "\n"
    "    def take(self):\n"
    "        self.refill()\n",
)
open(p, "w").write(s)
PY

jj new -m "add tests for the token bucket"
cat >tests/test_limits.py <<'F'
from client.limits import TokenBucket


def test_an_empty_bucket_refuses():
    bucket = TokenBucket(per_minute=1)
    assert bucket.take() is True
    assert bucket.take() is False
F
jj status >/dev/null
BOOTSTRAP

# Container contents:
#   - jj installed in /usr/local/bin/jj.
#   - /home/user/checkout-api.git -- bare origin, holding main and rate-limit as
#     they were three commits ago.
#   - /home/user/checkout-api -- colocated jj repo:
#       add the charge endpoint
#       route charges through handlers            <- main, pushed
#       add a token bucket to the client          <- rate-limit, pushed
#       read the rate limit from config           <- unpushed
#       refill the bucket between attempts        <- unpushed
#       add tests for the token bucket            <- unpushed, @

WORKDIR /home/user/checkout-api

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
