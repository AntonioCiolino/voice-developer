import asyncio
import json
import os
import subprocess
import unittest
from unittest.mock import patch

from fastapi import HTTPException

import controller.test_plan_flow as tpf
from controller import selection, state
from controller.coder import extract_cost_amount
from controller.escalation import UNPARSED_CLOUD_COST, estimate_cloud_cost, resolve_escalation
from controller.providers import PlannerConfigurationError, PlannerProvider, resolve_coder_provider
from controller.routes.jobs import continue_plan
from controller.store import load_jobs
from controller.worker import run_job

LADDER = "ollama:qwen2.5-coder:7b,openai:gpt-6.1-terra,openai:gpt-6.2-sol"
BASE = {"OPENAI_API_KEY": "sk-test", "OLLAMA_MODEL": "qwen2.5-coder:7b", "OLLAMA_API_BASE": "http://127.0.0.1:11434"}
LOCAL = PlannerProvider("ollama", "qwen2.5-coder:7b", ollama_api_base="http://127.0.0.1:11434")
TERRA = PlannerProvider("openai", "gpt-6.1-terra", api_key="sk-test")


def env(**extra):
    return {**BASE, "CODER_LADDER": LADDER, **extra}


class CostParsingTests(unittest.TestCase):
    def test_amounts(self):
        self.assertEqual(extract_cost_amount("Cost: $0.05 message, $0.05 session."), 0.05)
        self.assertAlmostEqual(extract_cost_amount("Cost: $0.05 message, $0.05 session.\nCost: $0.02 message, $0.07 session."), 0.07)
        self.assertEqual(extract_cost_amount("Cost: $0.00 message, $0.00 session."), 0.0)
        self.assertIsNone(extract_cost_amount("nothing here"))


class ResolveTests(unittest.TestCase):
    def test_parse_with_colons_and_defaults(self):
        esc = resolve_escalation(LOCAL, env())
        self.assertTrue(esc.active)
        self.assertEqual([r.spec for r in esc.rungs],
                         ["ollama:qwen2.5-coder:7b", "openai:gpt-6.1-terra", "openai:gpt-6.2-sol"])
        self.assertEqual((esc.mode, esc.max_plan_cost, esc.local_only), ("on", 1.0, False))

    def test_inactive_never_parses(self):
        for values in ({}, {"CODER_LADDER": ""}, {"CODER_LADDER": "garbage", "AUTO_ESCALATE": "off"}):
            esc = resolve_escalation(LOCAL, values)
            self.assertFalse(esc.active)
            self.assertEqual(len(esc.rungs), 1)

    def test_bad_ladders(self):
        for ladder in ("ollama", "foo:bar", "openai:", "ollama:a,,ollama:b", "ollama:a,ollama:a"):
            with self.subTest(ladder=ladder), self.assertRaises(PlannerConfigurationError):
                resolve_escalation(LOCAL, {**BASE, "CODER_LADDER": ladder})
        with self.assertRaises(PlannerConfigurationError) as raised:
            resolve_escalation(LOCAL, {"CODER_LADDER": "openai:gpt-6.1-terra"})
        self.assertIn("OPENAI_API_KEY", str(raised.exception))
        self.assertIn("CODER_LADDER entry 'openai:gpt-6.1-terra'", str(raised.exception))
        with self.assertRaises(PlannerConfigurationError):
            resolve_escalation(LOCAL, env(OLLAMA_API_BASE="http://example.com:11434"))

    def test_bad_settings(self):
        for bad in ({"AUTO_ESCALATE": "maybe"}, {"MAX_PLAN_COST": "abc"}, {"MAX_PLAN_COST": "0"},
                    {"MAX_PLAN_COST": "-1"}, {"ESCALATE_LOCAL_ONLY": "yes"}):
            with self.subTest(bad=bad), self.assertRaises(PlannerConfigurationError):
                resolve_escalation(LOCAL, env(**bad))

    def test_start_in_middle_and_prepended(self):
        self.assertEqual([r.label for r in resolve_escalation(TERRA, env()).rungs], ["gpt-6.1-terra", "gpt-6.2-sol"])
        other = PlannerProvider("ollama", "llama3:8b", ollama_api_base="http://127.0.0.1:11434")
        self.assertEqual([r.label for r in resolve_escalation(other, env()).rungs],
                         ["llama3:8b", "qwen2.5-coder:7b", "gpt-6.1-terra", "gpt-6.2-sol"])

    def test_local_only(self):
        ladder = LADDER + ",ollama:gpt-oss:120b-cloud,lmstudio:qwen-x"
        esc = resolve_escalation(LOCAL, {**env(ESCALATE_LOCAL_ONLY="on"), "CODER_LADDER": ladder})
        self.assertEqual([r.spec for r in esc.rungs], ["ollama:qwen2.5-coder:7b", "lmstudio:qwen-x"])
        with self.assertRaises(PlannerConfigurationError):
            resolve_escalation(TERRA, env(ESCALATE_LOCAL_ONLY="on"))


