import os
import re

from controller import config
from controller.providers import PlannerProvider


AIDER_VENV_BIN = config.REPO_ROOT / "controller" / "aider-venv" / "bin" / "aider"


def resolve_aider_bin(env: dict[str, str] | None = None) -> str:
    """AIDER_BIN (.env only) selects the Aider executable.

    Default: controller/aider-venv/bin/aider when it exists (a separate environment, so
    Aider's dependencies never change the controller's pinned packages), else `aider` on PATH.
    """
    values = os.environ if env is None else env
    configured = values.get("AIDER_BIN", "").strip()
    if configured:
        return configured
    return str(AIDER_VENV_BIN) if AIDER_VENV_BIN.exists() else "aider"


def build_aider_command(
    provider: PlannerProvider, task_prompt: str, files: list[str], edit_format: str = "diff"
) -> list[str]:
    """Build the queued Aider invocation for the selected provider."""
    # Commits are made by the controller (commit_task), so Aider never asks the
    # model to write a commit message and never commits unrelated dirty files.
    return [
        resolve_aider_bin(), "--yes-always", "--no-pretty", "--no-suggest-shell-commands",
        "--no-auto-commits", "--no-dirty-commits",
        # Local models (LM Studio, custom Ollama tags) are unknown to Aider. Its
        # warning asks to open a docs page, and --yes-always would open the browser.
        "--no-show-model-warnings",
        "--model", provider.aider_model, "--edit-format", edit_format,
        "--message", task_prompt, *files,
    ]


def extract_cost(log: str) -> str:
    m = re.search(r'Cost:\s*(\$[\d.]+)\s*message', log)
    return m.group(1) if m else ''
