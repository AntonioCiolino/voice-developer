import os
import unittest
from unittest.mock import patch

from controller.main import (
    PlannerConfigurationError,
    build_aider_command,
    create_planner_client,
    planner_provider_info,
    provider_environment,
    resolve_planner_provider,
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
        environment = provider_environment(provider, {
            "OPENAI_API_KEY": "test-openai-key",
            "OPENAI_BASE_URL": "https://cloud.example",
            "OPENAI_API_BASE": "https://cloud.example/v1",
            "ANTHROPIC_API_KEY": "test-anthropic-key",
            "ANTHROPIC_BASE_URL": "https://cloud.example/anthropic",
            "AZURE_OPENAI_API_KEY": "test-azure-key",
            "AZURE_OPENAI_ENDPOINT": "https://cloud.example/azure",
            "GOOGLE_API_KEY": "test-google-key",
            "GOOGLE_BASE_URL": "https://cloud.example/google",
            "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/google-credentials.json",
            "GEMINI_API_KEY": "test-gemini-key",
            "GEMINI_API_BASE": "https://cloud.example/gemini",
            "PATH": "/usr/bin",
        })

        for variable in (
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_API_BASE",
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_BASE_URL",
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "GOOGLE_API_KEY",
            "GOOGLE_BASE_URL",
            "GOOGLE_APPLICATION_CREDENTIALS",
            "GEMINI_API_KEY",
            "GEMINI_API_BASE",
        ):
            with self.subTest(variable=variable):
                self.assertNotIn(variable, environment)

        self.assertEqual(environment["OLLAMA_API_BASE"], "http://127.0.0.1:11434")
        self.assertEqual(environment["PATH"], "/usr/bin")

    def test_openai_environment_keeps_selected_key(self):
        provider = resolve_planner_provider({"OPENAI_API_KEY": "test-key"})
        environment = provider_environment(provider, {"PATH": "/usr/bin"})

        self.assertEqual(environment["OPENAI_API_KEY"], "test-key")
        self.assertEqual(environment["PATH"], "/usr/bin")


if __name__ == "__main__":
    unittest.main()
