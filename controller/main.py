import asyncio
import os
import pathlib
import re
import shutil
import subprocess
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

load_dotenv()

REPO_ROOT = pathlib.Path(__file__).parent.parent
APP_SRC = REPO_ROOT / "generated-app" / "src"
SAVED_APPS = REPO_ROOT / "saved-apps"

# Auth config
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me-in-production")
ALLOWED_EMAILS = {e.strip() for e in os.getenv("ALLOWED_EMAILS", "").split(",") if e.strip()}
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


class GenerateRequest(BaseModel):
    prompt: str


class SaveRequest(BaseModel):
    name: str


class PlanRequest(BaseModel):
    prompt: str


class LoadAppRequest(BaseModel):
    name: str


def extract_cost(log: str) -> str:
    m = re.search(r'Cost:\s*(\$[\d.]+)\s*message', log)
    return m.group(1) if m else ''


async def job_worker():
    while True:
        job_id = await job_queue.get()
        job = jobs[job_id]
        job['status'] = 'running'
        api_key = os.getenv("OPENAI_API_KEY")

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
                    ["aider", "--yes-always", "--no-pretty", "--no-suggest-shell-commands",
                     "--model", "gpt-5.4-mini", "--message", tp, *fl],
                    cwd=str(REPO_ROOT),
                    env={**os.environ, "OPENAI_API_KEY": api_key},
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

        job_queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global job_queue
    APP_SRC.mkdir(parents=True, exist_ok=True)
    job_queue = asyncio.Queue()
    worker = asyncio.create_task(job_worker())
    yield
    worker.cancel()


app = FastAPI(title="voice-developer controller", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_auth(request: Request, call_next):
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
    #logToggle { background: none; border: none; color: #71717a; cursor: pointer; font-size: 12px; padding: 4px 8px; text-align: left; }
    #log { max-height: 0; overflow: hidden; transition: max-height 0.2s; background: #18181b; border-radius: 8px; padding: 0 12px; font-size: 11px; color: #a1a1aa; font-family: monospace; line-height: 1.4; }
    #log.expanded { max-height: 200px; padding: 8px 12px; overflow-y: auto; }
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
      <button id="planBtn" onclick="plan()">Plan</button>
      <button id="btn" onclick="generate()">Generate</button>
    </div>
    <div id="status"></div>
    <div id="processing"></div>
    <button id="logToggle" onclick="toggleLog()">▶ log</button>
    <div id="log"></div>
    <div id="actions">
      <button id="saveBtn" onclick="openSaveModal()">Save App</button>
      <button id="loadBtn" onclick="openLoadModal()">Load App</button>
      <button id="newBtn" onclick="newApp()">New App</button>
      <button id="refreshBtn" onclick="reloadPreview()">⟳</button>
    </div>
    <div id="userBar">
      <span>{{USER_NAME}}</span>
      <button id="logoutBtn" onclick="window.location='/auth/logout'">logout</button>
    </div>
  </div>

  <div id="loadModal" onclick="if(event.target===this)closeLoadModal()">
    <div id="loadBox">
      <h2>Load App</h2>
      <div id="appsList"></div>
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

    let isExecuting = false;
    let pollTimer = null;

    // Reconnect to in-flight job on page load
    (async function reconnect() {
      const jobId = localStorage.getItem('activeJobId');
      if (!jobId) return;
      try {
        const res = await fetch(`/job/${jobId}`);
        if (!res.ok) { localStorage.removeItem('activeJobId'); return; }
        const job = await res.json();
        if (job.status === 'queued' || job.status === 'running') {
          document.getElementById('fullPlanText').textContent = job.plan || '';
          renderTaskList(job.tasks);
          document.getElementById('planModal').style.display = 'flex';
          document.getElementById('closeBtn').textContent = 'Running... (close anyway)';
          isExecuting = true;
          startPolling(jobId);
        } else {
          localStorage.removeItem('activeJobId');
        }
      } catch(e) { localStorage.removeItem('activeJobId'); }
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
          isExecuting = true;
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
            isExecuting = false;
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
            isExecuting = false;
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
      isExecuting = false;
      document.getElementById('planModal').style.display = 'none';
      document.getElementById('closeBtn').textContent = 'Close';
    }

    function toggleLog() {
      const log = document.getElementById('log');
      const toggle = document.getElementById('logToggle');
      if (log.classList.contains('expanded')) {
        log.classList.remove('expanded');
        toggle.textContent = '▶ log';
      } else {
        log.classList.add('expanded');
        toggle.textContent = '▼ log';
      }
    }

    function openSaveModal() {
      document.getElementById('modal').classList.add('open');
      document.getElementById('modalInput').focus();
    }

    function closeSaveModal() {
      document.getElementById('modal').classList.remove('open');
      document.getElementById('modalInput').value = '';
    }

    async function confirmSave() {
      const name = document.getElementById('modalInput').value.trim();
      if (!name) return;
      closeSaveModal();
      const status = document.getElementById('status');
      status.textContent = 'Saving...';
      status.className = '';
      try {
        const res = await fetch('/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name })
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
          document.getElementById('log').classList.remove('expanded');
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
            log.classList.add('expanded');
            document.getElementById('logToggle').textContent = '▼ log';
          }
        } else {
          status.textContent = data.detail || 'Error';
          status.className = 'err';
          if (data.log) {
            log.textContent = data.log;
            log.classList.add('expanded');
            document.getElementById('logToggle').textContent = '▼ log';
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
    name = get_session_name(request)
    return PHONE_UI.replace("{{USER_NAME}}", name)


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
    if ALLOWED_EMAILS and email not in ALLOWED_EMAILS:
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

    if save_path.exists():
        raise HTTPException(status_code=409, detail=f"App '{name}' already exists")

    SAVED_APPS.mkdir(parents=True, exist_ok=True)

    try:
        app_root = REPO_ROOT / "generated-app"

        # Ensure git history exists before saving
        git_dir = app_root / ".git"
        if not git_dir.exists():
            # Initialize git and commit current state
            subprocess.run(["git", "init"], cwd=str(app_root), capture_output=True)
            subprocess.run(["git", "add", "."], cwd=str(app_root), capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "initial commit"],
                cwd=str(app_root),
                capture_output=True,
            )

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


@app.post("/plan")
async def plan(req: PlanRequest):
    """Generate a plan and enqueue it as a background job."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model="gpt-5.4-mini",
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
        }
        await job_queue.put(job_id)

        return {
            "status": "ok",
            "job_id": job_id,
            "plan": plan_text,
            "tasks": tasks,
            "task_count": len(tasks),
            "queue_position": job_queue.qsize(),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Planning failed: {str(e)}")


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
