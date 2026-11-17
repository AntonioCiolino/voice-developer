import asyncio
import ipaddress
import json
import logging
import os
import pathlib
import re
import shutil
import subprocess
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

load_dotenv(pathlib.Path(__file__).with_name(".env"))

REPO_ROOT = pathlib.Path(__file__).parent.parent
APP_ROOT = REPO_ROOT / "generated-app"
APP_SRC = APP_ROOT / "src"
SAVED_APPS = REPO_ROOT / "saved-apps"
PLANS_DIR = REPO_ROOT / "plans"
logger = logging.getLogger("voice-developer")

# Auth config
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
ALLOWED_EMAILS = {e.strip() for e in os.getenv("ALLOWED_EMAILS", "").split(",") if e.strip()}
LOCAL_AUTH = os.getenv("VOICE_DEVELOPER_LOCAL_AUTH") == "1"
LAN_LOCAL_AUTH = os.getenv("VOICE_DEVELOPER_LOCAL_AUTH_LAN") == "1"
LAN_BIND_ADDRESS = "192.168.5.33"
LAN_HOSTNAMES = {"r2m2.local", LAN_BIND_ADDRESS}
LAN_CLIENT_NETWORK = ipaddress.ip_network("192.168.4.0/22")
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

# In-memory job store and queue
jobs: dict = {}
job_queue: asyncio.Queue = None
active_job_id: str | None = None


class SaveRequest(BaseModel):
    name: str
    overwrite: bool = False


class PlanRequest(BaseModel):
    prompt: str


class LoadAppRequest(BaseModel):
    name: str


class PlannerConfigurationError(ValueError):
    """Raised when the selected planner provider is not configured."""


@dataclass(frozen=True)
class PlannerProvider:
    name: str
    model: str
    api_key: str | None = None
    ollama_api_base: str | None = None
    lmstudio_api_base: str | None = None

    @property
    def is_local(self) -> bool:
        return self.name in LOCAL_PROVIDERS

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
def resolve_planner_provider(env: dict[str, str] | None = None) -> PlannerProvider:
    """Resolve and validate the explicitly selected planner provider."""
    values = os.environ if env is None else env
    return _resolve_role(values, "PLANNER_PROVIDER", "PLANNER_MODEL", "openai")
def resolve_coder_provider(env: dict[str, str] | None = None) -> PlannerProvider:
    """Resolve the coder (Aider) provider; it defaults to the planner's provider name."""
    values = os.environ if env is None else env
    default = _provider_name(values, "PLANNER_PROVIDER", "openai")
    return _resolve_role(values, "CODER_PROVIDER", "CODER_MODEL", default)
def resolve_roles(env: dict[str, str] | None = None) -> tuple[PlannerProvider, PlannerProvider]:
    """Resolve (planner, coder) together so bad coder config fails before any planning."""
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
            "label": "Ollama / local-only",
            "model": provider.model,
            "endpoint": provider.planner_base_url,
        }
    if provider.name == "lmstudio":
        return {
            "name": "lmstudio",
            "label": "LM Studio / local-only",
            "model": provider.model,
            "endpoint": provider.planner_base_url,
        }
    return {
        "name": "openai",
        "label": "OpenAI",
        "model": provider.model,
        "endpoint": "OpenAI-managed endpoint",
    }


def role_provider_info(role: str, provider: PlannerProvider) -> dict[str, str]:
    """Safe per-role evidence (no keys)."""
    if provider.name == "ollama":
        label, endpoint = "Ollama (local)", provider.planner_base_url
    elif provider.name == "lmstudio":
        label, endpoint = "LM Studio (local)", provider.planner_base_url
    else:
        label, endpoint = "OpenAI (cloud)", "OpenAI-managed endpoint"
    return {"role": role, "name": provider.name, "label": label,
            "model": provider.model, "endpoint": endpoint}
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
class CoderEngineNotImplemented(RuntimeError):
    """Raised when the selected coder engine is only a stub."""


OPENCODE_NOT_IMPLEMENTED = (
    "OpenCode coder engine is not implemented yet. Set CODER_ENGINE=aider or unset it."
)
_CODER_ENGINES = ("aider", "opencode")
_EDIT_FORMATS = ("diff", "diff-fenced", "udiff", "whole")
DEFAULT_CODER_TIMEOUT_SECONDS = 120
PLAN_CONTEXT_LIMIT = 4000
LOG_TAIL_LIMIT = 4000


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


def resolve_coder_edit_format(env: dict[str, str] | None = None) -> str:
    """CODER_EDIT_FORMAT: Aider edit format (default 'diff')."""
    values = os.environ if env is None else env
    edit_format = values.get("CODER_EDIT_FORMAT", "").strip().lower() or "diff"
    if edit_format not in _EDIT_FORMATS:
        raise PlannerConfigurationError(
            "CODER_EDIT_FORMAT must be one of: " + ", ".join(_EDIT_FORMATS)
        )
    return edit_format


AIDER_VENV_BIN = REPO_ROOT / "controller" / "aider-venv" / "bin" / "aider"


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


def build_opencode_command(provider: PlannerProvider, task_prompt: str) -> list[str]:
    """OpenCode integration point (stub: the command is defined but never executed).

    Future implementer notes:
    - Ollama must be registered as an OpenAI-compatible provider pointing at
      "<OLLAMA_API_BASE>/v1" in the opencode config, with a context window of 64k or more.
    - Run it with provider_environment(provider) so credentials stay isolated per role.
    - Parse the `--format json` event stream for the task log and error text.
    """
    return ["opencode", "run", "--model", f"{provider.name}/{provider.model}",
            "--format", "json", task_prompt]


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


def extract_cost(log: str) -> str:
    m = re.search(r'Cost:\s*(\$[\d.]+)\s*message', log)
    return m.group(1) if m else ''


# ---- Plan parsing -------------------------------------------------------

_HEADING_RE = re.compile(r"^\s*#{1,6}\s")
_TASKS_HEADING_RE = re.compile(r"^\s*#{1,6}\s*(\d+[.)]\s*)?tasks?\s*:?\s*$", re.IGNORECASE)
_TASK_LINE_RE = re.compile(r"^\s*\d+[.)]\s+(.+)$")


def parse_tasks(plan_text: str) -> list[str]:
    """Extract the clean task list: only the Tasks section, outside code fences, deduplicated."""
    lines = (plan_text or "").splitlines()

    def numbered(section: list[str]) -> list[str]:
        found, in_fence = [], False
        for line in section:
            if line.strip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            match = _TASK_LINE_RE.match(line)
            if match:
                text = match.group(1).strip()
                if text and text not in found:
                    found.append(text)
        return found

    def until_heading(section: list[str]) -> list[str]:
        out, in_fence = [], False
        for line in section:
            if line.strip().startswith("```"):
                in_fence = not in_fence
            elif not in_fence and _HEADING_RE.match(line):
                break
            out.append(line)
        return out

    for idx, line in enumerate(lines):
        if _TASKS_HEADING_RE.match(line):
            return numbered(until_heading(lines[idx + 1:]))
    return numbered(until_heading(lines))


# ---- Plan persistence ---------------------------------------------------

_PLAN_FILE_RE = re.compile(r"^[0-9a-f-]{36}\.json$")


def save_job(job_id: str) -> None:
    """Atomically write the job record to PLANS_DIR/<job_id>.json."""
    job = jobs[job_id]
    job["id"] = job_id
    job["updated_at"] = datetime.now().isoformat()
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    target = PLANS_DIR / f"{job_id}.json"
    tmp = PLANS_DIR / f".{job_id}.json.tmp"
    tmp.write_text(json.dumps(job, indent=2))
    os.replace(tmp, target)


