import asyncio
import os
import pathlib
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from controller import selection
from controller.providers import (
    fresh_provider,
    PlannerConfigurationError,
    create_planner_client,
    planner_provider_info,
    provider_environment,
    resolve_coder_provider,
    resolve_planner_provider,
    resolve_roles,
    role_provider_info,
    roles_info,
)
from controller.coder import build_aider_command
from controller.routes.planner import get_planner_provider, plan as create_plan
from controller.schemas import PlanRequest
from controller.state import jobs
from controller.ui import PHONE_UI


_selection_patch = None
_selection_tmp = None


def setUpModule():
    """Keep a real controller/model-selection.json from leaking into these tests."""
    global _selection_patch, _selection_tmp
    _selection_tmp = tempfile.mkdtemp()
    _selection_patch = patch.object(
        selection, "SELECTION_PATH", pathlib.Path(_selection_tmp) / "model-selection.json"
    )
    _selection_patch.start()


def tearDownModule():
    _selection_patch.stop()
    shutil.rmtree(_selection_tmp, True)


class PlannerProviderTests(unittest.TestCase):
    def test_default_provider_is_openai_and_keeps_model_default(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            provider = resolve_planner_provider()

        self.assertEqual(provider.name, "openai")
        self.assertEqual(provider.model, "gpt-5.4-mini")
        self.assertEqual(provider.api_key, "test-key")

    def test_openai_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(PlannerConfigurationError, "OPENAI_API_KEY"):
                resolve_planner_provider()

    def test_ollama_requires_model(self):
        environment = {"PLANNER_PROVIDER": "ollama"}
        with self.assertRaisesRegex(PlannerConfigurationError, "OLLAMA_MODEL"):
            resolve_planner_provider(environment)

    def test_ollama_rejects_invalid_base(self):
        environment = {
            "PLANNER_PROVIDER": "ollama",
            "OLLAMA_MODEL": "qwen2.5:7b",
            "OLLAMA_API_BASE": "not-a-url",
        }
        with self.assertRaisesRegex(PlannerConfigurationError, "OLLAMA_API_BASE"):
            resolve_planner_provider(environment)

    def test_ollama_rejects_non_local_base(self):
        environment = {
            "PLANNER_PROVIDER": "ollama",
            "OLLAMA_MODEL": "qwen2.5:7b",
            "OLLAMA_API_BASE": "https://api.example.com",
        }
        with self.assertRaisesRegex(PlannerConfigurationError, "localhost"):
            resolve_planner_provider(environment)

    def test_ollama_accepts_loopback_forms_and_normalizes_v1(self):
        cases = {
            "http://localhost:11434/v1/": "http://localhost:11434/v1",
            "http://127.0.0.1:11434/": "http://127.0.0.1:11434/v1",
            "http://[::1]:11434/v1": "http://[::1]:11434/v1",
        }
        for api_base, expected_endpoint in cases.items():
            with self.subTest(api_base=api_base):
                provider = resolve_planner_provider({
                    "PLANNER_PROVIDER": "ollama",
                    "OLLAMA_MODEL": "qwen2.5:7b",
                    "OLLAMA_API_BASE": api_base,
                })
                self.assertEqual(provider.planner_base_url, expected_endpoint)

    def test_ollama_rejects_url_credentials(self):
        environment = {
            "PLANNER_PROVIDER": "ollama",
            "OLLAMA_MODEL": "qwen2.5:7b",
            "OLLAMA_API_BASE": "http://secret@127.0.0.1:11434",
        }
        with self.assertRaisesRegex(PlannerConfigurationError, "credentials"):
            resolve_planner_provider(environment)

    def test_ollama_provider_reporting_is_safe(self):
        provider = resolve_planner_provider({
            "PLANNER_PROVIDER": "ollama",
            "OLLAMA_MODEL": "qwen2.5:7b",
            "OLLAMA_API_BASE": "http://127.0.0.1:11434/",
        })
        self.assertEqual(planner_provider_info(provider), {
            "name": "ollama",
            "label": "Ollama / local-only",
            "model": "qwen2.5:7b",
            "endpoint": "http://127.0.0.1:11434/v1",
            "location": "local",
        })
        self.assertNotIn("secret", str(planner_provider_info(provider)).lower())

        command = build_aider_command(provider, "plan this", ["generated-app/src/App.jsx"])
        self.assertEqual(command[command.index("--model") + 1], "ollama_chat/qwen2.5:7b")
        self.assertEqual(command[command.index("--message") + 1], "plan this")

    def test_openai_provider_reporting_is_separate_and_safe(self):
        provider = resolve_planner_provider({
            "PLANNER_PROVIDER": "openai",
            "OPENAI_API_KEY": "test-secret",
            "OPENAI_MODEL": "gpt-test",
        })

        self.assertEqual(planner_provider_info(provider), {
            "name": "openai",
            "label": "OpenAI",
            "model": "gpt-test",
            "endpoint": "OpenAI-managed endpoint",
            "location": "cloud",
        })
        self.assertNotIn("test-secret", str(planner_provider_info(provider)))

    def test_ollama_client_uses_compatible_local_endpoint(self):
        environment = {
            "PLANNER_PROVIDER": "ollama",
            "OLLAMA_MODEL": "qwen2.5:7b",
        }
        provider = resolve_planner_provider(environment)
        with patch("openai.OpenAI") as openai_client:
            create_planner_client(provider)

        openai_client.assert_called_once_with(
            api_key="ollama",
            base_url="http://127.0.0.1:11434/v1",
        )

    def test_ollama_environment_removes_cloud_credentials_and_sets_base(self):
        provider = resolve_planner_provider({
            "PLANNER_PROVIDER": "ollama",
            "OLLAMA_MODEL": "qwen2.5:7b",
        })
        cloud_environment = {
            "OPENAI_API_KEY": "test-openai-key",
            "OPENAI_BASE_URL": "https://cloud.example",
            "OPENAI_API_BASE": "https://cloud.example/v1",
            "AZURE_OPENAI_API_KEY": "test-azure-key",
            "AZURE_OPENAI_ENDPOINT": "https://cloud.example/azure",
            "ANTHROPIC_API_KEY": "test-anthropic-key",
            "ANTHROPIC_BASE_URL": "https://cloud.example/anthropic",
            "GOOGLE_API_KEY": "test-google-key",
            "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/google-credentials.json",
            "GEMINI_API_KEY": "test-gemini-key",
            "OPENROUTER_API_KEY": "test-openrouter-key",
            "DEEPSEEK_API_KEY": "test-deepseek-key",
            "MISTRAL_API_KEY": "test-mistral-key",
            "COHERE_API_KEY": "test-cohere-key",
            "GROQ_API_KEY": "test-groq-key",
            "TOGETHER_API_KEY": "test-together-key",
            "XAI_API_KEY": "test-xai-key",
            "AWS_ACCESS_KEY_ID": "test-access-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret-key",
            "AWS_SESSION_TOKEN": "test-session-token",
            "AWS_PROFILE": "test-profile",
            "AWS_BEARER_TOKEN_BEDROCK": "test-bedrock-token",
            "BEDROCK_API_KEY": "test-bedrock-key",
            "AIDER_API_KEY": "test-aider-key",
            "AIDER_API_BASE": "https://cloud.example/aider",
            "PATH": "/usr/bin",
            "HOME": "/tmp",
        }
        environment = provider_environment(provider, cloud_environment)

        for variable in set(cloud_environment) - {"PATH", "HOME"}:
            with self.subTest(variable=variable):
                self.assertNotIn(variable, environment)

        self.assertEqual(environment["OLLAMA_API_BASE"], "http://127.0.0.1:11434")
        self.assertEqual(environment["PATH"], "/usr/bin")
        self.assertEqual(environment["HOME"], "/tmp")

    def test_openai_environment_keeps_selected_key(self):
        provider = resolve_planner_provider({"OPENAI_API_KEY": "test-key"})
        environment = provider_environment(provider, {"PATH": "/usr/bin"})

        self.assertEqual(environment["OPENAI_API_KEY"], "test-key")
        self.assertEqual(environment["PATH"], "/usr/bin")

    def test_provider_route_reports_safe_active_provider(self):
        with patch.dict(os.environ, {
            "PLANNER_PROVIDER": "ollama",
            "OLLAMA_MODEL": "qwen2.5:7b",
            "OLLAMA_API_BASE": "http://127.0.0.1:11434",
        }, clear=True):
            result = get_planner_provider()
            self.assertEqual({k: v for k, v in result.items() if k != "roles"}, {
                "name": "ollama",
                "label": "Ollama / local-only",
                "model": "qwen2.5:7b",
                "endpoint": "http://127.0.0.1:11434/v1",
                "location": "local",
            })
            self.assertTrue(result["roles"]["local_only"])

    def test_provider_route_error_does_not_echo_rejected_endpoint(self):
        with patch.dict(os.environ, {
            "PLANNER_PROVIDER": "ollama",
            "OLLAMA_MODEL": "qwen2.5:7b",
            "OLLAMA_API_BASE": "https://cloud.example/v1",
        }, clear=True):
            with self.assertRaises(HTTPException) as raised:
                get_planner_provider()

        self.assertNotIn("cloud.example", str(raised.exception))
        self.assertIn("localhost", str(raised.exception))

    def test_plan_response_and_planned_job_include_same_safe_provider(self):
        class FakeQueue:
            def __init__(self):
                self.items = []

            async def put(self, job_id):
                self.items.append(job_id)

            def qsize(self):
                return len(self.items)

        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="## Tasks\n1) Keep it local"))]
        )
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=lambda **kwargs: response)
            )
        )
        queue = FakeQueue()
        existing_jobs = set(jobs)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)

        with (
            patch.dict(os.environ, {
                "PLANNER_PROVIDER": "ollama",
                "OLLAMA_MODEL": "qwen2.5:7b",
                "OLLAMA_API_BASE": "http://127.0.0.1:11434",
            }, clear=True),
            patch("controller.routes.planner.create_planner_client", return_value=fake_client),
            patch("controller.routes.planner.planner_user_msg", return_value="harmless prompt"),
            patch("controller.state.job_queue", queue),
            patch("controller.config.PLANS_DIR", pathlib.Path(tmp.name)),
        ):
            result = asyncio.run(create_plan(PlanRequest(prompt="harmless prompt")))

        try:
            self.assertEqual(result["provider"], {
                "name": "ollama",
                "label": "Ollama / local-only",
                "model": "qwen2.5:7b",
                "endpoint": "http://127.0.0.1:11434/v1",
                "location": "local",
            })
            self.assertEqual(jobs[result["job_id"]]["provider"], result["provider"])
            self.assertNotIn("OPENAI_API_KEY", str(result))
            self.assertEqual(result["status"], "planned")
            self.assertEqual(result["tasks"], ["Keep it local"])
            self.assertEqual(queue.items, [])
        finally:
            for job_id in set(jobs) - existing_jobs:
                jobs.pop(job_id, None)


