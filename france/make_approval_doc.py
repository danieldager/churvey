#!/usr/bin/env python3
"""Generate the approval sheet for Gate 1c (119 prepositions) and the proposed
question templates, as a self-contained HTML page.

Generated rather than hand-written so it stays in sync with prepositions.py.
The page exports a JSON patch that feeds straight back into prepositions.py.

  france/make_approval_doc.py  ->  docs/france-approval.html
"""
import json
import re
from pathlib import Path

from prepositions import (DEPARTEMENT_LOC, DEPARTEMENT_PREP,
                          REGION_LOC, REGION_PREP)

# forms longest-first so "de la" wins over "de"
FORMS = ["de l'", "de la", "des ", "du ", "d'", "de "]
LOC_FORMS = ["dans l'", "dans la", "dans les", "dans le", "en ", "à ", "aux "]

TEMPLATES = [
    dict(id="D1", status="built", n=101,
         text="Qui sont les sénateurs {dep_prep} ?",
         example="Qui sont les sénateurs du Nord ?",
         note="101 answer keys, from the Sénat's own live register. 7 départements "
              "elect only one senator, so those use « Qui est le sénateur … ? »."),
    dict(id="D2", status="built", n=101,
         text="Qui sont les députés {dep_prep} ?",
         example="Qui sont les députés de la Gironde ?",
         note="101 answer keys, from the Assemblée nationale's own register."),
    dict(id="S3", status="built", n=101,
         text="Combien y a-t-il de sénateurs {dep_prep} ?",
         example="Combien y a-t-il de sénateurs du Nord ? → 11",
         note="Free — the number was already stored on every D1 answer key. Same "
              "ground truth as D1 but an easier question, so it shows whether a model "
              "knows the count without knowing the names."),
    dict(id="S1", status="built", n=101,
         text="Le siège de sénateur {dep_prep} est-il renouvelé en septembre 2026 ?",
         example="Le siège de sénateur de la Marne est-il renouvelé en septembre 2026 ?",
         note="59 départements yes, 42 no. Half the Senate is renewed on 27 September "
              "2026. Must be retired or rewritten after the vote — the tense changes."),
    dict(id="S2", status="built", n=101,
         text="Combien de sièges de sénateur {dep_prep} seront renouvelés le 27 septembre 2026 ?",
         example="Combien de sièges de sénateur du Nord seront renouvelés… ? → 0",
         note="Phrased this way on purpose. « Combien de sénateurs seront élus … » "
              "would need the section-2 list, which is not approved yet."),
    dict(id="D3", status="built", n=95,
         text="Qui est le président du conseil départemental {dep_prep} ?",
         example="Qui est le président du conseil départemental de la Somme ?",
         note="95 answers. 7 départements have no such body and are not asked. The "
              "Rhône is split: 69 = Nouveau Rhône, 69M = Métropole de Lyon."),
    dict(id="R1", status="built", n=14,
         text="Qui est le président du conseil régional {reg_prep} ?",
         example="Qui est le président du conseil régional d'Occitanie ?",
         note="14 answers. Corsica, Martinique, Guyane and Mayotte have an assembly "
              "rather than a regional council, so they are not asked."),
    dict(id="PR", status="proposed", n=1,
         text="Comment voter par procuration ?",
         example="Comment voter par procuration ?",
         note="National, one question. Genuine and heavily searched. Its answer key is "
              "editorial, not computed — someone has to decide what a correct answer "
              "must contain, so it needs a French elections person, not a script."),
]


def split_form(prep, forms=None):
    for f in (forms or FORMS):
        if prep.startswith(f):
            return f.strip(), prep[len(f):]
    return "", prep


def rows(table, names, kind, forms=None):
    out = []
    for code, prep in sorted(table.items()):
        form, rest = split_form(prep, forms)
        out.append(dict(code=code, kind=kind, name=names[code], prep=prep,
                        form=form, rest=rest))
    return out


