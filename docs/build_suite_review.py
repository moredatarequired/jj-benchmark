#!/usr/bin/env python3
"""Regenerate the suite review page, in both of its renderings.

This is a review aid, not benchmark machinery: nothing in the harness imports
it, and running it touches only the two output files named below.

One entry per task: the prompt, a short grading summary, one line of metadata,
and a known hole only where one exists. Everything shared - how scoring works,
what "anchored" means, that the proposed tasks are unbuilt - is said once at the
top and never repeated per task.

Inputs:
  suite_review_data_built.json     judgments about the 21 built tasks: grading
                                   summary, known hole, anchored/provisional
  suite_review_data_proposed.json  the 9 proposed tasks, design stage
  ../tasks/<name>/instruction.md            the prompt, read live
  ../tasks/<name>/tests/vacuity_floor.json  test count and floor, read live
  ../tasks/<name>/tests/anchor_exemptions.json  presence only, read live

Prompts and counts are deliberately NOT stored in the data files. Both went
stale there once already: the fourteen prompts were rewritten in 4c2a6de0 and
squash_range's floor was re-measured in af369f13, and the snapshot kept serving
the old values. Reading them from the task tree makes that failure impossible.

Outputs, both written by one run so they cannot drift apart:
  suite_review.html   one self-contained paged page, no external assets
  suite_review.md     the same content linearly, for GitHub's rendered view

Usage:  python3 docs/build_suite_review.py
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TASKS = os.path.join(ROOT, "tasks")

built_doc = json.load(open(os.path.join(HERE, "suite_review_data_built.json")))
proposed_doc = json.load(open(os.path.join(HERE, "suite_review_data_proposed.json")))


# ---------------------------------------------------------------------------
# read the task tree - prompts, counts and floors are never stored in the data
# ---------------------------------------------------------------------------

def read_task(name):
    d = os.path.join(TASKS, name)
    if not os.path.isdir(d):
        raise SystemExit("no such task: %s" % d)
    prompt = open(os.path.join(d, "instruction.md")).read().rstrip("\n")
    floor = json.load(open(os.path.join(d, "tests", "vacuity_floor.json")))
    if floor["task"] != name:
        raise SystemExit("%s/tests/vacuity_floor.json is labelled %r"
                         % (name, floor["task"]))
    total, floored = floor["tests"], floor["floor"]
    names = floor["passes_without_agent"]
    if len(names) != floored:
        raise SystemExit("%s: floor %d but %d names listed" % (name, floored, len(names)))
    return {
        "prompt": prompt,
        "tests_total": total,
        "tests_floored": floored,
        "tests_scored": total - floored,
        "floored_test_names": [n.split("::")[-1] for n in names],
        "anchor_exemptions": os.path.isfile(
            os.path.join(d, "tests", "anchor_exemptions.json")),
    }


# The seven non-shipping entries are no longer read from `tasks/`: they were
# deleted when the suite was cut to 14, so there is no instruction.md and no
# vacuity_floor.json to read. They stay in the review as a record of what went
# and why, which is a judgment stored in suite_review_data_built.json and needs
# no task tree.
shipping, demoted = [], []
for t in built_doc["tasks"]:
    item = dict(t)
    item["status"] = "built"
    if t["tier"] == "shipping":
        item.update(read_task(t["name"]))
        shipping.append(item)
    else:
        demoted.append(item)

proposed = []
for t in proposed_doc["tasks"]:
    item = dict(t)
    item["status"] = "proposed"
    item["name"] = "%s — %s" % (t["code"], t["headline"])
    proposed.append(item)

assert len(shipping) == 14, len(shipping)
assert len(demoted) == 7, len(demoted)
assert len(proposed) == 9, len(proposed)

SUITE_TOTAL = len([d for d in os.listdir(TASKS)
                   if os.path.isdir(os.path.join(TASKS, d))])


def meta_line(t):
    """The one metadata line an entry gets, built the same way for both outputs."""
    bits = ["%d test%s, %d floored" % (t["tests_total"],
                                       "" if t["tests_total"] == 1 else "s",
                                       t["tests_floored"])]
    bits.append("anchored" if t["anchored"] else "not anchored")
    if t["anchor_exemptions"]:
        bits[-1] += ", with exemptions"
    if t["provisional"]:
        bits.append("provisional, held for coverage")
    elif t["separated"]:
        bits.append("separates models")
    return " · ".join(bits)


def proposed_meta(t):
    return "design stage, nothing built · " + (
        "Hugh's wording, verbatim" if t["wording_from_hugh"] else "wording drafted")


# ---------------------------------------------------------------------------
# shared copy - said once, here, and never repeated per task
# ---------------------------------------------------------------------------

TITLE = "The jj suite: prompts and grading"

INTRO = (
    "Every task's prompt, and what its verifier actually checks. **14 built and "
    "shipping** — %d task directories in the tree, so that is the whole suite — "
    "plus **9 proposed** (design stage, plus one unassigned slot) and **7 cut**. "
    "Generated "
    "by `docs/build_suite_review.py`, which writes this file and "
    "`docs/suite_review.html` in the same run; prompts and test counts are read "
    "from `tasks/` at build time, not stored." % SUITE_TOTAL
)

PREAMBLE = [
    ("Scoring",
     "A verifier is a set of pytest assertions. Any test that passes on the "
     "untouched image with no agent is **floored** — measured, not declared, by "
     "`scripts/vacuity_floor.py` — and is excluded from both sides of the "
     "fraction, so the reward is *(scored tests passed) / (scored tests)*. A "
     "floored test still has to pass: if pytest exits non-zero for any reason the "
     "reward is capped strictly below 1.0, so a failing floored guard caps a "
     "correct solve without otherwise penalising it. A no-agent run scores 0 on "
     "every task by construction — the only tests it passes are the floored ones, "
     "so its numerator is empty."),
    ("Anchored",
     "Before the agent runs, the harness measures the untouched image and records "
     "the change ids the bootstrap gave each commit, the per-workspace "
     "working-copy keys and the handover operation id. A verifier is **anchored** "
     "when its assertions are phrased in those recorded ids rather than in "
     "descriptions, positions or bookmarks — which is what stops a repository "
     "rebuilt from `root()` collecting full marks. *With exemptions* means the "
     "task ships an `anchor_exemptions.json` naming the specific commits the "
     "asked-for work is allowed to remove. In cold CI there is no anchor file and "
     "each check falls back to what it asserted before, saying out loud that no "
     "identity claim was made."),
    ("The proposed nine",
     "Nothing in the second section exists. No fixture, no verifier, no run, no "
     "measurement — so there is no test count, no floor, no anchor decision and no "
     "measured weakness for any of them. Their *graded* sentences describe what a "
     "verifier would assert."),
]

SECTIONS = [
    ("shipping", "Shipping now — 14 built",
     "The prompt shown is the file the agent is handed, `tasks/<name>/instruction.md`, "
     "read at build time; the grading is what `tests/test_final_state.py` asserts. "
     "All fourteen were rewritten from specifications into requests in `4c2a6de0`.",
     shipping),
    ("proposed", "Proposed — 9 designs, none built",
     proposed_doc["section_note"] + " " + proposed_doc["standing_constraints"],
     proposed),
    ("demoted", "Cut — 7 that measured nothing",
     "Structurally sound, and deleted anyway: all seven scored 5/5 on all three "
     "model tiers, and a task every model passes contributes exactly nothing to "
     "a paired comparison while still costing an image build and a verifier run "
     "per sweep. They were briefly parked as a smoke tier; that tier was dropped "
     "with them. Listed as a record of what went, not for review — the "
     "directories are gone from `tasks/`, so there is no prompt or test count to "
     "read.",
     demoted),
]


# ---------------------------------------------------------------------------
# markdown
# ---------------------------------------------------------------------------

def gh_slug(text, seen):
    """GitHub's heading-anchor rule: lowercase, drop punctuation, spaces to hyphens."""
    s = text.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s, flags=re.UNICODE)
    s = s.replace(" ", "-")
    n = seen.get(s, 0)
    seen[s] = n + 1
    return s if n == 0 else "%s-%d" % (s, n)


