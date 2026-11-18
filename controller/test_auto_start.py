"""Server-side auto-start: Plan starts itself after a countdown unless cancelled.

The countdown used to live only in the phone's browser, so a reload, a locked screen or a
backgrounded tab could stop a plan from ever starting.
"""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

import controller.test_plan_flow as tpf
from controller import state
from controller.routes import jobs as job_routes
from controller.routes import planner as planner_routes
from controller.schemas import PlanRequest


class AutoStartTests(tpf.TempAppCase):
    def setUp(self):
        super().setUp()
        self.queue = tpf.FakeQueue()
        for p in (patch.object(state, "job_queue", self.queue), patch.dict(state.auto_starts, clear=True)):
            p.start()
            self.addCleanup(p.stop)

    def run_async(self, coro_fn):
        async def main():
            return await coro_fn()
        return asyncio.run(main())

    def test_starts_by_itself_after_the_delay(self):
        self.make_job(tpf.JOB_A, ["t1"])

        async def scenario():
            job_routes.schedule_auto_start(tpf.JOB_A, 0.05)
            pending = job_routes.get_job(tpf.JOB_A)["auto_start_in"]
            await asyncio.sleep(0.2)
            return pending
        pending = self.run_async(scenario)
        self.assertIsNotNone(pending)  # pending (0.05 s rounds to 0.0 or 0.1)
        self.assertEqual(self.queue.items, [tpf.JOB_A])
        self.assertEqual(state.jobs[tpf.JOB_A]["status"], "queued")
        self.assertIsNone(job_routes.get_job(tpf.JOB_A)["auto_start_in"])

    def test_cancel_keeps_it_planned(self):
        self.make_job(tpf.JOB_A, ["t1"])

        async def scenario():
            job_routes.schedule_auto_start(tpf.JOB_A, 0.05)
            result = job_routes.cancel_auto_start(tpf.JOB_A)
            again = job_routes.cancel_auto_start(tpf.JOB_A)
            await asyncio.sleep(0.2)
            return result, again
        result, again = self.run_async(scenario)
        self.assertEqual((result["cancelled"], again["cancelled"]), (True, False))
        self.assertEqual(self.queue.items, [])
        self.assertEqual(state.jobs[tpf.JOB_A]["status"], "planned")

    def test_started_by_hand_first_is_not_started_twice(self):
        self.make_job(tpf.JOB_A, ["t1"])

        async def scenario():
            job_routes.schedule_auto_start(tpf.JOB_A, 0.05)
            await job_routes.execute_job(tpf.JOB_A)
            await asyncio.sleep(0.2)
        self.run_async(scenario)
        self.assertEqual(self.queue.items, [tpf.JOB_A])
        self.assertIsNone(state.jobs[tpf.JOB_A]["error"])

    def test_a_busy_server_records_why_it_could_not_start(self):
        self.make_job(tpf.JOB_A, ["t1"])
        self.make_job(tpf.JOB_B, ["t2"], status="running")

        async def scenario():
            job_routes.schedule_auto_start(tpf.JOB_A, 0.01)
            await asyncio.sleep(0.1)
        self.run_async(scenario)
        job = state.jobs[tpf.JOB_A]
        self.assertEqual(job["status"], "planned")
        self.assertEqual(job["error"], "Auto-start failed: A plan is already running")
        self.assertEqual(json.loads((self.plans / f"{tpf.JOB_A}.json").read_text())["error"], job["error"])

    def test_active_job_includes_a_plan_counting_down(self):
        self.make_job(tpf.JOB_A, ["t1"])
        self.assertIsNone(job_routes.get_active_job())

        async def scenario():
            job_routes.schedule_auto_start(tpf.JOB_A, 5)
            active = job_routes.get_active_job()
            job_routes.cancel_auto_start(tpf.JOB_A)
            return active
        active = self.run_async(scenario)
        self.assertEqual(active["job_id"], tpf.JOB_A)
        self.assertGreater(active["auto_start_in"], 4)
        self.assertIsNone(job_routes.get_active_job())

    def plan(self, auto_start):
        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
            create=lambda **kw: SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=tpf.USER_OUTPUT))]))))

        async def scenario():
            result = await planner_routes.plan(PlanRequest(prompt="cube green", auto_start=auto_start))
            pending = dict(state.auto_starts)
            job_routes.cancel_auto_start(result["job_id"])
            return result, pending
        with patch.object(planner_routes, "create_planner_client", return_value=fake_client), \
                patch.object(planner_routes, "planner_user_msg", return_value="x"):
            return self.run_async(scenario)

    def test_plan_schedules_only_when_asked(self):
        result, pending = self.plan(auto_start=True)
        self.assertEqual(list(pending), [result["job_id"]])
        self.assertGreater(result["auto_start_in"], 4)
        result, pending = self.plan(auto_start=False)
        self.assertEqual(pending, {})
        self.assertIsNone(result["auto_start_in"])
        self.assertEqual(self.queue.items, [])
