"""Chat isolation: account memory, the isolation canary, and deleting the chats churvey created.

Every question must land in a brand-new temporary chat of an account that remembers nothing. The extension proves the
first per record (`isolation` on each record, docs/isolation.md); this module checks the account side before a run:

  memory   read each account's memory setting (never changed here: `churvey account prepare` switches it off,
           `MEMORY_OFF` says where to do it by hand)
  canary   chat 1 « Retiens ce mot de code : girafe-47 », new chat 2 « Quel mot de code t'ai-je donné ? »:
           PASS if chat 2 knows nothing of it; both chats are deleted afterwards
  purge    delete, through the provider's own delete action, the chats listed in a run folder's chats.jsonl
"""

import json
import pathlib
import re
import time

from . import home

CANARY = ["Retiens ce mot de code : girafe-47. Réponds juste OK.", "Quel mot de code t'ai-je donné ?"]
CANARY_LEAK = re.compile(r"girafe|47", re.I)

# Where a person switches account memory off, by hand. Only `churvey account prepare` changes an account setting.
MEMORY_OFF = {
    "chatgpt": "chatgpt.com > Settings > Personalization > turn off 'Enable memory' (https://chatgpt.com/settings/personalization)",
    "claude": "claude.ai > Settings > Memory > turn off 'Search and reference chats' and 'Generate memory from chats' (https://claude.ai/settings/memory)",
    "gemini": "gemini.google.com > Settings > Personal context > turn off 'Memory' (https://gemini.google.com/saved-info)",
    "grok": "grok.com > Settings > Customize > turn off memory / 'Personalize with memories'",
    "mistral": "Le Chat > profile menu > Settings > Privacy > Personalization > turn off 'Knowledge'",
}
DONE = ("deleted", "not_found", "unsupported")   # a chat in one of these states is not a leftover
# not_found: the provider has no such chat for this account (ChatGPT temporary chats are never addressable by id)


def _launch(plan, out_dir, visible, timeout):
    from .survey import launch_browser as lb
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / ("maintenance-plan.json" if plan.get("task") == "maintenance" else "run-plan.json")
    p.write_text(json.dumps(plan, indent=1, ensure_ascii=False))
    argv = ["--run-plan", str(p), "--profile", str(home.profile_dir()), "--out", str(out_dir), "--timeout", str(timeout)]
    if not visible:
        argv.append("--headless")
    for _ in range(30):   # the previous session's Firefox can take a few seconds to release the profile
        if not lb.profile_in_use(home.profile_dir()):
            break
        time.sleep(1)
    return lb.launch(argv)


def maintain(maintenance, out_dir, visible=False, timeout=600):
    """Run one maintenance plan ({memory: [..], purge: {pid: ids}, list: [..], purgeListed: [..]}); its results dict."""
    rc, state = _launch({"task": "maintenance", "maintenance": maintenance}, out_dir, visible, timeout)
    return state.maintenance or {"error": "the extension never reported back"}


# --- chats churvey created ---------------------------------------------------------------------------------

def _jsonl(p):
    if not p.is_file():
        return []
    return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]


def run_folders(root=None):
    """Every folder under runs/ that holds a chats.jsonl (runs, their preflight/ and _doctor/ subfolders)."""
    root = root or home.runs_dir()
    return sorted({p.parent for p in root.glob("**/chats.jsonl")})


def leftovers(folders):
    """{folder: {pid: [chat ids not yet deleted]}}."""
    out = {}
    for f in folders:
        done = {(r["provider"], r["chat_id"]) for r in _jsonl(f / "purged.jsonl") if r.get("result") in DONE}
        left = {}
        for c in _jsonl(f / "chats.jsonl"):
            if (c["provider"], c["chat_id"]) not in done and c["chat_id"] not in left.get(c["provider"], []):
                left.setdefault(c["provider"], []).append(c["chat_id"])
        if left:
            out[f] = left
    return out


def purge_folders(folders, out_dir, visible=False, only=None):
    """Delete the leftover chats of `folders` (optionally only for providers in `only`). Writes each result to the
    folder the chat came from. Returns {pid: {"deleted": n, "unsupported": n, "failed": n}}."""
    from .survey.launch_browser import write_purged
    todo = leftovers(folders)
    byPid = {}
    for left in todo.values():
        for pid, ids in left.items():
            if only is None or pid in only:
                byPid.setdefault(pid, []).extend(ids)
    if not byPid:
        return {}
    res = maintain({"purge": byPid}, out_dir, visible).get("purge") or {}
    for f, left in todo.items():
        mine = {pid: {cid: res.get(pid, {}).get(cid, "error no result") for cid in ids} for pid, ids in left.items() if pid in byPid}
        write_purged(f, mine)
    return tally(res)


def tally(res):
    """{pid: {id: result}} -> {pid: {deleted, not_found, unsupported, failed}}."""
    return {pid: {"deleted": sum(v == "deleted" for v in r.values()), "not_found": sum(v == "not_found" for v in r.values()),
                  "unsupported": sum(v == "unsupported" for v in r.values()),
                  "failed": sum(v not in DONE for v in r.values())} for pid, r in res.items()}