def main():
    root = Path(__file__).resolve().parent.parent
    snap = root / "data/fr/raw/2026-08-03"
    deps = {d["code"]: d["nom"] for d in json.loads((snap / "departements.json").read_text(encoding="utf-8"))}
    regs = {r["code"]: r["nom"] for r in json.loads((snap / "regions.json").read_text(encoding="utf-8"))}

    data = rows(DEPARTEMENT_PREP, deps, "departement") + rows(REGION_PREP, regs, "region")
    loc = rows(DEPARTEMENT_LOC, deps, "departement", LOC_FORMS) + \
        rows(REGION_LOC, regs, "region", LOC_FORMS)
    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False)) \
                   .replace("__LOC__", json.dumps(loc, ensure_ascii=False)) \
                   .replace("__TEMPLATES__", json.dumps(TEMPLATES, ensure_ascii=False))
    out = root / "docs/france-approval.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}  ({len(data)} 'de' rows, {len(loc)} locative rows, "
          f"{len(TEMPLATES)} templates)")


TEMPLATE = r"""<title>France — approval sheet</title>
<style>
  :root{
    --paper:#FBF9F4; --surface:#FFFFFF; --line:#E2DCD0; --line-soft:#EFEAE0;
    --ink:#1C2438; --ink-soft:#5A6274; --ink-faint:#8B8F9C;
    --accent:#2F5D8C; --accent-soft:#E8EFF6;
    --ok:#3D7A5A; --ok-soft:#E6F0EA;
    --edit:#A8702A; --edit-soft:#F7EFE2;
    --radius:5px;
    --serif:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif;
    --sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
    --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
  }
  @media (prefers-color-scheme:dark){
    :root{
      --paper:#12151D; --surface:#191D27; --line:#2C3240; --line-soft:#232833;
      --ink:#E6E8EE; --ink-soft:#A5ABBA; --ink-faint:#767D8D;
      --accent:#7FA9D4; --accent-soft:#1E2A3A;
      --ok:#79B894; --ok-soft:#1B2A22;
      --edit:#D2A264; --edit-soft:#2B2318;
    }
  }
  :root[data-theme="dark"]{
    --paper:#12151D; --surface:#191D27; --line:#2C3240; --line-soft:#232833;
    --ink:#E6E8EE; --ink-soft:#A5ABBA; --ink-faint:#767D8D;
    --accent:#7FA9D4; --accent-soft:#1E2A3A;
    --ok:#79B894; --ok-soft:#1B2A22;
    --edit:#D2A264; --edit-soft:#2B2318;
  }
  :root[data-theme="light"]{
    --paper:#FBF9F4; --surface:#FFFFFF; --line:#E2DCD0; --line-soft:#EFEAE0;
    --ink:#1C2438; --ink-soft:#5A6274; --ink-faint:#8B8F9C;
    --accent:#2F5D8C; --accent-soft:#E8EFF6;
    --ok:#3D7A5A; --ok-soft:#E6F0EA;
    --edit:#A8702A; --edit-soft:#F7EFE2;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
       font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
  .wrap{max-width:820px;margin:0 auto;padding:0 20px 96px}
  header{padding:44px 0 22px;border-bottom:1px solid var(--line)}
  .eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;
           color:var(--ink-faint);font-weight:600}
  h1{font-family:var(--serif);font-weight:600;font-size:31px;line-height:1.2;
     margin:8px 0 10px;text-wrap:balance}
  .lede{color:var(--ink-soft);max-width:62ch;margin:0}
  h2{font-family:var(--serif);font-size:22px;font-weight:600;margin:0 0 4px}
  section{padding-top:38px}
  .sec-note{color:var(--ink-soft);max-width:64ch;margin:0 0 18px;font-size:14px}

  /* sticky progress */
  .bar{position:sticky;top:0;z-index:20;background:var(--paper);
       border-bottom:1px solid var(--line);padding:10px 0;margin-top:26px;
       display:flex;gap:14px;align-items:center;flex-wrap:wrap}
  .count{font-family:var(--mono);font-size:13px;font-variant-numeric:tabular-nums;
         color:var(--ink-soft)}
  .count b{color:var(--ink);font-weight:600}
  .track{flex:1;min-width:120px;height:5px;border-radius:99px;background:var(--line-soft);
         overflow:hidden}
  .fill{height:100%;width:0;background:var(--ok);transition:width .2s ease}

  button{font:inherit;cursor:pointer;border-radius:var(--radius);
         border:1px solid var(--line);background:var(--surface);color:var(--ink);
         padding:6px 11px;transition:background .12s,border-color .12s,color .12s}
  button:hover{border-color:var(--accent)}
  button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
  .primary{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
  .primary:hover{filter:brightness(1.08);border-color:var(--accent)}
  .ghost{font-size:13px;padding:5px 10px;color:var(--ink-soft)}

  /* preposition rows */
  .row{display:grid;grid-template-columns:150px 1fr;gap:14px;align-items:start;
       padding:11px 0;border-bottom:1px solid var(--line-soft)}
  .row[data-state="edited"]{background:var(--edit-soft);
       box-shadow:-14px 0 0 var(--edit-soft),14px 0 0 var(--edit-soft)}
  .who{display:flex;flex-direction:column;gap:1px;padding-top:5px}
  .who .nm{font-weight:600;font-size:13.5px;line-height:1.3}
  .who .cd{font-family:var(--mono);font-size:11px;color:var(--ink-faint)}
  .sentence{font-family:var(--serif);font-size:17px;line-height:1.4;margin:0 0 8px}
  .sentence .hl{background:var(--accent-soft);border-radius:3px;padding:0 3px;
                box-decoration-break:clone;-webkit-box-decoration-break:clone}
  .opts{display:flex;gap:5px;flex-wrap:wrap;align-items:center}
  .opt{font-family:var(--serif);font-size:14px;padding:3px 10px;min-width:34px}
  .opt[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);
       color:#fff}
  .row[data-state="edited"] .opt[aria-pressed="true"]{background:var(--edit);
       border-color:var(--edit)}
  .custom{font-family:var(--serif);font-size:14px;padding:4px 9px;width:160px;
          border:1px solid var(--line);border-radius:var(--radius);
          background:var(--surface);color:var(--ink)}
  .custom:focus{outline:2px solid var(--accent);outline-offset:1px}
  .grp{font-size:11px;letter-spacing:.12em;text-transform:uppercase;font-weight:600;
       color:var(--ink-faint);padding:22px 0 6px}

  /* templates */
  .card{border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);
        padding:15px 17px;margin-bottom:11px}
  .card-top{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;margin-bottom:7px}
  .tag{font-family:var(--mono);font-size:11px;font-weight:600;padding:2px 7px;
       border-radius:3px;background:var(--accent-soft);color:var(--accent)}
  .tag.built{background:var(--ok-soft);color:var(--ok)}
  .n{font-family:var(--mono);font-size:11.5px;color:var(--ink-faint);margin-left:auto;
     font-variant-numeric:tabular-nums}
  .q{font-family:var(--serif);font-size:17px;margin:0 0 3px}
  .ex{font-family:var(--serif);font-size:14px;color:var(--ink-soft);margin:0 0 9px}
  .ex::before{content:"ex. "}
  .why{font-size:13.5px;color:var(--ink-soft);margin:0 0 12px;max-width:64ch}
  .choices{display:flex;gap:6px;flex-wrap:wrap}
  .choices button[aria-pressed="true"]{background:var(--ok);border-color:var(--ok);
       color:#fff;font-weight:600}
  .choices button.no[aria-pressed="true"]{background:var(--ink-soft);
       border-color:var(--ink-soft)}
  .note{margin-top:9px;width:100%;font:inherit;font-size:13.5px;padding:7px 9px;
        border:1px solid var(--line);border-radius:var(--radius);resize:vertical;
        min-height:38px;background:var(--paper);color:var(--ink);display:none}
  .note.show{display:block}
  .note:focus{outline:2px solid var(--accent);outline-offset:1px}

  /* export */
  .export{position:sticky;bottom:0;background:var(--paper);
          border-top:1px solid var(--line);padding:13px 0;margin-top:34px;
          display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  .status{font-size:13px;color:var(--ink-soft)}
  .drop{border:1px dashed var(--line);border-radius:var(--radius);padding:13px;
        margin-top:13px;font-family:var(--mono);font-size:11.5px;
        color:var(--ink-faint);white-space:pre-wrap;word-break:break-all;
        max-height:180px;overflow:auto;display:none}
  .drop.show{display:block}
  @media (max-width:640px){
    .row{grid-template-columns:1fr;gap:5px}
    .who{flex-direction:row;gap:8px;align-items:baseline;padding-top:0}
  }
  @media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>

<div class="wrap">
<header>
  <div class="eyebrow">Civic AI Audit · France</div>
  <h1>Three things to approve</h1>
  <p class="lede">Two grammar lists and one set of questions. Both grammar lists are
  pre-filled with my draft, so you only touch what's wrong — or hit "accept all". Then press
  Export and send me the file.</p>
</header>

<section>
  <h2>1. Grammar in the question slots</h2>
  <p class="sec-note">French needs the article and preposition to agree with each place
  name, and no rule derives it — <em>du Nord</em> but <em>de l'Ain</em>, <em>des Landes</em>
  but <em>de la Somme</em>. Every question we ask is built from this list, so an error here
  makes that question unusable. Each row shows my draft selected. Change the ones that are
  wrong; leave the rest alone.</p>
</section>

<div class="bar">
  <span class="count"><b id="done">0</b> / <span id="total">0</span> reviewed</span>
  <div class="track"><div class="fill" id="fill"></div></div>
  <button class="ghost" id="markall">Accept all remaining as drafted</button>
  <button class="ghost" id="jumpnext">Next unreviewed</button>
</div>

<div id="preps"></div>

<section>
  <h2>2. The same 119 places, in a different grammatical case</h2>
  <p class="sec-note">This is a <strong>second, separate list</strong>. Section 1 covers
  <em>« les sénateurs <strong>du</strong> Nord »</em> — the place attached to a noun. This one
  covers <em>« seront élus <strong>dans le</strong> Nord »</em> — the place attached to a verb.
  French uses a different form for each, so questions phrased with a verb need their own
  approved list. Same drill: my draft is selected, change what's wrong.</p>
</section>

<div class="bar">
  <span class="count"><b id="ldone">0</b> / <span id="ltotal">0</span> reviewed</span>
  <div class="track"><div class="fill" id="lfill"></div></div>
  <button class="ghost" id="lmarkall">Accept all remaining as drafted</button>
</div>

<div id="locs"></div>

<section>
  <h2>3. Which questions we ask</h2>
  <p class="sec-note">Four are built and have answer keys. Four are proposed. Keep or drop
  each one; the box is there if you want to reword.</p>
  <div id="templates"></div>
</section>

<div class="export">
  <button class="primary" id="download">Export approvals</button>
  <button id="copy">Copy to clipboard</button>
  <span class="status" id="status">Your answers save in this browser as you go.</span>
</div>
<div class="drop" id="preview"></div>
</div>

<script>
const DATA = __DATA__;
const LOC = __LOC__;
const TEMPLATES = __TEMPLATES__;
const FORMS = ["de l'","de la","des","du","d'","de"];
const KEY = "fr-approval-v1";
const store = JSON.parse(localStorage.getItem(KEY) || '{"prep":{},"loc":{},"tpl":{}}');
if (!store.loc) store.loc = {};

const esc = s => s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const joined = (form, rest) => form.endsWith("'") ? form + rest : form + " " + rest;

function sentence(r, prep){
  const q = r.kind === "region"
    ? "Qui est le président du conseil régional "
    : "Qui sont les sénateurs ";
  return esc(q) + '<span class="hl">' + esc(prep) + "</span> ?";
}

function locSentence(r, prep){
  return "Combien de sénateurs seront élus " +
    '<span class="hl">' + esc(prep) + "</span> ?";
}

function currentPrep(r){
  const s = store.prep[r.code + ":" + r.kind];
  return s ? s.prep : r.prep;
}

function renderPreps(){
  const host = document.getElementById("preps");
  host.innerHTML = "";
  let kind = null;
  DATA.forEach(r => {
    if (r.kind !== kind){
      kind = r.kind;
      const h = document.createElement("div");
      h.className = "grp";
      h.textContent = kind === "region" ? "Régions (18)" : "Départements (101)";
      host.appendChild(h);
    }
    const id = r.code + ":" + r.kind;
    const saved = store.prep[id];
    const prep = saved ? saved.prep : r.prep;
    const edited = saved && saved.prep !== r.prep;

    const row = document.createElement("div");
    row.className = "row";
    row.id = "p-" + id.replace(":", "-");
    if (saved) row.dataset.state = edited ? "edited" : "ok";

    row.innerHTML =
      '<div class="who"><span class="nm">' + esc(r.name) + '</span>' +
      '<span class="cd">' + esc(r.code) + '</span></div>' +
      '<div><p class="sentence">' + sentence(r, prep) + '</p>' +
      '<div class="opts">' +
      FORMS.map(f => '<button class="opt" data-f="' + f + '" aria-pressed="' +
        (splitForm(prep)[0] === f) + '">' + f + '</button>').join("") +
      '<input class="custom" placeholder="ou écrivez la forme entière" value="' +
      (edited && splitForm(prep)[0] === "" ? esc(prep) : "") + '"></div></div>';

    row.querySelectorAll(".opt").forEach(b => b.addEventListener("click", () => {
      setPrep(r, joined(b.dataset.f, splitForm(currentPrep(r))[1] || r.rest));
    }));
    const cust = row.querySelector(".custom");
    cust.addEventListener("change", () => {
      if (cust.value.trim()) setPrep(r, cust.value.trim());
    });
    host.appendChild(row);
  });
  refresh();
}

function splitForm(prep){
  for (const f of FORMS){
    const probe = f.endsWith("'") ? f : f + " ";
    if (prep.startsWith(probe)) return [f, prep.slice(probe.length)];
  }
  return ["", prep];
}

function setPrep(r, prep){
  store.prep[r.code + ":" + r.kind] = {code:r.code, kind:r.kind, name:r.name,
                                       draft:r.prep, prep:prep};
  save();
  renderPreps();
}

function renderLocs(){
  const host = document.getElementById("locs");
  host.innerHTML = "";
  let kind = null;
  LOC.forEach(r => {
    if (r.kind !== kind){
      kind = r.kind;
      const h = document.createElement("div");
      h.className = "grp";
      h.textContent = kind === "region" ? "Régions (18)" : "Départements (101)";
      host.appendChild(h);
    }
    const id = r.code + ":" + r.kind;
    const saved = store.loc[id];
    const prep = saved ? saved.prep : r.prep;
    const edited = saved && saved.prep !== r.prep;

    const row = document.createElement("div");
    row.className = "row";
    if (saved) row.dataset.state = edited ? "edited" : "ok";
    row.innerHTML =
      '<div class="who"><span class="nm">' + esc(r.name) + '</span>' +
      '<span class="cd">' + esc(r.code) + '</span></div>' +
      '<div><p class="sentence">' + locSentence(r, prep) + '</p>' +
      '<div class="opts">' +
      LOC_FORMS.map(f => '<button class="opt" data-f="' + f + '" aria-pressed="' +
        (splitLoc(prep)[0] === f) + '">' + f + '</button>').join("") +
      '<input class="custom" placeholder="ou écrivez la forme entière" value="' +
      (edited && splitLoc(prep)[0] === "" ? esc(prep) : "") + '"></div></div>';

    row.querySelectorAll(".opt").forEach(b => b.addEventListener("click", () => {
      const rest = splitLoc(store.loc[id] ? store.loc[id].prep : r.prep)[1] || r.rest;
      setLoc(r, joined(b.dataset.f, rest));
    }));
    const cust = row.querySelector(".custom");
    cust.addEventListener("change", () => {
      if (cust.value.trim()) setLoc(r, cust.value.trim());
    });
    host.appendChild(row);
  });
  refresh();
}

function splitLoc(prep){
  for (const f of LOC_FORMS){
    const probe = f.endsWith("'") ? f : f + " ";
    if (prep.startsWith(probe)) return [f, prep.slice(probe.length)];
  }
  return ["", prep];
}

function setLoc(r, prep){
  store.loc[r.code + ":" + r.kind] = {code:r.code, kind:r.kind, name:r.name,
                                      draft:r.prep, prep:prep};
  save(); renderLocs();
}

function renderTemplates(){
  const host = document.getElementById("templates");
  host.innerHTML = "";
  TEMPLATES.forEach(t => {
    const saved = store.tpl[t.id] || {};
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML =
      '<div class="card-top"><span class="tag ' + (t.status === "built" ? "built" : "") +
      '">' + (t.status === "built" ? "built" : "proposed") + '</span>' +
      '<span class="tag">' + t.id + '</span>' +
      '<span class="n">' + t.n + (t.n === 1 ? " question" : " questions") + '</span></div>' +
      '<p class="q">' + esc(t.text) + '</p>' +
      '<p class="ex">' + esc(t.example) + '</p>' +
      '<p class="why">' + esc(t.note) + '</p>' +
      '<div class="choices">' +
      '<button data-v="keep" aria-pressed="' + (saved.verdict === "keep") + '">Keep</button>' +
      '<button class="no" data-v="drop" aria-pressed="' + (saved.verdict === "drop") + '">Drop</button>' +
      '<button class="ghost" data-v="note">Reword…</button></div>' +
      '<textarea class="note' + (saved.note ? " show" : "") +
      '" placeholder="How would you phrase it?">' + esc(saved.note || "") + '</textarea>';

    const ta = card.querySelector(".note");
    card.querySelectorAll(".choices button").forEach(b => b.addEventListener("click", () => {
      if (b.dataset.v === "note"){ ta.classList.toggle("show"); ta.focus(); return; }
      store.tpl[t.id] = Object.assign({}, store.tpl[t.id], {id:t.id, verdict:b.dataset.v});
      save(); renderTemplates();
    }));
    ta.addEventListener("change", () => {
      store.tpl[t.id] = Object.assign({}, store.tpl[t.id], {id:t.id, note:ta.value});
      save();
    });
    host.appendChild(card);
  });
  refresh();
}

function refresh(){
  const n = Object.keys(store.prep).length;
  document.getElementById("done").textContent = n;
  document.getElementById("total").textContent = DATA.length;
  document.getElementById("fill").style.width = (100 * n / DATA.length) + "%";
  const m = Object.keys(store.loc).length;
  document.getElementById("ldone").textContent = m;
  document.getElementById("ltotal").textContent = LOC.length;
  document.getElementById("lfill").style.width = (100 * m / LOC.length) + "%";
}

function save(){ localStorage.setItem(KEY, JSON.stringify(store)); }

function payload(){
  const changed = Object.values(store.prep).filter(p => p.prep !== p.draft);
  return {
    generated: new Date().toISOString(),
    prepositions: {
      total: DATA.length,
      reviewed: Object.keys(store.prep).length,
      corrections: changed.map(p => ({code:p.code, kind:p.kind, name:p.name,
                                      was:p.draft, now:p.prep}))
    },
    locative: {
      total: LOC.length,
      reviewed: Object.keys(store.loc).length,
      corrections: Object.values(store.loc).filter(p => p.prep !== p.draft)
        .map(p => ({code:p.code, kind:p.kind, name:p.name, was:p.draft, now:p.prep}))
    },
    templates: Object.values(store.tpl)
  };
}

document.getElementById("markall").addEventListener("click", () => {
  DATA.forEach(r => {
    const id = r.code + ":" + r.kind;
    if (!store.prep[id]) store.prep[id] = {code:r.code, kind:r.kind, name:r.name,
                                           draft:r.prep, prep:r.prep};
  });
  save(); renderPreps();
});

document.getElementById("lmarkall").addEventListener("click", () => {
  LOC.forEach(r => {
    const id = r.code + ":" + r.kind;
    if (!store.loc[id]) store.loc[id] = {code:r.code, kind:r.kind, name:r.name,
                                         draft:r.prep, prep:r.prep};
  });
  save(); renderLocs();
});

document.getElementById("jumpnext").addEventListener("click", () => {
  const next = DATA.find(r => !store.prep[r.code + ":" + r.kind]);
  if (!next) return;
  document.getElementById("p-" + next.code + "-" + next.kind)
          .scrollIntoView({behavior:"smooth", block:"center"});
});

document.getElementById("download").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(payload(), null, 2)], {type:"application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "france-approvals.json";
  a.click();
  document.getElementById("status").textContent = "Saved france-approvals.json — send me that file.";
});

document.getElementById("copy").addEventListener("click", async () => {
  const txt = JSON.stringify(payload(), null, 2);
  const el = document.getElementById("preview");
  try {
    await navigator.clipboard.writeText(txt);
    document.getElementById("status").textContent = "Copied — paste it to me.";
  } catch {
    el.textContent = txt; el.classList.add("show");
    document.getElementById("status").textContent = "Select the text below and copy it.";
  }
});

renderPreps();
renderLocs();
renderTemplates();
</script>
"""

if __name__ == "__main__":
    main()
