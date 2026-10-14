import json
import os
import pathlib
import plistlib
import tempfile
import unittest

from churvey import account as A, probe as P


def fp_home(**sel):
    return {"selectors": {"composer": "#prompt-textarea", "send": 'button[data-testid="send-button"]', **sel},
            "labels": ["Send prompt", "Turn on temporary chat"]}


SIGNED_IN = {
    "login": {"state": {"signedIn": True, "account": "a@b.c", "how": "/api/auth/session 200 user"}, "page": {"ok": True, "state": "ok", "text": ""}},
    "home": {"fingerprint": fp_home()},
    "temporary": {"url": "https://chatgpt.com/?temporary-chat=true", "fingerprint": fp_home(),
                  "state": {"ok": True, "temporary": True, "newChat": True, "evidence": "page /?temporary-chat=true, 'Turn off temporary chat' switch"}},
    "new_chat": {"url": "https://chatgpt.com/", "state": {"ok": True, "temporary": False, "newChat": True, "evidence": "page /"}},
    "shapes": {"memory": "200 sunshine:boolean moonshine:boolean", "list": "200 items:array total:number"},
    "banner": {"before": {"state": "ok", "banner": None}, "during": {"state": "rate_limited", "banner": "You've reached your message limit."}},
    "memory": {"status": "off", "detail": "sunshine=false"},
    "controls": {"switches": [{"label": "Enable memory", "checked": False}]},
    "list": {"count": 12},
}


def rec(qid, text, method="stream", status="ok", cites=(), dom=None):
    return {"questionId": qid, "itemKey": qid, "status": status, "responseText": text, "capture_method": method if status == "ok" else None,
            "citations": [{"url": u} for u in cites], "domSources": {"links": [{"url": u} for u in cites]},
            "probe": {"dom": {"text": text if dom is None else dom, "len": len(text)}}, "errorMessage": None if status == "ok" else "boom"}


RECS = [rec("canary1", "OK"), rec("canary2", "Je ne sais pas de quel mot de code vous parlez."),
        rec("probe_cite", "Vierzon a inauguré une nouvelle médiathèque cette semaine selon la presse locale.", cites=["https://www.leberry.fr/x"])]


