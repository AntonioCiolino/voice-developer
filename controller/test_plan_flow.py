import asyncio
import inspect
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

import controller.app as app_module
import controller.routes.planner as planner_routes
import controller.state as state
import controller.workspace as workspace
from controller import config, selection
from controller.coder import (
    CoderEngineNotImplemented,
    aider,
    build_aider_command,
    build_coder_command,
    build_opencode_command,
    resolve_coder_edit_format,
    resolve_coder_engine,
    resolve_coder_timeout,
)
from controller.planning import parse_tasks
from controller.providers import PlannerConfigurationError, PlannerProvider
from controller.routes.jobs import continue_plan, execute_job
from controller.schemas import PlanRequest
from controller.state import jobs
from controller.store import load_jobs, save_job
from controller.ui import PHONE_UI
from controller.worker import run_job
from controller.workspace import revert_task, snapshot_task_scope

_selection_patch = None
_selection_tmp = None


def setUpModule():
    """Keep a real controller/model-selection.json from leaking into these tests."""
    global _selection_patch, _selection_tmp
    _selection_tmp = tempfile.mkdtemp()
    _selection_patch = patch.object(
        selection, "SELECTION_PATH", pathlib.Path(_selection_tmp) / "model-selection.json"
    )
    _selection_patch.start()


def tearDownModule():
    _selection_patch.stop()
    shutil.rmtree(_selection_tmp, True)


CONTROLLER_DIR = pathlib.Path(__file__).parent


def controller_source() -> str:
    """Source of every non-test controller module plus the UI template (never the venvs)."""
    files = [
        f
        for pattern in ("*.py", "coder/*.py", "routes/*.py", "templates/*.html")
        for f in sorted(CONTROLLER_DIR.glob(pattern))
        if not f.name.startswith("test_")
    ]
    return "\n".join(f.read_text() for f in files)

LOCAL = PlannerProvider(name="ollama", model="qwen2.5-coder:7b", ollama_api_base="http://127.0.0.1:11434")
OLLAMA_ENV = {"PLANNER_PROVIDER": "ollama", "OLLAMA_MODEL": "qwen2.5:7b",
              "OLLAMA_API_BASE": "http://127.0.0.1:11434"}
APP_JSX = "import React from 'react';\nexport default function App() { return <div>hello world, this is a long enough file</div>; }\n"

USER_OUTPUT = """## Tasks
1) Update cube material color to green in the `App.jsx` file.

### Full Plan
## 1) Requirements
Change the color of the cube in the 3D scene to green.

## 2) Architecture
No changes.

## 3) Tasks
1) Update cube material color to green in the `App.jsx` file.
2) Ensure the cube is properly defined and accessible in `App.jsx`.

## 4) Acceptance Criteria
- The cube's material color should be updated to green.

### Code Changes
1) Task one
```jsx
const cubeMaterial = new THREE.MeshStandardMaterial({ color: 0x00ff00 });
```

2) Task two
```jsx
const x = 1;
```
"""


class ParseTasksTests(unittest.TestCase):
    def test_user_example_yields_one_task(self):
        self.assertEqual(parse_tasks(USER_OUTPUT),
                         ["Update cube material color to green in the `App.jsx` file."])

    def test_complex_plan_only_reads_tasks_section(self):
        text = ("## 1) Requirements\n1) not a task\n## 2) Architecture\n## 3) Tasks\n"
                "1) First\n2) Second\n3) First\n## 4) Acceptance Criteria\n1) not a task either\n")
        self.assertEqual(parse_tasks(text), ["First", "Second"])

    def test_code_fences_are_skipped(self):
        text = "## Tasks\n1) Real\n```\n2) fake in fence\n```\n2. Other\n"
        self.assertEqual(parse_tasks(text), ["Real", "Other"])

    def test_fallback_without_heading_and_empty(self):
        self.assertEqual(parse_tasks("1) A\n2) B\n## Notes\n3) C"), ["A", "B"])
        self.assertEqual(parse_tasks(""), [])
        self.assertEqual(parse_tasks("no tasks here"), [])


