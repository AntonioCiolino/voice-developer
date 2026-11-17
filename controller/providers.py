import ipaddress
import os
from dataclasses import dataclass
from urllib.parse import urlparse

from controller import config  # noqa: F401  (loads controller/.env)


class PlannerConfigurationError(ValueError):
    """Raised when the selected planner provider is not configured."""


# Ollama tags found (by discovery) to run in Ollama's cloud even though their names
# carry no :cloud suffix, e.g. a model created FROM a cloud model. Updated on each
# discovery of the Ollama server.
OLLAMA_REMOTE_MODELS: set[str] = set()


@dataclass(frozen=True)
class PlannerProvider:
    name: str
    model: str
    api_key: str | None = None
    ollama_api_base: str | None = None
    lmstudio_api_base: str | None = None

    @property
    def is_local(self) -> bool:
        if self.name == "ollama" and (
            self.model.lower().endswith((":cloud", "-cloud")) or self.model in OLLAMA_REMOTE_MODELS
        ):
            return False  # served through the local Ollama server but run in the cloud
        return self.name in LOCAL_PROVIDERS

    @property
    def location(self) -> str:
        return "local" if self.is_local else "cloud"

    @property
    def planner_base_url(self) -> str | None:
        if self.name == "ollama":
            return f"{self.ollama_api_base}/v1"
        if self.name == "lmstudio":
            return f"{self.lmstudio_api_base}/v1"
        return None

    @property
    def aider_model(self) -> str:
        if self.name == "ollama":
            return f"ollama_chat/{self.model}"
        if self.name == "lmstudio":
            return f"lm_studio/{self.model}"
        return self.model


LOCAL_PROVIDERS = frozenset({"ollama", "lmstudio"})
# LM Studio's local server does not check the key, but the OpenAI client and
# litellm both require a non-empty value.
LMSTUDIO_PLACEHOLDER_KEY = "lm-studio"


_OLLAMA_SUBPROCESS_ENV_VARS = frozenset({
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "LC_MESSAGES",
    "LC_NUMERIC",
    "LC_TIME",
    "LOGNAME",
    "PATH",
    "SHELL",
    "TERM",
    "TMPDIR",
    "TMP",
    "TEMP",
    "USER",
    "VIRTUAL_ENV",
})


def _normalize_ollama_api_base(value: str, variable: str = "OLLAMA_API_BASE") -> str:
    """Normalize a local server base URL and require it to be loopback (used for Ollama and LM Studio)."""
    base = value.strip().rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3].rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment:
        raise PlannerConfigurationError(
            f"{variable} must be an HTTP(S) URL without a query or fragment"
        )
    if parsed.username is not None or parsed.password is not None:
        raise PlannerConfigurationError(f"{variable} must not include URL credentials")
    try:
        host = parsed.hostname
        parsed.port
        is_loopback = host == "localhost" or (
            host is not None and ipaddress.ip_address(host).is_loopback
        )
    except ValueError:
        is_loopback = False
    if not is_loopback:
        raise PlannerConfigurationError(
            f"{variable} must resolve to localhost, 127.0.0.1, or ::1 in local-only mode"
        )
    return base


_VALID_PROVIDERS = {"openai", "ollama", "lmstudio"}


def _provider_name(values, provider_var: str, default: str) -> str:
    name = values.get(provider_var, "").strip().lower() or default
    if name not in _VALID_PROVIDERS:
        raise PlannerConfigurationError(
            f"{provider_var} must be one of 'openai', 'ollama', or 'lmstudio'"
        )
    return name


def _resolve_role(values, provider_var: str, model_var: str, default_provider: str) -> PlannerProvider:
    """Resolve one role (planner or coder). A bad setting raises; it never falls back to another provider."""
    provider_name = _provider_name(values, provider_var, default_provider)
    role_model = values.get(model_var, "").strip()
    if provider_name == "openai":
        api_key = values.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise PlannerConfigurationError(f"OPENAI_API_KEY is required when {provider_var}=openai")
        model = role_model or values.get("OPENAI_MODEL", "gpt-5.4-mini").strip() or "gpt-5.4-mini"
        return PlannerProvider(name="openai", model=model, api_key=api_key)
    if provider_name == "lmstudio":
        model = role_model or values.get("LMSTUDIO_MODEL", "").strip()
        if not model:
            raise PlannerConfigurationError(
                f"LMSTUDIO_MODEL (or {model_var}) is required when {provider_var}=lmstudio"
            )
        try:
            api_base = _normalize_ollama_api_base(
                values.get("LMSTUDIO_API_BASE", "http://127.0.0.1:1234"), "LMSTUDIO_API_BASE"
            )
        except PlannerConfigurationError as exc:
            raise PlannerConfigurationError(f"{provider_var}=lmstudio: {exc}") from None
        return PlannerProvider(name="lmstudio", model=model, lmstudio_api_base=api_base)
    model = role_model or values.get("OLLAMA_MODEL", "").strip()
    if not model:
        raise PlannerConfigurationError(
            f"OLLAMA_MODEL (or {model_var}) is required when {provider_var}=ollama"
        )
    try:
        api_base = _normalize_ollama_api_base(
            values.get("OLLAMA_API_BASE", "http://127.0.0.1:11434")
        )
    except PlannerConfigurationError as exc:
        raise PlannerConfigurationError(f"{provider_var}=ollama: {exc}") from None
    return PlannerProvider(name="ollama", model=model, ollama_api_base=api_base)