def load_jobs() -> None:
    """Load stored plans into `jobs`. Jobs interrupted by a restart are made resumable."""
    if not PLANS_DIR.exists():
        return
    for path in sorted(PLANS_DIR.iterdir()):
        if not _PLAN_FILE_RE.match(path.name):
            continue
        try:
            job = json.loads(path.read_text())
            if not isinstance(job, dict) or not isinstance(job.get("tasks"), list):
                raise ValueError("not a plan record")
        except Exception as exc:
            logger.warning("Skipping unreadable plan file %s: %s", path.name, exc)
            continue
        job_id = path.stem
        changed = False
        if job.get("status") == "running":
            running = [i for i, s in enumerate(job.get("task_statuses", [])) if s == "running"]
            for i in running:
                job["task_statuses"][i] = "failed"
            which = f"task {running[0] + 1}" if running else "a task"
            job["status"] = "failed"
            job["error"] = f"Controller restarted while {which} was running"
            if running:
                errors = job.setdefault("task_errors", [""] * len(job["tasks"]))
                errors[running[0]] = job["error"]
            changed = True
        elif job.get("status") == "queued":
            job["status"] = "planned"
            changed = True
        jobs[job_id] = job
        if changed:
            try:
                save_job(job_id)
            except OSError as exc:
                logger.warning("Could not rewrite plan file %s: %s", path.name, exc)


# ---- Per-task snapshot and revert --------------------------------------

_BINARY_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.woff', '.woff2',
                '.ttf', '.eot', '.map', '.lock'}


def task_scope_files() -> list[pathlib.Path]:
    """The exact files handed to the coder: non-binary src/ files plus top-level config files."""
    files = [f for f in sorted(APP_SRC.rglob("*")) if f.is_file() and f.suffix not in _BINARY_EXTS]
    for extra in ["vite.config.js", "index.html", "package.json"]:
        p = APP_ROOT / extra
        if p.exists():
            files.append(p)
    return files


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(APP_ROOT), capture_output=True, text=True)


def snapshot_task_scope() -> dict:
    """Capture file contents and the app repo HEAD before a task runs."""
    head = None
    if (APP_ROOT / ".git").exists():
        result = _git("rev-parse", "HEAD")
        if result.returncode == 0:
            head = result.stdout.strip() or None
    return {
        "files": {f.relative_to(APP_ROOT).as_posix(): f.read_bytes() for f in task_scope_files()},
        "src_files": {f.relative_to(APP_ROOT).as_posix() for f in APP_SRC.rglob("*") if f.is_file()},
        "head": head,
    }


def revert_task(snapshot: dict) -> str:
    """Undo one task's changes: only snapshotted files and new src/ files, never the whole app."""
    notes = []
    old_head = snapshot.get("head")
    if old_head:
        current = _git("rev-parse", "HEAD")
        new_head = current.stdout.strip() if current.returncode == 0 else ""
        if new_head and new_head != old_head and _git("merge-base", "--is-ancestor", old_head, new_head).returncode == 0:
            if _git("reset", "--mixed", old_head).returncode == 0:
                notes.append("moved the app repo HEAD back to the previous step")
    for f in list(APP_SRC.rglob("*")):
        if f.is_file() and f.relative_to(APP_ROOT).as_posix() not in snapshot["src_files"]:
            f.unlink()
            notes.append(f"removed new file {f.relative_to(APP_ROOT).as_posix()}")
    for rel, data in snapshot["files"].items():
        path = APP_ROOT / rel
        if not path.exists() or path.read_bytes() != data:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            notes.append(f"restored {rel}")
    return "; ".join(notes)


def changed_task_paths(snapshot: dict) -> list[str]:
    """Paths (relative to APP_ROOT) that a task changed, created, or deleted."""
    changed = []
    for rel, data in snapshot["files"].items():
        path = APP_ROOT / rel
        if not path.exists() or path.read_bytes() != data:
            changed.append(rel)
    for f in APP_SRC.rglob("*"):
        rel = f.relative_to(APP_ROOT).as_posix()
        if f.is_file() and rel not in snapshot["src_files"]:
            changed.append(rel)
    return changed


def commit_task(snapshot: dict, message: str) -> str:
    """Commit only the files this task changed, with a controller-written message."""
    if not (APP_ROOT / ".git").exists():
        return "no app repo, nothing committed"
    paths = changed_task_paths(snapshot)
    if not paths:
        return "no file changes to commit"
    added = _git("add", "-A", "--", *paths)
    if added.returncode != 0:
        return f"commit skipped: git add failed: {added.stderr.strip()[-300:]}"
    committed = _git("commit", "-q", "-m", message, "--", *paths)
    if committed.returncode != 0:
        return f"commit skipped: {(committed.stderr or committed.stdout).strip()[-300:]}"
    return f"committed {len(paths)} file(s)"


_APP_IGNORES = ("node_modules/", "dist/", ".vite/", ".DS_Store")


def ensure_app_repo_hygiene() -> str:
    """Keep build artifacts out of the app repo so Aider does not scan thousands of files."""
    if not (APP_ROOT / ".git").exists():
        return ""
    gitignore = APP_ROOT / ".gitignore"
    existing = gitignore.read_text().splitlines() if gitignore.exists() else []
    missing = [p for p in _APP_IGNORES if p not in existing]
    if missing:
        text = "\n".join(existing + missing).strip("\n") + "\n"
        gitignore.write_text(text)
    tracked = [p.rstrip("/") for p in _APP_IGNORES if _git("ls-files", "--", p.rstrip("/")).stdout.strip()]
    if tracked:
        _git("rm", "-r", "-q", "--cached", "--ignore-unmatch", "--", *tracked)
    if not missing and not tracked:
        return ""
    _git("add", "--", ".gitignore")
    # Commit the index without a pathspec: a pathspec commit would re-stage the
    # ignored files from the working tree and undo the `rm --cached`.
    result = _git("commit", "-q", "-m", "chore: stop tracking build artifacts")
    return "untracked build artifacts" if result.returncode == 0 else ""


# ---- Job execution ------------------------------------------------------

def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _tail(value, limit: int = LOG_TAIL_LIMIT) -> str:
    return _text(value).strip()[-limit:]


def build_task_prompt(job: dict, i: int) -> str:
    completed = [
        f"  - Task {j+1} (done): {job['tasks'][j]}"
        for j in range(i) if job['task_statuses'][j] == 'done'
    ]
    plan_text = (job.get('plan') or '').strip()
    if len(plan_text) > PLAN_CONTEXT_LIMIT:
        plan_text = plan_text[:PLAN_CONTEXT_LIMIT] + "\n... (plan truncated)"
    return (
        f"Overall goal: {job['prompt']}\n\n"
        + "Architecture: pure React + Vite SPA. No backend server, no express/fastapi, "
        + "no public/ folder unless you create it. All logic goes in src/ JSX files. "
        + "Tailwind CSS is loaded via CDN in index.html.\n\n"
        + (f"Approved plan:\n{plan_text}\n\n" if plan_text else "")
        + (f"Tasks already completed:\n" + "\n".join(completed) + "\n\n" if completed else "")
        + f"Now implement Task {i+1}/{len(job['tasks'])}: {job['tasks'][i]}\n\n"
        + "Do not ask clarifying questions. Do not request additional files. "
        + "Make your best judgment and implement it directly in the files provided."
    )


def _fail_task(job_id: str, i: int, snapshot: dict | None, message: str) -> None:
    job = jobs[job_id]
    note = ""
    if snapshot is not None:
        try:
            note = revert_task(snapshot)
        except Exception as exc:  # keep the original failure visible
            note = f"revert failed: {exc}"
    job['task_statuses'][i] = 'failed'
    job['status'] = 'failed'
    job['error'] = message
    job['task_errors'][i] = message
    job['task_logs'][i] = (job['task_logs'][i] + "\n" if job['task_logs'][i] else "") + (
        "Reverted this task's changes" + (f" ({note})" if note else " (nothing to undo)")
    )
    save_job(job_id)


