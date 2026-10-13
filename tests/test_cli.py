import contextlib
import io
import json
import os
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Parser(unittest.TestCase):
    def parse(self, *argv):
        from churvey.cli import build_parser
        return build_parser().parse_args(list(argv))

    def test_run_defaults_headless(self):
        a = self.parse("run", "pilot20")
        self.assertEqual((a.set, a.visible, a.repeat, a.chatbots), ("pilot20", False, None, None))

    def test_run_flags(self):
        a = self.parse("run", "x.json", "--chatbots", "claude,lechat", "--repeat", "3", "--visible")
        self.assertEqual((a.chatbots, a.repeat, a.visible), ("claude,lechat", 3, True))
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.parse("run", "x", "--visible", "--headless")

    def test_login_many(self):
        self.assertEqual(self.parse("login", "claude", "grok").chatbot, ["claude", "grok"])
        self.assertEqual(self.parse("login").chatbot, [])

    def test_controls(self):
        self.assertEqual(self.parse("pause", "mistral").chatbot, "mistral")
        self.assertTrue(self.parse("stop", "--yes").yes)
        self.assertEqual(self.parse("status", "--port", "8832").port, 8832)

    def test_questions_subcommands(self):
        for argv in (["questions", "list"], ["questions", "new", "s"], ["questions", "show", "s", "--json"], ["questions", "add", "s", "Q?", "--tags", "a,b"],
                     ["questions", "edit", "s"], ["questions", "rm", "s", "q1"], ["questions", "import", "f.txt", "--name", "n"],
                     ["questions", "export", "s", "--format", "csv"], ["questions", "validate"], ["questions", "ui", "--no-open"]):
            self.assertTrue(callable(self.parse(*argv).fn), argv)

    def test_chatbot_aliases(self):
        from churvey import home
        self.assertEqual(home.parse_chatbots("ChatGPT, lechat,claude,chatgpt"), ["chatgpt", "mistral", "claude"])
        with self.assertRaises(SystemExit):
            home.parse_chatbots("bard2")


class Commands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["CHURVEY_HOME"] = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("CHURVEY_HOME", None)

    def run_cli(self, *argv):
        from churvey.cli import main
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = main(list(argv))
        return rc, out.getvalue()

    def test_import_list_add_validate_rm(self):
        self.assertEqual(self.run_cli("questions", "import", str(ROOT / "examples/hello.txt"))[0], 0)
        rc, out = self.run_cli("questions", "list")
        self.assertIn("hello", out)
        self.run_cli("questions", "add", "hello", "One more?", "--id", "more", "--meta", '{"k": 1}')
        rc, out = self.run_cli("questions", "validate")
        self.assertEqual(rc, 0, out)
        self.run_cli("questions", "rm", "hello", "more")
        rc, out = self.run_cli("questions", "show", "hello", "--json")
        self.assertEqual(len(json.loads(out)["questions"]), 2)

    def test_validate_reports_errors(self):
        p = pathlib.Path(self.tmp.name) / "bad.json"
        p.write_text(json.dumps({"schema": "churvey/questions@1", "name": "Bad Name", "questions": [{"id": "a"}]}, indent=2))
        rc, out = self.run_cli("questions", "validate", str(p))
        self.assertEqual(rc, 1)
        self.assertIn('"name" must be', out)
        self.assertIn("question 1 (line 5)", out)

    def test_run_requires_setup(self):
        with self.assertRaises(SystemExit) as cm:
            self.run_cli("run", str(ROOT / "examples/hello.txt"))
        self.assertIn("churvey setup", str(cm.exception.code))

    def test_export_normalises_records(self):
        run = pathlib.Path(self.tmp.name) / "runs" / "r1"
        run.mkdir(parents=True)
        rec = {"provider": "gemini", "questionId": "q1", "questionText": "Q?", "responseText": "Answer <FollowUp label=\"x\" query=\"y\"/>",
               "citations": [{"url": "https://ex.org/a?utm_source=x#:~:text=hi", "via": "gemini_grounding"}], "fetchedUrls": ["https://ex.org/a"],
               "status": "ok", "recordId": "1", "runId": "run_x", "repIndex": 0, "itemKey": "neutral#r0#q1", "capture_method": "stream"}
        (run / "run_x.jsonl").write_text(json.dumps(rec) + "\n")
        (run / "churvey-run.json").write_text(json.dumps({"question_set": "s", "question_set_sha256": "abc"}))
        (run / "questions.json").write_text(json.dumps({"questions": [{"id": "q1", "text": "Q?", "group": "g1"}]}))
        rc, out = self.run_cli("export", "latest")
        row = json.loads((run / "responses.clean.jsonl").read_text())
        self.assertEqual(row["response_text"], "Answer")
        self.assertEqual(row["citations"][0]["url"], "https://ex.org/a")
        self.assertEqual(row["displayed_urls"], ["https://ex.org/a"])
        self.assertEqual((row["group"], row["question_set"]["sha256"], row["capture_method"]), ("g1", "abc", "stream"))


if __name__ == "__main__":
    unittest.main()
