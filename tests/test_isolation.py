import json
import pathlib
import tempfile
import types
import unittest


class Order(unittest.TestCase):
    def test_pairs_are_spread(self):
        from churvey import questions as Q
        qs = [{"id": f"{g}{k}", "group": f"g{g}"} for g in range(5) for k in range(2)]   # back to back in file order
        self.assertEqual(Q.min_group_gap(qs), 0)
        self.assertGreaterEqual(Q.min_group_gap(Q.spaced_order(qs)), 3)
        self.assertEqual(sorted(q["id"] for q in Q.spaced_order(qs)), sorted(q["id"] for q in qs))

    def test_followups_keep_order(self):
        from churvey import questions as Q
        qs = [{"id": "a", "group": "g"}, {"id": "b", "group": "g", "meta": {"followup_of": "a"}}, {"id": "c"}]
        self.assertEqual([q["id"] for q in Q.spaced_order(qs)], ["a", "b", "c"])

    def test_run_plan_carries_group_and_order(self):
        from churvey import questions as Q
        qs = {"questions": [{"id": "a1", "text": "?", "group": "a"}, {"id": "a2", "text": "?", "group": "a"}, {"id": "b1", "text": "?"}]}
        rp = Q.to_run_plan(qs, ["claude"], 1, True)
        self.assertEqual([q["id"] for q in rp["questions"]], ["a1", "b1", "a2"])
        self.assertEqual(rp["questions"][0]["group"], "a")


class Leftovers(unittest.TestCase):
    def test_only_undeleted_chats_are_left(self):
        from churvey import isolation as I
        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d) / "run1"
            f.mkdir()
            (f / "chats.jsonl").write_text("".join(json.dumps({"provider": p, "chat_id": c}) + "\n" for p, c in
                                                   [("claude", "x"), ("claude", "y"), ("gemini", "z"), ("grok", "w")]))
            (f / "purged.jsonl").write_text("".join(json.dumps({"provider": p, "chat_id": c, "result": r}) + "\n" for p, c, r in
                                                    [("claude", "x", "deleted"), ("gemini", "z", "unsupported"), ("grok", "w", "error 500")]))
            self.assertEqual(I.run_folders(pathlib.Path(d)), [f])
            self.assertEqual(I.leftovers([f]), {f: {"claude": ["y"], "grok": ["w"]}})

    def test_tally(self):
        from churvey import isolation as I
        t = I.tally({"chatgpt": {"a": "unsupported", "b": "deleted"}, "grok": {"c": "error 500", "d": "not_found"}})
        self.assertEqual(t["chatgpt"], {"deleted": 1, "not_found": 0, "unsupported": 1, "failed": 0})
        self.assertEqual(t["grok"], {"deleted": 0, "not_found": 1, "unsupported": 0, "failed": 1})


class Canary(unittest.TestCase):
    def state(self, recs, health=None):
        return types.SimpleNamespace(manifest={"records": recs}, health=health or {})

    def rec(self, q, text, chat, new=True, temp=True, status="ok"):
        return {"provider": "claude", "questionId": q, "status": status, "responseText": text, "errorMessage": None,
                "isolation": {"new_chat": new, "temporary": temp, "chat_id": chat, "evidence": "e"}}

    def test_pass(self):
        from churvey import isolation as I
        v = I.canary_verdicts(self.state([self.rec("canary1", "OK", "c1"), self.rec("canary2", "Aucun mot de code.", "c2")]), ["claude"])
        self.assertEqual(v["claude"][0], "PASS")

    def test_leak_fails(self):
        from churvey import isolation as I
        v = I.canary_verdicts(self.state([self.rec("canary1", "OK", "c1"), self.rec("canary2", "Le code était girafe-47.", "c2")]), ["claude"])
        self.assertEqual(v["claude"][0], "FAIL")

    def test_same_chat_or_not_temporary_fails(self):
        from churvey import isolation as I
        same = I.canary_verdicts(self.state([self.rec("canary1", "OK", "c1"), self.rec("canary2", "Aucun.", "c1")]), ["claude"])
        notemp = I.canary_verdicts(self.state([self.rec("canary1", "OK", "c1", temp=False), self.rec("canary2", "Aucun.", "c2")]), ["claude"])
        self.assertEqual((same["claude"][0], notemp["claude"][0]), ("FAIL", "FAIL"))

    def test_blocked(self):
        from churvey import isolation as I
        v = I.canary_verdicts(self.state([], {"claude": {"status": "rate_limited", "text": "limit"}}), ["claude"])
        self.assertEqual(v["claude"], ("rate_limited", "limit"))


class Parser(unittest.TestCase):
    def test_flags(self):
        from churvey.cli import build_parser
        a = build_parser().parse_args(["run", "s", "--keep-chats", "--allow-memory-unknown"])
        self.assertTrue(a.keep_chats and a.allow_memory_unknown)
        a = build_parser().parse_args(["purge", "--everything", "--chatbot", "claude"])
        self.assertEqual((a.everything, a.chatbot), (True, "claude"))
        self.assertEqual(build_parser().parse_args(["purge", "--run", "latest"]).run, "latest")


if __name__ == "__main__":
    unittest.main()
