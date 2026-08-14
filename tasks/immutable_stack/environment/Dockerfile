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
LABEL Description="checkout-api: an immutable_heads() alias that protects the author's own stack as well as main."

# The whole bootstrap as one shell script. BuildKit's heredoc support is what
# makes this legal in a Dockerfile; the inner heredocs all terminate on `F`, so
# no line of file content may be exactly `BOOTSTRAP`.
#
# THE FIXTURE INVARIANTS THE PROMPT RESTS ON. The prompt is one line -- "unblock
# my stack so I can reword 'fix nonce handling' to 'handle nonces on retried
# charges', but keep main protected" -- and both halves are scored, so both are
# stated. What is NOT stated is the obstacle: the agent meets it the first time
# it tries the reword.
#
#  1. THE ALIAS IS OVER-BROAD IN A WAY THAT LOOKS RIGHT.
#     `immutable_heads() = bookmarks()` protects every commit that has a local
#     bookmark on it, and everything below. That is a real thing to write --
#     "protect the branches" -- and it does protect main correctly. It also
#     protects `retry-backoff`, which is the author's own in-progress stack, so
#     `jj describe` on their own commit is refused. The whole task is the gap
#     between what the alias was meant to say and what it evaluates to.
#
#  2. THE ALIAS IS SET WITH `jj config set --repo`, never by hand-placing a
#     file. On jj 0.44 that writes to $HOME/.config/jj/repos/<20-hex>/config.toml
#     -- NOT to .jj/repo/config.toml -- and the hex is derived from the
#     repository path. Writing the file directly would put it where jj does not
#     look. `jj config path --repo` prints where it really is.
#
#  3. THERE IS NO GIT REMOTE, so the DEFAULT `immutable_heads()` does not
#     protect main. jj's builtin is `trunk() | tags() | untracked_remote_bookmarks()`
#     and `trunk()` falls back to `root()` when there is no origin. So deleting
#     the alias -- the obvious one-line fix -- unblocks the stack AND silently
#     unprotects main, which is exactly the half the prompt guards. Measured on
#     jj 0.44.0.
#
#  4. THE REWORD TARGET IS THE SECOND OF FOUR, so rewriting it rebases the two
#     above it: they keep their change ids and get NEW commit ids. Nothing in
#     tests/test_final_state.py asserts a commit id above the target.
#
#  5. `retry-backoff` IS ON THE THIRD COMMIT, NOT THE TIP. That is what leaves
#     the handover `@` outside the immutable set, so the working copy stays
#     usable and the agent is blocked on the stack rather than on everything.
#     It is also just what jj does: a bookmark does not advance when you commit.
#
#  6. THE HANDOVER `@` IS DESCRIBED AND NON-EMPTY -- a D11 guard, not
#     decoration. jj 0.44 silently abandons an empty, undescribed working-copy
#     commit the moment you `jj edit` or `jj new` elsewhere, printing nothing at
#     all, and `jj edit` on the reword target is a plausible first move.
#
#  7. THE REWORD TARGET OWNS A PATH NOTHING ELSE TOUCHES, src/api/nonce_store.py.
#     It is the only commit in the repository that does, which is what gives
#     tests/test_final_state.py a content-based fallback for a commit whose
#     DESCRIPTION the task changes: `description(substring:"fix nonce handling")`
#     stops matching the moment the task is done, so it cannot be the fallback.
#
# One further note on why a config edit alone is never enough here. jj 0.44
# accepts five config keys it has removed WITHOUT COMPLAINING (survey B9), so an
# agent that "fixes" the configuration by writing a key that does nothing gets
# exit 0 and no warning. The reword is scored separately from the alias, so a
# change that changes nothing fails visibly rather than passing quietly.
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
# perfect solve that also imported a project module while `@` was on the stack
# tip scored 0.667, because the resulting
# `src/client/__pycache__/retry.cpython-312.pyc` landed in `note the nonce work
# in the changelog` -- which the floored
# `test_the_stack_is_still_the_same_four_commits` grades by path set.
#
# This fixture ships no test file, so its pytest exposure is the weakest of the
# four; it is closed the same way as the others because the cost is a seven-line
# file that a real project has anyway. Editor leftovers are NOT weaker here: a
# `src/client/retry.py~` or a vim swap file left next to a file the agent read
# auto-tracks into whatever `@` is sitting on, with no test run needed at all.
# Measured on the sibling fixtures in this set, an otherwise perfect solve that
# left a `~` backup scored 0.667.
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
# only commit below every path-set assertion in the verifier, so the .gitignore
# is in force everywhere the grading looks. bootstrap/test_initial_state.py
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

