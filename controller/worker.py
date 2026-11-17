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


STREAM_POLL_SECONDS = 1.0


def _read_log(path) -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


async def run_coder_streaming(job_id: str, i: int, command: list[str], provider, timeout: int):
    """Run the coder and copy its output into the task log while it runs.

    The coder writes stdout and stderr to a log file; a poller copies the file's tail
    into job["task_logs"][i] every STREAM_POLL_SECONDS so the UI (which polls the job)
    shows live progress. Returns a CompletedProcess-like result whose stdout holds the
    whole output. A timeout raises subprocess.TimeoutExpired carrying that output.
    """
    import tempfile
    import pathlib

    job = state.jobs[job_id]
    env = {**provider_environment(provider), "PYTHONUNBUFFERED": "1"}  # flush output as it is produced
    with tempfile.TemporaryDirectory(prefix="coder-log-") as tmp:
        log_path = pathlib.Path(tmp) / "task.log"
        done = asyncio.Event()

        async def poll():
            last = None
            while not done.is_set():
                text = tail(_read_log(log_path))
                if text and text != last:
                    job['task_logs'][i] = text
                    last = text
                try:
                    await asyncio.wait_for(done.wait(), STREAM_POLL_SECONDS)
                except asyncio.TimeoutError:
                    pass

        def run():
            with open(log_path, "w") as log:
                return subprocess.run(
                    command,
                    cwd=str(config.REPO_ROOT),
                    env=env,
                    stdout=log, stderr=subprocess.STDOUT, text=True, timeout=timeout,
                    stdin=subprocess.DEVNULL,
                )

        poller = asyncio.create_task(poll())
        try:
            result = await asyncio.get_running_loop().run_in_executor(None, run)
        except subprocess.TimeoutExpired as exc:
            if not exc.stdout and not exc.stderr:
                exc.stdout = _read_log(log_path)
            raise
        finally:
            done.set()
            await poller
        streamed = _read_log(log_path)
    # A real run wrote everything to the log file; keep any output the result carries.
    stdout = result.stdout if isinstance(result.stdout, str) and result.stdout else streamed
    stderr = result.stderr if isinstance(result.stderr, str) else ""
    return subprocess.CompletedProcess(command, result.returncode, stdout, stderr)


# Aider prints this when it gives up re-asking the model to fix edits that did not apply.
_GAVE_UP_MARKER = "reflections allowed, stopping"


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
    """Prompt for one task. Scoped so the coder does only this task, with a minimal edit.

    The full plan is deliberately not included: given every task, small models tend to
    implement several at once. Earlier tasks are listed as already in the code and later
    ones as explicitly out of scope.
    """
    tasks = job['tasks']
    n = len(tasks)
    completed = [f"  - Task {j+1}: {tasks[j]}" for j in range(i) if job['task_statuses'][j] == 'done']
    later = [f"  - Task {j+1}: {tasks[j]}" for j in range(i + 1, n)]
    return (
        f"Overall goal (context only): {job['prompt']}\n\n"
        + "Architecture: pure React + Vite SPA. No backend server, no express/fastapi, "
        + "no public/ folder unless you create it. All logic goes in src/ JSX files. "
        + "Tailwind CSS is loaded via CDN in index.html.\n\n"
        + ("Already done (these changes are in the files; do not redo them):\n"
           + "\n".join(completed) + "\n\n" if completed else "")
        + f"YOUR TASK, step {i+1} of {n}:\n  {tasks[i]}\n\n"
        + ("Later steps (do NOT implement any of these now; they are done separately):\n"
           + "\n".join(later) + "\n\n" if later else "")
        + "Rules:\n"
        + "- Do only YOUR TASK. Stop when it is done.\n"
        + "- Make the smallest change that completes it. Edit only the lines it needs.\n"
        + "- Keep all existing code, names, formatting and behavior that the task does not require changing. "
        + "Do not refactor, reorder or reformat.\n"
        + "- Copy each SEARCH block exactly from the current file, including indentation.\n"
        + "- Never write '...' or any placeholder inside a SEARCH block; it must contain only real "
        + "lines from the file.\n"
        + "- Keep each SEARCH block short: just the few lines being changed plus a line or two around them. "
        + "Use several small blocks rather than one large one.\n"
        + "- Do not ask clarifying questions or request additional files; use the files provided."
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
            result = await run_coder_streaming(job_id, i, command, provider, timeout)
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
        if _GAVE_UP_MARKER in text_of(result.stdout) + text_of(result.stderr):
            # Some SEARCH blocks may have applied, but Aider stopped retrying the rest,
            # so the edit is incomplete. Revert it rather than leave half a change.
            _fail_task(job_id, i, snapshot, f"Task {i+1} was only partly applied: Aider stopped after "
                       "repeated SEARCH blocks that did not match the file. Its changes were reverted.\n"
                       + "output:\n" + tail(text_of(result.stdout) + "\n" + text_of(result.stderr)))
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
