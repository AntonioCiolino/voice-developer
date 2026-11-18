import ipaddress
import os
import re

import jwt
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from controller import config  # noqa: F401  (loads controller/.env)


# Auth config
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
ALLOWED_EMAILS = {e.strip() for e in os.getenv("ALLOWED_EMAILS", "").split(",") if e.strip()}
LOCAL_AUTH = os.getenv("VOICE_DEVELOPER_LOCAL_AUTH") == "1"
LAN_LOCAL_AUTH = os.getenv("VOICE_DEVELOPER_LOCAL_AUTH_LAN") == "1"


def private_lan_address(value: str | None) -> str | None:
    """The address if it is a private IPv4 LAN address (10/8, 172.16/12, 192.168/16), else None.

    Loopback, link-local, unspecified (0.0.0.0) and public addresses never qualify, so LAN
    mode can only ever listen on the Mac's own private network address.
    """
    try:
        ip = ipaddress.ip_address((value or "").strip())
    except ValueError:
        return None
    ok = ip.version == 4 and ip.is_private and not (ip.is_loopback or ip.is_link_local or ip.is_unspecified)
    return str(ip) if ok else None


def lan_client_network(bind_address: str) -> ipaddress.IPv4Network:
    """Clients allowed in LAN mode: the /22 around the bind address (e.g. 192.168.5.x -> 192.168.4.0/22)."""
    return ipaddress.ip_network(f"{bind_address}/22", strict=False)


# The Mac's current LAN address comes from the start command, not from code, because DHCP can
# change it. It must be a private address; validate_auth_config refuses anything else.
# The placeholder is never used: LAN mode refuses to start unless the host is a real private address.
LAN_BIND_ADDRESS = private_lan_address(os.getenv("VOICE_DEVELOPER_HOST")) or "192.168.0.1"
LAN_HOSTNAMES = {"r2m2.local", LAN_BIND_ADDRESS}
LAN_CLIENT_NETWORK = lan_client_network(LAN_BIND_ADDRESS)
LOOPBACK = {"localhost", "127.0.0.1", "::1"}
SESSION_COOKIE = "vd_session"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def get_session_email(request: Request) -> str | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        payload = jwt.decode(token, SESSION_SECRET, algorithms=["HS256"])
        return payload.get("email")
    except Exception:
        return None


def get_session_name(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return ""
    try:
        payload = jwt.decode(token, SESSION_SECRET, algorithms=["HS256"])
        return payload.get("name", payload.get("email", ""))
    except Exception:
        return ""


async def require_auth(request: Request, call_next):
    if LOCAL_AUTH:
        origin = request.headers.get("origin")
        request_hostname = (request.url.hostname or "").lower()
        client_is_loopback = request.client and request.client.host in LOOPBACK
        client_is_lan = False
        if request.client:
            try:
                client_is_lan = ipaddress.ip_address(request.client.host) in LAN_CLIENT_NETWORK
            except ValueError:
                client_is_lan = False
        if LAN_LOCAL_AUTH:
            allowed_hostname = request_hostname in LAN_HOSTNAMES
            allowed_client = client_is_lan
        else:
            allowed_hostname = request_hostname in LOOPBACK
            allowed_client = client_is_loopback
        if (
            not allowed_hostname
            or not allowed_client
            or (origin and origin != str(request.base_url).rstrip("/"))
            or request.url.path.startswith("/auth/")
        ):
            return HTMLResponse("Local access only", status_code=403)
        return await call_next(request)
    if request.url.path.startswith("/auth/"):
        return await call_next(request)
    if not get_session_email(request):
        return RedirectResponse(url="/auth/login")
    return await call_next(request)


def validate_auth_config() -> None:
    """Startup checks for the selected authentication mode."""
    configured_host = os.getenv("VOICE_DEVELOPER_HOST", "127.0.0.1")
    if LOCAL_AUTH:
        if LAN_LOCAL_AUTH:
            if private_lan_address(configured_host) != configured_host:
                raise RuntimeError(
                    "LAN local authentication requires VOICE_DEVELOPER_HOST to be this Mac's "
                    "private LAN address (10.x, 172.16-31.x or 192.168.x), not 0.0.0.0 or a public address."
                )
        elif configured_host != "127.0.0.1":
            raise RuntimeError("Local authentication mode requires binding to 127.0.0.1.")
    if not LOCAL_AUTH and (not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET or not ALLOWED_EMAILS):
        raise RuntimeError("Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and ALLOWED_EMAILS in controller/.env.")
    if not LOCAL_AUTH and not re.fullmatch(r"[0-9a-fA-F]{64}", SESSION_SECRET):
        raise RuntimeError("Set SESSION_SECRET to a random value generated with secrets.token_hex(32).")
