import asyncio
import ipaddress
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
APP_SRC = REPO_ROOT / "generated-app" / "src"
SAVED_APPS = REPO_ROOT / "saved-apps"

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


class GenerateRequest(BaseModel):
    prompt: str


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

    @property
    def planner_base_url(self) -> str | None:
        if self.name == "ollama":
            return f"{self.ollama_api_base}/v1"
        return None

    @property
    def aider_model(self) -> str:
        if self.name == "ollama":
            return f"ollama_chat/{self.model}"
        return self.model


_CLOUD_PROVIDER_ENV_VARS = (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_API_BASE",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_BASE_URL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL",
    "GOOGLE_API_KEY",
    "GOOGLE_BASE_URL",
    "GOOGLE_API_BASE",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GEMINI_API_KEY",
    "GEMINI_BASE_URL",
    "GEMINI_API_BASE",
)


def _normalize_ollama_api_base(value: str) -> str:
    base = value.strip().rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3].rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment:
        raise PlannerConfigurationError(
            "OLLAMA_API_BASE must be an HTTP(S) URL without a query or fragment"
        )
    if parsed.username is not None or parsed.password is not None:
        raise PlannerConfigurationError("OLLAMA_API_BASE must not include URL credentials")
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
            "OLLAMA_API_BASE must resolve to localhost, 127.0.0.1, or ::1 in local-only mode"
        )
    return base


def resolve_planner_provider(env: dict[str, str] | None = None) -> PlannerProvider:
    """Resolve and validate the explicitly selected planner provider."""
    values = os.environ if env is None else env
    provider_name = values.get("PLANNER_PROVIDER", "openai").strip().lower() or "openai"
    if provider_name not in {"openai", "ollama"}:
        raise PlannerConfigurationError(
            "PLANNER_PROVIDER must be either 'openai' or 'ollama'"
        )

    if provider_name == "openai":
        api_key = values.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise PlannerConfigurationError("OPENAI_API_KEY is required when PLANNER_PROVIDER=openai")
        model = values.get("OPENAI_MODEL", "gpt-5.4-mini").strip() or "gpt-5.4-mini"
        return PlannerProvider(name="openai", model=model, api_key=api_key)

    model = values.get("OLLAMA_MODEL", "").strip()
    if not model:
        raise PlannerConfigurationError("OLLAMA_MODEL is required when PLANNER_PROVIDER=ollama")
    api_base = _normalize_ollama_api_base(
        values.get("OLLAMA_API_BASE", "http://127.0.0.1:11434")
    )
    return PlannerProvider(name="ollama", model=model, ollama_api_base=api_base)


def create_planner_client(provider: PlannerProvider):
    """Create the OpenAI-compatible client for the selected provider."""
    from openai import OpenAI

    if provider.name == "ollama":
        return OpenAI(api_key="ollama", base_url=provider.planner_base_url)
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
    return {
        "name": "openai",
        "label": "OpenAI",
        "model": provider.model,
        "endpoint": "OpenAI-managed endpoint",
    }