def _esc(t):
    """Escape a run of plain prose so markdown renders it as written."""
    t = t.replace("\\", "\\\\")
    t = t.replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"(?<![0-9A-Za-z])_|_(?![0-9A-Za-z])", "\\\\_", t)
    t = t.replace("`", "\\`")  # only ever an unpaired leftover
    return t


def md_text(s):
    """Prose to markdown: backtick spans and **bold** kept, everything else escaped."""
    if s is None:
        return ""
    parts, i = [], 0
    for m in re.finditer(r"`+[^`]*`+|\*\*[^*]+\*\*", s):
        parts.append(_esc(s[i:m.start()]))
        parts.append(m.group(0))
        i = m.end()
    parts.append(_esc(s[i:]))
    return "".join(parts)


def fenced(text, lang="text"):
    """Fence verbatim text, widening the fence past any backtick run inside it."""
    runs = re.findall(r"`+", text)
    n = max(3, (max(len(r) for r in runs) + 1) if runs else 3)
    bar = "`" * n
    body = text if text.endswith("\n") else text + "\n"
    return "%s%s\n%s%s" % (bar, lang, body, bar)


md_seen, anchors = {}, {}
for sec, title, _blurb, _items in SECTIONS:
    anchors["sec:" + sec] = gh_slug(title, md_seen)
