import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from controller.main import (
    PlanRequest,
    PlannerConfigurationError,
    build_aider_command,
    create_planner_client,
    get_planner_provider,
    jobs,
    plan as create_plan,
    planner_provider_info,
    provider_environment,
    resolve_coder_provider,
    resolve_planner_provider,
    resolve_roles,
    role_provider_info,
    roles_info,
    PHONE_UI,
)


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

    def test_plan_response_and_queued_job_include_same_safe_provider(self):
        class FakeQueue:
            def __init__(self):
                self.items = []

            async def put(self, job_id):
                self.items.append(job_id)

            def qsize(self):
                return len(self.items)

        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="## Tasks\\n1) Keep it local"))]
        )
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=lambda **kwargs: response)
            )
        )
        queue = FakeQueue()
        existing_jobs = set(jobs)

        with (
            patch.dict(os.environ, {
                "PLANNER_PROVIDER": "ollama",
                "OLLAMA_MODEL": "qwen2.5:7b",
                "OLLAMA_API_BASE": "http://127.0.0.1:11434",
            }, clear=True),
            patch("controller.main.create_planner_client", return_value=fake_client),
            patch("controller.main._planner_user_msg", return_value="harmless prompt"),
            patch("controller.main.job_queue", queue),
        ):
            result = asyncio.run(create_plan(PlanRequest(prompt="harmless prompt")))

        try:
            self.assertEqual(result["provider"], {
                "name": "ollama",
                "label": "Ollama / local-only",
                "model": "qwen2.5:7b",
                "endpoint": "http://127.0.0.1:11434/v1",
            })
            self.assertEqual(jobs[result["job_id"]]["provider"], result["provider"])
            self.assertNotIn("OPENAI_API_KEY", str(result))
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
        self.assertEqual(build_aider_command(coder, "t", ["a"])[5], "ollama_chat/qwen2.5-coder:7b")
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
        self.assertEqual(build_aider_command(coder, "t", [])[5], "big")
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
                         "model": "gpt-5.4-mini", "endpoint": "OpenAI-managed endpoint"})
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
