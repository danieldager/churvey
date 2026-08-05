#!/usr/bin/env python3
"""fetch_community_notes.py — pull TODAY's X Community Notes and surface fresh
candidate misinformation on a topic. The DAILY lane (Google Fact Check API is the
slower, professionally-vetted lane).

Public bulk data, no auth, plain download:
  ton.twimg.com/birdwatch-public-data/YYYY/MM/DD/notes/notes-*.zip   (zipped TSV)
The largest shard (~450MB) is the comprehensive file where most recent notes live, so
we download ALL shards and dedup by noteId, then filter to classification=MISINFORMED,
recent, + a topic keyword.

We do NOT require CURRENTLY_RATED_HELPFUL. Fresh notes lag in reaching that status
(measured: of 63 recent immigration notes, only 1 was HELPFUL) — requiring it throws
away exactly the current material we want. The item pipeline verifies each candidate
downstream (grounding/retrieval), so the note is a *candidate* + a first-pass
correction, not trusted ground truth.

Each note gives: the correction (summary), the noted tweetId (fetch the tweet text
via the X API for the exact false claim), and source links in the summary.

Usage: python3 aggregator/fetch_community_notes.py ["topic-regex"] [--days N]
Default: immigration/ICE/deport..., last 45 days.
"""
import csv
import datetime
import io
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://ton.twimg.com/birdwatch-public-data"
CTX = ssl.create_default_context(cafile="/etc/ssl/cert.pem")  # system py3.14 has no default CA
UA = {"User-Agent": "Mozilla/5.0"}
DEFAULT_KW =r'\b(ICE|immigration|immigrants?|deport\w*|detain\w*|detention|migrants?|asylum|undocumented|border patrol)\b'


def _get(url, method="GET", timeout=120):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA, method=method), timeout=timeout, context=CTX)


def latest_snapshot():
    """Today's release path, walking back up to 5 days if not yet published (best-effort daily)."""
    day = datetime.date.today()
    for _ in range(5):
        try:
            if _get(f"{BASE}/{day:%Y/%m/%d}/notes/notes-00000.zip", "HEAD", 20).status == 200:
                return day
        except Exception:
            pass
        day -= datetime.timedelta(days=1)
    raise SystemExit("no recent Community Notes snapshot found")


def notes_rows(day):
    """Stream all shards (the ~450MB shard holds most recent notes, so no size skip);
    the caller dedups by noteId."""
    for i in range(30):
        url = f"{BASE}/{day:%Y/%m/%d}/notes/notes-{i:05d}.zip"
        try:
            data = _get(url, timeout=600).read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                break  # no more shards
            raise
        z = zipfile.ZipFile(io.BytesIO(data))
        with z.open(z.namelist()[0]) as fh:
            yield from csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8"), delimiter="\t")


def main():
    args = sys.argv[1:]
    kw = re.compile(args[0], re.I) if args and not args[0].startswith("--") else re.compile(DEFAULT_KW, re.I)
    days = int(args[args.index("--days") + 1]) if "--days" in args else 45
    floor = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=days)).timestamp() * 1000

    day = latest_snapshot()
    cands = []
    seen = set()
    for row in notes_rows(day):
        nid = row.get("noteId")
        if not nid or nid in seen:
            continue
        seen.add(nid)
        if "MISINFORMED" not in (row.get("classification") or ""):
            continue
        try:
            t = int(row["createdAtMillis"])
        except (KeyError, ValueError):
            continue
        if t < floor:
            continue
        s = row.get("summary") or ""
        if not kw.search(s):
            continue
        cands.append({
            "noteId": row["noteId"], "tweetId": row["tweetId"], "createdMs": t,
            "date": datetime.datetime.fromtimestamp(t / 1000, datetime.UTC).date().isoformat(),
            "factualError": row.get("misleadingFactualError"), "correction": s,
        })
    cands.sort(key=lambda c: -c["createdMs"])

    out = Path(__file__).parent / "out" / f"cn-{day:%Y-%m-%d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"snapshot": str(day), "topic": kw.pattern,
                               "count": len(cands), "candidates": cands},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{day}] {len(cands)} fresh MISLEADING notes on topic (last {days}d) -> {out}")
    for c in cands[:5]:
        print(f"  [{c['date']}] tweet {c['tweetId']}: {c['correction'][:110].strip()}")


if __name__ == "__main__":
    main()
