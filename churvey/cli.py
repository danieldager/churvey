"""churvey: put your questions to consumer chatbots through their own websites, in a Firefox profile of its own.

    churvey setup                         create the profile, sign in to each chatbot, test
    churvey run <question-set>            ask every question to every chatbot; answers land in ~/.churvey/runs/
    churvey export latest                 the clean per-answer JSONL

Data lives in ~/.churvey (override with $CHURVEY_HOME). Full guide: docs/cli.md.
"""

import argparse
import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone

from . import home, questions as Q

LOGIN_FIX = "churvey login {}"
BLOCK_TEXT = {"logged_out": "is not signed in", "rate_limited": "hit its message limit", "challenge": "showed a security check (captcha)"}


def version():
    try:
        from importlib.metadata import version as v
        return v("churvey")
    except Exception:
        return "dev"


def say(*a):
    print(*a, flush=True)


def interactive():
    return sys.stdin.isatty() and sys.stdout.isatty()


def interrupt(*_):
    raise KeyboardInterrupt


def require_setup():
    cfg = home.load_config()
    if not cfg.get("chatbots") or not home.profile_dir().is_dir():
        raise SystemExit("churvey is not set up yet. Run:  churvey setup")
    return cfg


def explain_blocked(health):
    """One plain sentence per blocked chatbot, with the exact fix command when there is one."""
    for pid, h in sorted(health.items()):
        st = (h or {}).get("status")
        if st in (None, "ok"):
            continue
        say(f"  {home.LABELS.get(pid, pid)} {BLOCK_TEXT.get(st, st)}." + (f" « {h.get('text')[:120]} »" if h.get("text") else ""))
        if st in ("logged_out", "challenge"):
            say("  " + LOGIN_FIX.format(pid))
        elif st == "rate_limited":
            say(f"  Wait for the limit to reset, then run again with --chatbots {pid}")


# --- setup / login ----------------------------------------------------------------------------------------

def cmd_setup(a, mode="setup"):
    from .survey import launch_browser as lb
    from . import web
    if not lb.find_firefox():
        raise SystemExit(f"Firefox is not installed (churvey drives Firefox). Install it:\n  {lb.install_hint()}\nthen run churvey setup again.")
    home.ensure()
    profile = home.profile_dir()
    if mode == "login":
        chatbots = [home.chatbot_id(c) for c in a.chatbot] or home.load_config().get("chatbots") or list(home.CHATBOTS)
    elif a.chatbots:
        chatbots = home.parse_chatbots(a.chatbots)
    elif interactive():
        ans = input(f"Chatbots to set up [{','.join(home.CHATBOTS)}]: ").strip()
        chatbots = home.parse_chatbots(ans) or list(home.CHATBOTS)
    else:
        chatbots = list(home.CHATBOTS)
    if lb.profile_in_use(profile):
        raise SystemExit("The churvey Firefox window is already open. Close it and run this again.")

    signal.signal(signal.SIGTERM, interrupt)   # a `kill` cleans up like Ctrl-C (closes Firefox)
    setup = web.Setup(chatbots, mode, dbg_port=None)
    srv, port = web.serve(setup.api())
    setup.dbg_port = port + 100
    setup.page_url = f"http://127.0.0.1:{port}/"
    url = setup.page_url + "setup.html"
    lb.ensure_prefs(profile)
    ff = lb.start_firefox(profile, setup.dbg_port, url=url)
    stop = threading.Event()
    try:
        lb.install_addon(setup.dbg_port, lb.find_ext_dir())
        threading.Thread(target=setup.run_worker, args=(stop,), daemon=True).start()
        say(f"Firefox is open on the churvey profile ({profile}).")
        say(f"Follow the checklist in its first tab ({url}).")
        say("Waiting for you to press Done there. Ctrl-C to cancel.")
        while not setup.saved.wait(1):
            if ff.poll() is not None:
                say("Firefox was closed before setup was saved. Your sign-ins are kept; run `churvey setup` again to finish.")
                return 1
        time.sleep(4)
    except KeyboardInterrupt:
        say("\ncancelled; sign-ins made so far are kept in the profile")
        return 130
    finally:
        stop.set()
        srv.shutdown()
        if ff.poll() is None:
            ff.terminate()
            try:
                ff.wait(20)
            except subprocess.TimeoutExpired:
                ff.kill()
    cfg = home.load_config()
    say(f"Saved {home.config_path()}: chatbots {', '.join(cfg.get('chatbots', []))}")
    say("Next:\n  churvey questions import my-questions.txt\n  churvey run my-questions\n  churvey export latest")
    return 0


