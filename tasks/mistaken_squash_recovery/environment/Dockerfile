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
LABEL Description="checkout-api: a mistaken squash buried in the operation log, with two commits made on top of it since."

# The whole bootstrap as one shell script. BuildKit's heredoc support is what
# makes this legal in a Dockerfile; the inner heredocs all terminate on `F`, so
# no line of file content may be exactly `BOOTSTRAP`.
#
# THE MISTAKE IS BAKED IN. The agent is handed a repository in which two
# commits have already been squashed into one BY THE BOOTSTRAP, and two further
# commits have landed on top since. Nothing is asked of the agent except to
# reverse that one operation without losing what came after it.
#
# THE FIXTURE INVARIANTS THE PROMPT AND THE VERIFIER REST ON:
#
#  1. EXACTLY ONE OPERATION IN THE BOOTSTRAP MAKES A CHANGE ID DISAPPEAR, and
#     it is the squash. This is load-bearing twice over. It is what lets the
#     one-line prompt say "the squash I did by mistake" and name a real,
#     findable operation. And it is how tests/test_final_state.py LOCATES that
#     operation at verification time -- by differencing the visible change-id
#     set across every bootstrap operation and taking the one where an id left,
#     never by matching jj's English description of the operation.
#
#     Measured on jj 0.44.0: this bootstrap's operation log contains exactly one
#     such operation. Two edits would silently break it, and neither looks
#     dangerous:
#       * squashing anything else while building the fixture;
#       * ending a step with `jj commit` and then moving `@` elsewhere with
#         `jj new`/`jj edit`. jj 0.44 auto-abandons an empty, undescribed
#         working-copy commit when you leave it, PRINTING NOTHING (the D11
#         case), which adds a second disappearance to the log.
#     That is why commit A below is made with `jj describe` on the working copy
#     rather than with `jj commit` followed by a move.
#
#  2. THE SQUASH IS NEITHER THE FIRST NOR THE LAST ENTRY. Five operations
#     follow it, so `jj undo` reverses the wrong thing and the mistake has to be
#     found rather than assumed to be the most recent event.
#
#  3. THE TWO PRE-SQUASH COMMITS BOTH TOUCH src/api/charge.py. `add idempotency
#     keys to charge requests` adds the helper; `return 409 on duplicate keys`
#     widens charge()'s signature in the same file AND adds src/api/handlers.py.
#     So the combined commit cannot be taken apart again by path -- a
#     `jj split` by filename leaves both charge.py hunks on one side and
#     reproduces neither original. Hand-rebuilding is caught by change id
#     anyway; this makes it fail on content too.
#
#  4. THE TWO LATER COMMITS TOUCH NEITHER OF THOSE PATHS -- one edits
#     src/client/retry.py, the other CHANGELOG.md. Their survival is therefore
#     independent of anything done to the squash, which is what makes
#     "keeping the two commits I made after it" a separable, gradeable claim.
#
#  5. THE HANDOVER `@` IS DESCRIBED AND NON-EMPTY (the second of the two later
#     commits). Same D11 guard as invariant 1, on the other side of the
#     handover: it means the correct solve cannot silently lose a bootstrap
#     commit, which is why this task ships with no anchor exemption file.
#
# WHAT THE WRONG ANSWERS DO, measured on this fixture:
#   * `jj op restore <the op before the squash>` restores A and B beautifully
#     and DELETES BOTH LATER COMMITS. The repository looks perfectly fine
#     afterwards; it just has less in it.
#   * `jj undo` reverses the most recent operation -- the changelog commit's
#     snapshot -- and leaves the squash entirely alone.
#   * `jj split` on the combined commit produces a right-looking log made of
#     new change ids.
# Only `jj op revert <the squash>` reaches the asked-for end state. Measured on
# 0.44 it restores B with its original change id AND its original commit id,
# rebases the two later commits onto the restored A, and -- contrary to the
# design note this task was written from -- leaves NO divergent change behind.
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

