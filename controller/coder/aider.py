import json
import os
import pathlib
import re

from controller import config
from controller.providers import PlannerProvider


AIDER_VENV_BIN = config.REPO_ROOT / "controller" / "aider-venv" / "bin" / "aider"
# Per-model overrides for Aider (e.g. GPT-6 models that only accept the default temperature).
AIDER_MODEL_SETTINGS = pathlib.Path(__file__).with_name("aider-model-settings.yml")
# Generated copies of those settings plus an output limit for a local model (git ignored).
GENERATED_SETTINGS_DIR = pathlib.Path(__file__).with_name(".generated")
# Output limit for local coders. Aider sends none, and LM Studio, MTPLX and Ollama then stop at
# their own default (about 2000 tokens), which silently cut whole-file edits short: App.jsx alone
# was about 3500 tokens. Reasoning models (Qwen3.5 with thinking on) also spend part of the
# budget thinking before they write, the same way gpt-6-luna emptied plans at 2000 (see
# routes/planner.py PLANNER_MAX_COMPLETION_TOKENS). Unused budget costs nothing.
LOCAL_CODER_MAX_TOKENS = 8192
_LOCAL_PROVIDERS = ("lmstudio", "ollama")


def model_settings_file(provider: PlannerProvider) -> pathlib.Path:
    """The --model-settings-file for this coder: the shared file, plus a max_tokens entry for a local model.

    Aider matches settings by exact model name, so the entry is written for the model in use
    (e.g. lm_studio/qwen3.5-4b-mtplx-optimized-speed) instead of listing every local model.
    """
    if provider.name not in _LOCAL_PROVIDERS:
        return AIDER_MODEL_SETTINGS
    name = provider.aider_model
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:120]
    GENERATED_SETTINGS_DIR.mkdir(exist_ok=True)
    path = GENERATED_SETTINGS_DIR / f"model-settings-{safe}.yml"
    entry = (f"\n# Generated for this local coder: an output limit, since Aider sends none.\n"
             f"- name: {json.dumps(name)}\n"
             f"  extra_params:\n"
             f"    max_tokens: {LOCAL_CODER_MAX_TOKENS}\n")
    text = AIDER_MODEL_SETTINGS.read_text().rstrip("\n") + "\n" + entry
    if not path.exists() or path.read_text() != text:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(text)
        os.replace(tmp, path)
    return path


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
    provider: PlannerProvider, task_prompt: str, files: list[str], edit_format: str = "diff",
    read_files: list[str] | None = None,
) -> list[str]:
    """Build the queued Aider invocation for the selected provider.

    read_files are shown to the model in full but are read-only (Aider's --read).
    """
    read_args = [arg for path in (read_files or []) for arg in ("--read", path)]
    # Commits are made by the controller (commit_task), so Aider never asks the
    # model to write a commit message and never commits unrelated dirty files.
    return [
        resolve_aider_bin(), "--yes-always", "--no-pretty", "--no-suggest-shell-commands",
        "--no-auto-commits", "--no-dirty-commits",
        # Local models (LM Studio, custom Ollama tags) are unknown to Aider. Its
        # warning asks to open a docs page, and --yes-always would open the browser.
        "--no-show-model-warnings",
        "--model-settings-file", str(model_settings_file(provider)),
        "--model", provider.aider_model, "--edit-format", edit_format,
        *read_args,
        "--message", task_prompt, *files,
    ]


def extract_cost(log: str) -> str:
    m = re.search(r'Cost:\s*(\$[\d.]+)\s*message', log)
    return m.group(1) if m else ''


def extract_cost_amount(log: str) -> float | None:
    """Sum of every `Cost: $X message` figure in the output, or None when Aider printed none."""
    amounts = re.findall(r'Cost:\s*\$(\d+(?:\.\d+)?)\s*message', log or "")
    return round(sum(float(a) for a in amounts), 6) if amounts else None
