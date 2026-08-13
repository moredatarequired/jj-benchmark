"""Verifier for the fileset_rollback task.

The request is "roll back the src/ changes but don't change the generated tree",
and the whole difficulty is that `src/generated` is NESTED INSIDE `src`. No
single path argument separates them: `jj restore src` takes the generated tree
with it, which is the wrong answer this file is written against by name.

WRITTEN AGAINST AN OBSERVED END STATE (R7)
==========================================

The fixture was built from environment/Dockerfile and solved in a container of
that image with

    jj restore 'src ~ src/generated'

before a line of this was written, and every constant below is the content that
run left behind, read back out of the repository rather than copied from the
Dockerfile. Three things that run showed, and that the assertions are shaped by:

  * `jj restore` preserves the working copy's change id and rewrites its commit
    id -- the handover `@` is still `@` afterwards, so no anchor exemption is
    needed and none is shipped;
  * restoring a path that the working copy ADDED removes the file, so
    `src/api/refunds.py` is gone from the tree and from disk. That is a
    consequence of the request, not an extra ask, and it is what separates a
    real rollback from one that only reverts the modified files;
  * `jj new` snapshots before it does anything, so an agent that parks itself on
    a fresh commit first does not strand the uncommitted work in an
    empty-and-therefore-abandonable commit. The handover commit survives that
    route with its content, which is why the graded revision is allowed to be a
    descendant of it (see `graded_revision`).

WHAT IS GRADED, AND FROM WHERE
==============================

The working copy at `@`, with one positional guard rather than a positional
pin: the bootstrap's handover working copy must still be `@` or an ancestor of
`@`. That is the `restore_interactive` idiom (`({handover}) & ::@`), and it is
there for the same reason -- an agent that ran `jj new` at some point must not
lose marks for it, while a stack fabricated from `root()` still cannot be what
gets graded.

Content is compared against the base commit's own bytes AND against literal
constants. Both, deliberately: comparing only against the base commit would
pass an agent that "rolled back" by editing the base commit to match the
working copy instead.
"""

import os
import subprocess

import anchor
from anchor import change_id_or_fallback, working_copy_or_fallback

PROJECT_DIR = "/home/user/checkout-api"

BASE = "let the http client read as well as write"
ROOT_COMMIT = "add the charge endpoint"

# --- the three files under src/ but outside src/generated, as the base commit
# --- has them. A rollback of src/ must put exactly these back.
BASE_SRC = {
    "src/api/charge.py": (
        "from client.http import post\n"
        "\n"
        "\n"
        'def charge(account_id, amount, currency="USD"):\n'
        '    return post("/v1/charges", {\n'
        '        "account_id": account_id,\n'
        '        "amount": amount,\n'
        '        "currency": currency,\n'
        "    })\n"
    ),
    "src/api/handlers.py": (
        "from api.charge import charge\n"
        "\n"
        "\n"
        "def handle(request):\n"
        '    return charge(request["account_id"], request["amount"])\n'
    ),
    "src/client/http.py": (
        "import json\n"
        "import urllib.request\n"
        "\n"
        'BASE_URL = "https://api.checkout.example"\n'
        "TIMEOUT_SECONDS = 10\n"
        "\n"
        "\n"
        "def post(path, payload):\n"
        "    request = urllib.request.Request(\n"
        "        BASE_URL + path,\n"
        "        data=json.dumps(payload).encode(),\n"
        '        headers={"Content-Type": "application/json"},\n'
        "    )\n"
        "    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:\n"
        "        return json.load(response)\n"
        "\n"
        "\n"
        "def get(path):\n"
        "    with urllib.request.urlopen(BASE_URL + path, timeout=TIMEOUT_SECONDS) as response:\n"
        "        return json.load(response)\n"
    ),
}

# The file the uncommitted work ADDED under src/ and outside the generated tree.
# Rolling src/ back removes it.
ADDED_UNDER_SRC = "src/api/refunds.py"