def cmd_login(a):
    return cmd_setup(a, mode="login")


# --- doctor / run -----------------------------------------------------------------------------------------

def cmd_doctor(a):
    from .survey import launch_browser as lb
    cfg = require_setup()
    chatbots = home.parse_chatbots(a.chatbots) or cfg["chatbots"]
    out = home.runs_dir() / "_doctor"
    argv = ["--preflight", "--profile", str(home.profile_dir()), "--providers", ",".join(chatbots), "--out", str(out)]
    if not a.visible:
        argv.append("--headless")
    say(f"Sending one short question to {', '.join(home.LABELS[c] for c in chatbots)}" + ("" if a.visible else " (no window)") + "...")
    rc, state = lb.launch(argv)
    if rc:
        explain_blocked(state.health)
    else:
        say("All chatbots answered. You are ready: churvey run <question-set>")
    return rc


def cmd_run(a):
    from .survey import launch_browser as lb
    cfg = require_setup()
    qs, src = Q.load(a.set)
    if not qs["questions"]:
        raise SystemExit(f"question set '{qs['name']}' has no questions yet: churvey questions add {qs['name']} \"...\"")
    d = qs.get("defaults", {})
    if a.chatbots:
        chatbots = home.parse_chatbots(a.chatbots)
    else:
        wanted = d.get("chatbots") or list(home.CHATBOTS)
        chatbots = [c for c in wanted if c in cfg["chatbots"]]
        skipped = [c for c in wanted if c not in chatbots]
        if skipped:
            say(f"Skipping {', '.join(skipped)}: not set up (add with: churvey login {' '.join(skipped)})")
    if not chatbots:
        raise SystemExit("no chatbots to ask; pass --chatbots or run churvey setup")
    repeat = a.repeat or d.get("repeat", 1)
    private = d.get("private", True)

    run_id = f"{qs['name']}_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}"
    folder = home.runs_dir() / run_id
    folder.mkdir(parents=True)
    (folder / "questions.json").write_text(Q.dump(qs), encoding="utf-8")   # frozen copy: later edits never change this run
    plan = Q.to_run_plan(qs, chatbots, repeat, private)
    (folder / "run-plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False))
    meta = {"run_id": run_id, "question_set": qs["name"], "question_set_sha256": Q.content_hash(qs), "question_set_source": str(src),
            "chatbots": chatbots, "repeat": repeat, "private": private, "headless": not a.visible,
            "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "churvey": version()}
    (folder / "churvey-run.json").write_text(json.dumps(meta, indent=2))

    n = len(qs["questions"]) * repeat
    timeout = a.timeout or 600 + n * len(chatbots) * 120
    say(f"Run {run_id}: {len(qs['questions'])} questions x {repeat} x {len(chatbots)} chatbots -> {folder}")
    argv = ["--run-plan", str(folder / "run-plan.json"), "--profile", str(home.profile_dir()), "--out", str(folder), "--timeout", str(timeout)]
    if not a.visible:
        argv.append("--headless")
    rc, state = lb.launch(argv)
    meta.update(finished_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), exit_code=rc,
                blocked={p: h.get("status") for p, h in state.health.items() if h and h.get("status") not in (None, "ok")})
    (folder / "churvey-run.json").write_text(json.dumps(meta, indent=2))
    explain_blocked(state.health)
    if state.written:
        say(f"Export the answers:  churvey export {run_id}")
    return rc


# --- remote control ----------------------------------------------------------------------------------------

def cmd_control(a):
    from .survey import ffctl
    argv = ["--port", str(a.port), a.cmd]
    if a.cmd in ("pause", "resume", "reload"):
        argv.append(home.chatbot_id(a.chatbot))
    if a.cmd == "stop":
        if not a.yes and not (interactive() and input("Stop the whole run? [y/N] ").strip().lower() == "y"):
            raise SystemExit("not stopped")
        argv.append("--yes")
    try:
        ffctl.main(argv)
    except SystemExit as e:
        if isinstance(e.code, str) and "debugger" in e.code.lower():
            raise SystemExit("No churvey run is going on (nothing listens on the debugger port).")
        raise
    return 0


def cmd_export(a):
    from . import export
    out, rows = export.export(a.run, a.out)
    ok = sum(1 for r in rows if r["status"] == "ok")
    say(f"{len(rows)} answers ({ok} ok) -> {out}")
    return 0


# --- questions ---------------------------------------------------------------------------------------------

def show_errors(errs, warns=()):
    for e in errs:
        say(f"  error: {e}")
    for w in warns:
        say(f"  note: {w}")


def q_new(a):
    if Q.set_path(Q.slugify(a.name, 64)).exists():
        raise SystemExit(f"question set '{a.name}' already exists")
    qs = Q.new_set(a.name, a.description or "", a.language)
    say(f"created {Q.save(qs)}")


def q_list(a):
    sets = Q.list_sets()
    if not sets:
        say(f"no question sets yet in {home.questions_dir()}. Create one: churvey questions import FILE")
    for p in sets:
        try:
            qs = json.loads(p.read_text())
            say(f"{p.stem:24} {len(qs.get('questions', [])):>4} questions  {qs.get('description', '')[:60]}")
        except ValueError:
            say(f"{p.stem:24}  (not valid JSON: churvey questions validate {p.stem})")


def q_show(a):
    qs, p = Q.load(a.set)
    if a.json:
        sys.stdout.write(Q.dump(qs))
        return
    d = qs.get("defaults", {})
    say(f"{qs['name']}: {qs.get('description', '')}  [{p}]")
    say(f"language {qs.get('language', '-')}, chatbots {','.join(d.get('chatbots', []))}, repeat {d.get('repeat', 1)}, private {d.get('private', True)}")
    for i, q in enumerate(qs["questions"], 1):
        extra = "".join([f"  #{','.join(q['tags'])}" if q.get("tags") else "", f"  group={q['group']}" if q.get("group") else ""])
        say(f"{i:>3}. {q['id']}: {q['text']}{extra}")


def q_add(a):
    qs, _ = Q.load(a.set)
    q = {"text": a.text}
    if a.id:
        q["id"] = a.id
    if a.tags:
        q["tags"] = [t.strip() for t in a.tags.split(",") if t.strip()]
    if a.group:
        q["group"] = a.group
    if a.meta:
        q["meta"] = json.loads(a.meta)
    qs["questions"].append(q)
    Q.fill_ids(qs)
    Q.save(qs)
    say(f"added {q['id']} to {qs['name']} ({len(qs['questions'])} questions)")


def q_edit(a):
    qs, p = Q.load(a.set)
    if p.parent != home.questions_dir():
        raise SystemExit(f"{p} is not a saved set; import it first: churvey questions import {p}")
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or ("notepad" if os.name == "nt" else "vi")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(p.read_text(encoding="utf-8"))
        tmp = pathlib.Path(f.name)
    try:
        while True:
            subprocess.call(editor.split() + [str(tmp)])
            text = tmp.read_text(encoding="utf-8")
            try:
                new = json.loads(text)
                errs, warns = Q.validate(new, text)
            except json.JSONDecodeError as e:
                errs, warns = [f"not valid JSON at line {e.lineno}, column {e.colno}: {e.msg}"], []
            if not errs:
                break
            show_errors(errs)
            if not (interactive() and input("Edit again? (no = discard your changes) [Y/n] ").strip().lower() in ("", "y", "yes")):
                raise SystemExit("changes discarded; the saved set is unchanged")
        Q.fill_ids(new)
        if new["name"] != p.stem and Q.set_path(new["name"]).exists():
            raise SystemExit(f"a set named '{new['name']}' already exists; changes discarded")
        Q.save(new)
        if new["name"] != p.stem:
            p.unlink()
        show_errors([], warns)
        say(f"saved {Q.set_path(new['name'])} ({len(new['questions'])} questions)")
    finally:
        tmp.unlink(missing_ok=True)


def q_rm(a):
    qs, p = Q.load(a.set)
    if a.question:
        left = [q for q in qs["questions"] if q["id"] != a.question]
        if len(left) == len(qs["questions"]):
            raise SystemExit(f"no question '{a.question}' in {qs['name']}")
        qs["questions"] = left
        Q.save(qs)
        say(f"removed {a.question} from {qs['name']} ({len(left)} questions left)")
        return
    if p.parent != home.questions_dir():
        raise SystemExit(f"{p} is not a saved set")
    if not a.yes and not (interactive() and input(f"Delete question set '{qs['name']}'? Past runs keep their copy. [y/N] ").strip().lower() == "y"):
        raise SystemExit("not deleted")
    p.unlink()
    say(f"deleted {p}")


def q_import(a):
    try:
        qs = Q.parse_file(a.file, a.name and Q.slugify(a.name, 64))
    except Q.Invalid as e:
        say(f"{a.file} cannot be imported:")
        show_errors(e.errors)
        return 1
    if Q.set_path(qs["name"]).exists() and not a.force:
        raise SystemExit(f"question set '{qs['name']}' already exists. Use --force to replace it, or --name to pick another name.")
    say(f"imported {len(qs['questions'])} questions -> {Q.save(qs)}")
    return 0


def q_export(a):
    qs, _ = Q.load(a.set)
    fmt = a.format or (pathlib.Path(a.out).suffix.lstrip(".") if a.out else "json")
    if fmt == "txt":
        text = "".join(q["text"].replace("\n", " ") + "\n" for q in qs["questions"])
    elif fmt == "csv":
        import csv
        import io
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["id", "text", "tags", "group"])
        for q in qs["questions"]:
            w.writerow([q["id"], q["text"], ";".join(q.get("tags", [])), q.get("group", "")])
        text = buf.getvalue()
    else:
        text = Q.dump(qs)
    if a.out:
        pathlib.Path(a.out).write_text(text, encoding="utf-8")
        say(f"wrote {a.out}")
    else:
        sys.stdout.write(text)