BASE = "http://127.0.0.1:11434"
SECRETS = {
    "OPENAI_API_KEY": "test-secret",
    "ANTHROPIC_API_KEY": "anthropic-secret",
    "SESSION_SECRET": "session-secret",
    "GOOGLE_CLIENT_SECRET": "google-secret",
    "PATH": "/usr/bin",
    "HOME": "/tmp",
}
ALL_LOCAL = {"PLANNER_PROVIDER": "ollama", "PLANNER_MODEL": "qwen3:8b",
             "CODER_PROVIDER": "ollama", "CODER_MODEL": "qwen2.5-coder:7b", "OLLAMA_API_BASE": BASE}
CLOUD_LOCAL = {"OPENAI_API_KEY": "test-secret", "PLANNER_MODEL": "gpt-5.4-mini",
               "CODER_PROVIDER": "ollama", "CODER_MODEL": "qwen2.5-coder:7b", "OLLAMA_API_BASE": BASE}
class RoleConfigTests(unittest.TestCase):
    def test_legacy_openai_coder_equals_planner(self):
        planner, coder = resolve_roles({"OPENAI_API_KEY": "k", "OPENAI_MODEL": "m1"})
        self.assertEqual(planner, coder)
        self.assertEqual((coder.name, coder.model, coder.api_key), ("openai", "m1", "k"))
    def test_legacy_ollama_coder_equals_planner(self):
        env = {"PLANNER_PROVIDER": "ollama", "OLLAMA_MODEL": "qwen2.5:7b"}
        planner, coder = resolve_roles(env)
        self.assertEqual(planner, coder)
        self.assertEqual(coder.ollama_api_base, BASE)
    def test_empty_new_values_count_as_unset(self):
        env = {"OPENAI_API_KEY": "k", "PLANNER_MODEL": "", "CODER_PROVIDER": "", "CODER_MODEL": ""}
        planner, coder = resolve_roles(env)
        self.assertEqual(planner, coder)
    def test_model_overrides_and_defaults(self):
        env = {"OPENAI_API_KEY": "k", "OPENAI_MODEL": "base", "CODER_MODEL": "big"}
        planner, coder = resolve_roles(env)
        self.assertEqual((planner.model, coder.model), ("base", "big"))
        env = {"PLANNER_PROVIDER": "ollama", "OLLAMA_MODEL": "a", "PLANNER_MODEL": "b"}
        planner, coder = resolve_roles(env)
        self.assertEqual((planner.model, coder.model), ("b", "a"))
    def test_combinations(self):
        planner, coder = resolve_roles(ALL_LOCAL)
        self.assertEqual((planner.name, planner.model, coder.name, coder.model),
                         ("ollama", "qwen3:8b", "ollama", "qwen2.5-coder:7b"))
        planner, coder = resolve_roles(CLOUD_LOCAL)
        self.assertEqual((planner.name, coder.name), ("openai", "ollama"))
        planner, coder = resolve_roles({"PLANNER_PROVIDER": "ollama", "PLANNER_MODEL": "q",
                                        "CODER_PROVIDER": "openai", "OPENAI_API_KEY": "k"})
        self.assertEqual((planner.name, coder.name, coder.model), ("ollama", "openai", "gpt-5.4-mini"))
        planner, coder = resolve_roles({"OPENAI_API_KEY": "k", "CODER_PROVIDER": "openai",
                                        "PLANNER_MODEL": "small", "CODER_MODEL": "large"})
        self.assertEqual((planner.model, coder.model), ("small", "large"))
    def test_errors_never_fall_back(self):
        with self.assertRaisesRegex(PlannerConfigurationError, "CODER_PROVIDER must be"):
            resolve_coder_provider({"OPENAI_API_KEY": "k", "CODER_PROVIDER": "bogus"})
        with self.assertRaisesRegex(PlannerConfigurationError, "CODER_MODEL.*CODER_PROVIDER=ollama"):
            resolve_coder_provider({"OPENAI_API_KEY": "k", "CODER_PROVIDER": "ollama"})
        with self.assertRaisesRegex(PlannerConfigurationError, "OPENAI_API_KEY is required when CODER_PROVIDER=openai"):
            resolve_roles({"PLANNER_PROVIDER": "ollama", "OLLAMA_MODEL": "m", "CODER_PROVIDER": "openai"})
        with self.assertRaises(PlannerConfigurationError) as raised:
            resolve_roles({**CLOUD_LOCAL, "OLLAMA_API_BASE": "https://cloud.example"})
        self.assertIn("CODER_PROVIDER=ollama", str(raised.exception))
        self.assertNotIn("cloud.example", str(raised.exception))
    def test_cloud_planner_local_coder_environment_isolation(self):
        planner, coder = resolve_roles(CLOUD_LOCAL)
        environment = provider_environment(coder, {**SECRETS, "OLLAMA_API_BASE": "ignored"})
        for variable in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "SESSION_SECRET", "GOOGLE_CLIENT_SECRET"):
            self.assertNotIn(variable, environment)
        self.assertEqual(environment["OLLAMA_API_BASE"], BASE)
        self.assertNotIn("test-secret", str(environment))
        cmd = build_aider_command(coder, "t", ["a"])
        self.assertEqual(cmd[cmd.index("--model") + 1], "ollama_chat/qwen2.5-coder:7b")
        self.assertEqual(planner.api_key, "test-secret")
    def test_openai_coder_environment_has_only_its_own_credential(self):
        _, coder = resolve_roles({"PLANNER_PROVIDER": "ollama", "OLLAMA_MODEL": "m",
                                  "CODER_PROVIDER": "openai", "OPENAI_API_KEY": "test-secret",
                                  "CODER_MODEL": "big"})
        environment = provider_environment(coder, {**SECRETS, "HTTPS_PROXY": "http://proxy"})
        self.assertEqual(environment["OPENAI_API_KEY"], "test-secret")
        self.assertEqual(environment["HTTPS_PROXY"], "http://proxy")
        for variable in ("ANTHROPIC_API_KEY", "SESSION_SECRET", "GOOGLE_CLIENT_SECRET"):
            self.assertNotIn(variable, environment)
        cmd = build_aider_command(coder, "t", [])
        self.assertEqual(cmd[cmd.index("--model") + 1], "big")
    def test_ollama_planner_client_uses_placeholder_key(self):
        planner, _ = resolve_roles({**ALL_LOCAL, "OPENAI_API_KEY": "test-secret"})
        with patch("openai.OpenAI") as client:
            create_planner_client(planner)
        client.assert_called_once_with(api_key="ollama", base_url=BASE + "/v1")
    def test_roles_info_and_local_only(self):
        cases = {"all_local": (ALL_LOCAL, True), "cloud_local": (CLOUD_LOCAL, False),
                 "all_cloud": ({"OPENAI_API_KEY": "test-secret"}, False)}
        for name, (env, local_only) in cases.items():
            with self.subTest(name):
                info = roles_info(*resolve_roles(env))
                self.assertEqual(info["local_only"], local_only)
                self.assertNotIn("test-secret", str(info))
        info = roles_info(*resolve_roles(CLOUD_LOCAL))
        self.assertEqual(info["planner"], {"role": "planner", "name": "openai", "label": "OpenAI (cloud)",
                         "model": "gpt-5.4-mini", "endpoint": "OpenAI-managed endpoint",
                         "location": "cloud"})
        self.assertEqual(info["coder"]["label"], "Ollama (local)")
        self.assertEqual(info["coder"]["endpoint"], BASE + "/v1")
    def test_route_reports_roles_and_keeps_provider_fields(self):
        with patch.dict(os.environ, CLOUD_LOCAL, clear=True):
            result = get_planner_provider()
        self.assertEqual(result["name"], "openai")
        self.assertFalse(result["roles"]["local_only"])
        self.assertNotIn("test-secret", str(result))
    def test_route_rejects_bad_coder_config_without_echo(self):
        with patch.dict(os.environ, {**CLOUD_LOCAL, "OLLAMA_API_BASE": "https://cloud.example"}, clear=True):
            with self.assertRaises(HTTPException) as raised:
                get_planner_provider()
        self.assertEqual(raised.exception.status_code, 500)
        self.assertNotIn("cloud.example", str(raised.exception))
    def test_ui_renders_roles_and_local_only_prefix(self):
        self.assertIn("roles.local_only", PHONE_UI)
        self.assertIn("Coder:", PHONE_UI)
        self.assertNotIn("OPENAI_API_KEY", PHONE_UI)

