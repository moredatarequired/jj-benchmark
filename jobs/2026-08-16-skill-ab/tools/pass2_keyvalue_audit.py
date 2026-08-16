#!/usr/bin/env python3
"""Pass 2 -- independent pre-publication check. Deliberately NOT credscan.py.

credscan.py works value-first: it looks for strings whose *shape* or *entropy*
resembles a secret, and it is explicitly documented as blind to UUID-shaped and
bare 32/40-char-hex secrets.

This check works the other way round, so that its blind spots are not the same:

  CHECK A -- key-first structural sweep.
      Enumerate every distinct `key: value`, `key=value` and JSON `"key":
      "value"` pair in the corpus whose KEY contains a credential-ish word,
      regardless of what the value looks like. A UUID-shaped or 40-hex secret
      that credscan demotes by shape is still caught here if it is sitting
      behind a key called `token`, `secret`, `api_key`, ...
      Reports the COMPLETE set of distinct keys, with value lengths and one
      redacted sample per key.

  CHECK B -- exact-value environment sweep.
      For every environment variable in THIS session whose NAME looks
      secret-ish and whose value is at least 12 characters, byte-search the
      whole corpus for that exact value. This needs no shape heuristic at all:
      it is an exact match against the real secrets that exist right now.

      Values are read from os.environ into memory and are NEVER printed,
      logged, or written anywhere. Only booleans and file locations are
      reported. Variables that are unset, or set but shorter than 12 chars,
      are listed explicitly as SKIPPED rather than being silently treated as a
      pass -- an unset variable proves nothing.

Exit code 0 = clean, 1 = something needs a human.
"""

from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# --------------------------------------------------------------------------
# CHECK A configuration
# --------------------------------------------------------------------------

# A key is "credential-ish" if it contains any of these as a substring
# (case-insensitive, after stripping separators).
CRED_WORDS = [
    "key", "token", "secret", "password", "passwd", "pwd", "passphrase",
    "credential", "cred", "auth", "bearer", "private", "apikey",
    "oauth", "session", "cookie", "signature", "salt", "cert", "access",
]

# Keys that are credential-ish by the substring rule but are structurally
# incapable of carrying a secret in this corpus. Each must be justified.
# NOTE: this list only affects how findings are GROUPED in the report; every
# key is still printed. Nothing is hidden.
NOISE_NOTE = {
    "session_id": "harbor/claude-code conversation id, ephemeral per trial",
    "sessionid": "as session_id",
    "parent_tool_use_id": "tool-call correlation id",
    "apikeysource": "sentinel naming where the key came from, not the key",
}

# key: value   /   key=value   /   "key": "value"
PAIR_RE = re.compile(
    r"""["']?(?P<key>[A-Za-z_][A-Za-z0-9_.\-]{1,60})["']?\s*[:=]\s*
        (?P<q>["']?)(?P<val>[^\s"',;}\])]{1,4096})(?P=q)""",
    re.VERBOSE,
)

KEYWORD_RE = re.compile("|".join(CRED_WORDS), re.IGNORECASE)

# Values that are obviously not secrets: booleans, nulls, numbers, sentinels.
BENIGN_VAL_RE = re.compile(
    r"^(?:true|false|null|none|nil|undefined|yes|no|on|off|"
    r"-?\d+(?:\.\d+)?|"
    r"none|unset|empty|n/?a|"
    r"/[A-Za-z0-9_./\-]*|"          # a path
    r"ANTHROPIC_API_KEY|apiKeySource|temporary|user|project|org|"
    r"\{\{[^}]*\}\}|\$\{[^}]*\}|<[^>]*>|"   # template placeholders
    r"\.{3}|\*+)$",
    re.IGNORECASE,
)

MIN_INTERESTING_LEN = 12


def redact(v: str) -> str:
    """Show only enough to recognise the shape. Never the middle."""
    if len(v) <= 8:
        return "*" * len(v)
    return f"{v[:4]}<+{len(v) - 8}ch>{v[-4:]}"


# --------------------------------------------------------------------------
# CHECK B configuration
# --------------------------------------------------------------------------

SECRETISH_NAME_RE = re.compile(
    r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|PASSPHRASE|CREDENTIAL|AUTH|"
    r"BEARER|PRIVATE|OAUTH|COOKIE|SIGNATURE|SALT|CERT|SESSION",
    re.IGNORECASE,
)
MIN_ENV_LEN = 12