for t in shipping + proposed:
    anchors[t["name"]] = gh_slug(t["name"], md_seen)

L = []
A = L.append

A("# %s" % TITLE)
A("")
A(INTRO)
A("")
A("## How to read this")
A("")
for label, body in PREAMBLE:
    A("**%s.** %s" % (label, md_text(body)))
    A("")

A("## Contents")
A("")
for sec, title, _blurb, items in SECTIONS:
    A("**[%s](#%s)**" % (md_text(title), anchors["sec:" + sec]))
    A("")
    if sec == "demoted":
        A("- %s" % ", ".join("`%s`" % t["name"] for t in items))
    else:
        for t in items:
            A("- [%s](#%s)" % (md_text(t["name"]), anchors[t["name"]]))
    A("")

for sec, title, blurb, items in SECTIONS:
    A("---")
    A("")
    A("## %s" % md_text(title))
    A("")
    A(md_text(blurb))
    A("")

    if sec == "demoted":
        A("| task | what it asked |")
        A("| --- | --- |")
        for t in items:
            A("| `%s` | %s |" % (t["name"], md_text(t["summary"])))
        A("")
        A("Grading summaries and known holes for these seven are kept in "
          "`docs/suite_review_data_built.json` rather than reproduced here; the "
          "task directories themselves are recoverable at commit `73854f0b`, "
          "the last commit before the cut.")
        A("")
        continue

    for t in items:
        A("### %s" % md_text(t["name"]))
        A("")
        A(fenced(t["prompt"]))
        A("")
        if t["status"] == "built":
            A(md_text(t["grading"]))
            A("")
            A("`%s`" % meta_line(t))
            A("")
            if t.get("hole"):
                A("**Known hole.** " + md_text(t["hole"]))
                A("")
        else:
            if t.get("recast_note"):
                A("**Recast.** " + md_text(t["recast_note"]))
                A("")
            A(md_text(t["design"]))
            A("")
            A("`%s`" % proposed_meta(t))
            A("")
            if t.get("open_question"):
                A("**Open question.** " + md_text(t["open_question"]))
                A("")
            if t.get("explainer"):
                A("#### %s" % md_text(t["explainer_title"]))
                A("")
                for para in t["explainer"]:
                    A(md_text(para))
                    A("")

md = "\n".join(L).rstrip("\n") + "\n"
md_out = os.path.join(HERE, "suite_review.md")
open(md_out, "w").write(md)
print("wrote", md_out, len(md), "bytes,", md.count("\n"), "lines")


# ---------------------------------------------------------------------------
# html - same content, one task per page
# ---------------------------------------------------------------------------

def slug(name):
    m = re.match(r"^(N\d+)", name)
    return m.group(1).lower() if m else re.sub(r"[^a-z0-9_]+", "-", name.lower()).strip("-")


pages = []
for t in shipping:
    pages.append({
        "kind": "built", "section": "shipping", "slug": slug(t["name"]),
        "name": t["name"], "prompt": t["prompt"], "grading": t["grading"],
        "meta": meta_line(t), "hole": t.get("hole"),
        "floored": t["floored_test_names"],
    })
for t in proposed:
    pages.append({
        "kind": "proposed", "section": "proposed", "slug": slug(t["name"]),
        "name": t["name"], "code": t["code"], "headline": t["headline"],
        "prompt": t["prompt"], "grading": t["design"],
        "meta": proposed_meta(t), "recast": t.get("recast_note"),
        "open_question": t.get("open_question"),
        "explainer_title": t.get("explainer_title"),
        "explainer": t.get("explainer"),
    })
