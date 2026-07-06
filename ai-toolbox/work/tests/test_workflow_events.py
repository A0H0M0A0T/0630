import os
import sys
import tempfile
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.orchestrator import state as workflow_state


class WorkflowEventPersistenceTests(unittest.TestCase):
    def setUp(self):
        self._old_db_path = workflow_state.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        workflow_state.DB_PATH = os.path.join(self.temp_dir.name, "workflows.db")
        workflow_state.init_workflow_db()

    def tearDown(self):
        workflow_state.DB_PATH = self._old_db_path
        self.temp_dir.cleanup()

    def test_record_and_list_workflow_events_in_order(self):
        workflow_state.record_workflow_event(
            workflow_id="wf_test",
            step_index=1,
            step_name="生成剧情分镜",
            event_type="started",
            message="Step 1 started",
            input_summary="story_type=正常性, gender=随机",
        )
        workflow_state.record_workflow_event(
            workflow_id="wf_test",
            step_index=1,
            step_name="生成剧情分镜",
            event_type="succeeded",
            message="Step 1 succeeded",
            duration_ms=123,
            output_summary="keyframes=4",
        )

        events = workflow_state.list_workflow_events("wf_test")

        self.assertEqual([event["event_type"] for event in events], ["started", "succeeded"])
        self.assertEqual(events[0]["workflow_id"], "wf_test")
        self.assertEqual(events[0]["step_index"], 1)
        self.assertEqual(events[0]["step_name"], "生成剧情分镜")
        self.assertEqual(events[0]["message"], "Step 1 started")
        self.assertEqual(events[0]["input_summary"], "story_type=正常性, gender=随机")
        self.assertEqual(events[1]["duration_ms"], 123)
        self.assertEqual(events[1]["output_summary"], "keyframes=4")
        self.assertTrue(events[0]["created_at"])

    def test_list_workflow_events_respects_limit_and_is_api_safe(self):
        for i in range(5):
            workflow_state.record_workflow_event(
                workflow_id="wf_limit",
                step_index=i + 1,
                step_name=f"步骤{i + 1}",
                event_type="started",
                message=f"event {i}",
            )

        events = workflow_state.list_workflow_events("wf_limit", limit=3)

        self.assertEqual(len(events), 3)
        self.assertEqual([event["message"] for event in events], ["event 2", "event 3", "event 4"])
        for event in events:
            self.assertIsInstance(event["id"], int)
            self.assertIn(event["event_type"], {"started", "succeeded", "failed", "warning", "cancelled"})

    def test_record_workflow_event_trims_large_traceback(self):
        workflow_state.record_workflow_event(
            workflow_id="wf_trace",
            step_index=2,
            step_name="提取关键帧生图提示词",
            event_type="failed",
            message="Step 2 failed",
            error_type="RuntimeError",
            error_traceback="x" * 20000,
        )

        event = workflow_state.list_workflow_events("wf_trace")[0]

        self.assertEqual(event["error_type"], "RuntimeError")
        self.assertLessEqual(len(event["error_traceback"]), 8000)
        self.assertTrue(event["error_traceback"].endswith("[TRUNCATED]"))


if __name__ == "__main__":
    unittest.main()
