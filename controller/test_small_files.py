import asyncio
import os
import shutil
import subprocess
import unittest
from unittest.mock import patch

import controller.test_plan_flow as tpf
from controller import config, state
from controller.coder import build_aider_command, resolve_coder_edit_format, resolve_max_file_lines
from controller.planning import parse_task_files, planner_system_prompt
from controller.providers import PlannerConfigurationError, PlannerProvider
from controller.worker import build_task_prompt, run_job
from controller.workspace import (
    changed_task_paths, commit_task, over_limit_files, revert_task, snapshot_task_scope,
    task_scope_files,
)

LOCAL_LM = PlannerProvider(name="lmstudio", model="qwen2.5-coder-7b-instruct",
                           lmstudio_api_base="http://127.0.0.1:1234")
CLOUD_OLLAMA = PlannerProvider(name="ollama", model="gpt-oss:120b-cloud",
                               ollama_api_base="http://127.0.0.1:11434")
CLOUD = PlannerProvider(name="openai", model="gpt-5.4-mini", api_key="k")


class PlannerPromptTests(unittest.TestCase):
    def test_prompt_demands_small_files_and_file_lists(self):
        prompt = planner_system_prompt(150)
        self.assertIn("under 150 lines", prompt)
        self.assertIn("one component or module per file", prompt)
        self.assertIn("NEW files", prompt)
        self.assertIn("[files:", prompt)
        self.assertNotIn("{MAX_LINES}", prompt)
        self.assertIn("under 80 lines", planner_system_prompt(80))


class ParseTaskFilesTests(unittest.TestCase):
    def test_formats_and_normalization(self):
        self.assertEqual(parse_task_files("Add timer [files: src/components/Timer.jsx, src/App.jsx]"),
                         ["src/components/Timer.jsx", "src/App.jsx"])
        self.assertEqual(parse_task_files("x (Files: `./src/a.js`, generated-app/src/b.js, src/a.js)"),
                         ["src/a.js", "src/b.js"])
        self.assertEqual(parse_task_files("x [files: index.html package.json]"), ["index.html", "package.json"])

    def test_unsafe_or_out_of_scope_paths_dropped(self):
        task = "x [files: ../secret.js, /etc/passwd, src/../../x.js, src/logo.png, README.md, node_modules/a.js, src//a.js]"
        self.assertEqual(parse_task_files(task), [])

    def test_no_files_gives_empty(self):
        self.assertEqual(parse_task_files("Change the color"), [])
        self.assertEqual(parse_task_files(""), [])


class ScopeTests(tpf.TempAppCase):
    def setUp(self):
        super().setUp()
        (self.src / "components").mkdir()
        (self.src / "components" / "Timer.jsx").write_text("export default function Timer(){return null}\n")
        (self.src / "App.jsx").write_text("import Timer from './components/Timer'\nexport default function App(){}\n")
        (self.src / "other.js").write_text("export const z = 1\n")
        (self.app / "package.json").write_text("{}")

    def rel(self, files):
        return sorted(f.relative_to(self.app).as_posix() for f in files)

    def test_named_file_plus_importers(self):
        files = task_scope_files(["src/components/Timer.jsx"])
        self.assertEqual(self.rel(files), ["src/App.jsx", "src/components/Timer.jsx"])
        self.assertNotIn("src/other.js", self.rel(files))
        self.assertNotIn("package.json", self.rel(files))

    def test_new_file_is_in_scope_and_named_wiring_file_is_kept(self):
        files = task_scope_files(["src/components/Clock.jsx", "src/App.jsx"])
        self.assertEqual(self.rel(files), ["src/App.jsx", "src/components/Clock.jsx"])

    def test_fallback_without_names_is_whole_scope(self):
        self.assertEqual(self.rel(task_scope_files([])),
                         ["index.html", "package.json", "src/App.jsx", "src/components/Timer.jsx",
                          "src/other.js", "src/util.js"])

    def test_snapshot_still_covers_everything_and_new_src_files(self):
        snap = snapshot_task_scope()
        self.assertEqual(set(snap["files"]), {"index.html", "package.json", "src/App.jsx",
                                              "src/components/Timer.jsx", "src/other.js", "src/util.js"})

    def test_revert_and_commit_stay_inside_scope(self):
        snap = snapshot_task_scope()
        outside = self.app / "notes.txt"
        outside.write_text("mine")
        (self.src / "other.js").write_text("export const z = 2\n")   # not named, but in snapshot scope
        (self.src / "components" / "New.jsx").write_text("x")
        revert_task(snap)
        self.assertEqual((self.src / "other.js").read_text(), "export const z = 1\n")
        self.assertFalse((self.src / "components" / "New.jsx").exists())
        self.assertEqual(outside.read_text(), "mine")
        outside.write_text("changed")
        (self.src / "components" / "New.jsx").write_text("x")
        self.assertEqual(sorted(changed_task_paths(snap)), ["src/components/New.jsx"])

    @unittest.skipUnless(shutil.which("git"), "git required")
    def test_commit_only_touches_task_paths(self):
        def git(*a):
            return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a],
                                  cwd=self.app, capture_output=True, text=True, check=True)
        git("init"); git("add", "."); git("commit", "-m", "base")
        snap = snapshot_task_scope()
        (self.app / "notes.txt").write_text("unrelated")
        (self.src / "components" / "New.jsx").write_text("x")
        commit_task(snap, "t")
        shown = git("show", "--name-only", "--format=", "HEAD").stdout.split()
        self.assertEqual(shown, ["src/components/New.jsx"])