pages.append({
    "kind": "table", "section": "demoted", "slug": "demoted",
    "name": "Cut — 7 that measured nothing",
    "rows": [[t["name"], t["summary"]] for t in demoted],
})

payload = {
    "title": TITLE,
    "intro": INTRO,
    "preamble": [{"label": a, "body": b} for a, b in PREAMBLE],
    "sections": [{"key": k, "title": ti, "blurb": bl} for k, ti, bl, _ in SECTIONS],
    "pages": pages,
}
data_json = (json.dumps(payload, ensure_ascii=False)
             .replace("<", "\\u003c")
             .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))

CSS = r"""
:root{
  color-scheme: light;
  --bg:#f2f4f4; --panel:#ffffff; --panel-2:#e9edee; --sunk:#eaeeee;
  --ink:#14181a; --ink-2:#465055; --ink-3:#6f7c82;
  --rule:#d5dbdc; --rule-soft:#e3e8e9;
  --accent:#0c6e70; --accent-soft:#dbeceb;
  --amber:#8a5a00; --amber-soft:#f5e9d2;
  --rose:#a52a37; --rose-soft:#f7e2e3;
  --mono: ui-monospace, "SF Mono", SFMono-Regular, "Cascadia Mono", Menlo, Consolas, monospace;
  --sans: "Inter var", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    color-scheme: dark;
    --bg:#0e1113; --panel:#161a1c; --panel-2:#1d2325; --sunk:#111517;
    --ink:#e7edef; --ink-2:#a6b2b6; --ink-3:#77848a;
    --rule:#272f32; --rule-soft:#1f2629;
    --accent:#4ecdc9; --accent-soft:#123033;
    --amber:#e2a63c; --amber-soft:#2e2513;
    --rose:#ff9095; --rose-soft:#331a1d;
  }
}
:root[data-theme="dark"]{
  color-scheme: dark;
  --bg:#0e1113; --panel:#161a1c; --panel-2:#1d2325; --sunk:#111517;
  --ink:#e7edef; --ink-2:#a6b2b6; --ink-3:#77848a;
  --rule:#272f32; --rule-soft:#1f2629;
  --accent:#4ecdc9; --accent-soft:#123033;
  --amber:#e2a63c; --amber-soft:#2e2513;
  --rose:#ff9095; --rose-soft:#331a1d;
}

*{box-sizing:border-box}
html,body{height:100%}
body{
  margin:0; background:var(--bg); color:var(--ink); font-family:var(--sans);
  font-size:15px; line-height:1.5; -webkit-font-smoothing:antialiased;
}
a{color:var(--accent)}
:focus-visible{outline:2px solid var(--accent); outline-offset:2px; border-radius:2px}

.shell{display:grid; grid-template-columns:300px minmax(0,1fr); height:100vh}
.rail{border-right:1px solid var(--rule); background:var(--panel); overflow-y:auto;
      overscroll-behavior:contain; display:flex; flex-direction:column}
.stage{overflow-y:auto; overscroll-behavior:contain; scroll-behavior:smooth}

.brand{padding:20px 20px 16px; border-bottom:1px solid var(--rule); display:flex;
       flex-direction:column; gap:8px}
.brand h1{margin:0; font-size:16px; line-height:1.25; font-weight:640; letter-spacing:-.01em}
.tally{display:flex; gap:6px; flex-wrap:wrap; margin-top:2px}
.tally span{font-family:var(--mono); font-size:10.5px; letter-spacing:.04em;
  text-transform:uppercase; padding:3px 7px; border-radius:3px;
  border:1px solid var(--rule); color:var(--ink-2); background:var(--panel-2)}
.tally .t-ship{color:var(--accent); border-color:var(--accent); background:var(--accent-soft)}
.tally .t-prop{color:var(--amber); border-color:var(--amber); background:var(--amber-soft)}

.idx{padding:10px 10px 32px; display:flex; flex-direction:column; gap:2px}
.grp{margin:14px 0 4px; padding:0 10px; display:flex; align-items:baseline; gap:8px}
.grp .gname{font-family:var(--mono); font-size:10.5px; letter-spacing:.09em;
            text-transform:uppercase; color:var(--ink-3)}
.grp .gcount{font-family:var(--mono); font-size:10.5px; color:var(--ink-3);
             margin-left:auto; font-variant-numeric:tabular-nums}
.grp.g-ship .gname{color:var(--accent)}
.grp.g-prop .gname{color:var(--amber)}

button.item{width:100%; text-align:left; display:grid; grid-template-columns:14px minmax(0,1fr);
  gap:8px; align-items:baseline; padding:6px 10px 7px; border:0; border-radius:5px;
  background:transparent; color:var(--ink-2); font:inherit; cursor:pointer; position:relative}
button.item:hover{background:var(--panel-2); color:var(--ink)}
button.item .glyph{font-size:11px; line-height:1.5; color:var(--ink-3)}
button.item .nm{font-family:var(--mono); font-size:12.5px; line-height:1.45; word-break:break-word}
button.item.on{background:var(--panel-2); color:var(--ink)}
button.item.on::before{content:""; position:absolute; left:0; top:5px; bottom:5px;
  width:2px; border-radius:2px; background:var(--accent)}
button.item.sec-proposed .glyph{color:var(--amber)}
button.item.sec-proposed.on::before{background:var(--amber)}
button.item .icode{color:var(--amber); font-weight:600}

.pane{max-width:860px; margin:0 auto; padding:0 40px 96px}
.taskhead{position:sticky; top:0; z-index:5; background:var(--bg);
  padding:22px 0 14px; border-bottom:1px solid var(--rule);
  display:flex; flex-direction:column; gap:10px}
.eyebrow{font-family:var(--mono); font-size:10.5px; letter-spacing:.09em;
  text-transform:uppercase; color:var(--ink-3); display:flex; align-items:center; gap:10px}
.eyebrow .sec-ship{color:var(--accent)}
.eyebrow .sec-prop{color:var(--amber)}
.titlerow{display:flex; align-items:flex-start; gap:16px; flex-wrap:wrap}
h2.tname{margin:0; font-family:var(--mono); font-size:21px; line-height:1.25; font-weight:600;
  letter-spacing:-.015em; word-break:break-word; flex:1 1 320px; min-width:0}
h2.tname .code{color:var(--amber)}
.nav{display:flex; align-items:center; gap:8px; margin-left:auto}
.nav button{font:inherit; font-family:var(--mono); font-size:12px; padding:5px 11px;
  border-radius:5px; border:1px solid var(--rule); background:var(--panel);
  color:var(--ink-2); cursor:pointer}
.nav button:hover:not(:disabled){border-color:var(--accent); color:var(--accent)}
.nav button:disabled{opacity:.4; cursor:default}
.counter{font-family:var(--mono); font-size:12px; color:var(--ink-3);
  font-variant-numeric:tabular-nums; white-space:nowrap}
.kbd{font-family:var(--mono); font-size:10.5px; color:var(--ink-3);
  border:1px solid var(--rule); border-bottom-width:2px; border-radius:3px; padding:1px 4px}

.body{display:flex; flex-direction:column; gap:20px; padding-top:24px}
.prose{margin:0; color:var(--ink-2); max-width:70ch; line-height:1.62}
.prose strong{color:var(--ink); font-weight:600}
.prose code, .metaline code{font-family:var(--mono); font-size:.9em;
  background:var(--panel-2); border:1px solid var(--rule-soft); border-radius:3px; padding:0 4px}

pre.prompt{margin:0; padding:16px 18px; background:var(--sunk);
  border:1px solid var(--rule-soft); border-left:3px solid var(--accent);
  border-radius:0 6px 6px 0; overflow-x:auto; color:var(--ink);
  font-family:var(--mono); font-size:13.5px; line-height:1.6;
  white-space:pre-wrap; word-wrap:break-word; tab-size:2}
pre.prompt.proposedp{border-left-color:var(--amber)}

.metaline{font-family:var(--mono); font-size:12px; color:var(--ink-3);
  border-top:1px solid var(--rule-soft); border-bottom:1px solid var(--rule-soft);
  padding:8px 0; letter-spacing:.01em}
.hole{border-left:3px solid var(--rose); background:var(--panel);
  border:1px solid var(--rule); border-left:3px solid var(--rose);
  border-radius:0 6px 6px 0; padding:12px 14px; display:flex; flex-direction:column; gap:6px}
.hole .lbl{font-family:var(--mono); font-size:10.5px; letter-spacing:.09em;
  text-transform:uppercase; color:var(--rose)}
.note{border:1px solid var(--rule); border-left:3px solid var(--amber);
  border-radius:0 6px 6px 0; background:var(--panel); padding:12px 14px;
  display:flex; flex-direction:column; gap:6px}
.note .lbl{font-family:var(--mono); font-size:10.5px; letter-spacing:.09em;
  text-transform:uppercase; color:var(--amber)}
.explainer{border:1px solid var(--rule); border-radius:6px; background:var(--panel);
  padding:16px 18px; display:flex; flex-direction:column; gap:12px}
.explainer h3{margin:0; font-size:14px; font-weight:640; color:var(--ink)}

table.demoted{border-collapse:collapse; width:100%; font-size:13.5px}
table.demoted th{text-align:left; font-family:var(--mono); font-size:10.5px;
  letter-spacing:.09em; text-transform:uppercase; color:var(--ink-3);
  border-bottom:1px solid var(--rule); padding:8px 12px 8px 0; font-weight:500}
table.demoted td{border-bottom:1px solid var(--rule-soft); padding:10px 12px 10px 0;
  color:var(--ink-2); vertical-align:top}
table.demoted td.nm{font-family:var(--mono); color:var(--ink); white-space:nowrap}
table.demoted td.n{font-family:var(--mono); white-space:nowrap;
  font-variant-numeric:tabular-nums}

.readme{display:flex; flex-direction:column; gap:14px; padding:26px 0 0;
  border-bottom:1px solid var(--rule); margin-bottom:6px}
.readme h2{margin:0; font-size:13px; font-family:var(--mono); letter-spacing:.09em;
  text-transform:uppercase; color:var(--ink-3); font-weight:500}

footer.pagefoot{margin-top:36px; padding-top:18px; border-top:1px solid var(--rule);
  display:flex; gap:14px; align-items:center; flex-wrap:wrap;
  font-size:12.5px; color:var(--ink-3)}

@media (prefers-reduced-motion: reduce){
  *{animation:none !important; transition:none !important; scroll-behavior:auto !important}
}
@media (max-width: 900px){
  .shell{grid-template-columns:1fr; height:auto; min-height:100vh}
  .rail{border-right:0; border-bottom:1px solid var(--rule); max-height:42vh;
        position:sticky; top:0; z-index:20}
  .pane{padding:0 20px 72px}
  .taskhead{position:static}
  h2.tname{font-size:18px}
}
"""

