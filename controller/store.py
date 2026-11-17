import json
import os
import re
from datetime import datetime

from controller import config, state


_PLAN_FILE_RE = re.compile(r"^[0-9a-f-]{36}\.json$")


def save_job(job_id: str) -> None:
    """Atomically write the job record to PLANS_DIR/<job_id>.json."""
    job = state.jobs[job_id]
    job["id"] = job_id
    job["updated_at"] = datetime.now().isoformat()
    config.PLANS_DIR.mkdir(parents=True, exist_ok=True)
    target = config.PLANS_DIR / f"{job_id}.json"
    tmp = config.PLANS_DIR / f".{job_id}.json.tmp"
    tmp.write_text(json.dumps(job, indent=2))
    os.replace(tmp, target)


def load_jobs() -> None:
    """Load stored plans into `jobs`. Jobs interrupted by a restart are made resumable."""
    if not config.PLANS_DIR.exists():
        return
    for path in sorted(config.PLANS_DIR.iterdir()):
        if not _PLAN_FILE_RE.match(path.name):
            continue
        try:
            job = json.loads(path.read_text())
            if not isinstance(job, dict) or not isinstance(job.get("tasks"), list):
                raise ValueError("not a plan record")
        except Exception as exc:
            config.logger.warning("Skipping unreadable plan file %s: %s", path.name, exc)
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
        state.jobs[job_id] = job
        if changed:
            try:
                save_job(job_id)
            except OSError as exc:
                config.logger.warning("Could not rewrite plan file %s: %s", path.name, exc)