class Assemble(unittest.TestCase):
    def test_signed_in_all_pass(self):
        r = P.assemble("chatgpt", SIGNED_IN, RECS, {"c1": "unsupported", "c2": "unsupported"}, None, ("PASS", "chat 2: « … »"))
        st = {k: v["status"] for k, v in r["checks"].items()}
        self.assertEqual([k for k, _ in P.CHECKS], list(st))
        self.assertEqual(st["logged_in"], "PASS")
        self.assertEqual(st["temporary_chat"], "PASS")
        self.assertEqual(st["stream_capture"], "PASS")
        self.assertEqual(st["poll_capture"], "N/A")
        self.assertEqual(st["dom_fallback"], "PASS")
        self.assertEqual(st["citations"], "PASS")
        self.assertEqual(st["memory_toggle"], "PASS")
        self.assertEqual(st["delete_one"], "N/A")
        self.assertEqual(st["canary"], "PASS")
        self.assertEqual(r["fingerprint"]["submit"]["home.composer"], "#prompt-textarea")
        self.assertEqual(r["fingerprint"]["temporary_chat"]["labels.temp"], "Turn on temporary chat")
        self.assertEqual(r["fingerprint"]["stream_capture"]["methods"], "stream")

    def test_signed_out_skips_what_needs_an_account(self):
        raw = {"login": {"state": {"signedIn": False, "how": "/api/auth/session 200 no user"}, "page": {"state": "logged_out", "text": '"Log in" button visible'}},
               "banner": SIGNED_IN["banner"], "memory": {"status": "unknown", "detail": "not signed in"}, "list": {"error": "not signed in"},
               "temporary": {"state": {"ok": True, "temporary": False, "newChat": True, "evidence": "page /, no temporary-chat switch"}}}
        r = P.assemble("chatgpt", raw, [], {}, None, None)
        st = {k: v["status"] for k, v in r["checks"].items()}
        self.assertEqual(st["logged_in"], "PASS")
        self.assertFalse(r["signed_in"])
        for k in ("temporary_chat", "submit", "memory_readable", "memory_toggle", "delete_all_available", "canary"):
            self.assertEqual(st[k], "SKIP", k)
        self.assertEqual(st["banner_detection"], "PASS")

    def test_failures(self):
        raw = dict(SIGNED_IN, banner={"before": {"state": "ok"}, "during": {"state": "ok", "banner": None}},
                   controls={"switches": [{"label": "Enable memory", "checked": True}]})
        recs = [rec("canary1", "OK", method="dom_fallback"), rec("canary2", "x", status="error"),
                rec("probe_cite", "Une réponse sans aucune source affichée par la page.", method="dom_fallback", cites=(), dom="tout autre chose ici affiché")]
        r = P.assemble("chatgpt", raw, recs, {"c1": "error 500"}, None, ("FAIL", "chat 2 answered: « girafe-47 »"))
        st = {k: v["status"] for k, v in r["checks"].items()}
        self.assertEqual(st["banner_detection"], "FAIL")
        self.assertEqual(st["memory_toggle"], "FAIL")          # a switch is on while the setting reads off
        self.assertEqual(st["stream_capture"], "FAIL")         # answers came by dom_fallback only
        self.assertEqual(st["dom_fallback"], "FAIL")
        self.assertEqual(st["citations"], "FAIL")
        self.assertEqual(st["delete_one"], "FAIL")
        self.assertEqual(st["canary"], "FAIL")

    def test_grok_is_polled_and_its_page_text_compared(self):
        # 2026-10-14 baseline: Grok's answers came by poll; the probe expected dom_fallback and failed it.
        recs = [rec(r["questionId"], r["responseText"], method="poll", cites=[c["url"] for c in r["citations"]]) for r in RECS]
        st = {k: v["status"] for k, v in P.assemble("grok", SIGNED_IN, recs, {}, None, None)["checks"].items()}
        self.assertEqual((st["poll_capture"], st["stream_capture"], st["dom_fallback"]), ("PASS", "N/A", "PASS"))

    def test_rate_limited_is_skip_not_fail(self):
        recs = [rec("canary1", "x", status="error")]
        r = P.assemble("grok", SIGNED_IN, recs, {}, {"status": "rate_limited", "text": "2 hours before limit is gone"}, ("rate_limited", "…"))
        self.assertEqual(r["checks"]["canary"]["status"], "SKIP")
        self.assertEqual(r["checks"]["submit"]["status"], "SKIP")
        self.assertEqual(r["checks"]["stream_capture"]["status"], "N/A")


class Popups(unittest.TestCase):
    def check(self, popups=None, recs=RECS, health=None):
        raw = dict(SIGNED_IN, **({"popups": popups} if popups is not None else {}))
        return P.assemble("claude", raw, recs, {}, health, ("PASS", ""))

    def test_none_seen(self):
        r = self.check([{"stage": "probe_home", "events": [], "blocking": None}])
        self.assertEqual(r["checks"]["popups"]["status"], "PASS")
        self.assertEqual(r["fingerprint"]["popups"]["seen"], "none")

    def test_handled_and_fingerprinted(self):
        ev = {"class": "cookie", "action": 'clicked "Tout refuser"', "text_snippet": "Nous utilisons des cookies"}
        recs = [dict(RECS[0], popups=[{"class": "announcement", "action": "escape", "text_snippet": "What's new"}])] + RECS[1:]
        r = self.check([{"stage": "probe_home", "events": [ev], "blocking": None}], recs)
        self.assertEqual(r["checks"]["popups"]["status"], "PASS")
        self.assertEqual(r["fingerprint"]["popups"]["seen"], 'announcement: escape | cookie: clicked "Tout refuser"')

    def test_left_in_the_way_fails(self):
        b = {"class": "unknown", "text": "Something odd", "reason": "unknown dialog"}
        r = self.check([{"stage": "probe_temporary", "events": [{"class": "unknown", "action": "paused"}], "blocking": b}])
        self.assertEqual(r["checks"]["popups"]["status"], "FAIL")
        self.assertIn("Something odd", r["checks"]["popups"]["detail"])
        r = self.check([], health={"status": "popup_unknown", "text": "unknown dialog: Hello"})
        self.assertEqual(r["checks"]["popups"]["status"], "FAIL")

    def test_new_popup_is_a_change(self):
        old = {"claude": self.check([])}
        new = {"claude": self.check([{"stage": "probe_home", "events": [{"class": "terms", "action": 'clicked "Accept"'}], "blocking": None}])}
        ch = P.diff_fingerprints(old, new)
        self.assertEqual([(c["check"], c["old"]) for c in ch], [("popups", "none")])


