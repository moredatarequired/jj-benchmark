#!/usr/bin/env python3
"""Regenerate the suite review page.

This is a review aid, not benchmark machinery: nothing in the harness imports
it, and running it touches only the output file named below.

Inputs (both alongside this script, in docs/):
  suite_review_data_built.json     the 21 built tasks - 14 shipping, 7 demoted
                                   to the smoke tier - with prompt and verifier
                                   summary for each
  suite_review_data_proposed.json  the 10 proposed-but-unbuilt tasks, plus the
                                   caveat text rendered above them

Output:
  suite_review.html                one self-contained page, no external assets

Usage:  python3 docs/build_suite_review.py
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
built = json.load(open(os.path.join(HERE, "suite_review_data_built.json")))
proposed_doc = json.load(open(os.path.join(HERE, "suite_review_data_proposed.json")))

built_tasks = built["tasks"]
proposed_tasks = proposed_doc["tasks"]
caveat = proposed_doc["caveat"]

shipping = [t for t in built_tasks if t["keep_tier"] == "shipping_14"]
demoted = [t for t in built_tasks if t["keep_tier"] == "smoke_tier_7"]
assert len(shipping) == 14 and len(demoted) == 7 and len(proposed_tasks) == 10


def slug(name):
    m = re.match(r"^(N\d+)", name)
    if m:
        return m.group(1).lower()
    return re.sub(r"[^a-z0-9_]+", "-", name.lower()).strip("-")


items = []
for t in shipping:
    d = dict(t)
    d["section"] = "shipping"
    d["slug"] = slug(t["name"])
    items.append(d)
for t in proposed_tasks:
    d = dict(t)
    d["section"] = "proposed"
    d["slug"] = slug(t["name"])
    d["struck"] = t["name"].startswith("N10")
    # display name: split the "N1 — rest" label
    parts = re.split(r"\s+—\s+", t["name"], maxsplit=1)
    d["code"] = parts[0]
    d["headline"] = parts[1] if len(parts) > 1 else ""
    items.append(d)
for t in demoted:
    d = dict(t)
    d["section"] = "demoted"
    d["slug"] = slug(t["name"])
    items.append(d)

payload = {"caveat": caveat, "items": items}
data_json = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")

CSS = r"""
:root{
  color-scheme: light;
  --bg:#f2f4f4;
  --panel:#ffffff;
  --panel-2:#e9edee;
  --sunk:#eaeeee;
  --ink:#14181a;
  --ink-2:#465055;
  --ink-3:#6f7c82;
  --rule:#d5dbdc;
  --rule-soft:#e3e8e9;
  --accent:#0c6e70;
  --accent-soft:#dbeceb;
  --amber:#8a5a00;
  --amber-soft:#f5e9d2;
  --rose:#a52a37;
  --rose-soft:#f7e2e3;
  --violet:#5f46a0;
  --violet-soft:#e9e3f7;
  --shadow:0 1px 0 rgba(20,24,26,.05), 0 8px 24px -18px rgba(20,24,26,.5);
  --mono: ui-monospace, "SF Mono", SFMono-Regular, "Cascadia Mono", "JetBrains Mono", Menlo, Consolas, "Liberation Mono", monospace;
  --sans: "Inter var", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    color-scheme: dark;
    --bg:#0e1113;
    --panel:#161a1c;
    --panel-2:#1d2325;
    --sunk:#111517;
    --ink:#e7edef;
    --ink-2:#a6b2b6;
    --ink-3:#77848a;
    --rule:#272f32;
    --rule-soft:#1f2629;
    --accent:#4ecdc9;
    --accent-soft:#123033;
    --amber:#e2a63c;
    --amber-soft:#2e2513;
    --rose:#ff9095;
    --rose-soft:#331a1d;
    --violet:#b6a0f2;
    --violet-soft:#221d33;
    --shadow:0 1px 0 rgba(0,0,0,.35), 0 10px 30px -22px #000;
  }
}
:root[data-theme="dark"]{
  color-scheme: dark;
  --bg:#0e1113;
  --panel:#161a1c;
  --panel-2:#1d2325;
  --sunk:#111517;
  --ink:#e7edef;
  --ink-2:#a6b2b6;
  --ink-3:#77848a;
  --rule:#272f32;
  --rule-soft:#1f2629;
  --accent:#4ecdc9;
  --accent-soft:#123033;
  --amber:#e2a63c;
  --amber-soft:#2e2513;
  --rose:#ff9095;
  --rose-soft:#331a1d;
  --violet:#b6a0f2;
  --violet-soft:#221d33;
  --shadow:0 1px 0 rgba(0,0,0,.35), 0 10px 30px -22px #000;
}

