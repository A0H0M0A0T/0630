import os
import sys
import tempfile
import unittest

import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.orchestrator import engine as workflow_engine
from modules.orchestrator import state as workflow_state
from modules.orchestrator.state import WorkflowState


class WorkflowEngineLoggingTests(unittest.TestCase):
    def setUp(self):
        self._old_db_path = workflow_state.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        workflow_state.DB_PATH = os.path.join(self.temp_dir.name, "workflows.db")
        workflow_state.init_workflow_db()

        self._old_storyboard = workflow_engine.generate_storyboard
        self._old_extract = workflow_engine.extract_keyframe_prompts
        self._old_score = workflow_engine.score_all_images
        self._old_assemble = workflow_engine.assemble_video_prompt
        self._old_generate_image = workflow_engine.WorkflowEngine._generate_image
        self._old_generate_copy = workflow_engine.WorkflowEngine._generate_copy

    def tearDown(self):
        workflow_engine.generate_storyboard = self._old_storyboard
        workflow_engine.extract_keyframe_prompts = self._old_extract
        workflow_engine.score_all_images = self._old_score
        workflow_engine.assemble_video_prompt = self._old_assemble
        workflow_engine.WorkflowEngine._generate_image = self._old_generate_image
        workflow_engine.WorkflowEngine._generate_copy = self._old_generate_copy
        workflow_state.DB_PATH = self._old_db_path
        self.temp_dir.cleanup()

    def test_failed_step_records_traceback_and_stops_at_real_step(self):
        def fake_storyboard(**kwargs):
            return {
                "storyboard_text": "剧情文本",
                "keyframes": [{"index": 1, "description": "第一帧", "camera": "手持", "composition": "近景"}],
                "gender": "女",
                "scene": "餐厅",
            }

        def fake_extract(**kwargs):
            raise RuntimeError("prompt model timeout")

        workflow_engine.generate_storyboard = fake_storyboard
        workflow_engine.extract_keyframe_prompts = fake_extract

        state = WorkflowState()
        engine = workflow_engine.WorkflowEngine(state)
        engine._run_steps()

        saved = WorkflowState(state.id)
        events = workflow_state.list_workflow_events(state.id)

        self.assertEqual(saved.status, "failed")
        self.assertEqual(saved.step_index, 2)
        self.assertIn("Step2 关键帧提取失败", saved.error_message)
        self.assertEqual([event["event_type"] for event in events], ["started", "succeeded", "started", "failed"])
        self.assertEqual(events[-1]["step_index"], 2)
        self.assertEqual(events[-1]["error_type"], "RuntimeError")
        self.assertIn("prompt model timeout", events[-1]["message"])
        self.assertIn("fake_extract", events[-1]["error_traceback"])

    def test_image_generation_failure_marks_step3_failed_and_does_not_score(self):
        def fake_storyboard(**kwargs):
            return {
                "storyboard_text": "剧情文本",
                "keyframes": [{"index": 1, "description": "第一帧", "camera": "手持", "composition": "近景"}],
                "gender": "男",
                "scene": "烧烤店",
            }

        def fake_extract(**kwargs):
            return ["帮我生成1张图片：第一张：测试"]

        def fake_generate_image(self, prompt, output_dir, index, product_image_path="", product_desc="", keyframes=None):
            raise RuntimeError("Image API returned 401")

        def fake_score(*args, **kwargs):
            raise AssertionError("scoring must not run after image generation failure")

        workflow_engine.generate_storyboard = fake_storyboard
        workflow_engine.extract_keyframe_prompts = fake_extract
        workflow_engine.WorkflowEngine._generate_image = fake_generate_image
        workflow_engine.score_all_images = fake_score

        state = WorkflowState()
        engine = workflow_engine.WorkflowEngine(state)
        engine._run_steps()

        saved = WorkflowState(state.id)
        events = workflow_state.list_workflow_events(state.id)

        self.assertEqual(saved.status, "failed")
        self.assertEqual(saved.step_index, 3)
        self.assertIn("Step3 四宫格图生成失败", saved.error_message)
        self.assertEqual(events[-1]["event_type"], "failed")
        self.assertEqual(events[-1]["step_index"], 3)
        self.assertIn("Image API returned 401", events[-1]["message"])

    def test_sslerror_in_step3_marks_workflow_failed_and_stops(self):
        """Simulate the real-world yunwu.ai SSLError bug.

        When _generate_image raises requests.exceptions.SSLError:
        - workflow.status MUST be "failed"
        - step_index MUST be 3
        - score_all_images MUST NOT be called
        - The failed event MUST capture the original SSLError type
        """
        def fake_storyboard(**kwargs):
            return {
                "storyboard_text": "剧情文本",
                "keyframes": [{"index": 1, "description": "第一帧", "camera": "手持", "composition": "近景"}],
                "gender": "女",
                "scene": "餐厅",
            }

        def fake_extract(**kwargs):
            return ["帮我生成1张图片：第一张：测试"]

        def fake_generate_image(self, prompt, output_dir, index, product_image_path="", product_desc="", keyframes=None):
            raise requests.exceptions.SSLError(
                "HTTPSConnectionPool(host='yunwu.ai', port=443): "
                "Max retries exceeded with url: /v1/images/generations "
                "(Caused by SSLError(SSLEOFError(8, 'EOF occurred in violation of protocol')))"
            )

        score_called = [False]

        def fake_score(*args, **kwargs):
            score_called[0] = True
            raise AssertionError("scoring must not run after image generation failure")

        workflow_engine.generate_storyboard = fake_storyboard
        workflow_engine.extract_keyframe_prompts = fake_extract
        workflow_engine.WorkflowEngine._generate_image = fake_generate_image
        workflow_engine.score_all_images = fake_score

        state = WorkflowState()
        engine = workflow_engine.WorkflowEngine(state)
        engine._run_steps()

        saved = WorkflowState(state.id)
        events = workflow_state.list_workflow_events(state.id)

        # ── Backend assertions ──
        self.assertEqual(saved.status, "failed",
                         "workflow.status must be 'failed' after Step3 SSLError")
        self.assertEqual(saved.step_index, 3,
                         "workflow.step_index must be 3, the true failing step")
        self.assertIn("Step3 四宫格图生成失败", saved.error_message,
                      "error_message must reference Step3 image generation failure")
        self.assertIn("SSLError", saved.error_message,
                      "error_message must preserve the original error type")

        # ── Event assertions ──
        event_types = [e["event_type"] for e in events]
        self.assertEqual(event_types, ["started", "succeeded", "started", "succeeded", "started", "failed"],
                         "event sequence must end with 'failed' at step 3")

        failed_event = events[-1]
        self.assertEqual(failed_event["step_index"], 3)
        self.assertEqual(failed_event["error_type"], "SSLError")
        self.assertIn("yunwu.ai", failed_event["message"])
        self.assertIn("SSLError", failed_event["error_traceback"])

        # ── Side-effect assertion ──
        self.assertFalse(score_called[0],
                         "score_all_images must never be called after Step3 failure")


if __name__ == "__main__":
    unittest.main()