class Diff(unittest.TestCase):
    def test_changed_selector_and_unobserved_check(self):
        old = {"chatgpt": {"fingerprint": {"temporary_chat": {"home.private": "a[x]", "labels.home": "A"}, "memory_readable": {"endpoint.memory": "200 sunshine:boolean"}}}}
        new = {"chatgpt": {"fingerprint": {"temporary_chat": {"home.private": None, "labels.home": "A"}}},   # memory not observed this time
               "claude": {"fingerprint": {"submit": {"home.send": "b"}}}}                                  # no earlier claude
        d = P.diff_fingerprints(old, new)
        self.assertEqual(d, [{"chatbot": "chatgpt", "check": "temporary_chat", "key": "home.private", "old": "a[x]", "new": None}])

    def test_key_appearing_is_a_change(self):
        d = P.diff_fingerprints({"g": {"fingerprint": {"submit": {"a": 1}}}}, {"g": {"fingerprint": {"submit": {"a": 1, "b": 2}}}})
        self.assertEqual([(c["key"], c["old"], c["new"]) for c in d], [("b", None, 2)])

    def test_mark_changed_only_touches_pass(self):
        res = {"g": {"checks": {"submit": {"status": "PASS"}, "new_chat": {"status": "FAIL"}}}}
        P.mark_changed(res, [{"chatbot": "g", "check": "submit"}, {"chatbot": "g", "check": "new_chat"}])
        self.assertEqual(res["g"]["checks"]["submit"]["status"], "CHANGED")
        self.assertEqual(res["g"]["checks"]["new_chat"]["status"], "FAIL")

    def test_previous_picks_latest_earlier_report(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            for n in ("2026-09-01", "2026-10-01", "2026-10-01_2", "2026-11-01"):
                (root / n).mkdir()
                if n != "2026-10-01_2":
                    (root / n / "report.json").write_text("{}")
            self.assertEqual(P.previous(root / "2026-11-01").name, "2026-10-01")
            self.assertIsNone(P.previous(root / "2026-09-01"))


class Report(unittest.TestCase):
    def rep(self):
        a = P.assemble("chatgpt", SIGNED_IN, RECS, {"c1": "unsupported"}, None, ("PASS", "ok"))
        b = P.assemble("grok", {"login": {"state": {"signedIn": False}, "page": {"state": "logged_out"}}}, [], {}, None, None)
        b["checks"]["banner_detection"]["evidence"]["screenshot"] = "grok_banner_detection.png"
        res = {"chatgpt": a, "grok": b}
        ch = [{"chatbot": "chatgpt", "check": "submit", "key": "home.send", "old": "x", "new": "y"}]
        P.mark_changed(res, ch)
        return {"date": "2026-11-01", "chatbots": ["chatgpt", "grok"], "destructive": False, "messages": 3, "previous": "2026-10-01", "changes": ch, "results": res}

    def test_markdown(self):
        md = P.render_report(self.rep())
        self.assertIn("# churvey probe, 2026-11-01", md)
        self.assertIn("| check | ChatGPT | Grok |", md)
        self.assertIn("| submit | **CHANGED** | SKIP |", md)
        self.assertIn("ChatGPT · submit · `home.send`: `x` → `y`", md)
        self.assertIn("Grok · banner_detection", md)
        self.assertIn("[screenshot](grok_banner_detection.png)", md)
        self.assertEqual(sum(1 for line in md.splitlines() if line.startswith("| ") and "|---" not in line and line.split("|")[1].strip() in dict(P.CHECKS)), 3 * len(P.CHECKS))

    def test_report_json_roundtrip_and_summary(self):
        rep = self.rep()
        self.assertEqual(json.loads(json.dumps(rep, ensure_ascii=False)), rep)
        lines = P.summary_lines(rep, pathlib.Path("/x"))
        self.assertTrue(any("CHANGED ChatGPT submit home.send: x -> y" in l for l in lines))
        self.assertTrue(lines[-1].endswith("/x/report.md"))

    def test_baseline_says_so(self):
        rep = dict(self.rep(), previous=None, changes=[])
        self.assertIn("this one is the baseline", P.render_report(rep))


class Schedule(unittest.TestCase):
    def test_launchd_plist_is_valid(self):
        name, body, how = P.schedule_file("darwin", ["/usr/local/bin/churvey"], {})
        self.assertEqual(name, "com.churvey.probe.plist")
        pl = plistlib.loads(body.encode())
        self.assertEqual(pl["ProgramArguments"], ["/usr/local/bin/churvey", "probe"])
        self.assertEqual(pl["StartCalendarInterval"], {"Day": 1, "Hour": 9, "Minute": 0})
        self.assertIn("launchctl bootstrap", how)

    def test_cron_line(self):
        name, body, how = P.schedule_file("linux", ["/usr/bin/churvey"], {"CHURVEY_HOME": "/h"})
        self.assertTrue(body.startswith("0 9 1 * * CHURVEY_HOME=/h /usr/bin/churvey probe >> "))
        self.assertIn("crontab", how)

    def test_install_writes_but_does_not_load(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["CHURVEY_HOME"] = d
            try:
                out = []
                p = P.install_schedule(out.append)
                self.assertTrue(p.is_file())
                self.assertTrue(str(p).startswith(d))
                self.assertIn("Not loaded", out[0])
            finally:
                del os.environ["CHURVEY_HOME"]


class Account(unittest.TestCase):
    READ = {"whoami": {"chatgpt": {"signedIn": True, "account": "a@b.c"}, "claude": {"signedIn": True}, "grok": {"signedIn": False}},
            "memory": {"chatgpt": {"status": "on", "detail": "sunshine=true"}, "claude": {"status": "off"}, "grok": {"status": "unknown"}},
            "list": {"chatgpt": {"ids": ["a", "b"]}, "claude": {"ids": []}, "grok": {"error": "x"}}}

    def test_plan(self):
        acts, lines = A.plan(["chatgpt", "claude", "grok"], self.READ)
        self.assertEqual(acts, {"chatgpt": {"memory_off": True, "delete_all": True}, "claude": {"memory_off": False, "delete_all": False},
                                "grok": {"memory_off": False, "delete_all": False}})
        text = "\n".join(lines)
        self.assertIn("ChatGPT (a@b.c)", text)
        self.assertIn("delete ALL of them: bulk: PATCH /backend-api/conversations", text)
        self.assertIn("NOT signed in", text)

    def test_outcome_verifies_readback(self):
        acts = {"chatgpt": {"memory_off": True, "delete_all": True}}
        done = {"memoryOff": {"chatgpt": {"before": {"status": "on"}, "after": {"status": "off"}}},
                "deleteAll": {"chatgpt": {"method": "bulk", "before": 2, "after": 0, "results": {}}}}
        ok, lines = A.outcome(["chatgpt"], acts, done)
        self.assertEqual(ok, {"chatgpt": True})
        done["deleteAll"]["chatgpt"]["after"] = 1
        self.assertEqual(A.outcome(["chatgpt"], acts, done)[0], {"chatgpt": False})

    def test_dry_run_changes_nothing(self):
        calls = []
        orig = A.I.maintain
        A.I.maintain = lambda m, *a, **k: calls.append(m) or self.READ
        with tempfile.TemporaryDirectory() as d:
            os.environ["CHURVEY_HOME"] = d
            try:
                rc = A.prepare(["chatgpt", "claude", "grok"], dry_run=True, say=lambda *a: None, ask=lambda *_: self.fail("asked"))
                self.assertEqual(rc, 0)
                self.assertEqual(len(calls), 1)
                self.assertNotIn("memoryOff", calls[0])
                logs = list(pathlib.Path(d, "account").glob("prepare_*/prepare.json"))
                self.assertTrue(json.loads(logs[0].read_text())["dry_run"])
            finally:
                A.I.maintain = orig
                del os.environ["CHURVEY_HOME"]

    def test_wrong_confirmation_changes_nothing(self):
        calls = []
        orig = A.I.maintain
        A.I.maintain = lambda m, *a, **k: calls.append(m) or self.READ
        with tempfile.TemporaryDirectory() as d:
            os.environ["CHURVEY_HOME"] = d
            try:
                self.assertEqual(A.prepare(["chatgpt"], say=lambda *a: None, ask=lambda *_: "yes"), 1)
                self.assertEqual(len(calls), 1)
            finally:
                A.I.maintain = orig
                del os.environ["CHURVEY_HOME"]


if __name__ == "__main__":
    unittest.main()
