"""
Workflow state persistence — SQLite-backed task state for the 8-step pipeline.
"""
import sqlite3
import json
import os
import uuid
import time
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
DB_PATH = os.path.join(_ROOT, "workflows.db")


def _safe_json_loads(raw: str):
    """json.loads with defensive try/except, returns None on corruption."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _trim_text(value: str | None, limit: int = 8000) -> str:
    if not value:
        return ""
    text = str(value)
    if len(text) <= limit:
        return text
    suffix = "[TRUNCATED]"
    return text[: max(0, limit - len(suffix))] + suffix


def init_workflow_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            story_type TEXT NOT NULL DEFAULT '正常性',
            gender TEXT DEFAULT '随机',
            scene TEXT DEFAULT '随机',
            status TEXT NOT NULL DEFAULT 'pending',
            current_step TEXT DEFAULT '',
            step_index INTEGER DEFAULT 0,
            total_steps INTEGER DEFAULT 8,
            product_image TEXT DEFAULT '',
            model TEXT DEFAULT 'deepseek4',
            audience TEXT DEFAULT '',
            weather TEXT DEFAULT '随机',
            style_param TEXT DEFAULT '随机',
            action_param TEXT DEFAULT '随机',
            extra TEXT DEFAULT '',
            aspect_ratio TEXT DEFAULT '1:1',
            storyboard_text TEXT DEFAULT '',
            keyframes_json TEXT DEFAULT '[]',
            image_prompts_json TEXT DEFAULT '[]',
            image_urls_json TEXT DEFAULT '[]',
            scores_json TEXT DEFAULT '[]',
            copy_text TEXT DEFAULT '',
            video_prompt TEXT DEFAULT '',
            video_status TEXT DEFAULT '',
            video_job_id TEXT DEFAULT '',
            video_url TEXT DEFAULT '',
            video_error TEXT DEFAULT '',
            error_message TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
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
    # Migration: add new columns if missing (for DBs created before schema update)
    for col, col_type in [
        ("model", "TEXT DEFAULT 'deepseek4'"),
        ("audience", "TEXT DEFAULT ''"),
        ("weather", "TEXT DEFAULT '随机'"),
        ("style_param", "TEXT DEFAULT '随机'"),
        ("action_param", "TEXT DEFAULT '随机'"),
        ("extra", "TEXT DEFAULT ''"),
        ("aspect_ratio", "TEXT DEFAULT '1:1'"),
        ("video_status", "TEXT DEFAULT ''"),
        ("video_job_id", "TEXT DEFAULT ''"),
        ("video_url", "TEXT DEFAULT ''"),
        ("video_error", "TEXT DEFAULT ''"),
        ("hashtags_json", "TEXT DEFAULT ''"),
    ]:
        try:
            conn.execute(f"ALTER TABLE workflows ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass  # Column already exists
    conn.commit()
    conn.close()


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


class WorkflowState:
    """In-memory + DB-backed state for one workflow run."""

    def __init__(self, workflow_id: str = None):
        if workflow_id:
            self.id = workflow_id
            self._load()
        else:
            self.id = f"wf_{uuid.uuid4().hex[:12]}"
            self.user_id = None
            self.story_type = "正常性"
            self.gender = "随机"
            self.scene = "随机"
            self.status = "pending"
            self.current_step = ""
            self.step_index = 0
            self.total_steps = 8
            self.product_image = ""
            # 高级参数
            self.model = "deepseek4"
            self.audience = "默认随机(按画像比例55/15/30)"
            self.weather = "随机"
            self.style = "随机"
            self.action = "随机"
            self.extra = ""
            self.aspect_ratio = "1:1"
            # 步骤产出
            self.storyboard_text = ""
            self.keyframes = []
            self.image_prompts = []
            self.image_urls = []
            self.scores = []
            self.copy_text = ""
            self.video_prompt = ""
            self.video_status = ""
            self.video_job_id = ""
            self.video_url = ""
            self.video_error = ""
            self.error_message = ""
            self.hashtags_json = ""

    def _load(self):
        conn = _get_conn()
        row = conn.execute("SELECT * FROM workflows WHERE id=?", (self.id,)).fetchone()
        conn.close()
        if not row:
            raise ValueError(f"Workflow {self.id} not found")
        d = dict(row)
        self.user_id = d.get("user_id")
        self.story_type = d.get("story_type", "正常性")
        self.gender = d.get("gender", "随机")
        self.scene = d.get("scene", "随机")
        self.status = d.get("status", "pending")
        self.current_step = d.get("current_step", "")
        self.step_index = d.get("step_index", 0)
        self.total_steps = d.get("total_steps", 8)
        self.product_image = d.get("product_image", "")
        self.model = d.get("model", "deepseek4")
        self.audience = d.get("audience", "")
        self.weather = d.get("weather", "随机")
        self.style = d.get("style_param", "随机")
        self.action = d.get("action_param", "随机")
        self.extra = d.get("extra", "")
        self.aspect_ratio = d.get("aspect_ratio", "1:1")
        self.storyboard_text = d.get("storyboard_text", "")
        self.keyframes = json.loads(d.get("keyframes_json", "[]"))
        self.image_prompts = json.loads(d.get("image_prompts_json", "[]"))
        self.image_urls = json.loads(d.get("image_urls_json", "[]"))
        self.scores = json.loads(d.get("scores_json", "[]"))
        self.copy_text = d.get("copy_text", "")
        self.video_prompt = d.get("video_prompt", "")
        self.video_status = d.get("video_status", "")
        self.video_job_id = d.get("video_job_id", "")
        self.video_url = d.get("video_url", "")
        self.video_error = d.get("video_error", "")
        self.error_message = d.get("error_message", "")
        self.hashtags_json = d.get("hashtags_json", "")

    def save(self):
        conn = _get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO workflows
            (id, user_id, story_type, gender, scene, status, current_step,
             step_index, total_steps, product_image, model, audience, weather,
             style_param, action_param, extra, aspect_ratio, storyboard_text,
             keyframes_json, image_prompts_json, image_urls_json,
             scores_json, copy_text, video_prompt, video_status, video_job_id,
             video_url, video_error, error_message, hashtags_json, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            self.id, self.user_id, self.story_type, self.gender, self.scene,
            self.status, self.current_step, self.step_index, self.total_steps,
            self.product_image, self.model, self.audience, self.weather,
            self.style, self.action, self.extra, self.aspect_ratio,
            self.storyboard_text,
            json.dumps(self.keyframes, ensure_ascii=False),
            json.dumps(self.image_prompts, ensure_ascii=False),
            json.dumps(self.image_urls, ensure_ascii=False),
            json.dumps(self.scores, ensure_ascii=False),
            self.copy_text, self.video_prompt,
            self.video_status, self.video_job_id, self.video_url, self.video_error,
            self.error_message, self.hashtags_json, _now(),
        ))
        conn.commit()
        conn.close()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "story_type": self.story_type,
            "gender": self.gender,
            "scene": self.scene,
            "status": self.status,
            "current_step": self.current_step,
            "step_index": self.step_index,
            "total_steps": self.total_steps,
            "product_image": self.product_image,
            "model": self.model,
            "audience": self.audience,
            "weather": self.weather,
            "style": self.style,
            "action": self.action,
            "extra": self.extra,
            "aspect_ratio": self.aspect_ratio,
            "storyboard_text": self.storyboard_text,
            "keyframes": self.keyframes,
            "image_prompts": self.image_prompts,
            "image_urls": self.image_urls,
            "scores": self.scores,
            "copy_text": self.copy_text,
            "video_prompt": self.video_prompt,
            "video_status": self.video_status,
            "video_job_id": self.video_job_id,
            "video_url": self.video_url,
            "video_error": self.video_error,
            "error_message": self.error_message,
            "hashtags": _safe_json_loads(self.hashtags_json) if self.hashtags_json else None,
        }

    def to_status_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "current_step": self.current_step,
            "step_index": self.step_index,
            "total_steps": self.total_steps,
            "error_message": self.error_message,
        }


def list_workflow_history(limit: int = 20) -> list[dict]:
    """Return recent workflows that have generated images, newest first."""
    safe_limit = max(1, min(int(limit or 20), 100))
    init_workflow_db()
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT id, story_type, scene, gender, status,
               image_urls_json, image_prompts_json,
               copy_text, video_prompt, error_message,
               created_at
        FROM workflows
        WHERE image_urls_json IS NOT NULL AND image_urls_json != '' AND image_urls_json != '[]'
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (safe_limit,),
    ).fetchall()
    conn.close()

    results = []
    for row in rows:
        d = dict(row)
        image_urls = json.loads(d.pop("image_urls_json", "[]"))
        image_prompts = json.loads(d.pop("image_prompts_json", "[]"))
        d["image_urls"] = image_urls
        d["image_prompt"] = image_prompts[0] if image_prompts else ""
        results.append(d)
    return results
