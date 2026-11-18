from fastapi import APIRouter, HTTPException

from controller import state
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



def _busy() -> bool:
    return any(j.get('status') in ('queued', 'running') for j in state.jobs.values())


@router.get("/job/active")
def get_active_job():
    if state.active_job_id and state.active_job_id in state.jobs:
        return {**state.jobs[state.active_job_id], "job_id": state.active_job_id}
    # Also check for queued state.jobs
    for jid, job in state.jobs.items():
        if job['status'] in ('queued', 'running'):
            return {**job, "job_id": jid}
    return None


@router.get("/job/{job_id}")
def get_job(job_id: str):
    if job_id not in state.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return {**state.jobs[job_id], "job_id": job_id}


async def _enqueue_job(job_id: str) -> dict:
    """Queue a planned or failed job. Failed tasks restart; done tasks stay done."""
    job = state.jobs[job_id]
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
    return {**job, "job_id": job_id}


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
