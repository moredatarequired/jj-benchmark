# 2026-08-16 — skill-effect A/B/C/D/E sweep (5 arms × 96 trials)

Raw harbor trial records for a five-arm comparison of how a *skill* affects an
agent's competence at Jujutsu (jj) tasks. All five arms run the same 24-task
"informed" suite, the same agent, the same model, and the same environment; the
only thing that varies is what jj guidance the agent is handed.

- **jj version under test:** 0.44.0
- **harbor:** 0.20.0 (`lock.json` → `.harbor.version` in each arm)
- **agent / model:** `claude-code` / `claude-haiku-4-5-20251001`
- **suite:** 24 tasks × `-k 4` attempts = **96 trials per arm**, **480 trials total**
- **exceptions:** 0 in every arm (all 480 trials scored)

Every command below was run against this archive **after** the two
transformations described in "Two ways this archive is not raw" below, and the
output pasted underneath is the real output, not a reconstruction. Run them
from the **repository root**.

> One exception to "run them yourself": the few commands that invoke
> `analyze/credscan.py`, `analyze/pass2_keyvalue_audit.py` or
> `analyze/open_rate.py` refer to the sweep's build-time analysis tooling, which
> lives in the run scratchpad and is **not** part of this archive or of this
> repository. Their pasted output is real, but you cannot re-run those three
> without that tooling. Everything else here is plain `grep`/`python3` against
> the archived files and is fully reproducible.

---

## The five arms

| arm | job name | condition | trials | mean reward | strict passes | anchor-violating trials | ran `jj` |
|---|---|---|---:|---:|---:|---:|---:|
| A | `armA-control` | informed images, no skill | 96 | 0.6563 | 50 | 10 | 89 |
| B | `armB-decoy` | + our own `jj-working-practices` skill | 96 | 0.6094 | 45 | 16 | 90 |
| C | `armC-schpet` | + third-party `schpet--toolbox--jj` skill | 96 | 0.6693 | 49 | 14 | 94 |
| D | `armD-forced` | + `forced-reference.md` injected as an extra instruction | 96 | 0.8194 | 70 | 10 | 95 |
| E | `armE-schpet-forced` | + the schpet `SKILL.md` **injected** as an extra instruction | 96 | 0.6936 | 56 | 12 | 96 |

"Informed" means all 24 task images write `/home/user/AGENTS.md` and symlink
`CLAUDE.md` to it. The symlink is load-bearing: the harness reads `CLAUDE.md`
and ignores a bare `AGENTS.md`. Arm A adds nothing on top of that baseline.

Arms C and E are the pair that separates *offering* guidance from *delivering*
it: they carry the **same document**, once as a skill the agent may open (C,
opened in 14/96) and once force-fed into every prompt (E, present in 96/96).

### Exact harbor invocation

Each arm was started with `harbor run -c <config>`. Harbor writes its resolved
job configuration into the job directory, so **`<arm>/config.json` in this
archive is the authoritative record of what was actually run** — prefer it over
the reconstructed flag forms below.

Arm A (control):

```
harbor run \
  --job-name armA-control \
  --jobs-dir jobs \
  -k 4 -n 8 \
  --agent-setup-timeout-multiplier 2.5 \
  --max-retries 3 \
  --retry-include AgentSetupTimeoutError \
  --retry-include EnvironmentStartTimeoutError \
  --retry-include RuntimeError \
  -a claude-code -m claude-haiku-4-5-20251001 \
  --dataset informed/tasks \
  --override-memory-mb 2048
```

Arm B (decoy skill) — arm A plus `--skill arms/jj-working-practices`
Arm C (third-party skill) — arm A plus `--skill arms/schpet--toolbox--jj`
Arm D (forced reference) — arm A plus `--extra-instruction-path arms/forced-reference.md`
Arm E (forced schpet) — arm A plus `--extra-instruction-path arms/schpet-forced.md`

`arms/schpet-forced.md` is byte-identical to the schpet `SKILL.md`
(sha256 `fe16ec8e7cb074bff1e247baec6f179c13beddd3579020f800317cefb13a833c`).
It is **not** archived here — see the redaction section.

Confirm the differences straight from the archived configs:

```console
$ for a in armA-control armB-decoy armC-schpet armD-forced armE-schpet-forced; do
    echo "== $a"; python3 -c "
import json
c=json.load(open('jobs/2026-08-16-skill-ab/$a/config.json'))
print(' skills:', c['agents'][0].get('skills', []))
print(' extra_instruction_paths:', c.get('extra_instruction_paths', []))"
  done
== armA-control
 skills: []
 extra_instruction_paths: []
== armB-decoy
 skills: ['arms/jj-working-practices']
 extra_instruction_paths: []
== armC-schpet
 skills: ['arms/schpet--toolbox--jj']
 extra_instruction_paths: []
== armD-forced
 skills: []
 extra_instruction_paths: ['arms/forced-reference.md']
== armE-schpet-forced
 skills: []
 extra_instruction_paths: ['arms/schpet-forced.md']
```

---

# Two ways this archive is not raw

Everything else is byte-identical to the harbor job directories as written.
These two transformations are not, and both are recorded here in full so a
reader can tell exactly what was changed and reconstruct what was removed.

## 1. Absolute build paths were rewritten to relative ones

### The exact substitution

Harbor records the absolute path of the scratch directory it ran in. On this
build that directory was named after the build session's UUID, which is also
the value of the `CLAUDE_CODE_SESSION_ID` environment variable — so leaving the
paths intact would publish a live session identifier 6,736 times. Every
occurrence was rewritten by deleting the prefix, and nothing else:

```
/tmp/claude-0/-home-user-jj-benchmark/<session-uuid>/scratchpad/   ->   (deleted)
```

That is the whole transformation — one prefix deletion applied to file bytes.
It leaves the run-relative structure exactly as harbor recorded it:

```json
"trials_dir": "jobs/armA-control"
"task": {"path": "informed/tasks/abandon_commits", "source": "tasks"}
```

which is the same shape the `archive/2026-08-14-baseline-24-trials` branch
already uses (`"trials_dir": "jobs/2026-08-14__21-17-36"`). No other path
component was touched: `informed/tasks` was **not** renamed to `tasks`, because
the suite really was the "informed" variant and that is worth knowing.

### What it touched

| arm | files rewritten | occurrences |
|---|---:|---:|
| `armA-control` | 387 | 962 |
| `armB-decoy` | 387 | 1,539 |
| `armC-schpet` | 387 | 1,539 |
| `armD-forced` | 387 | 1,347 |
| `armE-schpet-forced` | 387 | 1,347 |
| `arms/FINAL/MANIFEST.txt` | 1 | 2 |
| **total** | **1,936** | **6,736** |

Within each arm the affected files are `config.json`, `lock.json`,
`result.json` and `trial.log` in each of the 96 trials, plus the arm-level
`config.json`, `lock.json`, `result.json` and `job.log`. This README is the
only file excluded from the mechanical rewrite; it was edited by hand.

All 1,450 rewritten `.json` files were re-parsed after the substitution and all
1,450 still parse.

### It changes no measurement — and here is the proof

The claim is that this rewrite touches only path strings: **no reward, no
verifier output, no token count, no timestamp.** Asserting that is not enough,
because `result.json` is both a path-carrying file and a measurement-carrying
file. So each arm's mean reward and anchor-violation count were re-derived from
the **rewritten** tree and compared against the figures taken **before** the
rewrite. The means are re-averaged from the 96 per-trial `reward.txt` scalars
and the anchor counts from the 96 per-trial `verifier/ctrf.json` files — i.e.
recomputed from the raw evidence, not read back out of harbor's summary.

| arm | mean before | mean after | anchor violations before | after |
|---|---:|---:|---:|---:|
| `armA-control` | 0.656250 | 0.656250 | 10 | 10 |
| `armB-decoy` | 0.609375 | 0.609375 | 16 | 16 |
| `armC-schpet` | 0.669271 | 0.669271 | 14 | 14 |
| `armD-forced` | 0.819444 | 0.819444 | 10 | 10 |
| `armE-schpet-forced` | 0.693576 | 0.693576 | 12 | 12 |

Identical in every cell. (Arm E was rewritten as a separate later pass, once
its run finished; its before/after pair was captured the same way.)

Confirm the identifier is gone:

```console
$ grep -rl "$CLAUDE_CODE_SESSION_ID" jobs/2026-08-16-skill-ab | wc -l
0
```

## 2. Third-party skill prose was elided from the transcripts

### Why

