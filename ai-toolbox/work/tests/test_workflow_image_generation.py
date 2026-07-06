import base64
import os
import sys
import tempfile
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.orchestrator import engine as workflow_engine
from modules.orchestrator.state import WorkflowState


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, content=b""):
        self.status_code = status_code
        self._payload = payload or {}
        self.content = content
        self.text = str(self._payload)

    def json(self):
        return self._payload


class WorkflowImageGenerationTests(unittest.TestCase):
    def test_generate_image_saves_top_level_data_url_without_downloading(self):
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
            b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT"
            b"\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfeA"
            b"\xbf\xa1\x9d\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")

        original_post = workflow_engine.requests.post
        original_get = workflow_engine.requests.get
        try:
            def fake_post(url, **kwargs):
                return _FakeResponse(payload={"image": data_url})

            def fake_get(url, **kwargs):
                raise AssertionError("data URLs must be decoded locally, not downloaded")

            workflow_engine.requests.post = fake_post
            workflow_engine.requests.get = fake_get

            state = WorkflowState()
            eng = workflow_engine.WorkflowEngine(state)
            with tempfile.TemporaryDirectory() as temp_dir:
                local_url = eng._generate_image("test prompt", temp_dir, 0)
                saved_path = os.path.join(temp_dir, os.path.basename(local_url))

                self.assertEqual(local_url, f"/generated/wf_{state.id}_img1.png")
                self.assertTrue(os.path.exists(saved_path))
                with open(saved_path, "rb") as f:
                    saved_bytes = f.read()
                # API response is saved directly (mask protects product)
                self.assertTrue(saved_bytes.startswith(b"\x89PNG"))
        finally:
            workflow_engine.requests.post = original_post
            workflow_engine.requests.get = original_get


if __name__ == "__main__":
    unittest.main()
