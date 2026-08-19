# Archive: per-trial records, arm G (blind-authorship forced arm), 2026-08-19

This is an **orphan branch**. It shares no history with `main`, has no parent
commit, and carries no project source — only this README and the raw harbor job
directory for one 96-trial arm, plus the two scripts that were run against it.
`jobs/` is in the repository's `.gitignore` on every normal branch, which is why
these records live here rather than in a results PR. **Nothing here is meant to
be merged**, and because it descends from nothing it cannot be merged into
`main` by accident. This matches `archive/2026-08-16-skill-ab-trials` and
`archive/2026-08-14-baseline-24-trials`, which are built the same way.

The write-up these records back is **`results/2026-08-19-skill-armG.md`**.

**Arm G is the blind-authorship arm.** It fills arm D's slot in the 2026-08-16
six-arm design (`archive/2026-08-16-skill-ab-trials` @ `b7746772c4`) with one
byte changed: the injected document. Arm D's reference was written by us with
the failing tasks in view; arm G's was written from the jj 0.44.0 binary, the
v0.44.0 docs and the changelog alone, by an author who never saw the task suite,
the fixtures, the verifiers or any prior result.

- **jj version under test:** 0.44.0
- **harbor:** 0.20.0 (`armG-blind-forced/lock.json` → `.harbor.version`)
- **agent / model:** `claude-code` / `claude-haiku-4-5-20251001`
- **suite:** 24 tasks × `-k 4` attempts = **96 trials**
- **task images:** built from `42273ba1ac3f17cd6d3122c1442258b995498858`
  (tip of `repro/2026-08-14-informed-arm-images`) — the same pin arms A–F used
- **exceptions:** 0 — all 96 trials scored, all 96 produced `verifier/ctrf.json`
- **arm mean reward:** 0.729167 · strict passes 62/96 · anchor violations 11/96
- **harbor-recorded `cost_usd`:** $6.684122 (haiku needs no rescale)

Every command below was run against **this tree** and the output pasted under it
is the real output. Run them from `jobs/2026-08-19-armG/` unless stated
otherwise.

---

## Layout

```
/                                     ← branch root (orphan; no parent commit)
├── README.md                         ← this file
└── jobs/2026-08-19-armG/
    ├── MANIFEST.txt                  ← sha256 + sizes for the three non-record files
    ├── arms/
    │   └── armG-reference.md         ← THE INJECTED DOCUMENT, 14,360 bytes
    ├── tools/
    │   ├── verify_delivery.py        ← the two-layer delivery proof
    │   └── armG_stats.py             ← the estimator: paired t, Holm, cluster CIs,
    │                                    permutation, bootstrap
    └── armG-blind-forced/            ← the harbor job directory
        ├── config.json, lock.json, result.json, job.log
        └── <task>__<slug>/           ← 96 trial directories
            ├── config.json, lock.json, result.json, trial.log
            ├── agent/
            │   ├── claude-code.txt       stream-json transcript
            │   ├── trajectory.json       ← steps[0] carries the injected document
            │   └── sessions/             .claude.json + per-project JSONL
            ├── artifacts/manifest.json
            └── verifier/
                ├── ctrf.json             pytest CTRF report ← anchor codes live here
                ├── test-stdout.txt       pytest stdout      ← and here
                └── reward.txt            scalar reward
```

**The document sits at `arms/armG-reference.md`, which is its run-time path,
not under an `arms/FINAL/` directory as on the 2026-08-16 branch.** That is
deliberate: every trial's `lock.json` records the path `arms/armG-reference.md`,
so keeping it there lets `verify_delivery.py` run against this archive
unmodified and reproduce the delivery proof from the branch alone.

**Nothing is elided.** No third-party skill text was involved in this arm — the
document is ours — so unlike arms C and E on the 2026-08-16 branch there are no
redaction placeholders here, and a delivery check run against this archive
returns the true answer rather than a false zero.

```console
$ grep -rl "ELIDED" . | wc -l
0
$ find . -type d -path '*/sessions/skills/*' | wc -l
0
```

(The second is zero because arm G is a forced-instruction arm, not a skill arm;
an extra instruction carries no bundle.)

## The one way this archive is not raw

Harbor writes one absolute host path into each trial's `result.json`
(`trial_uri`). Every occurrence was rewritten by deleting the prefix, and
nothing else:

```
/root/scratch/armG/   ->   (deleted)
```

**97 files, 98 occurrences.** 96 of those files are trial `result.json`s (one
occurrence each); the 97th is `tools/armG_stats.py`, whose arm registry and
usage docstring name the run directory — and that file was **restored
byte-identical afterwards**, because the vendored script must be the script
that produced the numbers. So the two occurrences under `tools/` remain, on
purpose, and are the only ones left:

```console
$ grep -rl "/root/scratch/armG" . | grep -v '^./jobs/2026-08-19-armG/tools/' | wc -l
0
```

That path contains no session identifier and no credential; the rewrite is for
consistency with the other archive branches, not for redaction. All 675 JSON
files were re-parsed after the substitution and all 675 still parse.

**It changes no measurement, and that was checked rather than asserted** — the
arm mean and the anchor count were re-derived from the raw per-trial evidence
before and after:

| | mean (from 96 `reward.txt`) | anchor-violating trials | strict passes |
|---|---:|---:|---:|
| before rewrite | 0.729167 | 11 | 62 |
| after rewrite | 0.729167 | 11 | 62 |

## `userID` / `machineID` — considered, kept

```console
$ python3 -c "
import json,glob
us=set();ms=set();n=0
for p in glob.glob('armG-blind-forced/*/agent/sessions/.claude.json'):
    d=json.load(open(p));n+=1;us.add(d.get('userID'));ms.add(d.get('machineID'))
print('files=%d distinct userID=%d distinct machineID=%d'%(n,len(us),len(ms)))"
files=96 distinct userID=96 distinct machineID=96
```

96 distinct values — one per trial, regenerated inside each throwaway
container. Ephemeral per-container identifiers, not an account identifier or a
host fingerprint. Kept, for the same reason and with the same reasoning as
`archive/2026-08-16-skill-ab-trials`.

---

## The exact resolved config

`harbor run` writes its resolved configuration into the job directory, so
**`armG-blind-forced/config.json` is the authoritative record of what ran** —
prefer it over any reconstructed flag string.

```json
{
  "job_name": "armG-blind-forced",
  "n_attempts": 4,
  "agent_setup_timeout_multiplier": 2.5,
  "n_concurrent_trials": 8,
  "retry": {"max_retries": 3,
            "include_exceptions": ["AgentSetupTimeoutError","RuntimeError","EnvironmentStartTimeoutError"]},
  "environment": {"type": "docker", "override_memory_mb": 2048},
  "agents": [{"name": "claude-code", "model_name": "claude-haiku-4-5-20251001"}],
  "datasets": [{"path": "informed/tasks"}],
  "extra_instruction_paths": ["arms/armG-reference.md"]
}
```

Field-for-field against arm D's archived `config.json`
(`archive/2026-08-16-skill-ab-trials` @ `b7746772c4`,
`jobs/2026-08-16-skill-ab/armD-forced/config.json`), **ten fields are identical**
— `n_attempts`, `agent_setup_timeout_multiplier`, `n_concurrent_trials`,
`retry.max_retries`, `retry.include_exceptions` (same set; harbor stores it
unordered), `environment.type`, `environment.override_memory_mb`,
`agents[0].name`, `agents[0].model_name`, `datasets[0].path` — and **three
differ**:

| field | arm D | arm G | why |
|---|---|---|---|
| `job_name` | `armD-forced` | `armG-blind-forced` | intended — the arm's identity |
| `extra_instruction_paths` | `["arms/forced-reference.md"]` | `["arms/armG-reference.md"]` | intended — the one manipulated variable |
| `jobs_dir` | `"jobs"` | *absent* | an artifact of the 2026-08-16 archive's path rewriting, not a run difference |

On `jobs_dir`: harbor serialises the resolved config with `exclude_defaults=True`
(`harbor/cli/jobs.py:1519`) and the default is `jobs_dir: Path = Path("jobs")`
(`harbor/models/job/config.py:320`), so arm G — launched with `--jobs-dir jobs`,
which equals the default — omits the key. Arm D recorded a non-default absolute
path, which the 2026-08-16 archive's prefix rewrite collapsed to the string
`"jobs"`. Both arms wrote into a `jobs/` directory alongside `arms/` and
`informed/tasks/`, so the effective value is the same.

### The launch command, verbatim

