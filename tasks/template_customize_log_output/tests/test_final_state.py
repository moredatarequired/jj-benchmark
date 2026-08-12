r"""Grade the template alias by what it RENDERS, and accept every route to it.

The previous verifier read the alias with `jj config get` -- which returns the
value after TOML decoding -- and then required the decoded text to contain the
four literal characters `"\n"` (quote, backslash, n, quote). That penalised jj's
own documented interface. `jj config set`'s VALUE argument is parsed as a TOML
fragment, so the natural invocation is rejected outright and the agent has to
hand it a TOML string; and inside a TOML *basic* (double-quoted) string a single
`\n` is an escape that decodes to a real newline, while a TOML *literal*
(single-quoted) string keeps the two characters. Measured on jj 0.38.0, all four
of the following define the required alias and all four render identically:

  | the newline, as it reaches TOML  | decodes to    | old test |
  |---------------------------------|---------------|----------|
  | basic string, `\\n`  (doubled)   | backslash + n | PASS     |
  | literal string, `\n`            | backslash + n | PASS     |
  | basic string, `\n`  (single)    | 0x0A newline  | FAIL     |
  | hand-edited file, literal `\n`  | backslash + n | PASS     |

So the old assertion scored TOML escaping trivia rather than jj capability, and
the agent that reached for `jj config set` was the one that lost. In the shard-5
three-model baseline it cost sonnet two of its five attempts at this task (its
other two misses on it were genuine, and haiku's three passes were all
hand-written config files -- it never used `jj config set` at all).

The fix has two halves:

  * `test_alias_renders_the_required_format` is the real assertion, and it is
    behavioural: render the alias with `jj log -T log_custom` and require it to
    be byte-identical to the template the instruction specifies, over every
    commit in the repository. That compares rendered output, so it cannot see
    how the value was quoted, and it still catches every part of the spec --
    a full `change_id` instead of `change_id.short()`, a different separator,
    or a missing trailing `"\n"` all change the bytes.
  * `test_template_alias_configured` still reads the config, because the
    instruction names the pieces (`change_id.short()`, `description.first_line()`)
    and because an all-empty-description repository cannot tell
    `description.first_line()` from `description` by rendering alone. It is now
    tolerant: the decoded value is normalised by turning a real newline back
    into the two characters `\n` before the substring check, so the
    TOML-escaped and hand-written forms are treated as what they are -- the
    same alias.

Also fixed while here: the old file mutated the repository it was grading with
`jj describe -m ... check=True` (clobbering `@`'s description) and made every
jj call without `--ignore-working-copy`, so each read snapshotted the working
copy and appended an operation, and the verifier's first run changed what its
second run measured. Nothing here writes to the repository, and every jj call
passes `--ignore-working-copy`.
"""

import subprocess

PROJECT_DIR = "/home/user/repo"

ALIAS = "log_custom"
CONFIG_KEY = f"template-aliases.{ALIAS}"

# The template instruction.md specifies, verbatim: the short change id, then
# " | ", then the first line of the description, then a newline. This is the
# reference the alias has to render the same as.
REQUIRED_TEMPLATE = (
    'change_id.short() ++ " | " ++ description.first_line() ++ "\\n"'
)


def jj(*args):
    """A read-only jj call.

    `--ignore-working-copy` is not optional: every ordinary jj command
    snapshots the working copy before answering, which appends an operation and
    rewrites `@`, so a verifier without it mutates the repository it is grading
    and its second run measures what its first run did.
    """
    return subprocess.run(
        ["jj", "--ignore-working-copy", *args],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )


def test_template_alias_configured():
    """The alias exists under the required name and names the required pieces.

    Tolerant of how the value was quoted. `jj config get` returns the value
    after TOML decoding, so an alias written with `jj config set` and a
    single-escaped basic string arrives with a real newline where a
    hand-written literal string arrives with a backslash and an `n`. Both spell
    the same jj template, so the real newline is normalised back before the
    text is inspected.
    """
    result = jj("config", "get", CONFIG_KEY)
    assert result.returncode == 0, (
        f"`jj config get {CONFIG_KEY}` failed, so no template alias named "
        f"{ALIAS!r} is configured: {result.stderr.strip()}"
    )

    value = result.stdout.strip("\n")
    # A real 0x0A inside the value is a TOML-decoded `\n` escape; put it back
    # so that both ways of writing the same template compare equal here.
    normalized = value.replace("\n", "\\n")

    assert "change_id.short()" in normalized, (
        f"Alias {ALIAS!r} does not use change_id.short(): {value!r}"
    )
    assert "description.first_line()" in normalized, (
        f"Alias {ALIAS!r} does not use description.first_line(): {value!r}"
    )
    assert '" | "' in normalized or "' | '" in normalized, (
        f"Alias {ALIAS!r} is missing the ' | ' separator: {value!r}"
    )
    assert '"\\n"' in normalized or "'\\n'" in normalized, (
        f"Alias {ALIAS!r} does not end its line with a newline: {value!r}"
    )


def test_alias_renders_the_required_format():
    """The alias renders exactly what the instruction asks for.

    Rendered output is compared against the specified template applied to the
    same revisions, so this is indifferent to how the alias was quoted, which
    config layer it lives in, and whether it was written by `jj config set` or
    by hand -- and it is not indifferent to any part of the required format.
    """
    actual = jj("log", "-r", "all()", "--no-graph", "-T", ALIAS)
    assert actual.returncode == 0, (
        f"`jj log -T {ALIAS}` failed, so the template alias is not usable: "
        f"{actual.stderr.strip()}"
    )

    expected = jj("log", "-r", "all()", "--no-graph", "-T", REQUIRED_TEMPLATE)
    assert expected.returncode == 0, (
        f"the verifier's own reference template failed to render: "
        f"{expected.stderr.strip()}"
    )

    assert actual.stdout == expected.stdout, (
        f"`jj log -T {ALIAS}` rendered {actual.stdout!r}, but the required "
        f"template ({REQUIRED_TEMPLATE}) renders {expected.stdout!r}"
    )
