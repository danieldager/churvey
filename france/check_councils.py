#!/usr/bin/env python3
"""Automatic cross-check for the council-president answer keys (D3 and R1).

WHY THIS EXISTS. The RNE is the only machine-readable *authority* for conseil
départemental / régional présidents, and its presidency data is ~10 months stale.
An earlier pass concluded verification was not automatable - that conclusion was
WRONG, and only half-tested: it checked Wikidata's structured statements (5 of 101
départements) and stopped. The per-departement Wikipedia ARTICLES carry the
president in an infobox, follow a uniform title pattern, and expose a machine-
readable last-revision timestamp.

WHAT THIS IS AND IS NOT. Wikipedia is not an authority and this does not make a
row verified. It is a DISAGREEMENT DETECTOR: it turns "manually re-check 100 rows"
into "investigate the handful where two independent sources differ". Independently
reproduces both errors found by hand (02 Aisne, 82 Tarn-et-Garonne).

Read the revision date, not just the name. An article last revised before a change
happened cannot testify about it - the tool reports STALE for those rather than
letting an old agreement look like confirmation.

  france/check_councils.py [--data data/fr] [--max-age-days 120]
"""
import argparse
import json
import re
import subprocess
import sys
import unicodedata
import urllib.parse
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from name_matching import same_person
from prepositions import DEPARTEMENT_PREP, REGION_PREP

API = "https://fr.wikipedia.org/w/api.php"
UA = "llm_bench-france-audit/1.0 (civic AI research; contact via repo)"
BATCH = 20


def fetch(titles):
    out = {}
    for i in range(0, len(titles), BATCH):
        chunk = titles[i:i + BATCH]
        q = (f"{API}?action=query&format=json&prop=revisions&rvprop=content|timestamp"
             "&rvslots=main&redirects=1&titles=" + urllib.parse.quote("|".join(chunk)))
        data = None
        for attempt in range(4):
            r = subprocess.run(["curl", "-sS", "-m", "60", "--retry", "2",
                                "--retry-delay", "3", "-A", UA, q],
                               capture_output=True, text=True)
            try:
                data = json.loads(r.stdout).get("query", {})
                break
            except Exception:
                if attempt == 3:
                    sys.exit(f"fetch failed after 4 attempts: {r.stdout[:200]}")
                subprocess.run(["sleep", "5"])
        
        norm = {n["from"]: n["to"] for n in data.get("normalized", [])}
        redir = {n["from"]: n["to"] for n in data.get("redirects", [])}
        resolved = {}
        for t in chunk:
            t2 = norm.get(t, t)
            resolved[redir.get(t2, t2)] = t
        for p in data.get("pages", {}).values():
            src = resolved.get(p.get("title"), p.get("title"))
            if "revisions" not in p:
                out[src] = None
                continue
            rev = p["revisions"][0]
            out[src] = (rev["slots"]["main"]["*"], rev["timestamp"][:10])
    return out


def resolve_qids(qids):
    """{{Lien par élément|Q123}} points at a Wikidata item, not a name."""
    out = {}
    qids = sorted(set(qids))
    for i in range(0, len(qids), 40):
        chunk = qids[i:i + 40]
        q = ("https://www.wikidata.org/w/api.php?action=wbgetentities&format=json"
             "&props=labels&languages=fr&ids=" + "|".join(chunk))
        r = subprocess.run(["curl", "-sS", "-m", "45", "-A", UA, q],
                           capture_output=True, text=True)
        try:
            ent = json.loads(r.stdout).get("entities", {})
        except Exception:
            continue
        for qid, e in ent.items():
            lab = e.get("labels", {}).get("fr", {}).get("value")
            if lab:
                out[qid] = lab
    return out


