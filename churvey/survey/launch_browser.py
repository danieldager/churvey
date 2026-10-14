#!/usr/bin/env python3
"""Run an ff/ probe plan in Firefox with zero clicks.

Serves the run plan on a loopback port, launches Firefox on a dedicated profile,
installs `ff/` as a temporary add-on over Firefox's remote debugging protocol (the
same call `web-ext run` makes), then waits for the extension to post its results
back and shuts the browser down.

    python -m churvey.survey.launch_browser \
        --run-plan path/to/run-plan.json

Results are written next to the run plan. The extension directory is the repo's `ff/`
(or the copy bundled in a wheel); override with $CHURVEY_FF.

Live output, unbuffered, greppable by a log watcher:

    === 14:02:11 START <run-plan> chatgpt,claude x 20 items
    14:03:07 claude neutral#r0#q1 ok poll 41.2s
    14:03:09 mistral neutral#r0#q1 error - 0.0s [rate_limited] Limite de messages atteinte
    14:03:09 mistral HEALTH rate_limited Limite de messages atteinte   (provider paused, not retried)
    === 14:20:44 END 38/40 ok; blocked: mistral=rate_limited

    --preflight       one short question to each provider (--providers a,b,..): ok / logged_out /
                      rate_limited / challenge / capture_failed per provider; exit 0 only if all are ok
    --headless        run Firefox without a window (see docs/capture_robustness.md for what that costs)

Stdlib only: there is no node on this machine, so `web-ext` is not installable.
"""

import argparse
import configparser
import http.server
import json
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import threading
import time

PREFLIGHT_PROMPT = "R\u00e9ponds uniquement par le mot : OK"
ALL_PROVIDERS = ["chatgpt", "claude", "gemini", "grok", "mistral"]

def find_ext_dir():
    """$CHURVEY_FF, else repo-root ff/ (source or editable checkout), else the copy in a wheel."""
    here = pathlib.Path(__file__).resolve().parent
    env = os.environ.get("CHURVEY_FF")
    for c in ([pathlib.Path(env)] if env else []) + [here.parents[1] / "ff", here / "_ff"]:
        if (c / "manifest.json").is_file():
            return c
    raise SystemExit("extension not found: set CHURVEY_FF to the ff/ directory")

FIREFOX = pathlib.Path("/Applications/Firefox.app/Contents/MacOS/firefox")
FIREFOX_CANDIDATES = [FIREFOX, pathlib.Path.home() / "Applications/Firefox.app/Contents/MacOS/firefox",
                      pathlib.Path("/usr/bin/firefox"), pathlib.Path("/usr/bin/firefox-esr"), pathlib.Path("/usr/lib/firefox/firefox"),
                      pathlib.Path("/snap/bin/firefox")]


def find_firefox():
    """$CHURVEY_FIREFOX, the usual macOS / Linux install paths, else `firefox` on PATH. None if not found."""
    import shutil
    env = os.environ.get("CHURVEY_FIREFOX")
    for c in ([pathlib.Path(env)] if env else []) + FIREFOX_CANDIDATES:
        if c.is_file() and os.access(c, os.X_OK):
            return c
    w = shutil.which("firefox") or shutil.which("firefox-esr")
    return pathlib.Path(w) if w else None


def install_hint():
    if sys.platform == "darwin":
        return "brew install --cask firefox   (or download it from https://www.mozilla.org/firefox/)"
    if sys.platform.startswith("linux"):
        return "sudo apt install firefox   (Fedora: sudo dnf install firefox; Arch: sudo pacman -S firefox)"
    return "download it from https://www.mozilla.org/firefox/"
FF_HOME = pathlib.Path.home() / "Library/Application Support/Firefox"
DEFAULT_PROFILE = FF_HOME / "Profiles/cn-harvest"
PORTS = range(8731, 8736)  # must match PORTS in ff/src/background/autostart.js

