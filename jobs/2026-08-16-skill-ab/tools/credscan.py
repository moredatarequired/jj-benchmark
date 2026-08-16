#!/usr/bin/env python3
"""
credscan.py -- pre-publication credential scanner for jj-benchmark trial records.

Gate for archiving trial records to a PUBLIC repo.

Design premise (from the baseline-archive precedent): the dangerous failure mode
is conflating a credential variable NAME appearing in telemetry with an actual
secret VALUE. All 275 ANTHROPIC_API_KEY hits in the baseline archive were the
valueless `apiKeySource` telemetry field. So this scanner keeps three separate
ledgers:

  1. VALUE patterns  -- shapes that look like real secrets.            (fatal)
  2. NAME patterns   -- bare credential variable names, bucketed by
                        whether a value sits next to them on the line.
                        name-only / name-with-name-value = benign,
                        name-with-value                  = fatal.
  3. LIVE creds      -- literal values pulled from os.environ at runtime
                        and searched for. Values are NEVER printed,
                        written, or logged -- only a boolean + locations.

Nothing in this script ever emits a secret in full. Matched tokens are shown
as first-4 + length + last-4 at most; live credential values are shown not at
all.

==============================================================================
LIMITATIONS -- READ BEFORE TRUSTING A "CLEAN" VERDICT
==============================================================================
This gate is a filter, not a proof. Two classes of real secret pass it, both
KNOWN and ACCEPTED, neither fixed:

  1. UUID-SHAPED SECRETS SLIP.
     Any token matching 8-4-4-4-12 hex is demoted unconditionally by the
     `uuid` shape rule, without an entropy check, without an allowlist entry,
     and without appearing in any FAIL bucket. On arm A that rule demoted
     63,067 tokens -- by far the largest single demotion class -- so a real
     secret hiding among them would be invisible.
     This matters because UUIDv4 is a COMMON REAL API-KEY FORMAT: session
     tokens, tenant keys, webhook signing keys, and several vendors' primary
     API keys are literally UUIDs. `credscan` cannot tell one from a trial ID.

  2. BARE HEX-DIGEST-SHAPED SECRETS SLIP.
     Any all-hex token is demoted by the `pure-hex-digest` rule (3,044 on
     arm A), and `[nrtbf]`-prefixed hex by `escaped-ws + hex digest` (151).
     32-char and 40-char lowercase hex are ALSO COMMON REAL API-KEY AND
     TOKEN FORMATS (MD5/SHA1-shaped keys, many self-hosted services, HMAC
     signing secrets, older cloud tokens). They are indistinguishable here
     from git SHAs and content digests, which is why the rule exists.

  Consequence: a "CLEAN" verdict means "no secret of a shape this scanner
  models was found". It does NOT mean "no secret is present". For a corpus
  where UUID- or hex-formatted credentials are plausible, this gate must be
  supplemented by a provenance review of where those tokens came from.

  Two further, smaller caveats, documented at their implementation sites:
  a token inside a JSON field literally named "signature" is demoted
  (34,830 on arm A), and the boundary-erosion guard below covers only the
  specific VALUE patterns, not the generic bucket's shape rules.
==============================================================================

Usage:  python3 credscan.py DIR [DIR ...] [--max-examples N] [--all]
Exit:   0 = clean, 1 = findings that must block a push, 2 = usage/IO error.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import sys
from collections import defaultdict

# --------------------------------------------------------------------------
# Redaction helpers. Every path that emits matched text goes through these.
# --------------------------------------------------------------------------

MAX_LINE_ECHO = 200


def redact(tok: str) -> str:
    """First 4 + last 4, middle replaced by a length marker. Never full text."""
    tok = tok.strip()
    if len(tok) <= 8:
        return "*" * len(tok)
    return f"{tok[:4]}<+{len(tok) - 8}ch>{tok[-4:]}"


# Tokens that are safe to echo verbatim in a context line: they are the
# credential *names* we are deliberately looking for, plus obvious literals.
_ECHO_SAFE = set()  # populated after NAME_PATTERNS is defined
_LONG_TOKEN = re.compile(r"[A-Za-z0-9_\-]{20,}")


def redact_line(line: str) -> str:
    """Echo a line of context with every long token redacted."""
    line = line.rstrip("\n")
    if len(line) > MAX_LINE_ECHO:
        line = line[:MAX_LINE_ECHO] + "…"

    def sub(m: "re.Match[str]") -> str:
        t = m.group(0)
        return t if t in _ECHO_SAFE else redact(t)

    return _LONG_TOKEN.sub(sub, line)


def shannon(s: str) -> float:
    """Bits of entropy per character."""
    if not s:
        return 0.0
    counts = defaultdict(int)
    for ch in s:
        counts[ch] += 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


# --------------------------------------------------------------------------
# VALUE patterns -- shapes that look like an actual secret.
# --------------------------------------------------------------------------

VALUE_PATTERNS = [
    ("sk_ant_key",        re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}")),
    ("sk_generic_key",    re.compile(r"\bsk-(?!ant-)[A-Za-z0-9]{20,}")),
    ("pyd_gateway_token", re.compile(r"\bpyd_[A-Za-z0-9_\-]{8,}")),
    ("logfire_token",     re.compile(r"\b(?:pylf_v\d+_[a-z]+_|lf_)[A-Za-z0-9_\-]{16,}")),
    ("jwt",               re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]+")),
    ("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token",      re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}")),
    ("slack_token",       re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    # Authorization headers / Bearer tokens with a NON-EMPTY value.
    ("bearer_token",      re.compile(r"\bBearer\s+(?!\"\"|''|null\b|None\b)[A-Za-z0-9_\-\.=]{8,}")),
    ("authorization_hdr", re.compile(
        r"[\"']?[Aa]uthorization[\"']?\s*[:=]\s*[\"']?"
        r"(?:(?:Basic|Bearer|Token|ApiKey|Digest)\s+)?"
        r"(?!\"|'|null\b|None\b|\s*[,}\]])[^\"'\s,}\]]{8,}")),
    ("x_api_key_hdr",     re.compile(
        r"[\"']?[Xx]-[Aa]pi-[Kk]ey[\"']?\s*[:=]\s*[\"']?(?!\"|'|null\b|None\b|\s*[,}\]])[^\"'\s,}\]]{8,}")),
    # The catch-all. Extremely noisy on JSON/JSONL telemetry, so matches are
    # triaged by shape+entropy below rather than being fatal on sight.
    ("generic_secretish",  re.compile(r"[A-Za-z0-9_\-]{32,}")),
]

GENERIC_PATTERN = "generic_secretish"

# --------------------------------------------------------------------------
# Boundary-erosion guard.
#
# THE HOLE THIS CLOSES. Seven VALUE patterns above are `\b`-anchored
# (sk_generic_key, logfire_token, jwt, aws_access_key_id, github_token,
# slack_token, bearer_token). Gluing a word character onto the front of such a
# secret destroys the word boundary, so the specific pattern never fires; the
# residue falls into the generic catch-all, where an allowlist prefix or a
# shape rule then demotes it to exit 0. Four working bypasses were
# demonstrated against the previous build:
#     harbor_run_2026_<AWS key>   hb__<gh token>   hb__<sk- key>
#     harbor_<JWT>
# all of which exited 0 with the secret sitting in plain text.
#
# THE FIX, in two halves. Every specific VALUE pattern is recompiled with its
# OUTER `\b` anchors stripped:
#
#   half 1 (detection). Each line is swept with the relaxed patterns. Any
#     relaxed match that the corresponding STRICT pattern did not also produce
#     at the same offset is, by construction, a specific-shape secret whose
#     word boundary was eroded. It is recorded as fatal.
#
#   half 2 (demotion refusal). Before ANY generic-bucket token is demoted --
#     by the allowlist, by a shape rule, or by the signature-field rule -- the
#     token's span is checked against the eroded spans found on that line. An
#     overlap REFUSES the demotion, so no allowlist entry and no shape rule can
#     swallow the residue.
#
# Half 1 is what makes this hole actually closed rather than merely narrowed.
# A demotion-refusal check on its own is not enough: `harbor_<short JWT>` never
# produces a >=32-char generic token at all, so there is no demotion site to
# hang the check on, and the secret would slip with nothing to refuse.
#
# SCOPE, stated plainly: this guard restores the specific VALUE patterns'
# authority over the whole pipeline. It does NOT make the shape rules safe --
# see the LIMITATIONS block at the top of this file.
# --------------------------------------------------------------------------

def _relax(src: str) -> str:
    """Drop the OUTER word-boundary anchors, keep interior ones.

    Only the leading/trailing `\\b` are load-bearing for the glue attack;
    interior `\\b`s (inside the `null\\b|None\\b` negative lookaheads) are part
    of the pattern's own logic and are left alone.
    """
    if src.startswith(r"\b"):
        src = src[2:]
    if src.endswith(r"\b"):
        src = src[:-2]
    return src


RELAXED_VALUE_PATTERNS = [
    (name, re.compile(_relax(pat.pattern)))
    for name, pat in VALUE_PATTERNS
    if name != GENERIC_PATTERN
]

_STRICT_BY_NAME = dict(VALUE_PATTERNS)


def erosion_spans(line: str, hot_relaxed: list[tuple[str, "re.Pattern"]],
                  tally: dict[str, int]) -> list[tuple[str, int, int, str]]:
    """Relaxed specific-pattern matches the STRICT pattern missed on this line.

    Returns [(pattern_name, start, end, matched_text)]. A non-empty result means
    a specific-shape secret is present with its word boundary eroded.
    `tally` accumulates RAW relaxed match counts (before the strict-match
    filter) so the prefilter reconciliation can see them.
    """
    out: list[tuple[str, int, int, str]] = []
    for name, pat in hot_relaxed:
        strict = _STRICT_BY_NAME[name]
        strict_starts = {sm.start() for sm in strict.finditer(line)}
        for m in pat.finditer(line):
            tally[f"{name} (relaxed)"] += 1
            if m.start() in strict_starts:
                continue  # strict pattern already recorded this one
            out.append((name, m.start(), m.end(), m.group(0)))
    return out

# Shape rules that demote a `generic_secretish` match to non-fatal.
# Suppression counts are printed so a human can audit what was dropped.
_HEXISH = re.compile(r"^[0-9a-fA-F]+$")
_UUIDISH = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_DIGITS = re.compile(r"^[0-9_\-]+$")
_WORDS = re.compile(r"^[A-Za-z_\-]+$")
# JSON escape artifact: in `"...\nDEADBEEF..."` the backslash is outside the
# token character class but the escape letter is inside it, so a 40-char git
# SHA preceded by \n / \t / \r matches as n<sha> / t<sha> / r<sha>. 135 of the
# 136 residual hits on arm A were exactly this.
_ESCAPED_HEX = re.compile(r"^[nrtbf][0-9a-fA-F]{32,}$")
GENERIC_ENTROPY_FLOOR = 3.0


def generic_suppression(tok: str) -> str | None:
    """Return the name of the rule that demotes this token, or None if it stands."""
    if _UUIDISH.match(tok):
        return "uuid"
    if _HEXISH.match(tok):
        return "pure-hex-digest"
    if _ESCAPED_HEX.match(tok):
        return "escaped-ws + hex digest"
    if _DIGITS.match(tok):
        return "pure-digits"
    if _WORDS.match(tok):
        return "no-digits-wordlike"
    if shannon(tok) < GENERIC_ENTROPY_FLOOR:
        return f"entropy<{GENERIC_ENTROPY_FLOOR}"
    return None


# --------------------------------------------------------------------------
# Oplog glue: a TOKENIZER artifact, fixed by splitting rather than by pattern.
#
# `jj op log` output is multi-line. When it is captured into a JSON string the
# newline becomes a literal `\n`; the backslash is outside the token character
# class but the escape letter is not, so the 40-hex operation/commit ID and the
# first word of the NEXT line fuse into one token:
#
#     ...describe commit 38c522f1...fad4c7d2\npoint bookmark retry-backoff...
#                        \_______ 40 hex _______/  \_ next line starts here
#     tokenizes as:      38c522f1...fad4c7d2point         <- one 45-char token
#
# The fused token is neither pure hex nor pure word, so every shape rule misses
# it and it lands in the suspect bucket. 16 of the 72 residual suspects on the
# four-arm tree were exactly this (8x `...d2point`, 8x `...d2snapshot`).
#
# The fix is to SPLIT the token at the 40-hex boundary and triage the two
# halves separately:
#
#   * the 40-hex half is demoted as what it is -- a commit/operation ID;
#   * the trailing word is put back through the ORDINARY rules and must earn
#     its own demotion. Nothing here swallows it.
#
# That second half matters. An allowlist entry of the form `<40hex>[a-z]+`
# would have suppressed the whole token including its tail, so a secret glued
# to a commit ID would have ridden out on the commit ID's coat-tails. Splitting
# cannot do that: the tail is judged alone, and if it looks like a secret it is
# still KEPT and still fails the run.
#
# The split is attempted ONLY on a token that would otherwise be kept (see
# scan_file), so it can never change the disposition of a token that some
# existing rule already demotes.
# --------------------------------------------------------------------------
_OPLOG_GLUE = re.compile(r"^(?P<hex>[0-9a-f]{40})(?P<tail>[a-z]{2,})$")
OPLOG_HEX_RULE = "oplog-glue split: 40-hex commit id"


def generic_parts(tok: str, start: int) -> list[tuple[str, int, int, str | None]]:
    """Split a newline-glued `<40 hex><word>` token into its two real tokens.

    Returns [(subtoken, abs_start, abs_end, forced_rule_or_None)]. For anything
    that is not the glue shape, returns the token unchanged as a single part.
    The forced rule is set ONLY for the 40-hex half; the trailing word carries
    `None` and is triaged by the ordinary rules like any other token.
    """
    m = _OPLOG_GLUE.match(tok)
    if not m:
        return [(tok, start, start + len(tok), None)]
    hex_part, tail = m.group("hex"), m.group("tail")
    return [
        (hex_part, start, start + len(hex_part), OPLOG_HEX_RULE),
        (tail, start + len(hex_part), start + len(tok), None),
    ]


# Claude transcripts carry `"signature":"<long base64>"` on thinking blocks.
# These are server-issued integrity signatures over model output, not
# credentials, and a single one shatters into ~11 fragments under the generic
# pattern -- they were 97% of the raw generic noise on arm A. Tokens lying
# INSIDE such a JSON value are demoted, and the count is reported.
#
# CAVEAT, deliberately loud: this means a secret pasted into a field literally
# named "signature" would be demoted. That is an accepted, documented tradeoff.
_SIGNATURE_VALUE = re.compile(r"\"signature\"\s*:\s*\"([A-Za-z0-9+/=_\-]{64,})\"")


def signature_spans(line: str) -> list[tuple[int, int]]:
    """Character spans of `"signature":"..."` values on this line."""
    return [m.span(1) for m in _SIGNATURE_VALUE.finditer(line)]


def _would_keep(tok: str, line: str, f: "Findings", start: int) -> bool:
    """True if `tok` survives every demotion rule as a whole token.

    Side-effect free -- it only asks the question, it records nothing. Used to
    gate the oplog-glue split so that split is attempted ONLY on tokens that
    would otherwise be reported as suspects.
    """
    if generic_suppression(tok) is not None:
        return False
    if in_spans(start, signature_spans(line)):
        return False
    return not any(rx.match(tok) for rx, _lbl in f.allowlist)


def in_spans(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(a <= pos < b for a, b in spans)


def load_allowlist(path: str) -> list[tuple[re.Pattern, str]]:
    """Load reviewed allowlist regexes.

    Format: one regex per line; `#` starts a comment. Each entry must fully
    match a token to demote it.

    SAFETY PROPERTY, as actually enforced by the code:

      (a) The allowlist is consulted ONLY for the generic catch-all bucket.
          It is never consulted for a name-with-value hit or a
          live-credential hit; those can only be resolved by removing data.

      (b) It cannot suppress anything whose shape matches one of the specific
          VALUE patterns (sk-ant-, sk-, pyd_, logfire, JWT, AWS, GitHub,
          Slack, Bearer, Authorization, X-Api-Key, private key) -- EVEN IF
          that shape has been glued to an allowlisted prefix or otherwise
          stripped of its word boundaries. This is enforced by the
          boundary-erosion guard (erosion_hits), which re-runs the specific
          patterns with `\\b` removed before any demotion and refuses the
          demotion if one fires.

    Property (b) is new. The previous docstring, and the allowlist file
    header, claimed the allowlist "can NEVER suppress a specific-shape
    secret" as an unconditional fact. It was false: `\\b`-anchored patterns
    plus word-character allowlist prefixes let four bypasses through. The
    claim is now backed by code rather than asserted.

    NOT guaranteed: property (b) covers the specific VALUE patterns only. A
    secret that matches none of them -- a bare UUID, a bare hex digest -- is
    still demotable by the generic bucket's shape rules. See LIMITATIONS at
    the top of this file.
    """
    out: list[tuple[re.Pattern, str]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            out.append((re.compile(line + r"\Z"), raw.strip()))
    return out


# --------------------------------------------------------------------------
# NAME patterns -- credential variable names. Expected; usually benign.
# --------------------------------------------------------------------------

NAME_PATTERNS = [
    ("PYDANTIC_AI_GATEWAY_API_KEY", re.compile(r"\bPYDANTIC_AI_GATEWAY_API_KEY\b")),
    ("__ANTHROPIC_API_KEY",         re.compile(r"(?<![A-Za-z0-9])__ANTHROPIC_API_KEY\b")),
    ("LOGFIRE_API_KEY",             re.compile(r"\bLOGFIRE_API_KEY\b")),
    ("LOGFIRE_TOKEN",               re.compile(r"\bLOGFIRE_TOKEN\b")),
    # Plain ANTHROPIC_API_KEY, excluding the __-prefixed variant above.
    ("ANTHROPIC_API_KEY",           re.compile(r"(?<![A-Za-z0-9_])ANTHROPIC_API_KEY\b")),
    ("ANTHROPIC_AUTH_TOKEN",        re.compile(r"\bANTHROPIC_AUTH_TOKEN\b")),
    ("apiKeySource",                re.compile(r"\bapiKeySource\b")),
]

KNOWN_NAMES = {n for n, _ in NAME_PATTERNS}
_ECHO_SAFE.update(KNOWN_NAMES)
_ECHO_SAFE.update({"ANTHROPIC_BASE_URL", "apiKeySource", "none", "null", "true", "false"})

# A value sitting immediately after the name on the same line.
_ADJACENT = re.compile(r"^[\"']?\s*[:=]\s*[\"']?([^\"'\s,}\]]*)")

# Values that mean "no secret here".
_BENIGN_VALUES = {
    "", "null", "none", "None", "nil", "undefined", "true", "false",
    "0", "1", "{}", "[]", "\\\"\\\"", "unset", "unknown", "n/a", "N/A",
}

BUCKET_NAME_ONLY = "name only"
BUCKET_NAME_NAMEVAL = "name with name/sentinel value"
BUCKET_NAME_VALUE = "name with adjacent value"


def classify_name_hit(line: str, end: int) -> tuple[str, str]:
    """Given the line and the end offset of the NAME match, bucket it.

    Returns (bucket, redacted_value_or_empty).
    """
    m = _ADJACENT.match(line[end:])
    if not m:
        return BUCKET_NAME_ONLY, ""
    val = m.group(1)
    if val.strip() in _BENIGN_VALUES:
        return BUCKET_NAME_NAMEVAL, val
    # The precedent case: "apiKeySource":"ANTHROPIC_API_KEY" -- the value is
    # itself a credential variable NAME, i.e. telemetry about which env var
    # was used, not the key material.
    if val in KNOWN_NAMES or val.lstrip("_") in KNOWN_NAMES:
        return BUCKET_NAME_NAMEVAL, val
    # Also benign: pointing at a file path or a URL, not key material.
    if val.startswith(("/", "./", "~/", "http://", "https://", "$")):
        return BUCKET_NAME_NAMEVAL, val
    return BUCKET_NAME_VALUE, redact(val)


# --------------------------------------------------------------------------
# Live credential check. Values come from os.environ and are NEVER emitted.
# --------------------------------------------------------------------------

# Declared vars: always reported on, even when unset (an unset declared var is
# an UNVERIFIED gap, not a pass -- see the verdict line).
LIVE_CRED_VARS = [
    "PYDANTIC_AI_GATEWAY_API_KEY",
    "__ANTHROPIC_API_KEY",
    "LOGFIRE_API_KEY",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
]

# Plus a sweep of EVERY environment variable whose NAME looks secret-ish. The
# hand-maintained list above was stale: a review of one session's environment
# found 18 secret-ish names, several of them absent from the list (AWS_*,
# GH_TOKEN, GITHUB_TOKEN, CLOUDSDK_AUTH_ACCESS_TOKEN, CLAUDE_CODE_*_TOKEN...).
# A list that has to be remembered is a list that goes stale, so it is now a
# floor rather than the whole check.
#
# Only the NAME is ever inspected for the sweep decision, and only the name and
# a boolean/location are ever emitted. Values are read into memory, byte-
# searched, and never printed, written, logged, or redacted-echoed.
LIVE_NAME_RE = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH", re.I)

MIN_LIVE_LEN = 12  # below this, a literal search is not trustworthy

DECLARED = "declared"
DISCOVERED = "name-swept"


def load_live_creds() -> tuple[
        list[tuple[str, bytes]], list[tuple[str, str]], dict[str, str]]:
    """Return ([(var, value_bytes)], [(var, skip_reason)], {var: origin}).

    Values never leave this function except as opaque bytes for searching.
    """
    origin: dict[str, str] = {}
    order: list[str] = []
    for var in LIVE_CRED_VARS:
        origin[var] = DECLARED
        order.append(var)
    for var in sorted(os.environ):
        if var in origin:
            continue
        if LIVE_NAME_RE.search(var):
            origin[var] = DISCOVERED
            order.append(var)

    live: list[tuple[str, bytes]] = []
    skipped: list[tuple[str, str]] = []
    for var in order:
        raw = os.environ.get(var)
        if raw is None:
            skipped.append((var, "unset in environment"))
            continue
        if not raw.strip():
            skipped.append((var, "set but empty -- refusing to search (would match everywhere)"))
            continue
        if len(raw) < MIN_LIVE_LEN:
            skipped.append((var, f"set but shorter than {MIN_LIVE_LEN} chars -- too short to search safely"))
            continue
        live.append((var, raw.encode("utf-8", "surrogateescape")))
    return live, skipped, origin


# --------------------------------------------------------------------------
# Scanning
# --------------------------------------------------------------------------

MAX_FILE_BYTES = 64 * 1024 * 1024


class Findings:
    def __init__(self) -> None:
        # pattern -> list of (path, lineno, detail)
        self.value: dict[str, list] = defaultdict(list)
        self.generic_kept: list = []
        self.generic_suppressed: dict[str, int] = defaultdict(int)
        # (pattern, bucket) -> list of (path, lineno, detail)
        self.name: dict[tuple[str, str], list] = defaultdict(list)
        # var -> list of (path, lineno)   -- locations only, never the value
        self.live: dict[str, list] = defaultdict(list)
        self.files_scanned = 0
        self.bytes_scanned = 0
        self.unreadable: list[tuple[str, str]] = []
        self.oversized: list[tuple[str, int]] = []
        self.allowlist: list[tuple[re.Pattern, str]] = []
        self.allow_hits: dict[str, int] = defaultdict(int)
        # Boundary-eroded specific-shape hits. FATAL.
        # (path, lineno, pattern_name, redacted_match)
        self.eroded: list[tuple[str, int, str, str]] = []
        # Demotions REFUSED because they overlapped an eroded span. Audit trail.
        # (path, lineno, redacted_token, rule_that_would_have_demoted, pattern)
        self.demotion_refused: list[tuple[str, int, str, str, str]] = []
        # Prefilter/per-line disagreements: pattern HOT on whole text but zero
        # per-line matches => a silent false negative. Fatal-by-warning.
        # pattern -> list of paths
        self.prefilter_gap: dict[str, list[str]] = defaultdict(list)


def scan_file(path: str, f: Findings, live: list[tuple[str, bytes]]) -> None:
    try:
        size = os.path.getsize(path)
    except OSError as e:
        f.unreadable.append((path, str(e)))
        return
    if size > MAX_FILE_BYTES:
        f.oversized.append((path, size))
        return
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as e:
        f.unreadable.append((path, str(e)))
        return

    f.files_scanned += 1
    f.bytes_scanned += len(data)

    # --- live credential literals: byte search, no decoding, no echo ---
    for var, val in live:
        start = 0
        while True:
            idx = data.find(val, start)
            if idx < 0:
                break
            lineno = data.count(b"\n", 0, idx) + 1
            f.live[var].append((path, lineno))
            start = idx + 1
            if len(f.live[var]) > 500:  # runaway guard
                break

    text = data.decode("utf-8", "replace")

    # Fast prefilter: only walk lines for patterns that hit somewhere.
    hot_value = [(n, p) for n, p in VALUE_PATTERNS if p.search(text)]
    hot_name = [(n, p) for n, p in NAME_PATTERNS if p.search(text)]
    # The relaxed patterns get their own prefilter: a boundary-eroded secret is
    # by definition invisible to the strict prefilter above.
    hot_relaxed = [(n, p) for n, p in RELAXED_VALUE_PATTERNS if p.search(text)]
    if not hot_value and not hot_name and not hot_relaxed:
        return

    # Per-line match tallies, kept so the prefilter can be reconciled against
    # what the per-line pass actually saw (see below).
    per_line_seen: dict[str, int] = defaultdict(int)

    for lineno, line in enumerate(text.splitlines(), 1):
        sigspans: list[tuple[int, int]] | None = None

        # --- boundary-erosion guard, half 1: detect ---
        eroded = (erosion_spans(line, hot_relaxed, per_line_seen)
                  if hot_relaxed else [])
        for pname, _s, _e, frag in eroded:
            f.eroded.append((path, lineno, pname, redact(frag)))

        for name, pat in hot_value:
            for m in pat.finditer(line):
                per_line_seen[name] += 1
                tok = m.group(0)
                if name == GENERIC_PATTERN:
                    def triage(sub: str, s0: int, s1: int,
                               forced: str | None = None) -> None:
                        """Demote or keep ONE generic token, honouring the guard."""
                        nonlocal sigspans
                        rule = forced if forced is not None else generic_suppression(sub)
                        if rule is None:
                            if sigspans is None:
                                sigspans = signature_spans(line)
                            if in_spans(s0, sigspans):
                                rule = "inside-signature-field"
                        allowed = None
                        if rule is None:
                            allowed = next(
                                (lbl for rx, lbl in f.allowlist if rx.match(sub)), None)

                        if rule is not None or allowed is not None:
                            # --- boundary-erosion guard, half 2: refuse ---
                            # Nothing gets demoted if it overlaps a span where a
                            # specific VALUE pattern fired once boundaries were
                            # relaxed. Neither the allowlist nor the oplog-glue
                            # split gets to swallow it.
                            overlap = [pn for pn, s, e, _fr in eroded
                                       if s < s1 and s0 < e]
                            if overlap:
                                why = rule if rule is not None else f"allowlist: {allowed}"
                                for pn in overlap:
                                    f.demotion_refused.append(
                                        (path, lineno, redact(sub), why, pn))
                                return  # REFUSED -- not demoted, not silently kept
                            if allowed is not None:
                                f.allow_hits[allowed] += 1
                            else:
                                f.generic_suppressed[rule] += 1
                            return

                        f.generic_kept.append(
                            (path, lineno, redact(sub), round(shannon(sub), 2)))

                    # Would the whole token be kept? Only then is it worth
                    # asking whether it is really two tokens fused by a
                    # swallowed newline. Attempting the split only on
                    # otherwise-kept tokens guarantees the tokenizer fix cannot
                    # change the fate of anything an existing rule handles.
                    parts = generic_parts(tok, m.start())
                    if len(parts) > 1 and _would_keep(tok, line, f, m.start()):
                        for sub, s0, s1, forced in parts:
                            triage(sub, s0, s1, forced)
                    else:
                        triage(tok, m.start(), m.end())
                else:
                    f.value[name].append((path, lineno, redact(tok)))
        for name, pat in hot_name:
            for m in pat.finditer(line):
                per_line_seen[name] += 1
                bucket, detail = classify_name_hit(line, m.end())
                f.name[(name, bucket)].append((path, lineno, detail, redact_line(line)))

    # --- prefilter / per-line reconciliation -------------------------------
    # The prefilter runs `pat.search(text)` over the WHOLE FILE; the recording
    # pass runs `pat.finditer(line)` per line. Several patterns can span a
    # newline (`Bearer\s+`, `Authorization\s*[:=]\s*`, `X-Api-Key\s*[:=]\s*`
    # all admit \n inside \s). Such a match is seen by the prefilter and then
    # matched by NOTHING per line -- the finding evaporates with no output.
    # A silent false negative is the one failure a gate must not have, so the
    # disagreement is reported loudly and makes the run non-clean.
    checked = ([n for n, _ in hot_value]
               + [n for n, _ in hot_name]
               + [f"{n} (relaxed)" for n, _ in hot_relaxed])
    for key in checked:
        if per_line_seen[key] == 0:
            f.prefilter_gap[key].append(path)


def walk(roots: list[str], f: Findings, live: list[tuple[str, bytes]]) -> None:
    for root in roots:
        if os.path.isfile(root):
            scan_file(root, f, live)
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            for fn in sorted(filenames):
                p = os.path.join(dirpath, fn)
                if os.path.islink(p):
                    continue
                scan_file(p, f, live)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def hr(ch: str = "-", n: int = 78) -> str:
    return ch * n


def report(f: Findings, skipped: list[tuple[str, str]], live: list[tuple[str, bytes]],
           origin: dict[str, str], roots: list[str], max_examples: int,
           show_all: bool) -> int:
    out = print
    out(hr("="))
    out("credscan -- pre-publication credential scan")
    out(hr("="))
    out(f"roots        : {', '.join(roots)}")
    out(f"files scanned: {f.files_scanned}")
    out(f"bytes scanned: {f.bytes_scanned:,} ({f.bytes_scanned / 1048576:.1f} MiB)")
    if f.unreadable:
        out(f"unreadable   : {len(f.unreadable)}")
        for p, e in f.unreadable[:10]:
            out(f"    {p}: {e}")
    if f.oversized:
        out(f"skipped (too large): {len(f.oversized)}")
        for p, s in f.oversized[:10]:
            out(f"    {p}: {s:,} bytes")

    # ---- Section 1: VALUE patterns ----
    out("")
    out(hr())
    out("SECTION 1 -- VALUE PATTERNS (shapes that look like real secrets)")
    out(hr())
    value_total = 0
    for name, _ in VALUE_PATTERNS:
        if name == GENERIC_PATTERN:
            continue
        hits = f.value.get(name, [])
        if not hits:
            continue
        value_total += len(hits)
        out(f"\n  [FAIL] {name}: {len(hits)} hit(s) in "
            f"{len({h[0] for h in hits})} file(s)")
        shown = hits if show_all else hits[:max_examples]
        for p, ln, tok in shown:
            out(f"         {p}:{ln}  {tok}")
        if len(hits) > len(shown):
            out(f"         ... and {len(hits) - len(shown)} more")
    if value_total == 0:
        out("\n  [ OK ] no specific-shape secret patterns matched")

    # ---- generic catch-all ----
    out("")
    out(hr())
    out(f"SECTION 1b -- GENERIC CATCH-ALL  [A-Za-z0-9_-]{{32,}}")
    out(hr())
    sup_total = sum(f.generic_suppressed.values())
    allow_total = sum(f.allow_hits.values())
    out(f"  raw matches        : "
        f"{sup_total + allow_total + len(f.generic_kept) + len(f.demotion_refused):,}")
    out(f"  demotion REFUSED   : {len(f.demotion_refused):,}   "
        f"(boundary-erosion guard; see Section 1c -- FATAL)")
    out(f"  demoted by shape   : {sup_total:,}")
    for rule, n in sorted(f.generic_suppressed.items(), key=lambda kv: -kv[1]):
        out(f"      {rule:<24} {n:,}")
    if f.allowlist:
        out(f"  demoted by allowlist: {allow_total:,}  "
            f"(this bucket ONLY; never Section 1/2/3, and never a "
            f"boundary-eroded specific shape)")
        for lbl, _rx in sorted(((l, r) for r, l in f.allowlist), key=lambda kv: -f.allow_hits[kv[0]]):
            n = f.allow_hits.get(lbl, 0)
            mark = "" if n else "   <-- UNUSED, consider removing"
            out(f"      {n:>7,}  {lbl}{mark}")
    out(f"  remaining (suspect): {len(f.generic_kept):,}")
    if f.generic_kept:
        byfile = defaultdict(int)
        for p, _ln, _t, _e in f.generic_kept:
            byfile[p] += 1
        out(f"  spread over {len(byfile)} file(s); top files:")
        for p, n in sorted(byfile.items(), key=lambda kv: -kv[1])[:10]:
            out(f"      {n:>6}  {p}")
        out("  examples (redacted):")
        shown = f.generic_kept if show_all else f.generic_kept[:max_examples]
        for p, ln, tok, ent in shown:
            out(f"      {p}:{ln}  {tok}  entropy={ent}")
        if len(f.generic_kept) > len(shown):
            out(f"      ... and {len(f.generic_kept) - len(shown):,} more")

    # ---- Section 1c: demotions refused by the boundary-erosion guard ----
    out("")
    out(hr())
    out("SECTION 1c -- BOUNDARY EROSION (word-boundary-stripped specific shapes)")
    out(hr())
    if not f.eroded:
        out("  [ OK ] no specific VALUE pattern fired once word boundaries were")
        out("         relaxed, so no allowlist entry or shape rule was in a")
        out("         position to swallow a prefix-glued secret")
    else:
        byname: dict[str, list] = defaultdict(list)
        for rec in f.eroded:
            byname[rec[2]].append(rec)
        out(f"  !! {len(f.eroded)} BOUNDARY-ERODED specific-shape hit(s) across "
            f"{len(byname)} pattern(s).")
        out("  !! Each of these matched a specific VALUE pattern with its word")
        out("  !! boundary relaxed, but NOT with the boundary intact -- i.e. a")
        out("  !! word character is glued to the front (or back) of a secret.")
        out("  !! That is exactly the prefix-gluing bypass. THESE ARE FATAL.")
        for pname, recs in sorted(byname.items(), key=lambda kv: -len(kv[1])):
            out(f"\n  [FAIL] {pname} (boundary-relaxed): {len(recs)} hit(s) in "
                f"{len({r[0] for r in recs})} file(s)")
            shown = recs if show_all else recs[:max_examples]
            for p, ln, _pn, frag in shown:
                out(f"         {p}:{ln}  {frag}")
            if len(recs) > len(shown):
                out(f"         ... and {len(recs) - len(shown)} more")
    out("")
    if not f.demotion_refused:
        out("  demotions refused on this basis: 0")
    else:
        out(f"  !! demotions REFUSED on this basis: {len(f.demotion_refused)}")
        out("  !! (a shape rule or allowlist entry tried to demote a token that")
        out("  !!  overlapped an eroded secret; the demotion was blocked)")
        shown = (f.demotion_refused if show_all
                 else f.demotion_refused[:max_examples])
        for p, ln, tok, why, pn in shown:
            out(f"         {p}:{ln}  {tok}")
            out(f"           would-be: demoted by {why}")
            out(f"           blocked by: {pn} (boundary-relaxed)")
        if len(f.demotion_refused) > len(shown):
            out(f"         ... and {len(f.demotion_refused) - len(shown)} more")

    # ---- Section 2: NAME patterns ----
    out("")
    out(hr())
    out("SECTION 2 -- NAME PATTERNS (credential variable names; usually benign)")
    out(hr())
    name_value_total = 0
    if not f.name:
        out("\n  no credential variable names appear anywhere")
    for name, _ in NAME_PATTERNS:
        buckets = {b: f.name[(name, b)] for b in
                   (BUCKET_NAME_ONLY, BUCKET_NAME_NAMEVAL, BUCKET_NAME_VALUE)
                   if f.name.get((name, b))}
        if not buckets:
            continue
        total = sum(len(v) for v in buckets.values())
        out(f"\n  {name}: {total} hit(s)")
        for bucket, hits in buckets.items():
            flag = "FAIL" if bucket == BUCKET_NAME_VALUE else " OK "
            if bucket == BUCKET_NAME_VALUE:
                name_value_total += len(hits)
            files = {h[0] for h in hits}
            out(f"      [{flag}] {bucket:<32} {len(hits):>5} hit(s) in {len(files)} file(s)")
            shown = hits if show_all else hits[:max_examples]
            for p, ln, detail, ctx in shown:
                extra = f"  value={detail}" if bucket == BUCKET_NAME_VALUE else ""
                out(f"             {p}:{ln}{extra}")
                out(f"               | {ctx}")
            if len(hits) > len(shown):
                out(f"             ... and {len(hits) - len(shown)} more")

    # ---- Section 3: live credentials ----
    out("")
    out(hr())
    out("SECTION 3 -- LIVE CREDENTIAL VALUES FROM os.environ")
    out(hr())
    out("  (values are read into memory only; never printed, written, or logged)")
    out(f"  declared vars : {sum(1 for v in origin.values() if v == DECLARED)}")
    out(f"  name-swept    : {sum(1 for v in origin.values() if v == DISCOVERED)}"
        f"   (env NAME matches /{LIVE_NAME_RE.pattern}/i, value >= "
        f"{MIN_LIVE_LEN} chars)")
    out(f"  searched      : {len(live)}")
    out(f"  UNVERIFIED    : {len(skipped)}   <-- these were NOT checked")
    out("")
    live_total = 0
    for var, _val in live:
        hits = f.live.get(var, [])
        live_total += len(hits)
        tag = f"({origin.get(var, DECLARED)})"
        if hits:
            out(f"  [FAIL] {var} {tag}: PRESENT -- {len(hits)} location(s)")
            for p, ln in (hits if show_all else hits[:max_examples]):
                out(f"         {p}:{ln}")
            if len(hits) > max_examples and not show_all:
                out(f"         ... and {len(hits) - max_examples} more")
        else:
            out(f"  [ OK ] {var} {tag}: searched, not present")
    for var, reason in skipped:
        out(f"  [SKIP] {var} ({origin.get(var, DECLARED)}): {reason}"
            f"  -- UNVERIFIED, not a pass")

    # ---- Section 4: prefilter / per-line reconciliation ----
    out("")
    out(hr())
    out("SECTION 4 -- PREFILTER / PER-LINE RECONCILIATION")
    out(hr())
    gap_total = sum(len(v) for v in f.prefilter_gap.values())
    if not gap_total:
        out("  [ OK ] every pattern that was HOT on whole-file text also "
            "produced")
        out("         at least one per-line match. No finding evaporated.")
    else:
        out(f"  !! WARNING: {gap_total} pattern/file pair(s) matched the "
            f"whole-file prefilter")
        out("  !! but produced ZERO per-line matches. The per-line pass is what")
        out("  !! records findings, so each of these is a SILENT FALSE NEGATIVE:")
        out("  !! something matched and was then never reported. The usual cause")
        out("  !! is a pattern whose \\s spans a newline (Bearer, Authorization,")
        out("  !! X-Api-Key). The scan is NOT clean while this is outstanding.")
        for name, paths in sorted(f.prefilter_gap.items(), key=lambda kv: -len(kv[1])):
            out(f"\n  [WARN] {name}: hot on {len(paths)} file(s), 0 per-line matches")
            shown = paths if show_all else paths[:max_examples]
            for p in shown:
                out(f"         {p}")
            if len(paths) > len(shown):
                out(f"         ... and {len(paths) - len(shown)} more")

    # ---- Summary table ----
    out("")
    out(hr("="))
    out("SUMMARY")
    out(hr("="))
    rows: list[tuple[str, str, str, str]] = []
    for name, _ in VALUE_PATTERNS:
        if name == GENERIC_PATTERN:
            continue
        n = len(f.value.get(name, []))
        rows.append(("VALUE", name, str(n), "FAIL" if n else "clean"))
    rows.append(("VALUE", f"{GENERIC_PATTERN} (kept)", str(len(f.generic_kept)),
                 "FAIL" if f.generic_kept else "clean"))
    rows.append(("GUARD", "boundary-eroded specific shapes", str(len(f.eroded)),
                 "FAIL" if f.eroded else "clean"))
    rows.append(("GUARD", "demotions refused (boundary erosion)",
                 str(len(f.demotion_refused)),
                 "info" if f.demotion_refused else "clean"))
    rows.append(("VALUE", f"{GENERIC_PATTERN} (demoted by shape)", str(sup_total), "info"))
    if f.allowlist:
        rows.append(("VALUE", f"{GENERIC_PATTERN} (demoted by allowlist)",
                     str(allow_total), "info"))
    for name, _ in NAME_PATTERNS:
        for bucket in (BUCKET_NAME_ONLY, BUCKET_NAME_NAMEVAL, BUCKET_NAME_VALUE):
            n = len(f.name.get((name, bucket), []))
            if not n:
                continue
            verdict = "FAIL" if bucket == BUCKET_NAME_VALUE else "benign"
            rows.append(("NAME", f"{name} [{bucket}]", str(n), verdict))
    rows.append(("WARN", "prefilter hot / 0 per-line matches", str(gap_total),
                 "WARN-FAIL" if gap_total else "clean"))
    for var, _ in live:
        n = len(f.live.get(var, []))
        rows.append(("LIVE", var, str(n), "FAIL" if n else "clean"))
    for var, _r in skipped:
        rows.append(("LIVE", var, "-", "UNVERIFIED"))

    w1 = max(5, max(len(r[0]) for r in rows))
    w2 = max(7, max(len(r[1]) for r in rows))
    w3 = max(5, max(len(r[2]) for r in rows))
    out(f"  {'CLASS'.ljust(w1)}  {'PATTERN'.ljust(w2)}  {'COUNT'.rjust(w3)}  VERDICT")
    out(f"  {'-' * w1}  {'-' * w2}  {'-' * w3}  -------")
    for c, p, n, v in rows:
        out(f"  {c.ljust(w1)}  {p.ljust(w2)}  {n.rjust(w3)}  {v}")

    fail = (value_total + len(f.generic_kept) + name_value_total + live_total
            + len(f.eroded) + gap_total)
    out("")
    out(hr("="))
    if fail:
        out(f"RESULT: BLOCKED -- {value_total} value hit(s), "
            f"{len(f.generic_kept)} generic suspect(s), "
            f"{len(f.eroded)} boundary-eroded hit(s), "
            f"{name_value_total} name-with-value hit(s), "
            f"{live_total} live-credential hit(s), "
            f"{gap_total} prefilter warning(s)")
        out("Do NOT publish until every one of these is resolved.")
    elif skipped:
        # A skipped live variable is a HOLE, not a pass. Say so in the verdict
        # line itself: the previous build printed a bare "RESULT: CLEAN" while
        # two declared credential variables had never been searched for.
        n_unset = sum(1 for _v, r in skipped if r.startswith("unset"))
        n_other = len(skipped) - n_unset
        why = f"{n_unset} unset"
        if n_other:
            why += f", {n_other} not searchable"
        out(f"RESULT: clean, with {len(skipped)} live variable(s) UNVERIFIED "
            f"({why})")
        out("  No value hits, no name-with-value hits, no live-credential hits")
        out("  among the variables that WERE searched. The following were not")
        out("  searched at all, so this run says nothing about them:")
        for var, reason in skipped:
            out(f"    - {var} ({origin.get(var, DECLARED)}): {reason}")
        out("  Re-run with those variables set to close the gap.")
    else:
        out("RESULT: CLEAN -- no value hits, no name-with-value hits, "
            "no live-credential hits; every live variable was searched")
    out("")
    out("  Reminder: UUID-shaped and hex-digest-shaped secrets are NOT "
        "detected.")
    out("  See the LIMITATIONS block at the top of credscan.py.")
    out(hr("="))
    return 1 if fail else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Pre-publication credential scanner.")
    ap.add_argument("dirs", nargs="+", help="directories (or files) to scan")
    ap.add_argument("--max-examples", type=int, default=5,
                    help="max example findings printed per bucket (default 5)")
    ap.add_argument("--all", action="store_true", help="print every finding")
    ap.add_argument("--allowlist", help="file of reviewed regexes demoting generic-bucket "
                                        "tokens only; never suppresses Section 1/2/3, and "
                                        "never a boundary-eroded specific shape")
    args = ap.parse_args(argv)

    roots = [os.path.abspath(d) for d in args.dirs]
    for r in roots:
        if not os.path.exists(r):
            print(f"error: no such path: {r}", file=sys.stderr)
            return 2

    live, skipped, origin = load_live_creds()
    f = Findings()
    if args.allowlist:
        try:
            f.allowlist = load_allowlist(args.allowlist)
        except OSError as e:
            print(f"error: cannot read allowlist: {e}", file=sys.stderr)
            return 2
    walk(roots, f, live)
    return report(f, skipped, live, origin, roots, args.max_examples, args.all)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