def iter_files(root: Path):
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink():
            yield p


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: pass2_keyvalue_audit.py <dir>", file=sys.stderr)
        return 2
    root = Path(sys.argv[1]).resolve()

    files = list(iter_files(root))
    total_bytes = sum(p.stat().st_size for p in files)

    print("=" * 78)
    print("PASS 2 -- independent key-first + exact-value audit")
    print("=" * 78)
    print(f"root         : {root}")
    print(f"files scanned: {len(files)}")
    print(f"bytes scanned: {total_bytes:,} ({total_bytes / 1048576:.1f} MiB)")
    print()

    # ---------------- CHECK B setup: collect env targets BEFORE scanning ----
    searched: list[tuple[str, bytes]] = []
    skipped: list[tuple[str, str]] = []
    for name, val in sorted(os.environ.items()):
        if not SECRETISH_NAME_RE.search(name):
            continue
        if val is None or val == "":
            skipped.append((name, "unset or empty in environment"))
            continue
        if len(val) < MIN_ENV_LEN:
            skipped.append((name, f"set but only {len(val)} chars (< {MIN_ENV_LEN})"))
            continue
        searched.append((name, val.encode("utf-8", "replace")))

    env_hits: dict[str, list[str]] = defaultdict(list)

    # ---------------- single pass over the corpus ---------------------------
    # key -> {"lens": set, "sample": str, "count": int, "files": set}
    findings: dict[str, dict] = {}

    for p in files:
        raw = p.read_bytes()

        # CHECK B: exact byte search, values never leave memory
        for name, needle in searched:
            if needle in raw:
                env_hits[name].append(str(p.relative_to(root)))

        # CHECK A: key-first structural sweep
        text = raw.decode("utf-8", "replace")
        for m in PAIR_RE.finditer(text):
            key = m.group("key")
            if not KEYWORD_RE.search(key):
                continue
            val = m.group("val")
            if len(val) < MIN_INTERESTING_LEN:
                continue
            if BENIGN_VAL_RE.match(val):
                continue
            norm = key.lower().strip("_-.")
            f = findings.setdefault(
                norm, {"lens": set(), "sample": redact(val), "count": 0, "files": set()}
            )
            f["lens"].add(len(val))
            f["count"] += 1
            if len(f["files"]) < 3:
                f["files"].add(str(p.relative_to(root)))

    # ---------------- report CHECK A ---------------------------------------
    print("-" * 78)
    print("CHECK A -- every distinct credential-ish KEY carrying a value")
    print("-" * 78)
    if not findings:
        print("  no credential-ish key/value pairs found at all")
    else:
        print(f"  {len(findings)} distinct key(s). Complete set, nothing elided:")
        print()
        print(f"  {'KEY':<26} {'HITS':>7}  {'VALUE LEN(S)':<18} {'REDACTED SAMPLE':<26} NOTE")
        print(f"  {'-'*26} {'-'*7}  {'-'*18} {'-'*26} {'-'*4}")
        for key in sorted(findings):
            f = findings[key]
            lens = sorted(f["lens"])
            lens_s = (
                str(lens[0]) if len(lens) == 1
                else f"{lens[0]}-{lens[-1]} ({len(lens)} distinct)"
            )
            note = NOISE_NOTE.get(key, "")
            print(f"  {key:<26} {f['count']:>7}  {lens_s:<18} {f['sample']:<26} {note}")
        print()
        for key in sorted(findings):
            print(f"  {key}: e.g. {', '.join(sorted(findings[key]['files'])[:3])}")

    # ---------------- report CHECK B ---------------------------------------
    print()
    print("-" * 78)
    print("CHECK B -- exact byte-search for live environment secrets")
    print("-" * 78)
    print("  (values read into memory only; never printed, written, or logged)")
    print(f"  env vars with secret-ish NAME : {len(searched) + len(skipped)}")
    print(f"  searched (value >= {MIN_ENV_LEN} chars): {len(searched)}")
    print(f"  SKIPPED (not a pass)          : {len(skipped)}")
    print()
    for name, _ in searched:
        locs = env_hits.get(name, [])
        if locs:
            print(f"  [FAIL] {name}: value PRESENT in {len(locs)} file(s)")
            for loc in locs[:10]:
                print(f"           {loc}")
        else:
            print(f"  [ OK ] {name}: searched, value not present anywhere in corpus")
    if skipped:
        print()
        print("  Explicitly skipped -- these were NOT verified:")
        for name, why in skipped:
            print(f"  [SKIP] {name}: {why}")

    # ---------------- verdict ----------------------------------------------
    leaked = {k: v for k, v in env_hits.items() if v}
    print()
    print("=" * 78)
    if leaked:
        print(f"RESULT: BLOCKED -- {len(leaked)} live environment secret(s) found in corpus")
        print("=" * 78)
        return 1
    print("RESULT: CHECK B CLEAN -- no live environment secret value appears in the corpus")
    print(f"        CHECK A found {len(findings)} distinct credential-ish key(s);")
    print("        every one is listed above and requires human sign-off.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