JS = r"""
(function(){
  var DATA = JSON.parse(document.getElementById("suite-data").textContent);
  var pages = DATA.pages;
  var cur = 0;

  var SEC = {
    shipping: {label:"Shipping now", cls:"sec-ship"},
    proposed: {label:"Proposed \u2014 design stage", cls:"sec-prop"},
    demoted:  {label:"Cut \u2014 measured nothing", cls:"sec-dem"}
  };

  function el(tag, cls, text){
    var n = document.createElement(tag);
    if(cls) n.className = cls;
    if(text !== undefined && text !== null) n.textContent = text;
    return n;
  }

  /* `code` and **bold** become elements; everything else stays literal text. */
  function rich(node, text){
    var re = /`([^`]+)`|\*\*([^*]+)\*\*/g, last = 0, m;
    while((m = re.exec(text)) !== null){
      if(m.index > last) node.appendChild(document.createTextNode(text.slice(last, m.index)));
      node.appendChild(el(m[1] !== undefined ? "code" : "strong", null,
                          m[1] !== undefined ? m[1] : m[2]));
      last = re.lastIndex;
    }
    if(last < text.length) node.appendChild(document.createTextNode(text.slice(last)));
    return node;
  }
  function prose(text){ return rich(el("p","prose"), text); }

  /* ---------------- index ---------------- */
  var idx = document.getElementById("idx"), buttons = [];

  function itemButton(t, i){
    var b = el("button","item sec-" + t.section);
    b.type = "button";
    b.setAttribute("data-i", String(i));
    b.appendChild(el("span","glyph", t.kind === "built" ? "\u25c9"
                                   : t.kind === "proposed" ? "\u25cb" : "\u25a4"));
    var nm = el("span","nm");
    if(t.kind === "proposed"){
      nm.appendChild(el("span","icode", t.code));
      nm.appendChild(document.createTextNode(" " + t.headline));
    } else {
      nm.textContent = t.name;
    }
    b.appendChild(nm);
    b.addEventListener("click", function(){ go(i); });
    buttons.push(b);
    return b;
  }
  function groupHead(cls, name, count){
    var h = el("div","grp " + cls);
    h.appendChild(el("span","gname", name));
    h.appendChild(el("span","gcount", String(count)));
    return h;
  }

  var bySec = {shipping:[], proposed:[], demoted:[]};
  pages.forEach(function(t,i){ bySec[t.section].push(i); });

  idx.appendChild(groupHead("g-ship","Shipping now", bySec.shipping.length));
  bySec.shipping.forEach(function(i){ idx.appendChild(itemButton(pages[i], i)); });
  idx.appendChild(groupHead("g-prop","Proposed \u00b7 none built", bySec.proposed.length));
  bySec.proposed.forEach(function(i){ idx.appendChild(itemButton(pages[i], i)); });
  idx.appendChild(groupHead("g-dem","Demoted", 7));
  bySec.demoted.forEach(function(i){ idx.appendChild(itemButton(pages[i], i)); });

  /* ---------------- stage ---------------- */
  var head = document.getElementById("taskhead");
  var body = document.getElementById("taskbody");
  var prevBtn = el("button", null, "\u2190 prev");
  prevBtn.type = "button"; prevBtn.id = "prev"; prevBtn.setAttribute("aria-label","Previous");
  var nextBtn = el("button", null, "next \u2192");
  nextBtn.type = "button"; nextBtn.id = "next"; nextBtn.setAttribute("aria-label","Next");

  function sectionBlurb(key){
    for(var i = 0; i < DATA.sections.length; i++){
      if(DATA.sections[i].key === key) return DATA.sections[i].blurb;
    }
    return "";
  }

  function renderHead(t, i){
    head.textContent = "";
    var eb = el("div","eyebrow");
    eb.appendChild(el("span", SEC[t.section].cls, SEC[t.section].label));
    head.appendChild(eb);

    var row = el("div","titlerow");
    var h2 = el("h2","tname");
    if(t.kind === "proposed"){
      h2.appendChild(el("span","code", t.code + " \u2014"));
      h2.appendChild(document.createTextNode(" " + t.headline));
    } else {
      h2.textContent = t.name;
    }
    row.appendChild(h2);

    var nav = el("div","nav");
    nav.appendChild(prevBtn);
    nav.appendChild(el("span","counter", (i+1) + " / " + pages.length));
    nav.appendChild(nextBtn);
    row.appendChild(nav);
    head.appendChild(row);
  }

  function metaLine(text){
    var d = el("div","metaline");
    d.textContent = text;
    return d;
  }
  function callout(cls, label, text){
    var d = el("div", cls);
    d.appendChild(el("div","lbl", label));
    d.appendChild(prose(text));
    return d;
  }

  function renderTask(t){
    var pre = el("pre","prompt" + (t.kind === "proposed" ? " proposedp" : ""));
    pre.textContent = t.prompt;
    body.appendChild(pre);

    if(t.recast) body.appendChild(callout("note","Recast", t.recast));
    body.appendChild(prose(t.grading));
    body.appendChild(metaLine(t.meta));
    if(t.hole) body.appendChild(callout("hole","Known hole", t.hole));
    if(t.open_question) body.appendChild(callout("note","Open question", t.open_question));
    if(t.explainer){
      var box = el("div","explainer");
      box.appendChild(el("h3", null, t.explainer_title));
      t.explainer.forEach(function(p){ box.appendChild(prose(p)); });
      body.appendChild(box);
    }
  }

  function renderTable(t){
    var tbl = el("table","demoted");
    var thead = el("thead"), tr = el("tr");
    ["task","what it asked"].forEach(function(h){ tr.appendChild(el("th", null, h)); });
    thead.appendChild(tr); tbl.appendChild(thead);
    var tb = el("tbody");
    t.rows.forEach(function(r){
      var row = el("tr");
      row.appendChild(el("td","nm", r[0]));
      row.appendChild(rich(el("td"), r[1]));
      tb.appendChild(row);
    });
    tbl.appendChild(tb);
    body.appendChild(tbl);
    body.appendChild(prose("Grading summaries and known holes for these seven are kept in "
      + "`docs/suite_review_data_built.json` rather than reproduced here; the task "
      + "directories themselves are recoverable at commit `73854f0b`, the last "
      + "commit before the cut."));
  }

  function render(){
    var t = pages[cur];
    renderHead(t, cur);
    body.textContent = "";

    /* The section blurb belongs to the section, not to the task, so it appears
       once - on the first page of its section - rather than on all fourteen. */
    if(cur === 0 || pages[cur - 1].section !== t.section){
      var intro = el("div","readme");
      intro.appendChild(prose(sectionBlurb(t.section)));
      body.appendChild(intro);
    }

    if(t.kind === "table") renderTable(t); else renderTask(t);

    buttons.forEach(function(b){
      b.classList.toggle("on", Number(b.getAttribute("data-i")) === cur);
    });
    prevBtn.disabled = cur === 0;
    nextBtn.disabled = cur === pages.length - 1;
    document.getElementById("stage").scrollTop = 0;
    var on = buttons[cur];
    if(on){
      var rail = document.querySelector(".rail");
      var rb = rail.getBoundingClientRect(), bb = on.getBoundingClientRect();
      if(bb.top < rb.top + 4 || bb.bottom > rb.bottom - 4){
        rail.scrollTop += (bb.top - rb.top) - (rb.height / 2) + (bb.height / 2);
      }
    }
  }

  function go(i, skipHash){
    if(i < 0 || i >= pages.length) return;
    cur = i;
    if(!skipHash){
      var h = "#" + pages[i].slug;
      if(location.hash !== h) history.replaceState(null, "", h);
    }
    render();
  }

  prevBtn.addEventListener("click", function(){ go(cur - 1); });
  nextBtn.addEventListener("click", function(){ go(cur + 1); });

  document.addEventListener("keydown", function(e){
    if(e.metaKey || e.ctrlKey || e.altKey) return;
    var tag = (e.target && e.target.tagName || "").toLowerCase();
    if(tag === "input" || tag === "textarea" || (e.target && e.target.isContentEditable)) return;
    if(e.key === "ArrowRight" || e.key === "j"){ e.preventDefault(); go(cur + 1); }
    else if(e.key === "ArrowLeft" || e.key === "k"){ e.preventDefault(); go(cur - 1); }
    else if(e.key === "Home"){ e.preventDefault(); go(0); }
    else if(e.key === "End"){ e.preventDefault(); go(pages.length - 1); }
  });

  window.addEventListener("hashchange", function(){ fromHash(); });

  function fromHash(){
    var h = (location.hash || "").replace(/^#/, "").toLowerCase();
    if(!h) return false;
    for(var i = 0; i < pages.length; i++){
      if(pages[i].slug === h){ go(i, true); return true; }
    }
    return false;
  }

  /* the shared preamble, rendered once into the rail-adjacent header */
  var pre = document.getElementById("preamble");
  DATA.preamble.forEach(function(p){
    var d = el("details");
    var s = el("summary", null, p.label);
    d.appendChild(s);
    d.appendChild(prose(p.body));
    pre.appendChild(d);
  });

  if(!fromHash()) render();
})();
"""

