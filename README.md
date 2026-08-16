# Archive: per-trial records, 2026-08-16 skill-effect sweep (6 arms × 96 trials)

This is an **orphan branch**. It shares no history with `main`, has no parent
commit at all, and carries no project source — only this README and the raw
harbor job directories for one sweep. `jobs/` is in the repository's
`.gitignore` on every normal branch, which is why these records live here rather
than in a results PR. **Nothing on this branch is meant to be merged**, and
because it descends from nothing it cannot be merged into `main` by accident.
This matches `archive/2026-08-14-baseline-24-trials`, which is built the same
way.

Raw harbor trial records for a six-arm comparison of how a *skill* affects an
agent's competence at Jujutsu (jj) tasks. All six arms run the same 24-task
"informed" suite, the same agent, the same model, and the same environment; the
only thing that varies is what jj guidance the agent is handed.

- **jj version under test:** 0.44.0
- **harbor:** 0.20.0 (`lock.json` → `.harbor.version` in each arm)
- **agent / model:** `claude-code` / `claude-haiku-4-5-20251001`
- **suite:** 24 tasks × `-k 4` attempts = **96 trials per arm**, **576 trials total**
- **exceptions:** 0 in every arm (all 576 trials scored)

Every command below was run against this archive **after** the two
transformations described in "Two ways this archive is not raw" below, and the
output pasted underneath is the real output, not a reconstruction. Run them
from the **repository root** (the root of this branch).

> **Everything here is runnable.** The sweep's own analysis tooling —
> `credscan.py`, `credscan_allowlist.txt`, `pass2_keyvalue_audit.py`,
> `open_rate.py` and `extract_arm.py` — is vendored into
> `jobs/2026-08-16-skill-ab/tools/`, so the credential scans, the open-rate
> detector and the per-task extractor can all be re-run against the archived
> tree. They need nothing but Python 3 and the standard library. Everything
> else is plain `grep`/`python3` against the archived files.
>
> One honest caveat, stated by the tool itself rather than hidden: pass 2's
> CHECK B byte-searches the corpus for the values of secret-ish environment
> variables *that are set in the session running it*. Re-running it in a
> different session searches for a different set of values, and it reports
> every variable it could not search as `SKIP` rather than as a pass. The
> output pasted below is from the build session, where
> `CLAUDE_CODE_SESSION_ID` — the identifier this archive's path rewrite
> removes — was set and was searched for.

---

## The six arms

| arm | job name | condition | trials | mean reward | strict passes | anchor-violating trials | ran `jj` |
|---|---|---|---:|---:|---:|---:|---:|
| A | `armA-control` | informed images, no skill | 96 | 0.6563 | 50 | 10 | 89 |
| B | `armB-decoy` | + our own `jj-working-practices` skill | 96 | 0.6094 | 45 | 16 | 90 |
| C | `armC-schpet` | + third-party `schpet--toolbox--jj` skill | 96 | 0.6693 | 49 | 14 | 94 |
| D | `armD-forced` | + `forced-reference.md` injected as an extra instruction | 96 | 0.8194 | 70 | 10 | 95 |
| E | `armE-schpet-forced` | + the schpet `SKILL.md` **injected** as an extra instruction | 96 | 0.6936 | 56 | 12 | 96 |
| F | `armF-ref-as-skill` | + `forced-reference.md` **offered** as a skill | 96 | 0.7557 | 60 | 9 | 93 |

"Informed" means all 24 task images write `/home/user/AGENTS.md` and symlink
`CLAUDE.md` to it. The symlink is load-bearing: the harness reads `CLAUDE.md`
and ignores a bare `AGENTS.md`. Arm A adds nothing on top of that baseline.

### The 2×2 at the centre of the sweep

Two things vary independently: **which document** is handed over, and **through
which channel**. Four of the six arms fill the cells of that grid:

| | offered as a `--skill` (elective) | injected as an extra instruction (forced) |
|---|---|---|
| **our** `forced-reference.md` | **F** `armF-ref-as-skill` | **D** `armD-forced` |
| the **third-party** schpet `SKILL.md` | **C** `armC-schpet` | **E** `armE-schpet-forced` |

Arm A is the no-guidance control the grid is measured against. Arm B is a
second document of ours — `jj-working-practices`, short and advisory rather
than a reference — offered through the same elective channel as C and F; it is
the decoy, present to show that *a* skill is not the same as *this* skill.

Each row of the grid holds the content fixed and varies the channel; each
column holds the channel fixed and varies the content. C and E carry the same
document byte-for-byte. D and F carry the same document apart from the
five-line frontmatter that makes it loadable as a skill. That is what makes the
grid readable: any difference within a row is the channel's doing, and any
difference within a column is the document's.

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
Arm F (reference as a skill) — arm A plus `--skill arms/jj-forced-as-skill`