Standing rule: **no third-party skill text is vendored into this repository, in
any arm, at any stage.** The `schpet--toolbox--jj` SKILL.md carries no licence
grant for its own prose (only its `references/` directory is marked
Apache-2.0, being derived from jj's manpages), so republishing it is a real
problem rather than a technicality.

Excluding the skill *bundle* — which was done, see below — does not solve this.
When an agent opens a skill, the skill's body is pasted into its context and
recorded verbatim in the transcript; and arm E injects that same body into all
96 prompts by design. Deleting those transcripts would destroy the evidence for
the 14/96 open-rate result, which is one of the load-bearing findings. So the
prose was **redacted in place** instead.

### What was elided

Each elided document is replaced by a single placeholder naming it exactly:

```
[ELIDED: schpet--toolbox--jj SKILL.md, 9626 bytes, sha256 fe16ec8e7cb074bff1e247baec6f179c13beddd3579020f800317cefb13a833c — upstream https://github.com/schpet/toolbox at commit b39b24eacb9473e20f7271c23ee7160f74317d24, path plugins/jj-vcs/skills/jj/. Not redistributed here; fetch upstream to restore.]
```

| arm | document | sha256 | bytes | placeholders | files | trials |
|---|---|---|---:|---:|---:|---:|
| C | `SKILL.md` | `fe16ec8e7cb074bff1e247baec6f179c13beddd3579020f800317cefb13a833c` | 9,626 | 42 | 42 | 14 |
| C | `references/templates.md` | `10606c656fec7c4fd2d26cc6bd4c53e84bf2e770cace420be2d892f042070360` | 35,619 | 10 | 6 | 2 |
| C | `references/config.md` | `f8c4990341e0a3359a983fd886659b7c83aa3629fceabf7a9978fad31b67c1e7` | 80,401 | 5 | 3 | 1 |
| E | `SKILL.md` | `fe16ec8e7cb074bff1e247baec6f179c13beddd3579020f800317cefb13a833c` | 9,626 | 288 | 192 | 96 |

The byte counts and hashes are of the **upstream files**, which is what a
reader needs in order to restore them. Two details about how they appear:

- In **arm C** the skill loader strips the YAML frontmatter and prepends a
  `Base directory for this skill: ...` line, so the elided run is the SKILL.md
  body from its first heading onward (9,407 of the 9,626 bytes). The frontmatter
  and the base-directory line are still present in the transcripts.
- In **arm E** the document is injected whole, frontmatter included, appended
  to the task prompt. All 9,626 bytes are elided there.
- `references/config.md` was only ever **partially** read (the agent read the
  first 150 lines of 2,339), so arm C never contained the whole file. The
  placeholder still names the full upstream file, since that is what you fetch.

A previous draft of this README claimed arm C contained `references/config.md`
at ~11.7 KB and `references/templates.md` at ~78 KB. Both figures were wrong and
the two files were transposed; the table above is measured.

### What was deliberately NOT elided

The redaction is surgical because the open-rate detector reads structure, not
prose. Left completely intact:

- every `Skill` tool-call event (`"name":"Skill","input":{"skill":"..."}`) —
  this is what the strict detector actually counts;
- the init-event `skills` / `slash_commands` availability arrays;
- the one-line skill *description*, which is metadata, not the work;
- every `sessions/skills/<slug>/` path string, including `Read` `file_path`
  inputs and the `Base directory for this skill:` line;
- the `ARGUMENTS: <task prompt>` text carried on the same string as the body.

Method: target strings were located by *parsing* the JSON, then substituted
*textually* (the JSON-escaped body replaced by the JSON-escaped placeholder),
so no unrelated byte and no document structure changed.

### Verification

```console
$ python3 analyze/open_rate.py jobs/2026-08-16-skill-ab/armC-schpet \
    --slug schpet--toolbox--jj --quiet | python3 -c \
    "import json,sys; print(json.load(sys.stdin)['totals']['open_rate'])"
14/96
```

Unchanged from the pre-redaction value, so nothing the detector reads was cut.
Every JSON document and JSONL line in both redacted arms was re-parsed:
**22,306 parsed OK / 0 failed** in arm C, **20,442 / 0** in arm E.

### One thing that looks like leftover skill text and is not

A probe sweep of the redacted arms still matches short runs of
`references/jj-squash.md`, `references/jj-file-track.md`,
`references/tutorial.md` and `references/templates.md`. These are **jj's own
output**, captured from the container — `jj squash --help`, `jj file track
--help`, jj's conflict hints, and `jj help -k templates` — not the skill files.
The bundle's `references/` are generated from those same jj manpages and docs,
which is why they overlap. They are jj's Apache-2.0 output and are genuine
experimental evidence, so they stay.

```console
$ # the templates.md overlap in arm E, traced to its tool call
$ ... -> produced by: ('Bash', '{"command": "jj help -k templates 2>&1 | head -100"}')
```

---

## What else is not in this archive

### The third-party skill bundle (arm C)

Harbor copies a skill bundle into every trial at `agent/sessions/skills/<slug>/`;
those 96 copies were excluded during staging.

- upstream: `https://github.com/schpet/toolbox` (skill `jj`)
- pinned commit: `b39b24eacb9473e20f7271c23ee7160f74317d24`
- harbor digest: `sha256:65be8ec6ca029247f2288e6f3625ec1a6928de3f9faeca9127645a63b0921fbc`

```console
$ find jobs/2026-08-16-skill-ab -type d -name 'schpet--toolbox--jj' | wc -l
0
```

Arm E carried no bundle at all (an extra instruction is not a skill), so it has
no `sessions/skills/` content to exclude.

### Arm E's input file

`arms/schpet-forced.md` is the schpet SKILL.md verbatim, so it is **not** placed
in `arms/FINAL/` — that directory holds only the arm inputs we own and may
redistribute. It is identified by hash in the redaction table above.

---

## Layout

```
jobs/2026-08-16-skill-ab/
├── README.md              ← this file
├── arms/FINAL/            ← the arm inputs we own, with sha256s
│   ├── MANIFEST.txt
│   ├── forced-reference.md            (arm D)
│   └── jj-working-practices/SKILL.md  (arm B)
├── armA-control/
├── armB-decoy/
├── armC-schpet/
├── armD-forced/
└── armE-schpet-forced/
```

Each arm directory holds `config.json`, `lock.json`, `result.json`, `job.log`,
and 96 trial directories. Each trial directory holds:

```
<task>__<slug>/
├── config.json, lock.json, result.json, trial.log
├── agent/
│   ├── claude-code.txt          transcript, JSONL
│   ├── trajectory.json
│   └── sessions/                .claude.json, per-project JSONL transcript
├── artifacts/manifest.json
└── verifier/
    ├── ctrf.json                pytest CTRF report  ← anchor codes live here
    ├── test-stdout.txt          pytest stdout       ← and here
    └── reward.txt               scalar reward
```

### Verify the arm inputs we own

```console
$ (cd jobs/2026-08-16-skill-ab/arms/FINAL && grep -E '^[0-9a-f]{64}' MANIFEST.txt | sha256sum -c -)
./forced-reference.md: OK
./jj-working-practices/SKILL.md: OK
```

---

## Re-deriving the headline numbers

### Trial counts

```console
$ for a in armA-control armB-decoy armC-schpet armD-forced armE-schpet-forced; do
    printf '%-20s %s\n' "$a" "$(ls -d jobs/2026-08-16-skill-ab/$a/*/ | wc -l)"
  done
armA-control         96
armB-decoy           96
armC-schpet          96
armD-forced          96
armE-schpet-forced   96
```

### Mean reward — from harbor's own job summary

```console
$ for a in armA-control armB-decoy armC-schpet armD-forced armE-schpet-forced; do
    printf '%-20s ' "$a"
    python3 -c "
import json
d=json.load(open('jobs/2026-08-16-skill-ab/$a/result.json'))
e=next(iter(d['stats']['evals'].values()))
print(round(e['metrics'][0]['mean'],4), 'n=%d'%e['n_trials'], 'errors=%d'%e['n_errors'])"
  done
armA-control         0.6563 n=96 errors=0
armB-decoy           0.6094 n=96 errors=0
armC-schpet          0.6693 n=96 errors=0
armD-forced          0.8194 n=96 errors=0
armE-schpet-forced   0.6936 n=96 errors=0
```

### Mean reward — re-derived independently from the per-trial reward files

This does not read harbor's summary at all; it re-averages the 96 scalar
rewards. It agrees with the summary to four decimals in every arm, which is the
point of running it.

```console
$ for a in armA-control armB-decoy armC-schpet armD-forced armE-schpet-forced; do
    printf '%-20s ' "$a"
    cat jobs/2026-08-16-skill-ab/$a/*/verifier/reward.txt \
      | awk '{s+=$1; n++} END {printf "n=%d mean=%.4f\n", n, s/n}'
  done
armA-control         n=96 mean=0.6563
armB-decoy           n=96 mean=0.6094
armC-schpet          n=96 mean=0.6693
armD-forced          n=96 mean=0.8194
armE-schpet-forced   n=96 mean=0.6936
```

### Strict passes (reward exactly 1)

```console
$ for a in armA-control armB-decoy armC-schpet armD-forced armE-schpet-forced; do
    printf '%-20s strict=%s / 96\n' "$a" \
      "$(grep -lx '1' jobs/2026-08-16-skill-ab/$a/*/verifier/reward.txt | wc -l)"
  done
armA-control         strict=50 / 96
armB-decoy           strict=45 / 96
armC-schpet          strict=49 / 96
armD-forced          strict=70 / 96
armE-schpet-forced   strict=56 / 96
```

---

## Anchor violations — read this before you grep

> **Correction to the previous archive's README.** It told readers to look for
> anchor violations in `*/trial.log`. **That returns zero and always will** —
> `trial.log` is harbor's orchestration log and never contains the verifier's
> assertion text. Anyone following that instruction would have concluded there
> were no violations in any arm. There are 62 across the five arms.

The codes are raised by a session-scoped autouse fixture in the verifier, so
they land in the pytest CTRF report and in pytest's stdout. **Either of these
two files is correct**, and they agree:

```console
$ for a in armA-control armB-decoy armC-schpet armD-forced armE-schpet-forced; do
    printf '%-20s ctrf=%s  stdout=%s\n' "$a" \
      "$(grep -l 'BOOTSTRAP_ANCHOR_VIOLATION' jobs/2026-08-16-skill-ab/$a/*/verifier/ctrf.json | wc -l)" \
      "$(grep -l 'BOOTSTRAP_ANCHOR_VIOLATION' jobs/2026-08-16-skill-ab/$a/*/verifier/test-stdout.txt | wc -l)"
  done
armA-control         ctrf=10  stdout=10
armB-decoy           ctrf=16  stdout=16
armC-schpet          ctrf=14  stdout=14
armD-forced          ctrf=10  stdout=10
armE-schpet-forced   ctrf=12  stdout=12
```

### Breaking the violations down by code

One caveat: the fixture is session-scoped and autouse, so the violation message
is repeated once per failing test in a trial. Counting *occurrences* overcounts.
Count one code per **trial** by taking only the first match in each file:

```console
$ for a in armA-control armB-decoy armC-schpet armD-forced armE-schpet-forced; do
    echo "-- $a"
    for f in jobs/2026-08-16-skill-ab/$a/*/verifier/test-stdout.txt; do
      grep -ho 'codes=[A-Z0-9-]*' "$f" | head -1
    done | sort | uniq -c
  done
-- armA-control
      1 codes=ANCHOR-CHANGE-ID-DIVERGENT
      9 codes=ANCHOR-CHANGE-ID-MISSING
-- armB-decoy
      1 codes=ANCHOR-CHANGE-ID-DIVERGENT
     15 codes=ANCHOR-CHANGE-ID-MISSING
-- armC-schpet
      1 codes=ANCHOR-CHANGE-ID-DIVERGENT
     13 codes=ANCHOR-CHANGE-ID-MISSING
-- armD-forced
     10 codes=ANCHOR-CHANGE-ID-MISSING
-- armE-schpet-forced
     12 codes=ANCHOR-CHANGE-ID-MISSING
```

---

## Did the agent actually use jj, and did the guidance actually reach it?

### Trials that invoked `jj` in a Bash tool call

A plain `grep jj` over a transcript is far too loose — the string appears in
task prose, in file paths, and in the agent's own commentary. This walks the
JSONL and only counts genuine `Bash` tool calls:

```console
$ python3 - <<'PY'
import json, re, pathlib
JJ = re.compile(r'(?:^|[;&|(\s])jj(?:\s|$)')
for arm in ["armA-control","armB-decoy","armC-schpet","armD-forced","armE-schpet-forced"]:
    trials = sorted(p for p in pathlib.Path("jobs/2026-08-16-skill-ab", arm).iterdir() if p.is_dir())
    hit = 0
    for t in trials:
        tp = t / "agent" / "claude-code.txt"
        if not tp.is_file():
            continue
        for line in tp.read_text(errors="replace").splitlines():
            if not line.startswith("{"):
                continue
            try: ev = json.loads(line)
            except Exception: continue
            msg = ev.get("message")
            if not isinstance(msg, dict): continue
            content = msg.get("content")
            if not isinstance(content, list): continue
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Bash":
                    if JJ.search((b.get("input") or {}).get("command") or ""):
                        hit += 1; break
            else:
                continue
            break
    print(f"{arm}: ran jj in {hit}/{len(trials)} trials")
PY
armA-control: ran jj in 89/96 trials
armB-decoy: ran jj in 90/96 trials
armC-schpet: ran jj in 94/96 trials
armD-forced: ran jj in 95/96 trials
armE-schpet-forced: ran jj in 96/96 trials
```

### Did the guidance actually reach the agent?

This is the measurement that separates arms D and E from arms B and C. A skill
is *offered*; the agent may never open it. An extra instruction is *injected*;
the agent has no say. Probe for a distinctive sentence from each artifact **in
the transcripts only**.

For arms C and E the skill prose has been elided, so the probe is the elision
placeholder — which sits exactly where the prose sat, one per delivery, and
therefore counts the same thing:

```console
$ probe_count () {   # $1=arm  $2=probe string
    grep -rl "$2" \
      jobs/2026-08-16-skill-ab/$1/*/agent/sessions/projects/ \
      jobs/2026-08-16-skill-ab/$1/*/agent/trajectory.json 2>/dev/null \
      | cut -d/ -f4 | sort -u | wc -l
  }
$ echo -n "armB decoy SKILL.md opened:   "; probe_count armB-decoy   'state the intent in one line'
armB decoy SKILL.md opened:   8
$ echo -n "armC schpet SKILL.md opened:  "; probe_count armC-schpet  'ELIDED: schpet--toolbox--jj SKILL.md'
armC schpet SKILL.md opened:  14
$ echo -n "armD forced-ref present:      "; probe_count armD-forced  'reverses the last one and repeats further back'
armD forced-ref present:      96
$ echo -n "armE schpet injected:         "; probe_count armE-schpet-forced 'ELIDED: schpet--toolbox--jj SKILL.md'
armE schpet injected:         96
$ echo -n "armA control (decoy probe):   "; probe_count armA-control 'state the intent in one line'
armA control (decoy probe):   0
$ echo -n "armA control (forced probe):  "; probe_count armA-control 'reverses the last one and repeats further back'
armA control (forced probe):  0
$ echo -n "armE (armD's probe, expect 0):"; probe_count armE-schpet-forced 'reverses the last one and repeats further back'
armE (armD's probe, expect 0):0
```

So the offered skills were opened in **8/96** (arm B) and **14/96** (arm C),
while the injected documents reached **96/96** (arms D and E).

**Arm E is the control that keeps arm D honest.** Arm D moved the mean a long
way (0.66 → 0.82). Arm E proves that was the *content* of `forced-reference.md`
and not the mere fact of injection: the same delivery mechanism carrying the
schpet document reaches 96/96 but lands at 0.6936, barely above arm A's 0.6563
and well short of arm D. Delivery is necessary but nowhere near sufficient.

> **Do not use a bare `grep -r` across a whole arm directory for this.** Harbor
> copies the skill bundle into every trial, so the probe sentence matches the
> *vendored skill file* rather than any transcript, and every arm scores 96:
>
> ```console
> $ grep -rl 'state the intent in one line' jobs/2026-08-16-skill-ab/armB-decoy/ | cut -d/ -f4 | sort -u | wc -l
> 96
> ```
>
> That is 96 copies of a file on disk, not 96 reads. Restrict the search to
> `agent/sessions/projects/` and `agent/trajectory.json`, as `probe_count` does.
> (Arms C and E are immune to this particular trap only because neither has a
> bundle in the archive; arm B's was kept, because we own it.)

---

## `userID` and `machineID` in `agent/sessions/.claude.json` — considered, kept

Every trial carries a `.claude.json` with 64-hex `userID` and `machineID`
fields. These were investigated rather than overlooked:

```console
$ python3 - <<'PY'
import json, glob
for arm in ["armA-control","armB-decoy","armC-schpet","armD-forced","armE-schpet-forced"]:
    us=set(); ms=set(); n=0
    for p in glob.glob(f"jobs/2026-08-16-skill-ab/{arm}/*/agent/sessions/.claude.json"):
        d=json.load(open(p)); n+=1
        us.add(d.get("userID")); ms.add(d.get("machineID"))
    print(f"{arm}: files={n} distinct userID={len(us)} distinct machineID={len(ms)}")
PY
armA-control: files=96 distinct userID=96 distinct machineID=96
armB-decoy: files=96 distinct userID=96 distinct machineID=96
armC-schpet: files=96 distinct userID=96 distinct machineID=96
armD-forced: files=96 distinct userID=96 distinct machineID=96
armE-schpet-forced: files=96 distinct userID=96 distinct machineID=96
```

**96 distinct values per arm — one per trial.** They are regenerated inside each
throwaway container, so they are ephemeral per-container identifiers, not a
stable account identifier or a host fingerprint. Nothing links them to a real
user or machine.

They are therefore **kept in place**, for two reasons: they are inert, and the
same class of value is already public in the existing
`archive/2026-08-14-baseline-24-trials` branch (274 `.claude.json` files),
so stripping them here would make the two archives inconsistent for no gain.

Stated explicitly so a future reader knows this was a decision, not an oversight.

Note the contrast with the build-path rewrite above: the session UUID was
rewritten out precisely *because* it is the opposite kind of value — one stable
identifier, live at publication time, repeated in every arm.

---

## Credential scanning

Before commit, the staged tree was scanned twice with independent tooling, over
all 6,842 staged files (130.0 MiB). Both passes are clean.

**Pass 1 — `analyze/credscan.py`**, the project's pattern/entropy scanner.
Exit code 0, zero suspects:

```
  VALUE  generic_secretish (kept)                           0  clean
  GUARD  boundary-eroded specific shapes                    0  clean
  GUARD  demotions refused (boundary erosion)               0  clean
```

Two changes were needed to reach zero, both narrow, and neither of them
weakens the scanner:

- The 56 hits on jj's own build hash (`jj 0.44.0-af45d57de…`) are a public
  release identifier. It is allowlisted as a **literal**, not a pattern, so the
  entry can never widen to cover anything else.
- The other 16 were a **tokenizer artifact**: `jj op log` output captured into
  JSON puts a 40-hex operation ID immediately before an escaped newline, so the
  ID fused with the next line's first word into one token (`…fad4c7d2point`).
  Rather than allowlisting that shape — which would have let a secret ride out
  glued to a commit ID — the tokenizer now *splits* such a token, demotes the
  40-hex half as a commit ID, and puts the trailing word back through the
  ordinary rules to earn its own demotion. The split is attempted only on
  tokens that would otherwise be reported, so it cannot change any existing
  verdict.

The boundary-erosion guard was re-tested after the change against four
prefix-glued fake secrets (AWS, GitHub, `sk-`, JWT — freshly invented values,
deleted afterwards) and fired on all four. A secret glued *after* a commit ID
is not split, stays a suspect, and is caught by the guard as well.

**Pass 2 — a separate check with different logic**: enumerating every
`key: value` / `key=value` pair whose key matches a credential-ish word, plus a
byte-search of the corpus for the value of every secret-ish environment
variable present in the build session. Exit code 0. In particular
`CLAUDE_CODE_SESSION_ID`, which appeared in 1,550 files before the path
rewrite, is now absent from the corpus.

Pass 2's key-first sweep reports 8 distinct credential-ish keys for human
sign-off. All 8 were reviewed and none is a credential:

| key | hits | what it is |
|---|---:|---|
| `session_id` / `sessionid` | 76,424 / 33,382 | the per-trial conversation UUID, regenerated in each throwaway container |
| `signature` | 12,657 | server-issued integrity signatures over model thinking blocks |
| `key`, `key_pattern`, `self.tokens`, `oauth-refresh`, `noauth-refresh` | 88 / 8 / 8 / 23 / 8 | strings from the benchmark tasks' own fixture repositories (idempotency keys, a regex, a token-bucket field, config filenames) |

Known scanner limitations, recorded so a later reader does not overtrust pass 1:
UUID-shaped secrets and bare 32/40-character hex secrets can still slip past
`credscan.py`. The `userID`/`machineID` values above are exactly the 64-hex
shape that the second check enumerates explicitly; they are accounted for in the
section above.
