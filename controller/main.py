import os
import pathlib
import re
import shutil
import subprocess
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

load_dotenv()

REPO_ROOT = pathlib.Path(__file__).parent.parent
APP_SRC = REPO_ROOT / "generated-app" / "src"
SAVED_APPS = REPO_ROOT / "saved-apps"


class GenerateRequest(BaseModel):
    prompt: str


class SaveRequest(BaseModel):
    name: str


class PlanRequest(BaseModel):
    prompt: str


class ExecuteTaskRequest(BaseModel):
    task_num: int
    task_desc: str
    original_prompt: str


class LoadAppRequest(BaseModel):
    name: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    APP_SRC.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="voice-developer controller", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    #saveBtn, #newBtn, #loadBtn { flex: 1; background: #71717a; color: #fff; font-weight: 600; font-size: 13px; border: none; border-radius: 8px; padding: 8px; cursor: pointer; }
    #saveBtn:hover, #newBtn:hover, #loadBtn:hover { background: #a1a1aa; }
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
    iframe { flex: 1; border: none; background: #fff; }
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
    <button id="logToggle" onclick="toggleLog()">▶ log</button>
    <div id="log"></div>
    <div id="actions">
      <button id="saveBtn" onclick="openSaveModal()">Save App</button>
      <button id="loadBtn" onclick="openLoadModal()">Load App</button>
      <button id="newBtn" onclick="newApp()">New App</button>
    </div>
  </div>

  <div id="loadModal" onclick="if(event.target===this)closeLoadModal()">
    <div id="loadBox">
      <h2>Load App</h2>
      <div id="appsList"></div>
    </div>
  </div>

  <div id="planModal" onclick="if(event.target===this)closePlan()" style="display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.8); z-index: 1000; align-items: center; justify-content: center;">
    <div style="background: #18181b; border: 1px solid #3f3f46; border-radius: 12px; width: 90%; max-width: 700px; max-height: 80vh; overflow-y: auto; padding: 20px;">
      <h2 style="color: #fff; margin: 0 0 12px; font-size: 18px;">Plan</h2>
      <div id="planText" style="font-size: 12px; color: #a1a1aa; line-height: 1.6; margin-bottom: 12px; white-space: pre-wrap;"></div>
      <div id="genStatus" style="font-size: 13px; color: #71717a; margin-top: 12px; font-weight: 500;"></div>
      <div id="genLog" style="font-size: 11px; color: #a1a1aa; font-family: monospace; margin-top: 8px; max-height: 300px; overflow-y: auto; line-height: 1.4; background: #27272a; border-radius: 4px; padding: 8px; border: 1px solid #3f3f46;"></div>
      <button id="closeBtn" onclick="closePlan()" style="margin-top: 12px; background: #3f3f46; color: #fff; border: none; border-radius: 4px; padding: 8px 12px; cursor: pointer; font-size: 12px; width: 100%;">Close</button>
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
    const appUrl = `http://${location.hostname}:5773`;
    document.getElementById('preview').src = appUrl;

    let currentTasks = [];
    let currentTaskIndex = 0;
    let originalPrompt = '';

    async function plan() {
      const prompt = document.getElementById('prompt').value.trim();
      if (!prompt) return;
      originalPrompt = prompt;
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
          currentTasks = data.tasks || [];
          currentTaskIndex = 0;
          document.getElementById('planText').textContent = data.plan;
          document.getElementById('genStatus').innerHTML = `<strong>Plan ready.</strong> Executing ${data.task_count} tasks...`;
          document.getElementById('genLog').textContent = '';
          document.getElementById('planModal').style.display = 'flex';
          status.textContent = 'Executing tasks...';
          status.className = '';
          setTimeout(() => executeNextTask(), 300);
        } else {
          status.textContent = data.detail || 'Planning failed';
          status.className = 'err';
        }
      } catch (e) {
        status.textContent = 'Network error';
        status.className = 'err';
      }
    }

    async function executeNextTask() {
      if (currentTaskIndex >= currentTasks.length) {
        document.getElementById('genStatus').textContent = `✓ All ${currentTasks.length} tasks complete!`;
        document.getElementById('status').textContent = 'Done — app updated';
        document.getElementById('status').className = 'ok';
        document.getElementById('prompt').value = '';
        setTimeout(() => closePlan(), 1500);
        return;
      }

      const taskNum = currentTaskIndex + 1;
      const taskDesc = currentTasks[currentTaskIndex];
      const status = document.getElementById('status');
      const genStatus = document.getElementById('genStatus');
      const genLog = document.getElementById('genLog');

      genStatus.innerHTML = `<strong>Task ${taskNum}/${currentTasks.length}:</strong> ${taskDesc}`;
      status.textContent = `Task ${taskNum}/${currentTasks.length}...`;
      status.className = '';

      try {
        const res = await fetch('/execute-task', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            task_num: taskNum,
            task_desc: taskDesc,
            original_prompt: originalPrompt
          })
        });
        const data = await res.json();
        if (data.log) {
          genLog.textContent += `\n--- Task ${taskNum} ---\n` + data.log;
          genLog.scrollTop = genLog.scrollHeight;
        }
        if (res.ok) {
          currentTaskIndex++;
          setTimeout(() => executeNextTask(), 500);
        } else {
          genStatus.innerHTML += ` <span style="color: #f87171;">[FAILED]</span>`;
          status.textContent = 'Task failed';
          status.className = 'err';
        }
      } catch (e) {
        genStatus.innerHTML += ` <span style="color: #f87171;">[ERROR]</span>`;
        status.textContent = 'Network error';
        status.className = 'err';
      }
    }

    function closePlan() {
      document.getElementById('planModal').style.display = 'none';
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
          // Wait for files to settle, then hard-reload iframe with cache bust
          setTimeout(() => {
            const iframe = document.getElementById('preview');
            iframe.src = `${appUrl}?t=${Date.now()}`;
          }, 500);
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
def phone_ui():
    return PHONE_UI


@app.get("/status")
def status():
    return {"status": "running"}


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


@app.post("/plan")
def plan(req: PlanRequest):
    """Generate an architecture plan using OpenAI."""
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
                    "content": """You are a software architect. Based on complexity:

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

Tasks must use format: "1) Task name", "2) Task name", etc.""",
                },
                {"role": "user", "content": req.prompt},
            ],
            temperature=0.7,
            max_completion_tokens=2000,
        )

        plan_text = response.choices[0].message.content

        # Extract tasks (numbered 1) 2) 3) format)
        tasks = []
        for line in plan_text.split("\n"):
            match = re.match(r"^\s*\d+[\.\)]\s+(.+)$", line.strip())
            if match:
                tasks.append(match.group(1).strip())

        return {
            "status": "ok",
            "plan": plan_text,
            "tasks": tasks,
            "task_count": len(tasks),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Planning failed: {str(e)}")


@app.post("/execute-task")
def execute_task(req: ExecuteTaskRequest):
    """Execute a single task via aider."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")

    files = [str(f.relative_to(REPO_ROOT)) for f in APP_SRC.rglob("*.jsx")]
    files += [str(f.relative_to(REPO_ROOT)) for f in APP_SRC.rglob("*.js")
              if not f.name.endswith(".min.js")]

    task_prompt = f"Task {req.task_num}: {req.task_desc}\n\nContext: {req.original_prompt}"

    try:
        result = subprocess.run(
            [
                "aider",
                "--yes-always",
                "--no-pretty",
                "--model", "gpt-5.4-mini",
                "--message", task_prompt,
                *files,
            ],
            cwd=str(REPO_ROOT),
            env={**os.environ, "OPENAI_API_KEY": api_key},
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Task timed out")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="aider not found")

    if result.returncode != 0:
        raise HTTPException(status_code=502, detail=result.stderr[-2000:] or "Task failed")

    return {"status": "ok", "message": f"Task {req.task_num} complete", "log": result.stdout[-1000:]}


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
        if gen_app_path.exists():
            shutil.rmtree(gen_app_path)
        # Copy app but skip node_modules
        shutil.copytree(
            app_path,
            gen_app_path,
            ignore=shutil.ignore_patterns("node_modules", ".vite"),
            dirs_exist_ok=True,
        )

        # Ensure App.jsx and main.jsx have React import for JSX to work
        for jsx_file in ["App.jsx", "main.jsx"]:
            jsx_path = gen_app_path / "src" / jsx_file
            if jsx_path.exists():
                content = jsx_path.read_text()
                if 'import React' not in content:
                    # Add React import as first import
                    lines = content.split('\n')
                    lines.insert(0, 'import React from "react";')
                    jsx_path.write_text('\n'.join(lines))

        # Install npm dependencies
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
