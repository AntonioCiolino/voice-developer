import os

import httpx

from controller.providers import (
    OLLAMA_REMOTE_MODELS,
    SERVER_REMOTE_MODELS,
    PlannerConfigurationError,
    _normalize_ollama_api_base,
)

TIMEOUT_SECONDS = 2
# Real model weights are at least tens of megabytes; cloud stubs are under 1 KB.
LOCAL_WEIGHTS_MIN_BYTES = 1_000_000

_LABELS = {"lmstudio": "LM Studio", "ollama": "Ollama", "openai": "OpenAI"}


def _entry(name: str, models=None, error: str | None = None, kind: str | None = None,
           label: str | None = None, location: str | None = None) -> dict:
    return {
        "name": name,
        "kind": kind or name,
        "label": label or _LABELS[name],
        "location": location or ("cloud" if name == "openai" else "local"),
        "available": error is None,
        "error": error,
        "models": models or [],
    }


def _model(model_id: str, cloud: bool, where: str = "local") -> dict:
    return {"id": model_id, "label": model_id, "location": "cloud" if cloud else where}


def _ollama_runs_remotely(entry: dict) -> bool:
    """True when an Ollama tag runs in Ollama's cloud rather than on this machine.

    Ollama marks pulled cloud models with remote_host, but a model created FROM one
    (for example to change num_ctx) loses that marker and the :cloud suffix. Its
    manifest is still only a few hundred bytes, since no weights are stored locally.
    """
    name = entry["name"].lower()
    if name.endswith((":cloud", "-cloud")) or entry.get("remote_host"):
        return True
    size = entry.get("size")
    return isinstance(size, int) and size < LOCAL_WEIGHTS_MIN_BYTES


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
            entries = [m for m in data["models"] if isinstance(m.get("name"), str)]
            models = [_model(m["name"], _ollama_runs_remotely(m)) for m in entries]
            OLLAMA_REMOTE_MODELS.clear()
            OLLAMA_REMOTE_MODELS.update(m["id"] for m in models if m["location"] == "cloud")
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        return _entry(name, error=f"{label} server is not reachable")
    return _entry(name, models=models)


def _discover_openai() -> dict:
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        return _entry("openai", error="OPENAI_API_KEY is not set")
    candidates = os.environ.get("OPENAI_MODELS", "").split(",") + [
        os.environ.get("OPENAI_MODEL", "").strip() or "gpt-5.4-mini",
    ]
    # A role's model only belongs in the OpenAI list when .env runs that role on OpenAI;
    # otherwise e.g. an LM Studio CODER_MODEL would be offered as an OpenAI model.
    planner_provider = os.environ.get("PLANNER_PROVIDER", "").strip().lower() or "openai"
    coder_provider = os.environ.get("CODER_PROVIDER", "").strip().lower() or planner_provider
    if planner_provider == "openai":
        candidates.append(os.environ.get("PLANNER_MODEL", ""))
    if coder_provider == "openai":
        candidates.append(os.environ.get("CODER_MODEL", ""))
    ids = list(dict.fromkeys(c.strip() for c in candidates if c.strip()))
    return _entry("openai", models=[_model(i, True) for i in ids])


_MODELS_PATHS = {"lmstudio": "/v1/models", "ollama": "/api/tags"}


def _discover_server(name: str) -> dict:
    """One configured model server, queried live. Errors are short and never carry the URL."""
    from controller.model_servers import resolve_server  # lazy: model_servers imports providers
    try:
        server = resolve_server(os.environ, name)
    except PlannerConfigurationError as exc:
        return _entry(name, error=str(exc), kind="lmstudio", label=name)
    label = f"{_LABELS[server.kind]} on {name}"
    where = "lan" if server.lan else "local"
    try:
        data = _get_json(f"{server.base}{_MODELS_PATHS[server.kind]}")
        if server.kind == "lmstudio":
            ids = [m["id"] for m in data["data"] if isinstance(m.get("id"), str) and "embed" not in m["id"].lower()]
            models = [_model(i, False, where) for i in ids]
        else:
            entries = [m for m in data["models"] if isinstance(m.get("name"), str)]
            models = [_model(m["name"], _ollama_runs_remotely(m), where) for m in entries]
            SERVER_REMOTE_MODELS.difference_update({k for k in SERVER_REMOTE_MODELS if k[0] == name})
            SERVER_REMOTE_MODELS.update((name, m["id"]) for m in models if m["location"] == "cloud")
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        return _entry(name, error=f"{name} is not reachable", kind=server.kind, label=label, location=where)
    return _entry(name, models=models, kind=server.kind, label=label, location=where)


def probe_server(provider) -> bool:
    """One short GET of the server's models list. True when it answers; never raises, never reports the URL."""
    base = provider.lmstudio_api_base if provider.name == "lmstudio" else provider.ollama_api_base
    try:
        _get_json(f"{base}{_MODELS_PATHS[provider.name]}")
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        return False
    return True


def _discover_servers() -> list[dict]:
    from controller.model_servers import server_names
    try:
        names = server_names(os.environ)
    except PlannerConfigurationError as exc:
        return [_entry("model-servers", error=str(exc), kind="lmstudio", label="Model servers")]
    return [_discover_server(name) for name in names]


def discover_providers() -> list[dict]:
    """Fresh model lists per provider. Local servers are queried live; OpenAI comes from .env."""
    return [
        _discover_local("lmstudio", "LMSTUDIO_API_BASE", "http://127.0.0.1:1234", "/v1/models"),
        _discover_local("ollama", "OLLAMA_API_BASE", "http://127.0.0.1:11434", "/api/tags"),
        _discover_openai(),
        *_discover_servers(),
    ]
