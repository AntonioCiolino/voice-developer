from pydantic import BaseModel


class SaveRequest(BaseModel):
    name: str
    overwrite: bool = False


class PlanRequest(BaseModel):
    prompt: str


class LoadAppRequest(BaseModel):
    name: str
