"""churvey probe: does every action churvey needs still work on every chatbot, and what changed since last time?

One check per chatbot per capability (CHECKS). Two Firefox sessions:

  1. no message sent (ff/src/background/probe.js): sign-in state, the selectors the driver uses on the home page and in
     a new temporary chat, the endpoints it reads, the limit-banner detector, the memory setting and its switches, the
     chat list. With --destructive the memory is also switched off and read back.
  2. three messages per signed-in chatbot (the isolation canary's two, and one question that needs web search), run
     by the ordinary runner with config.probe: submit, capture (stream / poll), what the DOM fallback would have read,
     citations, deleting the chats afterwards.

Each check is PASS / FAIL / SKIP (could not be tried: signed out, rate limited) / N/A (not how this chatbot works),
and PASS becomes CHANGED when what the check depends on (its fingerprint: selectors matched, endpoint shapes, button
labels, capture method) differs from the previous probe. Results: ~/.churvey/probes/<date>/report.md + report.json,
and a PNG for each failed check that has one.
"""

import base64
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime

from . import home, isolation as I

CHECKS = [
    ("logged_in", "signed-in detection (account endpoint and page agree)"),
    ("new_chat", "new chat"),
    ("temporary_chat", "temporary / private chat, with its evidence"),
    ("submit", "type and submit a question"),
    ("stream_capture", "answer captured from the network stream"),
    ("poll_capture", "answer read back from the conversation endpoint"),
    ("dom_fallback", "the DOM fallback reads the same answer off the page"),
    ("citations", "citations parsed"),
    ("banner_detection", "limit / login / challenge banner detection"),
    ("memory_readable", "account memory setting readable"),
    ("memory_toggle", "memory switch found (and, with --destructive, switched off and read back)"),
    ("delete_one", "delete one chat (the probe's own)"),
    ("delete_all_available", "list the whole history (what delete-all works from)"),
    ("canary", "isolation canary"),
]
# How each chatbot's answers are captured today (docs/capture_robustness.md). Grok's private chats are not stored on
# the server (load-responses returns an empty message), so their answers come off the page.
CAPTURE = {"chatgpt": "stream", "gemini": "stream", "mistral": "stream", "claude": "poll", "grok": "dom_fallback"}
CITE_Q = {"id": "probe_cite", "text": "Quelles sont les dernières actualités de la ville de Vierzon ? Donne tes sources avec leurs liens."}
QUESTIONS = [{"id": "canary1", "text": I.CANARY[0]}, {"id": "canary2", "text": I.CANARY[1]}, CITE_Q]   # at most 3 messages per chatbot
SUBMIT_ERR = re.compile(r"submit|composer|waitFor|not ready|type", re.I)
# Where a failed check's picture comes from: a page of the no-message session, or the failed record (None).
SHOT = {"logged_in": "home", "banner_detection": "home", "delete_all_available": "home", "memory_readable": "settings",
        "new_chat": "temporary", "temporary_chat": "temporary", "memory_toggle": "settings"}
LABEL_CHECK = [(re.compile(r"temporar|incognito|private|priv[ée]", re.I), "temporary_chat"), (re.compile(r"new chat|nouveau", re.I), "new_chat"),
               (re.compile(r"memory|m[ée]moire", re.I), "memory_toggle"), (re.compile(r"delete|supprimer", re.I), "delete_all_available"),
               (re.compile(r"send|envoyer|submit|stop", re.I), "submit")]
SELECTOR_CHECK = {"composer": "submit", "send": "submit", "newChat": "new_chat", "turns": "new_chat", "sidebar": "new_chat"}


def probes_dir():
    return home.root() / "probes"


# --- turning raw observations into checks ---------------------------------------------------------------------

def _words(t):
    return set(w for w in re.findall(r"\w{3,}", (t or "").lower()))


def overlap(a, b):
    """Share of the smaller text's words found in the other (0..1): the DOM's text against the captured text."""
    A, B = _words(a), _words(b)
    if A and B:
        return len(A & B) / min(len(A), len(B))
    n = lambda t: " ".join((t or "").lower().split())   # a one-word answer ("OK"): containment
    return 1.0 if n(a) and n(b) and (n(a) in n(b) or n(b) in n(a)) else 0.0


def _err(x):
    return isinstance(x, dict) and "error" in x


