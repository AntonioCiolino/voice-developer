import asyncio
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import HTTPException

import controller.discovery as discovery
from controller import config, selection
from controller.discovery import discover_providers
from controller.providers import (
    PlannerConfigurationError,
    provider_environment,
    resolve_coder_provider,
    resolve_planner_provider,
    resolve_roles,
)
from controller.routes.models import delete_model_config, get_model_config, put_model_config
from controller.routes.planner import get_planner_provider
from controller.schemas import ModelConfigRequest
from controller.state import jobs
from controller.worker import run_job

BASE_ENV = {
    "OPENAI_API_KEY": "sk-secret-key",
    "OPENAI_MODELS": "gpt-5.4-mini, gpt-5.4",
    "OPENAI_MODEL": "gpt-5.4-mini",
    "PLANNER_PROVIDER": "lmstudio",
    "LMSTUDIO_MODEL": "qwen-env",
    "CODER_PROVIDER": "ollama",
    "OLLAMA_MODEL": "coder-env:7b",
}
LMSTUDIO_TAGS = {"data": [{"id": "qwen-env"}, {"id": "qwen-b"}, {"id": "text-embedding-nomic"}]}
OLLAMA_TAGS = {"models": [{"name": "coder-env:7b"}, {"name": "glm:cloud"}]}


def fake_get(down=()):
    def get(url, **kwargs):
        assert kwargs == {"timeout": 2, "follow_redirects": False, "trust_env": False}, kwargs
        name = "lmstudio" if ":1234" in url else "ollama"
        if name in down:
            raise httpx.ConnectError("refused")
        body = LMSTUDIO_TAGS if name == "lmstudio" else OLLAMA_TAGS
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: body)
    return get


def req(**roles):
    return ModelConfigRequest(**{r: {"provider": p, "model": m} for r, (p, m) in roles.items()})


