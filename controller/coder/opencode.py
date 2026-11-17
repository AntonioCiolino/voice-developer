from controller.providers import PlannerProvider


OPENCODE_NOT_IMPLEMENTED = (
    "OpenCode coder engine is not implemented yet. Set CODER_ENGINE=aider or unset it."
)


def build_opencode_command(provider: PlannerProvider, task_prompt: str) -> list[str]:
    """OpenCode integration point (stub: the command is defined but never executed).

    Future implementer notes:
    - Ollama must be registered as an OpenAI-compatible provider pointing at
      "<OLLAMA_API_BASE>/v1" in the opencode config, with a context window of 64k or more.
    - Run it with provider_environment(provider) so credentials stay isolated per role.
    - Parse the `--format json` event stream for the task log and error text.
    """
    return ["opencode", "run", "--model", f"{provider.name}/{provider.model}",
            "--format", "json", task_prompt]
