"""Verifier for the restore_interactive task.

The task asks for a file that a mid-stack commit deleted by mistake to be put
back *in that commit*, leaving everything else about the history alone.

Every assertion below is made against repository state -- commit trees, the
paths a commit changes, file contents at a revision -- and never against jj's
human-readable prose. The one place where jj output is parsed at all,
`descriptions()` and `changed_paths()`, uses an explicit template and
`--name-only`, whose output is data (descriptions, paths) rather than English.

Note on revision addressing: `test_history_shape` pins the four commits above
the root to the linear chain ending at `@`, in order, by description. Every
other test therefore addresses them positionally -- `@---` is `Initial
commit`, `@--` is `remove legacy module`, `@-` is `add logging` -- which avoids
depending on jj's revset string-pattern defaults.
"""

import os
import subprocess

import pytest

PROJECT_DIR = "/home/user/myproject"

REV_INITIAL = "@---"
REV_CLEANUP = "@--"
REV_LOGGING = "@-"

EXPECTED_DESCRIPTIONS = [
    "Initial commit",
    "remove legacy module",
    "add logging",
    "",
]

SETTINGS_TOML = '[server]\nhost = "127.0.0.1"\nport = 8080\n\n[logging]\nlevel = "info"\n'
MAIN_INITIAL = "from legacy import old_helper\n\n\ndef main():\n    print(old_helper())\n"
MAIN_AFTER_CLEANUP = 'def main():\n    print("running")\n'
MAIN_AFTER_LOGGING = (
    "import logging\n\n\ndef main():\n    logging.info(\"start\")\n    print(\"running\")\n"
)
NOTES_TXT = "todo: review the release checklist\n"


def jj(*args):
    """Run a jj command in the project and return the CompletedProcess."""
    return subprocess.run(
        ["jj", *args], cwd=PROJECT_DIR, capture_output=True, text=True
    )


def jj_ok(*args):
    result = jj(*args)
    assert result.returncode == 0, (
        f"`jj {' '.join(args)}` failed with exit code {result.returncode}: "
        f"{result.stderr.strip()}"
    )
    return result.stdout


def descriptions(revset):
    """First line of the description of every commit in revset, oldest first.

    Each description is bracketed in the template so that an empty description
    is still a line of output, and so trailing whitespace cannot be lost.
    """
    out = jj_ok(
        "log", "-r", revset, "--no-graph", "--reversed",
        "-T", '"[" ++ description.first_line() ++ "]\\n"',
    )
    lines = [line for line in out.splitlines() if line]
    for line in lines:
        assert line.startswith("[") and line.endswith("]"), (
            f"unexpected line in jj log output: {line!r}"
        )
    return [line[1:-1] for line in lines]


def changed_paths(rev):
    """The set of paths a revision changes relative to its parent."""
    out = jj_ok("diff", "-r", rev, "--name-only")
    return {line for line in out.splitlines() if line}


def tree_paths(rev):
    """The set of paths present in a revision's tree."""
    out = jj_ok("file", "list", "-r", rev)
    return {line for line in out.splitlines() if line}


def file_at(rev, path):
    """Contents of path at rev. Fails the test if the path is not there."""
    result = jj("file", "show", "-r", rev, path)
    assert result.returncode == 0, (
        f"`{path}` is not present in revision `{rev}`: {result.stderr.strip()}"
    )
    return result.stdout


def test_history_shape():
    """Exactly the original four commits, in the original order, still exist."""
    chain = descriptions("::@ ~ root()")
    assert chain == EXPECTED_DESCRIPTIONS, (
        "The four commits above the root must still be, oldest first: "
        f"{EXPECTED_DESCRIPTIONS}. Got: {chain}"
    )
    all_commits = descriptions("all() ~ root()")
    assert len(all_commits) == 4, (
        "The repository must still contain exactly four commits above the root; "
        f"found {len(all_commits)}: {all_commits}"
    )


def test_settings_restored_into_cleanup_commit():
    """`remove legacy module` contains settings.toml with the original content."""
    assert "settings.toml" in tree_paths(REV_CLEANUP), (
        "`settings.toml` is still missing from the `remove legacy module` commit."
    )
    assert file_at(REV_CLEANUP, "settings.toml") == SETTINGS_TOML, (
        "`settings.toml` in the `remove legacy module` commit does not have the "
        "content it has in `Initial commit`."
    )