def assemble(pid, raw, recs, purge, health, canary, destructive=False):
    """One chatbot's checks and fingerprint from the probe session (`raw`), the message session's records, the purge
    results of its chats ({chat_id: result}), its health ({status, text}) and its canary verdict ((verdict, detail))."""
    checks, fp = {}, {name: {} for name, _ in CHECKS}

    def put(name, status, detail, **evidence):
        checks[name] = {"status": status, "detail": detail, "evidence": {k: v for k, v in evidence.items() if v is not None}}

    raw = raw or {}
    # signed in?
    ls, page = (raw.get("login") or {}).get("state") or {}, (raw.get("login") or {}).get("page") or {}
    signed = None if _err(ls) else ls.get("signedIn")
    pstate = page.get("state")
    if _err(raw.get("open")) or not raw:
        put("logged_in", "FAIL", "the page never became ready: " + (raw.get("open") or {}).get("error", "no result"))
    elif pstate == "challenge":
        put("logged_in", "FAIL", "the page shows a security check: " + (page.get("text") or ""), page=page)
    elif signed is True and pstate != "logged_out":
        put("logged_in", "PASS", "signed in" + (f" as {ls['account']}" if ls.get("account") else ""), endpoint=ls.get("how"), page=pstate)
    elif signed is False and pstate == "logged_out":
        put("logged_in", "PASS", "signed out (endpoint and page agree)", endpoint=ls.get("how"), page=page.get("text"))
    else:
        put("logged_in", "FAIL", f"endpoint says signed in={signed}, page says {pstate}", endpoint=ls.get("how") or ls.get("error"), page=page)
    if signed is not None:
        fp["logged_in"]["signed_in"] = signed
    signed_in = signed is True and checks["logged_in"]["status"] == "PASS"
    blocked = (health or {}).get("status") not in (None, "ok")
    need = "needs a signed-in account"

    def skip_reason():
        if not signed_in:
            return need
        if blocked:
            return f"{health['status']}: {(health.get('text') or '')[:120]}"
        return None

    # selectors and labels, by the check that depends on them
    for stage, key in (("home", "home"), ("temp", "temporary")):
        f = (raw.get(key) or {}).get("fingerprint") or {}
        if _err(f) or not f:
            continue
        for k, sel in (f.get("selectors") or {}).items():
            fp[SELECTOR_CHECK.get(k, "temporary_chat")][f"{stage}.{k}"] = sel
        for lab in f.get("labels") or []:
            chk = next((c for r, c in LABEL_CHECK if r.search(lab)), None)
            if chk:
                fp[chk].setdefault(f"labels.{stage}", []).append(lab)
    for c in fp.values():
        for k, v in c.items():
            if isinstance(v, list):
                c[k] = " | ".join(sorted(set(v)))

    # new chat / temporary chat: what isolationState said before anything was typed
    for name, key, field in (("new_chat", "new_chat", "newChat"), ("temporary_chat", "temporary", "temporary")):
        o = raw.get(key) or {}
        st = o.get("state") or {}
        if o.get("error") or not st.get("ok"):
            why = o.get("error") or st.get("error") or "no isolation state"
            put(name, "SKIP" if not signed_in else "FAIL", why if signed_in else f"{need} ({why})", url=o.get("url"))
        elif st.get(field):
            put(name, "PASS", st.get("evidence", ""), url=o.get("url"))
        else:
            put(name, "SKIP" if not signed_in else "FAIL", ("" if signed_in else need + ": ") + st.get("evidence", ""), url=o.get("url"))

    # the three messages
    ok = [r for r in recs if r.get("status") == "ok"]
    bad = [r for r in recs if r.get("status") != "ok"]
    why = skip_reason()
    if not recs:
        for name in ("submit", "stream_capture", "poll_capture", "dom_fallback", "citations"):
            put(name, "SKIP", why or "no message was sent")
    else:
        sub_err = [r for r in bad if SUBMIT_ERR.search(r.get("errorMessage") or "")]
        if ok:
            put("submit", "PASS", f"{len(ok)}/{len(recs)} questions answered")
        elif sub_err:
            put("submit", "FAIL", sub_err[0]["errorMessage"][:200], record=sub_err[0].get("itemKey"))
        else:
            put("submit", "SKIP" if why else "FAIL", why or (bad[0].get("errorMessage") or "no answer")[:200])
        methods = sorted({r.get("capture_method") or "stream" for r in ok})
        want = CAPTURE.get(pid)
        if methods:
            fp["stream_capture" if want == "stream" else "poll_capture" if want == "poll" else "dom_fallback"]["methods"] = ",".join(methods)
        for name, m in (("stream_capture", "stream"), ("poll_capture", "poll")):
            if want != m:
                put(name, "N/A", f"{home.LABELS.get(pid, pid)} answers are captured by {want}")
            elif not ok:
                put(name, "SKIP" if why else "FAIL", why or "no answer landed")
            elif m in methods:
                put(name, "PASS", f"{sum((r.get('capture_method') or 'stream') == m for r in ok)}/{len(recs)} answers by {m}")
            else:
                put(name, "FAIL", f"answers landed by {', '.join(methods)}, none by {m}")
        doms = [((r.get("probe") or {}).get("dom") or {}, r) for r in ok]
        if want == "dom_fallback":
            put("dom_fallback", "PASS" if "dom_fallback" in methods else "FAIL",
                f"{sum((r.get('capture_method') == 'dom_fallback') for r in ok)} answers read off the page (the main path for {home.LABELS.get(pid, pid)})")
        elif not ok:
            put("dom_fallback", "SKIP" if why else "FAIL", why or "no answer to compare")
        else:
            scores = [round(overlap(d.get("text"), r.get("responseText")), 2) for d, r in doms]
            good = [s for s in scores if s >= 0.6]
            put("dom_fallback", "PASS" if len(good) == len(scores) else "FAIL",
                f"page text vs captured answer, word overlap {scores} (pass >= 0.6)", dom_chars=[d.get("len") for d, _ in doms])
        cite = next((r for r in recs if r.get("questionId") == CITE_Q["id"]), None)
        if not cite or cite.get("status") != "ok":
            put("citations", "SKIP" if why else "FAIL", why or ("the source question got no answer: " + ((cite or {}).get("errorMessage") or "not asked"))[:200])
        else:
            urls = [c["url"] for c in cite.get("citations") or [] if c.get("url")]
            shown = len(((cite.get("domSources") or {}).get("links")) or [])
            fp["citations"]["parsed"] = bool(urls)
            if urls:
                put("citations", "PASS", f"{len(urls)} citations with a URL (page shows {shown} links)", first=urls[:3])
            else:
                put("citations", "FAIL", f"no citation parsed; the page shows {shown} source links" + (" (did it search the web?)" if not shown else ""))

    # banner detector
    b = raw.get("banner") or {}
    if _err(b) or not b:
        put("banner_detection", "FAIL", "banner test did not run: " + b.get("error", "no result"))
    elif (b.get("during") or {}).get("banner"):
        put("banner_detection", "PASS", f"a test limit banner was detected; the page itself says {(b.get('before') or {}).get('state')}",
            page=b.get("before"))
    else:
        put("banner_detection", "FAIL", "a test limit banner put on the page was NOT detected", during=b.get("during"))

    # memory
    shapes = raw.get("shapes") or {}
    if not _err(shapes):
        for k, v in shapes.items():
            fp["memory_readable" if k == "memory" else "delete_all_available"][f"endpoint.{k}"] = v
    m = raw.get("memory") or {}
    if m.get("status") in ("on", "off"):
        put("memory_readable", "PASS", f"memory {m['status']}: {m.get('detail', '')}")
    else:
        put("memory_readable", "SKIP" if not signed_in else "FAIL", ("" if signed_in else need + ": ") + (m.get("detail") or "no result"))
    ctl = raw.get("controls") or {}
    off = raw.get("memoryOff") or {}
    sw = ctl.get("switches") if not _err(ctl) else None
    if sw:
        fp["memory_toggle"]["switches"] = " | ".join(sorted(s["label"][:60] for s in sw))
    if destructive and signed_in:
        if off.get("error"):
            put("memory_toggle", "FAIL", off["error"])
        elif (off.get("after") or {}).get("status") == "off":
            put("memory_toggle", "PASS" if off.get("action") != "already off" else "SKIP",
                "switched off and read back off" if off.get("action") != "already off" else "already off: the switch was not exercised", action=off.get("action"))
        else:
            put("memory_toggle", "FAIL", f"after switching off, memory reads {(off.get('after') or {}).get('status')}", action=off.get("action"))
    elif not signed_in:
        put("memory_toggle", "SKIP", need)
    elif _err(ctl):
        put("memory_toggle", "FAIL", "settings page: " + ctl["error"])
    elif ctl.get("needs"):
        put("memory_toggle", "FAIL", f"the settings page {ctl['needs']} did not open (redirected elsewhere)")
    elif sw is None:   # no settings page: the toggle is an API call (grok)
        f = fp["memory_readable"].get("endpoint.memory", "")
        put("memory_toggle", "PASS" if ":boolean" in f else "FAIL", f"API toggle (dry run, not called): setting field {f or 'not seen'}")
    elif not sw:
        put("memory_toggle", "FAIL", "no memory switch found on the settings page")
    else:
        on = any(s["checked"] for s in sw)
        agree = m.get("status") not in ("on", "off") or on == (m["status"] == "on")
        put("memory_toggle", "PASS" if agree else "FAIL",
            f"dry run: switches {', '.join(s['label'][:40] + ('=on' if s['checked'] else '=off') for s in sw)}" + ("" if agree else f"; but the setting reads {m.get('status')}"))

    # deleting
    if purge:
        res = list(purge.values())
        if "deleted" in res:
            put("delete_one", "PASS", f"{res.count('deleted')} of the probe's chats deleted")
        elif all(v == "unsupported" for v in res):
            put("delete_one", "N/A", "temporary chats cannot be deleted on this chatbot (kept by the provider, out of the history)")
        else:
            put("delete_one", "FAIL", ", ".join(sorted(set(res)))[:200])
    else:
        put("delete_one", "SKIP", why or "no chat to delete")
    lst = raw.get("list") or {}
    if "count" in lst:
        put("delete_all_available", "PASS", f"history lists {lst['count']} chats")
    else:
        put("delete_all_available", "SKIP" if not signed_in else "FAIL", ("" if signed_in else need + ": ") + (lst.get("error") or "no result"))

    v, d = canary or (None, None)
    if v == "PASS":
        put("canary", "PASS", d)
    elif v is None or not recs:
        put("canary", "SKIP", why or "not run")
    elif v in ("FAIL", "error") and not why:
        put("canary", "FAIL", d)
    else:
        put("canary", "SKIP", why or f"{v}: {d}")

    return {"signed_in": signed_in, "account": ls.get("account") if not _err(ls) else None,
            "checks": {n: checks[n] for n, _ in CHECKS}, "fingerprint": {k: v for k, v in fp.items() if v}}


