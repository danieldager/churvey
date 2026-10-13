"""The local pages: the setup checklist (`churvey setup` / `churvey login`) and the question-set editor
(`churvey questions ui`). One small loopback HTTP server; the pages are static files in churvey/web/ that
talk to a JSON API under /api/.

The setup page's live status comes from the extension itself: a worker thread attaches to the add-on's
background page over Firefox's debugger port (ffctl.Bg) and asks each chatbot tab what it shows
(the PAGE_STATUS check that the survey uses for logged_out / rate_limited / challenge).
"""

import http.server
import json
import pathlib
import threading
import time
import types
from datetime import datetime, timezone

from . import home

WEB = pathlib.Path(__file__).resolve().parent / "web"
PORTS = range(8741, 8750)   # not 8731-8735: the extension looks for run plans there
CTYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
          ".json": "application/json; charset=utf-8"}


def serve(api):
    """Serve churvey/web/ and `api` {("GET"|"POST"|"PUT"|"DELETE", "/api/x"): fn(query, body) -> (code, obj)}.
    Returns (server, port). The server runs on a daemon thread."""

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _send(self, code, body=b"", ctype="application/json; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _api(self, method):
            path, _, query = self.path.partition("?")
            fn = None
            for (m, p), f in api.items():   # exact match, or a prefix route ending in "/"
                if m == method and (path == p or (p.endswith("/") and path.startswith(p))):
                    fn = f
                    break
            if not fn:
                return self._send(404, b'{"error":"not found"}')
            body = None
            n = int(self.headers.get("Content-Length") or 0)
            if n:
                try:
                    body = json.loads(self.rfile.read(n))
                except ValueError:
                    return self._send(400, b'{"error":"bad json"}')
            try:
                code, obj = fn(path, body)
            except Exception as e:  # report to the page rather than dropping the connection
                code, obj = 500, {"error": str(e)}
            self._send(code, json.dumps(obj, ensure_ascii=False).encode())

        def do_GET(self):
            if self.path.startswith("/api/"):
                return self._api("GET")
            name = self.path.split("?")[0].lstrip("/") or "index.html"
            f = (WEB / name).resolve()
            if WEB not in f.parents or not f.is_file():
                return self._send(404, b"not found", "text/plain")
            self._send(200, f.read_bytes(), CTYPES.get(f.suffix, "application/octet-stream"))

        def do_POST(self):
            self._api("POST")

        def do_PUT(self):
            self._api("PUT")

        def do_DELETE(self):
            self._api("DELETE")

        def log_message(self, *a):
            pass

    from .survey.launch_browser import port_free
    for port in PORTS:
        if not port_free(port + 100):   # setup puts Firefox's debugger server there
            continue
        try:
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
        except OSError:
            continue
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv, port
    raise SystemExit(f"no free port in {PORTS.start}-{PORTS.stop - 1}")


def strings():
    return json.loads((WEB / "strings.json").read_text())


# --- setup checklist ----------------------------------------------------------------------------------------

# Is this tab signed in? Injected fresh into each chatbot tab on every poll (tabs.executeScript), so it does not depend
# on the content script having survived an SPA redirect. A positive check where the site has an account API
# (ChatGPT /api/auth/session, Claude /api/organizations); otherwise a visible "Sign in" / "Log in" / "Sign up"
# control anywhere on the page means signed out. Returns "in" | "out" | "unknown".
LOGIN_PROBE = r"""
(async () => {
  const get = async (path) => { try { const r = await fetch(location.origin + path, { credentials: "include" }); return r.ok ? await r.json() : null; } catch (_) { return null; } };
  const h = location.hostname;
  if (/^\/(login|signin|sign-in|auth|welcome)/i.test(location.pathname) || h.startsWith("accounts.") || h.startsWith("auth.")) return "out";
  if (h.endsWith("chatgpt.com")) { const j = await get("/api/auth/session"); if (j) return j.user ? "in" : "out"; }
  if (h.endsWith("claude.ai")) { const j = await get("/api/organizations"); return Array.isArray(j) && j.length ? "in" : "out"; }
  const vis = (el) => el.getClientRects().length > 0 && el.getBoundingClientRect().width > 0;
  const RE = /^(log ?in|sign ?in|sign ?up|se connecter|connexion|s['’]inscrire|inscription|create account)$/i;
  for (const b of document.querySelectorAll("button, a, [role=button]")) {
    const t = (b.innerText || b.getAttribute("aria-label") || "").replace(/\s+/g, " ").trim();
    if (t.length < 30 && RE.test(t) && vis(b)) return "out";
  }
  if (document.querySelector('a[href*="accounts.google.com/ServiceLogin"], a[href*="accounts.google.com/signin"]')) return "out";
  return document.readyState === "complete" ? "in" : "unknown";
})()
"""

STATUS_JS = r"""
const probe = %s;
const out = {};
for (const id of %s) {
  const p = Probe.providers.byId(id);
  const tabs = p ? await ext.tabs.query({ url: p.matchPattern }) : [];
  if (!tabs.length) { out[id] = { state: "not_open", text: "" }; continue; }
  let best = { state: "loading", text: "" };
  for (const t of tabs) {
    let login = "unknown", page = null;
    try { login = (await ext.tabs.executeScript(t.id, { code: probe }))[0] || "unknown"; } catch (_) {}
    try { page = await ext.tabs.sendMessage(t.id, { type: Probe.MSG.PAGE_STATUS }); } catch (_) {}
    let st;
    if (login === "out") st = { state: "logged_out", text: "" };
    else if (page && (page.state === "rate_limited" || (page.state === "challenge" && login !== "in"))) st = { state: page.state, text: page.text || "" };
    else if (login === "in") st = { state: "ok", text: "" };
    else st = { state: "loading", text: "" };
    best = st;
    if (st.state === "ok" || st.state === "rate_limited") break;
  }
  out[id] = best;
}
return out;
"""

TEST_START_JS = """
await Probe.runner.start(%s);
return 1;
"""

TEST_POLL_JS = """
const ov = await Probe.runner.overview();
const ex = await Probe.runner.buildExport();
return { status: ov.status, health: Probe.runner.providerHealth(), records: (ex.manifest.records || []).map((r) => ({
  provider: r.provider, status: r.status, responseText: (r.responseText || "").slice(0, 200), capture_method: r.capture_method,
  errorMessage: r.errorMessage })) };
"""

OPEN_JS = """
const p = Probe.providers.byId(%s);
const ts = await ext.tabs.query({ url: p.matchPattern });
const t = ts.length ? await ext.tabs.update(ts[0].id, { active: true }) : await ext.tabs.create({ url: %s, active: true });
await ext.windows.update(t.windowId, { focused: true });
return t.id;
"""

FOCUS_JS = """
const ts = await ext.tabs.query({ url: %s });
if (ts.length) { await ext.tabs.update(ts[0].id, { active: true }); await ext.windows.update(ts[0].windowId, { focused: true }); }
return ts.length;
"""


class Setup:
    """State behind the checklist page. The worker thread owns the debugger connection."""

    def __init__(self, chatbots, mode, dbg_port):
        self.mode = mode                      # "setup" | "login"
        self.chatbots = list(chatbots)
        self.dbg_port = dbg_port
        self.page_url = None
        self.rows = {c: {"state": "not_open", "text": ""} for c in chatbots}
        self.skipped = set()
        self.test = {"state": "idle", "results": {}}
        self.want_test = False
        self.to_open = []
        self.recheck = False
        self.connected = False
        self.saved = threading.Event()
        self.lock = threading.Lock()

    def active(self):
        return [c for c in self.chatbots if c not in self.skipped]

    # API -------------------------------------------------------------------------------------------------
    def api(self):
        return {("GET", "/api/state"): self.get_state, ("POST", "/api/skip"): self.post_skip,
                ("POST", "/api/test"): self.post_test, ("POST", "/api/open"): self.post_open,
                ("POST", "/api/recheck"): self.post_recheck, ("POST", "/api/done"): self.post_done,
                ("GET", "/api/strings"): lambda p, b: (200, strings())}

    def get_state(self, path, body):
        with self.lock:
            return 200, {"mode": self.mode, "connected": self.connected, "saved": self.saved.is_set(),
                         "chatbots": [{"id": c, "label": home.LABELS[c], "site": home.SITES[c], "skipped": c in self.skipped,
                                       **self.rows[c]} for c in self.chatbots],
                         "test": self.test}

    def post_skip(self, path, body):
        c = (body or {}).get("id")
        with self.lock:
            if c in self.chatbots:
                (self.skipped.discard if (body or {}).get("undo") else self.skipped.add)(c)
        return self.get_state(path, body)

    def post_open(self, path, body):
        c = (body or {}).get("id")
        if c in self.chatbots:
            self.to_open.append(c)
        return 200, {"queued": c}

    def post_recheck(self, path, body):
        c = (body or {}).get("id")
        with self.lock:
            if c in self.rows and self.rows[c]["state"] != "not_open":
                self.rows[c] = {"state": "loading", "text": ""}
        self.recheck = True
        return self.get_state(path, body)

    def signed_in(self):
        return [c for c in self.active() if self.rows[c]["state"] in ("ok", "rate_limited")]

    def post_test(self, path, body):
        with self.lock:
            if self.test["state"] != "running" and self.signed_in():
                self.want_test = True
                self.test = {"state": "running", "results": {}}
        return self.get_state(path, body)

    def post_done(self, path, body):
        cfg = home.load_config()
        prev = cfg.get("chatbots") or []
        res = self.test.get("results", {})
        chosen = [c for c in self.active() if res.get(c, {}).get("verdict") == "ok"]
        cfg["chatbots"] = [c for c in home.CHATBOTS if c in chosen or (self.mode == "login" and c in prev)]
        cfg["profile"] = str(home.profile_dir())
        cfg.setdefault("history", []).append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mode": self.mode,
                                              "chatbots": chosen, "status": {c: self.rows[c]["state"] for c in chosen},
                                              "test": {c: v["verdict"] for c, v in self.test.get("results", {}).items()}})
        home.save_config(cfg)
        self.saved.set()
        return self.get_state(path, body)

    # worker ----------------------------------------------------------------------------------------------
    def run_worker(self, stop):
        from .survey.ffctl import Bg
        bg = None
        while not stop.is_set():
            try:
                if bg is None:
                    bg = Bg(self.dbg_port)
                    self.connected = True
                while self.to_open:
                    c = self.to_open.pop(0)
                    bg.js(OPEN_JS % (json.dumps(c), json.dumps(home.SITES[c])), timeout=20)
                if self.want_test:
                    self.want_test = False
                    self._run_test(bg, stop)
                    continue
                self.recheck = False
                st = bg.js(STATUS_JS % (json.dumps(LOGIN_PROBE), json.dumps(self.chatbots)), timeout=30)
                with self.lock:
                    for c, v in st.items():
                        self.rows[c] = v
            except (SystemExit, OSError):   # Firefox not up yet, or closed: retry quietly
                bg, self.connected = None, False
                stop.wait(2)
                continue
            for _ in range(8):   # poll every 2 s, but react to an Open click within 0.25 s
                if stop.wait(0.25) or self.to_open or self.want_test or self.recheck:
                    break

    def _run_test(self, bg, stop):
        from .survey.launch_browser import PREFLIGHT_PROMPT, preflight_verdicts
        ids = self.signed_in()
        not_in = [c for c in self.active() if c not in ids]
        plan = {"providers": ids, "questions": [{"id": "preflight", "text": PREFLIGHT_PROMPT}], "personas": [], "repetitions": 1,
                "config": {"private": True, "preflight": True, "responseTimeoutMs": 90000}}
        bg.js(TEST_START_JS % json.dumps(plan), timeout=60)
        end = time.time() + 300
        snap = {}
        while time.time() < end and not stop.is_set():
            stop.wait(3)
            snap = bg.js(TEST_POLL_JS, timeout=30)
            if snap["status"] in ("done", "stopped"):
                break
        verdicts = preflight_verdicts(types.SimpleNamespace(manifest={"records": snap.get("records", [])}, health=snap.get("health") or {}), ids)
        with self.lock:
            res = {c: {"verdict": v, "detail": d} for c, (v, d) in verdicts.items()}
            res.update({c: {"verdict": "skipped", "detail": ""} for c in not_in})
            self.test = {"state": "done", "results": res}
        if self.page_url:
            try:
                bg.js(FOCUS_JS % json.dumps(self.page_url + "*"), timeout=10)
            except SystemExit:
                pass