# --- the generated tree as the regeneration left it. Every one of these is the
# --- 2.4 spec; the base commit has the 2.3 versions of the first two and does
# --- not have webhooks.py at all, so reverting the generated tree with the rest
# --- of src/ is visible here three times over.
GENERATED = {
    "src/generated/models.py": (
        "# GENERATED FILE -- do not edit by hand.\n"
        "# openapi-generator 6.2.0 from openapi/checkout-2.4.yaml\n"
        "\n"
        'CHARGE_FIELDS = ("account_id", "amount", "currency", "idempotency_key")\n'
        'REFUND_FIELDS = ("charge_id", "amount", "reason")\n'
        'WEBHOOK_FIELDS = ("event", "created_at")\n'
    ),
    "src/generated/openapi_client.py": (
        "# GENERATED FILE -- do not edit by hand.\n"
        "# openapi-generator 6.2.0 from openapi/checkout-2.4.yaml\n"
        "\n"
        "PATHS = {\n"
        '    "create_charge": "/v1/charges",\n'
        '    "get_charge": "/v1/charges/{charge_id}",\n'
        '    "create_refund": "/v1/refunds",\n'
        '    "list_webhooks": "/v1/webhooks",\n'
        "}\n"
    ),
    "src/generated/webhooks.py": (
        "# GENERATED FILE -- do not edit by hand.\n"
        "# openapi-generator 6.2.0 from openapi/checkout-2.4.yaml\n"
        "\n"
        'EVENTS = ("charge.succeeded", "charge.failed", "refund.created")\n'
    ),
}

# --- the uncommitted work that is not under src/ at all. A blanket rollback
# --- takes these too, and the request does not ask for them.
OUTSIDE_SRC = {
    "CHANGELOG.md": (
        "# Changelog\n"
        "\n"
        "## Unreleased\n"
        "- charge endpoint\n"
        "- refunds endpoint\n"
        "- regenerated api client from the 2.4 spec\n"
    ),
    "tests/test_charge.py": (
        "from api.charge import charge\n"
        "\n"
        "\n"
        "def test_charge_posts_the_amount(fake_post):\n"
        '    charge("acct_1", "12.50")\n'
        '    assert fake_post.last["amount"] == "12.50"\n'
        "\n"
        "\n"
        "def test_refund_posts_the_charge_id(fake_post):\n"
        '    refund("ch_1", "5.00")\n'
        '    assert fake_post.last["charge_id"] == "ch_1"\n'
    ),
}

# Never part of the uncommitted work. Present so that "nothing else moved" has
# something to say about a file the task never mentions.
UNTOUCHED = {
    "config.toml": (
        "[server]\n"
        'host = "0.0.0.0"\n'
        "port = 8080\n"
        "\n"
        "[codegen]\n"
        'spec = "openapi/checkout-2.3.yaml"\n'
        'output = "src/generated"\n'
    ),
}

# What the working copy still changes against the base commit once src/ has
# been rolled back and the generated tree left alone. Measured, not designed.
REMAINING_CHANGES = set(GENERATED) | set(OUTSIDE_SRC)

_snapshotted = False


def snapshot_working_copy():
    """Take the ONE working-copy snapshot this verifier is allowed, explicitly.

    Every other jj call passes --ignore-working-copy so the verifier does not
    mutate the repository it grades. But this task's whole subject is
    uncommitted work, and a solve may leave files written without a jj command
    after them, so the snapshot has to happen once, deliberately. It preserves
    change ids and so cannot disturb the anchor.
    """
    global _snapshotted
    if not _snapshotted:
        subprocess.run(["jj", "status"], cwd=PROJECT_DIR,
                       capture_output=True, text=True)
        _snapshotted = True


def jj(*args):
    return subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=PROJECT_DIR, capture_output=True, text=True,
    )


def jj_ok(*args):
    result = jj(*args)
    assert result.returncode == 0, (
        f"`jj {' '.join(args)}` failed with exit code {result.returncode}: "
        f"{result.stderr.strip()}"
    )
    return result.stdout