async def run_job(job_id: str) -> None:
    job = jobs[job_id]
    n = len(job['tasks'])
    job.setdefault('task_errors', [""] * n)
    job['status'] = 'running'
    job['error'] = None
    try:
        _, provider = resolve_roles()
        engine = resolve_coder_engine()
        timeout = resolve_coder_timeout()
        edit_format = resolve_coder_edit_format()
    except PlannerConfigurationError as exc:
        job['status'] = 'failed'
        job['error'] = str(exc)
        save_job(job_id)
        return
    job['engine'] = engine
    save_job(job_id)
    try:
        ensure_app_repo_hygiene()
    except Exception:
        pass  # hygiene is best-effort; never block a run on it

    for i in range(n):
        if job['task_statuses'][i] == 'done':
            continue
        job['current_task'] = i
        job['task_statuses'][i] = 'running'
        job['task_errors'][i] = ""
        save_job(job_id)
        snapshot = None
        try:
            snapshot = snapshot_task_scope()
            files = [str(f.relative_to(REPO_ROOT)) for f in task_scope_files()]
            command = build_coder_command(engine, provider, build_task_prompt(job, i), files, edit_format)
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, lambda cmd=command: subprocess.run(
                cmd,
                cwd=str(REPO_ROOT),
                env=provider_environment(provider),
                capture_output=True, text=True, timeout=timeout,
                stdin=subprocess.DEVNULL,
            ))
        except CoderEngineNotImplemented as exc:
            _fail_task(job_id, i, snapshot, str(exc))
            return
        except subprocess.TimeoutExpired as exc:
            message = f"Task {i+1} timed out after {timeout} s (CODER_TIMEOUT_SECONDS)."
            partial = _tail(exc.stderr) or _tail(exc.stdout)
            job['task_logs'][i] = _tail(exc.stdout)
            if partial:
                message += f"\nPartial output:\n{partial}"
            _fail_task(job_id, i, snapshot, message)
            return
        except FileNotFoundError as exc:
            missing = (
                f"aider not found at '{resolve_aider_bin()}'. Create it with: "
                "python3 -m venv controller/aider-venv && "
                "controller/aider-venv/bin/pip install aider-chat==0.86.2 (or set AIDER_BIN)"
            ) if engine == "aider" else str(exc)
            _fail_task(job_id, i, snapshot, missing)
            return
        except Exception as exc:
            _fail_task(job_id, i, snapshot, f"Task {i+1} failed: {exc}")
            return

        job['task_logs'][i] = _tail(result.stdout)
        job['task_costs'][i] = extract_cost(result.stdout)
        if result.returncode != 0:
            parts = [f"Task {i+1} failed (exit code {result.returncode})."]
            if _tail(result.stderr):
                parts.append("stderr:\n" + _tail(result.stderr))
            if _tail(result.stdout):
                parts.append("stdout:\n" + _tail(result.stdout))
            _fail_task(job_id, i, snapshot, "\n".join(parts))
            return
        app_jsx = APP_SRC / "App.jsx"
        if app_jsx.exists():
            content = app_jsx.read_text(errors='ignore')
            if len(content) < 100 or 'export default' not in content:
                _fail_task(job_id, i, snapshot, f"Task {i+1} corrupted App.jsx; its changes were reverted")
                return
        try:
            note = commit_task(snapshot, f"Task {i+1}/{n}: {job['tasks'][i]}"[:200])
        except Exception as exc:
            note = f"commit skipped: {exc}"
        job['task_logs'][i] = (job['task_logs'][i] + "\n" if job['task_logs'][i] else "") + note
        job['task_statuses'][i] = 'done'
        save_job(job_id)

    job['status'] = 'done'
    save_job(job_id)


async def job_worker():
    global active_job_id
    while True:
        job_id = await job_queue.get()
        active_job_id = job_id
        try:
            await run_job(job_id)
        except Exception as exc:  # never let one job kill the worker
            logger.exception("Job %s crashed", job_id)
            job = jobs.get(job_id)
            if job:
                job['status'] = 'failed'
                job['error'] = str(exc)
                try:
                    save_job(job_id)
                except OSError:
                    pass
        finally:
            active_job_id = None
            job_queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global job_queue
    configured_host = os.getenv("VOICE_DEVELOPER_HOST", "127.0.0.1")
    if LOCAL_AUTH:
        if LAN_LOCAL_AUTH:
            if configured_host != LAN_BIND_ADDRESS:
                raise RuntimeError(
                    f"LAN local authentication requires binding to {LAN_BIND_ADDRESS}."
                )
        elif configured_host != "127.0.0.1":
            raise RuntimeError("Local authentication mode requires binding to 127.0.0.1.")
    if not LOCAL_AUTH and (not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET or not ALLOWED_EMAILS):
        raise RuntimeError("Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and ALLOWED_EMAILS in controller/.env.")
    if not LOCAL_AUTH and not re.fullmatch(r"[0-9a-fA-F]{64}", SESSION_SECRET):
        raise RuntimeError("Set SESSION_SECRET to a random value generated with secrets.token_hex(32).")
    APP_SRC.mkdir(parents=True, exist_ok=True)
    load_jobs()
    job_queue = asyncio.Queue()
    worker = asyncio.create_task(job_worker())
    yield
    worker.cancel()


app = FastAPI(title="voice-developer controller", lifespan=lifespan)

@app.middleware("http")
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


