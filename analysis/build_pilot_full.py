#!/usr/bin/env python3
"""Assemble the final complete pilot set (pilot_full.jsonl) from recovered data.

Inputs (in data/chat-probe/):
  pilot_merged_recovered.jsonl        120 records; 12 chatgpt flagged `truncated`
  run_2026-07-10T04-03-55-349Z.jsonl  full run A export (has the trimmed rep2 records)
  *.raw-completions.json              raw streams for runs A and B

Replacements for the 12 truncated chatgpt records:
  - 10 run-A slots <- run A's trimmed rep2 records (their own streams survive in
    the raw ring), text recovered from stream, citations kept from the record.
  - 16.3 run-B slot <- same record, text recovered from its stream (verified by
    fuzzy window match).
  - P1 run-B slot   <- the 04:59:25 stream (a complete different-generation P1
    answer whose record was lost to a retry); citations harvested from its raw.

Also sanitizes ChatGPT UI marker tokens (U+E200 spans: cite/url/map/image_group/
entity) out of every chatgpt responseText, and renumbers reps 0..3 per question.
"""
import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from recover_chatgpt_stream import reconstruct

ASSET_RE = re.compile(
    r"gstatic\.com|googleusercontent|googleapis\.com|schema\.org|w3\.org|images\.openai\.com"
    r"|oaistatic|oaiusercontent|static-rsc|/s2/favicons|deepseek\.com/site-icons|sentry|fonts\."
    r"|\.(?:js|css|woff2?|png|jpe?g|svg|webp|gif|ico)($|\?)", re.I)

S, SEP, E = "", "", ""


def sanitize(t):
    """Strip ChatGPT stream marker spans; keep human-readable content."""
    def repl(m):
        body = m.group(1)
        kind, _, payload = body.partition(SEP)
        if kind == "entity":
            try:
                return json.loads(payload)[1]
            except Exception:
                return ""
        if kind == "url":
            return payload.split(SEP)[0]  # link text; drop the target ref
        return ""  # cite / map / image_group / unknown
    t = re.sub(f"{S}([^{S}{E}]*){E}", repl, t)
    t = t.replace(S, "").replace(E, "").replace(SEP, "")
    return re.sub(r"[ \t]+\n", "\n", t).strip()


def harvest_urls(raw):
    out, seen = [], set()
    for m in re.finditer(r"https?://[^\s\"'\\)<>]+", raw):
        u = re.sub(r"[.,;'\")]+$", "", m.group(0))
        if len(u) > 400 or ASSET_RE.search(u) or u in seen:
            continue
        seen.add(u)
        out.append({"url": u, "title": None, "via": "stream"})
        if len(out) >= 60:
            break
    return out


def windows_match(stored, full, w=30, step=40):
    a, b = sanitize(stored), sanitize(full)
    wins = [a[i:i + w] for i in range(0, max(1, len(a) - w), step)]
    hits = sum(1 for x in wins if x and x in b)
    return hits / max(1, len(wins))