`arms/schpet-forced.md` is byte-identical to the schpet `SKILL.md`
(sha256 `fe16ec8e7cb074bff1e247baec6f179c13beddd3579020f800317cefb13a833c`).
It is **not** archived here — see the redaction section.

`arms/jj-forced-as-skill/SKILL.md` is `arms/forced-reference.md` with a
five-line YAML frontmatter block (`name:` + `description:`) prepended, and
nothing else changed — that block is what makes a document loadable as a skill.
Both files are ours and both are archived under `arms/FINAL/`; the diff between
them is exactly those five lines.

Confirm the differences straight from the archived configs:

```console
$ for a in armA-control armB-decoy armC-schpet armD-forced \
           armE-schpet-forced armF-ref-as-skill; do
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
== armF-ref-as-skill
 skills: ['arms/jj-forced-as-skill']
 extra_instruction_paths: []
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
paths intact would publish a live session identifier 8,273 times. Every
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
| `armF-ref-as-skill` | 387 | 1,539 |
| **total** | **2,322** | **8,273** |

`arms/FINAL/MANIFEST.txt` is the one file in this archive that is neither a
harbor record nor a rewrite of one: it was **regenerated** when arm F's input
was added, and written with relative paths from the start, so there was nothing
in it to rewrite. Its checksums are verified below.

Every count in that table was re-derived from the untouched harbor job
directories rather than carried over from the earlier five-arm draft — which is
how the stale figure in the credential-scanning section below was caught.

The 387 files are the same set in every arm, and they add up exactly:

| file | count |
|---|---:|
| `config.json` | 97  (96 trials + the arm) |
| `lock.json` | 97  (96 trials + the arm) |
| `result.json` | 96  (trials only — the arm-level one carries no absolute path) |
| `trial.log` | 96 |
| `job.log` | 1 |
| **total** | **387** |

This README is the only file excluded from the mechanical rewrite; it was
edited by hand.

All 1,740 rewritten `.json` files were re-parsed after the substitution and all
1,740 still parse.

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
| `armF-ref-as-skill` | 0.755729 | 0.755729 | 9 | 9 |

Identical in every cell. (Arms E and F were each rewritten as a separate later
pass, once their runs finished; their before/after pairs were captured the same
way. Arm F's "before" figures were read out of the raw harbor job directory
before it was copied into this archive at all.)

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
the two files were transposed; the table above is measured. Every number in it
— placeholders, files and trials, not only the byte counts — was re-counted
from the committed tree by matching the placeholder text itself, and the
re-count reproduced the table exactly. The command is below.

**Arms A, B, D and F contribute no rows to this table, and that was checked
rather than assumed.** Arm F is the one worth being explicit about, because it
is a *skill* arm and so is the arm most likely to have picked up third-party
prose. Its skill is `arms/jj-forced-as-skill`, which is our own document, and
its bundle is therefore kept — but the staged arm was still probed for 18
distinctive lines of the schpet document, for the bare string `schpet`, and for
any pre-existing `[ELIDED:` placeholder before it was committed. Zero hits, so
nothing in arm F needed eliding.

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
$ python3 jobs/2026-08-16-skill-ab/tools/open_rate.py \
    jobs/2026-08-16-skill-ab/armC-schpet \
    --slug schpet--toolbox--jj --quiet | python3 -c \
    "import json,sys; print(json.load(sys.stdin)['totals']['open_rate'])"
14/96
```

Unchanged from the pre-redaction value, so nothing the detector reads was cut.
Every JSON document and JSONL line in both redacted arms was re-parsed:
**22,306 parsed OK / 0 failed** in arm C, **20,442 / 0** in arm E.

And the elision table itself, re-counted from the committed tree:

```console
$ python3 - <<'PY'
import pathlib, re, collections
root = pathlib.Path("jobs/2026-08-16-skill-ab")
rx = re.compile(r"\[ELIDED: (schpet--toolbox--jj) ([^,]+), (\d+) bytes, sha256 ([0-9a-f]{64})")
for arm in sorted(p.name for p in root.glob("arm?-*")):
    occ = collections.Counter()
    files = collections.defaultdict(set)
    trials = collections.defaultdict(set)
    for p in (root / arm).rglob("*"):
        if not p.is_file():
            continue
        for m in rx.finditer(p.read_text(errors="replace")):
            k = (m.group(2), m.group(3))
            occ[k] += 1
            files[k].add(str(p))
            trials[k].add(p.relative_to(root / arm).parts[0])
    if not occ:
        print(f"{arm}: no elisions")
        continue
    for k in sorted(occ):
        print(f"{arm}: {k[0]:24s} {k[1]:>6s} B  placeholders={occ[k]:4d} "
              f"files={len(files[k]):4d} trials={len(trials[k]):3d}")
PY
armA-control: no elisions
armB-decoy: no elisions
armC-schpet: SKILL.md                   9626 B  placeholders=  42 files=  42 trials= 14
armC-schpet: references/config.md      80401 B  placeholders=   5 files=   3 trials=  1
armC-schpet: references/templates.md   35619 B  placeholders=  10 files=   6 trials=  2
armD-forced: no elisions
armE-schpet-forced: SKILL.md                   9626 B  placeholders= 288 files= 192 trials= 96
armF-ref-as-skill: no elisions
```

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

Arms B and F are skill arms too, and **their bundles were kept**, because both
documents are ours. That asymmetry is deliberate and is the only reason arm C's
bundle is missing while theirs are present:

```console
$ for s in jj-working-practices schpet--toolbox--jj jj-forced-as-skill; do
    printf '%-22s %s\n' "$s" \
      "$(find jobs/2026-08-16-skill-ab -type d -path '*/sessions/skills/*' -name "$s" | wc -l)"
  done
jj-working-practices   96
schpet--toolbox--jj    0
jj-forced-as-skill     96
```

### Arm E's input file

`arms/schpet-forced.md` is the schpet SKILL.md verbatim, so it is **not** placed
in `arms/FINAL/` — that directory holds only the arm inputs we own and may
redistribute. It is identified by hash in the redaction table above.

---

## Layout

The whole branch, in full — there is nothing else on it:

```
/                                  ← branch root (orphan; no parent commit)
├── README.md                      ← this file
└── jobs/2026-08-16-skill-ab/
    ├── tools/                     ← the sweep's analysis tooling, vendored
    │   ├── credscan.py                pass-1 pattern/entropy scanner
    │   ├── credscan_allowlist.txt     its reviewed allowlist
    │   ├── pass2_keyvalue_audit.py    pass-2 key-first + env-value audit
    │   ├── open_rate.py               skill open-rate detector
    │   └── extract_arm.py             per-task breakdown for one arm
    ├── arms/FINAL/                ← the arm inputs we own, with sha256s
    │   ├── MANIFEST.txt
    │   ├── forced-reference.md            (arm D)
    │   ├── jj-working-practices/SKILL.md  (arm B)
    │   └── jj-forced-as-skill/SKILL.md    (arm F)
    ├── armA-control/
    ├── armB-decoy/
    ├── armC-schpet/
    ├── armD-forced/
    ├── armE-schpet-forced/
    └── armF-ref-as-skill/
```

The `tools/` directory is a copy of the build-time scripts, taken verbatim; it
is the only part of this archive that is code rather than record. It is here so
that the commands in this README are things you can run, not claims you have to
take on trust.

Each arm directory holds `config.json`, `lock.json`, `result.json`, `job.log`,
and 96 trial directories. Each trial directory holds:

```
<task>__<slug>/
├── config.json, lock.json, result.json, trial.log
├── agent/
│   ├── claude-code.txt          transcript, JSONL
│   ├── trajectory.json
│   └── sessions/                .claude.json, per-project JSONL transcript
│       └── skills/<slug>/       the skill bundle — arms B and F only
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
./jj-forced-as-skill/SKILL.md: OK
```

Arm F's input is arm D's input plus a frontmatter block, and that too is
checkable rather than asserted:

```console
$ diff jobs/2026-08-16-skill-ab/arms/FINAL/forced-reference.md \
       jobs/2026-08-16-skill-ab/arms/FINAL/jj-forced-as-skill/SKILL.md
0a1,5
> ---
> name: jj-forced-as-skill
> description: Operational reference for Jujutsu (jj) 0.44 — what each command actually does to the repository. Covers the rewriting surface (describe, commit, new, edit, squash, split, absorb, rebase, restore, abandon), the operation log and undo semantics, bookmarks and Git remotes, and the revset, fileset and template languages. Written for non-interactive agent use with no TTY and no editor, and it spells out the exit-status traps, including the mutations that match nothing and still exit 0. Use this whenever you are working in a jj repository and need exact command semantics rather than a guess.
> ---
>
```

---

## Re-deriving the headline numbers

### Trial counts

```console
$ for a in armA-control armB-decoy armC-schpet armD-forced \
           armE-schpet-forced armF-ref-as-skill; do
    printf '%-20s %s\n' "$a" "$(ls -d jobs/2026-08-16-skill-ab/$a/*/ | wc -l)"
  done
armA-control         96
armB-decoy           96
armC-schpet          96
armD-forced          96
armE-schpet-forced   96
armF-ref-as-skill    96
```

### Mean reward — from harbor's own job summary

```console
$ for a in armA-control armB-decoy armC-schpet armD-forced \
           armE-schpet-forced armF-ref-as-skill; do
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
armF-ref-as-skill    0.7557 n=96 errors=0
```

### Mean reward — re-derived independently from the per-trial reward files

This does not read harbor's summary at all; it re-averages the 96 scalar
rewards. It agrees with the summary to four decimals in every arm, which is the
point of running it.

```console
$ for a in armA-control armB-decoy armC-schpet armD-forced \
           armE-schpet-forced armF-ref-as-skill; do
    printf '%-20s ' "$a"
    cat jobs/2026-08-16-skill-ab/$a/*/verifier/reward.txt \
      | awk '{s+=$1; n++} END {printf "n=%d mean=%.4f\n", n, s/n}'
  done
armA-control         n=96 mean=0.6563
armB-decoy           n=96 mean=0.6094
armC-schpet          n=96 mean=0.6693
armD-forced          n=96 mean=0.8194
armE-schpet-forced   n=96 mean=0.6936
armF-ref-as-skill    n=96 mean=0.7557
```

### Strict passes (reward exactly 1)

```console
$ for a in armA-control armB-decoy armC-schpet armD-forced \
           armE-schpet-forced armF-ref-as-skill; do
    printf '%-20s strict=%s / 96\n' "$a" \
      "$(grep -lx '1' jobs/2026-08-16-skill-ab/$a/*/verifier/reward.txt | wc -l)"
  done
armA-control         strict=50 / 96
armB-decoy           strict=45 / 96
armC-schpet          strict=49 / 96
armD-forced          strict=70 / 96
armE-schpet-forced   strict=56 / 96
armF-ref-as-skill    strict=60 / 96
```

### Per-task breakdown for one arm

`tools/extract_arm.py` writes a per-task table and a per-trial JSON for one arm.
It re-derives everything from the trial directories, so it is a third
independent path to the same arm mean:

```console
$ python3 jobs/2026-08-16-skill-ab/tools/extract_arm.py \
    jobs/2026-08-16-skill-ab/armF-ref-as-skill armF --outdir /tmp/armF-extract
# Arm armF — per-task results

Job dir: `/home/user/jj-benchmark/jobs/2026-08-16-skill-ab/armF-ref-as-skill`

Trial dirs: 96 | with ctrf.json: 96 | without (ERRORED): 0 | scored: 96

**Arm mean reward: 0.7557**

| task | n scored | n errored | strict passes (>=1.0) | mean reward | ran jj |
|---|---:|---:|---:|---:|---:|
| abandon_commits | 4 | 0 | 3 | 0.7500 | 4 |
| absorb_changes | 4 | 0 | 4 | 1.0000 | 4 |
| bookmark_left_behind | 4 | 0 | 4 | 1.0000 | 4 |
| divergent_change | 4 | 0 | 3 | 0.9167 | 4 |
| duplicate_range | 4 | 0 | 4 | 1.0000 | 4 |
| edit_commit_message | 4 | 0 | 1 | 0.7500 | 4 |
| fileset_rollback | 4 | 0 | 3 | 0.8125 | 4 |
| git_fetch_remote | 4 | 0 | 3 | 0.8750 | 4 |
| immutable_stack | 4 | 0 | 0 | 0.6667 | 4 |
| merge_bookmarks | 4 | 0 | 4 | 1.0000 | 4 |
...
```

(Truncated here to ten rows; the command prints all 24, plus an anchor-code
breakdown and a reward histogram, and writes `armF_table.md` and
`armF_trials.json` into `--outdir`. `--outdir` is written to, so point it
somewhere outside this branch.)

---

## Anchor violations — read this before you grep

> **Correction to the previous archive's README.** It told readers to look for
> anchor violations in `*/trial.log`. **That returns zero and always will** —
> `trial.log` is harbor's orchestration log and never contains the verifier's
> assertion text. Anyone following that instruction would have concluded there
> were no violations in any arm. There are 71 across the six arms.

The codes are raised by a session-scoped autouse fixture in the verifier, so
they land in the pytest CTRF report and in pytest's stdout. **Either of these
two files is correct**, and they agree:

```console
$ for a in armA-control armB-decoy armC-schpet armD-forced \
           armE-schpet-forced armF-ref-as-skill; do
    printf '%-20s ctrf=%s  stdout=%s\n' "$a" \
      "$(grep -l 'BOOTSTRAP_ANCHOR_VIOLATION' jobs/2026-08-16-skill-ab/$a/*/verifier/ctrf.json | wc -l)" \
      "$(grep -l 'BOOTSTRAP_ANCHOR_VIOLATION' jobs/2026-08-16-skill-ab/$a/*/verifier/test-stdout.txt | wc -l)"
  done
armA-control         ctrf=10  stdout=10
armB-decoy           ctrf=16  stdout=16
armC-schpet          ctrf=14  stdout=14
armD-forced          ctrf=10  stdout=10
armE-schpet-forced   ctrf=12  stdout=12
armF-ref-as-skill    ctrf=9  stdout=9
```

### Breaking the violations down by code

One caveat: the fixture is session-scoped and autouse, so the violation message
is repeated once per failing test in a trial. Counting *occurrences* overcounts.
Count one code per **trial** by taking only the first match in each file:

```console
$ for a in armA-control armB-decoy armC-schpet armD-forced \
           armE-schpet-forced armF-ref-as-skill; do
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
-- armF-ref-as-skill
      1 codes=ANCHOR-CHANGE-ID-DIVERGENT
      8 codes=ANCHOR-CHANGE-ID-MISSING
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
for arm in ["armA-control","armB-decoy","armC-schpet","armD-forced",
            "armE-schpet-forced","armF-ref-as-skill"]:
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
armF-ref-as-skill: ran jj in 93/96 trials
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
$ echo -n "armF forced-ref opened:       "; probe_count armF-ref-as-skill 'reverses the last one and repeats further back'
armF forced-ref opened:       63
$ echo -n "armA control (decoy probe):   "; probe_count armA-control 'state the intent in one line'
armA control (decoy probe):   0
$ echo -n "armA control (forced probe):  "; probe_count armA-control 'reverses the last one and repeats further back'
armA control (forced probe):  0
$ echo -n "armE (armD's probe, expect 0):"; probe_count armE-schpet-forced 'reverses the last one and repeats further back'
armE (armD's probe, expect 0):0
```

The prose probe and the strict detector are independent implementations — one
greps for a sentence, the other parses the JSONL for `Skill` tool-call events —
so they are worth running against each other:

```console
$ for a in armB-decoy:jj-working-practices armC-schpet:schpet--toolbox--jj \
           armF-ref-as-skill:jj-forced-as-skill; do
    arm=${a%%:*}; slug=${a##*:}
    printf '%-20s %s\n' "$arm" \
      "$(python3 jobs/2026-08-16-skill-ab/tools/open_rate.py \
          jobs/2026-08-16-skill-ab/$arm --slug $slug --quiet \
          | python3 -c "import json,sys; print(json.load(sys.stdin)['totals']['open_rate'])")"
  done
armB-decoy           8/96
armC-schpet          14/96
armF-ref-as-skill    63/96
```

They agree in all three arms.

So the offered skills were opened in **8/96** (arm B), **14/96** (arm C) and
**63/96** (arm F), while the injected documents reached **96/96** (arms D
and E).

**Arm E is the control that keeps arm D honest.** Arm D moved the mean a long
way (0.66 → 0.82). Arm E proves that was the *content* of `forced-reference.md`
and not the mere fact of injection: the same delivery mechanism carrying the
schpet document reaches 96/96 but lands at 0.6936, barely above arm A's 0.6563
and well short of arm D. Delivery is necessary but nowhere near sufficient.

**Arm F is the control that keeps arm E honest in the other direction**, and it
is the reason the grid is worth having. Read the 2×2 by its numbers:

| | offered as a skill | injected | gap |
|---|---:|---:|---:|
| our `forced-reference.md` | **F** 0.7557 (opened 63/96) | **D** 0.8194 (96/96) | 0.0637 |
| the schpet `SKILL.md` | **C** 0.6693 (opened 14/96) | **E** 0.6936 (96/96) | 0.0243 |
| **content gap** | **0.0864** | **0.1258** | |

Three things fall out of it, and none of them is visible from any single arm:

1. **Content dominates channel.** Moving from the schpet document to ours is
   worth more (+0.086 elective, +0.126 forced) than moving from elective to
   forced delivery is (+0.024 for schpet, +0.064 for ours). A good document
   offered beats a mediocre one forced.
2. **The elective channel is lossy but not ruinous** — for a document the
   agent wants. Arm F reaches 0.7557 against arm A's 0.6563 and arm D's
   0.8194: offering the reference instead of forcing it recovers about 61% of
   the gain that forcing it produces.
3. **Open rate is a property of the document, not of the mechanism.** The same
   `--skill` channel that got the schpet skill opened 14/96 got ours opened
   63/96 — 4.5× as often, with an identical harness and identical tasks. Arm
   B's 8/96 rules out "our skills just get opened more": that is our document
   too, through the same channel, and it is the least-opened of the three.
   What differs is the frontmatter `description:`, which is all the agent sees
   before deciding.

The honest caveat: arm F's document is arm D's, and arm D's was written by us
with these 24 tasks in view. The grid measures channel and content faithfully
against each other; it does not tell you how a *neutral* reference of that
quality would fare.

> **Do not use a bare `grep -r` across a whole arm directory for this.** Harbor
> copies the skill bundle into every trial, so the probe sentence matches the
> *vendored skill file* rather than any transcript, and every arm scores 96:
>
> ```console
> $ grep -rl 'state the intent in one line' jobs/2026-08-16-skill-ab/armB-decoy/ | cut -d/ -f4 | sort -u | wc -l
> 96
> ```
>
> Arm F has the same trap, for the same reason:
>
> ```console
> $ grep -rl 'reverses the last one and repeats further back' jobs/2026-08-16-skill-ab/armF-ref-as-skill/ | cut -d/ -f4 | sort -u | wc -l
> 96
> ```
>
> 96 by the loose grep, 63 by `probe_count`, 63 by the strict detector. That is
> 96 copies of a file on disk against 63 actual reads. Restrict the search to
> `agent/sessions/projects/` and `agent/trajectory.json`, as `probe_count` does.
> (Arms C and E are immune to this particular trap only because neither has a
> bundle in the archive; arms B's and F's were kept, because we own both.)

---

## `userID` and `machineID` in `agent/sessions/.claude.json` — considered, kept

Every trial carries a `.claude.json` with 64-hex `userID` and `machineID`
fields. These were investigated rather than overlooked:

```console
$ python3 - <<'PY'
import json, glob
for arm in ["armA-control","armB-decoy","armC-schpet","armD-forced",
            "armE-schpet-forced","armF-ref-as-skill"]:
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
armF-ref-as-skill: files=96 distinct userID=96 distinct machineID=96
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

Before commit, the record tree was scanned twice with independent tooling, over
all 8,287 record files (154.5 MiB). Both passes are clean.

The scan target is the **records** — the six arm directories plus `arms/`.
Neither `tools/` nor this README is in that target; both are scanned, but
separately, and both results are stated below. The reason is the same in each
case: a scanner reading its own source, or a document quoting the scanner's
output, is a different question from a scanner reading a corpus of records.

**Pass 1 — `tools/credscan.py`**, the sweep's pattern/entropy scanner, run
value-first. Exit code 0, zero suspects:

```console
$ python3 jobs/2026-08-16-skill-ab/tools/credscan.py \
    jobs/2026-08-16-skill-ab/arm?-* jobs/2026-08-16-skill-ab/arms \
    --allowlist jobs/2026-08-16-skill-ab/tools/credscan_allowlist.txt
==============================================================================
credscan -- pre-publication credential scan
==============================================================================
roots        : .../armA-control, .../armB-decoy, .../armC-schpet,
               .../armD-forced, .../armE-schpet-forced, .../armF-ref-as-skill,
               .../arms
files scanned: 8287
bytes scanned: 162,014,807 (154.5 MiB)
...
  VALUE  sk_ant_key                                         0  clean
  VALUE  sk_generic_key                                     0  clean
  VALUE  pyd_gateway_token                                  0  clean
  VALUE  logfire_token                                      0  clean
  VALUE  jwt                                                0  clean
  VALUE  aws_access_key_id                                  0  clean
  VALUE  github_token                                       0  clean
  VALUE  slack_token                                        0  clean
  VALUE  private_key_block                                  0  clean
  VALUE  bearer_token                                       0  clean
  VALUE  authorization_hdr                                  0  clean
  VALUE  x_api_key_hdr                                      0  clean
  VALUE  generic_secretish (kept)                           0  clean
  GUARD  boundary-eroded specific shapes                    0  clean
  GUARD  demotions refused (boundary erosion)               0  clean
  VALUE  generic_secretish (demoted by shape)          514773  info
  VALUE  generic_secretish (demoted by allowlist)        6155  info
  NAME   ANTHROPIC_API_KEY [name only]                    576  benign
  NAME   apiKeySource [name with name/sentinel value]     576  benign
  WARN   prefilter hot / 0 per-line matches                 0  clean
  LIVE   (14 live variables searched)                        0  clean

==============================================================================
RESULT: clean, with 6 live variable(s) UNVERIFIED (2 unset, 4 not searchable)
  No value hits, no name-with-value hits, no live-credential hits
  among the variables that WERE searched. The following were not
  searched at all, so this run says nothing about them:
    - ANTHROPIC_API_KEY (declared): unset in environment
    - ANTHROPIC_AUTH_TOKEN (declared): unset in environment
    - CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR (name-swept): set but shorter than 12 chars -- too short to search safely
    - CLAUDE_CODE_WEBSOCKET_AUTH_FILE_DESCRIPTOR (name-swept): set but shorter than 12 chars -- too short to search safely
    - GIT_AUTHOR_NAME (name-swept): set but shorter than 12 chars -- too short to search safely
    - MAX_THINKING_TOKENS (name-swept): set but shorter than 12 chars -- too short to search safely
  Re-run with those variables set to close the gap.

  Reminder: UUID-shaped and hex-digest-shaped secrets are NOT detected.
  See the LIMITATIONS block at the top of credscan.py.
==============================================================================
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

**Pass 2 — `tools/pass2_keyvalue_audit.py`, a separate check with different
logic**, run key-first so that its blind spots are not pass 1's: it enumerates
every `key: value` / `key=value` pair whose *key* matches a credential-ish
word regardless of what the value looks like, then byte-searches the corpus for
the value of every secret-ish environment variable set in the session. Exit
code 0. In particular `CLAUDE_CODE_SESSION_ID`, which appeared in **2,322**
files before the path rewrite, is searched for and is absent from the corpus.

> A previous draft of this README put that figure at 1,550. That was the count
> taken when only four arms had been staged (4 × 387 files, plus the manifest);
> it was never updated as arms E and F landed. 2,322 is the measured count over
> all six arms — 387 files in each, every one of them now rewritten.

```console
$ python3 jobs/2026-08-16-skill-ab/tools/pass2_keyvalue_audit.py \
    jobs/2026-08-16-skill-ab
==============================================================================
PASS 2 -- independent key-first + exact-value audit
==============================================================================
root         : jobs/2026-08-16-skill-ab
files scanned: 8293
bytes scanned: 162,127,419 (154.6 MiB)

------------------------------------------------------------------------------
CHECK A -- every distinct credential-ish KEY carrying a value
------------------------------------------------------------------------------
  11 distinct key(s). Complete set, nothing elided:

  KEY                           HITS  VALUE LEN(S)       REDACTED SAMPLE            NOTE
  -------------------------- -------  ------------------ -------------------------- ----
  anchor_token                     1  26                 BOOT<+18ch>TION
  key                            112  25-27 (2 distinct) idem<+17ch>st[\
  key_pattern                      8  13                 re.c<+5ch>e(r\
  long_token                       1  12                 re.c<+4ch>le(r
  noauth-refresh                   8  12                 991a<+4ch>ffc9
  oauth-refresh                   23  12-47 (3 distinct) conf<+5ch>ml\n
  self.tokens                      8  13                 per_<+5ch>e\n│
  session_id                   88689  36                 6018<+28ch>14f7            harbor/claude-code conversation id, ephemeral per trial
  sessionid                    38856  36                 6018<+28ch>14f7            as session_id
  signature                    14580  364-4096 (748 distinct) EsoQ<+2828ch>QBgB
  signature_value                  1  12                 re.c<+4ch>le(r
...
------------------------------------------------------------------------------
CHECK B -- exact byte-search for live environment secrets
------------------------------------------------------------------------------
  (values read into memory only; never printed, written, or logged)
  env vars with secret-ish NAME : 31
  searched (value >= 12 chars): 24
  SKIPPED (not a pass)          : 7

  [ OK ] CLAUDE_CODE_SESSION_ID: searched, value not present anywhere in corpus
  ... 23 more [ OK ] lines ...

  Explicitly skipped -- these were NOT verified:
  [SKIP] CLAUDE_CODE_CHILD_SESSION: set but only 1 chars (< 12)
  [SKIP] CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR: set but only 1 chars (< 12)
  [SKIP] CLAUDE_CODE_POST_FOR_SESSION_INGRESS_V2: set but only 4 chars (< 12)
  [SKIP] CLAUDE_CODE_SYNC_SESSION_REFS: set but only 1 chars (< 12)
  [SKIP] CLAUDE_CODE_WEBSOCKET_AUTH_FILE_DESCRIPTOR: set but only 1 chars (< 12)
  [SKIP] GIT_AUTHOR_NAME: set but only 6 chars (< 12)
  [SKIP] MAX_THINKING_TOKENS: set but only 5 chars (< 12)

==============================================================================
RESULT: CHECK B CLEAN -- no live environment secret value appears in the corpus
        CHECK A found 11 distinct credential-ish key(s);
        every one is listed above and requires human sign-off.
==============================================================================
```

(Pass 2 takes one root, so it is pointed at the whole archive directory,
`tools/` included; pass 1 takes a list and is pointed at the records.)

Pass 2's key-first sweep reports **11** distinct credential-ish keys for human
sign-off. All 11 were reviewed and none is a credential:

| key | hits | what it is |
|---|---:|---|
| `session_id` / `sessionid` | 88,689 / 38,856 | the per-trial conversation UUID, regenerated in each throwaway container |
| `signature` | 14,580 | server-issued integrity signatures over model thinking blocks |
| `key`, `key_pattern`, `self.tokens`, `oauth-refresh`, `noauth-refresh` | 112 / 8 / 8 / 23 / 8 | strings from the benchmark tasks' own fixture repositories (idempotency keys, a regex, a token-bucket field, config filenames) |
| `anchor_token`, `long_token`, `signature_value` | 1 / 1 / 1 | **new in this run**: Python identifiers in `tools/`, not data. `anchor_token = "BOOTSTRAP_ANCHOR_VIOLATION"` in `extract_arm.py`; `long_token` and `signature_value` are parameter names in `credscan.py` whose "value" is the literal text `re.compile(r` from the next line |

Arm F changed the counts of the first eight but added no new key. The three new
keys come entirely from vendoring `tools/` into the scanned corpus, which is
the price of making this README's commands runnable — and they are exactly the
kind of finding pass 2 is designed to surface for a human rather than decide
for itself.

### Scanning the scanner

`tools/` was scanned by both passes as well, separately. Pass 2 is clean over
it (its three findings are the `anchor_token` / `long_token` / `signature_value`
rows above). **Pass 1 is not**, and the single hit is worth showing rather than
hiding:

```console
$ python3 jobs/2026-08-16-skill-ab/tools/credscan.py \
    jobs/2026-08-16-skill-ab/tools \
    --allowlist jobs/2026-08-16-skill-ab/tools/credscan_allowlist.txt --all
files scanned: 5
bytes scanned: 83,611 (0.1 MiB)
...
  [FAIL] pyd_gateway_token: 1 hit(s) in 1 file(s)
         .../tools/credscan.py:126  pyd_<+9ch>oken
...
RESULT: BLOCKED -- 1 value hit(s), ...
```

Line 126 of `credscan.py` is the definition of the `pyd_gateway_token` pattern
itself. The scanner is matching **its own pattern's name**, which happens to
have the shape the pattern looks for. There is no secret there.

Two things about how that was handled:

- It was **not** suppressed. The allowlist cannot suppress it even in
  principle — by design the allowlist is consulted only for the generic
  catch-all bucket and "never suppresses Section 1/2/3", and this is a
  Section-1 shape hit. Nor was the pattern renamed to make the noise go away:
  the vendored `credscan.py` is byte-identical to the one the sweep ran, and
  changing a scanner so that a corpus looks clean is precisely the move this
  README should never make.
- It is why the two scan targets are separate. Records are the thing being
  published; the scanner's source is a known self-referential special case.
  Folding them into one run would have meant either a false alarm on every
  future run or an edit to the scanner. Splitting them costs one extra command
  and one paragraph, and keeps both answers true.

### Scanning this README

Adding `README.md` to pass 1's roots makes it fail, and the failure is entirely
this document quoting the section above:

```console
$ python3 jobs/2026-08-16-skill-ab/tools/credscan.py \
    README.md jobs/2026-08-16-skill-ab/arm?-* jobs/2026-08-16-skill-ab/arms \
    --allowlist jobs/2026-08-16-skill-ab/tools/credscan_allowlist.txt
files scanned: 8288
...
  [FAIL] pyd_gateway_token: 5 hit(s) in 1 file(s)
         README.md:935   pyd_<+9ch>oken
         README.md:1096  pyd_<+9ch>oken
         README.md:1102  pyd_<+9ch>oken
         README.md:1132  pyd_<+9ch>oken
         README.md:1147  pyd_<+9ch>oken
...
  remaining (suspect): 2
      README.md:1050  CLAU<+31ch>S_V2  entropy=3.82
      README.md:1151  CLAU<+31ch>S_V2  entropy=3.82
...
RESULT: BLOCKED -- 5 value hit(s), 2 generic suspect(s), ...
```

All seven are strings this README prints on purpose. Five are the name
`pyd_gateway_token`: once in the pasted summary table, once in the `[FAIL]`
line of the tools scan, once in the sentence explaining that scan, and twice
more in this very section — the `[FAIL]` line just above and this sentence.
The other two are the environment variable name
`CLAUDE_CODE_POST_FOR_SESSION_INGRESS_V2`, copied out of pass 2's `SKIP` list
and then quoted again here. A name, not a value, in every case.

This is recursive in an unavoidable way: a document that reports what a
credential scanner found necessarily contains the scanner's vocabulary, and
scanning it reports the report. The alternative — mangling those strings so
they stop matching — would make the document less accurate in order to make a
tool quieter. So the README stays readable, sits outside pass 1's corpus, and
the exact consequence of putting it inside is printed here.

What that leaves unscanned is one hand-written file whose entire content is
prose, the outputs pasted above, and published hashes. It carries nothing
extracted from the trials beyond what is visibly quoted.

### Known limitations

Recorded so a later reader does not overtrust pass 1: UUID-shaped secrets and
bare 32/40-character hex secrets can still slip past `credscan.py`. The
`userID`/`machineID` values above are exactly the 64-hex shape that the second
check enumerates explicitly; they are accounted for in the section above.
