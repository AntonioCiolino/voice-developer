"""The current app name: set by Save and Load, cleared by New App, kept across a restart."""
import json
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from controller import config
from controller.routes import apps
from controller.schemas import LoadAppRequest, SaveRequest


class CurrentAppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.app = self.tmp / "generated-app"
        (self.app / "src").mkdir(parents=True)
        (self.app / ".git").mkdir()  # save skips git init when history exists
        (self.app / "src" / "App.jsx").write_text("export default function App() { return null; }\n")
        self.saved = self.tmp / "saved-apps"
        self.current = self.tmp / "current-app.json"
        for p in (patch.object(config, "APP_ROOT", self.app),
                  patch.object(config, "APP_SRC", self.app / "src"),
                  patch.object(config, "SAVED_APPS", self.saved),
                  patch.object(apps, "CURRENT_APP_PATH", self.current),
                  patch.object(subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""))):
            p.start()
            self.addCleanup(p.stop)

    def status(self, fn, *args):
        with self.assertRaises(HTTPException) as ctx:
            fn(*args)
        return ctx.exception.status_code

    def test_no_name_until_saved(self):
        self.assertEqual(apps.get_current_app(), {"name": None})

    def test_save_sets_the_name_and_it_survives_a_restart(self):
        result = apps.save_app(SaveRequest(name="  Space Pong  "))
        self.assertEqual(result["name"], "space-pong")
        self.assertTrue((self.saved / "space-pong" / "src" / "App.jsx").exists())
        self.assertEqual(json.loads(self.current.read_text()), {"name": "space-pong"})
        self.assertEqual(apps.get_current_app(), {"name": "space-pong"})  # read from disk each time

    def test_load_sets_and_new_clears(self):
        apps.save_app(SaveRequest(name="first"))
        apps.save_app(SaveRequest(name="second"))
        self.assertEqual(apps.load_app(LoadAppRequest(name="first"))["name"], "first")
        self.assertEqual(apps.get_current_app(), {"name": "first"})
        self.assertIsNone(apps.new_app()["name"])
        self.assertEqual(apps.get_current_app(), {"name": None})
        self.assertFalse(self.current.exists())

    def test_saving_again_needs_overwrite(self):
        apps.save_app(SaveRequest(name="pong"))
        self.assertEqual(self.status(apps.save_app, SaveRequest(name="pong")), 409)
        self.assertEqual(apps.save_app(SaveRequest(name="pong", overwrite=True))["name"], "pong")

    def test_names_cannot_leave_saved_apps(self):
        for bad in ("../escape", "a/b", ".hidden", "..", "émoji✨"):
            self.assertEqual(self.status(apps.save_app, SaveRequest(name=bad)), 400, bad)
        self.assertFalse((self.tmp / "escape").exists())
        (self.tmp / "outside").mkdir()
        for bad in ("../outside", "..", "missing"):
            self.assertEqual(self.status(apps.load_app, LoadAppRequest(name=bad)), 404, bad)
        self.assertEqual(apps.get_current_app(), {"name": None})

    def test_bad_state_file_reads_as_no_name(self):
        for text in ("not json", '{"name": "../x"}', '{"name": 3}', "[]"):
            self.current.write_text(text)
            self.assertEqual(apps.get_current_app(), {"name": None}, text)


if __name__ == "__main__":
    unittest.main()