def main():
    d = "."
    recs = [json.loads(l) for l in open(f"{d}/pilot_merged_recovered.jsonl")]
    run_a_full = [json.loads(l) for l in open(f"{d}/run_2026-07-10T04-03-55-349Z.jsonl")]

    # reconstruct all raw chatgpt streams for both runs
    streams = {}  # ts -> (run, raw, full)
    for f, run in [("run_2026-07-10T04-03-55-349Z.raw-completions.json", "A"),
                   ("run_2026-07-10T04-45-08-383Z.raw-completions.json", "B")]:
        for e in json.load(open(f"{d}/{f}")):
            if e.get("provider") == "chatgpt" and e.get("raw"):
                streams[e["ts"]] = (run, e["raw"], reconstruct(e["raw"]))

    # Duplicate-claim repair: if two records recovered to the SAME text, only one
    # generation's stream survived and both tails matched it. The stream belongs to
    # the record whose capture time is closest to the stream's timestamp; the other
    # record lost its stream and goes through the replacement path instead.
    from collections import defaultdict
    by_text = defaultdict(list)
    for r in recs:
        if r["provider"] == "chatgpt" and r.get("textRecovered"):
            by_text[r["responseText"]].append(r)
    from datetime import datetime
    ms = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    for text, g in by_text.items():
        if len(g) < 2:
            continue
        ts = next(t for t, v in streams.items() if v[2] == text)
        g.sort(key=lambda r: abs(ms(r["timestampEnd"]) - ms(ts)))
        for loser in g[1:]:
            print(f"  duplicate claim: {loser['questionId']} rep{loser['repIndex']} loses "
                  f"stream {ts} to rep{g[0]['repIndex']} -> replacement path")
            loser["responseText"] = loser["responseTextOriginal"]
            del loser["responseTextOriginal"], loser["textRecovered"]
            loser["truncated"] = True

    recovered_texts = {r["responseText"] for r in recs if r.get("textRecovered")}
    unclaimed = {ts: v for ts, v in streams.items() if v[2] and v[2] not in recovered_texts}

    out = [r for r in recs if not r.get("truncated")]
    dropped = [r for r in recs if r.get("truncated")]
    used_ts = set()

    def claim(record, min_score=0.5):
        """Find the unclaimed stream matching this record's (buggy) text."""
        best_ts, best = None, 0.0
        for ts, (run, raw, full) in unclaimed.items():
            if ts in used_ts:
                continue
            sc = windows_match(record["responseText"] or "", full)
            if sc > best:
                best_ts, best = ts, sc
        if best_ts and best >= min_score:
            used_ts.add(best_ts)
            return best_ts, unclaimed[best_ts]
        return None, None

    # 1) run-A slots: swap in the trimmed rep2 records, text from their streams
    a_missing = {r["questionId"] for r in dropped if r["runId"].endswith("04-03-55-349Z")}
    rep2 = {r["questionId"]: r for r in run_a_full
            if r["provider"] == "chatgpt" and r["repIndex"] == 2}
    for qid in sorted(a_missing):
        src = rep2.get(qid)
        assert src, f"no rep2 record for {qid} in run A full export"
        ts, hit = claim(src)
        assert hit, f"no stream matched run A rep2 {qid}"
        src = dict(src)
        src["responseTextOriginal"] = src["responseText"]
        src["responseText"] = hit[2]
        src["textRecovered"] = True
        src["replacedSlot"] = "rep0"  # provenance: substitutes the lost rep0 sample
        out.append(src)
        print(f"  run A {qid}: rep2 record + stream {ts} ({len(hit[2])} chars)")

    # 2) 16.3 run-B: same record, recovered text
    b163 = next(r for r in dropped if r["questionId"] == "16.3" and r["runId"].endswith("04-45-08-383Z"))
    ts, hit = claim(b163)
    assert hit, "16.3 run-B stream not matched"
    b163 = dict(b163)
    b163.pop("truncated")
    b163["responseTextOriginal"] = b163["responseText"]
    b163["responseText"] = hit[2]
    b163["textRecovered"] = True
    out.append(b163)
    print(f"  run B 16.3: own stream {ts} ({len(hit[2])} chars)")

    # 3) P1 run-B: different-generation stream; citations harvested from its raw
    bp1 = next(r for r in dropped if r["questionId"] == "P1" and r["runId"].endswith("04-45-08-383Z"))
    (ts, (run, raw, full)), = [(t, v) for t, v in unclaimed.items()
                               if t not in used_ts and v[0] == "B"]
    assert "August 4, 2026" in full and "line" in full, "leftover run-B stream is not a P1 answer"
    used_ts.add(ts)
    bp1 = dict(bp1)
    bp1.pop("truncated")
    bp1["responseTextOriginal"] = bp1["responseText"]
    bp1["responseText"] = full
    bp1["citations"] = harvest_urls(raw)
    bp1["textRecovered"] = True
    bp1["replacedSlot"] = "different generation (record lost to retry eviction)"
    out.append(bp1)
    print(f"  run B P1: stream {ts} ({len(full)} chars, {len(bp1['citations'])} citations)")

    # 4) sanitize all chatgpt texts; keep the raw reconstruction when it differs.
    # Also tag Google Maps place links (ChatGPT map-widget artifacts, not sources)
    # so graders exclude them from citation checks.
    for r in out:
        if r["provider"] != "chatgpt":
            continue
        for c in r.get("citations") or []:
            if re.match(r"https?://(www\.)?google\.com/maps/", c["url"]):
                c["via"] = "map-widget"
        clean = sanitize(r["responseText"])
        if clean != r["responseText"]:
            r["responseTextRaw"] = r["responseText"]
            r["responseText"] = clean

    # 5) renumber reps 0..3 per provider+question, chronological
    from collections import defaultdict
    groups = defaultdict(list)
    for r in out:
        groups[(r["provider"], r["questionId"])].append(r)
    for (prov, qid), g in groups.items():
        assert len(g) == 4, f"{prov} {qid}: {len(g)} records (want 4)"
        g.sort(key=lambda r: (r["runId"], r["timestampStart"]))
        for i, r in enumerate(g):
            r["repIndex"] = i
            r["itemKey"] = f"neutral#r{i}#{qid}"

    # 6) validate + write
    assert len(out) == 120
    texts = [r["responseText"] for r in out if r["provider"] == "chatgpt"]
    assert len(texts) == len(set(texts)), "duplicate chatgpt texts remain"
    for r in out:
        t = r["responseText"]
        assert t and len(t) > 100, f"short text: {r['provider']} {r['questionId']}"
        assert S not in t and E not in t and SEP not in t, "marker chars remain"
    out.sort(key=lambda r: (r["provider"], str(r["questionId"]), r["repIndex"]))
    with open(f"{d}/pilot_full.jsonl", "w") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_rec = sum(1 for r in out if r.get("textRecovered"))
    print(f"\nwrote pilot_full.jsonl: {len(out)} records "
          f"(60 chatgpt / 60 claude, 4 per question; {n_rec} chatgpt texts stream-recovered)")


if __name__ == "__main__":
    main()
