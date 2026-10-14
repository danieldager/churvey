"""churvey account prepare: make each chatbot account forget everything, through the provider's own settings.

For each account: switch memory / personalisation off and read it back; delete the whole chat history (the provider's
bulk "delete all" where it has one, else one by one) and list it again. Destructive, so it first reads each account
(no change) and prints exactly what it will do, then asks for a typed confirmation. --dry-run stops after the reading.
Never part of `churvey run`, which only refuses to start while memory is on. Log: ~/.churvey/account/prepare_<time>/.
"""

import json
import time
from datetime import datetime

from . import home, isolation as I

CONFIRM = "prepare"
# What account prepare does, per chatbot (the code is in ff/src/content/drivers.js: memoryOff, deleteAllChats).
MEMORY_HOW = {
    "chatgpt": "PATCH /backend-api/settings/account_user_setting feature=sunshine and moonshine value=false (the 'Enable memory' switch); read back from /backend-api/settings/user",
    "claude": "switch off 'Search and reference chats' and 'Generate memory from chats' on claude.ai/settings/memory; read back from /api/account (enabled_saffron*)",
    "gemini": "switch off 'Memory' on gemini.google.com/saved-info (Personal context); read back from the same switch. Gemini Apps Activity is not changed",
    "grok": "POST /rest/user-settings {enableMemory: false}; read back from /rest/user-settings",
    "mistral": "tRPC user.setKnowledgeEnabled {enabled: false} (the 'Knowledge' switch in Settings > Privacy); read back from tRPC user.getKnowledgeToggleState",
}
DELETE_HOW = {
    "chatgpt": "bulk: PATCH /backend-api/conversations {is_visible: false} (Settings > Data controls > Delete all chats)",
    "claude": "one by one: DELETE /api/organizations/<org>/chat_conversations/<id>",
    "gemini": "one by one through each sidebar conversation's menu > Delete (no list or delete API)",
    "grok": "one by one: DELETE /rest/app-chat/conversations/<id> (hard delete), then the same for chats in the trash",
    "mistral": "bulk: tRPC chat.deleteAll (Settings > danger zone > delete all chats)",
}
UNDELETABLE = {"chatgpt": "temporary chats (kept by OpenAI up to 30 days, out of the history) cannot be deleted",
               "gemini": "temporary chats never enter the history and cannot be deleted"}


def plan(chatbots, read):
    """What prepare will do, from the reading: ({pid: {"memory_off": bool, "delete_all": bool}}, lines to print)."""
    acts, lines = {}, []
    who, mem, lst = read.get("whoami") or {}, read.get("memory") or {}, read.get("list") or {}
    for p in chatbots:
        w, m, l = who.get(p) or {}, mem.get(p) or {"status": "unknown", "detail": "no result"}, lst.get(p) or {}
        acct = w.get("account") or ("signed in" if w.get("signedIn") else "NOT signed in" if w.get("signedIn") is False else "account unknown")
        lines.append(f"{home.LABELS.get(p, p)} ({acct})")
        if w.get("signedIn") is False:
            lines.append("  nothing: not signed in (churvey login " + p + ")")
            acts[p] = {"memory_off": False, "delete_all": False}
            continue
        off = m["status"] != "off"
        lines.append(f"  memory: {m['status']} ({m.get('detail', '')})")
        lines.append(f"    -> {'switch it off: ' + MEMORY_HOW[p] if off else 'already off, nothing to do'}")
        if "ids" in l:
            n = len(l["ids"])
            lines.append(f"  chats: {n}" + (" in the sidebar (more may load on scroll)" if p == "gemini" else " in the history"))
            lines.append(f"    -> {'delete ALL of them: ' + DELETE_HOW[p] + '; then list again' if n else 'nothing to delete'}")
        else:
            n = None
            lines.append(f"  chats: could not list ({l.get('error', 'no result')})")
            lines.append(f"    -> try anyway: {DELETE_HOW[p]}; then list again")
        if p in UNDELETABLE:
            lines.append(f"    note: {UNDELETABLE[p]}")
        acts[p] = {"memory_off": off, "delete_all": n != 0}
    return acts, lines


def outcome(chatbots, acts, done):
    """({pid: ok}, lines) from the memoryOff / deleteAll results: ok = memory reads off and the history lists empty."""
    ok, lines = {}, []
    mo, da = done.get("memoryOff") or {}, done.get("deleteAll") or {}
    for p in chatbots:
        a = acts.get(p) or {}
        if not (a.get("memory_off") or a.get("delete_all")):
            continue
        good = True
        lines.append(home.LABELS.get(p, p))
        if a.get("memory_off"):
            r = mo.get(p) or {"error": "no result"}
            after = (r.get("after") or {}).get("status")
            good &= after == "off"
            lines.append(f"  memory: {r['error'] if r.get('error') else (r.get('before') or {}).get('status', '?') + ' -> ' + str(after) + ('  (verified)' if after == 'off' else '  NOT OFF: ' + I.MEMORY_OFF[p])}")
        if a.get("delete_all"):
            r = da.get(p) or {"error": "no result"}
            failed = [v for v in (r.get("results") or {}).values() if v not in I.DONE]
            good &= not r.get("error") and r.get("after") == 0
            lines.append(f"  chats: {r['error']}" if r.get("error") else f"  chats: {r.get('before')} -> {r.get('after')} listed ({r.get('method')})" + (f", {len(failed)} delete errors" if failed else ""))
        ok[p] = good
    return ok, lines


def prepare(chatbots, dry_run=False, visible=False, say=print, ask=input, interactive=True):
    """Read, print the plan, (confirm, act, verify). Exit code: 0 everything verified (or dry run), 1 otherwise."""
    folder = home.root() / "account" / ("prepare_" + datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    folder.mkdir(parents=True, exist_ok=True)
    log = []

    def out(line=""):
        say(line)
        log.append(line)

    out(f"Reading {', '.join(home.LABELS[c] for c in chatbots)}: who is signed in, memory, chat history (nothing is changed)...")
    read = I.maintain({"whoami": list(chatbots), "memory": list(chatbots), "list": list(chatbots)}, folder / "read", visible)
    acts, lines = plan(chatbots, read)
    out()
    for line in lines:
        out(line)
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "chatbots": list(chatbots), "dry_run": dry_run, "read": read, "plan": acts}

    def finish(rc):
        rec["exit_code"] = rc
        (folder / "prepare.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False))
        (folder / "prepare.log").write_text("\n".join(log) + "\n")
        say(f"Log: {folder}")
        return rc

    todo = {p: a for p, a in acts.items() if a["memory_off"] or a["delete_all"]}
    out()
    if not todo:
        out("Nothing to do: every account has memory off and no chats.")
        return finish(0)
    if dry_run:
        out("Dry run: nothing was changed.")
        return finish(0)
    if not interactive:
        out("Not done: account prepare asks for a typed confirmation; run it in a terminal.")
        return finish(1)
    if ask(f"This deletes chat histories and changes account settings, and cannot be undone. Type '{CONFIRM}' to go on: ").strip() != CONFIRM:
        out("Not done.")
        return finish(1)
    rec["confirmed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    out("Switching memory off and deleting chats...")
    done = I.maintain({"memoryOff": [p for p, a in todo.items() if a["memory_off"]], "deleteAll": [p for p, a in todo.items() if a["delete_all"]]},
                      folder / "do", visible, timeout=3600)
    rec["done"] = done
    ok, lines = outcome(chatbots, todo, done)
    out()
    for line in lines:
        out(line)
    rec["verified"] = ok
    return finish(0 if all(ok.values()) else 1)