def provider_environment(provider: PlannerProvider, base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Build subprocess environment without cloud credentials in Ollama mode."""
    environment = dict(os.environ if base_env is None else base_env)
    if provider.name == "ollama":
        for variable in _CLOUD_PROVIDER_ENV_VARS:
            environment.pop(variable, None)
        environment["OLLAMA_API_BASE"] = provider.ollama_api_base
    else:
        environment["OPENAI_API_KEY"] = provider.api_key
    return environment


def build_aider_command(provider: PlannerProvider, task_prompt: str, files: list[str]) -> list[str]:
    """Build the queued Aider invocation for the selected provider."""
    return [
        "aider", "--yes-always", "--no-pretty", "--no-suggest-shell-commands",
        "--model", provider.aider_model, "--message", task_prompt, *files,
    ]


def extract_cost(log: str) -> str:
    m = re.search(r'Cost:\s*(\$[\d.]+)\s*message', log)
    return m.group(1) if m else ''


async def job_worker():
    global active_job_id
    while True:
        job_id = await job_queue.get()
        active_job_id = job_id
        job = jobs[job_id]
        job['status'] = 'running'
        try:
            provider = resolve_planner_provider()
        except PlannerConfigurationError as exc:
            job['status'] = 'failed'
            job['error'] = str(exc)
            active_job_id = None
            job_queue.task_done()
            continue

        for i, task_desc in enumerate(job['tasks']):
            job['current_task'] = i
            job['task_statuses'][i] = 'running'

            gen_app = REPO_ROOT / "generated-app"
            # Pass all non-binary src files so aider sees the full picture
            binary_exts = {'.png','.jpg','.jpeg','.gif','.ico','.svg','.woff','.woff2','.ttf','.eot','.map','.lock'}
            files = [
                str(f.relative_to(REPO_ROOT))
                for f in APP_SRC.rglob("*")
                if f.is_file() and f.suffix not in binary_exts
            ]
            # Include top-level config files for full project context
            for extra in ["vite.config.js", "index.html", "package.json"]:
                p = gen_app / extra
                if p.exists():
                    files.append(str(p.relative_to(REPO_ROOT)))

            # Build prompt with full context of what's been done so far
            completed = [
                f"  - Task {j+1} (done): {job['tasks'][j]}"
                for j in range(i) if job['task_statuses'][j] == 'done'
            ]
            task_prompt = (
                f"Overall goal: {job['prompt']}\n\n"
                + "Architecture: pure React + Vite SPA. No backend server, no express/fastapi, "
                + "no public/ folder unless you create it. All logic goes in src/ JSX files. "
                + "Tailwind CSS is loaded via CDN in index.html.\n\n"
                + (f"Tasks already completed:\n" + "\n".join(completed) + "\n\n" if completed else "")
                + f"Now implement Task {i+1}/{len(job['tasks'])}: {task_desc}\n\n"
                + "Do not ask clarifying questions. Do not request additional files. "
                + "Make your best judgment and implement it directly in the files provided."
            )

            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda tp=task_prompt, fl=files: subprocess.run(
                    build_aider_command(provider, tp, fl),
                    cwd=str(REPO_ROOT),
                    env=provider_environment(provider),
                    capture_output=True, text=True, timeout=120,
                    stdin=subprocess.DEVNULL,
                ))
                job['task_logs'][i] = result.stdout[-1000:]
                job['task_costs'][i] = extract_cost(result.stdout)
                if result.returncode == 0:
                    # Validate App.jsx wasn't corrupted
                    app_jsx = APP_SRC / "App.jsx"
                    if app_jsx.exists():
                        content = app_jsx.read_text(errors='ignore')
                        if len(content) < 100 or 'export default' not in content:
                            # Revert to last good commit
                            subprocess.run(
                                ["git", "checkout", "--", "."],
                                cwd=str(REPO_ROOT / "generated-app"),
                                capture_output=True,
                            )
                            job['task_statuses'][i] = 'failed'
                            job['status'] = 'failed'
                            job['error'] = f"Task {i+1} corrupted App.jsx — reverted to last good state"
                            break
                    job['task_statuses'][i] = 'done'
                else:
                    job['task_statuses'][i] = 'failed'
                    job['status'] = 'failed'
                    job['error'] = result.stderr[-500:]
                    break
            except Exception as e:
                job['task_statuses'][i] = 'failed'
                job['status'] = 'failed'
                job['error'] = str(e)
                break
        else:
            job['status'] = 'done'

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
      <button id="planBtn" title="Create a step-by-step plan and run it in the background." onclick="plan()">Plan</button>
      <button id="btn" title="Send the prompt directly to the app generator." onclick="generate()">Generate</button>
      <button id="currentPlanBtn" title="View the plan currently running on the server." onclick="showActivePlan()" style="background:#3f3f46;display:none;">Current Plan</button>
      <button id="helpBtn" title="Learn what each controller action does." aria-label="Open controller help" aria-controls="helpModal" aria-haspopup="dialog" onclick="openHelpModal()">ⓘ</button>
    </div>
    <div id="status"></div>
    <div id="providerStatus">Planner provider: loading...</div>
    <div id="processing"></div>
    <button id="logToggle" title="Open the latest generator output in a larger window." aria-label="Open generator log" aria-controls="logModal" aria-haspopup="dialog" onclick="openLogModal()">▶ log</button>
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
      <p>Describe your app in the prompt, then choose <strong>Plan</strong> to review progress or <strong>Generate</strong> for a direct update. The generated app appears in the preview below.</p>
      <p><strong>Plan</strong> breaks your request into tasks, shows progress, and runs them in the background.</p>
      <p><strong>Generate</strong> sends your request directly to the generator for a quick update.</p>
      <p><strong>Save App</strong> stores the current app. <strong>Load App</strong> restores a saved app.</p>
      <p><strong>New App</strong> clears the current app. Use <strong>⟳</strong> to reload the preview.</p>
      <p><strong>log</strong> opens the latest generator output for troubleshooting.</p>
      <button id="helpCloseBtn" type="button" aria-label="Close controller help" onclick="closeHelpModal()">Close</button>
    </div>
  </div>

  <div id="logModal" role="dialog" aria-modal="true" aria-labelledby="logModalTitle" tabindex="-1" onclick="if(event.target===this)closeLogModal()">
    <div class="infoBox">
      <h2 id="logModalTitle">Generator log</h2>
      <div id="logContent" aria-live="polite"></div>
      <button id="logCloseBtn" type="button" aria-label="Close generator log" onclick="closeLogModal()">Close</button>
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

    (async function loadPlannerProvider() {
      try {
        const res = await fetch('/planner-provider');
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail);
        document.getElementById('providerStatus').textContent = `Planner: ${data.label} — ${data.endpoint}`;
      } catch (e) {
        document.getElementById('providerStatus').textContent = `Planner unavailable: ${e.message}`;
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
        if (job.status === 'queued' || job.status === 'running') {
          localStorage.setItem('activeJobId', job.job_id);
          setExecuting(true);
          setProcessing('Plan running on server...');
        }
      } catch(e) {}
    })();

    async function plan() {
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
          localStorage.setItem('activeJobId', data.job_id);
          document.getElementById('fullPlanText').textContent = data.plan;
          renderTaskList(data.tasks || []);
          document.getElementById('planModal').style.display = 'flex';
          document.getElementById('closeBtn').textContent = 'Running... (close anyway)';
          status.textContent = data.queue_position > 1 ? `Queued (#${data.queue_position})` : 'Executing tasks...';
          setExecuting(true);
          setProcessing('Executing tasks...');
          startPolling(data.job_id);
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
            <span class="taskLabel" id="taskLabel-${i}">${i+1}/${tasks.length} &nbsp;${task}</span>
            <span class="taskMeta" id="taskMeta-${i}"></span>
            <span class="taskChevron" id="taskChevron-${i}">▶</span>
          </div>
          <div class="taskLog" id="taskLog-${i}"></div>
        </div>
      `).join('');
    }

    function updateTaskList(job) {
      const icons = { pending: '○', running: '⟳', done: '✓', failed: '✗' };
      job.tasks.forEach((task, i) => {
        const taskEl = document.getElementById(`task-${i}`);
        if (!taskEl) return;
        const s = job.task_statuses[i];
        taskEl.className = `taskItem task-${s}`;
        document.getElementById(`taskIcon-${i}`).textContent = icons[s] || '○';
        if (job.task_logs[i]) document.getElementById(`taskLog-${i}`).textContent = job.task_logs[i];
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
            document.getElementById('status').textContent = 'Task failed';
            document.getElementById('status').className = 'err';
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

    async function generate() {
      const prompt = document.getElementById('prompt').value.trim();
      if (!prompt) return;
      const btn = document.getElementById('btn');
      const status = document.getElementById('status');
      const log = document.getElementById('log');
      btn.disabled = true;
      btn.textContent = 'Generating...';
      status.textContent = '';
      status.className = '';
      log.textContent = '';
      try {
        const res = await fetch('/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt })
        });
        const data = await res.json();
        if (res.ok) {
          status.textContent = 'Done — app updated';
          status.className = 'ok';
          document.getElementById('prompt').value = '';
          if (data.log) {
            log.textContent = data.log;
          }
        } else {
          status.textContent = data.detail || 'Error';
          status.className = 'err';
          if (data.log) {
            log.textContent = data.log;
          }
        }
      } catch (e) {
        status.textContent = 'Network error';
        status.className = 'err';
      } finally {
        btn.disabled = false;
        btn.textContent = 'Generate';
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


@app.post("/generate")
def generate(req: GenerateRequest):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

    files = [str(f.relative_to(REPO_ROOT)) for f in APP_SRC.rglob("*.jsx")]
    files += [str(f.relative_to(REPO_ROOT)) for f in APP_SRC.rglob("*.js")
              if not f.name.endswith(".min.js")]

    try:
        result = subprocess.run(
            [
                "aider",
                "--yes-always",
                "--no-pretty",
                "--model", "claude-sonnet-4-6",
                "--message", req.prompt,
                *files,
            ],
            cwd=str(REPO_ROOT),
            env={**os.environ, "ANTHROPIC_API_KEY": api_key},
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Aider timed out")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="aider not found — run: pip install aider-chat")

    if result.returncode != 0:
        raise HTTPException(status_code=502, detail=result.stderr[-2000:] or "Aider failed")

    return {"status": "ok", "message": "App updated", "log": result.stdout[-2000:]}


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
        return planner_provider_info(resolve_planner_provider())
    except PlannerConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/plan")
async def plan(req: PlanRequest):
    """Generate a plan and enqueue it as a background job."""
    try:
        provider = resolve_planner_provider()
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

FOR SIMPLE REQUESTS (rename, small fix, minor change):
Output only:
## Tasks
1) Task one
2) Task two

FOR COMPLEX REQUESTS (new feature, refactor, system redesign):
Output full plan:
## 1) Requirements
...
## 2) Architecture
...
## 3) Tasks
1) Task one
2) Task two
...
## 4) Acceptance Criteria
...

Tasks must use format: "1) Task name", "2) Task name", etc.
Keep tasks concrete and self-contained. Never plan tasks that require files outside src/.""",
                },
                {"role": "user", "content": _planner_user_msg(req.prompt)},
            ],
            temperature=0.7,
            max_completion_tokens=2000,
        )

        plan_text = response.choices[0].message.content
        tasks = []
        for line in plan_text.split("\n"):
            match = re.match(r"^\s*\d+[\.\)]\s+(.+)$", line.strip())
            if match:
                tasks.append(match.group(1).strip())

        job_id = str(uuid.uuid4())
        jobs[job_id] = {
            "status": "queued",
            "prompt": req.prompt,
            "plan": plan_text,
            "tasks": tasks,
            "current_task": -1,
            "task_statuses": ["pending"] * len(tasks),
            "task_logs": [""] * len(tasks),
            "task_costs": [""] * len(tasks),
            "created_at": datetime.now().isoformat(),
            "error": None,
            "provider": planner_provider_info(provider),
        }
        await job_queue.put(job_id)

        return {
            "status": "ok",
            "job_id": job_id,
            "plan": plan_text,
            "tasks": tasks,
            "task_count": len(tasks),
            "queue_position": job_queue.qsize(),
            "provider": planner_provider_info(provider),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Planning failed: {str(e)}")


@app.get("/job/active")
def get_active_job():
    if active_job_id and active_job_id in jobs:
        return {**jobs[active_job_id], "job_id": active_job_id}
    # Also check for queued jobs
    for jid, job in jobs.items():
        if job['status'] == 'queued':
            return {**job, "job_id": jid}
    return None


@app.get("/job/{job_id}")
def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


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
