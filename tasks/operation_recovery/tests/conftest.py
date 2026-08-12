"""Make every task's verifier refuse to score a repository that was rebuilt.

This file rides along in the same tests/ directory harbor mounts read-only at
/tests, exactly like vacuity_floor.json and bootstrap_anchor.json, so it needs
no change to tests/test.sh -- which has to stay byte-identical across all 53
tasks (scripts/lint_tasks.py enforces that by sha256).

Verified, not assumed: pytest collects a conftest.py that sits beside the test
file even when the test file is named by ABSOLUTE path from an unrelated
directory, which is how test.sh invokes it:

    python3 -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_final_state.py -rA

WHY A SESSION-SCOPED autouse FIXTURE RATHER THAN A TEST
======================================================

An anchor assertion written as a test function would pass on the untouched
bootstrap image BY CONSTRUCTION, so scripts/vacuity_floor.py would measure it
into the floor -- and tests/test.sh excludes floored tests from BOTH sides of
the partial-credit fraction. A failing floored test then caps credit at
(scored-1)/scored instead of zeroing it, which for a nine-test task means a
detected cheat still scores 0.833. As a fixture it is not a test at all: when it
fails, every test in the file errors during setup, no scored test passes, and
the credit numerator is empty -- reward 0, with no change to test.sh and no
change to any floor file.

Measured with the exact pins in the task images (pytest==8.4.1,
pytest-json-ctrf==0.3.5), three tests and a failing session-scoped autouse
fixture:

    pytest exit code 1
    ctrf.json  summary: {"tests": 3, "passed": 0, "failed": 3, ...}
    ctrf.json  one entry per test, correct names, status "failed" for each

That last line is the load-bearing measurement. If the plugin had emitted ZERO
tests, test.sh would have called the run unscorable, written verifier_error.txt
and moved ctrf.json aside, and scripts/check_run_results.py would classify the
trial ERRORED-INFRA -- recording a cheat as broken infrastructure. It does not:
setup errors are reported per test, with the nodeids unchanged, so the floor
files stay valid too.

The fixture is also the reason nothing here may raise at IMPORT time. An
exception while conftest.py is being imported makes pytest exit 4 having
reported no tests at all, which IS the unscorable path. So the import block
below is deliberately trivial and every failure happens inside the fixture body.
"""

from __future__ import annotations

import pytest

from anchor import assert_bootstrap_anchor


@pytest.fixture(scope="session", autouse=True)
def bootstrap_anchor() -> str:
    """Fail the whole session if this repository was rebuilt rather than solved.

    Session-scoped so the jj calls happen once per run rather than once per
    test, and autouse so no task's test file has to opt in -- the point is that
    all 53 get it without 53 edits.
    """
    note = assert_bootstrap_anchor()
    print(note)
    return note