cat >src/api/nonce.py <<'F'
import secrets


def new_nonce():
    return secrets.token_hex(16)
F
jj commit -m "issue a nonce with every charge"
jj bookmark create main -r @-

# ---- the four-commit stack the author is working on ----

# 1 of 4.
jj new main -m "record retry attempts in the charge metrics"
cat >src/api/metrics.py <<'F'
RETRIES = {}


def record_retry(account_id):
    RETRIES[account_id] = RETRIES.get(account_id, 0) + 1
F

# 2 of 4. THE REWORD TARGET. src/api/nonce_store.py is the path nothing else in
# the repository touches -- invariant 7.
jj new -m "fix nonce handling"
cat >src/api/nonce_store.py <<'F'
ISSUED = {}


def remember(account_id, nonce):
    ISSUED[account_id] = nonce


def seen(account_id, nonce):
    return ISSUED.get(account_id) == nonce
F
python3 - <<'PY'
p = "src/api/nonce.py"
s = open(p).read()
s = s.replace(
    "import secrets\n",
    "import secrets\n\nfrom api.nonce_store import remember\n",
)
s = s.replace(
    "def new_nonce():\n    return secrets.token_hex(16)\n",
    "def new_nonce(account_id):\n"
    "    nonce = secrets.token_hex(16)\n"
    "    remember(account_id, nonce)\n"
    "    return nonce\n",
)
open(p, "w").write(s)
PY

# 3 of 4, and where the bookmark stopped -- invariant 5.
jj new -m "reuse the nonce on retried charges"
cat >src/client/retry.py <<'F'
import time

MAX_ATTEMPTS = 4
BACKOFF_BASE = 0.2


def with_backoff(call, nonce, attempts=MAX_ATTEMPTS, sleep=time.sleep):
    delay = BACKOFF_BASE
    for attempt in range(attempts):
        try:
            return call(nonce=nonce)
        except OSError:
            if attempt == attempts - 1:
                raise
            sleep(delay)
            delay *= 2
F
cat >config.toml <<'F'
[http]
base_url = "https://api.checkout.example"

[charges]
default_currency = "USD"

[nonces]
reuse_on_retry = true
F
jj bookmark create retry-backoff -r @

# 4 of 4, and the handover `@`: described and non-empty -- invariant 6.
jj new -m "note the nonce work in the changelog"
python3 - <<'PY'
c = open("CHANGELOG.md").read()
open("CHANGELOG.md", "w").write(c + "- nonces are reused across retried charges\n")
PY
jj status >/dev/null

# ---- the setting that blocks the author's own stack ----
# `bookmarks()` is every commit carrying a local bookmark. That is `main` AND
# `retry-backoff`, so `::immutable_heads()` swallows the first three commits of
# the stack as well as all of main. Set through jj, never by writing a file.
jj config set --repo 'revset-aliases."immutable_heads()"' 'bookmarks()'
BOOTSTRAP

# Container contents:
#   - jj installed in /usr/local/bin/jj.
#   - /home/user/checkout-api -- colocated jj repo:
#       add the charge endpoint
#       route charges through handlers
#       issue a nonce with every charge                     <- main      IMMUTABLE
#       record retry attempts in the charge metrics         <- stack 1/4 IMMUTABLE
#       fix nonce handling                                  <- stack 2/4 IMMUTABLE, reword target
#       reuse the nonce on retried charges                  <- retry-backoff, 3/4, IMMUTABLE
#       note the nonce work in the changelog                <- stack 4/4, @, mutable
#   - a repo-scoped `immutable_heads() = bookmarks()` alias, which is what makes
#     the first six of those immutable. `jj config path --repo` says where it is.

WORKDIR /home/user/checkout-api

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
