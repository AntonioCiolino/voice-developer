import asyncio
# In-memory job store and queue
jobs: dict = {}
job_queue: asyncio.Queue = None
active_job_id: str | None = None
# Plans waiting to start on their own: job id -> time.monotonic() deadline. In memory only, so a
# restart drops a pending start (the plan stays planned; Continue runs it).
auto_starts: dict[str, float] = {}
# Strong references to background tasks (asyncio keeps only weak ones).
background_tasks: set = set()