def describe(v):
    """One line for a tally() entry."""
    parts = [f"deleted {v['deleted']}"]
    if v["not_found"]:
        parts.append(f"{v['not_found']} not found by id (temporary chats the provider does not expose)")
    if v["unsupported"]:
        parts.append(f"{v['unsupported']} cannot be deleted (temporary chats, never in the history)")
    if v["failed"]:
        parts.append(f"{v['failed']} FAILED")
    return ", ".join(parts)


# --- account checks + canary ---------------------------------------------------------------------------------

def canary_verdicts(state, chatbots):
    """pid -> (verdict, detail). PASS needs both chats answered, each in a new temporary chat, and chat 2 free of the code."""
    recs = {}
    for r in (state.manifest or {}).get("records", []):
        recs.setdefault(r["provider"], {})[r["questionId"]] = r
    out = {}
    for pid in chatbots:
        h = (state.health.get(pid) or {}).get("status")
        r1, r2 = recs.get(pid, {}).get("canary1"), recs.get(pid, {}).get("canary2")
        if h not in (None, "ok"):
            out[pid] = (h, (state.health.get(pid) or {}).get("text") or "")
        elif not (r1 and r2 and r1.get("status") == "ok" and r2.get("status") == "ok"):
            bad = next((r for r in (r1, r2) if r and r.get("status") != "ok"), None)
            out[pid] = ("error", (bad or {}).get("errorMessage") or "no answer")
        elif CANARY_LEAK.search(r2.get("responseText") or ""):
            out[pid] = ("FAIL", "chat 2 answered: « " + (r2.get("responseText") or "")[:160].replace("\n", " ") + " »")
        else:
            iso = [r.get("isolation") or {} for r in (r1, r2)]
            same = iso[0].get("chat_id") and iso[0].get("chat_id") == iso[1].get("chat_id")
            if same or not all(i.get("new_chat") and i.get("temporary") for i in iso):
                out[pid] = ("FAIL", "isolation not proven: " + " | ".join(i.get("evidence", "none") for i in iso))
            else:
                out[pid] = ("PASS", "chat 2: « " + (r2.get("responseText") or "")[:100].replace("\n", " ") + " »")
    return out


def check(chatbots, out_dir, visible=False, say=print):
    """Memory status + leftover purge (one browser session), then the canary (a second one, which deletes its chats).
    Returns {pid: {"memory": {status, detail}, "canary": verdict, "canary_detail": str}}."""
    out_dir.mkdir(parents=True, exist_ok=True)
    left = leftovers(run_folders())
    byPid = {}
    for l in left.values():
        for pid, ids in l.items():
            byPid.setdefault(pid, []).extend(ids)
    say(f"Reading account memory settings" + (f" and deleting {sum(len(v) for v in byPid.values())} leftover churvey chats" if byPid else "") + "...")
    from .survey.launch_browser import write_purged
    res = maintain({"memory": list(chatbots), **({"purge": byPid} if byPid else {})}, out_dir / "maintenance", visible)
    for f, l in left.items():
        write_purged(f, {pid: {cid: (res.get("purge") or {}).get(pid, {}).get(cid, "error no result") for cid in ids} for pid, ids in l.items()})
    memory = res.get("memory") or {}

    say("Isolation canary: two separate chats per chatbot (code word, then « what code did I give you? »)...")
    plan = {"providers": list(chatbots), "personas": [], "repetitions": 1,
            "questions": [{"id": "canary1", "text": CANARY[0]}, {"id": "canary2", "text": CANARY[1]}],
            "config": {"private": True, "preflight": True, "purgeAfter": True, "responseTimeoutMs": 120000}}
    _, state = _launch(plan, out_dir / "canary", visible, 600)
    verdicts = canary_verdicts(state, chatbots)
    report = {}
    for pid in chatbots:
        v, d = verdicts.get(pid, ("error", "no result"))
        report[pid] = {"memory": memory.get(pid) or {"status": "unknown", "detail": res.get("error") or "no result"}, "canary": v, "canary_detail": d}
    (out_dir / "isolation.json").write_text(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "report": report}, indent=2, ensure_ascii=False))
    return report


def show(report, say=print):
    say(f"  {'chatbot':9} {'memory':8} {'canary':8} detail")
    for pid, r in report.items():
        m = r["memory"]
        say(f"  {pid:9} {m['status']:8} {r['canary']:8} {r['canary_detail'][:110]}")
        say(f"  {'':9} memory: {m.get('detail', '')}")
    on = [p for p, r in report.items() if r["memory"]["status"] == "on"]
    if on:
        say("")
        say("  !!! ACCOUNT MEMORY IS ON for " + ", ".join(home.LABELS.get(p, p) for p in on) + ". Answers can carry what the account")
        say("  !!! remembers from other chats. Switch it off:  churvey account prepare --chatbots " + ",".join(on))
        say("  !!! (it asks before changing anything), or by hand:")
        for p in on:
            say(f"  !!!   {home.LABELS.get(p, p)}: {MEMORY_OFF[p]}")
    unknown = [p for p, r in report.items() if r["memory"]["status"] == "unknown"]
    if unknown:
        say("  memory setting could not be read for " + ", ".join(unknown) + "; check it by hand:")
        for p in unknown:
            say(f"    {home.LABELS.get(p, p)}: {MEMORY_OFF[p]}")
    for pid, r in report.items():
        if r["canary"] != "PASS":
            say(f"  {home.LABELS.get(pid, pid)} failed the isolation canary ({r['canary']}): {r['canary_detail'][:200]}")