# --- month to month ------------------------------------------------------------------------------------------

def diff_fingerprints(old, new):
    """[{chatbot, check, key, old, new}] for every fingerprint value that differs. A check is compared only when both
    probes observed it (a chatbot signed out this month does not report everything as gone)."""
    out = []
    for pid, n in (new or {}).items():
        o = (old or {}).get(pid) or {}
        for chk, nv in (n.get("fingerprint") or {}).items():
            ov = (o.get("fingerprint") or {}).get(chk)
            if not ov or not nv:
                continue
            for k in sorted(set(ov) | set(nv)):
                if ov.get(k) != nv.get(k):
                    out.append({"chatbot": pid, "check": chk, "key": k, "old": ov.get(k), "new": nv.get(k)})
    return out


def mark_changed(results, changes):
    """A PASS whose fingerprint moved becomes CHANGED (it still works, but not the way it did)."""
    for c in changes:
        chk = results[c["chatbot"]]["checks"].get(c["check"])
        if chk and chk["status"] == "PASS":
            chk["status"] = "CHANGED"


def previous(current_dir):
    """The latest earlier probe folder with a report.json, or None."""
    root = current_dir.parent
    older = sorted(p for p in root.iterdir() if p.is_dir() and p.name < current_dir.name and (p / "report.json").is_file()) if root.is_dir() else []
    return older[-1] if older else None


