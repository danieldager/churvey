#!/usr/bin/env python3
"""Reconstruct full DeepSeek answers from raw SSE patch streams.

DeepSeek streams a patch-document: an init object {"v":{"response":{...}}},
path ops {"p":"response/fragments/-1/content","o":"APPEND","v":"..."},
BATCH ops {"p":"response","o":"BATCH","v":[subops]}, and bare {"v":"str"}
continuations at the last path. The old live parser missed BATCH ops (which
carry new fragments incl. the answer head) and mis-tracked the active path.

Usage: recover_deepseek_stream.py <run.jsonl> <raw-completions.json>
Writes <run>_dsfixed.jsonl and prints a report.
"""
import json
import re
import sys


def _resolve(doc, tokens):
    cur = doc
    for i, tok in enumerate(tokens[:-1]):
        nxt = tokens[i + 1]
        idx = -1 if tok == "-1" else (int(tok) if tok.lstrip("-").isdigit() else tok)
        if isinstance(cur, list):
            if idx == -1:
                idx = len(cur) - 1
            while len(cur) <= idx:
                cur.append({})
            if cur[idx] is None:
                cur[idx] = [] if (isinstance(nxt, str) and (nxt.lstrip("-").isdigit())) else {}
            cur = cur[idx]
        else:
            if idx not in cur or cur[idx] is None:
                cur[idx] = [] if (isinstance(nxt, str) and nxt.lstrip("-").isdigit()) else {}
            cur = cur[idx]
    return cur, tokens[-1]


class DsDoc:
    def __init__(self):
        self.root = {}
        self.last_path = None

    def apply(self, path, op, value):
        if path in (None, ""):
            if isinstance(value, dict):
                self.root = value
            return
        tokens = [t for t in path.split("/") if t != ""]
        cont, key = _resolve(self.root, tokens)
        if isinstance(cont, list):
            k = len(cont) - 1 if key == "-1" else int(key)
            while len(cont) <= k:
                cont.append(None)
        else:
            k = key
        old = cont[k] if (isinstance(cont, dict) and k in cont) or (isinstance(cont, list) and k < len(cont)) else None
        if op == "APPEND":
            if isinstance(old, str) and isinstance(value, str):
                cont[k] = old + value
            elif isinstance(old, list) and isinstance(value, list):
                cont[k] = old + value
            elif old is None and isinstance(value, str):
                cont[k] = value
            else:
                cont[k] = value
        else:  # SET / default
            cont[k] = value

    def feed(self, j):
        if not isinstance(j, dict) or "v" not in j:
            return
        path, op, v = j.get("p"), j.get("o"), j["v"]
        if op == "BATCH" and isinstance(v, list):
            for sub in v:
                if isinstance(sub, dict) and "v" in sub:
                    sp = sub.get("p") or ""
                    full = (path + "/" + sp).strip("/") if path else sp
                    self.apply(full, sub.get("o") or "SET", sub["v"])
                    if isinstance(sub["v"], str):
                        self.last_path = full
            return
        if path is None and op is None:
            if isinstance(v, str) and self.last_path:
                self.apply(self.last_path, "APPEND", v)
            elif isinstance(v, dict):
                self.apply("", "SET", v)
                self.last_path = None
            return
        self.apply(path or "", op or "SET", v)
        if isinstance(v, str) and path:
            self.last_path = path

    def answer(self):
        resp = self.root.get("response") if isinstance(self.root, dict) else None
        if isinstance(self.root, dict) and not resp and "fragments" in self.root:
            resp = self.root
        frags = (resp or {}).get("fragments") or []
        parts = [f.get("content") for f in frags
                 if isinstance(f, dict) and f.get("type") == "RESPONSE" and isinstance(f.get("content"), str)]
        return "".join(parts)


def reconstruct(raw):
    doc = DsDoc()
    for ln in raw.split("\n"):
        m = re.match(r"^data:\s?(.*)$", ln)
        if not m:
            continue
        p = m.group(1).strip()
        if not p or p == "[DONE]":
            continue
        try:
            doc.feed(json.loads(p))
        except json.JSONDecodeError:
            continue
    return doc.answer()


def main():
    run_path, raw_path = sys.argv[1], sys.argv[2]
    recs = [json.loads(l) for l in open(run_path)]
    raws = [e for e in json.load(open(raw_path)) if e.get("provider") == "deepseek" and e.get("raw")]
    for e in raws:
        e["_full"] = reconstruct(e["raw"])

    fixed = still = 0
    for r in recs:
        if r["provider"] != "deepseek" or r["status"] != "ok":
            continue
        tail = (r["responseText"] or "")[-80:].strip()
        cands = [e for e in raws if tail and tail in e["_full"] and len(e["_full"]) >= len(r["responseText"])]
        if cands:
            full = cands[0]["_full"]
            if full != r["responseText"]:
                r["responseTextOriginal"] = r["responseText"]
                r["responseText"] = full
                r["textRecovered"] = True
            fixed += 1
        else:
            r["headTruncated"] = True  # raw evicted; needs re-harvest
            still += 1

    out = run_path.replace(".jsonl", "_dsfixed.jsonl")
    with open(out, "w") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"deepseek ok records: recovered/verified {fixed}, unrecoverable (re-harvest) {still}")
    print("wrote", out)


if __name__ == "__main__":
    main()
