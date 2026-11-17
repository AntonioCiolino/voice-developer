import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from controller import state
from controller.coder import resolve_coder_engine
from controller.planning import PLANNER_SYSTEM_PROMPT, parse_tasks, planner_user_msg
from controller.providers import (
    PlannerConfigurationError,
    create_planner_client,
    planner_provider_info,
    resolve_roles,
    roles_info,
)
from controller.schemas import PlanRequest
from controller.store import save_job

router = APIRouter()

PLANNER_TEMPERATURE = 0.7
# Models (e.g. the GPT-6 family) that reject any temperature except the default.
_DEFAULT_TEMPERATURE_ONLY: set[str] = set()


def _rejects_temperature(exc: Exception) -> bool:
    if getattr(exc, "param", None) == "temperature":
        return True
    text = str(exc).lower()
    return "temperature" in text and ("unsupported" in text or "not support" in text)


def create_plan_completion(client, model: str, messages: list[dict]):
    """Call the planner. Retry once without temperature if the model only allows its default."""
    kwargs = {"model": model, "messages": messages, "max_completion_tokens": 2000}
    if model not in _DEFAULT_TEMPERATURE_ONLY:
        try:
            return client.chat.completions.create(temperature=PLANNER_TEMPERATURE, **kwargs)
        except Exception as exc:
            if not _rejects_temperature(exc):
                raise
            _DEFAULT_TEMPERATURE_ONLY.add(model)
    return client.chat.completions.create(**kwargs)



@router.get("/planner-provider")
def get_planner_provider():
    try:
        planner, coder = resolve_roles()
        return {**planner_provider_info(planner), "roles": roles_info(planner, coder)}
    except PlannerConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/plan")
async def plan(req: PlanRequest):
    """Generate a plan and store it as a planned job. Execution starts separately."""
    try:
        provider, coder = resolve_roles()
    except PlannerConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    client = create_planner_client(provider)

    try:
        response = create_plan_completion(
            client,
            provider.model,
            [
                {
                    "role": "system",
                    "content": PLANNER_SYSTEM_PROMPT,
                },
                {"role": "user", "content": planner_user_msg(req.prompt)},
            ],
        )

        plan_text = response.choices[0].message.content or ""
        if not plan_text.strip():
            raise RuntimeError(f"{provider.model} returned an empty plan")
        tasks = parse_tasks(plan_text)

        job_id = str(uuid.uuid4())
        state.jobs[job_id] = {
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