def counts(results):
    n = {}
    for r in results.values():
        for c in r["checks"].values():
            n[c["status"]] = n.get(c["status"], 0) + 1
    return n


def render_report(rep):
    """report.json -> report.md."""
    res, pids = rep["results"], list(rep["results"])
    L = [f"# churvey probe, {rep['date']}", ""]
    L.append(f"Chatbots: {', '.join(home.LABELS.get(p, p) for p in pids)}. Destructive: {'yes' if rep.get('destructive') else 'no'}. "
             f"Messages sent: {rep.get('messages', 0)}. Previous probe: {rep.get('previous') or 'none'}.")
    L.append("")
    L.append("Totals: " + ", ".join(f"{k} {v}" for k, v in sorted(counts(res).items())))
    L += ["", "| check | " + " | ".join(home.LABELS.get(p, p) for p in pids) + " |", "|---|" + "---|" * len(pids)]
    for name, _ in CHECKS:
        L.append(f"| {name} | " + " | ".join(f"**{s}**" if s in ("FAIL", "CHANGED") else s for s in (res[p]["checks"][name]["status"] for p in pids)) + " |")
    L += ["", f"## Changed since {rep.get('previous') or 'the previous probe'}", ""]
    if rep.get("changes"):
        for c in rep["changes"]:
            L.append(f"- {home.LABELS.get(c['chatbot'], c['chatbot'])} · {c['check']} · `{c['key']}`: `{c['old']}` → `{c['new']}`")
    else:
        L.append("Nothing." if rep.get("previous") else "No earlier probe to compare with: this one is the baseline.")
    fails = [(p, n, c) for p in pids for n, c in res[p]["checks"].items() if c["status"] == "FAIL"]
    L += ["", "## Failures", ""]
    L += [f"- {home.LABELS.get(p, p)} · {n}: {c['detail']}" + (f" ([screenshot]({c['evidence']['screenshot']}))" if c["evidence"].get("screenshot") else "") for p, n, c in fails] or ["None."]
    for p in pids:
        r = res[p]
        L += ["", f"## {home.LABELS.get(p, p)}" + (f" ({r['account']})" if r.get("account") else ""), "", "| check | status | detail |", "|---|---|---|"]
        for name, c in r["checks"].items():
            L.append(f"| {name} | {c['status']} | {str(c['detail']).replace('|', '/')[:300]} |")
    L += ["", "Checks: " + "; ".join(f"`{n}` {d}" for n, d in CHECKS) + ".",
          "SKIP = could not be tried (signed out, rate limited, no message sent); N/A = not how this chatbot works.", ""]
    return "\n".join(L)