*{box-sizing:border-box}
html,body{height:100%}
body{
  margin:0;
  background:var(--bg);
  color:var(--ink);
  font-family:var(--sans);
  font-size:15px;
  line-height:1.5;
  -webkit-font-smoothing:antialiased;
}
a{color:var(--accent)}
:focus-visible{outline:2px solid var(--accent); outline-offset:2px; border-radius:2px}

/* ---------- shell ---------- */
.shell{display:grid; grid-template-columns:312px minmax(0,1fr); height:100vh}
.rail{
  border-right:1px solid var(--rule);
  background:var(--panel);
  overflow-y:auto;
  overscroll-behavior:contain;
  display:flex; flex-direction:column;
}
.stage{overflow-y:auto; overscroll-behavior:contain; scroll-behavior:smooth}

/* ---------- rail head ---------- */
.brand{padding:20px 20px 16px; border-bottom:1px solid var(--rule); display:flex; flex-direction:column; gap:8px}
.brand h1{
  margin:0; font-size:16px; line-height:1.25; font-weight:640; letter-spacing:-.01em; text-wrap:balance;
}
.brand .sub{margin:0; font-size:12.5px; color:var(--ink-3); line-height:1.45}
.tally{display:flex; gap:6px; flex-wrap:wrap; margin-top:2px}
.tally span{
  font-family:var(--mono); font-size:10.5px; letter-spacing:.04em; text-transform:uppercase;
  padding:3px 7px; border-radius:3px; border:1px solid var(--rule); color:var(--ink-2); background:var(--panel-2);
}
.tally .t-ship{color:var(--accent); border-color:var(--accent); background:var(--accent-soft)}
.tally .t-prop{color:var(--amber); border-color:var(--amber); background:var(--amber-soft)}

/* ---------- index ---------- */
.idx{padding:10px 10px 32px; display:flex; flex-direction:column; gap:2px}
.grp{margin:14px 0 4px; padding:0 10px; display:flex; align-items:baseline; gap:8px}
.grp .gname{
  font-family:var(--mono); font-size:10.5px; letter-spacing:.09em; text-transform:uppercase; color:var(--ink-3);
}
.grp .gcount{font-family:var(--mono); font-size:10.5px; color:var(--ink-3); margin-left:auto; font-variant-numeric:tabular-nums}
.grp.g-ship .gname{color:var(--accent)}
.grp.g-prop .gname{color:var(--amber)}
details.demoted-wrap{margin-top:14px}
details.demoted-wrap>summary{
  list-style:none; cursor:pointer; padding:4px 10px; display:flex; align-items:center; gap:8px;
  font-family:var(--mono); font-size:10.5px; letter-spacing:.09em; text-transform:uppercase; color:var(--ink-3);
  border-radius:4px;
}
details.demoted-wrap>summary::-webkit-details-marker{display:none}
details.demoted-wrap>summary:hover{background:var(--panel-2); color:var(--ink-2)}
details.demoted-wrap>summary .chev{transition:transform .15s ease; display:inline-block; font-size:9px}
details.demoted-wrap[open]>summary .chev{transform:rotate(90deg)}
details.demoted-wrap>summary .gcount{margin-left:auto; font-variant-numeric:tabular-nums}

button.item{
  width:100%; text-align:left; display:grid; grid-template-columns:14px minmax(0,1fr); gap:8px; align-items:baseline;
  padding:6px 10px 7px; border:0; border-radius:5px; background:transparent; color:var(--ink-2);
  font:inherit; cursor:pointer; position:relative;
}
button.item:hover{background:var(--panel-2); color:var(--ink)}
button.item .glyph{font-size:11px; line-height:1.5; color:var(--ink-3)}
button.item .nm{font-family:var(--mono); font-size:12.5px; line-height:1.45; word-break:break-word}
button.item .tag{
  display:block; font-size:11px; color:var(--ink-3); margin-top:2px; line-height:1.35;
}
button.item.on{background:var(--panel-2); color:var(--ink)}
button.item.on::before{
  content:""; position:absolute; left:0; top:5px; bottom:5px; width:2px; border-radius:2px; background:var(--accent);
}
button.item.sec-proposed .glyph{color:var(--amber)}
button.item.sec-proposed.on::before{background:var(--amber)}
button.item .icode{color:var(--amber); font-weight:600}
button.item.is-struck .icode{color:var(--rose)}
button.item.is-struck .nm{text-decoration:line-through; text-decoration-thickness:1px}
button.item.is-struck .glyph{color:var(--rose)}
button.item.is-struck.on::before{background:var(--rose)}
button.item .dots{display:inline-flex; gap:4px; margin-left:6px; vertical-align:middle}
button.item .dot{width:5px; height:5px; border-radius:50%; display:inline-block}
.dot-prov{background:var(--violet)}
.dot-terse{background:var(--accent)}

