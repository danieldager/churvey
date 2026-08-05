"""Fetch real flagged-post text for chosen groundable examples; update JSON."""
import ssl, json, re, urllib.request

ENV = "/Users/daniel.dager/dev/disinform/factchecking_with_LLMs/src/.env"
CTX = ssl.create_default_context(cafile="/etc/ssl/cert.pem")
OUT = "/Users/daniel.dager/dev/disinform/llm_bench/aggregator/out/cn_yield_sample.json"
KEYS = {}
for ln in open(ENV):
    m = re.match(r"(\w+)\s*=\s*(\S+)", ln)
    if m:
        KEYS[m.group(1)] = m.group(2)


def fetch(tid):
    # try twitterapi.io
    try:
        req = urllib.request.Request(
            f"https://api.twitterapi.io/twitter/tweets?tweet_ids={tid}",
            headers={"X-API-Key": KEYS["TWITTERAPI_KEY"]})
        r = json.loads(urllib.request.urlopen(req, timeout=60, context=CTX).read())
        tws = r.get("tweets") or []
        if tws:
            t = tws[0]
            return {"text": t.get("text", ""), "author": t.get("author", {}).get("userName", ""),
                    "url": t.get("url", ""), "likes": t.get("likeCount"), "views": t.get("viewCount"),
                    "src": "twitterapi.io"}
    except Exception as e:
        print("twitterapi err", tid, repr(e)[:120])
    # fallback socialdata.tools
    try:
        req = urllib.request.Request(
            f"https://api.socialdata.tools/twitter/tweets/{tid}",
            headers={"Authorization": f"Bearer {KEYS['SOCIALDATA_API_KEY']}"})
        r = json.loads(urllib.request.urlopen(req, timeout=60, context=CTX).read())
        return {"text": r.get("full_text") or r.get("text", ""),
                "author": (r.get("user") or {}).get("screen_name", ""), "src": "socialdata.tools"}
    except Exception as e:
        print("socialdata err", tid, repr(e)[:120])
    return None


res = json.load(open(OUT))
# choose 6 diverse groundable tweetIds
picks = [
    "Senate advanced the NDAA",
    "E20 fuel",
    "Poor air quality",
    "Nancy Pelosi was subpoenaed",
    "Foreign fake driver",
    "North Korea threatened Israel",
]
by_claim = {it["false_claim"]: it for it in res["items"]}
chosen = []
for p in picks:
    for it in res["items"]:
        if it["verdict"] == "groundable" and p.lower() in it["false_claim"].lower() and it not in chosen:
            chosen.append(it)
            break

for it in chosen:
    f = fetch(it["tweetId"])
    if f and f.get("text"):
        it["flagged_post_text_or_null"] = f["text"]
        it["_flagged_meta"] = f
        print("OK", it["tweetId"], "@" + str(f.get("author")), "::", f["text"][:90].replace("\n", " "))
    else:
        print("FAIL", it["tweetId"], "-> fallback to url+claim")

json.dump(res, open(OUT, "w"), indent=2, ensure_ascii=False)
print("updated", OUT)
print("CHOSEN:", [it["tweetId"] for it in chosen])