class CoderConfigTests(unittest.TestCase):
    def test_aider_flags(self):
        cmd = build_aider_command(LOCAL, "do it", ["a.jsx"])
        self.assertEqual(cmd[cmd.index("--edit-format") + 1], "diff")
        self.assertLess(cmd.index("--edit-format"), cmd.index("--message"))
        cmd = build_aider_command(LOCAL, "do it", ["a.jsx"], "udiff")
        self.assertEqual(cmd[cmd.index("--edit-format") + 1], "udiff")
        self.assertEqual(cmd[-1], "a.jsx")

    def test_resolvers(self):
        self.assertEqual(resolve_coder_engine({}), "aider")
        self.assertEqual(resolve_coder_engine({"CODER_ENGINE": " OpenCode "}), "opencode")
        self.assertEqual(resolve_coder_timeout({}), 120)
        self.assertEqual(resolve_coder_timeout({"CODER_TIMEOUT_SECONDS": "300"}), 300)
        self.assertEqual(resolve_coder_edit_format({}), "diff")
        self.assertEqual(resolve_coder_edit_format({"CODER_EDIT_FORMAT": "whole"}), "whole")
        with self.assertRaises(PlannerConfigurationError):
            resolve_coder_engine({"CODER_ENGINE": "bogus"})
        for bad in ("abc", "0", "-5"):
            with self.assertRaises(PlannerConfigurationError):
                resolve_coder_timeout({"CODER_TIMEOUT_SECONDS": bad})
        with self.assertRaises(PlannerConfigurationError):
            resolve_coder_edit_format({"CODER_EDIT_FORMAT": "bogus"})

    def test_opencode_stub(self):
        self.assertEqual(build_opencode_command(LOCAL, "task"),
                         ["opencode", "run", "--model", "ollama/qwen2.5-coder:7b", "--format", "json", "task"])
        cloud = PlannerProvider(name="openai", model="gpt-x", api_key="k")
        self.assertEqual(build_opencode_command(cloud, "t")[3], "openai/gpt-x")
        with self.assertRaisesRegex(CoderEngineNotImplemented, "not implemented yet"):
            build_coder_command("opencode", LOCAL, "t", [])
        with patch.dict(os.environ, {"AIDER_BIN": "/opt/aider/bin/aider"}):
            self.assertEqual(build_coder_command("aider", LOCAL, "t", ["f"])[0], "/opt/aider/bin/aider")

    def test_aider_bin_resolution(self):
        self.assertEqual(aider.resolve_aider_bin({"AIDER_BIN": " /x/aider "}), "/x/aider")
        with patch.object(aider, "AIDER_VENV_BIN", pathlib.Path("/nonexistent/aider")):
            self.assertEqual(aider.resolve_aider_bin({}), "aider")
        with tempfile.TemporaryDirectory() as d:
            fake = pathlib.Path(d) / "aider"
            fake.write_text("")
            with patch.object(aider, "AIDER_VENV_BIN", fake):
                self.assertEqual(aider.resolve_aider_bin({}), str(fake))