# A REAL PYTHON REPOSITORY SHIPS ONE, AND THIS VERIFIER IS SENSITIVE TO IT.
# It goes into the FIRST commit so it is present at every revision the verifier
# grades, rather than only at the tip.
#
# jj 0.44 auto-tracks new files: anything appearing in the working copy is
# snapshotted into whichever commit the agent is standing on, with no `jj add`
# and no prompt. This task's verifier compares each commit's PATH SET against
# what it was at handover, so a stray bytecode cache is graded. MEASURED on
# this image, without this file: a correct `jj op revert <the squash>` followed
# by anything that imports src/api/charge.py drops from 1.000 to 0.667 on a
# touched src/api/__pycache__/charge.cpython-312.pyc alone.
#
# This fixture ships no tests/ directory, so nothing here invites the stray the
# way propagated_conflict does -- but the exposure is identical and the fix is
# the same one, applied to all three fixtures of this branch rather than to the
# one where it was caught.
#
# The list is not only bytecode. Editors are the other thing that runs during a
# solve, and everything they leave behind auto-tracks exactly the same way --
# measured on the propagated_conflict image, each of these cost an otherwise
# correct solve 0.667 before the pattern covering it was added, and 1.000
# after: an editor backup (`retry.py~`, `*~`); a vim swap file
# (`.retry.py.swp`) and its FALLBACK spellings used when `.swp` is taken
# (`.retry.py.swn`, both `*.sw[a-p]`); an emacs lock file (`.#retry.py`,
# `.#*`); and an emacs autosave (`#retry.py#`, `\#*#`). The emacs lock file is
# the one that should worry you: it appears the moment a file is OPENED for
# editing -- no save, no test run.
#
# THREE THINGS HERE WERE MEASURED ON THE PINNED jj 0.44 BINARY, not assumed:
#
#   * `\#*#` NEEDS THE BACKSLASH. A gitignore line beginning with `#` is a
#     COMMENT, so spelled `#*#` it is not a pattern at all -- `#foo#` came back
#     as `A #foo#` in `jj status` while the block still LOOKED like it covered
#     emacs autosaves. `.#*` needs no escape; it begins with a dot.
#   * `*.sw[a-p]` IS HONOURED AND THE CLASS DOES REAL WORK: `.swp`, `.swo`,
#     `.swn`, `.swm`, `.swa` ignored, `.swq` and `.swz` still tracked. vim
#     rolls DOWN from `.swp` towards `.swa`, so the range covers the real
#     fallback sequence.
#   * IGNORE RULES DO NOT RETROACTIVELY UNTRACK -- a `#foo.py#` created before
#     the rule existed stayed `A #foo.py#` afterwards. The file only helps
#     against strays created after it is in place, which is why it belongs in
#     the fixture rather than in the agent's hands.
#
# NO `*.pyo`, DELIBERATELY. It snapshots the same way, but CPython stopped
# writing `.pyo` at 3.5 and this image is 3.12; a pattern for a file kind dead
# for eight years dilutes a list whose job is to document what agents actually
# produce.
#
# The seven lines cover the file kinds agents actually leave behind, which
# closes this in practice; they are not a proof that no stray file can ever
# reach a path-set assertion.
#
# WHERE THIS LINE SITS IS PART OF THE FIX. It goes into `add the charge
# endpoint`, below every commit tests/test_final_state.py grades. The path-set
# assertions here read their expected set live with `--at-op`, so they tolerate
# a `.gitignore` inside a graded commit; propagated_conflict's OWN_PATHS is a
# literal, and does not. Keep it below the graded commits in all three fixtures
# rather than relying on which kind of assertion each one happens to use today.
#
# COMMITTING it is a fixture-realism choice, not a mechanism requirement: jj
# honours the file the instant it is on disk, committed or not. It is committed
# because a real Python repository ships one, and into the FIRST commit so it
# is present at every revision the verifier grades rather than only at the tip.
cat >.gitignore <<'F'
__pycache__/
*.pyc
.pytest_cache/
*~
*.sw[a-p]
\#*#
.#*
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

cat >src/client/retry.py <<'F'
import time

MAX_ATTEMPTS = 4
RETRY_BUDGET = 10.0


def with_backoff(call, attempts=MAX_ATTEMPTS, budget=RETRY_BUDGET, sleep=time.sleep):
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
jj bookmark create main -r @-

# ---- A: described in place on the working copy, NOT `jj commit` + move.
# See invariant 1: a `jj commit` here followed by `jj new` would auto-abandon
# the empty commit it left behind and put a second disappearance in the log.
jj describe -m "add idempotency keys to charge requests"
python3 - <<'PY'
p = "src/api/charge.py"
s = open(p).read()
s += '''

def idempotency_key(account_id, request_id):
    return "%s/%s" % (account_id, request_id)
'''
open(p, "w").write(s)
PY

# ---- B: touches charge.py as well as handlers.py -- invariant 3.
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
python3 - <<'PY'
p = "src/api/charge.py"
s = open(p).read()
s = s.replace('def charge(account_id, amount, currency="USD"):',
              'def charge(account_id, amount, currency="USD", request_id=None):')
open(p, "w").write(s)
PY
jj status >/dev/null

# ---- THE MISTAKE. B goes into A; B's change id and its message are gone.
# -u keeps the destination message and opens no editor. Without it jj drops
# into $EDITOR to combine the two descriptions, which fails in an image that
# has none -- and would leave B's message inside A, when the point of the
# story is that the squash swallowed it.
jj squash -u

# ---- and then two more commits land on top of it, so the mistake is buried.
jj describe -m "raise the retry budget for charges"
python3 - <<'PY'
p = "src/client/retry.py"
s = open(p).read().replace("RETRY_BUDGET = 10.0", "RETRY_BUDGET = 45.0")
open(p, "w").write(s)
PY

jj new -m "note the 409 behaviour in the changelog"
python3 - <<'PY'
c = open("CHANGELOG.md").read()
open("CHANGELOG.md", "w").write(c + "- duplicate charge requests now return 409\n")
PY
jj status >/dev/null
BOOTSTRAP

# Container contents:
#   - jj installed in /usr/local/bin/jj.
#   - /home/user/checkout-api -- colocated jj repo:
#       add the charge endpoint
#       retry failed charges with backoff                 <- main
#       add idempotency keys to charge requests           <- A, now carrying B too
#       raise the retry budget for charges                <- made after the mistake
#       note the 409 behaviour in the changelog           <- made after the mistake, @
#   - the operation log holds the squash five operations back from its head.

WORKDIR /home/user/checkout-api

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
