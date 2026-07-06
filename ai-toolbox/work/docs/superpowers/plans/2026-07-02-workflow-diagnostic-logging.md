# Workflow Diagnostic Logging Implementation Plan

> **[ARCHIVED — 计划已实施]** 此计划描述的 workflow 诊断日志功能已实现（event table、API 端点、前端诊断面板均已上线）。下文保留仅作历史参考。所有路径指向原工作区 `D:\0630\work\`，当前工作区为 `D:\0703\ai-toolbox\work\`。
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal (Completed):** Add reliable diagnostic logs so each workflow run shows exactly which of the 6 stages started, succeeded, failed, or was cancelled.

**Architecture:** Persist structured step events in `workflows.db`, write detailed backend logs to `logs/app.log`, expose events through `/api/workflow/logs/{workflow_id}`, and render a compact diagnostic panel in the workflow page. Keep the current 6-stage pipeline intact, but make failures stop at the true failing stage instead of cascading into later stages.

**Tech Stack:** Python 3, FastAPI, SQLite, standard-library `logging`, `unittest`, React, TypeScript, Vite.

---

## File Structure

- Modify: `D:\0630\work\modules\orchestrator\state.py`
  - Owns SQLite schema migration and workflow event persistence.
- Modify: `D:\0630\work\modules\orchestrator\engine.py`
  - Owns step start, success, failure, cancellation logging.
- Modify: `D:\0630\work\server.py`
  - Exposes the workflow logs API route used by the active app.
- Modify: `D:\0630\work\src\types.ts`
  - Adds the `WorkflowEvent` TypeScript type.
- Modify: `D:\0630\work\src\api\workflow.ts`
  - Adds `getWorkflowLogs()`.
- Modify: `D:\0630\work\src\components\WorkflowPage.tsx`
  - Adds the diagnostic log panel and copy diagnostic action.
- Create: `D:\0630\work\tests\test_workflow_events.py`
  - Verifies event persistence and API-safe serialization.
- Create: `D:\0630\work\tests\test_workflow_engine_logging.py`
  - Verifies the engine records the real failing stage and stops.

Do not modify `D:\0630\work\modules\orchestrator\routes.py` for the first implementation. It defines an unused router, while `D:\0630\work\server.py` currently owns the live `/api/workflow/*` routes.

---

## Task 1: Add Workflow Event Persistence

**Files:**
- Modify: `D:\0630\work\modules\orchestrator\state.py`
- Create: `D:\0630\work\tests\test_workflow_events.py`

- [ ] **Step 1: Write the failing persistence tests**

Create `D:\0630\work\tests\test_workflow_events.py`:

```python
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
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run:

```powershell
python -m unittest tests.test_workflow_events -v
```

Expected:

```text
ERROR: test_record_and_list_workflow_events_in_order
AttributeError: module 'modules.orchestrator.state' has no attribute 'record_workflow_event'
```

- [ ] **Step 3: Add the event table and helper functions**

In `D:\0630\work\modules\orchestrator\state.py`, add this import near the existing imports:

```python
from typing import Optional
```

Keep the existing `Optional` import if it is already present. Add this helper below `_get_conn()`:

```python
def _trim_text(value: str | None, limit: int = 8000) -> str:
    if not value:
        return ""
    text = str(value)
    if len(text) <= limit:
        return text
    suffix = "[TRUNCATED]"
    return text[: max(0, limit - len(suffix))] + suffix
```

Inside `init_workflow_db()`, after the existing `CREATE TABLE IF NOT EXISTS workflows (...)` statement, add:

```python
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id TEXT NOT NULL,
            step_index INTEGER DEFAULT 0,
            step_name TEXT DEFAULT '',
            event_type TEXT NOT NULL,
            message TEXT DEFAULT '',
            duration_ms INTEGER,
            error_type TEXT DEFAULT '',
            error_traceback TEXT DEFAULT '',
            input_summary TEXT DEFAULT '',
            output_summary TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_workflow_events_workflow_id_id
        ON workflow_events (workflow_id, id)
    """)
```

Below `init_workflow_db()`, add:

```python
VALID_WORKFLOW_EVENT_TYPES = {"started", "succeeded", "failed", "warning", "cancelled"}


def record_workflow_event(
    workflow_id: str,
    step_index: int,
    step_name: str,
    event_type: str,
    message: str,
    duration_ms: int | None = None,
    error_type: str = "",
    error_traceback: str = "",
    input_summary: str = "",
    output_summary: str = "",
) -> None:
    if event_type not in VALID_WORKFLOW_EVENT_TYPES:
        raise ValueError(f"Invalid workflow event type: {event_type}")

    init_workflow_db()
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO workflow_events
        (workflow_id, step_index, step_name, event_type, message, duration_ms,
         error_type, error_traceback, input_summary, output_summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            workflow_id,
            step_index,
            step_name,
            event_type,
            _trim_text(message, 1000),
            duration_ms,
            _trim_text(error_type, 200),
            _trim_text(error_traceback, 8000),
            _trim_text(input_summary, 2000),
            _trim_text(output_summary, 2000),
        ),
    )
    conn.commit()
    conn.close()


def list_workflow_events(workflow_id: str, limit: int = 200) -> list[dict]:
    safe_limit = max(1, min(int(limit or 200), 500))
    init_workflow_db()
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT * FROM (
            SELECT id, workflow_id, step_index, step_name, event_type, message,
                   duration_ms, error_type, error_traceback, input_summary,
                   output_summary, created_at
            FROM workflow_events
            WHERE workflow_id=?
            ORDER BY id DESC
            LIMIT ?
        )
        ORDER BY id ASC
        """,
        (workflow_id, safe_limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
```

- [ ] **Step 4: Run the persistence tests**

Run:

```powershell
python -m unittest tests.test_workflow_events -v
```

Expected:

```text
Ran 3 tests

OK
```

---

## Task 2: Log Real Step Start, Success, Failure, and Cancellation

**Files:**
- Modify: `D:\0630\work\modules\orchestrator\engine.py`
- Create: `D:\0630\work\tests\test_workflow_engine_logging.py`

- [ ] **Step 1: Write the failing engine logging tests**

Create `D:\0630\work\tests\test_workflow_engine_logging.py`:

```python
import os
import sys
import tempfile
import unittest


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

        def fake_generate_image(self, prompt, output_dir, index):
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run:

```powershell
python -m unittest tests.test_workflow_engine_logging -v
```

Expected:

```text
FAIL: test_failed_step_records_traceback_and_stops_at_real_step
FAIL: test_image_generation_failure_marks_step3_failed_and_does_not_score
```

- [ ] **Step 3: Add workflow event helpers to the engine**

In `D:\0630\work\modules\orchestrator\engine.py`, change the first import line from:

```python
import sys, os, time, random, threading, requests, base64, re
```

to:

```python
import sys, os, time, random, threading, requests, base64, re, traceback
```

Change the state import from:

```python
from .state import WorkflowState, init_workflow_db
```

to:

```python
from .state import WorkflowState, init_workflow_db, record_workflow_event
from modules.tupian.logger import get_logger
```

Below `_engines: dict = {}`, add:

```python
logger = get_logger("workflow")
```

Inside `WorkflowEngine`, add these methods after `stop()`:

```python
    def _step_input_summary(self) -> str:
        st = self.state
        return (
            f"story_type={st.story_type}, gender={st.gender}, scene={st.scene}, "
            f"audience={st.audience}, weather={st.weather}, style={st.style}, "
            f"action={st.action}, aspect_ratio={st.aspect_ratio}, "
            f"product_image={'yes' if st.product_image else 'no'}"
        )

    def _start_step(self, step_index: int) -> float:
        st = self.state
        step_name = self.STEP_LABELS[step_index]
        st.status = "running"
        st.current_step = step_name
        st.step_index = step_index
        st.save()
        record_workflow_event(
            workflow_id=st.id,
            step_index=step_index,
            step_name=step_name,
            event_type="started",
            message=f"Step{step_index} {step_name} started",
            input_summary=self._step_input_summary(),
        )
        logger.info("workflow=%s step=%s started name=%s", st.id, step_index, step_name)
        return time.perf_counter()

    def _finish_step(self, step_index: int, started_at: float, output_summary: str = "") -> None:
        st = self.state
        step_name = self.STEP_LABELS[step_index]
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        record_workflow_event(
            workflow_id=st.id,
            step_index=step_index,
            step_name=step_name,
            event_type="succeeded",
            message=f"Step{step_index} {step_name} succeeded",
            duration_ms=duration_ms,
            output_summary=output_summary,
        )
        logger.info(
            "workflow=%s step=%s succeeded duration_ms=%s output=%s",
            st.id,
            step_index,
            duration_ms,
            output_summary,
        )

    def _fail_step(self, step_index: int, started_at: float, message: str, exc: Exception) -> None:
        st = self.state
        step_name = self.STEP_LABELS[step_index]
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        error_message = f"Step{step_index} {message}: {str(exc)[:300]}"
        st.status = "failed"
        st.current_step = step_name
        st.step_index = step_index
        st.error_message = error_message
        st.save()
        record_workflow_event(
            workflow_id=st.id,
            step_index=step_index,
            step_name=step_name,
            event_type="failed",
            message=error_message,
            duration_ms=duration_ms,
            error_type=type(exc).__name__,
            error_traceback=traceback.format_exc(),
        )
        logger.exception(
            "workflow=%s step=%s failed duration_ms=%s error=%s",
            st.id,
            step_index,
            duration_ms,
            error_message,
        )
```

- [ ] **Step 4: Replace each step's ad hoc try/except with the helpers**

Update each step in `_run_steps()`:

Step 1 shape:

```python
        if self._stop_flag.is_set(): return
        started_at = self._start_step(1)
        try:
            sb = generate_storyboard(...)
            st.storyboard_text = sb["storyboard_text"]
            st.keyframes = sb["keyframes"]
            st.gender = sb["gender"]
            st.scene = sb["scene"]
            st.save()
            self._finish_step(1, started_at, f"gender={st.gender}, scene={st.scene}, keyframes={len(st.keyframes)}")
        except Exception as e:
            self._fail_step(1, started_at, "剧情生成失败", e)
            return
```

Step 2 shape:

```python
        if self._stop_flag.is_set(): return
        started_at = self._start_step(2)
        try:
            prompts = extract_keyframe_prompts(...)
            st.image_prompts = prompts
            st.save()
            self._finish_step(2, started_at, f"image_prompts={len(st.image_prompts)}")
        except Exception as e:
            self._fail_step(2, started_at, "关键帧提取失败", e)
            return
```

Step 3 must stop on failure:

```python
        if self._stop_flag.is_set(): return
        started_at = self._start_step(3)
        GENERATED_DIR = os.path.join(_ROOT, "static", "generated")
        os.makedirs(GENERATED_DIR, exist_ok=True)
        image_urls = []
        prompt = st.image_prompts[0] if st.image_prompts else ""
        try:
            url = self._generate_image(prompt, GENERATED_DIR, 0)
            if url and os.path.exists(os.path.join(_ROOT, "static", "generated", os.path.basename(url))):
                image_urls.append(url)
                st.error_message = ""
            else:
                raise RuntimeError("图片保存后路径校验失败")
            st.image_urls = image_urls
            st.save()
            self._finish_step(3, started_at, f"image_urls={len([u for u in image_urls if u])}")
        except Exception as e:
            st.image_urls = image_urls
            st.save()
            self._fail_step(3, started_at, "四宫格图生成失败", e)
            return
```

Step 4 shape:

```python
        if self._stop_flag.is_set(): return
        started_at = self._start_step(4)
        try:
            scores = score_all_images(st.image_urls, st.keyframes)
            st.scores = scores
            st.save()
            self._finish_step(4, started_at, f"scores={len(st.scores)}")
        except Exception as e:
            self._fail_step(4, started_at, "评分失败", e)
            return
```

Step 5 shape:

```python
        if self._stop_flag.is_set(): return
        started_at = self._start_step(5)
        try:
            st.copy_text = self._generate_copy()
            st.save()
            self._finish_step(5, started_at, f"copy_chars={len(st.copy_text)}")
        except Exception as e:
            self._fail_step(5, started_at, "文案生成失败", e)
            return
```

Step 6 shape:

```python
        if self._stop_flag.is_set(): return
        started_at = self._start_step(6)
        try:
            st.video_prompt = assemble_video_prompt(...)
            st.status = "completed"
            st.current_step = "完成"
            st.save()
            self._finish_step(6, started_at, f"video_prompt_chars={len(st.video_prompt)}")
        except Exception as e:
            self._fail_step(6, started_at, "最终提示词组装失败", e)
            return
```

Keep the existing function calls and arguments when replacing the bodies. Only change the control flow and event logging.

- [ ] **Step 5: Record cancellation events**

Update `stop()` in `D:\0630\work\modules\orchestrator\engine.py`:

```python
    def stop(self):
        self._stop_flag.set()
        self.state.status = "cancelled"
        self.state.save()
        record_workflow_event(
            workflow_id=self.state.id,
            step_index=self.state.step_index,
            step_name=self.state.current_step,
            event_type="cancelled",
            message=f"Workflow cancelled at step {self.state.step_index}: {self.state.current_step}",
        )
        logger.warning(
            "workflow=%s cancelled step=%s name=%s",
            self.state.id,
            self.state.step_index,
            self.state.current_step,
        )
```

- [ ] **Step 6: Run engine logging tests**

Run:

```powershell
python -m unittest tests.test_workflow_engine_logging -v
```

Expected:

```text
Ran 2 tests

OK
```

---

## Task 3: Expose Workflow Logs Through the Active API

**Files:**
- Modify: `D:\0630\work\server.py`

- [ ] **Step 1: Add the state import**

In `D:\0630\work\server.py`, change:

```python
from modules.orchestrator.state import WorkflowState, init_workflow_db
```

to:

```python
from modules.orchestrator.state import WorkflowState, init_workflow_db, list_workflow_events
```

- [ ] **Step 2: Add the logs endpoint after the status endpoint**

Add this route after `workflow_status_route`:

```python
@app.get("/api/workflow/logs/{workflow_id}")
async def workflow_logs_route(workflow_id: str, limit: int = Query(200, ge=1, le=500)):
    """获取工作流诊断日志。"""
    s = get_workflow_status(workflow_id)
    if s is None:
        raise HTTPException(404, f"Workflow {workflow_id} not found")
    return {
        "workflow_id": workflow_id,
        "items": list_workflow_events(workflow_id, limit=limit),
    }
```

- [ ] **Step 3: Run backend smoke checks**

Run:

```powershell
python -m compileall server.py modules\orchestrator tests
python -m unittest tests.test_workflow_events tests.test_workflow_engine_logging tests.test_workflow_image_generation -v
```

Expected:

```text
Ran 6 tests

OK
```

---

## Task 4: Add Frontend Types and API Client

**Files:**
- Modify: `D:\0630\work\src\types.ts`
- Modify: `D:\0630\work\src\api\workflow.ts`

- [ ] **Step 1: Add workflow event types**

In `D:\0630\work\src\types.ts`, below `WorkflowStatus`, add:

```ts
export type WorkflowEventType = "started" | "succeeded" | "failed" | "warning" | "cancelled";

export interface WorkflowEvent {
  id: number;
  workflow_id: string;
  step_index: number;
  step_name: string;
  event_type: WorkflowEventType;
  message: string;
  duration_ms: number | null;
  error_type: string;
  error_traceback: string;
  input_summary: string;
  output_summary: string;
  created_at: string;
}

export interface WorkflowLogsResponse {
  workflow_id: string;
  items: WorkflowEvent[];
}
```

- [ ] **Step 2: Add the logs API function**

In `D:\0630\work\src\api\workflow.ts`, change the import to include `WorkflowLogsResponse`:

```ts
import {
  WorkflowStartResponse,
  WorkflowStatus,
  WorkflowResult,
  WorkflowLogsResponse,
} from "../types";
```

Add after `getWorkflowStatus()`:

```ts
export async function getWorkflowLogs(id: string, limit = 200): Promise<WorkflowLogsResponse> {
  return requestJson<WorkflowLogsResponse>(`/api/workflow/logs/${id}?limit=${limit}`);
}
```

- [ ] **Step 3: Run TypeScript validation**

Run:

```powershell
npm run lint
```

Expected:

```text
> ai-toolbox-work-frontend@0.0.0 lint
> tsc --noEmit
```

No TypeScript errors.

---

## Task 5: Render the Diagnostic Log Panel

**Files:**
- Modify: `D:\0630\work\src\components\WorkflowPage.tsx`

- [ ] **Step 1: Update imports**

Update the type import:

```ts
import { WorkflowStatus, WorkflowResult, KeyframeData, PromptConfig, WorkflowEvent } from "../types";
```

Update the API import:

```ts
import { startWorkflow, stopWorkflow, uploadProductImage, pollWorkflowUntilDone, getWorkflowLogs, WorkflowParams } from "../api/workflow";
```

- [ ] **Step 2: Add local log state**

Near the existing workflow state hooks, add:

```ts
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
```

- [ ] **Step 3: Add a safe log refresh helper**

Add near `handleCopy`:

```ts
  const refreshLogs = async (workflowId: string) => {
    try {
      const logs = await getWorkflowLogs(workflowId);
      setEvents(logs.items);
    } catch {
      // The status poll already shows the main error. Log refresh should not break the workflow UI.
    }
  };
```

- [ ] **Step 4: Clear old logs when a new workflow starts**

At the start of `handleStart`, before calling `startWorkflow`, add:

```ts
    setEvents([]);
```

- [ ] **Step 5: Refresh logs during polling**

Inside the `pollWorkflowUntilDone` status callback, after `setStatus(nextStatus)`, add:

```ts
          refreshLogs(workflow_id);
```

After `setResult(finalResult);`, add:

```ts
      refreshLogs(workflow_id);
```

Inside the `catch` block, add:

```ts
      if (workflowId) {
        refreshLogs(workflowId);
      }
```

- [ ] **Step 6: Add diagnostic text composition**

Add before the component `return`:

```ts
  const failedEvent = events.find((event) => event.event_type === "failed");
  const diagnosticText = [
    `任务: ${status?.id || result?.id || "未开始"}`,
    `状态: ${status?.status || result?.status || "idle"}`,
    `当前步骤: ${status?.step_index ?? 0} / ${status?.total_steps ?? 6} ${status?.current_step || ""}`,
    failedEvent ? `失败步骤: 第 ${failedEvent.step_index} 步 ${failedEvent.step_name}` : "",
    failedEvent ? `错误类型: ${failedEvent.error_type}` : "",
    failedEvent ? `错误原因: ${failedEvent.message}` : status?.error_message || result?.error_message || "",
    "",
    ...events.map((event) => {
      const duration = event.duration_ms == null ? "" : ` (${event.duration_ms}ms)`;
      return `[${event.created_at}] Step${event.step_index} ${event.step_name} ${event.event_type}${duration}: ${event.message}`;
    }),
  ].filter(Boolean).join("\n");
```

- [ ] **Step 7: Render the diagnostic panel**

In the result/status area of `WorkflowPage.tsx`, add this block near the existing progress/results cards:

```tsx
              {(events.length > 0 || status?.error_message || result?.error_message) && (
                <section className="bg-white border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Eye className="w-4 h-4 text-gray-500" />
                    <h3 className="font-bold text-gray-900 text-sm">运行诊断</h3>
                    <button
                      onClick={() => handleCopy(diagnosticText, "diagnostic")}
                      className="ml-auto text-xs text-blue-600 hover:text-blue-700 inline-flex items-center gap-1"
                    >
                      {copied === "diagnostic" ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                      <span>{copied === "diagnostic" ? "已复制" : "复制诊断"}</span>
                    </button>
                  </div>

                  {failedEvent && (
                    <div className="mb-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
                      <div className="font-bold">第 {failedEvent.step_index} 步失败：{failedEvent.step_name}</div>
                      <div className="mt-1 text-xs leading-relaxed">{failedEvent.message}</div>
                    </div>
                  )}

                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {events.map((event) => (
                      <div key={event.id} className="flex items-start gap-2 text-xs border-b border-gray-100 pb-2 last:border-b-0">
                        <span className="shrink-0 text-gray-400 w-32">{event.created_at}</span>
                        <span className={`shrink-0 px-2 py-0.5 rounded-full border ${
                          event.event_type === "failed"
                            ? "bg-red-50 text-red-700 border-red-200"
                            : event.event_type === "succeeded"
                              ? "bg-green-50 text-green-700 border-green-200"
                              : event.event_type === "cancelled"
                                ? "bg-yellow-50 text-yellow-700 border-yellow-200"
                                : "bg-blue-50 text-blue-700 border-blue-200"
                        }`}>
                          {event.event_type}
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="font-medium text-gray-800">
                            第 {event.step_index} 步 {event.step_name}
                            {event.duration_ms != null && <span className="ml-1 text-gray-400">({event.duration_ms}ms)</span>}
                          </div>
                          <div className="text-gray-500 leading-relaxed break-words">{event.message}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}
```

- [ ] **Step 8: Run TypeScript validation**

Run:

```powershell
npm run lint
```

Expected: no TypeScript errors.

---

## Task 6: Full Verification

**Files:**
- Verify only, no planned edits.

- [ ] **Step 1: Run all backend tests**

Run:

```powershell
python -m unittest discover -v
```

Expected:

```text
OK
```

- [ ] **Step 2: Compile backend files**

Run:

```powershell
python -m compileall server.py modules tests
```

Expected: compileall completes without syntax errors.

- [ ] **Step 3: Run frontend type check**

Run:

```powershell
npm run lint
```

Expected: no TypeScript errors.

- [ ] **Step 4: Build frontend**

Run:

```powershell
npm run build
```

Expected:

```text
vite v6
built in
```

- [ ] **Step 5: Manual smoke test**

Run backend:

```powershell
python server.py
```

In another terminal, start frontend:

```powershell
npm run dev
```

Open the local Vite URL and start a workflow. Confirm:

- The progress UI still shows 6 steps.
- The diagnostic panel fills as steps run.
- A simulated API failure shows the exact failed step.
- The "复制诊断" button copies workflow id, status, failed step, error, and event timeline.
- `D:\0630\work\logs\app.log` contains workflow start, success, failure, or cancellation lines.

---

## Self-Review

- Spec coverage: The plan records step start, success, failure, cancellation, exposes logs in the API, and renders a user-visible diagnostic panel.
- Placeholder scan: No unresolved placeholder language remains.
- Type consistency: Backend uses `workflow_events`, frontend uses `WorkflowEvent`, API uses `WorkflowLogsResponse`, and all event types match `started/succeeded/failed/warning/cancelled`.
- Scope check: The plan intentionally does not add video generation step 7, log search, exports, or admin monitoring. Those can be separate later features.

---

## Execution Options

Plan complete. Two execution options:

**1. Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.