PREAMBLE_CSS = r"""
#preamble{padding:12px 14px 18px; border-bottom:1px solid var(--rule);
  display:flex; flex-direction:column; gap:6px}
#preamble details{border:1px solid var(--rule-soft); border-radius:5px; background:var(--panel-2)}
#preamble summary{cursor:pointer; padding:6px 10px; font-family:var(--mono);
  font-size:11px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-2)}
#preamble details[open] summary{color:var(--accent)}
#preamble .prose{padding:0 10px 10px; font-size:12.5px; line-height:1.55}
"""

html = f"""<title>{TITLE}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{CSS}{PREAMBLE_CSS}</style>

<div class="shell">
  <aside class="rail">
    <div class="brand">
      <h1>{TITLE}</h1>
      <div class="tally">
        <span class="t-ship">14 shipping</span>
        <span class="t-prop">9 proposed</span>
        <span>7 cut</span>
      </div>
    </div>
    <div id="preamble"></div>
    <nav class="idx" id="idx" aria-label="Task index"></nav>
  </aside>

  <main class="stage" id="stage">
    <div class="pane">
      <div class="taskhead" id="taskhead"></div>
      <div class="body" id="taskbody"></div>
      <footer class="pagefoot">
        <span><span class="kbd">\u2190</span> <span class="kbd">\u2192</span> to page</span>
        <span>Deep-linkable: the URL hash tracks the open task.</span>
      </footer>
    </div>
  </main>
</div>

<script id="suite-data" type="application/json">{data_json}</script>
<script>{JS}</script>
"""

out = os.path.join(HERE, "suite_review.html")
open(out, "w").write(html)
print("wrote", out, len(html), "bytes,", len(pages), "pages")
