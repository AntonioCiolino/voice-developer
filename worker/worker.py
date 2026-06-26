"""
worker.py — background task runner

Runs shell commands asynchronously and reports results.
Called by the controller for tasks that shouldn't block the main response:
  - npm install (if package.json changes)
  - git snapshots
  - future: deploy, build, etc.

Usage (standalone):
    python worker.py

Or import and call run_task() directly from the controller.
"""

import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
GENERATED_APP = ROOT / "generated-app"
LOG_PATH = ROOT / "worker" / "tasks.log"


def log(msg: str):
    entry = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(entry, flush=True)
    with open(LOG_PATH, "a") as f:
        f.write(entry + "\n")


def run_task(command: list[str], cwd: Path = ROOT) -> dict:
    """Run a shell command synchronously and return the result."""
    log(f"Running: {' '.join(command)} (cwd={cwd})")
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    outcome = {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }
    if result.returncode == 0:
        log(f"OK: {' '.join(command)}")
    else:
        log(f"FAIL (rc={result.returncode}): {result.stderr.strip()}")
    return outcome


async def run_task_async(command: list[str], cwd: Path = ROOT) -> dict:
    """Run a shell command asynchronously."""
    log(f"Async: {' '.join(command)} (cwd={cwd})")
    proc = await asyncio.create_subprocess_exec(
        *command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    outcome = {
        "command": command,
        "returncode": proc.returncode,
        "stdout": stdout.decode().strip(),
        "stderr": stderr.decode().strip(),
    }
    status = "OK" if proc.returncode == 0 else f"FAIL (rc={proc.returncode})"
    log(f"{status}: {' '.join(command)}")
    return outcome


# --- Named tasks ---

def npm_install():
    return run_task(["npm", "install"], cwd=GENERATED_APP)


def git_snapshot(message: str = "auto snapshot"):
    run_task(["git", "add", "-A"], cwd=ROOT)
    return run_task(["git", "commit", "-m", message, "--allow-empty"], cwd=ROOT)


# --- CLI entrypoint ---

TASKS = {
    "npm-install": npm_install,
    "git-snapshot": git_snapshot,
}

if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else None
    if task not in TASKS:
        print(f"Available tasks: {', '.join(TASKS)}")
        sys.exit(1)
    result = TASKS[task]()
    print(json.dumps(result, indent=2))
