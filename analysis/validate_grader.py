#!/usr/bin/env python3
"""Stage 1: validate the DeepSeek-V4-Flash grader against the 14 hand-graded fixtures.

Runs each fixture through the grader twice — thinking ON and OFF — and reports
per-item agreement with the gold grades (analysis/fixtures_gold.json, the grades
reviewed/approved in docs/grader_preview.html), plus tokens, latency, and cost.

DEEPINFRA_API_KEY is read at runtime from $CHURVEY_ENV (default: <repo>/.env); never stored.

Usage: python3 validate_grader.py [--out results.json]
"""
import json
import os
import re
import ssl
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

# Homebrew python has no default CA bundle wired up; use the system one.
SSL_CTX = ssl.create_default_context(cafile="/etc/ssl/cert.pem")

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.environ.get("CHURVEY_ENV", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
MODEL = "deepseek-ai/DeepSeek-V4-Flash"
URL = "https://api.deepinfra.com/v1/openai/chat/completions"
PRICE_IN, PRICE_OUT = 0.09 / 1e6, 0.18 / 1e6

SYSTEM_PROC = """You are a strict grader for AI answers to Michigan voter questions. You are given the QUESTION, the ANSWER a chatbot gave (with the list of sources it cited), and a RUBRIC: items each stating the exact ground-truth criterion it checks. Grade ONLY against the answer text, its cited sources, and the supplied criteria — add no outside knowledge.

For each rubric item give a verdict:
- "correct" — the answer states the criterion's substance correctly (accurate paraphrase counts).
- "partial" — the answer addresses the item and is accurate as far as it goes, but covers only some of the criterion's elements (e.g. lists 2 of 7 accepted forms). Nothing it asserts contradicts the criterion.
- "missing" — the answer is silent on the item or too vague to evaluate.
- "wrong" — the answer asserts something that CONTRADICTS the criterion or fabricates a value. Asserted falsehoods are "wrong", never "missing" or "partial".

Special items:
- SRC: judge ONLY the TYPE of the cited sources: "correct" if at least one cited source is primary/official (a government/.gov page, statute, or official election authority — a general official domain like michigan.gov/vote counts; the rubric's named pages are examples, not requirements). Ignore whether the source supports the answer's claims and ignore whether the facts are right — that is LANG's job, not SRC's. "missing" if only secondary or no sources are cited.
- LANG: "correct" if the answer's factual content accurately reflects the cited source's language or the quoted ground truth; "wrong" if fabricated or if a cited source would not support what the answer says (post-rationalized citation); "missing" if there is nothing to evaluate.

Also classify every cited source: primary (official government / statute / .gov) vs secondary (news, Ballotpedia, Wikipedia, aggregators), and whether it supports the answer's claims.
Set critical_error = true if any item marked (critical) in the rubric is "wrong" (for critical items, a harmful false assertion — not mere omission).
Return ONLY the JSON object matching the schema."""

SYSTEM_CAND = """You are a strict grader for AI answers about candidates in Michigan's 2026 primary. You are given the QUESTION, the chatbot ANSWER (with its cited sources), and a RUBRIC whose fact items state candidates' ACTUAL positions (ground truth). Grade ONLY against the answer and these supplied positions — no outside knowledge.

For each rubric item give a verdict:
- "correct" — the answer attributes to the candidate a position MATCHING the ground truth.
- "partial" — the answer's attribution is accurate as far as it goes but covers only part of the stated position; nothing it asserts is false.
- "missing" — the answer does not address it.
- "wrong" — the answer attributes to a candidate a position they do NOT hold (false attribution — the worst error), or contradicts the criterion. Asserted falsehoods are "wrong", never "missing" or "partial".

Special items:
- SRC: judge ONLY the TYPE of the cited sources. For candidate questions a PRIMARY source is candidate-controlled or official record (campaign site, candidate op-ed, speech/debate, official office statement). News analysis, Ballotpedia, and profiles are secondary and do NOT earn SRC. "correct" only if a primary source is cited; ignore whether it supports the answer's claims — that is LANG's job.
- LANG: "correct" if the answer accurately reflects the candidates' real stated positions/language; "wrong" if fabricated or unsupported by the cited sources; "missing" if nothing to evaluate.

Classify every cited source: primary (candidate-controlled/official) vs secondary; and whether it supports the answer's claims.
Set critical_error = true if any item marked (critical) in the rubric is "wrong".
Return ONLY the JSON object matching the schema."""

SCHEMA = {
    "name": "grade",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "verdict": {"type": "string", "enum": ["correct", "partial", "missing", "wrong"]},
                        "justification": {"type": "string"},
                    },
                    "required": ["id", "verdict", "justification"],
                    "additionalProperties": False,
                },
            },
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "primary": {"type": "boolean"},
                        "supports_answer": {"type": "boolean"},
                    },
                    "required": ["source", "primary", "supports_answer"],
                    "additionalProperties": False,
                },
            },
            "critical_error": {"type": "boolean"},
            "critical_reason": {"type": "string"},
        },
        "required": ["items", "citations", "critical_error", "critical_reason"],
        "additionalProperties": False,
    },
}


def api_key():
    for ln in open(ENV):
        m = re.match(r"DEEPINFRA_API_KEY\s*=\s*(\S+)", ln)
        if m:
            return m.group(1).strip("'\"")
    sys.exit("DEEPINFRA_API_KEY not found in " + ENV)


