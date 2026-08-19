#!/usr/bin/env python3
"""Prove a forced-injection arm actually delivered its document, before trusting any number.

Two independent layers (recon 2026-08-19, section 5):

  Layer 1 -- the trial lock digest. Every trial's `lock.json` must carry EXACTLY ONE
             `extra_instructions` entry, with the expected path and the expected
             sha256 digest. Harbor content-digests the file into the lock
             (`harbor/models/job/lock.py:288-290`, `_build_extra_instruction_locks`
             at `lock.py:374-382`), so this is immune to transcript elision.

  Layer 2 -- the transcript. Every trial's `agent/trajectory.json` must have
             `steps[0].source == "user"` and `steps[0].message` must END WITH the
             document's exact bytes. Harbor appends the extra instruction to every
             task instruction with "\n\n" as the joiner
             (`harbor/models/task/task.py:184-185`), so the document is the tail of
             the first user step.

Anything less than N/N on BOTH layers is a FAILED MANIPULATION, not a null result.

DO NOT use `agent/claude-code.txt` for this check. It returns 0/96 even for a
genuinely delivered, un-elided forced document: harbor feeds the prompt on STDIN
(`claude_code.py:1512-1530`) and that file is only the `--output-format=stream-json`
stream, which never echoes the prompt. This script refuses to look at it.

Usage:
    python3 verify_delivery.py <job-dir> <document-path> [--expect N]

    python3 verify_delivery.py jobs/armG-blind-forced arms/armG-reference.md

Exit status: 0 only if both layers report N/N. Non-zero otherwise.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys

DEFAULT_EXPECT = 96


def fail(msg: str) -> None:
    print("FATAL: %s" % msg, file=sys.stderr)
    raise SystemExit(2)


def load_json(path: str):
    try:
        with open(path, "rb") as fh:
            return json.loads(fh.read().decode("utf-8"))
    except Exception as exc:                                  # noqa: BLE001
        return exc


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Prove a forced-injection arm delivered its document (2 layers).")
    ap.add_argument("job_dir", help="the arm's job directory, e.g. jobs/armG-blind-forced")
    ap.add_argument("document", help="the injected document, e.g. arms/armG-reference.md")
    ap.add_argument("--expect", type=int, default=DEFAULT_EXPECT,
                    help="number of trials expected (default %d)" % DEFAULT_EXPECT)
    ap.add_argument("--lock-path", default=None,
                    help="the path string as it appears in lock.json "
                         "(default: the document argument, verbatim)")
    args = ap.parse_args()

    job_dir = args.job_dir.rstrip("/")
    if not os.path.isdir(job_dir):
        fail("job dir %r does not exist" % job_dir)
    if not os.path.isfile(args.document):
        fail("document %r does not exist" % args.document)

    # The lock records the path exactly as it was passed to --extra-instruction-path.
    expected_path = args.lock_path if args.lock_path is not None else args.document

    doc_bytes = open(args.document, "rb").read()
    expected_digest = "sha256:" + hashlib.sha256(doc_bytes).hexdigest()

    print("job dir          : %s" % job_dir)
    print("document         : %s (%d bytes)" % (args.document, len(doc_bytes)))
    print("expected path    : %s" % expected_path)
    print("expected digest  : %s" % expected_digest)
    print("expected trials  : %d" % args.expect)
    print()

    trials = sorted(
        d for d in glob.glob(os.path.join(job_dir, "*"))
        if os.path.isdir(d) and os.path.isfile(os.path.join(d, "lock.json"))
    )
    n_trials = len(trials)
    print("trial dirs found : %d" % n_trials)
    if n_trials != args.expect:
        print("  !! expected %d, found %d" % (args.expect, n_trials))
    print()

    # ---------------------------------------------------------------- layer 1
    l1_ok = 0
    l1_bad: list[str] = []
    for t in trials:
        p = os.path.join(t, "lock.json")
        d = load_json(p)
        if isinstance(d, Exception):
            l1_bad.append("%s: unreadable lock.json (%s)" % (os.path.basename(t), d))
            continue
        entries = d.get("extra_instructions")
        if not isinstance(entries, list):
            l1_bad.append("%s: extra_instructions missing or not a list (%r)"
                          % (os.path.basename(t), entries))
            continue
        if len(entries) != 1:
            l1_bad.append("%s: expected exactly 1 extra_instructions entry, got %d"
                          % (os.path.basename(t), len(entries)))
            continue
        e = entries[0]
        got_path, got_digest = e.get("path"), e.get("digest")
        if got_path != expected_path:
            l1_bad.append("%s: path %r != expected %r"
                          % (os.path.basename(t), got_path, expected_path))
            continue
        if got_digest != expected_digest:
            l1_bad.append("%s: digest %r != expected %r"
                          % (os.path.basename(t), got_digest, expected_digest))
            continue
        l1_ok += 1

    # ---------------------------------------------------------------- layer 2
    l2_ok = 0
    l2_bad: list[str] = []
    for t in trials:
        p = os.path.join(t, "agent", "trajectory.json")
        if not os.path.isfile(p):
            l2_bad.append("%s: no agent/trajectory.json" % os.path.basename(t))
            continue
        d = load_json(p)
        if isinstance(d, Exception):
            l2_bad.append("%s: unreadable trajectory.json (%s)" % (os.path.basename(t), d))
            continue
        steps = d.get("steps") if isinstance(d, dict) else d
        if not isinstance(steps, list) or not steps:
            l2_bad.append("%s: trajectory has no steps" % os.path.basename(t))
            continue
        s0 = steps[0]
        if s0.get("source") != "user":
            l2_bad.append("%s: steps[0].source is %r, expected 'user'"
                          % (os.path.basename(t), s0.get("source")))
            continue
        msg = s0.get("message")
        if not isinstance(msg, str):
            l2_bad.append("%s: steps[0].message is %s, not a string"
                          % (os.path.basename(t), type(msg).__name__))
            continue
        if not msg.encode("utf-8").endswith(doc_bytes):
            l2_bad.append("%s: steps[0].message does not END WITH the document bytes"
                          % os.path.basename(t))
            continue
        l2_ok += 1

    # ---------------------------------------------------------------- report
    def band(label: str, ok: int, bad: list[str]) -> None:
        print("%s: %d/%d" % (label, ok, args.expect))
        for line in bad[:15]:
            print("    - %s" % line)
        if len(bad) > 15:
            print("    ... and %d more" % (len(bad) - 15))
        print()

    band("LAYER 1  lock.json extra_instructions digest ", l1_ok, l1_bad)
    band("LAYER 2  trajectory.json steps[0] tail bytes ", l2_ok, l2_bad)

    good = (l1_ok == args.expect and l2_ok == args.expect and n_trials == args.expect)
    if good:
        print("PASS: delivery proven on both layers, %d/%d." % (args.expect, args.expect))
        return 0

    print("FAIL: delivery NOT proven. This is a FAILED MANIPULATION, not a null result.")
    print("      Do not report arm results until both layers read %d/%d."
          % (args.expect, args.expect))
    return 1


if __name__ == "__main__":
    sys.exit(main())
