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
# A real Python project ships one of these, and this fixture needs it more than
# any of the four: jj 0.44 AUTO-TRACKS new files, the top commit here is
# literally `add tests for the token bucket`, and tests/test_limits.py actually
# passes -- so running it is the obvious thing to do before pushing. Measured on
# this image before the file existed, a perfect solve that ran the tests first
# scored 0.667: `tests/__pycache__/...pyc` and
# `src/client/__pycache__/limits...pyc` were folded into `add tests for the
# token bucket`, which the floored `test_nothing_else_was_published_or_rewritten`
# grades by path set -- and, being the tip, they were then published to origin
# as well.
#
# Editor leftovers reach origin exactly the same way, and were measured the
# same way on this image with only `__pycache__/` and `.pytest_cache/` ignored:
# an otherwise perfect solve that left `src/api/charge.py~` next to the file it
# read scored 0.667, and one that left a vim swap file (`src/client/.limits.py.swp`)
# scored 0.667 -- and in both cases `git ls-tree -r refs/heads/rate-limit` in
# the bare origin afterwards LISTED the leftover, so the junk was published.
#
# `__pycache__/` and `*~` are the load-bearing lines here; `*.pyc` covers the
# bytecode `python3 -m compileall -b` writes beside the source instead of into
# `__pycache__/`. `*.sw[a-p]` covers vim, which rolls DOWN from `.swp` toward
# `.swa` when a swap file is already in the way, so the fallbacks need the range
# and not just `.swp`/`.swo` -- measured on the pinned binary, `.swp`, `.swo`,
# `.swn`, `.swm` and `.swa` are ignored while `.swq` and `.swz` are still
# tracked, so the character class is doing real work rather than matching by
# accident. `\#*#` and `.#*` cover emacs autosaves and LOCK files, and the lock
# file is the sharpest stray of the lot: emacs writes `.#charge.py` the moment a
# file is OPENED for editing. No save, no test run -- an agent that merely
# opened a file to read it has already paid.
#
# THE BACKSLASH ON `\#*#` IS NOT OPTIONAL. A gitignore line beginning with `#`
# is a COMMENT, so the bare spelling covers nothing at all while looking like it
# covers something, which is worse than omitting the line. Measured both ways on
# the pinned binary: with `#*#` a `#charge.py#` comes back from `jj status` as
# `A #charge.py#`; with `\#*#` it does not appear at all. `.#*` needs no escape
# because it starts with a dot.
#
# There is deliberately NO `*.pyo`. It is a real exposure in principle -- jj
# would snapshot one -- but CPython stopped writing `.pyo` at 3.5 and this
# fixture runs 3.12, so the line would document a stray no agent here can
# produce. The list is meant to say what agents actually leave behind, and a
# pattern dead for eight years dilutes that.
#
# `.pytest_cache/` writes its own
# `.gitignore` containing `*` and so already ignores itself; nothing rests on it.
#
# THE SEVEN LINES AND THEIR ORDER ARE SHARED with the other three fixtures in
# this task set: sha256
# 667e996c96b4b8fcd40525cb2e3b3026a1da94f3ca89eac16d6bf1d761b093ff.
# Keep them identical; there is nothing task-specific here.
#
# Two mechanics, measured rather than assumed, because the placement note below
# rests on both. FIRST, AN IGNORE RULE DOES NOT RETROACTIVELY UNTRACK: a file
# already carried by a commit stays there when a pattern matching it is added
# afterwards (measured -- a `#foo#` committed before the rule existed is still
# in the tree, and `jj status` reports nothing to untrack). The rule has to be
# in force BEFORE the stray appears, which is what makes placement a
# correctness question rather than a tidiness one. SECOND, jj honours the file
# even UNCOMMITTED (measured -- an uncommitted `.gitignore` already suppresses
# a new match), so committing it into the first fixture commit is a realism
# choice, not a mechanism requirement: a real project has one in its history.
cat >.gitignore <<'F'
__pycache__/
*.pyc
.pytest_cache/
*~
*.sw[a-p]
\#*#
.#*
F
# THE PLACEMENT IS LOAD-BEARING, not just tidy: `add the charge endpoint` is the
# only commit below every path-set assertion in the verifier and below both
# bookmarks, so the .gitignore is in force everywhere the grading looks -- and
# everywhere a push could carry junk to origin. bootstrap/test_initial_state.py
# asserts the file is present in this commit's tree -- AND that every commit in
# the repository still carries it byte for byte, since birth is not force and
# nothing stops a later commit emptying it -- so that a move or a truncation
# fails loudly in the bootstrap check rather than quietly in the verifier.
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
#   - /home/user/AGENTS.md (+ CLAUDE.md symlink) -- project conventions for the agent.

# Project conventions for coding agents. Deliberately placed in /home/user, the
# PARENT of the project directory, and never inside the repository: two verifiers
# assert an exact tracked-file set, so a committed AGENTS.md caps a correct solve
# below 1.0. What makes it reach the agent is the filename CLAUDE.md, not the
# symlink: captured on Claude Code 2.1.235 inside the built task image,
# /home/user/CLAUDE.md arrives in the assembled system prompt under `Contents of
# /home/user/CLAUDE.md (project instructions, checked into the codebase):`, and a
# bare AGENTS.md is not delivered, at that position or at the project root;
# reproduced on Claude Code 2.1.42 against a replica of the layout. How the
# harness finds the file was not measured, only that it arrives -- evidence in
# results/2026-08-14-baseline-24.md:40-52. The `ln -s` spelling below is pinned
# by scripts/lint_tasks.py, so all 24 copies stay byte-identical and comparable;
# AGENTS.md is the real file so the note also suits agents reading that name.
RUN printf '%s\n' \
      '# Contributing' \
      '' \
      'This project uses Jujutsu (`jj`) for version control. Please use `jj` for all' \
      'version control work in this repository; `git` should not be used for it.' \
      > /home/user/AGENTS.md && \
    ln -s AGENTS.md /home/user/CLAUDE.md

WORKDIR /home/user/checkout-api

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
