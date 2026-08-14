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
# A real Python project ships one of these, and this fixture needs it for a
# reason that has nothing to do with realism: jj 0.44 AUTO-TRACKS new files, so
# without it the project's own tests cannot be run without changing the answer.
# Measured on this image before the file existed:
#
#   * a perfect copy that parked `@` on the release line and ran the tests
#     scored 0.000 -- pytest wrote a .pyc, `@` became non-empty, so it stopped
#     being a JUST_LOOKING commit and counted as a FOURTH copy, failing all
#     three scored tests;
#   * running the tests WITHOUT moving `@` scored 0.667 -- the .pyc landed in
#     `sketch the refund endpoint`, which the floored no-collateral-damage test
#     grades by path set.
#
# Editor leftovers are the same exposure and were measured the same way, on
# this image with only `__pycache__/` and `.pytest_cache/` ignored:
#
#   * a perfect copy that also left `src/api/charge.py~` next to the file it
#     read scored 0.667, and a vim swap file (`src/api/.charge.py.swp`) scored
#     0.667 -- both landed in `sketch the refund endpoint`;
#   * a perfect copy that parked `@` on the release line and left the same
#     `charge.py~` there scored 0.000, for the same reason pytest did: the
#     backup made `@` non-empty, so it counted as a FOURTH copy.
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
# `.gitignore` containing `*` and so already ignores itself (measured: it never
# appears in `jj status`); it is listed for the same reason a real project lists
# it, and nothing rests on it.
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
# THE PLACEMENT IS LOAD-BEARING, not just tidy. `add the charge endpoint` is the
# earliest commit and the only one below every path-set assertion in the
# verifier, so committing the .gitignore here puts it in force everywhere the
# grading looks.
#
# BE EXACT ABOUT WHAT MOVING IT WOULD COST, because an earlier version of this
# comment was wrong about it in two ways. THE FORK POINT IS `route charges
# through handlers`, the NEXT commit down, not this one: `release/2.4` and
# main's line both leave from there. So moving this heredoc one commit later
# lands it IN the fork point, where it is still an ancestor of both `main` and
# `release/2.4`, and the only commit it stops covering is `add the charge
# endpoint` itself. Measured on exactly that image, with no
# bootstrap_anchor.json anywhere under tasks/: the vacuity floor is 1/4 -- the
# same count AND the same test name, `test_nothing_else_in_the_repository_moved`,
# as the fixture as shipped -- and `scripts/vacuity_floor.py --check` against
# the committed floor file passes on it. The earlier claim that the move drops
# the floor to 0/4 is false, and the phrase "would leave the fork point
# unprotected" named the wrong commit as the fork point: the moved file lands
# ON the fork point and protects it.
#
# The move is still wrong, and it is worth guarding precisely BECAUSE it is
# silent: it costs one commit's worth of coverage and moves no score, so
# nothing in CI would ever report it. bootstrap/test_initial_state.py asserts
# the placement instead -- and, since birth is not force, that every commit
# still carries the file byte for byte. On that same moved image the check
# fails loudly with "`add the charge endpoint` has no .gitignore in its tree".
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

# Project conventions for coding agents. Deliberately placed in /home/user, the
# PARENT of the project directory, and never inside the repository: two verifiers
# assert an exact tracked-file set, so a committed AGENTS.md caps a correct solve
# below 1.0. CLAUDE.md is a symlink to it and the symlink is load-bearing --
# measured, the agent harness reads CLAUDE.md and ignores a bare AGENTS.md.
RUN printf '%s\n' \
      '# Contributing' \
      '' \
      'This project uses Jujutsu (`jj`) for version control. Please use `jj` for all' \
      'version control work in this repository; `git` should not be used for it.' \
      > /home/user/AGENTS.md && \
    ln -s AGENTS.md /home/user/CLAUDE.md

WORKDIR /home/user/checkout-api

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
