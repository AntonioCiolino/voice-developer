import asyncio
import time

from fastapi import APIRouter, HTTPException

from controller import config, state
from controller.coder import (
    OPENCODE_NOT_IMPLEMENTED,
    CoderEngineNotImplemented,
    resolve_coder_edit_format,
    resolve_coder_engine,
    resolve_coder_timeout,
)
from controller.escalation import resolve_escalation
from controller.providers import PlannerConfigurationError, resolve_roles
from controller.store import save_job

router = APIRouter()



# A new plan starts this long after Plan unless the phone cancels it.
AUTO_START_SECONDS = 5


def _busy() -> bool:
    return any(j.get('status') in ('queued', 'running') for j in state.jobs.values())


def auto_start_in(job_id: str) -> float | None:
    """Seconds until a pending auto-start of this plan, or None when none is pending."""
    deadline = state.auto_starts.get(job_id)
    return None if deadline is None else round(max(0.0, deadline - time.monotonic()), 1)


def _job_view(job_id: str) -> dict:
    return {**state.jobs[job_id], "job_id": job_id, "auto_start_in": auto_start_in(job_id)}


def schedule_auto_start(job_id: str, delay: float = AUTO_START_SECONDS) -> None:
    """Start the plan after `delay` seconds on the server, unless cancelled or started first.

    The countdown used to run only in the phone's browser: a page reload, a locked screen or a
    backgrounded tab lost or froze it, and the plan never started.
    """
    deadline = time.monotonic() + delay
    state.auto_starts[job_id] = deadline
    task = asyncio.get_running_loop().create_task(_auto_start_after(job_id, deadline))
    state.background_tasks.add(task)
    task.add_done_callback(state.background_tasks.discard)


async def _auto_start_after(job_id: str, deadline: float) -> None:
    await asyncio.sleep(max(0.0, deadline - time.monotonic()))
    if state.auto_starts.get(job_id) != deadline:
        return  # cancelled, started by hand, or replaced
    state.auto_starts.pop(job_id, None)
    if job_id not in state.jobs:
        return
    try:
        await _enqueue_job(job_id)
    except HTTPException as exc:
        # Shown by the phone, which is polling the plan: e.g. another plan is running.
        state.jobs[job_id]['error'] = f"Auto-start failed: {exc.detail}"
        save_job(job_id)
        config.logger.warning("Auto-start of plan %s failed: %s", job_id, exc.detail)


@router.get("/job/active")
def get_active_job():
    if state.active_job_id and state.active_job_id in state.jobs:
        return _job_view(state.active_job_id)
    # Also check for queued state.jobs
    for jid, job in state.jobs.items():
        if job['status'] in ('queued', 'running'):
            return _job_view(jid)
    # A plan about to start on its own, so a reloaded page can show its countdown.
    for jid in list(state.auto_starts):
        if jid in state.jobs:
            return _job_view(jid)
    return None


@router.get("/job/{job_id}")
def get_job(job_id: str):
    if job_id not in state.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_view(job_id)


@router.post("/job/{job_id}/cancel-start")
def cancel_auto_start(job_id: str):
    """Cancel a pending auto-start. The plan stays planned; Continue plan runs it later."""
    if job_id not in state.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    cancelled = state.auto_starts.pop(job_id, None) is not None
    return {**_job_view(job_id), "cancelled": cancelled}


async def _enqueue_job(job_id: str) -> dict:
    """Queue a planned or failed job. Failed tasks restart; done tasks stay done."""
    job = state.jobs[job_id]
    state.auto_starts.pop(job_id, None)  # started now, by hand or by its countdown
    if _busy():
        raise HTTPException(status_code=409, detail="A plan is already running")
    if job['status'] not in ('planned', 'failed') or all(s == 'done' for s in job['task_statuses']):
        raise HTTPException(status_code=409, detail=f"Plan is {job['status']} and cannot be started")
    if not job['tasks']:
        raise HTTPException(status_code=409, detail="This plan has no tasks to run")
    try:
        _, coder = resolve_roles()
        resolve_escalation(coder)
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
    await state.job_queue.put(job_id)
    return _job_view(job_id)


@router.post("/job/{job_id}/execute")
async def execute_job(job_id: str):
    if job_id not in state.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return await _enqueue_job(job_id)


@router.post("/continue")
async def continue_plan():
    """Resume the most recent stored plan from its next pending or failed task."""
    if _busy():
        raise HTTPException(status_code=409, detail="A plan is already running")
    resumable = [
        (j.get('created_at', ''), jid) for jid, j in state.jobs.items()
        if j.get('status') in ('planned', 'failed')
        and j.get('tasks') and any(s != 'done' for s in j['task_statuses'])
    ]
    if not resumable:
        if any(j.get('tasks') for j in state.jobs.values()):
            raise HTTPException(status_code=404, detail="The latest plan is already complete. Press Plan to create a new one.")
        raise HTTPException(status_code=404, detail="No stored plan to continue. Press Plan to create one.")
    return await _enqueue_job(max(resumable)[1])
