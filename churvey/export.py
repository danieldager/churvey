"""Clean per-answer JSONL from a run: one row per extension record, the schema the claim pipeline reads.

Ported from llm_bench dashboard/ingest/normalise_run.py (the schema v5/v6 path) and url_canon.py. Fields:
question_id, question_user_fr (the question as asked), provider, model_label_if_visible, response_text,
citations (DISPLAYED citations: url, title, domain, site_name, cited_text, anchor_text/start/end, marker, ref_id,
via, position), displayed_urls, fetched_urls, citation_extraction, citation_extraction_note, text_cleaning,
searched, captured_at, capture_method, raw_record_path, status, error; plus run_id, rep_index, item_key, group and
question_set {name, sha256} from the churvey run folder.
"""

import json
import pathlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import home

FOLLOWUP_RE = re.compile(r'(?:\s*<FollowUp\b(?:\s+\w+="[^"]*")*\s*/>)+\s*$')   # Gemini's trailing suggestion tags
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
TRACK_PARAMS = {"gclid", "dclid", "fbclid", "msclkid", "yclid", "igshid", "srsltid", "ocid", "mc_cid", "mc_eid", "_ga", "_gl"}
STRUCT_VIA = {"gemini_grounding", "gemini_search_panel", "claude_inline", "claude_poll", "claude_search_result", "chatgpt_marker",
              "chatgpt_sources_list", "text_link", "mistral_inline", "mistral_source", "grok_inline", "grok_xpost"}
CITE_KEYS = ("url", "title", "domain", "site_name", "cited_text", "anchor_text", "anchor_start", "anchor_end", "marker", "ref_id", "via")


def canonical_url(u):
    """No #fragment, no tracking params (utm_*, gclid, ...). Twin of `canon` in ff/src/background/citations.js."""
    s = urlsplit(u)
    q = urlencode([(k, v) for k, v in parse_qsl(s.query, keep_blank_values=True)
                   if not (k.lower().startswith("utm") or k.lower() in TRACK_PARAMS)])
    return urlunsplit((s.scheme, s.netloc, s.path, q, ""))


def fetched_urls(urls):
    """Deduped; a bare host root is dropped when a deeper URL on the same host exists."""
    out = []
    for u in urls:
        if u not in out:
            out.append(u)
    deep = {urlsplit(u).netloc for u in out if urlsplit(u).path not in ("", "/")}
    return [u for u in out if urlsplit(u).path not in ("", "/") or urlsplit(u).netloc not in deep]


def normalise(rec, raw_path):
    pid, text = rec["provider"], rec.get("responseText") or ""
    raw = rec.get("citations") or []
    cleaning = None
    if pid == "gemini":
        cleaned = FOLLOWUP_RE.sub("", text)
        if cleaned != text:
            cleaning, text = "stripped trailing <FollowUp label=.. query=../> suggestion tag(s)", cleaned
    cites = []
    for c in raw:
        if c.get("via") in STRUCT_VIA:
            row = {k: c.get(k) for k in CITE_KEYS}
            if row["url"] and canonical_url(row["url"]) != row["url"]:
                row["url_raw"], row["url"] = row["url"], canonical_url(row["url"])
            row["position"] = len(cites)
            cites.append(row)
    for c in raw:
        if c.get("via") == "dom":   # DOM fallback / Gemini chip scrape
            cites.append({**{k: None for k in CITE_KEYS}, "url": c.get("url"), "title": c.get("title"), "via": "dom", "position": len(cites)})
    if not cites and "fetchedUrls" not in rec:   # pre-v5 record: only inline markdown links are recoverable
        cites = [{**{k: None for k in CITE_KEYS}, "url": m.group(2), "anchor_text": m.group(1), "via": "text_link", "position": i}
                 for i, m in enumerate(MD_LINK_RE.finditer(text))]
    displayed = []
    for c in cites:
        u = canonical_url(c.get("url") or "")
        if u and u not in displayed:
            displayed.append(u)
    fetched = fetched_urls([canonical_url(u) for u in rec.get("fetchedUrls") or []])
    unresolved = sum(1 for c in cites if c["via"] == "chatgpt_marker" and not c["url"])
    return {
        "question_id": rec["questionId"],
        "question_user_fr": rec.get("questionText"),
        "provider": pid,
        "model_label_if_visible": rec.get("modelLabel"),
        "response_text": text,
        "citations": cites,
        "displayed_urls": displayed,
        "fetched_urls": fetched,
        "citation_extraction": "structured" if cites else "none",
        "citation_extraction_note": (f"{len(cites)} displayed citation rows ({sorted({c['via'] for c in cites})}); "
                                     f"{unresolved} ChatGPT markers without URL" if cites else "no displayed citations"),
        "text_cleaning": cleaning,
        "searched": bool(cites or fetched),
        "captured_at": rec.get("timestampEnd"),
        "capture_method": rec.get("capture_method"),
        "raw_record_path": f"{raw_path}#recordId={rec.get('recordId')}",
        "status": rec.get("status"),
        "error": rec.get("errorMessage"),
        "run_id": rec.get("runId"),
        "rep_index": rec.get("repIndex"),
        "item_key": rec.get("itemKey"),
    }


def find_run(ref):
    """Run folder for a run id, "latest", a folder, or a records .jsonl. Returns (folder, records file)."""
    p = pathlib.Path(ref).expanduser()
    if ref == "latest":
        runs = sorted((d for d in home.runs_dir().glob("*") if d.is_dir() and not d.name.startswith("_")),
                      key=lambda d: d.stat().st_mtime) if home.runs_dir().is_dir() else []
        if not runs:
            raise SystemExit(f"no runs yet in {home.runs_dir()}")
        p = runs[-1]
    elif not p.exists():
        p = home.runs_dir() / ref
        if not p.exists():
            raise SystemExit(f"no run '{ref}' (looked for a path and for {p})")
    if p.is_file():
        return p.parent, p
    recs = [f for f in sorted(p.glob("*.jsonl")) if f.name != "responses.clean.jsonl"]
    if not recs:
        raise SystemExit(f"{p} holds no records (*.jsonl). Did the run finish?")
    return p, max(recs, key=lambda f: f.stat().st_mtime)


def export(ref, out=None):
    folder, recs_file = find_run(ref)
    meta = {}
    if (folder / "churvey-run.json").is_file():
        meta = json.loads((folder / "churvey-run.json").read_text())
    groups = {}
    if (folder / "questions.json").is_file():
        groups = {q["id"]: q.get("group") for q in json.loads((folder / "questions.json").read_text()).get("questions", [])}
    qset = {"name": meta.get("question_set"), "sha256": meta.get("question_set_sha256")} if meta else None
    rows = []
    for line in recs_file.read_text().splitlines():
        if line.strip():
            r = normalise(json.loads(line), recs_file.name)
            r["group"] = groups.get(r["question_id"])
            r["question_set"] = qset
            rows.append(r)
    out = pathlib.Path(out) if out else folder / "responses.clean.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    return out, rows