def test_cleanup_commit_no_longer_deletes_settings():
    """Structural check: that commit does not change settings.toml at all.

    Compared against its parent rather than against a literal, so that a
    solution which "fixed" things by rewriting `Initial commit` instead cannot
    pass; the parent's content is pinned separately below.
    """
    assert file_at(REV_INITIAL, "settings.toml") == SETTINGS_TOML, (
        "`settings.toml` in `Initial commit` was modified; it must be left alone."
    )
    assert file_at(REV_CLEANUP, "settings.toml") == file_at(
        REV_INITIAL, "settings.toml"
    ), "The `remove legacy module` commit still changes `settings.toml`."
    assert "settings.toml" not in changed_paths(REV_CLEANUP), (
        "The `remove legacy module` commit must no longer touch `settings.toml`, "
        f"but it changes: {sorted(changed_paths(REV_CLEANUP))}"
    )


def test_cleanup_commit_keeps_its_own_changes():
    """The rest of that commit is untouched: legacy.py gone, main.py rewritten."""
    assert "legacy.py" in tree_paths(REV_INITIAL), (
        "`legacy.py` is missing from `Initial commit`; that commit must be left alone."
    )
    assert file_at(REV_INITIAL, "main.py") == MAIN_INITIAL, (
        "`main.py` in `Initial commit` was modified; it must be left alone."
    )
    assert "legacy.py" not in tree_paths(REV_CLEANUP), (
        "`legacy.py` must still be deleted by the `remove legacy module` commit."
    )
    assert file_at(REV_CLEANUP, "main.py") == MAIN_AFTER_CLEANUP, (
        "The `remove legacy module` commit's change to `main.py` was altered."
    )
    assert changed_paths(REV_CLEANUP) == {"legacy.py", "main.py"}, (
        "The `remove legacy module` commit must change exactly `legacy.py` and "
        f"`main.py`, but it changes: {sorted(changed_paths(REV_CLEANUP))}"
    )


def test_later_commit_intact():
    """`add logging` still records only its own change to main.py."""
    assert changed_paths(REV_LOGGING) == {"main.py"}, (
        "The `add logging` commit must change only `main.py`, but it changes: "
        f"{sorted(changed_paths(REV_LOGGING))}"
    )
    assert file_at(REV_LOGGING, "main.py") == MAIN_AFTER_LOGGING, (
        "The `add logging` commit's change to `main.py` was altered."
    )
    assert file_at(REV_LOGGING, "settings.toml") == SETTINGS_TOML, (
        "`settings.toml` must be present with the original content in the "
        "`add logging` commit."
    )
    assert "legacy.py" not in tree_paths(REV_LOGGING), (
        "`legacy.py` must stay deleted in the `add logging` commit."
    )


def test_working_copy_intact():
    """The working copy still adds notes.txt and nothing else."""
    assert changed_paths("@") == {"notes.txt"}, (
        "The working copy's only change relative to its parent must be the "
        f"addition of `notes.txt`, but it changes: {sorted(changed_paths('@'))}"
    )
    assert file_at("@", "notes.txt") == NOTES_TXT, "`notes.txt` was modified."
    assert file_at("@", "settings.toml") == SETTINGS_TOML, (
        "`settings.toml` must be present with the original content in the "
        "working copy."
    )
    assert file_at("@", "main.py") == MAIN_AFTER_LOGGING, "`main.py` was modified."
    assert "legacy.py" not in tree_paths("@"), (
        "`legacy.py` must stay deleted in the working copy."
    )


def test_settings_on_disk():
    """The checked-out tree really has the file back, not just the commits."""
    settings_path = os.path.join(PROJECT_DIR, "settings.toml")
    assert os.path.isfile(settings_path), (
        f"{settings_path} does not exist on disk."
    )
    with open(settings_path) as fh:
        assert fh.read() == SETTINGS_TOML, (
            f"{settings_path} on disk does not have the original content."
        )
