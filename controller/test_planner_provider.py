import os
import unittest
from unittest.mock import patch

from controller.main import (
    PlannerConfigurationError,
    build_aider_command,
    create_planner_client,
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

    def test_ollama_wires_normalized_endpoint_and_model(self):
        environment = {
            "PLANNER_PROVIDER": "ollama",
            "OLLAMA_MODEL": "qwen2.5:7b",
            "OLLAMA_API_BASE": "http://127.0.0.1:11434/",
        }
        provider = resolve_planner_provider(environment)

        self.assertEqual(provider.planner_base_url, "http://127.0.0.1:11434/v1")
        self.assertEqual(provider.aider_model, "ollama_chat/qwen2.5:7b")
        command = build_aider_command(provider, "plan this", ["generated-app/src/App.jsx"])
        self.assertEqual(command[command.index("--model") + 1], "ollama_chat/qwen2.5:7b")
        self.assertEqual(command[command.index("--message") + 1], "plan this")

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
            "PATH": "/usr/bin",
        })

        self.assertNotIn("OPENAI_API_KEY", environment)
        self.assertNotIn("OPENAI_BASE_URL", environment)
        self.assertNotIn("OPENAI_API_BASE", environment)
        self.assertNotIn("ANTHROPIC_API_KEY", environment)
        self.assertNotIn("ANTHROPIC_BASE_URL", environment)
        self.assertEqual(environment["OLLAMA_API_BASE"], "http://127.0.0.1:11434")
        self.assertEqual(environment["PATH"], "/usr/bin")

    def test_openai_environment_keeps_selected_key(self):
        provider = resolve_planner_provider({"OPENAI_API_KEY": "test-key"})
        environment = provider_environment(provider, {"PATH": "/usr/bin"})

        self.assertEqual(environment["OPENAI_API_KEY"], "test-key")
        self.assertEqual(environment["PATH"], "/usr/bin")


if __name__ == "__main__":
    unittest.main()
