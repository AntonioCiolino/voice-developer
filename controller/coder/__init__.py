from controller.coder.aider import AIDER_VENV_BIN, build_aider_command, extract_cost, resolve_aider_bin
from controller.coder.base import (
    DEFAULT_CODER_TIMEOUT_SECONDS,
    CoderEngineNotImplemented,
    resolve_coder_edit_format,
    resolve_coder_engine,
    resolve_coder_timeout,
)
from controller.coder.opencode import OPENCODE_NOT_IMPLEMENTED, build_opencode_command
from controller.providers import PlannerConfigurationError, PlannerProvider



def build_coder_command(
    engine: str, provider: PlannerProvider, task_prompt: str, files: list[str],
    edit_format: str = "diff",
) -> list[str]:
    """Dispatch to the configured coder engine. OpenCode is a stub and never falls back."""
    if engine == "aider":
        return build_aider_command(provider, task_prompt, files, edit_format)
    if engine == "opencode":
        raise CoderEngineNotImplemented(OPENCODE_NOT_IMPLEMENTED)
    raise PlannerConfigurationError("CODER_ENGINE must be either 'aider' or 'opencode'")