/* ---------- stage ---------- */
.pane{max-width:900px; margin:0 auto; padding:0 40px 96px}

.taskhead{
  position:sticky; top:0; z-index:5; background:var(--bg);
  padding:22px 0 14px; border-bottom:1px solid var(--rule);
  display:flex; flex-direction:column; gap:10px;
}
.eyebrow{
  font-family:var(--mono); font-size:10.5px; letter-spacing:.09em; text-transform:uppercase; color:var(--ink-3);
  display:flex; align-items:center; gap:10px;
}
.eyebrow .sec-ship{color:var(--accent)}
.eyebrow .sec-prop{color:var(--amber)}
.eyebrow .sec-dem{color:var(--ink-3)}
.titlerow{display:flex; align-items:flex-start; gap:16px; flex-wrap:wrap}
h2.tname{
  margin:0; font-family:var(--mono); font-size:22px; line-height:1.2; font-weight:600; letter-spacing:-.015em;
  word-break:break-word; flex:1 1 320px; min-width:0;
}
h2.tname.struck{text-decoration:line-through; text-decoration-thickness:1.5px; color:var(--rose)}
h2.tname .code{color:var(--amber)}
h2.tname.struck .code{color:var(--rose)}
.subhead{font-family:var(--sans); font-size:15px; color:var(--ink-2); margin:-2px 0 0; font-weight:400; line-height:1.4}
.chips{display:flex; gap:6px; flex-wrap:wrap; align-items:center}
.chip{
  font-family:var(--mono); font-size:10.5px; letter-spacing:.05em; text-transform:uppercase;
  padding:3px 8px; border-radius:3px; border:1px solid; white-space:nowrap;
}
.chip-built{color:var(--accent); border-color:var(--accent); background:var(--accent-soft)}
.chip-proposed{color:var(--amber); border-color:var(--amber); background:var(--amber-soft)}
.chip-prov{color:var(--violet); border-color:var(--violet); background:var(--violet-soft)}
.chip-struck{color:var(--rose); border-color:var(--rose); background:var(--rose-soft)}
.chip-quiet{color:var(--ink-3); border-color:var(--rule); background:var(--panel-2)}

.nav{display:flex; align-items:center; gap:8px; margin-left:auto}
.nav button{
  font:inherit; font-family:var(--mono); font-size:12px; padding:5px 11px; border-radius:5px;
  border:1px solid var(--rule); background:var(--panel); color:var(--ink-2); cursor:pointer;
}
.nav button:hover:not(:disabled){border-color:var(--accent); color:var(--accent)}
.nav button:disabled{opacity:.4; cursor:default}
.counter{font-family:var(--mono); font-size:12px; color:var(--ink-3); font-variant-numeric:tabular-nums; white-space:nowrap}
.kbd{font-family:var(--mono); font-size:10.5px; color:var(--ink-3); border:1px solid var(--rule); border-bottom-width:2px; border-radius:3px; padding:1px 4px}

/* ---------- body blocks ---------- */
.body{display:flex; flex-direction:column; gap:26px; padding-top:26px}
.blk{display:flex; flex-direction:column; gap:10px}
.blabel{
  font-family:var(--mono); font-size:10.5px; letter-spacing:.09em; text-transform:uppercase; color:var(--ink-3);
  display:flex; align-items:center; gap:10px; flex-wrap:wrap;
}
.blabel .flag{
  text-transform:none; letter-spacing:0; font-size:11px; padding:2px 7px; border-radius:3px; border:1px solid;
}
.flag-amber{color:var(--amber); border-color:var(--amber); background:var(--amber-soft)}
.flag-accent{color:var(--accent); border-color:var(--accent); background:var(--accent-soft)}
.flag-quiet{color:var(--ink-3); border-color:var(--rule); background:var(--panel-2)}
.prose{margin:0; color:var(--ink-2); max-width:68ch; line-height:1.62}
.prose strong{color:var(--ink); font-weight:600}

