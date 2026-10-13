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
import threading
import time

def find_ext_dir():
    """$CHURVEY_FF, else repo-root ff/ (source or editable checkout), else the copy in a wheel."""
    here = pathlib.Path(__file__).resolve().parent
    env = os.environ.get("CHURVEY_FF")
    for c in ([pathlib.Path(env)] if env else []) + [here.parents[1] / "ff", here / "_ff"]:
        if (c / "manifest.json").is_file():
            return c
    raise SystemExit("extension not found: set CHURVEY_FF to the ff/ directory")

FIREFOX = pathlib.Path("/Applications/Firefox.app/Contents/MacOS/firefox")
FF_HOME = pathlib.Path.home() / "Library/Application Support/Firefox"
DEFAULT_PROFILE = FF_HOME / "Profiles/cn-harvest"
PORTS = range(8731, 8736)  # must match PORTS in ff/src/background/autostart.js

PREFS_MARK = "// managed by cn_bench/launch_browser.py — do not edit below"
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
]


# --- the loopback server the extension talks to -----------------------------

class State:
    def __init__(self, plan, out_dir):
        self.plan = plan
        self.out_dir = out_dir
        self.finished = threading.Event()
        self.status = "waiting"
        self.written = None


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
            state.status = msg.get("status", "?")
            if msg.get("manifest"):
                state.written = write_results(state.out_dir, msg)
            self._send(200, b'{"ok":true}')
            if self.path.startswith("/done"):
                state.finished.set()

        def log_message(self, *a):
            pass

    return Handler


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
    ok = sum(1 for r in records if r.get("status") == "ok")
    return {"run_id": run_id, "records": len(records), "ok": ok, "dir": out_dir}


def serve(state):
    for port in PORTS:
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
    return any("Firefox.app" in ln and str(profile) in ln for ln in ps.splitlines())


def ensure_prefs(profile):
    f = profile / "user.js"
    cur = f.read_text() if f.exists() else ""
    if PREFS_MARK in cur:
        return
    sep = "" if not cur or cur.endswith("\n") else "\n"
    f.write_text(cur + sep + PREFS_MARK + "\n" + "\n".join(PREFS) + "\n")


# --- main -------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-plan", required=True, type=pathlib.Path, help="ff/ run config JSON")
    ap.add_argument("--profile", default=str(DEFAULT_PROFILE), help="profile name or path (default: cn-harvest)")
    ap.add_argument("--out", type=pathlib.Path, help="where to write results (default: next to the run plan)")
    ap.add_argument("--timeout", type=int, default=1800, help="seconds to wait for the run (default 1800)")
    ap.add_argument("--no-close", action="store_true", help="leave Firefox open when the run finishes")
    args = ap.parse_args()

    plan = json.loads(args.run_plan.read_text())
    if not plan.get("providers") or not plan.get("questions"):
        raise SystemExit("run plan needs non-empty `providers` and `questions`")
    out_dir = args.out or args.run_plan.parent

    profile = resolve_profile(args.profile)
    if not profile.is_dir():
        raise SystemExit(
            f"profile {profile} does not exist.\n"
            f"Create it once:  {FIREFOX} --no-remote -CreateProfile 'cn-harvest {profile}'\n"
            f"then launch it and log into claude.ai, gemini.google.com and chatgpt.com."
        )
    if profile_in_use(profile):
        raise SystemExit(f"Firefox is already running on {profile.name} — close that window and retry.")

    state = State(plan, out_dir)
    srv, http_port = serve(state)
    dbg_port = http_port + 100
    ensure_prefs(profile)

    n_items = len(plan["questions"]) * max(1, plan.get("repetitions", 1)) * max(1, len(plan.get("personas") or []))
    print(f"plan: {', '.join(plan['providers'])} x {n_items} items -> {out_dir}")
    print(f"serving run plan on 127.0.0.1:{http_port}, profile {profile.name}")

    ff = subprocess.Popen(
        [str(FIREFOX), "--profile", str(profile), "--no-remote", "--new-instance",
         "--start-debugger-server", str(dbg_port), "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        addon_id = install_addon(dbg_port, find_ext_dir())
        print(f"installed {addon_id}; waiting up to {args.timeout}s for the run")
        done = state.finished.wait(args.timeout)
        # Give the final POST a moment to land before we tear the server down.
        time.sleep(1)
        if not done:
            print(f"TIMEOUT after {args.timeout}s (last status: {state.status})", file=sys.stderr)
    finally:
        srv.shutdown()
        if args.no_close:
            print("leaving Firefox open (--no-close)")
        else:
            ff.terminate()
            try:
                ff.wait(20)
            except subprocess.TimeoutExpired:
                ff.kill()

    w = state.written
    if not w:
        print("no results posted — the extension never reported back", file=sys.stderr)
        return 1
    print(f"{w['ok']}/{w['records']} ok -> {w['dir']}/{w['run_id']}.jsonl")
    return 0 if state.finished.is_set() else 1


if __name__ == "__main__":
    sys.exit(main())