PREFS_MARK = "// managed by cn_bench/launch_browser.py — do not edit below"  # unchanged so old profiles upgrade in place
PREFS = [
    # required for --start-debugger-server, i.e. for installing the add-on
    'user_pref("devtools.debugger.remote-enabled", true);',
    'user_pref("devtools.debugger.prompt-connection", false);',
    'user_pref("devtools.chrome.enabled", true);',
    # keep an unattended launch free of dialogs that would steal focus
    'user_pref("browser.shell.checkDefaultBrowser", false);',
    'user_pref("browser.sessionstore.resume_from_crash", false);',
    'user_pref("browser.aboutwelcome.enabled", false);',
    'user_pref("browser.startup.homepage_override.mstone", "ignore");',
    'user_pref("datareporting.policy.dataSubmissionEnabled", false);',
    'user_pref("app.update.auto", false);',
    # A Firefox that is killed (Ctrl-C, timeout) counts as a failed startup; after 3 of them Firefox restarts itself
    # into safe mode WITHOUT our arguments (no debugger server, so no add-on): seen 2026-10-14. Never do that.
    'user_pref("toolkit.startup.max_resumed_crashes", -1);',
    # Never depend on focus or visibility: a covered, minimised or background window must keep running at full
    # speed. All names verified against Firefox 157 (compiled into XUL / browser/defaults firefox.js).
    'user_pref("dom.min_background_timeout_value", 4);',                                   # was 1000 ms: background setTimeout clamp
    'user_pref("dom.min_background_timeout_value_without_budget_throttling", 4);',       # was 1000 ms: same, for tabs playing audio etc.
    'user_pref("dom.timeout.enable_budget_timer_throttling", false);',                    # budget-based throttling of background timers
    'user_pref("dom.suspend_inactive.enabled", false);',                                  # do not suspend inactive windows' timers/events
    'user_pref("dom.ipc.processPriorityManager.enabled", false);',                        # do not drop background content processes to low priority
    # macOS: a window that is not on screen (another Space, covered, the app hidden) lowers the main-thread priority of
    # its processes; on a loaded machine they then do not run for minutes (Mozilla bug 1960741; WebDriver sets this too).
    # Measured 2026-10-14: 4-minute stalls of a --visible probe whose windows sat on another Space.
    'user_pref("threads.lower_mainthread_priority_in_background.enabled", false);',
    'user_pref("layout.throttled_frame_rate", 60);',                                     # was 1 fps for hidden documents
    'user_pref("browser.tabs.unloadOnLowMemory", false);',                                # never discard background tabs under memory pressure
    'user_pref("browser.tabs.min_inactive_duration_before_unload", 86400000);',           # and not after 10 minutes of inactivity either
]


# --- the loopback server the extension talks to -----------------------------

class State:
    def __init__(self, plan, out_dir):
        self.plan = plan
        self.out_dir = out_dir
        self.finished = threading.Event()
        self.status = "waiting"
        self.written = None
        self.health = {}
        self.seen = {}
        self.maintenance = None   # results of a {task: "maintenance"} plan (memory / purge / list)
        self.purge = None         # {provider: {chat_id: result}} from the after-run purge