PHONE_UI = """<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>voice-developer</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #09090b; font-family: system-ui, sans-serif; display: flex; flex-direction: column; height: 100dvh; }
    #panel { display: flex; flex-direction: column; gap: 8px; padding: 12px; background: #09090b; border-bottom: 1px solid #27272a; }
    textarea { width: 100%; background: #18181b; color: #fff; border: 1px solid #3f3f46; border-radius: 10px; padding: 10px 12px; font-size: 15px; resize: none; outline: none; }
    textarea:focus { border-color: #71717a; }
    #row { display: flex; gap: 8px; }
    button { flex: 1; background: #fff; color: #000; font-weight: 600; font-size: 15px; border: none; border-radius: 10px; padding: 11px; cursor: pointer; }
    button:disabled { opacity: 0.5; }
    #planBtn { background: #6366f1; color: #fff; }
    #planBtn:hover { background: #818cf8; }
    #status { font-size: 12px; color: #71717a; min-height: 16px; text-align: center; }
    #status.ok { color: #4ade80; }
    #status.err { color: #f87171; }
    #providerStatus { font-size: 11px; color: #a1a1aa; text-align: center; }
    #logToggle { background: none; border: none; color: #71717a; cursor: pointer; font-size: 12px; padding: 4px 8px; text-align: left; }
    #log { display: none; }
    #helpBtn { flex: none; width: 32px; padding: 8px; background: #3f3f46; color: #fff; }
    #helpModal, #logModal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.8); z-index: 1001; align-items: center; justify-content: center; }
    #helpModal.open, #logModal.open { display: flex; }
    .infoBox { background: #18181b; border: 1px solid #3f3f46; border-radius: 12px; width: 90%; max-width: 480px; max-height: 85vh; overflow-y: auto; padding: 20px; color: #d4d4d8; }
    .infoBox h2 { color: #fff; font-size: 17px; margin-bottom: 12px; }
    .infoBox p { font-size: 13px; line-height: 1.5; margin-bottom: 10px; }
    .infoBox button { margin-top: 8px; background: #3f3f46; color: #fff; }
    #logContent { white-space: pre-wrap; font: 11px/1.4 monospace; color: #a1a1aa; max-height: 60vh; overflow-y: auto; }
    #actions { display: flex; gap: 8px; margin-top: 8px; }
    #saveBtn, #newBtn, #loadBtn, #refreshBtn { flex: 1; background: #71717a; color: #fff; font-weight: 600; font-size: 13px; border: none; border-radius: 8px; padding: 8px; cursor: pointer; }
    #saveBtn:hover, #newBtn:hover, #loadBtn:hover, #refreshBtn:hover { background: #a1a1aa; }
    #refreshBtn { background: #3f3f46; }
    #userBar { display: flex; align-items: center; justify-content: space-between; font-size: 11px; color: #52525b; margin-top: 4px; }
    #logoutBtn { background: none; border: none; color: #52525b; cursor: pointer; font-size: 11px; padding: 0; flex: none; text-decoration: underline; }
    #loadModal { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.8); z-index: 999; }
    #loadModal.open { display: flex; align-items: center; justify-content: center; }
    #loadBox { background: #18181b; border: 1px solid #3f3f46; border-radius: 12px; width: 90%; max-width: 400px; max-height: 70vh; overflow-y: auto; padding: 20px; }
    #loadBox h2 { color: #fff; margin: 0 0 12px; font-size: 16px; }
    #appsList { display: flex; flex-direction: column; gap: 8px; }
    .appItem { background: #27272a; border: 1px solid #3f3f46; border-radius: 8px; padding: 12px; cursor: pointer; }
    .appItem:hover { background: #3f3f46; border-color: #6366f1; }
    .appItem-name { color: #fff; font-weight: 600; font-size: 13px; }
    .appItem-info { color: #a1a1aa; font-size: 11px; margin-top: 4px; }
    #modal { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); align-items: center; justify-content: center; z-index: 999; }
    #modal.open { display: flex; }
    #modalContent { background: #18181b; border: 1px solid #3f3f46; border-radius: 12px; padding: 20px; width: 90%; max-width: 300px; }
    #modalContent h2 { color: #fff; margin: 0 0 12px; font-size: 16px; }
    #modalInput { width: 100%; background: #09090b; color: #fff; border: 1px solid #3f3f46; border-radius: 8px; padding: 10px; font-size: 14px; margin-bottom: 12px; outline: none; }
    #modalInput:focus { border-color: #71717a; }
    #modalBtns { display: flex; gap: 8px; }
    #modalBtns button { flex: 1; padding: 10px; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; }
    #saveConfirm { background: #4ade80; color: #000; }
    #cancelModal { background: #3f3f46; color: #fff; }
    #processing { color: #f97316; font-weight: 600; font-size: 13px; margin-top: 8px; display: none; }
    #processing.active { display: block; }
    #processing::before { content: '⏳ '; }
    iframe { flex: 1; border: none; background: #fff; }
    .taskItem { border: 1px solid #3f3f46; border-radius: 8px; overflow: hidden; background: #18181b; }
    .taskHeader { display: flex; align-items: center; gap: 8px; padding: 9px 12px; cursor: pointer; user-select: none; }
    .taskHeader:hover { background: #27272a; }
    .taskIcon { font-size: 13px; flex-shrink: 0; width: 18px; text-align: center; color: #52525b; }
    .taskLabel { flex: 1; font-size: 12px; color: #71717a; }
    .taskMeta { font-size: 11px; color: #52525b; flex-shrink: 0; }
    .taskChevron { font-size: 10px; color: #52525b; flex-shrink: 0; }
    .taskLog { font-size: 11px; font-family: monospace; color: #a1a1aa; padding: 8px 12px; background: #09090b; border-top: 1px solid #27272a; line-height: 1.4; max-height: 180px; overflow-y: auto; white-space: pre-wrap; display: none; }
    .task-running .taskHeader { background: rgba(251,191,36,0.05); }
    .task-running .taskIcon { color: #fbbf24; }
    .task-running .taskLabel { color: #fbbf24; }
    .task-done .taskIcon { color: #4ade80; }
    .task-done .taskLabel { color: #d4d4d8; }
    .task-failed .taskIcon { color: #f87171; }
    .task-failed .taskLabel { color: #f87171; }
    #planHeader { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
    #fullPlanToggle { background: none; border: 1px solid #3f3f46; color: #71717a; border-radius: 6px; padding: 3px 10px; cursor: pointer; font-size: 11px; flex: none; }
    #fullPlanText { display: none; font-size: 11px; color: #71717a; white-space: pre-wrap; margin-bottom: 12px; background: #09090b; border-radius: 6px; padding: 10px; line-height: 1.6; border: 1px solid #27272a; max-height: 200px; overflow-y: auto; }
    #taskList { display: flex; flex-direction: column; gap: 5px; margin-bottom: 12px; }
  </style>
</head>
<body>
  <div id="panel">
    <textarea id="prompt" rows="3" placeholder="Describe the app you want..."></textarea>
    <div id="row">
      <button id="planBtn" title="Create a plan and task list. It starts automatically after 5 seconds unless you cancel." onclick="plan()">Plan</button>
      <button id="btn" title="Resume the latest stored plan from its next pending or failed task. Where it runs is set by PLANNER_*/CODER_* in controller/.env." onclick="continuePlan()">Continue plan</button>
      <button id="currentPlanBtn" title="View the plan currently running on the server." onclick="showActivePlan()" style="background:#3f3f46;display:none;">Current Plan</button>
      <button id="helpBtn" title="Learn what each controller action does." aria-label="Open controller help" aria-controls="helpModal" aria-haspopup="dialog" onclick="openHelpModal()">ⓘ</button>
    </div>
    <div id="status"></div>
    <div id="providerStatus">Planner provider: loading...</div>
    <div id="processing"></div>
    <button id="logToggle" title="Open the latest task error or output in a larger window." aria-label="Open task log" aria-controls="logModal" aria-haspopup="dialog" onclick="openLogModal()">▶ log</button>
    <div id="log"></div>
    <div id="actions">
      <button id="saveBtn" title="Save the current generated app to the saved-apps list." onclick="openSaveModal()">Save App</button>
      <button id="loadBtn" title="Load a previously saved app." onclick="openLoadModal()">Load App</button>
      <button id="newBtn" title="Reset the generated app and start fresh." onclick="newApp()">New App</button>
      <button id="refreshBtn" title="Reload the generated app preview." onclick="reloadPreview()">⟳</button>
    </div>
    <div id="userBar">
      <span>{{USER_NAME}}</span>
      <button title="Sign out of the controller." {{LOGOUT_VISIBILITY}} id="logoutBtn" onclick="window.location='/auth/logout'">logout</button>
    </div>
  </div>

  <div id="loadModal" onclick="if(event.target===this)closeLoadModal()">
    <div id="loadBox">
      <h2>Load App</h2>
      <div id="appsList"></div>
    </div>
  </div>

  <div id="helpModal" role="dialog" aria-modal="true" aria-labelledby="helpModalTitle" tabindex="-1" onclick="if(event.target===this)closeHelpModal()">
    <div class="infoBox">
      <h2 id="helpModalTitle">Using the controller</h2>
      <p>Describe your app in the prompt, then choose <strong>Plan</strong>. The generated app appears in the preview below.</p>
      <p><strong>Plan</strong> creates a plan and a task list. The tasks start automatically after 5 seconds. Click the button during the countdown to cancel, or close the plan window.</p>
      <p><strong>Continue plan</strong> resumes the latest stored plan from its next pending or failed task. A failed task stops the run and only that task's changes are undone. Where the code runs (local or cloud, which model) is set by PLANNER_* and CODER_* in controller/.env, not by the button.</p>
      <p><strong>Save App</strong> stores the current app. <strong>Load App</strong> restores a saved app.</p>
      <p><strong>New App</strong> clears the current app. Use <strong>⟳</strong> to reload the preview.</p>
      <p><strong>log</strong> opens the latest task error or output for troubleshooting.</p>
      <button id="helpCloseBtn" type="button" aria-label="Close controller help" onclick="closeHelpModal()">Close</button>
    </div>
  </div>

  <div id="logModal" role="dialog" aria-modal="true" aria-labelledby="logModalTitle" tabindex="-1" onclick="if(event.target===this)closeLogModal()">
    <div class="infoBox">
      <h2 id="logModalTitle">Task log</h2>
      <div id="logContent" aria-live="polite"></div>
      <button id="logCloseBtn" type="button" aria-label="Close task log" onclick="closeLogModal()">Close</button>
    </div>
  </div>

  <div id="planModal" style="display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.8); z-index: 1000; align-items: center; justify-content: center;">
    <div style="background: #18181b; border: 1px solid #3f3f46; border-radius: 12px; width: 90%; max-width: 600px; max-height: 85vh; overflow-y: auto; padding: 20px;">
      <div id="planHeader">
        <h2 style="color: #fff; font-size: 16px; margin: 0;">Plan</h2>
        <button id="fullPlanToggle" onclick="toggleFullPlan()">Show full plan</button>
      </div>
      <div id="fullPlanText"></div>
      <div id="taskList"></div>
      <button id="closeBtn" onclick="closePlan()" style="background: #3f3f46; color: #fff; border: none; border-radius: 6px; padding: 9px 12px; cursor: pointer; font-size: 13px; width: 100%;">Close</button>
    </div>
  </div>

  <div id="modal">
    <div id="modalContent">
      <h2>Save App</h2>
      <input id="modalInput" type="text" placeholder="App name..." onkeypress="if(event.key==='Enter')confirmSave()" />
      <label style="display:flex;align-items:center;gap:6px;font-size:12px;color:#a1a1aa;margin-bottom:12px;cursor:pointer;">
        <input type="checkbox" id="overwriteCheck" style="width:auto;flex:none;" /> Overwrite if exists
      </label>
      <div id="modalBtns">
        <button id="saveConfirm" onclick="confirmSave()">Save</button>
        <button id="cancelModal" onclick="closeSaveModal()">Cancel</button>
      </div>
    </div>
  </div>

  <iframe id="preview" src="" title="Generated app"></iframe>

  <script>
    const appUrl = `${location.protocol}//${location.hostname}:5773`;
    document.getElementById('preview').src = appUrl;

    // Restore processing state from localStorage
    function restoreProcessingState() {
      const processingMsg = localStorage.getItem('processingMsg');
      if (processingMsg) {
        document.getElementById('processing').textContent = processingMsg;
        document.getElementById('processing').classList.add('active');
      }
    }

    function setProcessing(msg) {
      localStorage.setItem('processingMsg', msg);
      document.getElementById('processing').textContent = msg;
      document.getElementById('processing').classList.add('active');
    }

    function clearProcessing() {
      localStorage.removeItem('processingMsg');
      document.getElementById('processing').classList.remove('active');
    }

    restoreProcessingState();

    function renderPlannerProvider(provider) {
      const roles = provider && provider.roles;
      if (roles && roles.planner && roles.coder) {
        const part = (r) => `${r.label} ${r.model}`;
        const prefix = roles.local_only ? 'Local-only: ' : '';
        document.getElementById('providerStatus').textContent =
          `${prefix}Planner: ${part(roles.planner)} | Coder: ${part(roles.coder)}`;
        return;
      }
      if (!provider || !provider.label || !provider.endpoint) return;
      document.getElementById('providerStatus').textContent = `Planner: ${provider.label} — ${provider.endpoint}`;
    }
    function jobProvider(job) {
      return job.roles ? { ...(job.provider || {}), roles: job.roles } : job.provider;
    }
    function showPlannerConfigurationError() {
      document.getElementById('providerStatus').textContent = 'Planner/coder configuration error — check provider settings';
    }
    (async function loadPlannerProvider() {
      try {
        const res = await fetch('/planner-provider');
        const data = await res.json();
        if (!res.ok) {
          showPlannerConfigurationError();
          return;
        }
        renderPlannerProvider(data);
      } catch (e) {
        document.getElementById('providerStatus').textContent = 'Planner/coder unavailable — controller could not report providers';
      }
    })();

    let isExecuting = false;
    let pollTimer = null;

    function setExecuting(val) {
      isExecuting = val;
      document.getElementById('currentPlanBtn').style.display = val ? 'block' : 'none';
      document.getElementById('loadBtn').disabled = val;
      document.getElementById('newBtn').disabled = val;
      document.getElementById('loadBtn').style.opacity = val ? '0.4' : '1';
      document.getElementById('newBtn').style.opacity = val ? '0.4' : '1';
    }

    async function showActivePlan() {
      try {
        const res = await fetch('/job/active');
        if (!res.ok) return;
        const job = await res.json();
        if (!job) { alert('No active plan running.'); return; }
        renderPlannerProvider(jobProvider(job));
        document.getElementById('fullPlanText').textContent = job.plan || '';
        renderTaskList(job.tasks);
        updateTaskList(job);
        document.getElementById('planModal').style.display = 'flex';
        if (job.status === 'queued' || job.status === 'running') {
          document.getElementById('closeBtn').textContent = 'Running... (close anyway)';
          startPolling(job.job_id);
        }
      } catch(e) { alert('Could not fetch active plan.'); }
    }

    // On load: check server for any active job (works across devices)
    (async function reconnect() {
      try {
        const res = await fetch('/job/active');
        if (!res.ok) return;
        const job = await res.json();
        if (!job) return;
        renderPlannerProvider(jobProvider(job));
        if (job.status === 'queued' || job.status === 'running') {
          localStorage.setItem('activeJobId', job.job_id);
          setExecuting(true);
          setProcessing('Plan running on server...');
        }
      } catch(e) {}
    })();

    const AUTO_START_SECONDS = 5;
    let countdownTimer = null;

    function escapeHtml(text) {
      return String(text).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    function cancelCountdown(message) {
      if (!countdownTimer) return false;
      clearInterval(countdownTimer);
      countdownTimer = null;
      const btn = document.getElementById('planBtn');
      btn.textContent = 'Plan';
      document.getElementById('closeBtn').textContent = 'Close';
      clearProcessing();
      if (message) {
        const status = document.getElementById('status');
        status.textContent = message;
        status.className = '';
      }
      return true;
    }

    async function executePlan(jobId) {
      const status = document.getElementById('status');
      try {
        const res = await fetch(`/job/${jobId}/execute`, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
          document.getElementById('closeBtn').textContent = 'Running... (close anyway)';
          status.textContent = 'Executing tasks...';
          status.className = '';
          setExecuting(true);
          setProcessing('Executing tasks...');
          startPolling(jobId);
        } else {
          status.textContent = data.detail || 'Could not start the plan';
          status.className = 'err';
          clearProcessing();
        }
      } catch (e) {
        status.textContent = 'Network error';
        status.className = 'err';
        clearProcessing();
      }
    }

    function startCountdown(jobId) {
      let left = AUTO_START_SECONDS;
      const btn = document.getElementById('planBtn');
      const show = () => {
        btn.textContent = `Starting in ${left}s... click to cancel`;
        document.getElementById('status').textContent = `Plan ready. Starting in ${left}s. Click Plan or close this window to cancel.`;
      };
      document.getElementById('closeBtn').textContent = 'Close (cancels auto-start)';
      setProcessing('Plan ready. Starting soon...');
      show();
      countdownTimer = setInterval(() => {
        left -= 1;
        if (left > 0) { show(); return; }
        clearInterval(countdownTimer);
        countdownTimer = null;
        btn.textContent = 'Plan';
        executePlan(jobId);
      }, 1000);
    }

    async function plan() {
      if (cancelCountdown('Auto-start cancelled. Press Continue plan to run this plan.')) return;
      const prompt = document.getElementById('prompt').value.trim();
      if (!prompt) return;
      setProcessing('Planning...');
      const status = document.getElementById('status');
      status.textContent = 'Planning...';
      status.className = '';

      try {
        const res = await fetch('/plan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt })
        });
        const data = await res.json();
        if (res.ok) {
          renderPlannerProvider(jobProvider(data));
          document.getElementById('fullPlanText').textContent = data.plan;
          renderTaskList(data.tasks || []);
          document.getElementById('planModal').style.display = 'flex';
          if ((data.tasks || []).length > 0) {
            localStorage.setItem('activeJobId', data.job_id);
            startCountdown(data.job_id);
          } else {
            status.textContent = 'Plan has no tasks to run';
            status.className = 'err';
            clearProcessing();
          }
        } else {
          status.textContent = data.detail || 'Planning failed';
          status.className = 'err';
          clearProcessing();
        }
      } catch (e) {
        status.textContent = 'Network error';
        status.className = 'err';
        clearProcessing();
      }
    }

    function renderTaskList(tasks) {
      document.getElementById('taskList').innerHTML = tasks.map((task, i) => `
        <div class="taskItem task-pending" id="task-${i}">
          <div class="taskHeader" onclick="toggleTaskLog(${i})">
            <span class="taskIcon" id="taskIcon-${i}">○</span>
            <span class="taskLabel" id="taskLabel-${i}">${i+1}/${tasks.length} &nbsp;${escapeHtml(task)}</span>
            <span class="taskMeta" id="taskMeta-${i}"></span>
            <span class="taskChevron" id="taskChevron-${i}">▶</span>
          </div>
          <div class="taskLog" id="taskLog-${i}"></div>
        </div>
      `).join('');
    }

    function updateTaskList(job) {
      const icons = { pending: '○', running: '⟳', done: '✓', failed: '✗' };
      renderPlannerProvider(jobProvider(job));
      job.tasks.forEach((task, i) => {
        const taskEl = document.getElementById(`task-${i}`);
        if (!taskEl) return;
        const s = job.task_statuses[i];
        taskEl.className = `taskItem task-${s}`;
        document.getElementById(`taskIcon-${i}`).textContent = icons[s] || '○';
        const taskError = (job.task_errors || [])[i];
        const logText = [job.task_logs[i], taskError].filter(Boolean).join('\\n\\n');
        if (logText) document.getElementById(`taskLog-${i}`).textContent = logText;
        if (s === 'failed' && taskError) {
          document.getElementById(`taskLog-${i}`).style.display = 'block';
          document.getElementById(`taskChevron-${i}`).textContent = '▼';
        }
        if (job.task_costs[i]) document.getElementById(`taskMeta-${i}`).textContent = job.task_costs[i];
      });
      const status = document.getElementById('status');
      if (job.status === 'queued') {
        status.textContent = 'Queued...';
      } else if (job.status === 'running' && job.current_task >= 0) {
        status.textContent = `Task ${job.current_task + 1}/${job.tasks.length}...`;
      }
    }

    function startPolling(jobId) {
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = setInterval(async () => {
        try {
          const res = await fetch(`/job/${jobId}`);
          if (!res.ok) return;
          const job = await res.json();
          updateTaskList(job);
          if (job.status === 'done') {
            clearInterval(pollTimer);
            pollTimer = null;
            setExecuting(false);
            localStorage.removeItem('activeJobId');
            document.getElementById('closeBtn').textContent = 'Close';
            document.getElementById('status').textContent = 'Done — app updated';
            document.getElementById('status').className = 'ok';
            document.getElementById('prompt').value = '';
            clearProcessing();
            reloadPreview();
            setTimeout(() => closePlan(), 10000);
          } else if (job.status === 'failed') {
            clearInterval(pollTimer);
            pollTimer = null;
            setExecuting(false);
            localStorage.removeItem('activeJobId');
            document.getElementById('closeBtn').textContent = 'Close';
            const failure = job.error || 'Task failed';
            document.getElementById('status').textContent = failure.slice(0, 300);
            document.getElementById('status').className = 'err';
            document.getElementById('log').textContent = failure;
            clearProcessing();
          }
        } catch(e) { /* network blip, keep polling */ }
      }, 2000);
    }

    function reloadPreview() {
      const iframe = document.getElementById('preview');
      iframe.src = `${appUrl}?t=${Date.now()}`;
    }

    function toggleTaskLog(i) {
      const log = document.getElementById(`taskLog-${i}`);
      const chevron = document.getElementById(`taskChevron-${i}`);
      const visible = log.style.display === 'block';
      log.style.display = visible ? 'none' : 'block';
      chevron.textContent = visible ? '▶' : '▼';
    }

    function toggleFullPlan() {
      const el = document.getElementById('fullPlanText');
      const btn = document.getElementById('fullPlanToggle');
      const visible = el.style.display === 'block';
      el.style.display = visible ? 'none' : 'block';
      btn.textContent = visible ? 'Show full plan' : 'Hide full plan';
    }

    function closePlan() {
      cancelCountdown('Auto-start cancelled. Press Continue plan to run this plan.');
      if (isExecuting) {
        if (!confirm('Tasks are still running on the server. Close this panel? Tasks will continue in the background.')) return;
      }
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
      document.getElementById('planModal').style.display = 'none';
      document.getElementById('closeBtn').textContent = 'Close';
    }

    let helpModalTrigger = null;
    let logModalTrigger = null;

    function openHelpModal() {
      helpModalTrigger = document.activeElement;
      document.getElementById('helpModal').classList.add('open');
      document.getElementById('helpCloseBtn').focus();
    }

    function closeHelpModal() {
      document.getElementById('helpModal').classList.remove('open');
      if (helpModalTrigger && document.contains(helpModalTrigger)) helpModalTrigger.focus();
      helpModalTrigger = null;
    }

    function openLogModal() {
      logModalTrigger = document.activeElement;
      document.getElementById('logContent').textContent = document.getElementById('log').textContent || 'No log output yet.';
      document.getElementById('logModal').classList.add('open');
      document.getElementById('logCloseBtn').focus();
    }

    function closeLogModal() {
      document.getElementById('logModal').classList.remove('open');
      if (logModalTrigger && document.contains(logModalTrigger)) logModalTrigger.focus();
      logModalTrigger = null;
    }

    function getModalFocusableElements(modal) {
      return [...modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')]
        .filter(element => !element.disabled && element.offsetParent !== null);
    }

    document.addEventListener('keydown', (event) => {
      const openModal = [
        document.getElementById('helpModal'),
        document.getElementById('logModal'),
      ].find(modal => modal.classList.contains('open'));
      if (!openModal) return;

      if (event.key === 'Escape') {
        if (openModal.id === 'helpModal') closeHelpModal();
        else closeLogModal();
        return;
      }

      if (event.key !== 'Tab') return;
      const focusable = getModalFocusableElements(openModal);
      if (!focusable.length) {
        event.preventDefault();
        openModal.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || !openModal.contains(document.activeElement))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !openModal.contains(document.activeElement))) {
        event.preventDefault();
        first.focus();
      }
    });

    function openSaveModal() {
      document.getElementById('modal').classList.add('open');
      document.getElementById('modalInput').focus();
    }

    function closeSaveModal() {
      document.getElementById('modal').classList.remove('open');
      document.getElementById('modalInput').value = '';
      document.getElementById('overwriteCheck').checked = false;
    }

    async function confirmSave() {
      const name = document.getElementById('modalInput').value.trim();
      if (!name) return;
      const overwrite = document.getElementById('overwriteCheck').checked;
      closeSaveModal();
      const status = document.getElementById('status');
      status.textContent = 'Saving...';
      status.className = '';
      try {
        const res = await fetch('/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, overwrite })
        });
        const data = await res.json();
        if (res.ok) {
          status.textContent = `Saved: "${name}" ✓`;
          status.className = 'ok';
        } else {
          status.textContent = data.detail || 'Save failed';
          status.className = 'err';
        }
      } catch (e) {
        status.textContent = 'Network error';
        status.className = 'err';
      }
    }

    async function newApp() {
      const status = document.getElementById('status');
      status.textContent = 'Creating new app...';
      status.className = '';
      try {
        const res = await fetch('/new', { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
          status.textContent = 'New app ready';
          status.className = 'ok';
          document.getElementById('log').textContent = '';
          setTimeout(() => {
            const iframe = document.getElementById('preview');
            iframe.src = `${appUrl}?t=${Date.now()}`;
          }, 500);
        } else {
          status.textContent = data.detail || 'New app failed';
          status.className = 'err';
        }
      } catch (e) {
        status.textContent = 'Network error';
        status.className = 'err';
      }
    }

    async function continuePlan() {
      cancelCountdown();
      const status = document.getElementById('status');
      status.textContent = 'Continuing plan...';
      status.className = '';
      document.getElementById('log').textContent = '';
      try {
        const res = await fetch('/continue', { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
          localStorage.setItem('activeJobId', data.job_id);
          renderPlannerProvider(jobProvider(data));
          document.getElementById('fullPlanText').textContent = data.plan || '';
          renderTaskList(data.tasks);
          updateTaskList(data);
          document.getElementById('planModal').style.display = 'flex';
          document.getElementById('closeBtn').textContent = 'Running... (close anyway)';
          status.textContent = 'Continuing plan...';
          setExecuting(true);
          setProcessing('Executing tasks...');
          startPolling(data.job_id);
        } else {
          status.textContent = data.detail || 'Could not continue the plan';
          status.className = 'err';
          document.getElementById('log').textContent = data.detail || '';
        }
      } catch (e) {
        status.textContent = 'Network error';
        status.className = 'err';
      }
    }

    async function openLoadModal() {
      const appsList = document.getElementById('appsList');
      appsList.innerHTML = '<p style="color: #a1a1aa; font-size: 12px;">Loading...</p>';
      document.getElementById('loadModal').classList.add('open');
      try {
        const res = await fetch('/list-apps');
        const data = await res.json();
        if (res.ok && data.apps.length > 0) {
          appsList.innerHTML = data.apps.map(app => `
            <div class="appItem" onclick="loadApp('${app.name}')">
              <div class="appItem-name">${app.name}</div>
              <div class="appItem-info">${app.has_history ? '✓ has history' : 'no history'}</div>
            </div>
          `).join('');
        } else {
          appsList.innerHTML = '<p style="color: #a1a1aa;">No saved apps yet</p>';
        }
      } catch (e) {
        appsList.innerHTML = '<p style="color: #f87171;">Failed to load apps</p>';
      }
    }

    function closeLoadModal() {
      document.getElementById('loadModal').classList.remove('open');
    }

    async function loadApp(name) {
      const status = document.getElementById('status');
      status.textContent = `Loading "${name}"...`;
      status.className = '';
      closeLoadModal();
      try {
        const res = await fetch('/load-app', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name })
        });
        const data = await res.json();
        if (res.ok) {
          status.textContent = `Loaded: "${name}" ✓`;
          status.className = 'ok';
        } else {
          status.textContent = data.detail || 'Load failed';
          status.className = 'err';
        }
      } catch (e) {
        status.textContent = 'Network error';
        status.className = 'err';
      }
    }

  </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def phone_ui(request: Request):
    name = "Local session" if LOCAL_AUTH else get_session_name(request)
    return PHONE_UI.replace("{{USER_NAME}}", name).replace(
        "{{LOGOUT_VISIBILITY}}", "hidden" if LOCAL_AUTH else ""
    )


@app.get("/auth/login")
def auth_login(request: Request):
    redirect_uri = str(request.base_url).rstrip("/") + "/auth/callback"
    params = "&".join([
        f"client_id={GOOGLE_CLIENT_ID}",
        f"redirect_uri={redirect_uri}",
        "response_type=code",
        "scope=openid%20email%20profile",
        "access_type=offline",
        "prompt=select_account",
    ])
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{params}")


@app.get("/auth/callback")
async def auth_callback(code: str, request: Request):
    redirect_uri = str(request.base_url).rstrip("/") + "/auth/callback"
    async with httpx.AsyncClient() as client:
        token_res = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        tokens = token_res.json()
        if "access_token" not in tokens:
            raise HTTPException(status_code=400, detail="OAuth token exchange failed")

        userinfo_res = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        userinfo = userinfo_res.json()

    email = userinfo.get("email", "")
    if userinfo.get("email_verified") is not True or email not in ALLOWED_EMAILS:
        raise HTTPException(status_code=403, detail=f"Access denied for {email}")

    session_token = jwt.encode({
        "email": email,
        "name": userinfo.get("name", email),
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
    }, SESSION_SECRET, algorithm="HS256")

    response = RedirectResponse(url="/")
    response.set_cookie(
        SESSION_COOKIE, session_token,
        httponly=True, samesite="lax",
        max_age=30 * 24 * 3600,
    )
    return response


@app.get("/auth/logout")
def auth_logout():
    response = RedirectResponse(url="/auth/login")
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/status")
def status():
    return {"status": "running"}


@app.get("/check-api")
def check_api():
    api_key = os.getenv("OPENAI_API_KEY")
    return {"has_api_key": bool(api_key)}


@app.post("/save")
def save_app(req: SaveRequest):
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="App name required")

    name = req.name.strip().replace(" ", "-").lower()[:50]
    save_path = SAVED_APPS / name

    if save_path.exists() and not req.overwrite:
        raise HTTPException(status_code=409, detail=f"App '{name}' already exists. Save with overwrite=true to replace it.")

    SAVED_APPS.mkdir(parents=True, exist_ok=True)

    try:
        app_root = REPO_ROOT / "generated-app"

        # Ensure git history exists before saving
        git_dir = app_root / ".git"
        if not git_dir.exists():
            subprocess.run(["git", "init"], cwd=str(app_root), capture_output=True)
            subprocess.run(["git", "add", "."], cwd=str(app_root), capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "initial commit"],
                cwd=str(app_root),
                capture_output=True,
            )

        if save_path.exists():
            shutil.rmtree(save_path)

        # Copy entire generated-app (includes .git for history)
        shutil.copytree(app_root, save_path)
        return {
            "status": "ok",
            "message": f"App saved as '{name}'",
            "path": str(save_path),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Save failed: {str(e)}")


def _planner_user_msg(prompt: str) -> str:
    """Build the planner user message including current app code for context."""
    msg = prompt
    # Attach current src files so planner knows what already exists
    src_snippets = []
    binary_exts = {'.png','.jpg','.jpeg','.gif','.ico','.svg','.woff','.woff2','.ttf','.eot','.map','.lock'}
    for f in sorted(APP_SRC.rglob("*")):
        if f.is_file() and f.suffix not in binary_exts:
            try:
                content = f.read_text(errors='ignore')
                if len(content) > 2000:
                    content = content[:2000] + "\n... (truncated)"
                src_snippets.append(f"### {f.relative_to(REPO_ROOT)}\n```\n{content}\n```")
            except Exception:
                pass
    if src_snippets:
        msg += "\n\n---\nCurrent app code for context:\n\n" + "\n\n".join(src_snippets)
    return msg


@app.get("/planner-provider")
def get_planner_provider():
    try:
        planner, coder = resolve_roles()
        return {**planner_provider_info(planner), "roles": roles_info(planner, coder)}
    except PlannerConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/plan")
async def plan(req: PlanRequest):
    """Generate a plan and store it as a planned job. Execution starts separately."""
    try:
        provider, coder = resolve_roles()
    except PlannerConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    client = create_planner_client(provider)

    try:
        response = client.chat.completions.create(
            model=provider.model,
            messages=[
                {
                    "role": "system",
                    "content": """You are a software architect planning tasks for a pure React + Vite SPA.

