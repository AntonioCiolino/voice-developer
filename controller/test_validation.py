import asyncio
import os
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import controller.test_plan_flow as tpf
from controller import state, validation
from controller.coder import resolve_task_validation, resolve_validation_timeout
from controller.providers import PlannerConfigurationError
from controller.validation import lint_targets, validate_app
from controller.worker import build_task_prompt, run_job
from controller.workspace import snapshot_task_scope


class ResolverTests(unittest.TestCase):
    def test_checks(self):
        self.assertEqual(resolve_task_validation({}), {"build", "lint"})
        self.assertEqual(resolve_task_validation({"TASK_VALIDATION": "off"}), set())
        self.assertEqual(resolve_task_validation({"TASK_VALIDATION": "lint"}), {"lint"})
        self.assertEqual(resolve_task_validation({"TASK_VALIDATION": "Build, lint"}), {"build", "lint"})
        with self.assertRaises(PlannerConfigurationError):
            resolve_task_validation({"TASK_VALIDATION": "build,test"})

    def test_timeout(self):
        self.assertEqual(resolve_validation_timeout({}), 120)
        self.assertEqual(resolve_validation_timeout({"VALIDATION_TIMEOUT_SECONDS": "30"}), 30)
        for bad in ("abc", "0", "-5"):
            with self.assertRaises(PlannerConfigurationError):
                resolve_validation_timeout({"VALIDATION_TIMEOUT_SECONDS": bad})