def q_validate(a):
    bad = 0
    targets = a.sets or [p.stem for p in Q.list_sets()]
    if not targets:
        say("nothing to validate")
    for t in targets:
        p = pathlib.Path(t).expanduser()
        p = p if p.is_file() else Q.set_path(t)
        if not p.is_file():
            say(f"{t}: not found")
            bad += 1
            continue
        if p.suffix.lower() in (".txt", ".csv"):
            try:
                qs = Q.parse_file(p)
                errs, warns = [], [f"{len(qs['questions'])} questions would be imported"]
            except Q.Invalid as e:
                errs, warns = e.errors, []
        else:
            text = p.read_text(encoding="utf-8")
            try:
                data = json.loads(text)
                errs, warns = Q.validate(data, text)
            except json.JSONDecodeError as e:
                errs, warns = [f"not valid JSON at line {e.lineno}, column {e.colno}: {e.msg}"], []
        say(f"{p}: {'OK' if not errs else f'{len(errs)} error(s)'}")
        show_errors(errs, warns)
        bad += bool(errs)
    return 1 if bad else 0


def q_ui(a):
    from . import web, qui
    home.ensure()
    srv, port = web.serve(qui.api())
    url = f"http://127.0.0.1:{port}/questions.html"
    say(f"Question editor: {url}   (Ctrl-C to stop)")
    if not a.no_open:
        import webbrowser
        webbrowser.open(url)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