def summary_lines(rep, out_dir):
    res, pids = rep["results"], list(rep["results"])
    L = ["  " + f"{'check':22}" + "".join(f"{home.LABELS.get(p, p)[:9]:10}" for p in pids)]
    for name, _ in CHECKS:
        L.append("  " + f"{name:22}" + "".join(f"{res[p]['checks'][name]['status']:10}" for p in pids))
    L.append("  " + ", ".join(f"{k} {v}" for k, v in sorted(counts(res).items())))
    for c in rep.get("changes") or []:
        L.append(f"  CHANGED {home.LABELS.get(c['chatbot'], c['chatbot'])} {c['check']} {c['key']}: {c['old']} -> {c['new']}")
    L.append(f"  Report: {out_dir / 'report.md'}")
    return L


# --- running it ----------------------------------------------------------------------------------------------

def _save_png(data, path):
    if isinstance(data, str) and data.startswith("data:image/png;base64,"):
        path.write_bytes(base64.b64decode(data.split(",", 1)[1]))
        return True
    return False


def new_dir():
    d = probes_dir() / datetime.now().strftime("%Y-%m-%d")
    n = 2
    while d.exists():
        d = probes_dir() / (datetime.now().strftime("%Y-%m-%d") + f"_{n}")
        n += 1
    d.mkdir(parents=True)
    return d


