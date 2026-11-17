import asyncio
import subprocess

from controller import config, state
from controller.coder import (
    CoderEngineNotImplemented,
    build_coder_command,
    extract_cost,
    resolve_aider_bin,
    resolve_coder_edit_format,
    resolve_coder_engine,
    resolve_coder_timeout,
)
from controller.providers import (
    PlannerConfigurationError,
    provider_environment,
    resolve_roles,
    role_provider_info,
    roles_info,
)
from controller.store import save_job
from controller.workspace import (
    changed_task_paths,
    commit_task,
    ensure_app_repo_hygiene,
    revert_task,
    snapshot_task_scope,
    task_scope_files,
)


PLAN_CONTEXT_LIMIT = 4000
LOG_TAIL_LIMIT = 4000

# Aider prints these (and still exits 0) when no edit reached the files.
_EDIT_FAILURE_MARKERS = (
    ("BadRequestError", "the model API rejected the request"),
    ("AuthenticationError", "the model API rejected the credentials"),
    ("APIConnectionError", "the model server could not be reached"),
    ("RateLimitError", "the model API rate-limited the request"),
    ("failed to exactly match", "the model's SEARCH block did not match the file"),
    ("did not conform to the edit format", "the model's reply was not in the edit format"),
)


def edit_failure_reason(stdout, stderr) -> str:
    """Return why Aider applied no edit, or "" when its output shows no failure."""
    output = text_of(stdout) + "\n" + text_of(stderr)
    return next((reason for marker, reason in _EDIT_FAILURE_MARKERS if marker in output), "")


def text_of(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def tail(value, limit: int = LOG_TAIL_LIMIT) -> str:
    return text_of(value).strip()[-limit:]


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
    job = state.jobs[job_id]
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


def _record_coder(job: dict, planner, coder) -> None:
    """Store the coder this run actually uses (resolved once, at run start)."""
    roles = job.get('roles')
    if not isinstance(roles, dict) or not isinstance(roles.get('planner'), dict):
        job['roles'] = roles_info(planner, coder)
        return
    roles['coder'] = role_provider_info('coder', coder)
    planned = roles['planner']
    planner_local = planned.get('location') == 'local' if 'location' in planned else planner.is_local
    roles['local_only'] = planner_local and coder.is_local


async def run_job(job_id: str) -> None:
    job = state.jobs[job_id]
    n = len(job['tasks'])
    job.setdefault('task_errors', [""] * n)
    job['status'] = 'running'
    job['error'] = None
    try:
        planner, provider = resolve_roles()
        engine = resolve_coder_engine()
        timeout = resolve_coder_timeout()
        edit_format = resolve_coder_edit_format()
    except PlannerConfigurationError as exc:
        job['status'] = 'failed'
        job['error'] = str(exc)
        save_job(job_id)
        return
    job['engine'] = engine
    _record_coder(job, planner, provider)
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
            files = [str(f.relative_to(config.REPO_ROOT)) for f in task_scope_files()]
            command = build_coder_command(engine, provider, build_task_prompt(job, i), files, edit_format)
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, lambda cmd=command: subprocess.run(
                cmd,
                cwd=str(config.REPO_ROOT),
                env=provider_environment(provider),
                capture_output=True, text=True, timeout=timeout,
                stdin=subprocess.DEVNULL,
            ))
        except CoderEngineNotImplemented as exc:
            _fail_task(job_id, i, snapshot, str(exc))
            return
        except subprocess.TimeoutExpired as exc:
            message = f"Task {i+1} timed out after {timeout} s (CODER_TIMEOUT_SECONDS)."
            partial = tail(exc.stderr) or tail(exc.stdout)
            job['task_logs'][i] = tail(exc.stdout)
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

        job['task_logs'][i] = tail(result.stdout)
        job['task_costs'][i] = extract_cost(result.stdout)
        if result.returncode != 0:
            parts = [f"Task {i+1} failed (exit code {result.returncode})."]
            if tail(result.stderr):
                parts.append("stderr:\n" + tail(result.stderr))
            if tail(result.stdout):
                parts.append("stdout:\n" + tail(result.stdout))
            _fail_task(job_id, i, snapshot, "\n".join(parts))
            return
        app_jsx = config.APP_SRC / "App.jsx"
        if app_jsx.exists():
            content = app_jsx.read_text(errors='ignore')
            if len(content) < 100 or 'export default' not in content:
                _fail_task(job_id, i, snapshot, f"Task {i+1} corrupted App.jsx; its changes were reverted")
                return
        unapplied = edit_failure_reason(result.stdout, result.stderr)
        if unapplied and not changed_task_paths(snapshot):
            # Aider exits 0 even when the model call fails or no edit applies.
            _fail_task(job_id, i, snapshot, f"Task {i+1} made no changes: {unapplied}\n"
                       + "output:\n" + tail(text_of(result.stdout) + "\n" + text_of(result.stderr)))
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
    while True:
        job_id = await state.job_queue.get()
        state.active_job_id = job_id
        try:
            await run_job(job_id)
        except Exception as exc:  # never let one job kill the worker
            config.logger.exception("Job %s crashed", job_id)
            job = state.jobs.get(job_id)
            if job:
                job['status'] = 'failed'
                job['error'] = str(exc)
                try:
                    save_job(job_id)
                except OSError:
                    pass
        finally:
            state.active_job_id = None
            state.job_queue.task_done()