class ValidateAppTests(tpf.TempAppCase):
    def setUp(self):
        super().setUp()
        self.tools = self.tmp / "lint-tools"
        for exe in (self.app / "node_modules" / ".bin" / "vite", self.tools / "node_modules" / ".bin" / "eslint"):
            exe.parent.mkdir(parents=True)
            exe.write_text("")
        p = patch.object(validation, "lint_tools_dir", lambda: self.tools)
        p.start()
        self.addCleanup(p.stop)
        p = patch.object(validation.shutil, "which", lambda name: "/usr/bin/node")
        p.start()
        self.addCleanup(p.stop)
        self.snap = snapshot_task_scope()
        self.logs = []
        self.runs = []

    def fake_run(self, build=(0, ""), lint=(0, ""), timeout_on=None):
        def run(cmd, **kwargs):
            self.runs.append((cmd, kwargs))
            kind = "build" if cmd[0].endswith("vite") else "lint"
            if timeout_on == kind:
                raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
            rc, err = build if kind == "build" else lint
            return SimpleNamespace(returncode=rc, stdout="", stderr=err)
        return patch.object(validation.subprocess, "run", run)

    def validate(self, checks=("build", "lint")):
        return validate_app(self.snap, set(checks), 7, self.logs.append)

    def change(self):
        (self.src / "App.jsx").write_text(tpf.APP_JSX + "// changed\n")
        (self.src / "New.jsx").write_text("export default function New(){return null}\n")

    def test_pass_runs_both_and_logs(self):
        self.change()
        with self.fake_run():
            self.assertEqual(self.validate(), [])
        self.assertEqual(len(self.runs), 2)
        self.assertEqual(self.logs, ["Validating: build (vite)...", "build passed",
                                     "Validating: lint (eslint, 2 file(s))...", "lint passed"])
        self.assertEqual(self.runs[0][1]["timeout"], 7)

    def test_build_uses_temp_outdir_and_leaves_app_untouched(self):
        self.change()
        before = sorted((p.relative_to(self.app).as_posix(), p.read_bytes())
                        for p in self.app.rglob("*") if p.is_file())
        with self.fake_run():
            self.validate(["build"])
        cmd = self.runs[0][0]
        outdir = cmd[cmd.index("--outDir") + 1]
        self.assertFalse(outdir.startswith(str(self.app)))
        self.assertEqual(self.runs[0][1]["cwd"], str(self.app))
        after = sorted((p.relative_to(self.app).as_posix(), p.read_bytes())
                       for p in self.app.rglob("*") if p.is_file())
        self.assertEqual(before, after)
        self.assertFalse((self.app / "dist").exists())

    def test_build_failure(self):
        self.change()
        with self.fake_run(build=(1, "Could not resolve ./Missing")):
            failures = self.validate()
        self.assertEqual([name for name, _ in failures], ["build"])
        self.assertIn("Could not resolve", failures[0][1])
        self.assertIn("build FAILED", self.logs)
        self.assertEqual(len(self.runs), 2)  # lint still ran

    def test_lint_failure(self):
        self.change()
        with self.fake_run(lint=(1, "'updateBallPhysics' is not defined  no-undef")):
            failures = self.validate()
        self.assertEqual([name for name, _ in failures], ["lint"])
        self.assertIn("no-undef", failures[0][1])
        self.assertIn("lint FAILED", self.logs)

    def test_lint_gets_only_existing_changed_source_files(self):
        (self.src / "util.js").unlink()
        (self.src / "App.jsx").write_text(tpf.APP_JSX + "// c\n")
        (self.src / "styles.css").write_text("a{}")
        (self.app / "package.json").write_text("{}")
        self.assertEqual(lint_targets(self.snap), ["src/App.jsx"])
        with self.fake_run():
            self.validate()
        lint_cmd = self.runs[1][0]
        self.assertEqual(lint_cmd[-1], "src/App.jsx")
        self.assertIn(str(self.tools / "eslint.config.js"), lint_cmd)
        self.assertEqual(len(self.runs), 2)  # build ran because package.json changed too

    def test_no_changes_runs_nothing(self):
        with self.fake_run():
            self.assertEqual(self.validate(), [])
        self.assertEqual(self.runs, [])
        self.assertEqual(self.logs, ["Validation skipped: no files changed"])

    def test_only_enabled_checks_run(self):
        self.change()
        with self.fake_run():
            self.validate(["lint"])
        self.assertEqual(len(self.runs), 1)
        with self.fake_run():
            self.assertEqual(self.validate([]), [])

    def test_missing_tools_skip_with_log(self):
        self.change()
        (self.app / "node_modules" / ".bin" / "vite").unlink()
        (self.tools / "node_modules" / ".bin" / "eslint").unlink()
        with self.fake_run():
            self.assertEqual(self.validate(), [])
        self.assertEqual(self.runs, [])
        self.assertTrue(all("run ./setup.sh" in line for line in self.logs))
        self.assertEqual(len(self.logs), 2)

    def test_missing_node_skips(self):
        self.change()
        with patch.object(validation.shutil, "which", lambda name: None), self.fake_run():
            self.assertEqual(self.validate(), [])
        self.assertEqual(self.runs, [])

    def test_timeout_is_a_failure(self):
        self.change()
        with self.fake_run(timeout_on="build"):
            failures = self.validate(["build"])
        self.assertIn("build timed out after 7 s (VALIDATION_TIMEOUT_SECONDS)", failures[0][1])


