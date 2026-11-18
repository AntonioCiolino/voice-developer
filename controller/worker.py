import asyncio
import subprocess
from dataclasses import dataclass

from controller import config, state
from controller.coder import (
    CoderEngineNotImplemented,
    build_coder_command,
    extract_cost,
    extract_cost_amount,
    resolve_aider_bin,
    resolve_coder_edit_format,
    resolve_coder_engine,
    resolve_coder_timeout,
    resolve_max_file_lines,
    resolve_task_validation,
    resolve_validation_timeout,
)
from controller.escalation import UNPARSED_CLOUD_COST, resolve_escalation
from controller.planning import parse_task_files
from controller.providers import (
    PlannerConfigurationError,
    provider_environment,
    resolve_roles,
    role_provider_info,
    roles_info,
)
from controller.store import save_job
from controller.validation import validate_app
from controller.workspace import (
    changed_task_paths,
    commit_task,
    over_limit_files,
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


async def run_coder_streaming(job_id: str, i: int, command: list[str], provider, timeout: int,
                              prefix: str = ""):
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
                text = tail(prefix + _read_log(log_path))
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


def build_task_prompt(job: dict, i: int, edit_format: str = "diff", max_lines: int | None = None,
                      files: list[str] | None = None, validation_errors: str = "",
                      previous_failure: str = "") -> str:
    """Prompt for one task. Scoped so the coder does only this task, with a minimal edit.

    The full plan is deliberately not included: given every task, small models tend to
    implement several at once. Earlier tasks are listed as already in the code and later
    ones as explicitly out of scope.
    """
    tasks = job['tasks']
    n = len(tasks)
    max_lines = max_lines or config.DEFAULT_MAX_FILE_LINES
    if edit_format == "whole":
        edit_rules = (
            "- Return each file you change in full, with every existing line that the task does not "
            "change kept exactly as it is. Never drop, shorten or summarize existing code.\n"
        )
    else:
        edit_rules = (
            "- Copy each SEARCH block exactly from the current file, including indentation.\n"
            + "- Never write '...' or any placeholder inside a SEARCH block; it must contain only real "
            + "lines from the file.\n"
            + "- Keep each SEARCH block short: just the few lines being changed plus a line or two around them. "
            + "Use several small blocks rather than one large one.\n"
        )
    completed = [f"  - Task {j+1}: {tasks[j]}" for j in range(i) if job['task_statuses'][j] == 'done']
    later = [f"  - Task {j+1}: {tasks[j]}" for j in range(i + 1, n)]
    fix_block = (
        "\n\nYour previous attempt at this task left the app failing its build or lint check. "
        + "The current files already contain that attempt. Fix only these errors, keeping the change minimal "
        + "and keeping the rest of the task as it is:\n" + validation_errors
    ) if validation_errors else ""
    earlier_block = (
        "\n\nAn earlier attempt at this task with another model failed and was reverted, so the files are back "
        + "to their state before the task. Here is why it failed; avoid the same mistake:\n" + previous_failure[:1500]
    ) if previous_failure else ""
    return (
        f"Overall goal (context only): {job['prompt']}\n\n"
        + "Architecture: pure React + Vite SPA. No backend server, no express/fastapi, "
        + "no public/ folder unless you create it. All logic goes in src/ JSX files. "
        + "Tailwind CSS is loaded via CDN in index.html.\n\n"
        + ("Already done (these changes are in the files; do not redo them):\n"
           + "\n".join(completed) + "\n\n" if completed else "")
        + f"YOUR TASK, step {i+1} of {n}:\n  {tasks[i]}\n\n"
        + ("Files provided for this task (create a file named here if it does not exist): "
           + ", ".join(files) + "\n\n" if files else "")
        + ("Later steps (do NOT implement any of these now; they are done separately):\n"
           + "\n".join(later) + "\n\n" if later else "")
        + "Rules:\n"
        + "- Do only YOUR TASK. Stop when it is done.\n"
        + "- Make the smallest change that completes it. Edit only the lines it needs.\n"
        + "- Keep all existing code, names, formatting and behavior that the task does not require changing. "
        + "Do not refactor, reorder or reformat.\n"
        + edit_rules
        + f"- Keep every file under {max_lines} lines. Put new components or logic in a new small file "
        + "under src/ and wire it in with an import and a few lines, instead of growing an existing file.\n"
        + "- Do not ask clarifying questions or request additional files; use the files provided."
        + fix_block
        + earlier_block
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


@dataclass
class TaskFailure:
    """Why one rung attempt failed. `message` is the text a failed run shows (today's wording)."""
    kind: str
    summary: str
    detail: str
    message: str
    escalate: bool


@dataclass
class RunContext:
    engine: str
    timeout: int
    max_lines: int
    checks: object
    val_timeout: int
    active: bool


def _first_line(text: str, limit: int = 160) -> str:
    line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    return line[:limit]


def _charge(job: dict, i: int, rung, output: str, active: bool, costs: list[str]) -> None:
    """Record an attempt's cost: the display string always, the plan total when the ladder is active."""
    shown = extract_cost(output)
    amount = extract_cost_amount(output)
    estimated = False
    if active and amount is None and not rung.provider.is_local:
        amount, estimated = UNPARSED_CLOUD_COST, True
        job['plan_cost_estimated'] = True
        line = f"cost not reported by Aider; counted ${UNPARSED_CLOUD_COST:.2f} estimate"
        job['task_logs'][i] = (job['task_logs'][i] + "\n" if job['task_logs'][i] else "") + line
    if shown:
        costs.append(shown)
    elif estimated:
        costs.append(f"~${UNPARSED_CLOUD_COST:.2f}")
    job['task_costs'][i] = " + ".join(costs)
    if active:
        job['plan_cost'] = round(float(job.get('plan_cost') or 0.0) + (amount or 0.0), 6)
    save_job(job['id'])


def _cap_message(job: dict, esc, i: int, last: str) -> str:
    estimated = " (estimated parts included)" if job.get('plan_cost_estimated') else ""
    return (f"Stopped at task {i+1}: plan cost ${job['plan_cost']:.2f} reached MAX_PLAN_COST "
            f"${esc.max_plan_cost:.2f}{estimated}; not escalating further. Last attempt: {last}")


async def _run_rung_attempt(job_id: str, i: int, rung, ctx: RunContext, box: dict,
                            previous_failure: str, escalated: bool) -> TaskFailure | None:
    """One rung's attempt at task i: the coder run plus, on build/lint failure, the one fix retry.

    Returns None on success, else why it failed. It never reverts; the caller does.
    box carries "snapshot" (set here) and "costs" (the task's cost display parts).
    """
    job = state.jobs[job_id]
    provider = rung.provider
    edit_format = resolve_coder_edit_format(provider=provider)
    n = len(job['tasks'])
    validation_errors = ""
    scope_files: list[str] = []
    for attempt in (1, 2):
        prefix = job['task_logs'][i] + "\n" if (attempt == 2 or escalated) else ""
        try:
            if attempt == 1:
                box['snapshot'] = snapshot_task_scope()
                # Only the files this task names (plus their importers); no named file -> all src files.
                scope_files = [str(f.relative_to(config.REPO_ROOT))
                               for f in task_scope_files(parse_task_files(job['tasks'][i]))]
                files = scope_files
            else:
                # Retry on the current files: also hand over files the first attempt created.
                files = scope_files + [
                    rel for rel in (str((config.APP_ROOT / p).relative_to(config.REPO_ROOT))
                                    for p in changed_task_paths(box['snapshot']) if (config.APP_ROOT / p).is_file())
                    if rel not in scope_files
                ]
            prompt = build_task_prompt(job, i, edit_format, ctx.max_lines, files, validation_errors,
                                       previous_failure)
            command = build_coder_command(ctx.engine, provider, prompt, files, edit_format)
            result = await run_coder_streaming(job_id, i, command, provider, ctx.timeout, prefix)
        except CoderEngineNotImplemented as exc:
            return TaskFailure("engine", "engine not implemented", str(exc), str(exc), False)
        except subprocess.TimeoutExpired as exc:
            message = f"Task {i+1} timed out after {ctx.timeout} s (CODER_TIMEOUT_SECONDS)"
            message += " (retry after validation failure)." if attempt == 2 else "."
            partial = tail(exc.stderr) or tail(exc.stdout)
            job['task_logs'][i] = tail(prefix + text_of(exc.stdout))
            if partial:
                message += f"\nPartial output:\n{partial}"
            _charge(job, i, rung, text_of(exc.stdout) + "\n" + text_of(exc.stderr), ctx.active, box['costs'])
            return TaskFailure("timeout", f"timed out after {ctx.timeout} s",
                               f"It timed out after {ctx.timeout} s." + (f"\nPartial output:\n{partial}" if partial else ""),
                               message, True)
        except FileNotFoundError as exc:
            missing = (
                f"aider not found at '{resolve_aider_bin()}'. Create it with: "
                "python3 -m venv controller/aider-venv && "
                "controller/aider-venv/bin/pip install aider-chat==0.86.2 (or set AIDER_BIN)"
            ) if ctx.engine == "aider" else str(exc)
            return TaskFailure("missing", "coder not found", missing, missing, False)
        except Exception as exc:
            message = f"Task {i+1} failed: {exc}"
            return TaskFailure("error", f"failed: {exc}", message, message, False)
        job['task_logs'][i] = tail(prefix + text_of(result.stdout))
        _charge(job, i, rung, text_of(result.stdout), ctx.active, box['costs'])
        if result.returncode != 0:
            parts = [f"Task {i+1} failed (exit code {result.returncode})."]
            if tail(result.stderr):
                parts.append("stderr:\n" + tail(result.stderr))
            if tail(result.stdout):
                parts.append("stdout:\n" + tail(result.stdout))
            message = "\n".join(parts)
            return TaskFailure("exit", f"exited with code {result.returncode}", message, message, False)
        app_jsx = config.APP_SRC / "App.jsx"
        if app_jsx.exists():
            content = app_jsx.read_text(errors='ignore')
            if len(content) < 100 or 'export default' not in content:
                message = f"Task {i+1} corrupted App.jsx; its changes were reverted"
                return TaskFailure("corrupted", "corrupted App.jsx", message, message, True)
        if _GAVE_UP_MARKER in text_of(result.stdout) + text_of(result.stderr):
            # Some SEARCH blocks may have applied, but Aider stopped retrying the rest,
            # so the edit is incomplete. Revert it rather than leave half a change.
            output = "output:\n" + tail(text_of(result.stdout) + "\n" + text_of(result.stderr))
            message = (f"Task {i+1} was only partly applied: Aider stopped after "
                       "repeated SEARCH blocks that did not match the file. Its changes were reverted.\n" + output)
            return TaskFailure("partial", "was only partly applied (Aider stopped after repeated SEARCH mismatches)",
                               "It was only partly applied: Aider stopped after repeated SEARCH blocks that did "
                               "not match the file.\n" + output, message, True)
        unapplied = edit_failure_reason(result.stdout, result.stderr)
        if unapplied and not changed_task_paths(box['snapshot']):
            # Aider exits 0 even when the model call fails or no edit applies.
            output = "output:\n" + tail(text_of(result.stdout) + "\n" + text_of(result.stderr))
            message = f"Task {i+1} made no changes: {unapplied}\n" + output
            return TaskFailure("no-edit", f"applied no edit ({unapplied})",
                               f"It applied no edit: {unapplied}\n" + output, message, True)

        def log_line(line: str, i=i) -> None:
            job['task_logs'][i] = (job['task_logs'][i] + "\n" if job['task_logs'][i] else "") + line
            save_job(job_id)

        try:
            failures = await asyncio.get_running_loop().run_in_executor(
                None, validate_app, box['snapshot'], ctx.checks, ctx.val_timeout, log_line)
        except Exception as exc:  # a broken validator must not hide the coder's work as done
            failures = [("validation", f"validation could not run: {exc}")]
        if not failures:
            return None
        errors = "\n\n".join(f"{name} output:\n{output}" for name, output in failures)
        if attempt == 1:
            validation_errors = errors
            log_line("Validation failed, retrying once with the errors...")
            continue
        names = "/".join(name for name, _ in failures)
        message = f"Task {i+1} failed validation ({names}) after one retry:\n{errors}"
        name, output = failures[0]
        return TaskFailure("validation", f"failed {name}: {_first_line(output)}", errors, message,
                           any(name in ("build", "lint") for name, _ in failures))
    return None


async def run_job(job_id: str) -> None:
    job = state.jobs[job_id]
    n = len(job['tasks'])
    job.setdefault('task_errors', [""] * n)
    job.setdefault('task_warnings', [""] * n)
    job['status'] = 'running'
    job['error'] = None
    try:
        planner, provider = resolve_roles()
        engine = resolve_coder_engine()
        timeout = resolve_coder_timeout()
        edit_format = resolve_coder_edit_format(provider=provider)  # default follows the coder in use
        max_lines = resolve_max_file_lines()
        checks = resolve_task_validation()
        val_timeout = resolve_validation_timeout()
        esc = resolve_escalation(provider)
    except PlannerConfigurationError as exc:
        job['status'] = 'failed'
        job['error'] = str(exc)
        save_job(job_id)
        return
    job['engine'] = engine
    _record_coder(job, planner, provider)
    if esc.active:
        job['ladder'] = esc.info()
        if not isinstance(job.get('task_rungs'), list) or len(job['task_rungs']) != n:
            job['task_rungs'] = [None] * n
        job.setdefault('plan_cost', 0.0)
        job.setdefault('plan_cost_estimated', False)
    else:
        job.pop('ladder', None)
    save_job(job_id)
    try:
        ensure_app_repo_hygiene()
    except Exception:
        pass  # hygiene is best-effort; never block a run on it
    ctx = RunContext(engine, timeout, max_lines, checks, val_timeout, esc.active)

    for i in range(n):
        if job['task_statuses'][i] == 'done':
            continue
        job['current_task'] = i
        job['task_statuses'][i] = 'running'
        job['task_errors'][i] = ""
        job['task_warnings'][i] = ""
        save_job(job_id)
        box = {"snapshot": None, "costs": []}
        start, previous_failure, history = 0, "", []
        suggestion = job.get('suggested_rung')
        if esc.active and isinstance(suggestion, dict) and suggestion.get('task') == i:
            job['suggested_rung'] = None
            specs = [r.spec for r in esc.rungs]
            if suggestion.get('spec') in specs:
                start = specs.index(suggestion['spec'])
                previous_failure = suggestion.get('previous_failure', "")
                if suggestion.get('history'):
                    history = [suggestion['history']]
            else:
                job['task_logs'][i] = (f"Suggested rung {suggestion.get('spec')} is no longer in the ladder; "
                                       f"starting on {esc.rungs[0].label}.")
        failure = None
        failure_label = ""
        for r in range(start, len(esc.rungs)):
            rung = esc.rungs[r]
            if esc.active and not rung.provider.is_local and job['plan_cost'] >= esc.max_plan_cost:
                last = f"{failure_label} {failure.summary}" if failure else "none yet"
                _fail_task(job_id, i, None, _cap_message(job, esc, i, last))
                return
            if esc.active:
                _record_coder(job, planner, rung.provider)
                job['task_rungs'][i] = {**rung.info(), "history": list(history)}
                if history:
                    job['task_logs'][i] = "\n".join(history)
                save_job(job_id)
            failure = await _run_rung_attempt(job_id, i, rung, ctx, box, previous_failure, bool(history))
            if failure is None:
                break
            failure_label = rung.label
            if not (esc.active and failure.escalate):
                _fail_task(job_id, i, box['snapshot'], failure.message)
                return
            if r + 1 >= len(esc.rungs):
                names = ", ".join(x.label for x in esc.rungs)
                count = f"{len(esc.rungs)} rung" + ("" if len(esc.rungs) == 1 else "s")
                _fail_task(job_id, i, box['snapshot'],
                           f"Task {i+1} failed on all {count} ({names}). Last failure on {rung.label}:\n"
                           + failure.message)
                return
            nxt = esc.rungs[r + 1]
            line = f"{nxt.label}, after {rung.label} {failure.summary}"
            if esc.mode == 'suggest':
                if not nxt.provider.is_local and job['plan_cost'] >= esc.max_plan_cost:
                    _fail_task(job_id, i, box['snapshot'],
                               _cap_message(job, esc, i, f"{rung.label} {failure.summary}"))
                    return
                job['suggested_rung'] = {"task": i, "spec": nxt.spec, "label": nxt.label,
                                         "previous_failure": failure.detail[-1500:], "history": line}
                _fail_task(job_id, i, box['snapshot'],
                           f"Task {i+1} failed on {rung.label} ({failure.summary}). "
                           f"Suggested next: {nxt.label} ({nxt.spec}). Press Continue to retry it there.")
                return
            try:
                note = revert_task(box['snapshot']) if box['snapshot'] is not None else ""
            except Exception as exc:  # keep the original failure visible
                note = f"revert failed: {exc}"
            history.append(line)
            job['task_logs'][i] = (job['task_logs'][i] + "\n" if job['task_logs'][i] else "") + (
                "Reverted this task's changes" + (f" ({note})" if note else " (nothing to undo)") + "\n" + line)
            previous_failure = failure.detail[-1500:]
            save_job(job_id)
        snapshot = box['snapshot']
        try:
            note = commit_task(snapshot, f"Task {i+1}/{n}: {job['tasks'][i]}"[:200])
        except Exception as exc:
            note = f"commit skipped: {exc}"
        job['task_logs'][i] = (job['task_logs'][i] + "\n" if job['task_logs'][i] else "") + note
        # Over-limit files are a warning, not a failure: the work is kept and committed (see README).
        over = over_limit_files(snapshot, max_lines)
        if over:
            job['task_warnings'][i] = "Over the line limit (MAX_FILE_LINES=%d): " % max_lines + ", ".join(
                f"{rel} has {count} lines" for rel, count in over
            ) + ". Split it into smaller files in a later task."
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