pre.prompt{
  margin:0; padding:18px 20px; background:var(--sunk); border:1px solid var(--rule-soft); border-left:3px solid var(--accent);
  border-radius:0 6px 6px 0; overflow-x:auto; color:var(--ink);
  font-family:var(--mono); font-size:13px; line-height:1.62; white-space:pre-wrap; word-wrap:break-word; tab-size:2;
}
pre.prompt.terse{border-left-color:var(--violet); background:var(--panel-2)}
pre.prompt.proposedp{border-left-color:var(--amber)}
.prompt-pair{display:flex; flex-direction:column; gap:18px}

.meta{
  display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:1px;
  background:var(--rule-soft); border:1px solid var(--rule-soft); border-radius:6px; overflow:hidden;
}
.meta .cell{background:var(--panel); padding:12px 14px; display:flex; flex-direction:column; gap:4px}
.meta .k{font-family:var(--mono); font-size:10px; letter-spacing:.08em; text-transform:uppercase; color:var(--ink-3)}
.meta .v{font-family:var(--mono); font-size:15px; color:var(--ink); font-variant-numeric:tabular-nums; line-height:1.3}
.meta .v.no{color:var(--ink-3)}
.meta .v.yes{color:var(--accent)}
.meta .v.warn{color:var(--amber)}

ul.floored{margin:0; padding-left:0; list-style:none; display:flex; flex-direction:column; gap:4px}
ul.floored li{font-family:var(--mono); font-size:12px; color:var(--ink-2); display:flex; gap:8px}
ul.floored li::before{content:"⌞"; color:var(--ink-3)}

.callout{
  border:1px solid var(--rule); border-left:3px solid var(--ink-3); border-radius:0 6px 6px 0;
  background:var(--panel); padding:14px 16px; display:flex; flex-direction:column; gap:8px;
}
.callout.holes{border-left-color:var(--rose)}
.callout.holes .blabel{color:var(--rose)}
.callout.verify{border-left-color:var(--amber)}
.callout.verify .blabel{color:var(--amber)}
.callout.struck{border-left-color:var(--rose); background:var(--rose-soft)}
.callout.stage-note{border-left-color:var(--amber); background:var(--amber-soft)}
.callout .prose{color:var(--ink-2)}
.callout.struck .prose, .callout.stage-note .prose{color:var(--ink)}

code, .mono{font-family:var(--mono); font-size:.92em}
.prose code{background:var(--panel-2); border:1px solid var(--rule-soft); border-radius:3px; padding:0 4px}

.sectionmark{
  display:flex; flex-direction:column; gap:6px; padding:22px 0 0;
}
footer.pagefoot{
  margin-top:36px; padding-top:18px; border-top:1px solid var(--rule);
  display:flex; gap:14px; align-items:center; flex-wrap:wrap;
  font-size:12.5px; color:var(--ink-3);
}

@media (prefers-reduced-motion: reduce){
  *{animation:none !important; transition:none !important; scroll-behavior:auto !important}
}