# --- parser ------------------------------------------------------------------------------------------------

def build_parser():
    ap = argparse.ArgumentParser(prog="churvey", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"churvey {version()}")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="COMMAND")

    p = sub.add_parser("setup", help="create the churvey Firefox profile and sign in to the chatbots")
    p.add_argument("--chatbots", help=f"comma list (default: ask; all = {','.join(home.CHATBOTS)})")
    p.set_defaults(fn=cmd_setup)
    p = sub.add_parser("login", help="sign in again to one or more chatbots")
    p.add_argument("chatbot", nargs="*", help="chatbot(s) to sign in to (default: all set up)")
    p.set_defaults(fn=cmd_login)
    p = sub.add_parser("doctor", help="check every chatbot answers (one short question each, no window)")
    p.add_argument("--chatbots", help="comma list (default: those set up)")
    p.add_argument("--visible", action="store_true", help="show the Firefox window")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("run", help="ask a question set to the chatbots")
    p.add_argument("set", help="question set name (see churvey questions list) or a file path")
    p.add_argument("--chatbots", help="comma list (default: the set's defaults that are set up)")
    p.add_argument("--repeat", type=int, help="ask each question N times (default: the set's)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--headless", dest="visible", action="store_false", help="no Firefox window (default)")
    g.add_argument("--visible", dest="visible", action="store_true", help="show the Firefox window")
    p.add_argument("--timeout", type=int, help="give up after N seconds (default: scales with the run size)")
    p.set_defaults(fn=cmd_run, visible=False)

    for name, hlp in (("status", "progress of the run going on"), ("pause", "pause one chatbot in the running run"),
                      ("resume", "resume a paused or blocked chatbot"), ("reload", "reload a chatbot's tab"), ("stop", "stop the run")):
        p = sub.add_parser(name, help=hlp)
        if name in ("pause", "resume", "reload"):
            p.add_argument("chatbot")
        if name == "stop":
            p.add_argument("--yes", action="store_true", help="do not ask for confirmation")
        p.add_argument("--port", type=int, default=8831, help="Firefox debugger port of the run (default 8831)")
        p.set_defaults(fn=cmd_control)

    p = sub.add_parser("export", help="write the clean per-answer JSONL of a run")
    p.add_argument("run", help='run id (folder name in ~/.churvey/runs), "latest", or a path')
    p.add_argument("--out", help="output file (default: <run folder>/responses.clean.jsonl)")
    p.set_defaults(fn=cmd_export)

    p = sub.add_parser("questions", help="create, edit, import and check question sets")
    qs = p.add_subparsers(dest="qcmd", required=True, metavar="ACTION")
    x = qs.add_parser("new", help="create an empty set")
    x.add_argument("name")
    x.add_argument("--description")
    x.add_argument("--language", help="e.g. fr, en")
    x.set_defaults(fn=q_new)
    qs.add_parser("list", help="list saved sets").set_defaults(fn=q_list)
    x = qs.add_parser("show", help="print a set")
    x.add_argument("set")
    x.add_argument("--json", action="store_true")
    x.set_defaults(fn=q_show)
    x = qs.add_parser("add", help="add one question")
    x.add_argument("set")
    x.add_argument("text")
    x.add_argument("--id")
    x.add_argument("--tags", help="comma list")
    x.add_argument("--group")
    x.add_argument("--meta", help="JSON object of extra data")
    x.set_defaults(fn=q_add)
    x = qs.add_parser("edit", help="open a set in $EDITOR, validated on save")
    x.add_argument("set")
    x.set_defaults(fn=q_edit)
    x = qs.add_parser("rm", help="delete a set, or one question from it")
    x.add_argument("set")
    x.add_argument("question", nargs="?", help="question id to remove (omit to delete the whole set)")
    x.add_argument("--yes", action="store_true")
    x.set_defaults(fn=q_rm)
    x = qs.add_parser("import", help="import a .txt, .csv, ff/ run plan or churvey .json file")
    x.add_argument("file")
    x.add_argument("--name", help="set name (default: the file name)")
    x.add_argument("--force", action="store_true", help="replace a set of the same name")
    x.set_defaults(fn=q_import)
    x = qs.add_parser("export", help="write a set as json, txt or csv")
    x.add_argument("set")
    x.add_argument("--out")
    x.add_argument("--format", choices=["json", "txt", "csv"])
    x.set_defaults(fn=q_export)
    x = qs.add_parser("validate", help="check sets or files (default: every saved set)")
    x.add_argument("sets", nargs="*")
    x.set_defaults(fn=q_validate)
    x = qs.add_parser("ui", help="open the question editor in your browser")
    x.add_argument("--no-open", action="store_true", help="only print the address")
    x.set_defaults(fn=q_ui)
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    try:
        return a.fn(a) or 0
    except Q.Invalid as e:
        say("The question set is not valid:")
        show_errors(e.errors)
        return 1


if __name__ == "__main__":
    sys.exit(main())