def run(chatbots, destructive=False, visible=False, say=print):
    """Both sessions, the report, the console summary. Returns (report dict, folder)."""
    from .survey import launch_browser as lb
    out = new_dir()
    work = home.runs_dir() / "_probe" / out.name   # under runs/: chats the probe could not delete are leftovers for purge
    say(f"Probe 1/2: pages, endpoints and settings of {', '.join(home.LABELS[c] for c in chatbots)} (no message sent)...")
    raw = I.maintain({"probe": {"providers": list(chatbots), "destructive": destructive}}, work / "pages", visible, timeout=300 * len(chatbots)).get("probe") or {}
    signed = [p for p in chatbots if (((raw.get(p) or {}).get("login") or {}).get("state") or {}).get("signedIn") is True]
    recs, purge, health, canary = {}, {}, {}, {}
    if signed:
        say(f"Probe 2/2: {len(QUESTIONS)} messages to each of {', '.join(home.LABELS[c] for c in signed)}...")
        plan = {"providers": signed, "personas": [], "repetitions": 1, "questions": QUESTIONS,
                "config": {"private": True, "preflight": True, "purgeAfter": True, "probe": True, "auditSources": True, "responseTimeoutMs": 150000}}
        _, state = I._launch(plan, work / "messages", visible, 900)
        for r in (state.manifest or {}).get("records", []):
            recs.setdefault(r["provider"], []).append(r)
        purge, health = state.purge or {}, state.health or {}
        canary = I.canary_verdicts(state, signed)
    else:
        say("Probe 2/2 skipped: no chatbot is signed in.")
    results = {p: assemble(p, raw.get(p), recs.get(p, []), purge.get(p, {}), health.get(p), canary.get(p), destructive) for p in chatbots}

    # pictures of what failed
    for p in chatbots:
        shots = (raw.get(p) or {}).get("shots") or {}
        for name, c in results[p]["checks"].items():
            if c["status"] != "FAIL":
                continue
            data = shots.get(SHOT[name]) if name in SHOT else next(((r.get("probe") or {}).get("screenshot") for r in recs.get(p, []) if (r.get("probe") or {}).get("screenshot")), None)
            if _save_png(data, out / f"{p}_{name}.png"):
                c["evidence"]["screenshot"] = f"{p}_{name}.png"
            elif isinstance(data, str) and data.startswith("error"):
                c["evidence"]["screenshot"] = data[:120]
    prev = previous(out)
    old = json.loads((prev / "report.json").read_text())["results"] if prev else {}
    changes = diff_fingerprints(old, results)
    mark_changed(results, changes)
    rep = {"date": out.name, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "chatbots": list(chatbots), "destructive": destructive,
           "messages": sum(len(v) for v in recs.values()), "previous": prev.name if prev else None, "changes": changes, "results": results}
    (out / "report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False))
    (out / "report.md").write_text(render_report(rep))
    # the raw observations, without the pictures
    for v in raw.values():
        if isinstance(v, dict):
            v.pop("shots", None)
    for rs in recs.values():
        for r in rs:
            (r.get("probe") or {}).pop("screenshot", None)
    (out / "raw.json").write_text(json.dumps({"pages": raw, "records": recs, "purge": purge, "health": health}, indent=1, ensure_ascii=False, default=str))
    for line in summary_lines(rep, out):
        say(line)
    return rep, out


# --- monthly schedule ----------------------------------------------------------------------------------------

LABEL = "com.churvey.probe"


def churvey_command():
    exe = shutil.which("churvey")
    return [exe] if exe else [sys.executable, "-m", "churvey.cli"]


def schedule_file(platform=None, cmd=None, env=None):
    """(file name, content, how to load it) for a probe at 09:00 on the 1st of every month."""
    platform = platform or sys.platform
    cmd = (cmd or churvey_command()) + ["probe"]
    env = env if env is not None else ({"CHURVEY_HOME": str(home.root())} if "CHURVEY_HOME" in os.environ else {})
    log = probes_dir() / "scheduled.log"
    if platform == "darwin":
        from xml.sax.saxutils import escape
        args = "".join(f"\n    <string>{escape(a)}</string>" for a in cmd)
        envs = "".join(f"\n    <key>{escape(k)}</key><string>{escape(v)}</string>" for k, v in {"PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin", **env}.items())
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key>
  <array>{args}
  </array>
  <key>EnvironmentVariables</key>
  <dict>{envs}
  </dict>
  <key>StartCalendarInterval</key>
  <dict><key>Day</key><integer>1</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>{escape(str(log))}</string>
  <key>StandardErrorPath</key><string>{escape(str(log))}</string>
</dict>
</plist>
"""
        name = f"{LABEL}.plist"
        how = (f"cp {{path}} ~/Library/LaunchAgents/{name}\n"
               f"launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/{name}\n"
               f"(remove: launchctl bootout gui/$(id -u)/{LABEL}; rm ~/Library/LaunchAgents/{name})")
        return name, body, how
    import shlex
    prefix = "".join(f"{k}={shlex.quote(v)} " for k, v in env.items())
    body = f"0 9 1 * * {prefix}{' '.join(shlex.quote(a) for a in cmd)} >> {shlex.quote(str(log))} 2>&1\n"
    return "churvey-probe.cron", body, "(crontab -l 2>/dev/null; cat {path}) | crontab -\n(remove: crontab -e, delete the churvey probe line)"


def install_schedule(say=print):
    """Write the schedule file under ~/.churvey/schedule/ and print how to load it. Never loads it."""
    name, body, how = schedule_file()
    d = home.root() / "schedule"
    d.mkdir(parents=True, exist_ok=True)
    probes_dir().mkdir(parents=True, exist_ok=True)   # launchd does not create the log's folder
    (d / name).write_text(body)
    say(f"Wrote {d / name}: churvey probe at 09:00 on the 1st of every month. Not loaded. To load it:")
    for line in how.format(path=d / name).splitlines():
        say("  " + line)
    return d / name
