from pydantic import BaseModel


class SaveRequest(BaseModel):
    name: str
    overwrite: bool = False


class PlanRequest(BaseModel):
    prompt: str
    # Start the plan on the server after routes.jobs.AUTO_START_SECONDS unless cancelled.
    auto_start: bool = False


class LoadAppRequest(BaseModel):
    name: str


class RoleSelection(BaseModel):
    provider: str
    model: str


class ModelConfigRequest(BaseModel):
    planner: RoleSelection | None = None
    coder: RoleSelection | None = None
