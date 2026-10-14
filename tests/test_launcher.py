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


if __name__ == "__main__":
    unittest.main()