def make_handler(state):
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _send(self, code, body=b"", ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            if body:
                self.wfile.write(body)

        def do_GET(self):
            if self.path.startswith("/run-plan.json"):
                self._send(200, json.dumps(state.plan).encode())
            else:
                self._send(404)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            try:
                msg = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                self._send(400)
                return
            if self.path.startswith("/event"):
                show_event(state, msg)
                self._send(200, b'{"ok":true}')
                return
            state.status = msg.get("status", "?")
            if msg.get("maintenance") is not None:
                state.maintenance = msg["maintenance"]
            if msg.get("purge") and state.plan.get("task") != "maintenance":
                state.purge = msg["purge"]
                write_purged(state.out_dir, msg["purge"])
            if msg.get("health"):
                state.health = msg["health"]
            if msg.get("manifest"):
                state.manifest = msg["manifest"]
                state.written = write_results(state.out_dir, msg)
            self._send(200, b'{"ok":true}')
            if self.path.startswith("/done"):
                state.finished.set()

        def log_message(self, *a):
            pass

    return Handler


def say(line):
    """One line, flushed at once: this output is tailed by a log watcher."""
    print(line, flush=True)


def hms(iso=None):
    if iso:
        try:
            from datetime import datetime
            return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%H:%M:%S")
        except ValueError:
            pass
    return time.strftime("%H:%M:%S")


def show_event(state, ev):
    """The extension posts one event per landed record and per provider health change."""
    if ev.get("type") == "record":
        lat = ev.get("latencyMs")
        lat = f"{lat / 1000:.1f}s" if isinstance(lat, (int, float)) else "-"
        err = f" {ev['error']}" if ev.get("status") != "ok" and ev.get("error") else ""
        say(f"{hms(ev.get('ts'))} {ev['provider']} {ev['itemKey']} {ev['status']} {ev.get('capture_method') or '-'} {lat}{err}")
    elif ev.get("type") == "health":
        state.health[ev["provider"]] = {"status": ev["status"], "text": ev.get("text")}
        say(f"{hms(ev.get('ts'))} {ev['provider']} HEALTH {ev['status']} {ev.get('text') or ''}   (provider paused, not retried)")


def write_results(out_dir, msg):
    """Write the extension's export payload. Called on every progress post, so a
    run that times out or is cut short still leaves its records on disk."""
    manifest = msg["manifest"]
    cfg = manifest.get("runConfig") or {}
    run_id = cfg.get("runId") or "run"
    records = manifest.get("records") or []
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{run_id}.run.json").write_text(json.dumps(manifest, indent=2))
    (out_dir / f"{run_id}.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n")
    if msg.get("summaryText"):
        (out_dir / f"{run_id}.summary.txt").write_text(msg["summaryText"])
    if msg.get("rawCompletions"):  # only on the final post; input for offline re-parsing of citations
        (out_dir / f"{run_id}.raw-completions.json").write_text(json.dumps(msg["rawCompletions"]))
    if manifest.get("chats") is not None:   # every chat the run created: what `churvey purge --run` deletes
        (out_dir / "chats.jsonl").write_text("".join(json.dumps(c) + "\n" for c in manifest["chats"]))
    ok = sum(1 for r in records if r.get("status") == "ok")
    return {"run_id": run_id, "records": len(records), "ok": ok, "dir": out_dir}


def write_purged(out_dir, purge):
    """Append one line per chat delete attempt: {provider, chat_id, result, at}."""
    out_dir.mkdir(parents=True, exist_ok=True)
    at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with open(out_dir / "purged.jsonl", "a") as f:
        for pid, res in (purge or {}).items():
            for cid, r in (res or {}).items():
                f.write(json.dumps({"provider": pid, "chat_id": cid, "result": r, "at": at}) + "\n")


def port_free(port):
    """True if nothing listens on 127.0.0.1:port (Firefox's debugger server would fail to bind, and we would
    talk to whichever Firefox already holds it)."""
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def serve(state):
    for port in PORTS:
        if not port_free(port + 100):   # the debugger port that goes with this plan port
            continue
        try:
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
        except OSError:
            continue
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv, port
    raise SystemExit(f"no free port in {PORTS.start}-{PORTS.stop - 1}")


# --- Firefox remote debugging protocol --------------------------------------

class RDP:
    """Minimal client for Firefox's devtools protocol: length-prefixed JSON
    packets, `<byteLength>:<json>`, over a plain TCP socket."""

    def __init__(self, port, timeout=60):
        self.buf = b""
        self.sock = None
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                self.sock = socket.create_connection(("127.0.0.1", port), timeout=10)
                break
            except OSError:
                time.sleep(0.5)
        if not self.sock:
            raise SystemExit(f"Firefox never opened its debugger server on {port}")

    def send(self, obj):
        b = json.dumps(obj).encode()
        self.sock.sendall(f"{len(b)}:".encode() + b)

    def read(self):
        while True:
            i = self.buf.find(b":")
            if i > 0:
                n = int(self.buf[:i])
                if len(self.buf) >= i + 1 + n:
                    pkt, self.buf = self.buf[i + 1:i + 1 + n], self.buf[i + 1 + n:]
                    return json.loads(pkt)
            chunk = self.sock.recv(65536)
            if not chunk:
                raise SystemExit("debugger connection closed")
            self.buf += chunk


def install_addon(port, addon_path):
    c = RDP(port)
    c.read()  # server hello
    c.send({"to": "root", "type": "getRoot"})
    actor = c.read().get("addonsActor")
    if not actor:
        raise SystemExit("no addonsActor — is this a devtools-enabled Firefox?")
    c.send({"to": actor, "type": "installTemporaryAddon", "addonPath": str(addon_path)})
    reply = c.read()
    if "error" in reply:
        raise SystemExit(f"add-on install failed: {reply}")
    return reply.get("addon", {}).get("id")


# --- profile ----------------------------------------------------------------

def resolve_profile(name_or_path):
    p = pathlib.Path(name_or_path).expanduser()
    if p.is_absolute() or p.exists():
        return p
    ini = configparser.ConfigParser()
    ini.read(FF_HOME / "profiles.ini")
    for sec in ini.sections():
        if ini[sec].get("Name") == name_or_path:
            rel = ini[sec].get("Path", "")
            return FF_HOME / rel if ini[sec].get("IsRelative", "1") == "1" else pathlib.Path(rel)
    return FF_HOME / "Profiles" / name_or_path


def profile_in_use(profile):
    """True if some Firefox is already running on this profile — launching a
    second one would hit the profile lock (and we must never disturb the first)."""
    ps = subprocess.run(["/bin/ps", "-axo", "command"], capture_output=True, text=True).stdout
    return any(("Firefox.app" in ln or "firefox" in ln) and str(profile) in ln for ln in ps.splitlines())


def ensure_prefs(profile):
    f = profile / "user.js"
    cur = f.read_text() if f.exists() else ""
    block = PREFS_MARK + "\n" + "\n".join(PREFS) + "\n"
    if PREFS_MARK in cur:  # everything below the marker is ours: refresh it so new prefs reach old profiles
        head = cur[:cur.index(PREFS_MARK)]
        if cur == head + block:
            return
        f.write_text(head + block)
        return
    sep = "" if not cur or cur.endswith("\n") else "\n"
    f.write_text(cur + sep + block)


# --- main -------------------------------------------------------------------

def preflight_verdicts(state, providers):
    """provider -> ok | logged_out | rate_limited | challenge | capture_failed, from the records and health."""
    recs = {}
    for r in (state.manifest or {}).get("records", []):
        recs.setdefault(r["provider"], []).append(r)
    out = {}
    for pid in providers:
        h = (state.health.get(pid) or {}).get("status", "ok")
        rs = recs.get(pid, [])
        if any(r.get("status") == "ok" and (r.get("responseText") or "").strip() for r in rs):
            out[pid] = ("ok", f"{rs[-1].get('capture_method')} {len((rs[-1].get('responseText') or ''))}c")
        elif h not in ("ok", None):
            out[pid] = (h, (state.health.get(pid) or {}).get("text") or "")
        else:
            err = next((r.get("errorMessage") for r in reversed(rs) if r.get("errorMessage")), "no record")
            out[pid] = ("capture_failed", err)
    return out


def start_firefox(profile, dbg_port, url="about:blank", headless=False):
    """Firefox on `profile` with the debugger server on `dbg_port`, opening `url`."""
    exe = find_firefox()
    if not exe:
        raise SystemExit(f"Firefox not found. Install it:\n  {install_hint()}")
    cmd = [str(exe), "--profile", str(profile), "--no-remote", "--new-instance"]
    if headless:
        cmd.append("--headless")
    cmd += ["--start-debugger-server", str(dbg_port), url]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main(argv=None):
    rc, _ = launch(argv)
    return rc


def launch(argv=None):
    """Parse `argv` and run; returns (exit code, State). State.health holds the blocked providers."""
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-plan", type=pathlib.Path, help="ff/ run config JSON (not needed with --preflight)")
    ap.add_argument("--profile", default=str(DEFAULT_PROFILE), help="profile name or path (default: cn-harvest)")
    ap.add_argument("--out", type=pathlib.Path, help="where to write results (default: next to the run plan)")
    ap.add_argument("--timeout", type=int, default=1800, help="seconds to wait for the run (default 1800; preflight 240)")
    ap.add_argument("--no-close", action="store_true", help="leave Firefox open when the run finishes")
    ap.add_argument("--headless", action="store_true", help="run Firefox without a window")
    ap.add_argument("--preflight", action="store_true", help="1 short question x each provider; report ok/logged_out/rate_limited/challenge/capture_failed")
    ap.add_argument("--providers", help="comma list (preflight default: all; otherwise overrides the plan's providers)")
    args = ap.parse_args(argv)

    if args.preflight:
        providers = [p for p in (args.providers or ",".join(ALL_PROVIDERS)).split(",") if p]
        plan = {"providers": providers, "questions": [{"id": "preflight", "text": PREFLIGHT_PROMPT}], "personas": [], "repetitions": 1,
                "config": {"private": True, "preflight": True, "responseTimeoutMs": 90000}}
        out_dir = args.out or pathlib.Path(tempfile.gettempdir()) / "churvey_preflight"
        args.timeout = min(args.timeout, 240)
        plan_name = "preflight"
    else:
        if not args.run_plan:
            raise SystemExit("--run-plan is required (or use --preflight)")
        plan = json.loads(args.run_plan.read_text())
        if args.providers:
            plan["providers"] = [p for p in args.providers.split(",") if p]
        out_dir = args.out or args.run_plan.parent
        plan_name = str(args.run_plan)
    if plan.get("task") != "maintenance" and (not plan.get("providers") or not plan.get("questions")):
        raise SystemExit("run plan needs non-empty `providers` and `questions`")

    profile = resolve_profile(args.profile)
    if not profile.is_dir():
        raise SystemExit(
            f"profile {profile} does not exist.\n"
            f"Create it once:  {find_firefox() or FIREFOX} --no-remote -CreateProfile 'cn-harvest {profile}'\n"
            f"then launch it and log into claude.ai, gemini.google.com and chatgpt.com."
        )
    if profile_in_use(profile):
        raise SystemExit(f"Firefox is already running on {profile.name} — close that window and retry.")

    state = State(plan, out_dir)
    state.manifest = None
    srv, http_port = serve(state)
    dbg_port = http_port + 100
    ensure_prefs(profile)

    n_items = len(plan.get("questions") or []) * max(1, plan.get("repetitions", 1)) * max(1, len(plan.get("personas") or []))
    say(f"plan: {', '.join(plan.get('providers') or [])} x {n_items} items -> {out_dir}" + (" [headless]" if args.headless else ""))
    say(f"serving run plan on 127.0.0.1:{http_port}, profile {profile.name}")
    say(f"=== {hms()} START {plan_name} {','.join(plan.get('providers') or [])} x {n_items} items")

    ff = start_firefox(profile, dbg_port, headless=args.headless)
    try:
        addon_id = install_addon(dbg_port, find_ext_dir())
        say(f"installed {addon_id}; waiting up to {args.timeout}s for the run")
        done = state.finished.wait(args.timeout)
        # Give the final POST a moment to land before we tear the server down.
        time.sleep(1)
        if not done:
            say(f"TIMEOUT after {args.timeout}s (last status: {state.status})")
    finally:
        srv.shutdown()
        if args.no_close:
            say("leaving Firefox open (--no-close)")
        else:
            ff.terminate()
            try:
                ff.wait(20)
            except subprocess.TimeoutExpired:
                ff.kill()

    blocked = {p: h["status"] for p, h in state.health.items() if h and h.get("status") not in ("ok", None)}
    if args.preflight:
        verdicts = preflight_verdicts(state, plan["providers"])
        for pid, (v, detail) in verdicts.items():
            say(f"PREFLIGHT {pid:9} {v:15} {detail}")
        good = all(v == "ok" for v, _ in verdicts.values())
        say(f"=== {hms()} END preflight {'PASS' if good else 'FAIL'}: " + " ".join(f"{p}={v}" for p, (v, _) in verdicts.items()))
        return (0 if good else 1), state

    if plan.get("task") == "maintenance":
        say(f"=== {hms()} END maintenance" + ("" if state.maintenance is not None else " - the extension never reported back"))
        return (0 if state.maintenance is not None else 1), state
    w = state.written
    if not w:
        say(f"=== {hms()} END no results posted - the extension never reported back")
        return 1, state
    say(f"{w['ok']}/{w['records']} ok -> {w['dir']}/{w['run_id']}.jsonl")
    tail = f"; blocked: {', '.join(f'{p}={v}' for p, v in blocked.items())}" if blocked else ""
    say(f"=== {hms()} END {w['ok']}/{w['records']} ok{tail}")
    if not state.finished.is_set():
        return 1, state
    return (3 if blocked else 0), state


if __name__ == "__main__":
    sys.exit(main())
