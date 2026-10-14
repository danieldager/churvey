import os
import pathlib
import tempfile
import unittest
from unittest import mock

from churvey.survey import launch_browser as lb


class StartupCache(unittest.TestCase):
    def test_cleared_in_every_local_dir(self):
        with tempfile.TemporaryDirectory() as t:
            home = pathlib.Path(t)
            profile = home / "ff" / "Profiles" / "cn-harvest"
            with mock.patch.object(pathlib.Path, "home", return_value=home):
                dirs = lb.startup_cache_dirs(profile)
                for d in dirs:
                    d.mkdir(parents=True)
                    (d / "startupCache.4.little").write_text("x")
                (profile / "prefs.js").write_text("keep")
                lb.clear_startup_cache(profile)
            self.assertEqual([d.exists() for d in dirs], [False, False, False])
            self.assertEqual((profile / "prefs.js").read_text(), "keep")
            self.assertIn(home / "Library/Caches/Firefox/Profiles/cn-harvest/startupCache", dirs)
            self.assertFalse(lb.clear_startup_cache(profile))   # nothing left: the next start is not slow


class Popups(unittest.TestCase):
    def test_popups_jsonl_and_screenshot(self):
        import base64
        import json
        with tempfile.TemporaryDirectory() as t:
            out = pathlib.Path(t)
            shot = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8jpeg").decode()
            lb.write_popups(out, [{"provider": "claude", "class": "cookie", "action": 'clicked "Refuser"'},
                                  {"provider": "claude", "class": "unknown", "action": "provider_paused", "screenshot": shot}])
            rows = [json.loads(x) for x in (out / "popups.jsonl").read_text().splitlines()]
            self.assertEqual(rows[1]["screenshot"], "popup_claude_1.jpg")
            self.assertEqual((out / "popup_claude_1.jpg").read_bytes(), b"\xff\xd8jpeg")
            self.assertNotIn("screenshot", rows[0])

    def test_popup_event_line(self):
        with mock.patch.object(lb, "say") as say:
            lb.show_event(lb.State({}, None), {"type": "popup", "provider": "claude", "class": "terms", "action": 'clicked "Accept"', "text": "We updated our terms", "prominent": True})
        self.assertIn("POPUP terms", say.call_args[0][0])
        self.assertIn("TERMS ACCEPTED", say.call_args[0][0])


class InstallAddon(unittest.TestCase):
    def test_silent_firefox_retries_once_then_says_so(self):
        """A debugger port that accepts but never speaks (Firefox still rebuilding its caches)."""
        import socket
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(4)
        port = srv.getsockname()[1]
        calls = []
        real = lb._install_once

        def short(p, path, ct, rt):
            calls.append((ct, rt))
            return real(p, path, 2, 0.3)
        try:
            with mock.patch.object(lb, "_install_once", short), mock.patch.object(lb.time, "sleep"), mock.patch.object(lb, "say"):
                with self.assertRaises(SystemExit) as cm:
                    lb.install_addon(port, "/nowhere", slow=True)
        finally:
            srv.close()
        self.assertEqual(calls, [(180, 90), (180, 90)])
        self.assertIn("Could not install the churvey add-on", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
