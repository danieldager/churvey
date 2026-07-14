#!/usr/bin/env python3
"""Build a simple review page for a grading pass -> docs/grade_review.html.

Summary tables up top, then every record grouped by question: verdict-per-item
with the grader's justification, collapsible answer text and citations.

Usage: python3 build_review_html.py [pass_label]   (default pass1)
"""
import html
import json
import os
import sys
import collections
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "chat-probe")
OUT = os.path.join(HERE, "..", "docs", "grade_review.html")
POINTS = {"correct": 1.0, "partial": 0.5, "missing": 0.0, "wrong": 0.0}
PROV_LABEL = {"chatgpt": "ChatGPT", "claude": "Claude"}


def esc(s):
    return html.escape(str(s if s is not None else ""))


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "pass1"
    grades = [json.loads(l) for l in open(os.path.join(DATA, f"grades_{label}.jsonl"))]
    recs = {r["recordId"]: r for r in (json.loads(l) for l in open(os.path.join(DATA, "pilot_full.jsonl")))}
    rubrics = json.load(open(os.path.join(HERE, "rubrics.json")))
    questions = {str(r["questionId"]): r["questionText"] for r in recs.values()}
    qorder = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8",
              "16.2", "16.3", "16.4", "16.5", "16.6", "16.7", "16.8"]

    def score(g):
        items = g["grade"]["items"]
        return sum(POINTS.get(i["verdict"], 0) for i in items) / len(items)

    # provider summary
    prov_rows = []
    for p in ("chatgpt", "claude"):
        gs = [g for g in grades if g["provider"] == p and g.get("grade")]
        vd = collections.Counter(i["verdict"] for g in gs for i in g["grade"]["items"])
        wrongs = sum(1 for g in gs if any(
            i["verdict"] == "wrong" and i["id"].upper().strip("[]") not in ("SRC", "LANG")
            for i in g["grade"]["items"]))
        crits = sum(1 for g in gs if g["grade"].get("critical_error"))
        prov_rows.append(
            f"<tr><td>{PROV_LABEL[p]}</td><td>{len(gs)}</td>"
            f"<td>{statistics.mean(score(g) for g in gs)*100:.0f}%</td>"
            f"<td>{vd.get('correct',0)}</td><td>{vd.get('partial',0)}</td>"
            f"<td>{vd.get('missing',0)}</td><td class='w'>{vd.get('wrong',0)}</td>"
            f"<td class='w'>{wrongs} ({100*wrongs/len(gs):.0f}%)</td><td class='w'>{crits}</td></tr>")

    # per-question mean scores
    qrows = []
    for q in qorder:
        cells = [f"<td class='ql'>{q}</td>"]
        for p in ("chatgpt", "claude"):
            gs = [g for g in grades if g["provider"] == p and g["questionId"] == q and g.get("grade")]
            m = statistics.mean(score(g) for g in gs) * 100 if gs else 0
            nw = sum(1 for g in gs if any(i["verdict"] == "wrong" for i in g["grade"]["items"]))
            cells.append(f"<td>{m:.0f}%{' · ' + str(nw) + 'w' if nw else ''}</td>")
        qrows.append("<tr>" + "".join(cells) + f"<td class='qt'>{esc(questions[q][:90])}</td></tr>")

    # record cards
    sections = []
    for q in qorder:
        cards = []
        for p in ("chatgpt", "claude"):
            for g in sorted((g for g in grades if g["provider"] == p and g["questionId"] == q),
                            key=lambda g: g["repIndex"]):
                rec = recs[g["recordId"]]
                if not g.get("grade"):
                    cards.append(f"<div class='card'><b>{PROV_LABEL[p]} · rep {g['repIndex']}</b> "
                                 f"— <span class='w'>GRADING FAILED</span></div>")
                    continue
                gr = g["grade"]
                rows = "".join(
                    f"<tr><td class='iid'>{esc(i['id'])}</td>"
                    f"<td><span class='v {esc(i['verdict'])}'>{esc(i['verdict'])}</span></td>"
                    f"<td class='crit'>{'⚠' if next((it for it in rubrics[q]['items'] if it['id'].upper()==i['id'].upper().strip('[]')), {}).get('crit') else ''}</td>"
                    f"<td class='just'>{esc(i['justification'])}</td></tr>"
                    for i in gr["items"])
                crit = (f"<div class='critbox'>⚠ critical: {esc(gr.get('critical_reason',''))}</div>"
                        if gr.get("critical_error") else "")
                cites = [c for c in rec.get("citations") or [] if c.get("via") != "map-widget"]
                cite_lis = "".join(f"<li>{esc(c['url'])}</li>" for c in cites[:40])
                gcites = "".join(
                    f"<li>{esc(c['source'])} — {'primary' if c.get('primary') else 'secondary'}"
                    f"{', supports' if c.get('supports_answer') else ', does not support'}</li>"
                    for c in gr.get("citations", []))
                cards.append(f"""
<div class='card'>
 <div class='cardhead'><b>{PROV_LABEL[p]} · rep {g['repIndex']}</b>
   <span class='score'>{score(g)*100:.0f}%</span></div>
 {crit}
 <table class='items'>{rows}</table>
 <details><summary>answer ({len(rec['responseText'])} chars)</summary>
   <pre class='ans'>{esc(rec['responseText'])}</pre></details>
 <details><summary>cited sources ({len(cites)}) + grader's classification</summary>
   <div class='twocol'><ul>{cite_lis}</ul><ul>{gcites}</ul></div></details>
</div>""")
        rub_lis = "".join(f"<li><b>{esc(it['id'])}</b>{' ⚠' if it['crit'] else ''}: {esc(it['check'])}</li>"
                          for it in rubrics[q]["items"])
        sections.append(f"""
<section id='q{q.replace('.','-')}'>
 <h2>{q} — {esc(questions[q])}</h2>
 <details class='rub'><summary>rubric ({len(rubrics[q]['items'])} items)</summary><ul>{rub_lis}</ul></details>
 {''.join(cards)}
</section>""")

    nav = " ".join(f"<a href='#q{q.replace('.','-')}'>{q}</a>" for q in qorder)
    doc = f"""<title>Pilot grades — review ({label})</title>
<style>
 body {{ font: 14px/1.45 -apple-system, system-ui, sans-serif; margin: 24px auto; max-width: 980px; padding: 0 16px; }}
 h1 {{ font-size: 20px; }} h2 {{ font-size: 16px; margin: 28px 0 8px; border-bottom: 1px solid #8884; padding-bottom: 4px; }}
 table {{ border-collapse: collapse; width: 100%; margin: 8px 0; }}
 th, td {{ text-align: left; padding: 4px 8px; border-bottom: 1px solid #8883; vertical-align: top; }}
 th {{ font-size: 12px; text-transform: uppercase; letter-spacing: .04em; opacity: .7; }}
 .v {{ padding: 1px 7px; border-radius: 9px; font-size: 12px; font-weight: 600; }}
 .v.correct {{ background: #2da44e33; color: #1a7f37; }} .v.partial {{ background: #bf8b0033; color: #9a6700; }}
 .v.missing {{ background: #8886; }} .v.wrong {{ background: #cf222e33; color: #cf222e; }}
 .w {{ color: #cf222e; font-weight: 600; }}
 .card {{ border: 1px solid #8884; border-radius: 8px; padding: 10px 14px; margin: 10px 0; }}
 .cardhead {{ display: flex; justify-content: space-between; }}
 .score {{ font-weight: 700; }}
 .items td {{ font-size: 13px; }} .iid {{ font-weight: 600; width: 46px; }} .crit {{ width: 18px; }}
 .just {{ opacity: .85; }}
 .critbox {{ background: #cf222e1a; border-left: 3px solid #cf222e; padding: 6px 10px; margin: 6px 0; font-size: 13px; }}
 .ans {{ white-space: pre-wrap; font-size: 13px; background: #8881; padding: 10px; border-radius: 6px; }}
 details {{ margin: 6px 0; }} summary {{ cursor: pointer; opacity: .8; font-size: 13px; }}
 .twocol {{ display: flex; gap: 24px; }} .twocol ul {{ font-size: 12px; margin: 6px 0; padding-left: 18px; max-width: 50%; overflow-wrap: anywhere; }}
 nav a {{ margin-right: 10px; }} .ql {{ font-weight: 700; }} .qt {{ font-size: 12px; opacity: .7; }}
 .rub ul {{ font-size: 13px; }}
 @media (prefers-color-scheme: dark) {{ .v.correct {{ color: #4ac26b; }} .v.partial {{ color: #d4a72c; }} }}
</style>
<h1>Michigan pilot — grader review <small>({label}, DeepSeek-V4-Flash thinking, single pass)</small></h1>
<p>Score = correct 1 · partial 0.5 · missing/wrong 0, over that question's rubric items.
Misinfo = answers asserting ≥1 false fact item (SRC/LANG excluded). ⚠ marks critical rubric items.</p>
<table><tr><th>provider</th><th>n</th><th>mean score</th><th>correct</th><th>partial</th>
<th>missing</th><th>wrong</th><th>misinfo answers</th><th>critical</th></tr>{''.join(prov_rows)}</table>
<h2>Per question (mean score · wrong-count)</h2>
<table><tr><th>q</th><th>ChatGPT</th><th>Claude</th><th></th></tr>{''.join(qrows)}</table>
<nav>{nav}</nav>
{''.join(sections)}
"""
    open(OUT, "w").write(doc)
    print("wrote", OUT, f"({os.path.getsize(OUT)//1024} KB)")


if __name__ == "__main__":
    main()