class LineLimitTests(tpf.TempAppCase):
    def test_only_changed_files_over_limit_reported(self):
        (self.src / "util.js").write_text("a\n" * 200)    # already oversized, snapshot taken after
        snap = snapshot_task_scope()
        (self.src / "App.jsx").write_text("x\n" * 151)
        (self.src / "Big.jsx").write_text("x\n" * 150)    # exactly at limit: fine
        (self.src / "Bigger.jsx").write_text("x\n" * 151)
        over = over_limit_files(snap, 150)
        self.assertEqual(sorted(over), [("src/App.jsx", 151), ("src/Bigger.jsx", 151)])
        self.assertEqual(over_limit_files(snap, 500), [])

    def test_max_file_lines_setting(self):
        self.assertEqual(resolve_max_file_lines({}), 150)
        self.assertEqual(resolve_max_file_lines({"MAX_FILE_LINES": "90"}), 90)
        for bad in ("abc", "0", "-1"):
            with self.assertRaises(PlannerConfigurationError):
                resolve_max_file_lines({"MAX_FILE_LINES": bad})

    def test_over_limit_is_warning_on_done_task_and_edit_kept(self):
        self.make_job(tpf.JOB_A, ["t1 [files: src/App.jsx]"])
        big = tpf.APP_JSX + "// x\n" * 160
        fake = tpf.fake_aider(self.src, [{"edit": big}])
        with patch.object(subprocess, "run", fake):
            asyncio.run(run_job(tpf.JOB_A))
        job = state.jobs[tpf.JOB_A]
        self.assertEqual(job["task_statuses"], ["done"])
        self.assertIn("src/App.jsx has 162 lines", job["task_warnings"][0])
        self.assertIn("MAX_FILE_LINES=150", job["task_warnings"][0])
        self.assertEqual((self.src / "App.jsx").read_text(), big)

    def test_no_warning_when_small(self):
        self.make_job(tpf.JOB_A, ["t1"])
        with patch.object(subprocess, "run", tpf.fake_aider(self.src, [{"edit": tpf.APP_JSX + "// y\n"}])):
            asyncio.run(run_job(tpf.JOB_A))
        self.assertEqual(state.jobs[tpf.JOB_A]["task_warnings"], [""])


class EditFormatTests(tpf.TempAppCase):
    def test_default_per_provider(self):
        self.assertEqual(resolve_coder_edit_format({}, tpf.LOCAL), "whole")
        self.assertEqual(resolve_coder_edit_format({}, LOCAL_LM), "whole")
        self.assertEqual(resolve_coder_edit_format({}, CLOUD), "diff")
        self.assertEqual(resolve_coder_edit_format({}, CLOUD_OLLAMA), "diff")   # ':cloud' runs remotely
        self.assertEqual(resolve_coder_edit_format({}), "diff")

    def test_env_overrides_default(self):
        self.assertEqual(resolve_coder_edit_format({"CODER_EDIT_FORMAT": "diff"}, tpf.LOCAL), "diff")
        self.assertEqual(resolve_coder_edit_format({"CODER_EDIT_FORMAT": "whole"}, CLOUD), "whole")
        with self.assertRaises(PlannerConfigurationError):
            resolve_coder_edit_format({"CODER_EDIT_FORMAT": "bogus"}, tpf.LOCAL)

    def test_run_uses_swapped_coder_default(self):
        self.make_job(tpf.JOB_A, ["t1"])
        fake = tpf.fake_aider(self.src, [{}])
        env = {**tpf.OLLAMA_ENV, "CODER_PROVIDER": "openai", "CODER_MODEL": "gpt-5.4-mini", "OPENAI_API_KEY": "k"}
        with patch.dict(os.environ, env, clear=True), patch.object(subprocess, "run", fake):
            asyncio.run(run_job(tpf.JOB_A))
        cmd = fake.calls[0][0]
        self.assertEqual(cmd[cmd.index("--edit-format") + 1], "diff")

    def test_prompt_rules_follow_format(self):
        self.make_job(tpf.JOB_A, ["t1"])
        job = state.jobs[tpf.JOB_A]
        whole = build_task_prompt(job, 0, "whole", 150, ["generated-app/src/App.jsx"])
        diff = build_task_prompt(job, 0, "diff", 150)
        self.assertNotIn("SEARCH", whole)
        self.assertIn("in full", whole)
        self.assertIn("under 150 lines", whole)
        self.assertIn("generated-app/src/App.jsx", whole)
        self.assertIn("SEARCH", diff)


class RunScopeTests(tpf.TempAppCase):
    def test_coder_gets_only_named_files(self):
        (self.src / "other.js").write_text("export const z = 1\n")
        self.make_job(tpf.JOB_A, ["t1 [files: src/util.js, src/New.jsx]", "t2"])
        fake = tpf.fake_aider(self.src, [{"new_file": "New.jsx"}, {}])
        with patch.object(subprocess, "run", fake):
            asyncio.run(run_job(tpf.JOB_A))
        first, second = fake.calls[0][0], fake.calls[1][0]
        msg = first.index("--message") + 2
        # App-relative paths, run from the app folder: a generated-app/ prefix in the prompt got copied
        # into new file names, which then landed in generated-app/generated-app/src.
        self.assertEqual(first[msg:], ["src/util.js", "src/New.jsx"])
        self.assertEqual(fake.calls[0][1]["cwd"], str(config.APP_ROOT))
        self.assertNotIn("generated-app/", first[msg - 1])
        self.assertIn("src/util.js, src/New.jsx", first[msg - 1])
        # No named file: all src files plus config, as before.
        self.assertIn("src/App.jsx", second)
        self.assertIn("index.html", second)
        self.assertEqual(state.jobs[tpf.JOB_A]["task_statuses"], ["done", "done"])


if __name__ == "__main__":
    unittest.main()
