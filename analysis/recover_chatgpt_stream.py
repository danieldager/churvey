#!/usr/bin/env python3
"""Reconstruct full ChatGPT answers from raw event streams (delta_encoding v1).

The extension's live parser (ff/src/background/capture.js) only handled bare
string deltas, dropping the initial message `add` (answer head) and `patch`
batches (mid-answer holes). The exported *.raw-completions.json files contain
the full streams, so the text is fully recoverable.

Usage:
  python3 recover_chatgpt_stream.py <merged.jsonl> <raw1.json> [<raw2.json> ...]

Writes <merged>_recovered.jsonl next to the input and prints a report.
"""
import json
import re
import sys
from datetime import datetime


# ---------- delta_encoding v1 document reconstruction ----------

def _navigate(doc, tokens):
    """Return (container, key) for a JSON-pointer-ish path; create dicts on the way."""
    cur = doc
    for i, tok in enumerate(tokens[:-1]):
        nxt = tokens[i + 1]
        if isinstance(cur, list):
            idx = int(tok)
            while len(cur) <= idx:
                cur.append({})
            if cur[idx] is None:
                cur[idx] = [] if nxt.isdigit() else {}
            cur = cur[idx]
        else:
            if tok not in cur or cur[tok] is None:
                cur[tok] = [] if nxt.isdigit() else {}
            cur = cur[tok]
    return cur, tokens[-1]


class DeltaDoc:
    """Applies ChatGPT delta_encoding v1 ops onto a message document."""

    def __init__(self):
        self.root = None
        self.last_path = ""
        self.messages = []  # archived completed message roots

    def _apply(self, op, path, value):
        if path == "" or path is None:
            if op == "add":
                # New message root: archive the previous one.
                if self.root is not None:
                    self.messages.append(self.root)
                self.root = value
            elif op == "replace":
                self.root = value
            return
        tokens = [t for t in path.split("/") if t != ""]
        if self.root is None:
            self.root = {}
        cont, key = _navigate(self.root, tokens)
        if isinstance(cont, list):
            idx = int(key)
            if op == "append":
                while len(cont) <= idx:
                    cont.append("")
                if isinstance(cont[idx], str) and isinstance(value, str):
                    cont[idx] += value
                elif isinstance(cont[idx], list) and isinstance(value, list):
                    cont[idx].extend(value)
                else:
                    cont[idx] = value
            elif op in ("add", "replace"):
                while len(cont) <= idx:
                    cont.append(None)
                cont[idx] = value
        else:
            if op == "append":
                old = cont.get(key)
                if isinstance(old, str) and isinstance(value, str):
                    cont[key] = old + value
                elif isinstance(old, list) and isinstance(value, list):
                    cont[key] = old + value
                else:
                    cont[key] = value
            elif op in ("add", "replace"):
                cont[key] = value

    def feed(self, j):
        """One `data:` JSON payload."""
        if not isinstance(j, dict):
            return
        if "type" in j and "v" not in j:
            return  # control frames (markers, moderation, resume tokens)
        op = j.get("o")
        path = j.get("p")
        v = j.get("v")
        if op == "patch" or (op is None and isinstance(v, list) and path is None):
            for sub in v:
                if isinstance(sub, dict):
                    self._apply(sub.get("o") or "append", sub.get("p") or "", sub.get("v"))
                    if sub.get("p"):
                        self.last_path = sub["p"]
            return
        if op is None and path is None:
            if isinstance(v, str):
                # bare append continues at the last explicit path
                self._apply("append", self.last_path or "/message/content/parts/0", v)
            elif isinstance(v, dict):
                self._apply("add", "", v)
                self.last_path = ""
            return
        if path is not None:
            self.last_path = path
        self._apply(op or "append", path or "", v)

    def assistant_text(self):
        """Join text parts of assistant messages; prefer the last 'final' one."""
        roots = self.messages + ([self.root] if self.root is not None else [])
        texts = []
        for r in roots:
            msg = r.get("message") if isinstance(r, dict) else None
            if not isinstance(msg, dict):
                continue
            author = (msg.get("author") or {}).get("role")
            content = msg.get("content") or {}
            if author != "assistant" or content.get("content_type") != "text":
                continue
            parts = content.get("parts") or []
            txt = "".join(p for p in parts if isinstance(p, str))
            if txt.strip():
                texts.append((msg.get("channel"), txt))
        if not texts:
            return ""
        finals = [t for ch, t in texts if ch in (None, "final")]
        return finals[-1] if finals else texts[-1][1]


def reconstruct(raw_stream):
    doc = DeltaDoc()
    for ln in raw_stream.split("\n"):
        m = re.match(r"^data:\s?(.*)$", ln)
        if not m:
            continue
        p = m.group(1).strip()
        if not p or p == "[DONE]":
            continue
        try:
            j = json.loads(p)
        except json.JSONDecodeError:
            continue
        doc.feed(j)
    return doc.assistant_text()


# ---------- pairing raw captures to records ----------

def ts_ms(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000


def main():
    merged_path, raw_paths = sys.argv[1], sys.argv[2:]
    recs = [json.loads(l) for l in open(merged_path)]
    raws = []
    for rp in raw_paths:
        run_id = re.search(r"(run_[\dTZ:-]+?)\.raw", rp).group(1)
        for e in json.load(open(rp)):
            if e.get("provider") == "chatgpt":
                e["_run"] = run_id
                raws.append(e)

    # reconstruct every raw once, then pair records to raws by CONTENT:
    # the stored (buggy) text has holes but its tail is verbatim from the stream,
    # so the right raw is the one whose reconstruction contains that tail.
    for e in raws:
        e["_full"] = reconstruct(e["raw"])

    n_ok = n_fail = n_skip = 0
    for r in recs:
        if r["provider"] != "chatgpt":
            continue
        old = r.get("responseText") or ""
        tail = old[-80:].strip()
        cands = [e for e in raws
                 if e["_run"] == r["runId"] and tail and tail in e["_full"]
                 and len(e["_full"]) >= len(old)]
        if not cands:
            print(f"  MISS {r['questionId']} rep{r['repIndex']}: no raw stream contains this "
                  f"record's tail (raw ring evicted it?)")
            n_skip += 1
            continue
        if len(cands) > 1:  # identical tails across reps — tiebreak by timestamp
            cands.sort(key=lambda e: abs(ts_ms(e["ts"]) - ts_ms(r["timestampEnd"])))
        full = cands[0]["_full"]
        if full != old:
            r["responseTextOriginal"] = old
            r["responseText"] = full
            r["textRecovered"] = True
        n_ok += 1

    out = merged_path.replace(".jsonl", "_recovered.jsonl")
    with open(out, "w") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    fixed = sum(1 for r in recs if r.get("textRecovered"))
    print(f"\nchatgpt records: verified {n_ok} (of which {fixed} repaired), unmatched {n_skip}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