def _values(env: dict[str, str] | None):
    """The environment to resolve from: the given mapping, else .env plus any saved UI selection."""
    if env is not None:
        return env
    from controller.selection import effective_env  # lazy: selection imports providers
    return effective_env()
def resolve_planner_provider(env: dict[str, str] | None = None) -> PlannerProvider:
    """Resolve and validate the explicitly selected planner provider."""
    values = _values(env)
    return _resolve_role(values, "PLANNER_PROVIDER", "PLANNER_MODEL", "openai")


def resolve_coder_provider(env: dict[str, str] | None = None) -> PlannerProvider:
    """Resolve the coder (Aider) provider; it defaults to the planner's provider name."""
    values = _values(env)
    default = _provider_name(values, "PLANNER_PROVIDER", "openai")
    return _resolve_role(values, "CODER_PROVIDER", "CODER_MODEL", default)


def resolve_roles(env: dict[str, str] | None = None) -> tuple[PlannerProvider, PlannerProvider]:
    """Resolve (planner, coder) together so bad coder config fails before any planning."""
    if env is None:
        env = _values(None)  # one snapshot so both roles see the same selection
    return resolve_planner_provider(env), resolve_coder_provider(env)


def create_planner_client(provider: PlannerProvider):
    """Create the OpenAI-compatible client for the selected provider."""
    from openai import OpenAI

    if provider.name == "ollama":
        return OpenAI(api_key="ollama", base_url=provider.planner_base_url)
    if provider.name == "lmstudio":
        return OpenAI(api_key=LMSTUDIO_PLACEHOLDER_KEY, base_url=provider.planner_base_url)
    return OpenAI(api_key=provider.api_key)


def planner_provider_info(provider: PlannerProvider) -> dict[str, str]:
    """Return safe provider evidence for UI and API responses."""
    if provider.name == "ollama":
        return {
            "name": "ollama",
            "label": "Ollama / local-only" if provider.is_local else "Ollama cloud model (via local server)",
            "model": provider.model,
            "endpoint": provider.planner_base_url,
            "location": provider.location,
        }
    if provider.name == "lmstudio":
        return {
            "name": "lmstudio",
            "label": "LM Studio / local-only",
            "model": provider.model,
            "endpoint": provider.planner_base_url,
            "location": "local",
        }
    return {
        "name": "openai",
        "label": "OpenAI",
        "model": provider.model,
        "endpoint": "OpenAI-managed endpoint",
        "location": "cloud",
    }


def role_provider_info(role: str, provider: PlannerProvider) -> dict[str, str]:
    """Safe per-role evidence (no keys)."""
    if provider.name == "ollama":
        label = "Ollama (local)" if provider.is_local else "Ollama cloud model (via local server)"
        endpoint = provider.planner_base_url
    elif provider.name == "lmstudio":
        label, endpoint = "LM Studio (local)", provider.planner_base_url
    else:
        label, endpoint = "OpenAI (cloud)", "OpenAI-managed endpoint"
    return {"role": role, "name": provider.name, "label": label,
            "model": provider.model, "endpoint": endpoint, "location": provider.location}


def roles_info(planner: PlannerProvider, coder: PlannerProvider) -> dict:
    return {
        "planner": role_provider_info("planner", planner),
        "coder": role_provider_info("coder", coder),
        "local_only": planner.is_local and coder.is_local,
    }
_OPENAI_OPTIONAL_ENV_VARS = frozenset({
    "OPENAI_API_BASE", "OPENAI_BASE_URL", "OPENAI_ORG_ID",
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy",
    "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE",
})


def provider_environment(provider: PlannerProvider, base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Build a role's subprocess environment: allowlist plus only that role's own endpoint/credential."""
    source = os.environ if base_env is None else base_env
    environment = {
        variable: value
        for variable, value in source.items()
        if variable in _OLLAMA_SUBPROCESS_ENV_VARS
    }
    if provider.name == "ollama":
        environment["OLLAMA_API_BASE"] = provider.ollama_api_base
        return environment
    if provider.name == "lmstudio":
        # litellm's lm_studio/ provider reads these two variables.
        environment["LM_STUDIO_API_BASE"] = provider.planner_base_url
        environment["LM_STUDIO_API_KEY"] = LMSTUDIO_PLACEHOLDER_KEY
        return environment
    for variable in _OPENAI_OPTIONAL_ENV_VARS:
        if variable in source:
            environment[variable] = source[variable]
    environment["OPENAI_API_KEY"] = provider.api_key
    return environment