SERVER_ENV = {"ALLOW_LAN_MODEL_SERVERS": "on", "MODEL_SERVERS": "mini",
              "MODEL_SERVER_MINI_KIND": "lmstudio", "MODEL_SERVER_MINI_URL": "http://192.168.1.20:1234"}
MINI = PlannerProvider("lmstudio", "qwen3-4b", lmstudio_api_base="http://192.168.1.20:1234", server="mini", lan=True)


class ServerLadderTests(unittest.TestCase):
    LADDER = "lmstudio:a,mini:qwen3:8b,openai:gpt-6.1-terra"

    def esc(self, start=LOCAL, **extra):
        return resolve_escalation(start, {**BASE, **SERVER_ENV, "CODER_LADDER": self.LADDER, **extra})

    def test_ladder_with_server_entries(self):
        esc = self.esc()
        self.assertEqual([r.spec for r in esc.rungs],
                         ["ollama:qwen2.5-coder:7b", "lmstudio:a", "mini:qwen3:8b", "openai:gpt-6.1-terra"])
        rung = esc.rungs[2]
        self.assertEqual((rung.label, rung.provider.model, rung.provider.server), ("qwen3:8b@mini", "qwen3:8b", "mini"))
        info = rung.info()
        self.assertEqual((info["provider"], info["server"], info["location"]), ("mini", "mini", "lan"))
        self.assertNotIn("192.168", repr(esc.info()))
        self.assertEqual(esc.scope, "off")

    def test_duplicate_per_server(self):
        with self.assertRaises(PlannerConfigurationError):
            self.esc(CODER_LADDER="mini:a,mini:a")
        self.assertEqual(len(self.esc(CODER_LADDER="mini:a,lmstudio:a").rungs), 3)

    def test_unknown_server_names_the_entry(self):
        with self.assertRaises(PlannerConfigurationError) as raised:
            self.esc(CODER_LADDER="studio:a")
        self.assertIn("CODER_LADDER entry 'studio:a'", str(raised.exception))
        with self.assertRaises(PlannerConfigurationError) as raised:
            resolve_escalation(LOCAL, {**BASE, "CODER_LADDER": "mini:a"})
        self.assertIn("provider must be one of 'openai', 'ollama', or 'lmstudio'", str(raised.exception))
        self.assertNotIn("model server", str(raised.exception))

    def test_server_start_rung_found_in_ladder(self):
        self.assertEqual([r.label for r in self.esc(MINI.__class__("lmstudio", "qwen3:8b", lmstudio_api_base="http://192.168.1.20:1234", server="mini", lan=True)).rungs],
                         ["qwen3:8b@mini", "gpt-6.1-terra"])

    def test_on_drops_lan_and_cloud(self):
        esc = self.esc(ESCALATE_LOCAL_ONLY="on")
        self.assertEqual([r.spec for r in esc.rungs], ["ollama:qwen2.5-coder:7b", "lmstudio:a"])
        self.assertEqual((esc.local_only, esc.scope), (True, "machine"))

    def test_lan_keeps_lan_drops_cloud(self):
        esc = self.esc(ESCALATE_LOCAL_ONLY="lan")
        self.assertEqual([r.spec for r in esc.rungs], ["ollama:qwen2.5-coder:7b", "lmstudio:a", "mini:qwen3:8b"])
        self.assertEqual((esc.local_only, esc.scope), (True, "lan"))
        self.assertEqual(esc.info()["scope"], "lan")

    def test_lan_start_under_on_raises(self):
        with self.assertRaises(PlannerConfigurationError) as raised:
            self.esc(MINI, ESCALATE_LOCAL_ONLY="on")
        self.assertEqual(str(raised.exception), "ESCALATE_LOCAL_ONLY=on but the selected coder qwen3-4b@mini runs on "
                         "the local network (use ESCALATE_LOCAL_ONLY=lan to allow it)")
        self.assertTrue(self.esc(MINI, ESCALATE_LOCAL_ONLY="lan").local_only)

    def test_cloud_start_message_unchanged(self):
        for setting in ("on", "lan"):
            with self.assertRaises(PlannerConfigurationError) as raised:
                self.esc(TERRA, ESCALATE_LOCAL_ONLY=setting)
            self.assertEqual(str(raised.exception),
                             "ESCALATE_LOCAL_ONLY=on but the selected coder gpt-6.1-terra runs in the cloud")


