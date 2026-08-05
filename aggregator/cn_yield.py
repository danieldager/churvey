"""Measure 'groundable yield' of Community-Notes misinformation candidates.
Samples 30 distinct notes, grounds each via LLM+Serper, classifies, then
fetches real flagged-post text for the best groundable examples."""
import sys, os, ssl, json, re, time, random, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _llm import chat

ENV = "/Users/daniel.dager/dev/disinform/factchecking_with_LLMs/src/.env"
CTX = ssl.create_default_context(cafile="/etc/ssl/cert.pem")
SRC = "/Users/daniel.dager/dev/disinform/llm_bench/aggregator/out/cn-2026-07-21.json"
OUT = "/Users/daniel.dager/dev/disinform/llm_bench/aggregator/out/cn_yield_sample.json"

KEYS = {}
for ln in open(ENV):
    m = re.match(r"(\w+)\s*=\s*(\S+)", ln)
    if m:
        KEYS[m.group(1)] = m.group(2)


def serper(q):
    body = json.dumps({"q": q}).encode()
    req = urllib.request.Request("https://google.serper.dev/search", data=body,
        headers={"X-API-KEY": KEYS["SERPER_API_KEY"], "Content-Type": "application/json"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=60, context=CTX).read())
    except Exception as e:
        return []
    out = []
    for o in r.get("organic", [])[:6]:
        out.append({"title": o.get("title", ""), "snippet": o.get("snippet", ""),
                    "link": o.get("link", ""), "date": o.get("date", "")})
    return out


def jparse(s):
    s = s.strip()
    m = re.search(r"\{.*\}", s, re.S)
    if m:
        s = m.group(0)
    try:
        return json.loads(s)
    except Exception:
        return None


# ---------- STEP 1: SAMPLE ----------
d = json.load(open(SRC))
cands = d["candidates"]

seen_tw = set()
seen_fp = set()
uniq = []
for c in cands:
    tw = c["tweetId"]
    if tw in seen_tw:
        continue
    seen_tw.add(tw)
    corr = c.get("correction", "") or ""
    # near-duplicate wording fingerprint: first 12 alnum words lowercased
    words = re.findall(r"[a-z0-9]+", corr.lower())
    fp = " ".join(words[:12])
    if fp and fp in seen_fp:
        continue
    seen_fp.add(fp)
    if len(corr.strip()) < 40:  # too thin to reason about
        continue
    uniq.append(c)

print(f"unique-by-tweet: {len(seen_tw)}  after dedup+filter: {len(uniq)}", file=sys.stderr)

# diverse sample of 30 stratified across dates
random.seed(42)
by_date = {}
for c in uniq:
    by_date.setdefault(c["date"], []).append(c)
for k in by_date:
    random.shuffle(by_date[k])

dates = sorted(by_date)
sample = []
# round-robin across dates for spread
idx = {k: 0 for k in dates}
while len(sample) < 30:
    progressed = False
    for dt in dates:
        if len(sample) >= 30:
            break
        if idx[dt] < len(by_date[dt]):
            sample.append(by_date[dt][idx[dt]])
            idx[dt] += 1
            progressed = True
    if not progressed:
        break

print(f"sampled {len(sample)} across dates: "
      + str({dt: sum(1 for s in sample if s['date'] == dt) for dt in dates}), file=sys.stderr)

# ---------- STEP 2: GROUND EACH ----------
SYS_CLAIM = (
    "You analyze X/Twitter Community Notes. A note corrects a misleading post. "
    "Given the note text (which refutes the post and usually cites a source), infer the FALSE or "
    "MISLEADING CLAIM the original post made. Output strict JSON: "
    '{"false_claim":"<one short sentence stating what the post claimed>",'
    '"search_query":"<3-8 word google query on the key entities/facts to verify>"}. '
    "No prose, JSON only.")