def president(wikitext):
    """Pull the président out of the infobox. Three markup variants in the wild:
       | président = Jean Dupont
       | président = {{Lien par élément|Q123}}      (departement articles)
       | leader1_type = Président / | leader1_name = ...   (region articles)
    Returns a name, or ("QID", "Q123") for the Wikidata-link form."""
    m = re.search(r"\|\s*(?:président|presidente|président[e]?)\s*=\s*([^\n|]*(?:\|[^\n}]*)?)",
                  wikitext, re.I)
    if m and "Lien par élément" in m.group(1):
        q = re.search(r"Lien par élément\s*\|\s*(Q\d+)", m.group(1))
        if q:
            return ("QID", q.group(1))
    if not m or not m.group(1).strip():
        lt = re.search(r"\|\s*leader(\d)_type\s*=\s*Président", wikitext, re.I)
        if lt:
            ln = re.search(rf"\|\s*leader{lt.group(1)}(?:_name)?\s*=\s*([^\n|]+)",
                           wikitext)
            if ln:
                m = ln
    if not m:
        return None
    v = m.group(1)
    v = re.sub(r"<[^>]+>", " ", v)                       # <small>…
    v = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", v)  # [[A|B]] -> B
    v = re.sub(r"\[\[([^\]]+)\]\]", r"\1", v)             # [[A]]  -> A
    v = re.split(r"[(（]", v)[0]                          # drop party in parens
    v = re.sub(r"\{\{[^}]*\}\}", " ", v)
    return re.sub(r"\s+", " ", v).strip(" '\"") or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/fr")
    ap.add_argument("--max-age-days", type=int, default=120,
                    help="an article older than this cannot confirm a recent change")
    args = ap.parse_args()
    gt = Path(args.data) / "groundtruth"
    today = date.today()

    d3 = json.loads((gt / "d3_president_conseil_departemental.json").read_text(encoding="utf-8"))
    r1 = json.loads((gt / "r1_president_conseil_regional.json").read_text(encoding="utf-8"))

    rows = []
    for r in d3:
        c = r["bindings"]["departement"]
        if c == "69M":
            title = "Métropole de Lyon"
        elif c in DEPARTEMENT_PREP:
            title = "Conseil départemental " + DEPARTEMENT_PREP[c]
        else:
            continue
        rows.append(("D3", c, title, r))
    for r in r1:
        c = r["bindings"]["region"]
        rows.append(("R1", c, "Conseil régional " + REGION_PREP[c], r))

    print(f"checking {len(rows)} council rows against fr.wikipedia…\n")
    pages = fetch([t for _, _, t, _ in rows])

    parsed = {}
    for tmpl, code, title, row in rows:
        page = pages.get(title)
        parsed[(tmpl, code)] = president(page[0]) if page else None
    qids = [v[1] for v in parsed.values() if isinstance(v, tuple)]
    labels = resolve_qids(qids) if qids else {}
    print(f"resolved {len(labels)}/{len(set(qids))} Wikidata-linked names\n")

    agree, disagree, stale, missing = [], [], [], []
    for tmpl, code, title, row in rows:
        page = pages.get(title)
        if not page:
            missing.append((tmpl, code, title))
            continue
        text, revised = page
        theirs = parsed[(tmpl, code)]
        if isinstance(theirs, tuple):
            theirs = labels.get(theirs[1])
        if not theirs:
            missing.append((tmpl, code, title + " (no président field)"))
            continue
        age = (today - date.fromisoformat(revised)).days
        ours = row["expected"]
        ok = same_person(ours, theirs)
        rec = (tmpl, code, ours, theirs, revised, age)
        if not ok:
            disagree.append(rec)
        elif age > args.max_age_days:
            stale.append(rec)
        else:
            agree.append(rec)

    if disagree:
        print(f"=== DISAGREEMENT — investigate these {len(disagree)} ===")
        for tmpl, code, ours, theirs, rev, age in sorted(disagree, key=lambda x: x[1]):
            print(f"  {tmpl} {code:5s} ours: {ours:28s} wikipedia: {theirs:28s} "
                  f"[rev {rev}, {age}d]")
        print()
    if stale:
        print(f"=== AGREES, BUT THE ARTICLE IS OLD ({len(stale)}) ===")
        print(f"    revised >{args.max_age_days}d ago, so it cannot testify to a recent change")
        for tmpl, code, ours, theirs, rev, age in sorted(stale, key=lambda x: -x[5]):
            print(f"  {tmpl} {code:5s} {ours:28s} [rev {rev}, {age}d old]")
        print()
    if missing:
        print(f"=== NO ARTICLE / NO INFOBOX FIELD ({len(missing)}) ===")
        for tmpl, code, title in missing:
            print(f"  {tmpl} {code:5s} {title}")
        print()

    n = len(rows)
    print(f"agree & fresh {len(agree)}/{n} · disagree {len(disagree)} · "
          f"agree-but-stale {len(stale)} · unchecked {len(missing)}")
    print("\nWikipedia is NOT an authority. Agreement lowers suspicion; it does not")
    print("verify a row. Disagreement is the signal worth acting on.")
    rep = Path(args.data) / "review/council_crosscheck.json"
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps({
        "checked": today.isoformat(), "source": "fr.wikipedia article infoboxes",
        "caveat": "NOT an authority - a disagreement detector. Agreement lowers "
                  "suspicion; it does not verify a row.",
        "max_age_days": args.max_age_days,
        "disagree": [dict(zip(("template","binding","ours","wikipedia","revised","age_days"), d))
                     for d in disagree],
        "agree_but_stale": [dict(zip(("template","binding","ours","wikipedia","revised","age_days"), d))
                            for d in stale],
        "unchecked": [dict(zip(("template","binding","title"), m)) for m in missing],
        "agree_fresh": [d[1] for d in agree],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {rep}")


if __name__ == "__main__":
    main()
