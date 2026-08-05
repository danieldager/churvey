#!/usr/bin/env python3
"""Pull the month's salient political TOPICS per region, one high-quality
monthly source each, via fetch -> LLM extraction into a ranked list.

Sources (one per region, monthly resolution):
  US    - Gallup "Most Important Problem"        (JS-embedded -> Selenium render)
  FR    - Ipsos "Ce qui preoccupe les Francais"  (HTML)
  World - Ipsos "What Worries the World"          (DEFERRED: full ranking + % is
          PDF-only; HTML gives no usable ranking. Add PDF parsing later.)

Output: aggregator/out/topics-<REGION>-<YYYY-MM>.json

Run with the venv python (needs selenium for the US source):
  aggregator/.venv/bin/python aggregator/fetch_topics.py
"""
import json
import re
import urllib.request
from datetime import date
from pathlib import Path

from _llm import chat

SOURCES = {
    "US": {
        "url": "https://news.gallup.com/poll/1675/most-important-problem.aspx",
        "render": "selenium",
        "ask": "the most important problem facing the country as named by Americans (Gallup MIP); use the most recent month's column",
    },
    "FR": {
        "url": "https://www.ipsos.com/fr-fr/ce-qui-preoccupe-les-francais",
        "render": "http",
        "ask": "the issues that most worry the French this month (Ipsos), keep the French issue labels",
    },
    # World (Ipsos "What Worries the World") deferred: full global ranking + % is
    # in the monthly PDF only; the HTML page yields no usable ranking. Add a PDF
    # parsing path here later.
}

SYS = (
    "You extract a ranked list of the most salient political/social ISSUES from a "
    "pollster's web page. Return ONLY minified JSON, no prose, no code fence:\n"
    '{"month":"<as stated e.g. June 2026 or null>","items":[{"rank":1,"issue":"...","pct":<number or null>}]}\n'
    "Use the issue labels as the source states them. Rank by the stated percentage, "
    "highest first. If the page contains no usable ranking, return "
    '{"month":null,"items":[]}.'
)


def fetch_http(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def fetch_selenium(url):
    import time
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    opts = Options()
    opts.add_argument("--headless=new")
    driver = webdriver.Chrome(options=opts)
    try:
        driver.get(url)
        time.sleep(6)  # let embeds render
        parts = [driver.page_source]
        for fr in driver.find_elements("tag name", "iframe"):
            try:
                driver.switch_to.frame(fr)
                parts.append(driver.find_element("tag name", "body").text)
            except Exception:
                pass
            finally:
                driver.switch_to.default_content()
        return "\n".join(parts)
    finally:
        driver.quit()


def to_text(html):
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    txt = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", txt).strip()


def extract(region):
    s = SOURCES[region]
    raw = fetch_selenium(s["url"]) if s["render"] == "selenium" else fetch_http(s["url"])
    txt = to_text(raw)[:12000]
    out = chat(SYS, f"SOURCE PAGE (region {region}; extract {s['ask']}):\n\n{txt}").strip()
    out = re.sub(r"^```(?:json)?\s*|\s*```$", "", out).strip()
    data = json.loads(out)
    data.update(region=region, source=s["url"])
    return data


def main():
    stamp = date.today().strftime("%Y-%m")
    outdir = Path(__file__).parent / "out"
    outdir.mkdir(exist_ok=True)
    for region in SOURCES:
        print(f"[{region}] {SOURCES[region]['url']}")
        try:
            data = extract(region)
            (outdir / f"topics-{region}-{stamp}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  month={data.get('month')}  {len(data.get('items', []))} issues")
            for it in data.get("items", [])[:8]:
                print(f"    {it.get('rank')}. {it.get('issue')} ({it.get('pct')})")
        except Exception as e:
            print(f"  ! FAILED: {type(e).__name__}: {str(e)[:180]}")


if __name__ == "__main__":
    main()
