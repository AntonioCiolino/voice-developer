import json
import os
import pathlib
import threading

from controller.providers import PlannerConfigurationError, _provider_name

ROLES = ("planner", "coder")

# Read once at import; tests patch SELECTION_PATH directly.
SELECTION_PATH = pathlib.Path(
    os.environ.get("VOICE_DEVELOPER_SELECTION_FILE")
    or pathlib.Path(__file__).parent / "model-selection.json"
)
_lock = threading.Lock()


def _validated(data) -> dict:
    if not isinstance(data, dict):
        raise ValueError("expected an object")
    result = {}
    for role, entry in data.items():
        if role not in ROLES:
            raise ValueError(f"unknown role {role!r}")
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("provider"), str)
            or not isinstance(entry.get("model"), str)
            or not entry["provider"]
            or not entry["model"]
        ):
            raise ValueError(f"bad {role} entry")
        result[role] = {"provider": entry["provider"], "model": entry["model"]}
    return result


def load_selection() -> dict | None:
    """Saved {role: {provider, model}} or None when there is no file. A corrupt file raises."""
    with _lock:
        try:
            text = pathlib.Path(SELECTION_PATH).read_text()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise PlannerConfigurationError(
                f"Saved model selection is unreadable ({exc.__class__.__name__}); use Reset to .env"
            ) from None
    try:
        return _validated(json.loads(text)) or None
    except ValueError:
        raise PlannerConfigurationError(
            "Saved model selection is corrupt; use Reset to .env"
        ) from None


def save_selection(role_map: dict) -> None:
    """Atomically persist the selection (provider and model only, never keys or URLs)."""
    data = _validated(role_map)
    path = pathlib.Path(SELECTION_PATH)
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, path)


def clear_selection() -> None:
    with _lock:
        try:
            pathlib.Path(SELECTION_PATH).unlink()
        except FileNotFoundError:
            pass


def overlay_env(role_map: dict | None):
    """os.environ itself when there is no selection; else a copy with the selected roles overlaid."""
    if not role_map:
        return os.environ
    env = dict(os.environ)
    if "planner" in role_map and "coder" not in role_map and not env.get("CODER_PROVIDER", "").strip():
        # A planner swap must not drag the coder along: pin its provider as .env resolves it today.
        env["CODER_PROVIDER"] = _provider_name(env, "PLANNER_PROVIDER", "openai")
    for role, entry in role_map.items():
        env[f"{role.upper()}_PROVIDER"] = entry["provider"]
        env[f"{role.upper()}_MODEL"] = entry["model"]
    return env


def effective_env():
    return overlay_env(load_selection())
