#!/usr/bin/env python3
"""Grade the 120 pilot records with the validated DeepSeek-V4-Flash grader.

Single pass, thinking mode (reasoning_effort=high), temp 0. Reuses the prompts,
schema, and API plumbing from validate_grader.py (99% fixture agreement).

Usage: python3 grade_pilot.py [pass_label]
Reads  ../data/chat-probe/pilot_full.jsonl + rubrics.json
Writes ../data/chat-probe/grades_<pass_label>.jsonl (default pass1)
"""
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from validate_grader import (SYSTEM_PROC, SYSTEM_CAND, SCHEMA, SCHEMA_HINT,
                             MODEL, URL, SSL_CTX, api_key)

DATA = os.path.join(HERE, "..", "data", "chat-probe")


def build_user(rec, rub):
    lines = [f"- {it['id']}: {it['check']}{'  (critical)' if it['crit'] else ''}"
             for it in rub["items"]]
    seen, cites = set(), []
    for c in rec.get("citations") or []:
        if c.get("via") == "map-widget":
            continue
        u = c["url"]
        if u in seen:
            continue
        seen.add(u)
        cites.append(u if not c.get("title") else f"{c['title']} — {u}")
        if len(cites) >= 40:
            break
    cite_block = "\n".join(f"- {c}" for c in cites) if cites else "(none cited)"
    return (f"QUESTION: {rec['questionText']}\n\n"
            f"ANSWER:\n{rec['responseText']}\n\n"
            f"CITED SOURCES (as displayed by the chatbot):\n{cite_block}\n\n"
            f"RUBRIC:\n" + "\n".join(lines) + "\n\nReturn the JSON.")


def parse_grade(content):
    """Tolerant parse of the judge's JSON.

    DeepSeek-V4-Flash in reasoning mode does not honour response_format, and two
    malformed shapes show up: (1) raw control chars inside strings, (2) it copies
    the JSON-Schema nesting and emits "items":{"items":[...]} with unbalanced
    braces. Both are recoverable; anything else raises.
    """
    c = (content or "").strip()
    if c.startswith("```"):
        c = re.sub(r"^```(?:json)?\s*", "", c)
        c = re.sub(r"\s*```$", "", c)
    # undo the schema-mimicry double-wrap (drops the spurious, never-closed brace)
    unwrapped = re.sub(r'"items"\s*:\s*\{\s*"items"\s*:\s*\[', '"items":[', c, count=1)
    for cand in (c, unwrapped):
        try:
            g = json.loads(cand, strict=False)  # strict=False tolerates control chars
        except Exception:
            continue
        if isinstance(g.get("items"), dict) and "items" in g["items"]:
            g["items"] = g["items"]["items"]
        if isinstance(g.get("items"), list):
            return g
    raise ValueError("unparseable grade JSON")


def grade_one(rec, rub, key):
    # NOTE: no response_format. DeepInfra does not enforce json_schema in reasoning
    # mode, and sending it actively corrupts the output: the model copies the schema's
    # own items.items nesting and emits unbalanced JSON. Measured 1/6 vs 6/6 clean
    # parses with it removed. The shape is pinned by SCHEMA_HINT + validated below.
    body = {
        "model": MODEL, "temperature": 0, "max_tokens": 8000,
        "messages": [
            {"role": "system", "content": (SYSTEM_CAND if rub["sec"] == "cand" else SYSTEM_PROC) + SCHEMA_HINT},
            {"role": "user", "content": build_user(rec, rub)},
        ],
        "reasoning_effort": "high",
    }
    req = urllib.request.Request(URL, json.dumps(body).encode(),
                                 {"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    t0 = time.time()
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=300, context=SSL_CTX) as r:
                resp = json.load(r)
            grade = parse_grade(resp["choices"][0]["message"]["content"])
            want = {it["id"].upper() for it in rub["items"]}
            got = {i["id"].strip().upper().strip("[]") for i in grade["items"]}
            if want - got:
                raise ValueError(f"missing rubric items in grade: {want - got}")
            if "critical_error" not in grade:
                raise ValueError("no critical_error key")
            u = resp.get("usage", {})
            return {"recordId": rec["recordId"], "provider": rec["provider"],
                    "questionId": str(rec["questionId"]), "repIndex": rec["repIndex"],
                    "grade": grade, "in_tok": u.get("prompt_tokens"),
                    "out_tok": u.get("completion_tokens"),
                    "latency": round(time.time() - t0, 1)}
        except Exception as e:
            err = ""
            try:
                err = e.read()[:200].decode()
            except Exception:
                pass
            print(f"  retry {rec['provider']}/{rec['questionId']}/r{rec['repIndex']} "
                  f"({attempt+1}): {e} {err}", file=sys.stderr)
            time.sleep(3 * (attempt + 1))
    return {"recordId": rec["recordId"], "provider": rec["provider"],
            "questionId": str(rec["questionId"]), "repIndex": rec["repIndex"],
            "grade": None, "error": "failed after retries"}


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "pass1"
    key = api_key()
    rubrics = json.load(open(os.path.join(HERE, "rubrics.json")))
    recs = [json.loads(l) for l in open(os.path.join(DATA, "pilot_full.jsonl"))]
    print(f"grading {len(recs)} records, thinking mode, 1 pass ...")
    done = [0]

    def work(rec):
        out = grade_one(rec, rubrics[str(rec["questionId"])], key)
        done[0] += 1
        if done[0] % 20 == 0:
            print(f"  {done[0]}/{len(recs)}")
        return out

    t0 = time.time()
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(work, recs))
    path = os.path.join(DATA, f"grades_{label}.jsonl")
    with open(path, "w") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    ok = sum(1 for r in results if r.get("grade"))
    tin = sum(r.get("in_tok") or 0 for r in results)
    tout = sum(r.get("out_tok") or 0 for r in results)
    print(f"\n{ok}/{len(recs)} graded in {(time.time()-t0)/60:.1f} min; "
          f"{tin}+{tout} tok = ${tin*0.09/1e6 + tout*0.18/1e6:.3f}")
    print("wrote", path)


if __name__ == "__main__":
    main()