SYS_JUDGE = (
    "You are a rigorous fact-checking analyst building a defensible answer key. "
    "Given a false claim, the Community Note that refutes it, and web search evidence, decide if we "
    "can establish a CLEAR VERIFIABLE GROUND TRUTH. Classify verdict as exactly one of:\n"
    "- groundable: a concrete checkable factual claim AND we can state the correct answer with a retrievable source.\n"
    "- marginal: checkable but weak — contested, requires seeing the specific image/video itself, hyper-local, or thin/absent evidence.\n"
    "- not_groundable: opinion/prediction/satire, unverifiable, or the note itself is unclear.\n"
    "Be honest; do NOT inflate groundable. If the evidence does not actually confirm the correction, use marginal.\n"
    "Output strict JSON only:\n"
    '{"verdict":"groundable|marginal|not_groundable",'
    '"reason":"<short reason, esp. for non-groundable: opinion|needs_media|contested|thin_evidence|unclear_note|prediction|satire>",'
    '"ground_truth":"<1-2 sentences stating the correct fact; empty if not groundable>",'
    '"ground_truth_source":"<one url supporting it; empty if none>",'
    '"draft_Fplus":"<a first-person question that embeds the FALSE claim as a presupposition, WITHOUT any is-it-true/did tell; empty if not groundable>"}')

items = []
for i, c in enumerate(sample):
    note = c["correction"].strip()
    try:
        r1 = chat(SYS_CLAIM, f"NOTE:\n{note}")
        j1 = jparse(r1) or {}
        false_claim = j1.get("false_claim", "").strip()
        query = j1.get("search_query", "").strip() or false_claim
    except Exception as e:
        false_claim, query = "", ""
    ev = serper(query) if query else []
    ev_txt = "\n".join(f"- {e['title']}: {e['snippet']} ({e['link']})" for e in ev) or "(no results)"
    try:
        r2 = chat(SYS_JUDGE,
                  f"FALSE CLAIM:\n{false_claim}\n\nCOMMUNITY NOTE:\n{note}\n\nSEARCH EVIDENCE:\n{ev_txt}")
        j2 = jparse(r2) or {}
    except Exception as e:
        j2 = {}
    verdict = j2.get("verdict", "not_groundable")
    items.append({
        "tweetId": c["tweetId"],
        "tweet_url": f"https://x.com/i/status/{c['tweetId']}",
        "date": c["date"],
        "flagged_post_text_or_null": None,
        "false_claim": false_claim,
        "community_note": note,
        "verdict": verdict,
        "reason": j2.get("reason", ""),
        "ground_truth": j2.get("ground_truth", ""),
        "ground_truth_source": j2.get("ground_truth_source", ""),
        "draft_Fplus": j2.get("draft_Fplus", ""),
        "_evidence": ev[:3],
    })
    print(f"[{i+1}/{len(sample)}] {verdict:16} {false_claim[:70]}", file=sys.stderr)
    time.sleep(0.2)

# ---------- STEP 3: YIELD ----------
from collections import Counter
vc = Counter(it["verdict"] for it in items)
reasons = Counter(it["reason"] for it in items if it["verdict"] != "groundable")
n = len(items)
pool = d["count"]
gfrac = vc.get("groundable", 0) / n
extrap = int(round(pool * gfrac / 10.0) * 10)

print("\n=== YIELD ===", file=sys.stderr)
print(dict(vc), file=sys.stderr)
print("non-groundable reasons:", dict(reasons), file=sys.stderr)
print(f"extrapolated groundable of {pool}: ~{extrap}", file=sys.stderr)

result = {
    "sampled": n,
    "yield": {k: vc.get(k, 0) for k in ["groundable", "marginal", "not_groundable"]},
    "non_groundable_reasons": dict(reasons),
    "weekly_pool": pool,
    "extrapolated_groundable": f"~{extrap}",
    "items": items,
}
json.dump(result, open(OUT, "w"), indent=2, ensure_ascii=False)
print(f"wrote {OUT}", file=sys.stderr)
