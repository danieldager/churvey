#!/usr/bin/env python3
"""Harvest real question strings people type into Google, via the public
autocomplete endpoint. Free, no API key, stdlib only.

Each civic/political seed is expanded with question-word prefixes so the
completions come back in question form. Dedupes case-insensitively and writes
one dated JSON file per country.

This is the FREE tier of the monthly question aggregator (autocomplete only).
People-Also-Ask and Trends rising-queries are the heavier upgrades.

Usage: python3 aggregator/harvest_questions.py
"""
import json
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ENDPOINT = "http://suggestqueries.google.com/complete/search"

LOCALES = {
    "US": {
        "hl": "en",
        "gl": "us",
        "qwords": ["how", "what", "why", "when", "where", "who",
                   "is", "can", "does", "will"],
        "seeds": [
            "vote in the primary", "immigration", "tariffs",
            "abortion law", "social security", "inflation",
        ],
    },
    "FR": {
        "hl": "fr",
        "gl": "fr",
        "qwords": ["comment", "pourquoi", "quand", "où", "qui",
                   "quel", "est-ce que", "peut-on", "faut-il"],
        "seeds": [
            "voter", "retraite", "immigration", "budget",
            "impôts", "assurance chômage",
        ],
    },
}


def suggest(query, hl, gl):
    """Return Google's autocomplete completions for one query string."""
    params = urllib.parse.urlencode(
        {"client": "firefox", "hl": hl, "gl": gl, "q": query})
    req = urllib.request.Request(
        f"{ENDPOINT}?{params}", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data[1] if len(data) > 1 else []


def harvest(country):
    cfg = LOCALES[country]
    seen = {}
    for seed in cfg["seeds"]:
        prefixes = [seed] + [f"{q} {seed}" for q in cfg["qwords"]]
        for p in prefixes:
            try:
                for s in suggest(p, cfg["hl"], cfg["gl"]):
                    key = s.lower().strip()
                    if key not in seen:
                        seen[key] = {"question": s, "seed": seed}
            except Exception as e:
                print(f"  ! {p!r}: {e}")
            time.sleep(0.25)
    return list(seen.values())


def main():
    stamp = date.today().strftime("%Y-%m")
    outdir = Path(__file__).parent / "out"
    outdir.mkdir(exist_ok=True)
    for country in LOCALES:
        print(f"[{country}] harvesting {len(LOCALES[country]['seeds'])} seeds...")
        rows = harvest(country)
        out = outdir / f"{country}-{stamp}.json"
        out.write_text(json.dumps({
            "country": country,
            "harvested": stamp,
            "source": "google-autocomplete",
            "count": len(rows),
            "items": rows,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {len(rows)} unique queries -> {out}")


if __name__ == "__main__":
    main()
