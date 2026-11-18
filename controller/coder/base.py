import os

from controller import config  # noqa: F401  (loads controller/.env)
from controller.providers import PlannerConfigurationError


class CoderEngineNotImplemented(RuntimeError):
    """Raised when the selected coder engine is only a stub."""


_CODER_ENGINES = ("aider", "opencode")
_EDIT_FORMATS = ("diff", "diff-fenced", "udiff", "whole")
DEFAULT_CODER_TIMEOUT_SECONDS = 120


def resolve_coder_engine(env: dict[str, str] | None = None) -> str:
    """CODER_ENGINE (.env only): 'aider' (default) or 'opencode'. Unknown values raise."""
    values = os.environ if env is None else env
    engine = values.get("CODER_ENGINE", "").strip().lower() or "aider"
    if engine not in _CODER_ENGINES:
        raise PlannerConfigurationError("CODER_ENGINE must be either 'aider' or 'opencode'")
    return engine


def resolve_coder_timeout(env: dict[str, str] | None = None) -> int:
    """CODER_TIMEOUT_SECONDS: per-task subprocess timeout, a positive integer (default 120)."""
    values = os.environ if env is None else env
    raw = values.get("CODER_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return DEFAULT_CODER_TIMEOUT_SECONDS
    try:
        seconds = int(raw)
    except ValueError:
        seconds = 0
    if seconds <= 0:
        raise PlannerConfigurationError("CODER_TIMEOUT_SECONDS must be a positive integer")
    return seconds


def resolve_max_file_lines(env: dict[str, str] | None = None) -> int:
    """MAX_FILE_LINES (.env only): the line limit per generated source file (default 150)."""
    values = os.environ if env is None else env
    raw = values.get("MAX_FILE_LINES", "").strip()
    if not raw:
        return config.DEFAULT_MAX_FILE_LINES
    try:
        lines = int(raw)
    except ValueError:
        lines = 0
    if lines <= 0:
        raise PlannerConfigurationError("MAX_FILE_LINES must be a positive integer")
    return lines


def resolve_coder_edit_format(env: dict[str, str] | None = None, provider=None) -> str:
    """CODER_EDIT_FORMAT: Aider edit format.

    When unset the default follows the coder provider: 'whole' for a local coder
    (ollama/lmstudio, where the files are kept small and a 7B model cannot reproduce
    SEARCH blocks) and 'diff' for a cloud coder. An Ollama ':cloud' model runs in the
    cloud (provider.is_local is False), so it gets 'diff'. CODER_EDIT_FORMAT, when set,
    always wins. The caller passes the coder resolved for this run, so a hot-swapped
    coder gets its own default. Without a provider the default is 'diff'.
    """
    values = os.environ if env is None else env
    default = "whole" if provider is not None and provider.is_local else "diff"
    edit_format = values.get("CODER_EDIT_FORMAT", "").strip().lower() or default
    if edit_format not in _EDIT_FORMATS:
        raise PlannerConfigurationError(
            "CODER_EDIT_FORMAT must be one of: " + ", ".join(_EDIT_FORMATS)
        )
    return edit_format