class TempAppCase(unittest.TestCase):
    """Patches the app, repo and plans locations to a temp directory."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = self.tmp / "repo"
        self.app = self.root / "generated-app"
        self.src = self.app / "src"
        self.src.mkdir(parents=True)
        (self.src / "App.jsx").write_text(APP_JSX)
        (self.src / "util.js").write_text("export const a = 1;\n")
        (self.app / "index.html").write_text("<html></html>")
        self.plans = self.tmp / "plans"
        for name, value in (("REPO_ROOT", self.root), ("APP_ROOT", self.app),
                            ("APP_SRC", self.src), ("PLANS_DIR", self.plans)):
            p = patch.object(config, name, value)
            p.start()
            self.addCleanup(p.stop)
        env = patch.dict(os.environ, OLLAMA_ENV, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.before = dict(jobs)
        self.addCleanup(self._restore_jobs)

    def _restore_jobs(self):
        jobs.clear()
        jobs.update(self.before)

    def make_job(self, job_id, tasks, statuses=None, status="planned", created="2024-01-01T00:00:00"):
        n = len(tasks)
        jobs[job_id] = {
            "id": job_id, "status": status, "prompt": "p", "plan": "## Tasks\n" + "\n".join(
                f"{i+1}) {t}" for i, t in enumerate(tasks)),
            "tasks": tasks, "current_task": -1,
            "task_statuses": statuses or ["pending"] * n, "task_logs": [""] * n,
            "task_costs": [""] * n, "task_errors": [""] * n, "created_at": created, "error": None,
        }
        return job_id


JOB_A = "00000000-0000-0000-0000-00000000000a"
JOB_B = "00000000-0000-0000-0000-00000000000b"
JOB_C = "00000000-0000-0000-0000-00000000000c"


def fake_aider(app_src, behaviors):
    """Returns a subprocess.run replacement that edits App.jsx per call, then returns a result."""
    calls = []

    def run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        n = len(calls)
        action = behaviors[n - 1]
        if action.get("edit"):
            (app_src / "App.jsx").write_text(action["edit"])
        if action.get("new_file"):
            (app_src / action["new_file"]).write_text("new")
        if action.get("timeout"):
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"], output=action.get("stdout"),
                                            stderr=action.get("stderr"))
        return SimpleNamespace(returncode=action.get("rc", 0), stdout=action.get("stdout", ""),
                               stderr=action.get("stderr", ""))
    run.calls = calls
    return run


class PersistenceTests(TempAppCase):
    def test_round_trip_and_restart_fixups(self):
        self.make_job(JOB_A, ["t1", "t2"], ["done", "pending"], status="planned")
        self.make_job(JOB_B, ["t1", "t2"], ["done", "running"], status="running")
        self.make_job(JOB_C, ["t1"], ["pending"], status="queued")
        for jid in (JOB_A, JOB_B, JOB_C):
            save_job(jid)
        saved_a = json.loads((self.plans / f"{JOB_A}.json").read_text())
        jobs.clear()
        (self.plans / "garbage.json").write_text("{}")
        (self.plans / f"{JOB_A[:-1]}z.json").write_text("{not json")
        load_jobs()
        self.assertEqual(jobs[JOB_A]["tasks"], saved_a["tasks"])
        self.assertEqual(jobs[JOB_A]["task_statuses"], ["done", "pending"])
        self.assertEqual(jobs[JOB_B]["status"], "failed")
        self.assertEqual(jobs[JOB_B]["task_statuses"], ["done", "failed"])
        self.assertIn("Controller restarted while task 2 was running", jobs[JOB_B]["error"])
        self.assertEqual(jobs[JOB_C]["status"], "planned")
        self.assertEqual(set(jobs), {JOB_A, JOB_B, JOB_C})
        # Fixups were persisted too.
        self.assertEqual(json.loads((self.plans / f"{JOB_B}.json").read_text())["status"], "failed")

    def test_plan_endpoint_writes_plan_file_and_leaves_queue_empty(self):
        class Q:
            items = []

            async def put(self, item):
                self.items.append(item)

        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
            create=lambda **kw: SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=USER_OUTPUT))]))))
        q = Q()
        with patch.object(planner_routes, "create_planner_client", return_value=fake_client), \
                patch.object(planner_routes, "planner_user_msg", return_value="x"), patch.object(state, "job_queue", q):
            result = asyncio.run(planner_routes.plan(PlanRequest(prompt="cube green")))
        self.assertEqual(result["status"], "planned")
        self.assertEqual(len(result["tasks"]), 1)
        self.assertEqual(q.items, [])
        stored = json.loads((self.plans / f"{result['job_id']}.json").read_text())
        self.assertEqual(stored["status"], "planned")
        self.assertEqual(stored["task_statuses"], ["pending"])


class RevertTests(TempAppCase):
    def test_file_level_revert_leaves_other_files_alone(self):
        outside = self.app / "notes.txt"
        outside.write_text("keep me")
        snap = snapshot_task_scope()
        (self.src / "App.jsx").write_text("broken")
        (self.src / "util.js").unlink()
        (self.src / "new.jsx").write_text("x")
        outside.write_text("changed after snapshot")
        revert_task(snap)
        self.assertEqual((self.src / "App.jsx").read_text(), APP_JSX)
        self.assertEqual((self.src / "util.js").read_text(), "export const a = 1;\n")
        self.assertFalse((self.src / "new.jsx").exists())
        self.assertEqual(outside.read_text(), "changed after snapshot")

    @unittest.skipUnless(shutil.which("git"), "git required")
    def test_git_head_reset_keeps_unrelated_uncommitted_work(self):
        def git(*args):
            return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                                  cwd=self.app, capture_output=True, text=True, check=True)
        git("init")
        git("add", ".")
        git("commit", "-m", "base")
        base = git("rev-parse", "HEAD").stdout.strip()
        (self.app / "scratch.txt").write_text("uncommitted, unrelated")
        snap = snapshot_task_scope()
        self.assertEqual(snap["head"], base)
        (self.src / "App.jsx").write_text("changed by aider")
        git("commit", "-am", "aider commit")
        revert_task(snap)
        self.assertEqual(git("rev-parse", "HEAD").stdout.strip(), base)
        self.assertEqual((self.src / "App.jsx").read_text(), APP_JSX)
        self.assertEqual((self.app / "scratch.txt").read_text(), "uncommitted, unrelated")
        self.assertEqual(git("status", "--porcelain").stdout.strip(), "?? scratch.txt")

    def test_never_uses_checkout_everything(self):
        self.make_job(JOB_A, ["t1"])
        fake = fake_aider(self.src, [{"rc": 1, "stderr": "boom", "edit": "x"}])
        with patch.object(subprocess, "run", fake):
            asyncio.run(run_job(JOB_A))
        for cmd, _ in fake.calls:
            self.assertNotEqual(cmd[:2], ["git", "checkout"])
        self.assertNotIn("checkout", inspect.getsource(revert_task))
        self.assertNotIn('"checkout"', controller_source())


@unittest.skipUnless(shutil.which("git"), "git required")
class ControllerCommitTests(TempAppCase):
    def git(self, *args):
        return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                              cwd=self.app, capture_output=True, text=True, check=True)

    def setUp(self):
        super().setUp()
        self.git("init")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        self.git("add", ".")
        self.git("commit", "-m", "base")

    def test_aider_never_commits_itself(self):
        cmd = build_aider_command(LOCAL, "do it", ["a.jsx"])
        self.assertIn("--no-auto-commits", cmd)
        self.assertIn("--no-dirty-commits", cmd)
        self.assertIn("--no-show-model-warnings", cmd)
        settings = pathlib.Path(cmd[cmd.index("--model-settings-file") + 1])
        self.assertTrue(settings.exists())
        self.assertIn("- name: gpt-6-luna\n  use_temperature: false", settings.read_text())

    def test_commit_task_commits_only_the_task_files(self):
        (self.app / "scratch.txt").write_text("unrelated, uncommitted")
        snap = snapshot_task_scope()
        (self.src / "App.jsx").write_text(APP_JSX + "// green\n")
        (self.src / "new.jsx").write_text("export default 1;\n")
        note = workspace.commit_task(snap, "Task 1/1: make it green")
        self.assertIn("committed 2 file(s)", note)
        self.assertEqual(self.git("log", "-1", "--format=%s").stdout.strip(), "Task 1/1: make it green")
        changed = set(self.git("show", "--name-only", "--format=", "HEAD").stdout.split())
        self.assertEqual(changed, {"src/App.jsx", "src/new.jsx"})
        self.assertEqual(self.git("status", "--porcelain").stdout.strip(), "?? scratch.txt")

    def test_commit_task_with_no_changes(self):
        snap = snapshot_task_scope()
        self.assertEqual(workspace.commit_task(snap, "Task 1/1: nothing"), "no file changes to commit")

    def test_hygiene_untracks_node_modules_but_keeps_files(self):
        nm = self.app / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("x")
        self.git("add", "-f", "node_modules")
        self.git("commit", "-m", "track node_modules")
        self.assertEqual(workspace.ensure_app_repo_hygiene(), "untracked build artifacts")
        self.assertEqual(self.git("ls-files", "node_modules").stdout.strip(), "")
        self.assertTrue((nm / "index.js").exists())
        self.assertIn("node_modules/", (self.app / ".gitignore").read_text())
        self.assertEqual(workspace.ensure_app_repo_hygiene(), "")  # idempotent

    def test_successful_run_commits_with_task_title(self):
        self.make_job(JOB_A, ["make the cube green"])
        fake = fake_aider(self.src, [{"edit": APP_JSX + "// green\n"}])
        real_run = subprocess.run

        def run(cmd, **kwargs):
            if cmd and cmd[0] == "git":
                return real_run(cmd, **kwargs)
            return fake(cmd, **kwargs)
        with patch.object(subprocess, "run", run):
            asyncio.run(run_job(JOB_A))
        self.assertEqual(jobs[JOB_A]["status"], "done")
        self.assertEqual(self.git("log", "-1", "--format=%s").stdout.strip(),
                         "Task 1/1: make the cube green")
        self.assertIn("committed 1 file(s)", jobs[JOB_A]["task_logs"][0])


class StreamingTests(TempAppCase):
    """The task log fills in while the coder runs, not only when it exits."""

    def test_output_is_visible_before_the_coder_finishes(self):
        import threading
        import time
        self.make_job(JOB_A, ["t1"])
        seen_mid_run = []

        def run(cmd, **kwargs):
            log = kwargs["stdout"]
            self.assertEqual(kwargs["stderr"], subprocess.STDOUT)
            self.assertEqual(kwargs["env"]["PYTHONUNBUFFERED"], "1")
            log.write("Applying edit to src/App.jsx\n")
            log.flush()
            deadline = time.time() + 3
            while time.time() < deadline and "Applying edit" not in jobs[JOB_A]["task_logs"][0]:
                time.sleep(0.05)
            seen_mid_run.append(jobs[JOB_A]["task_logs"][0])
            (self.src / "App.jsx").write_text(APP_JSX.replace("hello", "green"))
            log.write("Applied edit to src/App.jsx\n")
            return SimpleNamespace(returncode=0, stdout=None, stderr=None)

        import controller.worker as worker_module
        with patch.object(worker_module, "STREAM_POLL_SECONDS", 0.05), patch.object(subprocess, "run", run):
            asyncio.run(run_job(JOB_A))
        self.assertIn("Applying edit to src/App.jsx", seen_mid_run[0])
        job = jobs[JOB_A]
        self.assertEqual(job["task_statuses"], ["done"])
        self.assertIn("Applied edit to src/App.jsx", job["task_logs"][0])

    def test_timeout_keeps_the_streamed_output(self):
        self.make_job(JOB_A, ["t1"])

        def run(cmd, **kwargs):
            kwargs["stdout"].write("model still thinking...\n")
            kwargs["stdout"].flush()
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

        with patch.object(subprocess, "run", run):
            asyncio.run(run_job(JOB_A))
        self.assertIn("timed out", jobs[JOB_A]["task_errors"][0])
        self.assertIn("model still thinking", jobs[JOB_A]["task_errors"][0])


class NoEditDetectionTests(TempAppCase):
    """Aider exits 0 even when the model call fails; such a task must not show as done."""

    def test_model_error_with_no_changes_fails_the_task_and_stops(self):
        self.make_job(JOB_A, ["make balls fall", "t2"])
        stdout = ("litellm.BadRequestError: OpenAIException - Unsupported value: 'temperature' "
                  "does not support 0 with this model.")
        fake = fake_aider(self.src, [{"stdout": stdout}])
        with patch.object(subprocess, "run", fake):
            asyncio.run(run_job(JOB_A))
        job = jobs[JOB_A]
        self.assertEqual(job["task_statuses"], ["failed", "pending"])
        self.assertEqual(job["status"], "failed")
        self.assertIn("made no changes: the model API rejected the request", job["task_errors"][0])
        self.assertIn("temperature", job["task_errors"][0])
        self.assertEqual(len(fake.calls), 1)

    def test_search_mismatch_with_no_changes_fails(self):
        self.make_job(JOB_A, ["t1"])
        fake = fake_aider(self.src, [{"stdout": "This SEARCH block failed to exactly match lines in src/App.jsx"}])
        with patch.object(subprocess, "run", fake):
            asyncio.run(run_job(JOB_A))
        self.assertIn("SEARCH block did not match", jobs[JOB_A]["task_errors"][0])

    def test_clean_no_change_task_is_still_done(self):
        # e.g. a "verify the controls still work" task legitimately edits nothing.
        self.make_job(JOB_A, ["verify the controls still work"])
        fake = fake_aider(self.src, [{"stdout": "Everything already works; no changes needed."}])
        with patch.object(subprocess, "run", fake):
            asyncio.run(run_job(JOB_A))
        self.assertEqual(jobs[JOB_A]["task_statuses"], ["done"])

    def test_partial_edit_after_aider_gives_up_is_failed_and_reverted(self):
        self.make_job(JOB_A, ["spawn balls", "t2"])
        fake = fake_aider(self.src, [{"edit": APP_JSX.replace("hello", "half done"),
                                       "stdout": "Applied edit to src/App.jsx\n"
                                                 "SEARCH block failed to exactly match lines in src/App.jsx\n"
                                                 "Only 3 reflections allowed, stopping."}])
        with patch.object(subprocess, "run", fake):
            asyncio.run(run_job(JOB_A))
        job = jobs[JOB_A]
        self.assertEqual(job["task_statuses"], ["failed", "pending"])
        self.assertIn("only partly applied", job["task_errors"][0])
        self.assertEqual((self.src / "App.jsx").read_text(), APP_JSX)  # half edit reverted

    def test_prompt_forbids_placeholders_in_search_blocks(self):
        from controller.worker import build_task_prompt
        self.make_job(JOB_A, ["t1"])
        prompt = build_task_prompt(jobs[JOB_A], 0)
        self.assertIn("Never write '...'", prompt)
        self.assertIn("Keep each SEARCH block short", prompt)

    def test_error_text_but_edit_applied_is_done(self):
        # A first SEARCH block can miss and a retry can still apply the edit.
        self.make_job(JOB_A, ["t1"])
        fake = fake_aider(self.src, [{"edit": APP_JSX.replace("hello", "green"),
                                       "stdout": "SEARCH block failed to exactly match ... Applied edit to src/App.jsx"}])
        with patch.object(subprocess, "run", fake):
            asyncio.run(run_job(JOB_A))
        self.assertEqual(jobs[JOB_A]["task_statuses"], ["done"])


class RunJobTests(TempAppCase):
    def test_aider_command_flags_and_timeout(self):
        self.make_job(JOB_A, ["t1"])
        fake = fake_aider(self.src, [{}])
        with patch.object(subprocess, "run", fake):
            asyncio.run(run_job(JOB_A))
        cmd, kwargs = fake.calls[0]
        self.assertEqual(cmd[cmd.index("--edit-format") + 1], "diff")
        self.assertEqual(kwargs["timeout"], 120)
        self.assertIn("YOUR TASK, step 1 of 1:\n  t1", cmd[cmd.index("--message") + 1])
        self.assertEqual(jobs[JOB_A]["status"], "done")

    def test_task_prompt_is_scoped_to_one_task(self):
        from controller.worker import build_task_prompt
        self.make_job(JOB_A, ["add click handler", "add gravity", "clean up listeners"],
                      ["done", "pending", "pending"])
        jobs[JOB_A]["plan"] = "## Tasks\n1) add click handler\n2) add gravity\n3) clean up listeners\n## Acceptance"
        prompt = build_task_prompt(jobs[JOB_A], 1)
        self.assertIn("YOUR TASK, step 2 of 3:\n  add gravity", prompt)
        self.assertIn("Already done (these changes are in the files; do not redo them):\n  - Task 1: add click handler",
                      prompt)
        self.assertIn("Later steps (do NOT implement any of these now; they are done separately):\n"
                      "  - Task 3: clean up listeners", prompt)
        self.assertIn("smallest change", prompt)
        self.assertNotIn("## Acceptance", prompt)  # the full plan text is not included
        last = build_task_prompt(jobs[JOB_A], 2)
        self.assertNotIn("Later steps", last)

    def test_configured_timeout_and_edit_format(self):
        self.make_job(JOB_A, ["t1"])
        fake = fake_aider(self.src, [{}])
        with patch.dict(os.environ, {"CODER_TIMEOUT_SECONDS": "45", "CODER_EDIT_FORMAT": "udiff"}), \
                patch.object(subprocess, "run", fake):
            asyncio.run(run_job(JOB_A))
        cmd, kwargs = fake.calls[0]
        self.assertEqual(kwargs["timeout"], 45)
        self.assertEqual(cmd[cmd.index("--edit-format") + 1], "udiff")

    def test_failure_stops_reverts_only_that_task_and_surfaces_error(self):
        self.make_job(JOB_A, ["t1", "t2", "t3"])
        edited = APP_JSX.replace("hello", "task one")
        fake = fake_aider(self.src, [
            {"edit": edited, "stdout": "ok"},
            {"edit": "garbage", "new_file": "extra.jsx", "rc": 1, "stderr": "aider exploded", "stdout": "last words"},
        ])
        with patch.object(subprocess, "run", fake):
            asyncio.run(run_job(JOB_A))
        job = jobs[JOB_A]
        self.assertEqual(job["task_statuses"], ["done", "failed", "pending"])
        self.assertEqual(job["status"], "failed")
        self.assertEqual((self.src / "App.jsx").read_text(), edited)
        self.assertFalse((self.src / "extra.jsx").exists())
        self.assertIn("aider exploded", job["error"])
        self.assertIn("last words", job["error"])
        self.assertEqual(job["task_errors"][1], job["error"])
        self.assertIn("Reverted this task's changes", job["task_logs"][1])
        self.assertEqual(len(fake.calls), 2)
        stored = json.loads((self.plans / f"{JOB_A}.json").read_text())
        self.assertEqual(stored["task_statuses"], ["done", "failed", "pending"])

    def test_timeout_message_with_partial_output(self):
        for partial in ("partial out", b"partial bytes"):
            with self.subTest(partial=partial):
                self.make_job(JOB_A, ["t1"])
                fake = fake_aider(self.src, [{"timeout": True, "stderr": partial, "edit": "half written"}])
                with patch.dict(os.environ, {"CODER_TIMEOUT_SECONDS": "7"}), patch.object(subprocess, "run", fake):
                    asyncio.run(run_job(JOB_A))
                job = jobs[JOB_A]
                self.assertEqual(job["task_statuses"], ["failed"])
                self.assertIn("timed out after 7 s", job["error"])
                self.assertIn("partial", job["error"])
                self.assertEqual((self.src / "App.jsx").read_text(), APP_JSX)

    def test_resume_skips_done_tasks(self):
        self.make_job(JOB_A, ["t1", "t2", "t3"], ["done", "failed", "pending"], status="failed")
        fake = fake_aider(self.src, [{}, {}])
        with patch.object(subprocess, "run", fake):
            asyncio.run(run_job(JOB_A))
        self.assertEqual(len(fake.calls), 2)
        prompts = [c[0][c[0].index("--message") + 1] for c in fake.calls]
        self.assertIn("YOUR TASK, step 2 of 3:\n  t2", prompts[0])
        self.assertIn("YOUR TASK, step 3 of 3:\n  t3", prompts[1])
        self.assertIn("do not redo them):\n  - Task 1: t1", prompts[0])
        self.assertEqual(jobs[JOB_A]["task_statuses"], ["done", "done", "done"])
        self.assertEqual(jobs[JOB_A]["status"], "done")

    def test_corrupted_app_jsx_is_restored(self):
        self.make_job(JOB_A, ["t1"])
        fake = fake_aider(self.src, [{"edit": "tiny"}])
        with patch.object(subprocess, "run", fake):
            asyncio.run(run_job(JOB_A))
        self.assertEqual(jobs[JOB_A]["task_statuses"], ["failed"])
        self.assertIn("corrupted App.jsx", jobs[JOB_A]["error"])
        self.assertEqual((self.src / "App.jsx").read_text(), APP_JSX)

    def test_opencode_stub_fails_clearly_without_running_anything(self):
        self.make_job(JOB_A, ["t1"])
        with patch.dict(os.environ, {"CODER_ENGINE": "opencode"}), \
                patch.object(subprocess, "run") as run:
            asyncio.run(run_job(JOB_A))
        run.assert_not_called()
        self.assertEqual(jobs[JOB_A]["status"], "failed")
        self.assertIn("not implemented yet", jobs[JOB_A]["error"])
        self.assertIn("not implemented yet", jobs[JOB_A]["task_errors"][0])

    def test_bad_coder_config_fails_job(self):
        self.make_job(JOB_A, ["t1"])
        with patch.dict(os.environ, {"CODER_TIMEOUT_SECONDS": "nope"}), patch.object(subprocess, "run") as run:
            asyncio.run(run_job(JOB_A))
        run.assert_not_called()
        self.assertIn("CODER_TIMEOUT_SECONDS", jobs[JOB_A]["error"])


class FakeQueue:
    def __init__(self):
        self.items = []

    async def put(self, item):
        self.items.append(item)


class EndpointTests(TempAppCase):
    def setUp(self):
        super().setUp()
        self.queue = FakeQueue()
        p = patch.object(state, "job_queue", self.queue)
        p.start()
        self.addCleanup(p.stop)

    def test_execute_enqueues_once(self):
        self.make_job(JOB_A, ["t1"])
        result = asyncio.run(execute_job(JOB_A))
        self.assertEqual(result["status"], "queued")
        self.assertEqual(self.queue.items, [JOB_A])
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(execute_job(JOB_A))
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(self.queue.items, [JOB_A])

    def test_execute_rejects_done_unknown_and_empty(self):
        self.make_job(JOB_A, ["t1"], ["done"], status="done")
        self.make_job(JOB_B, [], status="planned")
        for jid, code in ((JOB_A, 409), (JOB_B, 409), (JOB_C, 404)):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(execute_job(jid))
            self.assertEqual(raised.exception.status_code, code)
        self.assertEqual(self.queue.items, [])

    def test_continue_picks_latest_resumable_and_keeps_done_tasks(self):
        self.make_job(JOB_A, ["a1", "a2"], ["done", "failed"], status="failed", created="2024-01-01T00:00:00")
        self.make_job(JOB_B, ["b1", "b2"], ["done", "failed"], status="failed", created="2024-01-02T00:00:00")
        self.make_job(JOB_C, ["c1"], ["done"], status="done", created="2024-01-03T00:00:00")
        jobs[JOB_B]["task_errors"][1] = "old error"
        result = asyncio.run(continue_plan())
        self.assertEqual(result["job_id"], JOB_B)
        self.assertEqual(self.queue.items, [JOB_B])
        self.assertEqual(jobs[JOB_B]["task_statuses"], ["done", "pending"])
        self.assertEqual(jobs[JOB_B]["task_errors"], ["", ""])
        self.assertEqual(jobs[JOB_B]["status"], "queued")

    def test_continue_without_plan_says_so(self):
        for existing, text in (({}, "No stored plan to continue"), (None, "already complete")):
            with self.subTest(text=text):
                jobs.clear()
                if existing is None:
                    self.make_job(JOB_A, ["t"], ["done"], status="done")
                with self.assertRaises(HTTPException) as raised:
                    asyncio.run(continue_plan())
                self.assertEqual(raised.exception.status_code, 404)
                self.assertIn(text, raised.exception.detail)

    def test_continue_while_running_is_409(self):
        self.make_job(JOB_A, ["t"], ["running"], status="running")
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(continue_plan())
        self.assertEqual(raised.exception.status_code, 409)

    def test_opencode_returns_501_and_queue_stays_empty(self):
        self.make_job(JOB_A, ["t1"])
        with patch.dict(os.environ, {"CODER_ENGINE": "opencode"}):
            for call in (lambda: execute_job(JOB_A), continue_plan):
                with self.assertRaises(HTTPException) as raised:
                    asyncio.run(call())
                self.assertEqual(raised.exception.status_code, 501)
                self.assertIn("not implemented yet", raised.exception.detail)
        self.assertEqual(self.queue.items, [])
        self.assertEqual(jobs[JOB_A]["status"], "planned")

    def test_generate_route_and_anthropic_are_gone(self):
        self.assertNotIn("/generate", [r.path for r in app_module.app.routes])
        source = controller_source()
        self.assertNotIn("ANTHROPIC", source)
        self.assertNotIn("claude-sonnet", source)


class UiTests(unittest.TestCase):
    def test_ui_strings(self):
        for needle in ("AUTO_START_SECONDS = 5", "/job/${", "/continue", "Continue plan",
                       "task_errors", "cancelCountdown", "click to cancel",
                       "/model-config", "configModal", "configBtn"):
            self.assertIn(needle, PHONE_UI)
        for needle in ("/generate", "claude-sonnet", "Generate"):
            self.assertNotIn(needle, PHONE_UI.replace("Generated app", "").replace("generated app", "")
                             .replace("generated-app", ""))

    @unittest.skipUnless(shutil.which("node"), "node required")
    def test_script_is_valid_javascript(self):
        script = re.search(r"<script>(.*)</script>", PHONE_UI, re.S).group(1)
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "ui.js"
            path.write_text(script)
            result = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