class ModelConfigCase(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.path = self.tmp / "sel.json"
        for p in (
            patch.object(selection, "SELECTION_PATH", self.path),
            patch.dict(os.environ, BASE_ENV, clear=True),
            patch.object(discovery.httpx, "get", fake_get()),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.before = dict(jobs)
        self.addCleanup(lambda: (jobs.clear(), jobs.update(self.before)))
        discovery.OLLAMA_REMOTE_MODELS.clear()
        self.addCleanup(discovery.OLLAMA_REMOTE_MODELS.clear)

    def raises(self, status, request):
        with self.assertRaises(HTTPException) as ctx:
            put_model_config(request)
        self.assertEqual(ctx.exception.status_code, status)
        self.assertFalse(self.path.exists())
        return ctx.exception.detail


class SelectionTests(ModelConfigCase):
    def test_no_file_is_identical_to_env(self):
        self.assertIs(selection.effective_env(), os.environ)
        planner, coder = resolve_roles()
        self.assertEqual((planner.name, planner.model), ("lmstudio", "qwen-env"))
        self.assertEqual((coder.name, coder.model), ("ollama", "coder-env:7b"))
        self.assertEqual(get_model_config()["roles"]["planner"]["source"], "env")

    def test_ui_selection_beats_env_and_planner_only_keeps_coder(self):
        put_model_config(req(planner=("openai", "gpt-5.4")))
        planner, coder = resolve_roles()
        self.assertEqual((planner.name, planner.model), ("openai", "gpt-5.4"))
        self.assertEqual((coder.name, coder.model), ("ollama", "coder-env:7b"))
        roles = get_model_config()["roles"]
        self.assertEqual((roles["planner"]["source"], roles["coder"]["source"]), ("ui", "env"))

    def test_planner_swap_pins_coder_provider_when_blank(self):
        env = {k: v for k, v in BASE_ENV.items() if k != "CODER_PROVIDER"}
        with patch.dict(os.environ, env, clear=True):
            selection.save_selection({"planner": {"provider": "openai", "model": "gpt-5.4"}})
            self.assertEqual(resolve_planner_provider().name, "openai")
            coder = resolve_coder_provider()
            self.assertEqual((coder.name, coder.model), ("lmstudio", "qwen-env"))

    def test_corrupt_file_errors_without_fallback(self):
        self.path.write_text("{not json")
        with self.assertRaisesRegex(PlannerConfigurationError, "corrupt"):
            resolve_roles()
        with self.assertRaises(HTTPException) as ctx:
            get_planner_provider()
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertIsNotNone(get_model_config()["config_error"])
        delete_model_config()
        self.assertEqual(resolve_roles()[0].model, "qwen-env")

    def test_persistence_across_restart_and_reset(self):
        put_model_config(req(coder=("lmstudio", "qwen-b")))
        reloaded = json.loads(self.path.read_text())
        self.assertEqual(reloaded, {"coder": {"provider": "lmstudio", "model": "qwen-b"}})
        self.assertEqual(selection.load_selection(), reloaded)
        self.assertEqual(resolve_coder_provider().model, "qwen-b")
        delete_model_config()
        self.assertFalse(self.path.exists())
        self.assertEqual(resolve_coder_provider().model, "coder-env:7b")


class DiscoveryTests(ModelConfigCase):
    def by_name(self):
        return {p["name"]: p for p in discover_providers()}

    def test_lists_models(self):
        found = self.by_name()
        self.assertEqual([m["id"] for m in found["lmstudio"]["models"]], ["qwen-env", "qwen-b"])
        self.assertEqual(
            [(m["id"], m["location"]) for m in found["ollama"]["models"]],
            [("coder-env:7b", "local"), ("glm:cloud", "cloud")],
        )
        self.assertEqual([m["id"] for m in found["openai"]["models"]], ["gpt-5.4-mini", "gpt-5.4"])

    def test_down_server_and_other_providers_still_list(self):
        with patch.object(discovery.httpx, "get", fake_get(down=("lmstudio",))):
            found = self.by_name()
        self.assertFalse(found["lmstudio"]["available"])
        self.assertEqual(found["lmstudio"]["error"], "LM Studio server is not reachable")
        self.assertEqual(found["lmstudio"]["models"], [])
        self.assertTrue(found["ollama"]["available"])

    def test_non_loopback_base_is_an_error_entry_without_url(self):
        with patch.dict(os.environ, {"OLLAMA_API_BASE": "http://cloud.example:11434"}):
            entry = self.by_name()["ollama"]
        self.assertFalse(entry["available"])
        self.assertNotIn("cloud.example", json.dumps(entry))

    def test_ollama_cloud_stub_without_suffix_is_labeled_cloud(self):
        tags = {"models": [
            {"name": "coder-env:7b", "size": 4_683_087_561},
            {"name": "qwen3-coder:480b-cloud", "size": 382, "remote_host": "https://ollama.com:443"},
            {"name": "qwen3-coder-480b-64k:latest", "size": 259},  # created FROM a cloud model
            {"name": "remote-only", "remote_host": "https://ollama.com:443"},
        ]}
        with patch.object(discovery, "_get_json", side_effect=lambda url: tags if ":11434" in url else LMSTUDIO_TAGS):
            found = {m["id"]: m["location"] for m in self.by_name()["ollama"]["models"]}
        self.assertEqual(found, {"coder-env:7b": "local", "qwen3-coder:480b-cloud": "cloud",
                                 "qwen3-coder-480b-64k:latest": "cloud", "remote-only": "cloud"})
        coder = resolve_coder_provider({**BASE_ENV, "OLLAMA_MODEL": "qwen3-coder-480b-64k:latest"})
        self.assertFalse(coder.is_local)
        self.assertEqual(coder.location, "cloud")

    def test_openai_list_only_takes_role_models_from_openai_roles(self):
        # The lmstudio PLANNER_MODEL and ollama CODER_MODEL must not appear as OpenAI models.
        with patch.dict(os.environ, {"PLANNER_MODEL": "qwen-env", "CODER_MODEL": "coder-env:7b"}):
            ids = [m["id"] for m in self.by_name()["openai"]["models"]]
        self.assertEqual(ids, ["gpt-5.4-mini", "gpt-5.4"])
        with patch.dict(os.environ, {"PLANNER_PROVIDER": "openai", "PLANNER_MODEL": "gpt-6",
                                     "CODER_PROVIDER": "lmstudio", "CODER_MODEL": "qwen-env"}):
            ids = [m["id"] for m in self.by_name()["openai"]["models"]]
        self.assertEqual(ids, ["gpt-5.4-mini", "gpt-5.4", "gpt-6"])

    def test_openai_needs_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            self.assertFalse(self.by_name()["openai"]["available"])


class PutValidationTests(ModelConfigCase):
    def test_errors_leave_selection_unchanged(self):
        self.raises(400, ModelConfigRequest())
        self.raises(400, req(planner=("bogus", "m")))
        self.raises(400, req(planner=("lmstudio", "bad model;rm")))
        self.raises(400, req(planner=("lmstudio", "not-offered")))
        with patch.object(discovery.httpx, "get", fake_get(down=("ollama",))):
            self.raises(503, req(coder=("ollama", "coder-env:7b")))
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            self.raises(400, req(planner=("openai", "gpt-5.4")))

    def test_failed_put_keeps_existing_selection(self):
        put_model_config(req(planner=("lmstudio", "qwen-b")))
        before = self.path.read_text()
        with self.assertRaises(HTTPException):
            put_model_config(req(coder=("ollama", "nope")))
        self.assertEqual(self.path.read_text(), before)


class SwapTests(ModelConfigCase):
    def test_planner_provider_endpoint_changes_without_restart(self):
        self.assertEqual(get_planner_provider()["model"], "qwen-env")
        put_model_config(req(planner=("lmstudio", "qwen-b")))
        self.assertEqual(get_planner_provider()["model"], "qwen-b")
        put_model_config(req(planner=("openai", "gpt-5.4")))
        info = get_planner_provider()
        self.assertEqual((info["name"], info["location"]), ("openai", "cloud"))

    def test_ollama_cloud_model_is_not_local_only(self):
        self.assertTrue(get_planner_provider()["roles"]["local_only"])
        payload = put_model_config(req(coder=("ollama", "glm:cloud")))
        self.assertFalse(payload["local_only"])
        coder = get_planner_provider()["roles"]["coder"]
        self.assertEqual((coder["location"], coder["name"]), ("cloud", "ollama"))
        self.assertEqual(coder["label"], "Ollama cloud model (via local server)")

    def test_credential_isolation_after_swap(self):
        put_model_config(req(coder=("lmstudio", "qwen-b")))
        env = provider_environment(resolve_coder_provider(), os.environ)
        self.assertNotIn("OPENAI_API_KEY", env)
        put_model_config(req(coder=("openai", "gpt-5.4")))
        env = provider_environment(resolve_coder_provider(), os.environ)
        self.assertEqual(env["OPENAI_API_KEY"], "sk-secret-key")
        self.assertFalse([k for k in env if k.startswith("LM_STUDIO_")])

    def test_payload_never_contains_key_or_url(self):
        put_model_config(req(planner=("openai", "gpt-5.4")))
        text = json.dumps(get_model_config())
        for secret in ("sk-secret-key", "127.0.0.1", "localhost", "http"):
            self.assertNotIn(secret, text)


class RunJobCoderTests(ModelConfigCase):
    def test_run_job_keeps_start_coder_then_next_run_uses_new_one(self):
        root = self.tmp / "repo"
        app = root / "generated-app"
        (app / "src").mkdir(parents=True)
        (app / "src" / "App.jsx").write_text("export default function App() { return null; } // padding padding padding padding padding padding padding\n")
        (app / "index.html").write_text("<html></html>")
        for name, value in (("REPO_ROOT", root), ("APP_ROOT", app), ("APP_SRC", app / "src"),
                            ("PLANS_DIR", self.tmp / "plans")):
            p = patch.object(config, name, value)
            p.start()
            self.addCleanup(p.stop)
        put_model_config(req(coder=("lmstudio", "qwen-env")))

        def new_job(job_id):
            jobs[job_id] = {
                "id": job_id, "status": "planned", "prompt": "p", "plan": "", "tasks": ["t1", "t2"],
                "current_task": -1, "task_statuses": ["pending"] * 2, "task_logs": [""] * 2,
                "task_costs": [""] * 2, "task_errors": [""] * 2, "created_at": "x", "error": None,
                "roles": {"planner": {"name": "lmstudio", "location": "local"},
                          "coder": {"name": "ollama"}, "local_only": True},
            }

        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if len(calls) == 1:  # swap the selection while the first task runs
                put_model_config(req(coder=("openai", "gpt-5.4")))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        job_a = "00000000-0000-0000-0000-0000000000a1"
        new_job(job_a)
        with patch.object(subprocess, "run", fake_run):
            asyncio.run(run_job(job_a))
        joined = [" ".join(c) for c in calls]
        self.assertTrue(all("qwen-env" in c for c in joined), joined)
        self.assertEqual(jobs[job_a]["roles"]["coder"]["name"], "lmstudio")
        self.assertTrue(jobs[job_a]["roles"]["local_only"])

        calls.clear()
        job_b = "00000000-0000-0000-0000-0000000000b2"
        new_job(job_b)
        with patch.object(subprocess, "run", fake_run):
            asyncio.run(run_job(job_b))
        self.assertIn("gpt-5.4", " ".join(calls[0]))
        self.assertEqual(jobs[job_b]["roles"]["coder"]["name"], "openai")
        self.assertFalse(jobs[job_b]["roles"]["local_only"])


if __name__ == "__main__":
    unittest.main()


class PlannerTemperatureTests(unittest.TestCase):
    """GPT-6 models reject temperature=0.7; the planner retries once without it."""

    def setUp(self):
        from controller.routes import planner as planner_routes
        self.planner = planner_routes
        planner_routes._DEFAULT_TEMPERATURE_ONLY.clear()
        self.addCleanup(planner_routes._DEFAULT_TEMPERATURE_ONLY.clear)

    def client(self, reject_temperature):
        calls = []

        class Rejected(Exception):
            param = "temperature"

        def create(**kwargs):
            calls.append(kwargs)
            if reject_temperature and "temperature" in kwargs:
                raise Rejected("Unsupported value: 'temperature' does not support 0.7 with this model.")
            return "ok"
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))), calls

    def test_models_that_accept_temperature_get_it(self):
        client, calls = self.client(reject_temperature=False)
        self.assertEqual(self.planner.create_plan_completion(client, "gpt-5.4-mini", []), "ok")
        self.assertEqual([c.get("temperature") for c in calls], [0.7])

    def test_retries_without_temperature_and_remembers_the_model(self):
        client, calls = self.client(reject_temperature=True)
        self.assertEqual(self.planner.create_plan_completion(client, "gpt-6-luna", []), "ok")
        self.assertEqual(["temperature" in c for c in calls], [True, False])
        calls.clear()
        self.planner.create_plan_completion(client, "gpt-6-luna", [])
        self.assertEqual(["temperature" in c for c in calls], [False])  # no wasted first call

    def test_other_errors_are_not_swallowed(self):
        def create(**kwargs):
            raise RuntimeError("rate limited")
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with self.assertRaisesRegex(RuntimeError, "rate limited"):
            self.planner.create_plan_completion(client, "gpt-6-luna", [])
