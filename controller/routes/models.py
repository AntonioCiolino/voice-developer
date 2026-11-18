import re

from fastapi import APIRouter, HTTPException

from controller import selection
from controller.discovery import discover_providers
from controller.providers import LOCATION_LABELS, PlannerConfigurationError, resolve_roles, roles_info
from controller.routes.jobs import _busy
from controller.schemas import ModelConfigRequest

router = APIRouter()

MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$")


def _payload() -> dict:
    roles, local_only, uses_lan, error = None, None, None, None
    try:
        saved = selection.load_selection() or {}
        planner, coder = resolve_roles()
        info = roles_info(planner, coder)
        roles = {
            role: {
                "provider": info[role]["name"],
                "model": info[role]["model"],
                "location": info[role]["location"],
                "location_label": LOCATION_LABELS[info[role]["location"]],
                "server": info[role].get("server"),
                "source": "ui" if role in saved else "env",
            }
            for role in selection.ROLES
        }
        local_only = info["local_only"]
        uses_lan = info["uses_lan"]
    except PlannerConfigurationError as exc:
        error = str(exc)
    return {
        "roles": roles,
        "local_only": local_only,
        "uses_lan": uses_lan,
        "providers": discover_providers(),
        "busy": _busy(),
        "config_error": error,
    }


@router.get("/model-config")
def get_model_config():
    return _payload()


@router.put("/model-config")
def put_model_config(req: ModelConfigRequest):
    requested = {role: getattr(req, role) for role in selection.ROLES if getattr(req, role) is not None}
    if not requested:
        raise HTTPException(status_code=400, detail="Choose a planner or coder model")
    providers = {p["name"]: p for p in discover_providers()}
    for role, choice in requested.items():
        provider = providers.get(choice.provider)
        if provider is None:
            raise HTTPException(status_code=400, detail=f"Unknown provider for {role}")
        if not MODEL_RE.match(choice.model):
            raise HTTPException(status_code=400, detail=f"Invalid model name for {role}")
        if not provider["available"]:
            status = 400 if choice.provider == "openai" else 503
            raise HTTPException(status_code=status, detail=f"{provider['label']}: {provider['error']}")
        if choice.model not in {m["id"] for m in provider["models"]}:
            raise HTTPException(
                status_code=400, detail=f"{provider['label']} does not offer that model for {role}"
            )
    try:
        merged = {**(selection.load_selection() or {}),
                  **{role: {"provider": c.provider, "model": c.model} for role, c in requested.items()}}
        resolve_roles(selection.overlay_env(merged))
    except PlannerConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    selection.save_selection(merged)
    return _payload()


@router.delete("/model-config")
def delete_model_config():
    selection.clear_selection()
    return _payload()
