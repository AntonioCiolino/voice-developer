import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from controller import config, state
from controller.auth import require_auth, validate_auth_config
from controller.routes import apps, auth, jobs, models, planner, system, ui
from controller.store import load_jobs
from controller.worker import job_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_auth_config()
    config.APP_SRC.mkdir(parents=True, exist_ok=True)
    load_jobs()
    state.job_queue = asyncio.Queue()
    worker = asyncio.create_task(job_worker())
    yield
    worker.cancel()


app = FastAPI(title="voice-developer controller", lifespan=lifespan)
app.middleware("http")(require_auth)
for module in (ui, auth, system, apps, planner, jobs, models):
    app.include_router(module.router)