if __name__ == "__main__":
    unittest.main()


LMSTUDIO_ENV = {"PLANNER_PROVIDER": "lmstudio", "LMSTUDIO_MODEL": "qwen2.5-coder-7b-instruct"}


class LmStudioProviderTests(unittest.TestCase):
    def test_defaults_to_loopback_port_1234(self):
        provider = resolve_planner_provider(LMSTUDIO_ENV)
        self.assertEqual(provider.name, "lmstudio")
        self.assertEqual(provider.model, "qwen2.5-coder-7b-instruct")
        self.assertEqual(provider.planner_base_url, "http://127.0.0.1:1234/v1")
        self.assertTrue(provider.is_local)

    def test_api_base_is_normalized_and_must_be_loopback(self):
        provider = resolve_planner_provider({**LMSTUDIO_ENV, "LMSTUDIO_API_BASE": "http://localhost:4321/v1/"})
        self.assertEqual(provider.planner_base_url, "http://localhost:4321/v1")
        for bad in ("http://192.168.1.5:1234", "https://lmstudio.example.com", "http://u:p@127.0.0.1:1234"):
            with self.assertRaises(PlannerConfigurationError) as ctx:
                resolve_planner_provider({**LMSTUDIO_ENV, "LMSTUDIO_API_BASE": bad})
            self.assertIn("LMSTUDIO_API_BASE", str(ctx.exception))

    def test_model_is_required_and_role_model_wins(self):
        with self.assertRaises(PlannerConfigurationError) as ctx:
            resolve_planner_provider({"PLANNER_PROVIDER": "lmstudio"})
        self.assertIn("LMSTUDIO_MODEL", str(ctx.exception))
        provider = resolve_planner_provider({**LMSTUDIO_ENV, "PLANNER_MODEL": "phi-4-mini"})
        self.assertEqual(provider.model, "phi-4-mini")

    def test_unknown_provider_lists_all_three(self):
        with self.assertRaises(PlannerConfigurationError) as ctx:
            resolve_planner_provider({"PLANNER_PROVIDER": "lmstuido"})
        for name in ("openai", "ollama", "lmstudio"):
            self.assertIn(name, str(ctx.exception))

    def test_aider_command_and_environment(self):
        coder = resolve_coder_provider({"PLANNER_PROVIDER": "openai", "OPENAI_API_KEY": "secret",
                                        "CODER_PROVIDER": "lmstudio", "CODER_MODEL": "qwen2.5-coder-7b-instruct"})
        cmd = build_aider_command(coder, "t", ["a"])
        self.assertEqual(cmd[cmd.index("--model") + 1], "lm_studio/qwen2.5-coder-7b-instruct")
        env = provider_environment(coder, {"PATH": "/bin", "OPENAI_API_KEY": "secret",
                                           "ANTHROPIC_API_KEY": "secret", "OLLAMA_API_BASE": "x"})
        self.assertEqual(env["LM_STUDIO_API_BASE"], "http://127.0.0.1:1234/v1")
        self.assertEqual(env["LM_STUDIO_API_KEY"], "lm-studio")
        self.assertEqual(env["PATH"], "/bin")
        self.assertNotIn("secret", " ".join(env.values()))
        self.assertNotIn("OLLAMA_API_BASE", env)

    def test_planner_client_uses_local_server(self):
        client = create_planner_client(resolve_planner_provider(LMSTUDIO_ENV))
        self.assertEqual(str(client.base_url).rstrip("/"), "http://127.0.0.1:1234/v1")

    def test_reporting_and_local_only(self):
        lm = resolve_planner_provider(LMSTUDIO_ENV)
        self.assertEqual(planner_provider_info(lm)["label"], "LM Studio / local-only")
        self.assertEqual(role_provider_info("coder", lm)["label"], "LM Studio (local)")
        ollama = resolve_planner_provider({"PLANNER_PROVIDER": "ollama", "OLLAMA_MODEL": "qwen2.5:7b"})
        cloud = resolve_planner_provider({"OPENAI_API_KEY": "k"})
        self.assertTrue(roles_info(lm, lm)["local_only"])
        self.assertTrue(roles_info(ollama, lm)["local_only"])
        self.assertFalse(roles_info(cloud, lm)["local_only"])
