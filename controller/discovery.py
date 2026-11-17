import os

import httpx

from controller.providers import PlannerConfigurationError, _normalize_ollama_api_base

TIMEOUT_SECONDS = 2

_LABELS = {"lmstudio": "LM Studio", "ollama": "Ollama", "openai": "OpenAI"}


def _entry(name: str, models=None, error: str | None = None) -> dict:
    return {
        "name": name,
        "label": _LABELS[name],
        "location": "cloud" if name == "openai" else "local",
        "available": error is None,
        "error": error,
        "models": models or [],
    }


def _model(model_id: str, cloud: bool) -> dict:
    return {"id": model_id, "label": model_id, "location": "cloud" if cloud else "local"}


def _get_json(url: str):
    response = httpx.get(url, timeout=TIMEOUT_SECONDS, follow_redirects=False, trust_env=False)
    response.raise_for_status()
    return response.json()


def _discover_local(name: str, base_var: str, default_base: str, path: str) -> dict:
    label = _LABELS[name]
    try:
        base = _normalize_ollama_api_base(os.environ.get(base_var, default_base), base_var)
    except PlannerConfigurationError as exc:
        return _entry(name, error=str(exc))
    try:
        data = _get_json(f"{base}{path}")
        if name == "lmstudio":
            ids = [m["id"] for m in data["data"] if isinstance(m.get("id"), str) and "embed" not in m["id"].lower()]
            models = [_model(i, False) for i in ids]
        else:
            ids = [m["name"] for m in data["models"] if isinstance(m.get("name"), str)]
            models = [_model(i, i.lower().endswith((":cloud", "-cloud"))) for i in ids]
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        return _entry(name, error=f"{label} server is not reachable")
    return _entry(name, models=models)


def _discover_openai() -> dict:
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        return _entry("openai", error="OPENAI_API_KEY is not set")
    candidates = os.environ.get("OPENAI_MODELS", "").split(",") + [
        os.environ.get(var, "") for var in ("OPENAI_MODEL", "PLANNER_MODEL", "CODER_MODEL")
    ]
    ids = list(dict.fromkeys(c.strip() for c in candidates if c.strip()))
    return _entry("openai", models=[_model(i, True) for i in ids])


def discover_providers() -> list[dict]:
    """Fresh model lists per provider. Local servers are queried live; OpenAI comes from .env."""
    return [
        _discover_local("lmstudio", "LMSTUDIO_API_BASE", "http://127.0.0.1:1234", "/v1/models"),
        _discover_local("ollama", "OLLAMA_API_BASE", "http://127.0.0.1:11434", "/api/tags"),
        _discover_openai(),
    ]
