import json
import os
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        os.environ["CHURVEY_HOME"] = str(self.dir / "home")

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("CHURVEY_HOME", None)

    def write(self, name, text):
        p = self.dir / name
        p.write_text(text, encoding="utf-8")
        return p


class Import(Base):
    def test_txt_skips_comments_and_blanks(self):
        from churvey import questions as Q
        qs = Q.parse_file(self.write("hello.txt", "# c\n\nQuelle heure est-il ?\n  Why?  \n"))
        self.assertEqual([q["text"] for q in qs["questions"]], ["Quelle heure est-il ?", "Why?"])
        self.assertEqual(qs["name"], "hello")
        self.assertEqual(qs["questions"][0]["id"], "quelle-heure-est-il")

    def test_duplicate_texts_get_unique_ids(self):
        from churvey import questions as Q
        qs = Q.parse_file(self.write("d.txt", "Same?\nSame?\n"))
        self.assertEqual([q["id"] for q in qs["questions"]], ["same", "same-2"])

    def test_csv_with_header_tags_and_extra_columns(self):
        from churvey import questions as Q
        qs = Q.parse_file(self.write("c.csv", "id,text,tags,answer\nq1,\"Is it, really?\",a;b,yes\n,No id here,,\n"))
        q1, q2 = qs["questions"]
        self.assertEqual(q1, {"id": "q1", "text": "Is it, really?", "tags": ["a", "b"], "meta": {"answer": "yes"}})
        self.assertEqual(q2["id"], "no-id-here")

    def test_csv_without_header(self):
        from churvey import questions as Q
        qs = Q.parse_file(self.write("c.csv", "First question\nSecond question\n"))
        self.assertEqual(len(qs["questions"]), 2)

    def test_run_plan_keeps_extra_keys_in_meta(self):
        from churvey import questions as Q
        plan = {"providers": ["claude", "gemini"], "repetitions": 3, "config": {"private": False},
                "questions": [{"id": "a", "text": "A?", "tags": ["x"], "form": "open"}, {"id": "b", "text": "B?", "followup_of": "a"}]}
        qs = Q.parse_file(self.write("plan.json", json.dumps(plan)), "imported")
        self.assertEqual(qs["defaults"], {"chatbots": ["claude", "gemini"], "repeat": 3, "private": False})
        self.assertEqual(qs["questions"][0]["meta"], {"form": "open"})
        rp = Q.to_run_plan(qs, ["claude"], 1, True)
        self.assertEqual(rp["questions"][1]["followup_of"], "a")    # meta.followup_of reaches the extension
        self.assertNotIn("form", rp["questions"][0])

    def test_examples_are_valid(self):
        from churvey import questions as Q
        p20 = Q.parse_file(ROOT / "examples/pilot20.questions.json")
        self.assertEqual(len(p20["questions"]), 20)
        self.assertIn("premise_false", p20["questions"][1]["meta"])
        self.assertEqual(len(Q.parse_file(ROOT / "examples/hello.txt")["questions"]), 2)


class Validate(Base):
    def good(self):
        return {"schema": "churvey/questions@1", "name": "s", "questions": [{"id": "a", "text": "A?"}]}

    def test_good(self):
        from churvey import questions as Q
        self.assertEqual(Q.validate(self.good()), ([], []))

    def test_errors_are_readable_and_carry_line_numbers(self):
        from churvey import questions as Q
        bad = self.good()
        bad["questions"] += [{"id": "a", "text": ""}, {"text": "C", "answer": 1}]
        text = json.dumps(bad, indent=2)
        errs, warns = Q.validate(bad, text)
        joined = "\n".join(errs)
        self.assertIn('duplicate id "a"', joined)
        self.assertIn('"text" is required', joined)
        self.assertIn('unknown field "answer" (put extra data in "meta")', joined)
        line2 = text.splitlines().index("    {", text.splitlines().index("    {") + 1) + 1
        self.assertIn(f"question 2 (line {line2})", joined)
        self.assertEqual(warns, ["question 3 (line %d): no id; one will be generated from the text" % (text.count("\n", 0, text.rindex("    {")) + 1)])

    def test_bad_defaults_and_schema(self):
        from churvey import questions as Q
        bad = self.good()
        bad.update(schema="v0", defaults={"chatbots": ["bard"], "repeat": 0})
        errs, _ = Q.validate(bad)
        self.assertEqual(len(errs), 3)

    def test_invalid_json_reports_line(self):
        from churvey import questions as Q
        with self.assertRaises(Q.Invalid) as cm:
            Q.parse_file(self.write("x.json", '{\n "schema": "churvey/questions@1",\n "name": "x"\n "questions": []}'))
        self.assertIn("line 4", cm.exception.errors[0])

    def test_schema_file_matches_constants(self):
        from churvey import questions as Q
        schema = json.loads((ROOT / "schema/questions.schema.json").read_text())
        self.assertEqual(schema["properties"]["schema"]["const"], Q.SCHEMA)
        self.assertEqual(set(schema["properties"]), Q.TOP_KEYS)
        self.assertEqual(set(schema["properties"]["questions"]["items"]["properties"]), Q.Q_KEYS)


class Hash(Base):
    def test_hash_ignores_key_order_and_sees_edits(self):
        from churvey import questions as Q
        a = {"schema": "churvey/questions@1", "name": "s", "questions": [{"id": "a", "text": "A?"}]}
        b = json.loads(json.dumps(a, sort_keys=True))
        self.assertEqual(Q.content_hash(a), Q.content_hash(dict(reversed(list(b.items())))))
        b["questions"][0]["text"] = "A ?"
        self.assertNotEqual(Q.content_hash(a), Q.content_hash(b))


class Storage(Base):
    def test_save_load_by_name_and_path(self):
        from churvey import questions as Q
        qs = Q.parse_file(self.write("hello.txt", "Hi?\n"))
        p = Q.save(qs)
        self.assertEqual(Q.load("hello")[0], qs)
        self.assertEqual(Q.load(str(p))[0], qs)
        with self.assertRaises(SystemExit):
            Q.load("nope")


if __name__ == "__main__":
    unittest.main()