```
env -u ANTHROPIC_API_KEY -u CLAUDE_CODE_OAUTH_TOKEN \
  ANTHROPIC_BASE_URL="https://gateway-us.pydantic.dev/proxy/anthropic" \
  ANTHROPIC_AUTH_TOKEN="$PYDANTIC_AI_GATEWAY_API_KEY" \
  DOCKER_DEFAULT_PLATFORM=linux/amd64 POCHI_API_KEY=dummy \
  uvx --from harbor==0.20.0 harbor run \
    --job-name armG-blind-forced \
    --jobs-dir jobs \
    -k 4 -n 8 \
    --agent-setup-timeout-multiplier 2.5 \
    --max-retries 3 \
    --retry-include AgentSetupTimeoutError \
    --retry-include EnvironmentStartTimeoutError \
    --retry-include RuntimeError \
    -a claude-code -m claude-haiku-4-5-20251001 \
    --env docker \
    --path informed/tasks \
    --override-memory-mb 2048 \
    --extra-instruction-path arms/armG-reference.md \
    -y
```

**`--path`, not `--dataset`.** The 2026-08-16 archive README reconstructs the
flag form with `--dataset informed/tasks`; in harbor 0.20.0 `--dataset`/`-d` is
a *registry* identifier (`name@version`) and a local directory needs
`--path`/`-p`. Launching with `--dataset` fails in ~15 s with
`ValueError: Tag 'latest' not found for dataset 'informed/tasks'` and creates no
job directory. The resolved `config.json` records `datasets: [{"path": ...}]` in
both arms, which is what `--path` produces — so this is a defect in the
reconstructed flag string on that branch, not a difference in what ran.

---

## How to reproduce

### 0. Fetch this branch and the 2026-08-16 branch

Both are orphans and must be fetched by name:

```bash
git fetch origin archive/2026-08-19-armG-trials
git fetch origin archive/2026-08-16-skill-ab-trials
```

### 1. Rebuild the task images from the pin

```bash
mkdir -p ~/scratch/armG && cd ~/scratch/armG && git init -q
git remote add origin https://github.com/moredatarequired/jj-benchmark
git fetch --depth=1 origin 42273ba1ac3f17cd6d3122c1442258b995498858
git checkout -q FETCH_HEAD
mv tasks informed_tasks && mkdir -p informed && mv informed_tasks informed/tasks
python3 scripts/bootstrap_anchor.py --write      # builds all 24 images and KEEPS them
python3 scripts/bootstrap_anchor.py --check
python3 scripts/bootstrap_anchor.py --verify-untouched
```

`scripts/bootstrap_anchor.py` anchors the tree its own `__file__` lives in and
has no path flag, so it must be run from the scratch tree. The anchors it
writes (`tasks/*/tests/bootstrap_anchor.json`) are gitignored at `.gitignore:74`,
so `git status` stays silent about a stale one — `--check` is the loud signal.

**A rebuilt image will not reproduce the recorded `task.digest`.** The per-task
digest hashes the task directory including that per-build anchor file, so it
moves on every build: this arm records
`sha256:9e16272a3ed2c6ad802ecc6357aca18253b33ae6fb2d8cb8b94ec3de780313d1` for
`abandon_commits` against the 2026-08-16 arms' `sha256:adf1885265fc46…`, from
the same git tree. The digest is tree-*sensitive* but not tree-*recoverable*;
comparability across arms rests on the git pin, not on the digest.

### 2. Re-run the arm

Copy `arms/armG-reference.md` from this branch into `~/scratch/armG/arms/`,
confirm `sha256sum` gives
`6075fc63ded87a305f143fbd471ee18b2a6782845f204fb6add56657ebe61440`, then run
the launch command above.

### 3. Prove delivery — before trusting any number

```console
$ python3 tools/verify_delivery.py armG-blind-forced arms/armG-reference.md
job dir          : armG-blind-forced
document         : arms/armG-reference.md (14360 bytes)
expected path    : arms/armG-reference.md
expected digest  : sha256:6075fc63ded87a305f143fbd471ee18b2a6782845f204fb6add56657ebe61440
expected trials  : 96

trial dirs found : 96

LAYER 1  lock.json extra_instructions digest : 96/96

LAYER 2  trajectory.json steps[0] tail bytes : 96/96

PASS: delivery proven on both layers, 96/96.
```