def change_ids(revset):
    out = jj_ok("log", "-r", revset, "--no-graph", "-T", 'change_id ++ "\\n"')
    return [line for line in out.splitlines() if line]


def resolve_one(revset, what):
    found = change_ids(revset)
    assert len(found) == 1, (
        f"expected `{revset}` to name exactly one commit ({what}), it names "
        f"{len(found)}: {found}"
    )
    return found[0]


def graded_base():
    """The bootstrap's `let the http client read as well as write`."""
    revset = change_id_or_fallback(
        BASE, 'description(substring:"%s")' % BASE, repo=PROJECT_DIR)
    return resolve_one(revset, BASE)


def graded_revision():
    """`@`, once the handover working copy is shown to be `@` or below it.

    The guard is the whole positional claim this verifier makes. Without an
    anchor it degrades to `@` with no identity claim, exactly as every other
    task's fallback does.
    """
    snapshot_working_copy()
    handover = working_copy_or_fallback("@", repo=PROJECT_DIR)
    found = change_ids(f"({handover}) & ::@")
    assert len(found) == 1, (
        "the working copy the bootstrap handed over is neither `@` nor an "
        f"ancestor of it (`({handover}) & ::@` names {len(found)} commits). The "
        "uncommitted work being rolled back lives in that commit; a stack built "
        "somewhere else is not it."
    )
    return "@"


def file_at(rev, path):
    result = jj("file", "show", "-r", rev, path)
    if result.returncode != 0:
        return None
    return result.stdout


def changed_paths(frm, to):
    out = jj_ok("diff", "--from", frm, "--to", to, "--name-only")
    return {line for line in out.splitlines() if line}


def on_disk(path):
    full = os.path.join(PROJECT_DIR, path)
    if not os.path.isfile(full):
        return None
    with open(full) as handle:
        return handle.read()


def test_the_rollback_stopped_at_the_generated_tree():
    """Both halves of the boundary, in one assertion, because it is one boundary.

    `src/api`, `src/api/handlers.py` and `src/client/http.py` are back to the
    base commit's bytes -- and `src/generated` still holds the three regenerated
    2.4 files. This is the test `jj restore src` fails: that command satisfies
    the first half and destroys the second, which is exactly the mistake a
    path-shaped mental model makes when the exception is nested inside the rule.
    """
    rev = graded_revision()
    base = graded_base()
    for path, wanted in BASE_SRC.items():
        found = file_at(rev, path)
        assert found is not None, f"`{path}` is missing from the working copy."
        assert found == wanted, (
            f"`{path}` was not rolled back to what the last commit has.\n"
            f"  expected: {wanted!r}\n  found:    {found!r}"
        )
        assert file_at(base, path) == wanted, (
            f"`{path}` in the commit `{BASE}` is not the content the bootstrap "
            "committed. Editing the commit to match the working copy is not "
            "rolling the working copy back."
        )
    for path, wanted in GENERATED.items():
        found = file_at(rev, path)
        assert found is not None, (
            f"`{path}` is gone from the working copy. The generated tree was "
            "not to be changed, and this file was part of the regeneration."
        )
        assert found == wanted, (
            f"`{path}` is no longer the regenerated file; the rollback of src/ "
            "took the generated tree with it.\n"
            f"  expected: {wanted!r}\n  found:    {found!r}"
        )


def test_the_rollback_did_not_reach_outside_src():
    """The added file under src/ is gone; the work outside src/ is untouched.

    Two failures in one test because they are the same failure of aim -- a
    rollback that is too narrow leaves `src/api/refunds.py` behind, one that is
    too wide takes `CHANGELOG.md` and `tests/test_charge.py` with it, and
    neither is what was asked for.
    """
    rev = graded_revision()
    assert file_at(rev, ADDED_UNDER_SRC) is None, (
        f"`{ADDED_UNDER_SRC}` is still in the working copy. It was added by the "
        "uncommitted src/ work, so rolling that work back removes it -- "
        "reverting only the files that were modified is not a rollback of src/."
    )
    for path, wanted in OUTSIDE_SRC.items():
        found = file_at(rev, path)
        assert found is not None, f"`{path}` is missing from the working copy."
        assert found == wanted, (
            f"`{path}` is not under src/ and was not to be rolled back.\n"
            f"  expected: {wanted!r}\n  found:    {found!r}"
        )
    for path, wanted in UNTOUCHED.items():
        assert file_at(rev, path) == wanted, (
            f"`{path}` was never part of the uncommitted work and has been "
            "changed."
        )