ARCHITECTURE CONSTRAINTS (never violate these):
- Pure React frontend only. No backend server (no express, fastapi, next.js, etc.)
- All code lives in src/ as JSX/JS files
- No public/ folder, no JSON config files, no static assets unless creating them in src/
- Tailwind CSS via CDN in index.html — use className with Tailwind classes
- All data must be hardcoded in JS/JSX or fetched from external public APIs
- Tasks are executed by aider which reads the provided src/ files — keep tasks self-contained

OUTPUT FORMAT (use only these sections, never repeat the plan or add other sections, no code):

FOR SIMPLE REQUESTS (rename, small fix, minor change), output only:
## Tasks
1) Task name
2) Task name

FOR COMPLEX REQUESTS (new feature, refactor, system redesign), output only:
## 1) Requirements
...
## 2) Architecture
...
## 3) Tasks
1) Task name
2) Task name
## 4) Acceptance Criteria
...

List each task exactly once, in the Tasks section, as "1) Task name", "2) Task name", etc.
Do not include code snippets or a second copy of the task list. Keep tasks concrete and self-contained. Never plan tasks that require files outside src/.""",
                },
                {"role": "user", "content": _planner_user_msg(req.prompt)},
            ],
            temperature=0.7,
            max_completion_tokens=2000,
        )

        plan_text = response.choices[0].message.content
        tasks = parse_tasks(plan_text)

        job_id = str(uuid.uuid4())
        jobs[job_id] = {
            "id": job_id,
            "version": 1,
            "status": "planned",
            "prompt": req.prompt,
            "plan": plan_text,
            "tasks": tasks,
            "current_task": -1,
            "task_statuses": ["pending"] * len(tasks),
            "task_logs": [""] * len(tasks),
            "task_costs": [""] * len(tasks),
            "task_errors": [""] * len(tasks),
            "created_at": datetime.now().isoformat(),
            "error": None,
            "engine": resolve_coder_engine(),
            "provider": planner_provider_info(provider),
            "roles": roles_info(provider, coder),
        }
        save_job(job_id)

        return {
            "status": "planned",
            "job_id": job_id,
            "plan": plan_text,
            "tasks": tasks,
            "task_count": len(tasks),
            "provider": planner_provider_info(provider),
            "roles": roles_info(provider, coder),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Planning failed: {str(e)}")


def _busy() -> bool:
    return any(j.get('status') in ('queued', 'running') for j in jobs.values())


@app.get("/job/active")
def get_active_job():
    if active_job_id and active_job_id in jobs:
        return {**jobs[active_job_id], "job_id": active_job_id}
    # Also check for queued jobs
    for jid, job in jobs.items():
        if job['status'] in ('queued', 'running'):
            return {**job, "job_id": jid}
    return None


@app.get("/job/{job_id}")
def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return {**jobs[job_id], "job_id": job_id}


async def _enqueue_job(job_id: str) -> dict:
    """Queue a planned or failed job. Failed tasks restart; done tasks stay done."""
    job = jobs[job_id]
    if _busy():
        raise HTTPException(status_code=409, detail="A plan is already running")
    if job['status'] not in ('planned', 'failed') or all(s == 'done' for s in job['task_statuses']):
        raise HTTPException(status_code=409, detail=f"Plan is {job['status']} and cannot be started")
    if not job['tasks']:
        raise HTTPException(status_code=409, detail="This plan has no tasks to run")
    try:
        resolve_roles()
        engine = resolve_coder_engine()
        resolve_coder_timeout()
        resolve_coder_edit_format()
        if engine == "opencode":
            raise CoderEngineNotImplemented(OPENCODE_NOT_IMPLEMENTED)
    except CoderEngineNotImplemented as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    except PlannerConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    job.setdefault('task_errors', [""] * len(job['tasks']))
    for i, status in enumerate(job['task_statuses']):
        if status != 'done':
            job['task_statuses'][i] = 'pending'
            job['task_errors'][i] = ""
    job['status'] = 'queued'
    job['error'] = None
    job['engine'] = engine
    save_job(job_id)
    await job_queue.put(job_id)
    return {**job, "job_id": job_id}


@app.post("/job/{job_id}/execute")
async def execute_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return await _enqueue_job(job_id)


@app.post("/continue")
async def continue_plan():
    """Resume the most recent stored plan from its next pending or failed task."""
    if _busy():
        raise HTTPException(status_code=409, detail="A plan is already running")
    resumable = [
        (j.get('created_at', ''), jid) for jid, j in jobs.items()
        if j.get('status') in ('planned', 'failed')
        and j.get('tasks') and any(s != 'done' for s in j['task_statuses'])
    ]
    if not resumable:
        if any(j.get('tasks') for j in jobs.values()):
            raise HTTPException(status_code=404, detail="The latest plan is already complete. Press Plan to create a new one.")
        raise HTTPException(status_code=404, detail="No stored plan to continue. Press Plan to create one.")
    return await _enqueue_job(max(resumable)[1])


@app.get("/list-apps")
def list_apps():
    try:
        if not SAVED_APPS.exists():
            return {"status": "ok", "apps": []}
        apps = []
        for app_dir in SAVED_APPS.iterdir():
            if app_dir.is_dir():
                git_dir = app_dir / ".git"
                apps.append({
                    "name": app_dir.name,
                    "has_history": git_dir.exists(),
                })
        return {"status": "ok", "apps": sorted(apps, key=lambda x: x["name"])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list apps: {str(e)}")


@app.post("/load-app")
def load_app(req: LoadAppRequest):
    app_path = SAVED_APPS / req.name
    if not app_path.exists():
        raise HTTPException(status_code=404, detail=f"App '{req.name}' not found")
    try:
        gen_app_path = REPO_ROOT / "generated-app"

        # Replace src contents without deleting the dir — keeps Vite's watcher alive
        src_dest = gen_app_path / "src"
        src_dest.mkdir(parents=True, exist_ok=True)
        for item in src_dest.iterdir():
            item.unlink() if item.is_file() else shutil.rmtree(item)
        saved_src = app_path / "src"
        if saved_src.exists():
            for item in saved_src.iterdir():
                dest = src_dest / item.name
                shutil.copy2(item, dest) if item.is_file() else shutil.copytree(item, dest)

        # Update top-level config files (never overwrite vite.config.js — it has server settings)
        for config_file in ["package.json", "index.html"]:
            saved_file = app_path / config_file
            if saved_file.exists():
                shutil.copy2(saved_file, gen_app_path / config_file)

        # Ensure React import exists in JSX files
        for jsx_file in ["App.jsx", "main.jsx"]:
            jsx_path = src_dest / jsx_file
            if jsx_path.exists():
                content = jsx_path.read_text()
                if 'import React' not in content:
                    lines = content.split('\n')
                    lines.insert(0, 'import React from "react";')
                    jsx_path.write_text('\n'.join(lines))

        # Install deps in case package.json changed
        subprocess.run(
            ["npm", "install"],
            cwd=str(gen_app_path),
            capture_output=True,
            timeout=60,
        )

        return {"status": "ok", "message": f"Loaded app '{req.name}'"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Load failed: {str(e)}")


@app.post("/revert")
def revert(count: int = 1):
    """Revert to a previous commit in generated-app."""
    app_root = REPO_ROOT / "generated-app"
    try:
        # Get the commit hash to revert to
        result = subprocess.run(
            ["git", "log", "--oneline", f"-{count + 1}"],
            cwd=str(app_root),
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise HTTPException(status_code=400, detail="Not enough commits to revert")

        lines = result.stdout.strip().split("\n")
        if len(lines) < count + 1:
            raise HTTPException(status_code=400, detail=f"Only {len(lines) - 1} commits available")

        target_commit = lines[count].split()[0]

        # Reset to that commit
        result = subprocess.run(
            ["git", "reset", "--hard", target_commit],
            cwd=str(app_root),
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise HTTPException(status_code=502, detail="Failed to revert")

        return {
            "status": "ok",
            "message": f"Reverted {count} version(s)",
            "commit": target_commit,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Revert failed: {str(e)}")


@app.post("/new")
def new_app():
    try:
        # Remove all src files
        for f in APP_SRC.iterdir():
            if f.is_file():
                f.unlink()
            elif f.is_dir():
                shutil.rmtree(f)

        # Create fresh main.jsx
        main_jsx = APP_SRC / "main.jsx"
        main_jsx.write_text("""import React, { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
""")

        # Create blank App.jsx
        app_jsx = APP_SRC / "App.jsx"
        app_jsx.write_text("""import React from "react";

export default function App() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">New App</h1>
        <p className="text-gray-600">Ready to build...</p>
      </div>
    </div>
  );
}
""")

        # Ensure npm dependencies are installed
        subprocess.run(
            ["npm", "install"],
            cwd=str(REPO_ROOT / "generated-app"),
            capture_output=True,
        )

        return {
            "status": "ok",
            "message": "Fresh app created — ready to generate",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"New app failed: {str(e)}")