Exit status 0. Layer 1 reads the content digest harbor writes into every trial's
`lock.json` (`harbor/models/job/lock.py:288-290`, `:374-382`) and is immune to
transcript elision. Layer 2 reads `agent/trajectory.json` `steps[0]`, which is
`instruction.md` + `"\n\n"` + the document (`harbor/models/task/task.py:184-185`).

> **Do not use `agent/claude-code.txt` for this check.** It reads 0/96 even for a
> genuinely delivered, un-elided forced document, because harbor feeds the
> prompt on stdin (`claude_code.py:1512-1530`) and that file is only the
> `--output-format=stream-json` stream, which never echoes the prompt. Measured
> here on a distinctive sentence from the document:
>
> ```console
> $ grep -l 'Read-only `git` commands are fine' armG-blind-forced/*/agent/claude-code.txt | wc -l
> 0
> $ grep -l 'Read-only `git` commands are fine' armG-blind-forced/*/agent/trajectory.json | wc -l
> 96
> ```
>
> `verify_delivery.py` refuses to look at `claude-code.txt` for this reason.

### 4. Re-derive the arm mean, three independent ways

```console
$ cat armG-blind-forced/*/verifier/reward.txt | awk '{s+=$1;n++} END {printf "n=%d mean=%.6f\n",n,s/n}'
n=96 mean=0.729167
$ python3 -c "
import json;d=json.load(open('armG-blind-forced/result.json'));e=next(iter(d['stats']['evals'].values()))
print(round(e['metrics'][0]['mean'],6),'n=%d'%e['n_trials'],'errors=%d'%e['n_errors'],'cost=%.6f'%d['stats']['cost_usd'])"
0.729167 n=96 errors=0 cost=6.684122
$ grep -lx '1' armG-blind-forced/*/verifier/reward.txt | wc -l
62
$ cat armG-blind-forced/*/verifier/reward.txt | sort | uniq -c
     18 0
      4 0.250000
      6 0.500000
      6 0.666667
     62 1
```

The third path is `result.json` → `verifier_result.rewards.reward` per trial,
which `armG_stats.py` reads and cross-checks against `reward.txt`; it reports 0
disagreements.

### 5. Re-run the statistics

`armG_stats.py` re-implements the estimator of `results/2026-08-16-skill-ab.md`
so that arm G is analysed by the code that reproduces the published A–F figures.
It needs the six 2026-08-16 arm directories; point it at a checkout of that
branch:

```bash
AB=<path to archive/2026-08-16-skill-ab-trials>/jobs/2026-08-16-skill-ab
python3 tools/armG_stats.py \
  A=$AB/armA-control B=$AB/armB-decoy C=$AB/armC-schpet \
  D=$AB/armD-forced E=$AB/armE-schpet-forced F=$AB/armF-ref-as-skill \
  G=armG-blind-forced --exact-perm
```

Runs in ~47 s, no third-party dependencies. Seeds are fixed in the source:
permutation 200,000 draws seed 20260819, bootstrap 200,000 resamples seed
20260820, so the output is byte-reproducible. Run from this branch it reproduces
the run-scratchpad output of record **line for line, with one line differing** —
the echoed job-directory path.

**It re-derives arms A–F in the same pass, and they are unchanged by arm G's
presence:** 436 A–F cells were machine-compared against the pre-arm-G validation
run with 0 mismatches, covering the per-arm means, the arm intervals and DEFF,
all 11 published contrasts, the permutation legs, the channel/content share
block (byte-identical), the per-task table and the anchor and cost figures. The
one section that moves is Holm, by design: with G loaded the primary family
becomes G's three contrasts. Re-running the published seven-contrast family with
G loaded (`--primary D-A,F-A,D-C,F-C,D-F,E-D,E-C`) reproduces every published
adjusted p exactly, and E − D remains the only published contrast surviving
correction.

### 6. Anchor violations — read this before you grep

A violation forces reward to **exactly 0.0**, so it is invisible in a mean.
Report the split alongside the mean, never the mean alone.

```console
$ printf 'ctrf=%s  stdout=%s\n' \
    "$(grep -l 'BOOTSTRAP_ANCHOR_VIOLATION' armG-blind-forced/*/verifier/ctrf.json | wc -l)" \
    "$(grep -l 'BOOTSTRAP_ANCHOR_VIOLATION' armG-blind-forced/*/verifier/test-stdout.txt | wc -l)"
ctrf=11  stdout=11

$ for f in armG-blind-forced/*/verifier/test-stdout.txt; do
    grep -ho 'codes=[A-Z0-9-]*' "$f" | head -1
  done | sort | uniq -c
     11 codes=ANCHOR-CHANGE-ID-MISSING
```