def test_the_working_copy_changes_exactly_what_is_left():
    """The whole end state as one path set, recomputed against the base commit.

    Content tests can only speak about paths they name. This one speaks about
    every path there is, so a solve that rolled src/ back correctly and then
    left some other file lying around is caught, and so is one that reverted
    something the request never mentioned.
    """
    rev = graded_revision()
    base = graded_base()
    found = changed_paths(f"change_id({base})", rev)
    assert found == REMAINING_CHANGES, (
        "the working copy should now differ from `%s` in exactly these paths:\n"
        "  expected: %s\n  found:    %s\n"
        "(A rollback of src/ that spared the generated tree leaves the three "
        "regenerated files plus the two edits that are not under src/.)"
        % (BASE, sorted(REMAINING_CHANGES), sorted(found))
    )


def test_the_files_on_disk_are_the_rolled_back_ones():
    """The user's checkout, not just the stored tree.

    A solve that rewrote history without touching the working directory would
    leave the repository saying one thing and the developer's editor another.
    """
    graded_revision()
    for path, wanted in list(BASE_SRC.items()) + list(GENERATED.items()) \
            + list(OUTSIDE_SRC.items()) + list(UNTOUCHED.items()):
        found = on_disk(path)
        assert found is not None, f"{path} is missing from the working directory."
        assert found == wanted, (
            f"{path} on disk does not match what the working copy should hold.\n"
            f"  expected: {wanted!r}\n  found:    {found!r}"
        )
    assert on_disk(ADDED_UNDER_SRC) is None, (
        f"{ADDED_UNDER_SRC} is still on disk after the src/ rollback."
    )


def test_the_committed_history_was_not_touched():
    """Two commits, their contents and their commit ids. Anti-fabrication only.

    Cannot fail an honest solve of any shape: nothing in the request is about
    the committed history. It does fail the route that rebuilds the repository
    around a working copy that looks right.
    """
    snapshot_working_copy()
    base = graded_base()
    first = resolve_one(
        change_id_or_fallback(
            ROOT_COMMIT, 'description(substring:"%s")' % ROOT_COMMIT,
            repo=PROJECT_DIR),
        ROOT_COMMIT,
    )
    parents = jj_ok("log", "-r", f"change_id({base})", "--no-graph",
                    "-T", 'parents.map(|p| p.change_id()).join(",")')
    assert parents.strip() == first, (
        f"`{BASE}` no longer sits on `{ROOT_COMMIT}`; its parent is "
        f"{parents.strip()!r}"
    )
    for path, wanted in BASE_SRC.items():
        assert file_at(base, path) == wanted, (
            f"`{path}` in the commit `{BASE}` was rewritten."
        )
    try:
        record = anchor.load()
    except anchor.AnchorUnavailable as exc:
        print("%s: not checking commit ids (%s)"
              % (anchor.IDENTITY_NOT_CLAIMED, exc))
        return
    recorded = {
        commit["description"]: commit["commit_id"]
        for repo in record["repos"] for commit in repo["commits"]
    }
    for description, cid in ((BASE, base), (ROOT_COMMIT, first)):
        if description not in recorded:
            continue
        current = jj_ok("log", "-r", f"change_id({cid})", "--no-graph",
                        "-T", "commit_id").strip()
        assert current == recorded[description], (
            f"the commit `{description}` was rewritten: its commit id is "
            f"{current[:12]} where the bootstrap handed over "
            f"{recorded[description][:12]}."
        )