class ModelServerProviderTests(unittest.TestCase):
    SERVERS = {
        "ALLOW_LAN_MODEL_SERVERS": "on", "MODEL_SERVERS": "mini,here",
        "MODEL_SERVER_MINI_KIND": "lmstudio", "MODEL_SERVER_MINI_URL": "http://192.168.1.20:1234",
        "MODEL_SERVER_HERE_KIND": "ollama", "MODEL_SERVER_HERE_URL": "http://127.0.0.1:11435",
        "OPENAI_API_KEY": "sk-secret",
    }

    def values(self, **extra):
        return {**self.SERVERS, "PLANNER_PROVIDER": "mini", "PLANNER_MODEL": "qwen3-4b",
                "CODER_PROVIDER": "mini", "CODER_MODEL": "qwen3-4b", **extra}

    def test_server_role_resolves(self):
        provider = resolve_coder_provider(self.values())
        self.assertEqual((provider.name, provider.server, provider.lan, provider.location),
                         ("lmstudio", "mini", True, "lan"))
        self.assertTrue(provider.is_local)
        self.assertEqual(provider.aider_model, "lm_studio/qwen3-4b")
        self.assertEqual(provider.planner_base_url, "http://192.168.1.20:1234/v1")

    def test_server_environment_is_isolated(self):
        provider = resolve_coder_provider(self.values())
        environment = provider_environment(provider, {**self.SERVERS, "PATH": "/bin", "OPENAI_API_KEY": "sk-secret"})
        self.assertEqual(environment["LM_STUDIO_API_BASE"], "http://192.168.1.20:1234/v1")
        self.assertEqual(environment["LM_STUDIO_API_KEY"], "lm-studio")
        self.assertEqual(environment["PATH"], "/bin")
        self.assertFalse([k for k in environment if k.startswith("OPENAI") or k.startswith("MODEL_SERVER")])

    def test_ollama_kind_loopback_server(self):
        provider = resolve_coder_provider(self.values(CODER_PROVIDER="here", CODER_MODEL="qwen2.5:7b",
                                                      ALLOW_LAN_MODEL_SERVERS="off"))
        self.assertEqual((provider.name, provider.location, provider.aider_model),
                         ("ollama", "local", "ollama_chat/qwen2.5:7b"))
        self.assertEqual(provider_environment(provider, {})["OLLAMA_API_BASE"], "http://127.0.0.1:11435")

    def test_labels_and_no_url(self):
        planner, coder = resolve_roles(self.values(CODER_PROVIDER="here", CODER_MODEL="m"))
        info = roles_info(planner, coder)
        self.assertEqual(info["planner"]["label"], "LM Studio on mini (local network)")
        self.assertEqual(info["coder"]["label"], "Ollama on here (local)")
        self.assertEqual((info["planner"]["name"], info["planner"]["endpoint"], info["planner"]["location_label"]),
                         ("mini", "mini", "Local network"))
        self.assertEqual((info["planner"]["kind"], info["planner"]["server"]), ("lmstudio", "mini"))
        self.assertFalse(info["local_only"])
        self.assertTrue(info["uses_lan"])
        self.assertNotIn("192.168", repr(info) + repr(planner_provider_info(planner)))

    def test_loopback_servers_are_local_only(self):
        here = resolve_roles(self.values(PLANNER_PROVIDER="here", CODER_PROVIDER="here", CODER_MODEL="m",
                                         PLANNER_MODEL="m"))
        info = roles_info(*here)
        self.assertTrue(info["local_only"])
        self.assertFalse(info["uses_lan"])

    def test_model_required(self):
        with self.assertRaises(PlannerConfigurationError) as raised:
            resolve_coder_provider(self.values(CODER_MODEL=""))
        self.assertIn("CODER_MODEL", str(raised.exception))

    def test_removed_server_raises_without_fallback(self):
        with self.assertRaises(PlannerConfigurationError) as raised:
            resolve_coder_provider(self.values(MODEL_SERVERS="here"))
        self.assertIn("'mini' is not a configured model server", str(raised.exception))
        with self.assertRaises(PlannerConfigurationError) as raised:
            resolve_coder_provider(self.values(ALLOW_LAN_MODEL_SERVERS="off"))
        self.assertIn("ALLOW_LAN_MODEL_SERVERS", str(raised.exception))

    def test_unchanged_message_without_servers(self):
        with self.assertRaises(PlannerConfigurationError) as raised:
            resolve_planner_provider({"PLANNER_PROVIDER": "mini", "PLANNER_MODEL": "m"})
        self.assertIn("must be one of 'openai', 'ollama', or 'lmstudio'", str(raised.exception))

    def test_fresh_provider_re_resolves(self):
        values = self.values(MODEL_SERVER_MINI_URL="http://r2m2-mini.local:1234")
        answer = lambda ip: (lambda host, port, family=0: [(family, 1, 6, "", (ip, port or 0))])
        with patch("controller.model_servers.socket.getaddrinfo", answer("192.168.1.9")):
            provider = resolve_coder_provider(values)
        self.assertEqual(provider.lmstudio_api_base, "http://192.168.1.9:1234")
        with patch.dict(os.environ, values), patch("controller.model_servers.socket.getaddrinfo", answer("192.168.1.10")):
            self.assertEqual(fresh_provider(provider).lmstudio_api_base, "http://192.168.1.10:1234")
        with patch.dict(os.environ, values), patch("controller.model_servers.socket.getaddrinfo", answer("8.8.8.8")):
            with self.assertRaises(PlannerConfigurationError):
                fresh_provider(provider)
        plain = resolve_planner_provider({"PLANNER_PROVIDER": "lmstudio", "PLANNER_MODEL": "m"})
        self.assertIs(fresh_provider(plain), plain)

    def test_server_ollama_remote_model_is_cloud(self):
        from controller.providers import SERVER_REMOTE_MODELS
        provider = resolve_coder_provider(self.values(CODER_PROVIDER="here", CODER_MODEL="stub"))
        SERVER_REMOTE_MODELS.add(("here", "stub"))
        try:
            self.assertEqual(provider.location, "cloud")
        finally:
            SERVER_REMOTE_MODELS.discard(("here", "stub"))
        cloud = resolve_coder_provider(self.values(CODER_PROVIDER="here", CODER_MODEL="gpt-oss:120b-cloud"))
        self.assertEqual(cloud.location, "cloud")