Zero `ANCHOR-*-DIVERGENT`. By task: `operation_recovery` 4/4, `abandon_commits`
2/4, `propagated_conflict` 2/4, `mistaken_squash_recovery` 1/4, `rebase_branch`
1/4, `split_commit_interactive` 1/4. Of the 18 trials at reward 0.0, **11 are
anchor violations and 7 are genuine zeros**.

The fixture is session-scoped and autouse, so the message repeats once per
failing test in a trial — count one code per trial by taking the first match per
file, as above.

> **`trial.log` reads falsely clean and did again here.**
> `grep -l BOOTSTRAP_ANCHOR_VIOLATION armG-blind-forced/*/trial.log | wc -l`
> returns **0** against the true 11. Use `verifier/ctrf.json` or
> `verifier/test-stdout.txt`; they agree.

### 7. Did the agent use jj?

**96/96.** Walking the JSONL for genuine `Bash` tool calls (a bare `grep jj` over
a transcript is far too loose — the string appears in task prose, in paths and in
the agent's own commentary):

```console
$ python3 - <<'PY'
import json, re, pathlib
JJ = re.compile(r'(?:^|[;&|(\s])jj(?:\s|$)')
trials = sorted(p for p in pathlib.Path("armG-blind-forced").iterdir() if p.is_dir())
hit = 0
for t in trials:
    tp = t / "agent" / "claude-code.txt"
    if not tp.is_file(): continue
    found = False
    for line in tp.read_text(errors="replace").splitlines():
        if not line.startswith("{"): continue
        try: ev = json.loads(line)
        except Exception: continue
        msg = ev.get("message")
        if not isinstance(msg, dict): continue
        c = msg.get("content")
        if not isinstance(c, list): continue
        for b in c:
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Bash":
                if JJ.search((b.get("input") or {}).get("command") or ""): found = True; break
        if found: break
    hit += found
print(f"ran jj in {hit}/{len(trials)} trials")
PY
ran jj in 96/96 trials
```

---

## Verify the document

```console
$ (cd jobs/2026-08-19-armG && grep -E '^[0-9a-f]{64}' MANIFEST.txt | sha256sum -c -)
./arms/armG-reference.md: OK
./tools/verify_delivery.py: OK
./tools/armG_stats.py: OK
```

`MANIFEST.txt` also records lines/words/bytes: the document is **280 lines,
2,147 words, 14,360 bytes**. Arm D's document, for comparison, is 250 lines,
2,345 words, 16,143 bytes (`archive/2026-08-16-skill-ab-trials` @ `b7746772c4`,
`jobs/2026-08-16-skill-ab/arms/FINAL/MANIFEST.txt`). **They differ in formatting
as well as in content** — arm G has 17 fenced code blocks and arm D has none —
which the write-up records as a confound on D − G.

## Credential scanning

Scanned twice before commit, with independent tooling taken from
`archive/2026-08-16-skill-ab-trials` @ `b7746772c4`
(`jobs/2026-08-16-skill-ab/tools/`) and run unmodified. Both passes clean, both
exit 0.

**Pass 1 — `credscan.py`**, pattern/entropy, run value-first. **This README is
inside the scanned corpus**, unlike the 2026-08-16 branch, where the README had
to sit outside pass 1 because it pasted a pattern name that its own scanner
matches. This one describes that summary row instead of quoting it, so the whole
branch scans clean in one run:

```
$ python3 <2026-08-16 branch>/jobs/2026-08-16-skill-ab/tools/credscan.py \
    README.md jobs/2026-08-19-armG/armG-blind-forced jobs/2026-08-19-armG/arms \
    --allowlist <2026-08-16 branch>/jobs/2026-08-16-skill-ab/tools/credscan_allowlist.txt

files scanned: 1350          (this README + the 96 trial dirs + the document)
bytes scanned: ~24.6 MiB
  VALUE  all 13 specific-shape patterns (Anthropic and generic API
         keys, the gateway and Logfire token shapes, JWTs, AWS,
         GitHub and Slack tokens, private-key blocks, bearer /
         authorization / x-api-key headers, generic secretish)
                                                           0 each   clean
  GUARD  boundary-eroded specific shapes                        0   clean
  GUARD  demotions refused (boundary erosion)                   0   clean
  VALUE  generic_secretish (demoted by shape)               73587   info
  VALUE  generic_secretish (demoted by allowlist)            1012   info
  NAME   (5 rows: credential variable NAMES with no value or a
          name/sentinel value -- 96 each from the trials' own
          environment blocks, the rest from the launch command
          quoted in this README)                            benign
  LIVE   (15 live variables searched)                           0   clean

RESULT: clean, with 7 live variable(s) UNVERIFIED (2 unset, 5 not searchable)
```

The shape demotions are ~42.5k UUIDs, ~26.7k tokens inside model `signature`
fields, ~2.2k wordlike digit-free tokens and ~2.2k pure hex digests; the 1,012
allowlist demotions are harbor's own instruction and container ids. Every `NAME`
row is a variable *name* carrying no value or a sentinel value; the counts are
mildly self-referential, since this README quotes the launch command's
environment block and then gets scanned.
The allowlist's jj-build-hash entry (`0-af45d57de716…`) fired **0** times here
and is reported as unused. The 7 UNVERIFIED live variables are reported as
unverified rather than as passes, which is the tool's design.

**Pass 2 — `pass2_keyvalue_audit.py`**, different logic: key-first, so its blind
spots are not pass 1's. It enumerates every `key: value` / `key=value` pair whose
*key* is credential-ish regardless of the value's shape, then byte-searches the
corpus for the value of every secret-ish environment variable set in the session.
Pass 2 takes one root, so it is pointed at the whole branch — records, the
document, `tools/`, `MANIFEST.txt` and this README:

```
$ python3 <2026-08-16 branch>/jobs/2026-08-16-skill-ab/tools/pass2_keyvalue_audit.py .

files scanned: 1353          (the whole branch)
bytes scanned: ~24.6 MiB

CHECK A -- 5 distinct credential-ish key(s):
  anthropic_auth_token  1  README.md -- the launch command's
                           ANTHROPIC_AUTH_TOKEN="$PYDANTIC_AI_GATEWAY_API_KEY";
                           the "value" is the shell variable reference, not a secret
  key             16      idempotency-key strings from a task's own fixture repo
  session_id   12225      harbor/claude-code conversation id, ephemeral per trial
  sessionid     5702      the same id, in the session JSONL filename field
  signature     1971      server-issued integrity signatures over model thinking blocks

CHECK B -- 25 env vars searched, 8 SKIPPED (value < 12 chars, reported as
           unverified rather than as passes). All 25 searched values absent
           from the corpus, the gateway and Anthropic tokens, the GitHub and
           AWS credentials, the Logfire key and the session id among them.

RESULT: CHECK B CLEAN -- no live environment secret value appears in the corpus
        CHECK A found 5 distinct credential-ish key(s);
        every one is listed above and requires human sign-off.
```

All five CHECK A keys were reviewed and none is a credential. Four are the same
classes signed off on the 2026-08-16 branch; the fifth is this README quoting
the launch command, whose token argument is a `$VARIABLE` reference and not a
value. Scanning the record tree alone (`jobs/2026-08-19-armG`) returns the four
without it.

**Known limitations, recorded so a later reader does not overtrust pass 1:**
UUID-shaped and bare 32/40-hex secrets are not detected by `credscan.py`. The
`userID`/`machineID` values are exactly the 64-hex shape, and they are accounted
for in the section above. Pass 2's CHECK B searches only for variables set in the
session that runs it, and says nothing about the 8 it skipped.

## Not in this archive

- **The task tree and the built images.** Rebuild from the pin, above.
- **`tasks/*/tests/bootstrap_anchor.json`** — per-build, gitignored, and not
  part of a harbor job directory.
- **The credential scanners.** They live on
  `archive/2026-08-16-skill-ab-trials` @ `b7746772c4` under
  `jobs/2026-08-16-skill-ab/tools/` and were run from there unmodified; not
  copied here, so that there is one copy of record rather than two.
- **Arm D's document.** It is on that same branch at
  `jobs/2026-08-16-skill-ab/arms/FINAL/forced-reference.md`, sha256
  `a22214c6a228dc54b897b4898b4200ca20dd4afb9f6fc9e5ec51b6502b51908b`.
- **No third-party skill text**, in any form. Arm G neither used nor produced
  any.