@media (max-width: 900px){
  .shell{grid-template-columns:1fr; height:auto; min-height:100vh}
  .rail{border-right:0; border-bottom:1px solid var(--rule); max-height:44vh; position:sticky; top:0; z-index:20}
  .pane{padding:0 20px 72px}
  .taskhead{position:static}
  h2.tname{font-size:19px}
}
"""

JS = r"""
(function(){
  var DATA = JSON.parse(document.getElementById("suite-data").textContent);
  var items = DATA.items;
  var cur = 0;

  var SECTIONS = {
    shipping: {label:"Shipping now", cls:"sec-ship"},
    proposed: {label:"Proposed \u2014 design stage", cls:"sec-prop"},
    demoted:  {label:"Demoted \u2014 kept, not shipping", cls:"sec-dem"}
  };

  function el(tag, cls, text){
    var n = document.createElement(tag);
    if(cls) n.className = cls;
    if(text !== undefined && text !== null) n.textContent = text;
    return n;
  }
  function blk(label, flags){
    var s = el("section","blk");
    var l = el("div","blabel");
    l.appendChild(document.createTextNode(label));
    (flags||[]).forEach(function(f){
      var b = el("span","flag " + (f.cls||"flag-quiet"), f.text);
      l.appendChild(b);
    });
    s.appendChild(l);
    return s;
  }
  function prose(text){ return el("p","prose", text); }

  /* ---------------- index ---------------- */
  var idx = document.getElementById("idx");
  var buttons = [];

  function itemButton(t, i){
    var b = el("button","item sec-" + t.section);
    b.type = "button";
    if(t.struck) b.className += " is-struck";
    b.setAttribute("data-i", String(i));
    var g = el("span","glyph", t.struck ? "\u00d7" : (t.status === "built" ? "\u25c9" : "\u25cb"));
    b.appendChild(g);
    var wrap = el("span");
    var nm = el("span","nm");
    if(t.status === "built"){
      nm.textContent = t.name;
    } else {
      nm.appendChild(el("span","icode", t.code));
      nm.appendChild(document.createTextNode(" " + t.headline));
    }
    wrap.appendChild(nm);
    var dots = el("span","dots");
    if(t.provisional){ var d1 = el("span","dot dot-prov"); d1.title = "provisional"; dots.appendChild(d1); }
    if(t.prompt_terse_verbatim){ var d2 = el("span","dot dot-terse"); d2.title = "has rewritten one-liner"; dots.appendChild(d2); }
    if(dots.childNodes.length) nm.appendChild(dots);
    b.appendChild(wrap);
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

  var shipIdx = [], propIdx = [], demIdx = [];
  items.forEach(function(t,i){
    (t.section === "shipping" ? shipIdx : t.section === "proposed" ? propIdx : demIdx).push(i);
  });

  idx.appendChild(groupHead("g-ship","Shipping now", shipIdx.length));
  shipIdx.forEach(function(i){ idx.appendChild(itemButton(items[i], i)); });
  idx.appendChild(groupHead("g-prop","Proposed \u00b7 none built", propIdx.length));
  propIdx.forEach(function(i){ idx.appendChild(itemButton(items[i], i)); });

  var det = document.createElement("details");
  det.className = "demoted-wrap";
  var sum = document.createElement("summary");
  sum.appendChild(el("span","chev","\u25b6"));
  sum.appendChild(el("span",null,"Demoted \u00b7 smoke tier"));
  sum.appendChild(el("span","gcount", String(demIdx.length)));
  det.appendChild(sum);
  var demBox = el("div");
  demIdx.forEach(function(i){ demBox.appendChild(itemButton(items[i], i)); });
  det.appendChild(demBox);
  idx.appendChild(det);

  /* ---------------- stage ---------------- */
  var head = document.getElementById("taskhead");
  var body = document.getElementById("taskbody");
  var prevBtn = el("button", null, "← prev");
  prevBtn.type = "button"; prevBtn.id = "prev"; prevBtn.setAttribute("aria-label","Previous task");
  var nextBtn = el("button", null, "next →");
  nextBtn.type = "button"; nextBtn.id = "next"; nextBtn.setAttribute("aria-label","Next task");

  function renderHead(t, i){
    head.textContent = "";
    var eb = el("div","eyebrow");
    eb.appendChild(el("span", SECTIONS[t.section].cls, SECTIONS[t.section].label));
    if(t.section === "shipping") eb.appendChild(el("span",null,"14 built tasks"));
    if(t.section === "proposed") eb.appendChild(el("span",null,"10 new tasks, none built"));
    if(t.section === "demoted") eb.appendChild(el("span",null,"7 kept, secondary"));
    head.appendChild(eb);

    var row = el("div","titlerow");
    var h2 = el("h2","tname" + (t.struck ? " struck" : ""));
    if(t.status === "proposed"){
      h2.appendChild(el("span","code", t.code + " —"));
      h2.appendChild(document.createTextNode(" " + t.headline));
    } else {
      h2.textContent = t.name;
    }
    row.appendChild(h2);

    var nav = el("div","nav");
    nav.appendChild(prevBtn);
    nav.appendChild(el("span","counter", (i+1) + " / " + items.length));
    nav.appendChild(nextBtn);
    row.appendChild(nav);
    head.appendChild(row);

    var chips = el("div","chips");
    if(t.status === "built"){
      chips.appendChild(el("span","chip chip-built","built"));
      if(t.provisional) chips.appendChild(el("span","chip chip-prov","provisional"));
    } else {
      chips.appendChild(el("span","chip chip-proposed","proposed"));
      if(t.struck) chips.appendChild(el("span","chip chip-struck","struck \u00b7 slot unassigned"));
    }
    if(t.prompt_terse_verbatim) chips.appendChild(el("span","chip chip-quiet","prompt rewritten"));
    if(t.status === "built" && !t.prompt_terse_verbatim) chips.appendChild(el("span","chip chip-quiet","rewrite pending"));
    if(t.status === "built") chips.appendChild(el("span","chip chip-quiet","separated models: " + (t.separated_models ? "yes" : "no")));
    head.appendChild(chips);
  }

  function renderBuilt(t){
    /* prompt */
    var hasTerse = !!t.prompt_terse_verbatim;
    var s = blk(hasTerse ? "The prompt \u00b7 two versions, verbatim"
                         : "The prompt, verbatim \u00b7 instruction.md",
                hasTerse ? [] : [{text:"still spec-style \u2014 rewrite pending", cls:"flag-quiet"}]);
    var pair = el("div","prompt-pair");

    var c1 = el("div","blk");
    if(hasTerse){
      var l1 = el("div","blabel");
      l1.appendChild(document.createTextNode("Current \u2014 instruction.md"));
      l1.appendChild(el("span","flag flag-quiet","spec-style"));
      c1.appendChild(l1);
    }
    var p1 = el("pre","prompt");
    p1.textContent = t.prompt_verbatim;
    c1.appendChild(p1);
    pair.appendChild(c1);

    if(hasTerse){
      var c2 = el("div","blk");
      var l2 = el("div","blabel");
      l2.appendChild(document.createTextNode("Rewritten \u2014 one-line, user voice"));
      l2.appendChild(el("span","flag flag-accent","arm: " + t.terse_arm));
      c2.appendChild(l2);
      var p2 = el("pre","prompt terse");
      p2.textContent = t.prompt_terse_verbatim;
      c2.appendChild(p2);
      pair.appendChild(c2);
    }
    s.appendChild(pair);
    body.appendChild(s);

    /* grading */
    var g = blk("How success is graded");
    g.appendChild(prose(t.grading));
    body.appendChild(g);

    /* scoring */
    var sc = blk("Scoring");
    var m = el("div","meta");
    [["tests total", String(t.tests_total), ""],
     ["floored", String(t.tests_floored), t.tests_floored ? "warn" : "no"],
     ["scored", String(t.tests_scored), "yes"],
     ["anchored", t.anchored ? "yes" : "no", t.anchored ? "yes" : "warn"],
     ["anchor exemptions", t.anchor_exemptions ? "yes" : "none", t.anchor_exemptions ? "" : "no"]
    ].forEach(function(kv){
      var c = el("div","cell");
      c.appendChild(el("div","k", kv[0]));
      c.appendChild(el("div","v " + kv[2], kv[1]));
      m.appendChild(c);
    });
    sc.appendChild(m);
    sc.appendChild(prose(t.scoring));
    if(t.floored_test_names && t.floored_test_names.length){
      var fl = el("div","blabel");
      fl.textContent = "Floored \u2014 must pass, earns nothing";
      sc.appendChild(fl);
      var ul = el("ul","floored");
      t.floored_test_names.forEach(function(n){ ul.appendChild(el("li", null, n)); });
      sc.appendChild(ul);
    }
    body.appendChild(sc);

    /* weaknesses */
    var w = el("div","callout holes");
    w.appendChild(el("div","blabel","Known holes"));
    w.appendChild(prose(t.weaknesses === null || t.weaknesses === undefined ? "None recorded." : t.weaknesses));
    body.appendChild(w);

    /* repair */
    var r = el("div","callout");
    r.appendChild(el("div","blabel","Repair queued"));
    r.appendChild(prose(t.repair_needed === null || t.repair_needed === undefined ? "None \u2014 no repair queued against this task." : t.repair_needed));
    body.appendChild(r);
  }

  function renderProposed(t){
    if(t.struck){
      var st = el("div","callout struck");
      st.appendChild(el("div","blabel","Struck by the proposal"));
      st.appendChild(prose("The proposal strikes N10 as a rule violation \u2014 requiring \u2011i is a method constraint and an R3 violation \u2014 and its slot in the target set is unassigned. The proposal's own answer is to fill that slot from the survey's Tier 3 (2.1 split-by-path or 3.3 absorb-into-a-stack cover the salvageable ask). It is shown here rather than hidden because the ask is salvageable; the wording below is a reconstruction, not a design the proposal states."));
      body.appendChild(st);
    } else {
      var ds = el("div","callout stage-note");
      ds.appendChild(el("div","blabel","Design stage \u2014 nothing built"));
      ds.appendChild(prose(DATA.caveat));
      body.appendChild(ds);
    }

    var flags = [t.prompt_is_drafted_by_me
      ? {text:"wording drafted, not fixed", cls:"flag-amber"}
      : {text:"wording as the proposal states it", cls:"flag-quiet"}];
    var s = blk("The proposed prompt", flags);
    var p = el("pre","prompt proposedp");
    p.textContent = t.prompt_proposed;
    s.appendChild(p);
    body.appendChild(s);

    var g = blk("How success would be graded",
      t.grading_is_inferred ? [{text:"grading reconstructed, not stated by the proposal", cls:"flag-amber"}] : []);
    g.appendChild(prose(t.grading));
    body.appendChild(g);

    var sc = el("div","callout");
    sc.appendChild(el("div","blabel","Scoring, anchoring, known holes"));
    sc.appendChild(prose("Not recorded \u2014 no verifier exists, so there is no test count, no floored set, no anchor decision and no measured weaknesses for this task. Risks below are the proposal's, not measurements."));
    body.appendChild(sc);

    [["Capability", t.capability],
     ["Fixture", t.fixture],
     ["What it discriminates", t.discriminates],
     ["Risks", t.risks]].forEach(function(kv){
      var b = blk(kv[0]);
      b.appendChild(prose(kv[1]));
      body.appendChild(b);
    });

    var v = el("div","callout" + (t.needs_verification ? " verify" : ""));
    v.appendChild(el("div","blabel","Needs verification on 0.44"));
    v.appendChild(prose(t.needs_verification === null || t.needs_verification === undefined
      ? "Nothing flagged for 0.44 verification on this task."
      : t.needs_verification));
    body.appendChild(v);
  }

  function render(){
    var t = items[cur];
    renderHead(t, cur);
    body.textContent = "";
    if(t.status === "built") renderBuilt(t); else renderProposed(t);

    buttons.forEach(function(b){
      b.classList.toggle("on", Number(b.getAttribute("data-i")) === cur);
    });
    prevBtn.disabled = cur === 0;
    nextBtn.disabled = cur === items.length - 1;
    document.getElementById("stage").scrollTop = 0;
    if(t.section === "demoted") det.open = true;
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
    if(i < 0 || i >= items.length) return;
    cur = i;
    if(!skipHash){
      var h = "#" + items[i].slug;
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
    else if(e.key === "End"){ e.preventDefault(); go(items.length - 1); }
  });

  window.addEventListener("hashchange", function(){ fromHash(true); });

  function fromHash(){
    var h = (location.hash || "").replace(/^#/, "").toLowerCase();
    if(!h) return false;
    for(var i = 0; i < items.length; i++){
      if(items[i].slug === h){ go(i, true); return true; }
    }
    return false;
  }

  if(!fromHash()) render();
})();
"""

def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

html = f"""<title>The 24-task jj suite</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{CSS}</style>

<div class="shell">
  <aside class="rail">
    <div class="brand">
      <h1>The 24-task jj suite: prompts and grading</h1>
      <p class="sub">Every task, one at a time \u2014 the exact prompt handed to the agent, and precisely how the run is scored.</p>
      <div class="tally">
        <span class="t-ship">14 shipping</span>
        <span class="t-prop">10 proposed</span>
        <span>7 demoted</span>
      </div>
    </div>
    <nav class="idx" id="idx" aria-label="Task index"></nav>
  </aside>

  <main class="stage" id="stage">
    <div class="pane">
      <div class="taskhead" id="taskhead"></div>
      <div class="body" id="taskbody"></div>
      <footer class="pagefoot">
        <span><span class="kbd">\u2190</span> <span class="kbd">\u2192</span> to page</span>
        <span>\u25c9 built \u00b7 \u25cb proposed \u00b7 \u00d7 struck</span>
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
print("wrote", out, len(html), "bytes")