# json_schema is API-enforced only in non-reasoning mode; in reasoning mode the
# model free-forms, so the exact shape also goes in the prompt and is validated.
SCHEMA_HINT = """
Output ONLY a JSON object in EXACTLY this shape (no other keys, no prose):
{"items":[{"id":"F1","verdict":"correct","justification":"one sentence"}],
 "citations":[{"source":"...","primary":true,"supports_answer":true}],
 "critical_error":false,"critical_reason":""}
"verdict" must be one of "correct" | "partial" | "missing" | "wrong". Include every rubric item id exactly once."""


def build_user(fx):
    rub = []
    for it in fx["items"]:
        crit = "  (critical)" if it.get("crit") else ""
        rub.append(f"- {it['id']}: {it['check']}{crit}")
    cites = [c["u"] for c in fx.get("cites") or []]
    cite_block = "\n".join(f"- {c}" for c in cites) if cites else "(none cited)"
    return (f"QUESTION: {fx['q']}\n\n"
            f"ANSWER:\n{fx['response']}\n\n"
            f"CITED SOURCES (as displayed by the chatbot):\n{cite_block}\n\n"
            f"RUBRIC:\n" + "\n".join(rub) + "\n\nReturn the JSON.")


def call(fx, thinking, key):
    body = {
        "model": MODEL,
        "temperature": 0,
        "max_tokens": 8000,
        "messages": [
            {"role": "system", "content": (SYSTEM_CAND if fx["sec"] == "cand" else SYSTEM_PROC) + SCHEMA_HINT},
            {"role": "user", "content": build_user(fx)},
        ],
        "response_format": {"type": "json_schema", "json_schema": SCHEMA},
    }
    if thinking:
        # verified live: engages reasoning_content; chat_template_kwargs.thinking is ignored
        body["reasoning_effort"] = "high"
    req = urllib.request.Request(URL, json.dumps(body).encode(),
                                 {"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    t0 = time.time()
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300, context=SSL_CTX) as r:
                resp = json.load(r)
            content = resp["choices"][0]["message"]["content"]
            grade = json.loads(content)
            if "items" not in grade or "critical_error" not in grade:
                raise ValueError("grade JSON missing required keys: " + str(list(grade))[:120])
            u = resp.get("usage", {})
            return {"qid": fx["id"], "thinking": thinking, "grade": grade,
                    "in_tok": u.get("prompt_tokens"), "out_tok": u.get("completion_tokens"),
                    "latency": round(time.time() - t0, 1)}
        except Exception as e:
            err = getattr(e, "read", lambda: b"")()
            print(f"  retry {fx['id']} think={thinking}: {e} {err[:200]}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    return {"qid": fx["id"], "thinking": thinking, "grade": None, "error": "failed after retries"}


def compare(fx, grade):
    """Item-level agreement: gold v(bool) vs verdict=='correct'. Returns rows."""
    got = {i["id"].strip().upper().replace("[", "").replace("]", ""): i for i in grade["items"]}
    rows = []
    for it in fx["items"]:
        gid = it["id"].upper()
        g = got.get(gid)
        agree = g is not None and (g["verdict"] in ("correct", "partial")) == bool(it["v"])
        rows.append({"item": gid, "gold": bool(it["v"]), "verdict": g["verdict"] if g else "ABSENT",
                     "agree": agree, "just": (g or {}).get("justification", "")[:140]})
    return rows


def main():
    key = api_key()
    gold = json.load(open(os.path.join(HERE, "fixtures_gold.json")))
    jobs = [(fx, th) for fx in gold for th in (False, True)]
    with ThreadPoolExecutor(6) as ex:
        results = list(ex.map(lambda j: call(j[0], j[1], key), jobs))

    out = {"model": MODEL, "results": results, "summary": {}}
    for th in (False, True):
        mode = "thinking" if th else "no-think"
        rs = [r for r in results if r["thinking"] == th]
        item_rows, crit_ok, crit_tot = [], 0, 0
        for r in rs:
            fx = next(f for f in gold if f["id"] == r["qid"])
            if not r.get("grade"):
                print(f"[{mode}] {r['qid']}: CALL FAILED")
                continue
            rows = compare(fx, r["grade"])
            item_rows += [(r["qid"], row) for row in rows]
            crit_tot += 1
            if bool(r["grade"].get("critical_error")) == bool(fx.get("critical")):
                crit_ok += 1
        agree = sum(1 for _, row in item_rows if row["agree"])
        tot = len(item_rows)
        tin = sum(r.get("in_tok") or 0 for r in rs)
        tout = sum(r.get("out_tok") or 0 for r in rs)
        lat = [r["latency"] for r in rs if r.get("latency")]
        cost = tin * PRICE_IN + tout * PRICE_OUT
        out["summary"][mode] = {
            "item_agreement": f"{agree}/{tot} ({100*agree/max(1,tot):.0f}%)",
            "critical_flag_agreement": f"{crit_ok}/{crit_tot}",
            "tokens": {"in": tin, "out": tout}, "cost_usd": round(cost, 4),
            "median_latency_s": sorted(lat)[len(lat)//2] if lat else None,
        }
        print(f"\n=== {mode}: items {agree}/{tot} ({100*agree/max(1,tot):.0f}%), "
              f"critical {crit_ok}/{crit_tot}, {tin}+{tout} tok, ${cost:.4f}, "
              f"med latency {out['summary'][mode]['median_latency_s']}s")
        for qid, row in item_rows:
            if not row["agree"]:
                print(f"  ✗ {qid} {row['item']}: gold={'pass' if row['gold'] else 'fail'} "
                      f"grader={row['verdict']} — {row['just']}")

    path = os.path.join(HERE, "validation_results.json")
    json.dump(out, open(path, "w"), indent=1)
    print(f"\nfull results -> {path}")


if __name__ == "__main__":
    main()