class RunJobValidationTests(tpf.TempAppCase):
    EDIT1 = tpf.APP_JSX + "// attempt 1\n"
    EDIT2 = tpf.APP_JSX + "// attempt 2\n"

    def run_with(self, behaviors, results, env=None):
        self.make_job(tpf.JOB_A, ["t1", "t2"])
        fake = tpf.fake_aider(self.src, behaviors)
        calls = []
        results = list(results)

        def fake_validate(snapshot, checks, timeout, log):
            calls.append(checks)
            log("Validating: build (vite)...")
            return results.pop(0)
        with patch.dict(os.environ, env or {}), patch.object(subprocess, "run", fake), \
                patch("controller.worker.validate_app", fake_validate):
            asyncio.run(run_job(tpf.JOB_A))
        return state.jobs[tpf.JOB_A], fake, calls

    def test_pass_commits_and_continues(self):
        job, fake, calls = self.run_with([{"edit": self.EDIT1}, {"edit": self.EDIT2}], [[], []])
        self.assertEqual(job["status"], "done")
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual(len(calls), 2)
        self.assertIn("Validating: build (vite)...", job["task_logs"][0])

    def test_one_retry_with_error_in_prompt(self):
        err = "Could not resolve ./updateBallPhysics"
        job, fake, _ = self.run_with(
            [{"edit": self.EDIT1, "stdout": "Cost: $0.01 message, $0.01 session."}, {"edit": self.EDIT2},
             {"edit": self.EDIT2}],
            [[("build", err)], [], []])
        self.assertEqual(job["task_statuses"][:1], ["done"])
        first, second = fake.calls[0][0], fake.calls[1][0]
        self.assertNotIn("previous attempt", " ".join(first))
        self.assertIn("previous attempt", " ".join(second))
        self.assertIn(err, " ".join(second))
        self.assertIn("Validation failed, retrying once", job["task_logs"][0])
        self.assertEqual((self.src / "App.jsx").read_text(), self.EDIT2)  # no revert between attempts

    def test_final_failure_reverts_and_stops(self):
        job, fake, _ = self.run_with(
            [{"edit": self.EDIT1, "new_file": "New.jsx"}, {"edit": self.EDIT2}],
            [[("build", "err one")], [("lint", "'foo' is not defined")]])
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["task_statuses"], ["failed", "pending"])
        self.assertIn("failed validation (lint)", job["task_errors"][0])
        self.assertIn("'foo' is not defined", job["task_errors"][0])
        self.assertEqual((self.src / "App.jsx").read_text(), tpf.APP_JSX)
        self.assertFalse((self.src / "New.jsx").exists())
        self.assertIn("Reverted this task's changes", job["task_logs"][0])

    def test_partial_apply_fails_without_validation_or_retry(self):
        job, fake, calls = self.run_with(
            [{"edit": self.EDIT1, "stdout": "Only 3 reflections allowed, stopping."}], [])
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(calls, [])
        self.assertIn("only partly applied", job["task_errors"][0])
        self.assertEqual((self.src / "App.jsx").read_text(), tpf.APP_JSX)

    def test_timeout_on_retry_reverts_to_original(self):
        job, fake, _ = self.run_with(
            [{"edit": self.EDIT1}, {"edit": self.EDIT2, "timeout": True}], [[("build", "bad")]])
        self.assertIn("retry after validation failure", job["task_errors"][0])
        self.assertEqual((self.src / "App.jsx").read_text(), tpf.APP_JSX)

    def test_off_still_passes_checks_to_validator_as_empty(self):
        job, _, calls = self.run_with([{"edit": self.EDIT1}, {"edit": self.EDIT2}], [[], []],
                                      {"TASK_VALIDATION": "off"})
        self.assertEqual(calls, [set(), set()])
        self.assertEqual(job["status"], "done")

    def test_invalid_setting_fails_job(self):
        job, fake, _ = self.run_with([], [], {"TASK_VALIDATION": "nope"})
        self.assertEqual(job["status"], "failed")
        self.assertIn("TASK_VALIDATION", job["error"])
        self.assertEqual(fake.calls, [])

    def test_no_change_task_passes_with_real_validator(self):
        self.make_job(tpf.JOB_A, ["t1"])
        with patch.object(subprocess, "run", tpf.fake_aider(self.src, [{}])):
            asyncio.run(run_job(tpf.JOB_A))
        job = state.jobs[tpf.JOB_A]
        self.assertEqual(job["task_statuses"], ["done"])
        self.assertIn("Validation skipped: no files changed", job["task_logs"][0])

    def test_prompt_fix_block(self):
        self.make_job(tpf.JOB_A, ["t1"])
        self.assertNotIn("previous attempt", build_task_prompt(state.jobs[tpf.JOB_A], 0))
        self.assertIn("boom", build_task_prompt(state.jobs[tpf.JOB_A], 0, validation_errors="boom"))


if __name__ == "__main__":
    unittest.main()