class LadderRunTests(tpf.TempAppCase):
    E = [tpf.APP_JSX + f"// edit {k}\n" for k in range(8)]
    COST = "Cost: $0.05 message, $0.05 session."

    def run_with(self, behaviors, results=None, extra=None, tasks=("t1", "t2"), job_env=None):
        self.make_job(tpf.JOB_A, list(tasks))
        fake = tpf.fake_aider(self.src, behaviors)
        results = list(results or [])
        validated = []

        def fake_validate(snapshot, checks, timeout, log):
            validated.append(1)
            return results.pop(0) if results else []
        values = {**(env() if job_env is None else job_env), **(extra or {})}
        with patch.dict(os.environ, values), patch.object(subprocess, "run", fake), \
                patch("controller.worker.validate_app", fake_validate):
            asyncio.run(run_job(tpf.JOB_A))
        return state.jobs[tpf.JOB_A], fake

    def models(self, fake):
        return [c[0][c[0].index("--model") + 1] for c in fake.calls]

    def ok(self, k, **kw):
        return {"edit": self.E[k], **kw}

    def test_build_failure_after_retry_escalates_with_history_and_previous_error(self):
        err = "'updateBallPhysics' is not defined"
        job, fake = self.run_with(
            [self.ok(0), self.ok(1), self.ok(2), self.ok(3)],
            [[("lint", err)], [("lint", err)], [], []], tasks=("t1",))
        self.assertEqual(job["status"], "done")
        self.assertEqual(self.models(fake), ["ollama_chat/qwen2.5-coder:7b"] * 2 + ["gpt-6.1-terra"])
        prompts = [" ".join(c[0]) for c in fake.calls]
        self.assertIn("previous attempt", prompts[1])
        self.assertNotIn("earlier attempt", prompts[1])
        self.assertIn("earlier attempt", prompts[2])
        self.assertIn(err, prompts[2])
        self.assertEqual(job["task_rungs"][0]["history"], [f"gpt-6.1-terra, after qwen2.5-coder:7b failed lint: {err}"])
        self.assertIn(job["task_rungs"][0]["history"][0], job["task_logs"][0])
        self.assertEqual(job["task_rungs"][0]["label"], "gpt-6.1-terra")
        self.assertEqual((self.src / "App.jsx").read_text(), self.E[2])

    def assert_escalates(self, first, summary, **kw):
        job, fake = self.run_with([first, self.ok(5)], tasks=("t1",), **kw)
        self.assertEqual(job["status"], "done")
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual(self.models(fake)[1], "gpt-6.1-terra")
        self.assertIn(summary, job["task_rungs"][0]["history"][0])
        self.assertEqual((self.src / "App.jsx").read_text(), self.E[5])
        return job

    def test_escalates_on_timeout(self):
        self.assert_escalates({"timeout": True}, "timed out after 120 s")

    def test_escalates_on_partial_apply(self):
        self.assert_escalates({"edit": self.E[0], "stdout": "Only 3 reflections allowed, stopping."}, "partly applied")
        self.assertEqual(len(list(self.src.glob("*.tmp"))), 0)

    def test_escalates_on_no_edit_api_error(self):
        job = self.assert_escalates({"stdout": "litellm.APIConnectionError: connection refused"},
                                    "applied no edit (the model server could not be reached)")
        self.assertIn("qwen2.5-coder:7b", job["task_rungs"][0]["history"][0])

    def test_escalates_on_corruption(self):
        self.assert_escalates({"edit": "x"}, "corrupted App.jsx")

    def test_no_escalation_on_exit_code_or_validator_failure(self):
        job, fake = self.run_with([{"rc": 2, "stderr": "boom"}], tasks=("t1",))
        self.assertEqual((job["status"], len(fake.calls)), ("failed", 1))
        self.assertIn("failed (exit code 2)", job["error"])
        self.state_reset()
        job, fake = self.run_with([self.ok(0), self.ok(1)], [[("validation", "x")], [("validation", "x")]], tasks=("t1",))
        self.assertEqual((job["status"], len(fake.calls)), ("failed", 2))
        self.assertIn("failed validation (validation)", job["error"])

    def state_reset(self):
        state.jobs.pop(tpf.JOB_A, None)

    def test_mid_rung_success_and_next_task_restarts_on_start_rung(self):
        job, fake = self.run_with([{"stdout": "APIConnectionError"}, self.ok(0), self.ok(1)])
        self.assertEqual(job["status"], "done")
        self.assertEqual(self.models(fake), ["ollama_chat/qwen2.5-coder:7b", "gpt-6.1-terra", "ollama_chat/qwen2.5-coder:7b"])
        self.assertEqual([r["label"] for r in job["task_rungs"]], ["gpt-6.1-terra", "qwen2.5-coder:7b"])
        self.assertEqual(job["task_rungs"][1]["history"], [])

    def test_exhausting_the_ladder(self):
        bad = {"stdout": "APIConnectionError"}
        job, fake = self.run_with([bad, bad, bad], tasks=("t1",))
        self.assertEqual((job["status"], job["task_statuses"]), ("failed", ["failed"]))
        self.assertIn("failed on all 3 rungs (qwen2.5-coder:7b, gpt-6.1-terra, gpt-6.2-sol)", job["error"])
        self.assertIn("Last failure on gpt-6.2-sol", job["error"])
        self.assertEqual((self.src / "App.jsx").read_text(), tpf.APP_JSX)

    def test_each_rung_gets_only_its_credentials_and_edit_format(self):
        job, fake = self.run_with([{"stdout": "APIConnectionError"}, self.ok(0)], tasks=("t1",))
        local_env, cloud_env = fake.calls[0][1]["env"], fake.calls[1][1]["env"]
        self.assertNotIn("OPENAI_API_KEY", local_env)
        self.assertIn("OLLAMA_API_BASE", local_env)
        self.assertEqual(cloud_env["OPENAI_API_KEY"], "sk-test")
        self.assertNotIn("OLLAMA_API_BASE", cloud_env)
        fmt = lambda c: c[0][c[0].index("--edit-format") + 1]
        self.assertEqual([fmt(c) for c in fake.calls], ["whole", "diff"])

    def test_edit_format_override_applies_to_every_rung(self):
        job, fake = self.run_with([{"stdout": "APIConnectionError"}, self.ok(0)], tasks=("t1",),
                                  extra={"CODER_EDIT_FORMAT": "udiff"})
        self.assertEqual([c[0][c[0].index("--edit-format") + 1] for c in fake.calls], ["udiff", "udiff"])

    def test_start_rung_from_gear_selection(self):
        selection.save_selection({"coder": {"provider": "openai", "model": "gpt-6.1-terra"}})
        job, fake = self.run_with([self.ok(0)], tasks=("t1",))
        self.assertEqual(self.models(fake), ["gpt-6.1-terra"])
        self.assertEqual([r["label"] for r in job["ladder"]["rungs"]], ["gpt-6.1-terra", "gpt-6.2-sol"])

    def test_selection_outside_ladder_is_prepended(self):
        selection.save_selection({"coder": {"provider": "ollama", "model": "llama3:8b"}})
        job, fake = self.run_with([{"stdout": "APIConnectionError"}, self.ok(0)], tasks=("t1",))
        self.assertEqual(self.models(fake), ["ollama_chat/llama3:8b", "ollama_chat/qwen2.5-coder:7b"])

    def test_local_only_never_runs_cloud(self):
        ladder = "ollama:qwen2.5-coder:7b,ollama:qwen3:14b,openai:gpt-6.1-terra"
        bad = {"stdout": "APIConnectionError"}
        job, fake = self.run_with([bad, self.ok(0)], tasks=("t1",),
                                  extra={"CODER_LADDER": ladder, "ESCALATE_LOCAL_ONLY": "on"})
        self.assertEqual(self.models(fake), ["ollama_chat/qwen2.5-coder:7b", "ollama_chat/qwen3:14b"])
        self.assertTrue(job["roles"]["local_only"])
        self.state_reset()
        job, fake = self.run_with([bad, bad], tasks=("t1",),
                                  extra={"CODER_LADDER": ladder, "ESCALATE_LOCAL_ONLY": "on"})
        self.assertEqual(len(fake.calls), 2)
        self.assertIn("failed on all 2 rungs", job["error"])
        self.state_reset()
        selection.save_selection({"coder": {"provider": "openai", "model": "gpt-6.1-terra"}})
        job, fake = self.run_with([], tasks=("t1",), extra={"ESCALATE_LOCAL_ONLY": "on"})
        self.assertEqual((job["status"], len(fake.calls)), ("failed", 0))
        self.assertIn("ESCALATE_LOCAL_ONLY=on", job["error"])

    def test_off_and_unset_ladder_are_single_coder(self):
        bad = {"stdout": "APIConnectionError"}
        for extra, job_env in (({"AUTO_ESCALATE": "off", "MAX_PLAN_COST": "0.0001"}, None),
                               ({"MAX_PLAN_COST": "0.0001"}, {**BASE})):
            with self.subTest(extra=extra):
                self.state_reset()
                job, fake = self.run_with([bad], tasks=("t1",), extra=extra, job_env=job_env)
                self.assertEqual((job["status"], len(fake.calls)), ("failed", 1))
                self.assertIn("made no changes", job["error"])
                self.assertNotIn("ladder", job)
                self.assertNotIn("plan_cost", job)
                self.assertNotIn("task_rungs", job)

    def test_suggest_stops_then_continue_starts_on_suggested_rung(self):
        bad = {"stdout": "APIConnectionError"}
        job, fake = self.run_with([bad], tasks=("t1",), extra={"AUTO_ESCALATE": "suggest"})
        self.assertEqual((job["status"], len(fake.calls)), ("failed", 1))
        self.assertIn("Suggested next: gpt-6.1-terra (openai:gpt-6.1-terra). Press Continue", job["error"])
        self.assertEqual(job["suggested_rung"]["spec"], "openai:gpt-6.1-terra")
        self.assertEqual(json.loads((self.plans / f"{tpf.JOB_A}.json").read_text())["suggested_rung"]["task"], 0)
        queue = tpf.FakeQueue()
        fake2 = tpf.fake_aider(self.src, [self.ok(0)])
        with patch.dict(os.environ, env(AUTO_ESCALATE="suggest")), patch.object(state, "job_queue", queue):
            asyncio.run(continue_plan())
            self.assertEqual(queue.items, [tpf.JOB_A])
            with patch.object(subprocess, "run", fake2), patch("controller.worker.validate_app", lambda *a: []):
                asyncio.run(run_job(tpf.JOB_A))
        job = state.jobs[tpf.JOB_A]
        self.assertEqual(self.models(fake2), ["gpt-6.1-terra"])
        self.assertEqual(job["status"], "done")
        self.assertIsNone(job["suggested_rung"])
        self.assertIn("earlier attempt", " ".join(fake2.calls[0][0]))
        self.assertTrue(job["task_rungs"][0]["history"][0].startswith("gpt-6.1-terra, after qwen2.5-coder:7b"))

    def test_cost_cap_stops_with_parsed_cost(self):
        bad = {"stdout": "APIConnectionError\n" + self.COST}
        local_bad = {"stdout": "APIConnectionError"}
        job, fake = self.run_with([local_bad, bad, self.ok(0)], tasks=("t1", "t2"), extra={"MAX_PLAN_COST": "0.04"})
        # local attempt is free; terra costs 0.05 and fails; the cap blocks sol.
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual(job["status"], "failed")
        self.assertIn("Stopped at task 1: plan cost $0.05 reached MAX_PLAN_COST $0.04", job["error"])
        self.assertIn("gpt-6.1-terra", job["error"])
        self.assertEqual(job["plan_cost"], 0.05)

    def test_cost_cap_with_unparsable_cloud_cost_counts_estimate(self):
        bad = {"stdout": "APIConnectionError"}
        job, fake = self.run_with([bad, bad, self.ok(0)], tasks=("t1",), extra={"MAX_PLAN_COST": "0.02"})
        self.assertEqual(len(fake.calls), 2)
        # Terra with no token lines: the assumed 8k in / 4k out at $1 / $5 per 1M tokens.
        self.assertEqual(job["plan_cost"], 0.028)
        self.assertTrue(job["plan_cost_estimated"])
        self.assertIn("estimated parts included", job["error"])
        self.assertIn("counted $0.0280 estimate from token counts", job["task_logs"][0])

    def test_estimate_uses_printed_token_counts_and_the_models_price(self):
        out = "Tokens: 4.9k sent, 3.5k received.\nTokens: 1.2k sent, 94 received."
        # 6.1k in and 3594 out on Luna ($0.10 / $0.50 per 1M).
        self.assertEqual(estimate_cloud_cost("gpt-6-luna", out), round(6100 / 1e6 * 0.10 + 3594 / 1e6 * 0.50, 6))
        self.assertLess(estimate_cloud_cost("gpt-6-luna", out), 0.003)
        self.assertEqual(estimate_cloud_cost("openai/gpt-6.2-astra", "Tokens: 5k sent, 3.5k received."),
                         round(5000 / 1e6 * 8 + 3500 / 1e6 * 40, 6))

    def test_estimate_without_counts_assumes_a_typical_attempt_and_unknown_models_stay_flat(self):
        self.assertEqual(estimate_cloud_cost("gpt-6-luna", ""), 0.0028)
        self.assertEqual(estimate_cloud_cost("some-new-model", "Tokens: 5k sent, 3k received."),
                         UNPARSED_CLOUD_COST)

    def test_local_attempt_is_free_and_not_blocked_after_cap(self):
        self.make_job(tpf.JOB_A, ["t1"])
        state.jobs[tpf.JOB_A]["plan_cost"] = 5.0
        fake = tpf.fake_aider(self.src, [self.ok(0)])
        with patch.dict(os.environ, env()), patch.object(subprocess, "run", fake), \
                patch("controller.worker.validate_app", lambda *a: []):
            asyncio.run(run_job(tpf.JOB_A))
        job = state.jobs[tpf.JOB_A]
        self.assertEqual((job["status"], job["plan_cost"]), ("done", 5.0))

    def test_cost_persists_across_continue_and_restart(self):
        bad = {"stdout": "APIConnectionError\n" + self.COST}
        job, _ = self.run_with([{"stdout": "APIConnectionError"}, bad], tasks=("t1",), extra={"MAX_PLAN_COST": "0.04"})
        self.assertEqual(job["plan_cost"], 0.05)
        self.assertEqual(json.loads((self.plans / f"{tpf.JOB_A}.json").read_text())["plan_cost"], 0.05)
        state.jobs.clear()
        load_jobs()
        self.assertEqual(state.jobs[tpf.JOB_A]["plan_cost"], 0.05)
        state.jobs[tpf.JOB_A]["task_statuses"] = ["pending"]
        fake = tpf.fake_aider(self.src, [{"stdout": "APIConnectionError"}, self.ok(0)])
        with patch.dict(os.environ, env(MAX_PLAN_COST="0.04")), patch.object(subprocess, "run", fake), \
                patch("controller.worker.validate_app", lambda *a: []):
            asyncio.run(run_job(tpf.JOB_A))
        job = state.jobs[tpf.JOB_A]
        self.assertEqual(len(fake.calls), 1)  # local attempt only; the cap blocks the cloud rung
        self.assertIn("Stopped at task 1: plan cost $0.05", job["error"])
        self.assertEqual(job["plan_cost"], 0.05)

    def test_roles_evidence_is_truthful_after_escalation(self):
        job, _ = self.run_with([{"stdout": "APIConnectionError"}, self.ok(0), self.ok(1)])
        self.assertEqual(job["roles"]["coder"]["model"], "qwen2.5-coder:7b")  # last task ran locally
        self.state_reset()
        job, _ = self.run_with([{"stdout": "APIConnectionError"}, self.ok(0)], tasks=("t1",))
        self.assertEqual(job["roles"]["coder"]["model"], "gpt-6.1-terra")
        self.assertEqual(job["roles"]["coder"]["location"], "cloud")
        self.assertFalse(job["roles"]["local_only"])
        stored = json.loads((self.plans / f"{tpf.JOB_A}.json").read_text())
        self.assertIn("task_rungs", stored)
        self.assertIn("ladder", stored)
        self.assertEqual(stored["roles"]["coder"]["model"], "gpt-6.1-terra")

    def test_no_escalation_keeps_local_roles(self):
        job, _ = self.run_with([self.ok(0)], tasks=("t1",))
        self.assertEqual(job["roles"]["coder"]["model"], "qwen2.5-coder:7b")
        self.assertTrue(job["roles"]["local_only"])

    def test_bad_ladder_fails_run_and_continue(self):
        for bad in ({"CODER_LADDER": "mystery:x"}, {"CODER_LADDER": "openai:gpt-6.1-terra", "OPENAI_API_KEY": ""}):
            with self.subTest(bad=bad):
                self.state_reset()
                job, fake = self.run_with([], tasks=("t1",), extra=bad)
                self.assertEqual((job["status"], len(fake.calls)), ("failed", 0))
                self.assertIn("CODER_LADDER entry", job["error"])
                with patch.dict(os.environ, {**env(), **bad}), patch.object(state, "job_queue", tpf.FakeQueue()):
                    job["status"] = "failed"
                    with self.assertRaises(HTTPException) as raised:
                        asyncio.run(continue_plan())
                    self.assertEqual(raised.exception.status_code, 500)


if __name__ == "__main__":
    unittest.main()
