#!/usr/bin/env python3
"""Remote control for the running ff/ extension, over Firefox's debugger server.

Attaches to the extension's background page on 127.0.0.1:8831 (the port
`launch_browser.py` opens) and evaluates JS there. It never launches Firefox and
never installs or reloads the add-on.

    python -m churvey.survey.ffctl status             # per provider: ok/total, errors, capture methods, health
                                                      # (rate_limited / logged_out / challenge + banner text)
    python -m churvey.survey.ffctl log -n 300 --grep claude  # extension log ring
    python -m churvey.survey.ffctl pause mistral      # also: resume <pid>
    python -m churvey.survey.ffctl reload claude      # reload that provider's tab(s)
    python -m churvey.survey.ffctl stop --yes         # stops the whole run
    python -m churvey.survey.ffctl eval --unsafe 'JS' # top-level await ok; JSON-printed

`status` is read-only. pause/resume/reload/stop change the run; eval needs --unsafe.
"""

import argparse
import json
import sys
import time

from .launch_browser import RDP

ADDON_ID = "chat-probe@research.local"


class Bg:
    """Console of the extension's background page."""

    def __init__(self, port):
        self.c = RDP(port, timeout=5)
        self.c.sock.settimeout(60)
        self.c.read()
        addons = self.call("root", "listAddons")["addons"]
        desc = next((a for a in addons if a["id"] == ADDON_ID), None)
        if not desc:
            raise SystemExit(f"add-on {ADDON_ID} not installed in this Firefox")
        watcher = self.call(desc["actor"], "getWatcher", isServerTargetSwitchingEnabled=False)["actor"]
        self.c.send({"to": watcher, "type": "watchTargets", "targetType": "frame"})
        self.console = None
        while not self.console:
            m = self.c.read()
            t = m.get("target") or {}
            if m.get("type") == "target-available-form" and t.get("url", "").endswith("_generated_background_page.html"):
                self.console = t["consoleActor"]

    def call(self, to, type_, **kw):
        self.c.send({"to": to, "type": type_, **kw})
        while True:
            r = self.c.read()
            if r.get("from") == to and "type" not in r or r.get("from") == to and r.get("error"):
                if r.get("error"):
                    raise SystemExit(f"{type_}: {r.get('message') or r['error']}")
                return r

    def eval_raw(self, text):
        self.c.send({"to": self.console, "type": "evaluateJSAsync", "text": text})
        rid = None
        while True:
            r = self.c.read()
            if r.get("from") != self.console:
                continue
            if "resultID" in r and r.get("type") is None:
                rid = r["resultID"]
            elif r.get("type") == "evaluationResult" and (rid is None or r.get("resultID") == rid):
                if r.get("exception"):
                    raise SystemExit("JS exception: " + json.dumps(r.get("exceptionMessage") or r["exception"])[:500])
                res = r.get("result")
                if isinstance(res, dict) and res.get("type") == "longString":  # big strings come as a grip
                    res = self.call(res["actor"], "substring", start=0, end=res["length"])["substring"]
                return res

    def js(self, code, timeout=30):
        """Run `code` as an async function body in the page; return its JSON-decoded value.
        The console does not await promises, so the result is parked on a global and polled."""
        slot = "__ffctl_" + str(time.time_ns())
        self.eval_raw(
            f"globalThis.{slot} = {{}}; (async () => {{ {code} }})()"
            f".then(v => globalThis.{slot} = {{ v: JSON.stringify(v === undefined ? null : v) }},"
            f" e => globalThis.{slot} = {{ e: String(e && e.stack || e) }}); 1"
        )
        end = time.time() + timeout
        while time.time() < end:
            r = self.eval_raw(f"JSON.stringify(globalThis.{slot})")
            d = json.loads(r) if isinstance(r, str) else {}
            if "e" in d:
                self.eval_raw(f"delete globalThis.{slot}")
                raise SystemExit("JS error: " + d["e"][:500])
            if "v" in d:
                self.eval_raw(f"delete globalThis.{slot}")
                return json.loads(d["v"])
            time.sleep(0.2)
        raise SystemExit("timed out waiting for the page")


def cmd_status(bg, a):
    o = bg.js("return await Probe.runner.overview();")
    cfg = o.get("runConfig") or {}
    print(f"run {cfg.get('runId')}  status={o['status']}  records={o['recordCount']}")
    for pid, p in o["perProvider"].items():
        run = [i for i in p["items"] if i["s"] == "run"]
        cur = f"  now: {run[0]['k']}" + (f" (fails {run[0]['n']})" if run[0]["n"] else "") if run else ""
        h = p.get("health") or {}
        flag = " PAUSED" if p["paused"] else ""
        if h.get("status") not in (None, "ok"):
            flag += f" [{h['status'].upper()}: {h.get('text') or ''}]"
        cap = " ".join(f"{k}={v}" for k, v in sorted((p.get("capture") or {}).items()))
        print(f"{pid:9} {p['ok']:>3}/{p['total']} ok  err {p['error']:>2}  inflight={p['inflight']}{flag}{cur}" + (f"  via {cap}" if cap else ""))
        for i in p["items"]:
            if i["s"] == "err":
                print(f"          err {i['k']}  fails={i['n']} retry_in={i['in']}s  {i['e'] or ''}")


def cmd_log(bg, a):
    for ln in bg.js("return await Probe.log.getRing();")[-a.n:]:
        if not a.grep or a.grep.lower() in ln.lower():
            print(ln)


def cmd_pause(bg, a):
    bg.js(f"Probe.runner.pauseProvider({json.dumps(a.pid)}); return 1;")
    print(f"paused {a.pid}")
    cmd_status(bg, a)


def cmd_resume(bg, a):
    bg.js(f"Probe.runner.resumeProvider({json.dumps(a.pid)}); return 1;")
    print(f"resumed {a.pid}")


def cmd_reload(bg, a):
    # RUN lives in runner.js's closure, so find the tab(s) by the provider's host pattern.
    tabs = bg.js(f"""
        const p = Probe.providers.byId({json.dumps(a.pid)});
        if (!p) return null;
        const ts = await ext.tabs.query({{ url: p.matchPattern }});
        for (const t of ts) await ext.tabs.reload(t.id);
        return ts.map(t => ({{ id: t.id, url: t.url }}));""")
    if tabs is None:
        raise SystemExit(f"unknown provider {a.pid}")
    print(f"reloaded {len(tabs)} tab(s): " + ", ".join(f"{t['id']} {t['url'][:70]}" for t in tabs))


def cmd_stop(bg, a):
    if not a.yes:
        raise SystemExit("stop ends the whole run; pass --yes")
    bg.js("Probe.runner.stop(); return 1;")
    print("run stopped")


def cmd_eval(bg, a):
    if not a.unsafe:
        raise SystemExit("eval can change anything in the extension; pass --unsafe")
    code = a.js if "return" in a.js else f"return ({a.js});"
    print(json.dumps(bg.js(code), indent=2, ensure_ascii=False))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8831, help="Firefox debugger port (default 8831)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    lg = sub.add_parser("log")
    lg.add_argument("-n", type=int, default=60, help="last N ring lines (ring holds 300)")
    lg.add_argument("--grep", help="case-insensitive substring filter")
    for n in ("pause", "resume", "reload"):
        sub.add_parser(n).add_argument("pid")
    sub.add_parser("stop").add_argument("--yes", action="store_true")
    e = sub.add_parser("eval")
    e.add_argument("js")
    e.add_argument("--unsafe", action="store_true")
    a = ap.parse_args(argv)
    globals()["cmd_" + a.cmd](Bg(a.port), a)


if __name__ == "__main__":
    main()
