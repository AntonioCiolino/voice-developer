"""Named model servers (LM Studio, Ollama or any OpenAI-compatible server) on this machine or the LAN.

A server is configured in .env, never by the UI or the voice user:

    ALLOW_LAN_MODEL_SERVERS=on
    MODEL_SERVERS=mini,studio
    MODEL_SERVER_MINI_KIND=lmstudio        # lmstudio | ollama
    MODEL_SERVER_MINI_URL=http://r2m2-mini.local:1234

Servers are validated only when used. Error text names the setting and never echoes the URL.
A `.local` host is resolved on every use and the validated IPv4 replaces the name in the
returned base, so the name is not resolved a second time between the check and the use.
"""
import concurrent.futures
import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

from controller.providers import PlannerConfigurationError

RESERVED_NAMES = frozenset({"openai", "ollama", "lmstudio"})
KINDS = ("lmstudio", "ollama")
RESOLVE_TIMEOUT_SECONDS = 2
_NAME = re.compile(r"^[a-z][a-z0-9-]{0,23}$")
_LOCAL_HOST = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)*\.local$", re.IGNORECASE)
_PRIVATE_NETWORKS = tuple(
    ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)
_OPT_IN = "ALLOW_LAN_MODEL_SERVERS"
_NEEDS_OPT_IN = "set ALLOW_LAN_MODEL_SERVERS=on to use a model server on the local network"


@dataclass(frozen=True)
class ModelServer:
    name: str
    kind: str   # "lmstudio" | "ollama"
    base: str   # http(s)://host[:port], no trailing slash or /v1; a .local host is already pinned to its IPv4
    lan: bool   # True when the host is on the local network rather than this machine


def _infix(name: str) -> str:
    return name.upper().replace("-", "_")


def lan_opt_in(values) -> bool:
    value = values.get(_OPT_IN, "").strip().lower()
    if value in ("on", "1"):
        return True
    if value in ("", "off", "0"):
        return False
    raise PlannerConfigurationError(f"{_OPT_IN} must be 'on' or 'off'")


def server_names(values) -> list[str]:
    """Names listed in MODEL_SERVERS (empty when unset). Raises if the list is malformed."""
    raw = values.get("MODEL_SERVERS", "").strip()
    if not raw:
        return []
    names: list[str] = []
    for entry in raw.split(","):
        name = entry.strip().lower()
        if not name:
            raise PlannerConfigurationError("MODEL_SERVERS has an empty entry")
        if not _NAME.match(name):
            raise PlannerConfigurationError(
                "MODEL_SERVERS names must start with a letter and use only a-z, 0-9 and '-' (at most 24 characters)")
        if name in RESERVED_NAMES:
            raise PlannerConfigurationError(
                "MODEL_SERVERS names may not be 'openai', 'ollama' or 'lmstudio'")
        if name in names:
            raise PlannerConfigurationError(f"MODEL_SERVERS lists '{name}' more than once")
        names.append(name)
    return names


def _is_private(address: str) -> bool:
    try:
        ip = ipaddress.IPv4Address(address)
    except ValueError:
        return False
    return any(ip in network for network in _PRIVATE_NETWORKS)


def _resolve_ipv4(host: str, port: int | None = None, variable: str = "the model server URL") -> list[str]:
    """IPv4 addresses for `host`, looked up fresh each call with a short timeout."""
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(socket.getaddrinfo, host, port, socket.AF_INET)
        try:
            infos = future.result(timeout=RESOLVE_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            raise PlannerConfigurationError(f"{variable}: the host name did not resolve in time") from None
        except OSError:
            raise PlannerConfigurationError(f"{variable}: the host name does not resolve") from None
    finally:
        executor.shutdown(wait=False)
    addresses: list[str] = []
    for info in infos:
        address = info[4][0]
        if address not in addresses:
            addresses.append(address)
    return addresses


def validate_server_url(value: str, variable: str, allow_lan: bool) -> tuple[str, bool]:
    """Validate a model server URL. Returns (base, lan); a .local host is pinned to its IPv4."""
    text = value.strip()
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise PlannerConfigurationError(f"{variable} must be an HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise PlannerConfigurationError(f"{variable} must not include URL credentials")
    if parsed.query or parsed.fragment or "?" in text or "#" in text:
        raise PlannerConfigurationError(f"{variable} must not include a query or fragment")
    try:
        port = parsed.port
        host = parsed.hostname
    except ValueError:
        raise PlannerConfigurationError(f"{variable} has an invalid port") from None
    if not host:
        raise PlannerConfigurationError(f"{variable} must be an HTTP(S) URL")
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3].rstrip("/")

    def build(netloc: str) -> str:
        return f"{parsed.scheme}://{netloc}{path}"

    if host == "localhost":
        return build(parsed.netloc), False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        if ip.is_loopback and (ip.version == 4 or str(ip) == "::1"):
            return build(parsed.netloc), False
        if ip.version == 4 and _is_private(host):
            if not allow_lan:
                raise PlannerConfigurationError(f"{variable}: {_NEEDS_OPT_IN}")
            return build(parsed.netloc), True
        raise PlannerConfigurationError(
            f"{variable} must point at this machine or a private network address (10.x, 172.16-31.x, 192.168.x)")
    if _LOCAL_HOST.match(host):
        if not allow_lan:
            raise PlannerConfigurationError(f"{variable}: {_NEEDS_OPT_IN}")
        if parsed.scheme == "https":
            raise PlannerConfigurationError(f"{variable}: https cannot be used with a .local host name; use http")
        addresses = _resolve_ipv4(host, port, variable)
        if not addresses or not all(_is_private(a) for a in addresses):
            raise PlannerConfigurationError(
                f"{variable}: the host name must resolve only to private network addresses")
        pinned = addresses[0] if port is None else f"{addresses[0]}:{port}"
        return build(pinned), True
    raise PlannerConfigurationError(
        f"{variable} must be localhost, a private network IP address, or a .local host name")


_KIND_DISPLAY = {"lmstudio": "LM Studio", "ollama": "Ollama"}


def server_label(values, name: str, kind: str | None = None) -> str:
    """Display name for a server: MODEL_SERVER_<NAME>_LABEL, else "<kind> on <name>".

    Needed because kind "lmstudio" means "any OpenAI-compatible server" (MTPLX too),
    so the default name can be misleading. Never contains the URL.
    """
    raw = values.get(f"MODEL_SERVER_{_infix(name)}_LABEL", "").strip()
    cleaned = "".join(ch for ch in raw if ch.isprintable())[:40].strip()
    if cleaned:
        return cleaned
    kind = kind or values.get(f"MODEL_SERVER_{_infix(name)}_KIND", "").strip().lower()
    return f"{_KIND_DISPLAY.get(kind, 'Server')} on {name}"


def resolve_server(values, name: str) -> ModelServer:
    """Build a configured server. A .local host is resolved now; call again to refresh."""
    if name not in server_names(values):
        raise PlannerConfigurationError(f"'{name}' is not a configured model server")
    infix = _infix(name)
    kind_var, url_var = f"MODEL_SERVER_{infix}_KIND", f"MODEL_SERVER_{infix}_URL"
    kind = values.get(kind_var, "").strip().lower()
    if kind not in KINDS:
        raise PlannerConfigurationError(f"{kind_var} must be 'lmstudio' or 'ollama'")
    url = values.get(url_var, "").strip()
    if not url:
        raise PlannerConfigurationError(f"{url_var} is required for model server '{name}'")
    base, lan = validate_server_url(url, url_var, lan_opt_in(values))
    return ModelServer(name, kind, base, lan)
