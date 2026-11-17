import asyncio


# In-memory job store and queue
jobs: dict = {}
job_queue: asyncio.Queue = None
active_job_id: str | None = None
