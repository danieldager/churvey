"""content/popups.js against the fixture dialogs of test/popups/cases.js, in a headless Firefox on a throwaway profile.

The page test/popups/harness.html runs every case and POSTs the result here. Skipped when Firefox is not installed.
"""
import http.server
import json
import pathlib
import subprocess
import tempfile
import threading
import unittest

from churvey.survey import launch_browser as lb

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULT = None


def run_harness(timeout=90):
    got = threading.Event()
    box = {}

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(ROOT), **k)

        def do_POST(self):
            box["r"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()
            got.set()

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/test/popups/harness.html?post=1"
    with tempfile.TemporaryDirectory() as prof:
        ff = subprocess.Popen([str(lb.find_firefox()), "--profile", prof, "--no-remote", "--new-instance", "--headless",
                               "--window-size", "1280,900", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            got.wait(timeout)
        finally:
            ff.terminate()
            try:
                ff.wait(20)
            except subprocess.TimeoutExpired:
                ff.kill()
            srv.shutdown()
    return box.get("r")


@unittest.skipUnless(lb.find_firefox(), "Firefox not installed")
class PopupFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global RESULT
        RESULT = RESULT or run_harness()
        if not RESULT:
            raise unittest.SkipTest("the harness page never reported back")

    def test_each_case(self):
        for c in RESULT["cases"]:
            e = c["expect"]
            with self.subTest(c["name"]):
                self.assertIsNone(c["error"])
                self.assertTrue(c["scanned"], "overlay not found")
                self.assertEqual(c["scanned"][0]["cls"], e["class"])
                if "kind" in e:
                    self.assertEqual(c["scanned"][0]["kind"], e["kind"])
                if "blocking" in e:
                    self.assertEqual(c["scanned"][0]["blocking"], e["blocking"])
                for bad in e["never"]:
                    self.assertNotIn(bad, c["clicks"], f"clicked a never-click button: {bad}")
                self.assertEqual(c["clicks"], [e["clicked"]] if e["clicked"] else [])
                acts = [ev["action"] for ev in c["events"]]
                if "action" in e:
                    self.assertTrue(any(a.startswith(e["action"]) for a in acts), acts)
                left = any(a.startswith(("paused", "stuck")) for a in acts)
                self.assertEqual(c["blocking"] is not None, left, acts)
                if e.get("prominent"):
                    self.assertTrue(any(ev["prominent"] for ev in c["events"]))

    def test_extension_scripts_parse(self):
        self.assertEqual(RESULT["syntax"], [])

    def test_never_click_guard(self):
        g = RESULT["guard"]
        for k in ("g1", "g2", "g3", "g4", "g5", "g6", "g7", "g8"):
            self.assertIsNotNone(g[k], k)
        self.assertIsNone(g["ok1"])
        self.assertIsNone(g["ok2"])


if __name__ == "__main__":
    unittest.main()
