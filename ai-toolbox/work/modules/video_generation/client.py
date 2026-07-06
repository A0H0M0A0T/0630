"""
Video generation client — provider integration shell.

═══════════════════════════════════════════════════════════════════════════════
ARCHITECTURE
═══════════════════════════════════════════════════════════════════════════════

This module defines the stable contract between the workflow engine and ANY
video generation provider (Seedance, Kling, Jimeng, Vidu, etc.).

The public API — submit_video_generation() and check_video_generation_status()
— is called by WorkflowEngine (engine.py) and the REST routes (server.py).
They do NOT change when you swap providers.

Provider-specific logic lives in two private functions:

    _submit_to_provider(config, payload)   → POST a new video job
    _poll_provider_status(config, payload) → query an existing job

Only these two functions need to be rewritten when wiring a real provider.
Everything else (state persistence, HTTP routes, frontend UI) is provider-agnostic.

═══════════════════════════════════════════════════════════════════════════════
CONFIGURATION
═══════════════════════════════════════════════════════════════════════════════

Set these environment variables before starting the server:

    VIDEO_PROVIDER    e.g. "seedance", "kling", "jimeng", "vidu"
    VIDEO_API_URL     provider's HTTP API base URL
    VIDEO_API_KEY     API key or bearer token
    VIDEO_MODEL       model identifier string for the provider

When none are set (current state), both public functions return
video_status="not_configured" without making any HTTP calls.

═══════════════════════════════════════════════════════════════════════════════
RETURN SHAPE CONTRACT
═══════════════════════════════════════════════════════════════════════════════

Every function in this module MUST return a dict with exactly these four keys:

    {
        "video_status":  str,   # one of the status values below
        "video_job_id":  str,   # provider-assigned job ID, "" if none
        "video_url":     str,   # final video URL, "" until completed
        "video_error":   str,   # human-readable error, "" on success
    }

Standard video_status values (add provider-specific ones as needed):

    not_configured   — no provider env vars set
    submitted        — job accepted, queued
    running          — generation in progress
    completed        — video_url is ready
    failed           — terminal error, see video_error

The WorkflowState (state.py) stores all four fields per workflow run.
The REST API always returns all four fields.
The frontend reads all four fields.

═══════════════════════════════════════════════════════════════════════════════
FRONTEND INTEGRATION (already built — no changes needed)
═══════════════════════════════════════════════════════════════════════════════

POST /api/workflow/video-status/{workflow_id}
    Refreshes video job status from the provider.
    If video_job_id is set, calls check_video_generation_status().
    Otherwise returns current state as-is.

POST /api/workflow/video-url/{workflow_id}
    Manual backfill. Accepts {"video_url": "..."}.
    Sets video_status="completed", clears video_error.
    Useful before a real provider is wired in.

WorkflowPage.tsx Step 7 card:
    - "刷新状态" button → calls the refresh endpoint
    - Input + "保存" button → calls the backfill endpoint
    - <video> player → shown when video_url is present

═══════════════════════════════════════════════════════════════════════════════
INTEGRATION CHECKLIST (for wiring a real provider)
═══════════════════════════════════════════════════════════════════════════════

1. Read the provider's API docs (job submission + status polling endpoints).
2. Update _submit_to_provider() — POST a job, return the four-field dict.
3. Update _poll_provider_status() — GET job status, return the four-field dict.
4. Set VIDEO_PROVIDER / VIDEO_API_URL / VIDEO_API_KEY / VIDEO_MODEL env vars.
5. Restart the server.
6. Run a workflow — Step 7 will now submit to the real provider.
7. Use the frontend "刷新状态" button to poll, or wait for polling logic (TBD).

No other files need to change.
"""
from dataclasses import dataclass
import os
from typing import Any


# ── Environment variable keys ──────────────────────────────────────────────
# Set these before starting the server to activate a real video provider.
# When all are empty, the module returns "not_configured" for every call.

VIDEO_PROVIDER_ENV = "VIDEO_PROVIDER"   # provider name slug
VIDEO_API_URL_ENV = "VIDEO_API_URL"     # base URL for the provider's HTTP API
VIDEO_API_KEY_ENV = "VIDEO_API_KEY"     # API key or bearer token
VIDEO_MODEL_ENV = "VIDEO_MODEL"         # model identifier string


# ── Config dataclass ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class VideoGenerationConfig:
    """Immutable config loaded from environment variables.

    is_configured is True only when provider, api_url, and api_key are all set.
    The public API functions use this to decide whether to call provider logic
    or return a "not_configured" placeholder.
    """
    provider: str
    api_url: str
    api_key: str
    model: str

    @property
    def is_configured(self) -> bool:
        return bool(self.provider and self.api_url and self.api_key)


def load_video_generation_config() -> VideoGenerationConfig:
    """Read provider credentials from environment variables."""
    return VideoGenerationConfig(
        provider=os.getenv(VIDEO_PROVIDER_ENV, "").strip(),
        api_url=os.getenv(VIDEO_API_URL_ENV, "").strip(),
        api_key=os.getenv(VIDEO_API_KEY_ENV, "").strip(),
        model=os.getenv(VIDEO_MODEL_ENV, "").strip(),
    )


# ── Payload builders ───────────────────────────────────────────────────────
# These build provider-specific request bodies. Override payload shape here
# if the provider's API expects different field names.

def build_video_generation_payload(
    video_prompt: str,
    image_urls: list[str] | None = None,
    config: VideoGenerationConfig | None = None,
) -> dict[str, Any]:
    """Build the request payload for submitting a new video generation job."""
    cfg = config or load_video_generation_config()
    return {
        "model": cfg.model,
        "prompt": video_prompt,
        "image_urls": image_urls or [],
    }


def build_video_status_payload(
    video_job_id: str,
    config: VideoGenerationConfig | None = None,
) -> dict[str, Any]:
    """Build the request payload for querying a video job's status."""
    cfg = config or load_video_generation_config()
    return {
        "provider": cfg.provider,
        "job_id": video_job_id,
    }


# ── Provider implementation (REPLACE THESE TWO FUNCTIONS) ──────────────────
#
# These are the ONLY functions you need to rewrite to wire a real provider.
# Each receives a VideoGenerationConfig and a payload dict.
# Each MUST return {video_status, video_job_id, video_url, video_error}.
#
# Example for a hypothetical provider:
#
#   def _submit_to_provider(config, payload):
#       resp = requests.post(
#           f"{config.api_url}/v1/videos",
#           headers={"Authorization": f"Bearer {config.api_key}"},
#           json={"model": payload["model"], "prompt": payload["prompt"]},
#           timeout=30,
#       )
#       data = resp.json()
#       return {
#           "video_status": "submitted",
#           "video_job_id": data["id"],
#           "video_url": "",
#           "video_error": "",
#       }
#
#   def _poll_provider_status(config, payload):
#       resp = requests.get(
#           f"{config.api_url}/v1/videos/{payload['job_id']}",
#           headers={"Authorization": f"Bearer {config.api_key}"},
#           timeout=10,
#       )
#       data = resp.json()
#       return {
#           "video_status": data["status"],        # map provider status
#           "video_job_id": payload["job_id"],
#           "video_url": data.get("video_url", ""),
#           "video_error": data.get("error", ""),
#       }

def _submit_to_provider(config: VideoGenerationConfig, payload: dict[str, Any]) -> dict:
    """API docking point: implement provider-specific HTTP submission here.

    Called by submit_video_generation() when config.is_configured is True.

    Args:
        config: VideoGenerationConfig with provider, api_url, api_key, model.
        payload: dict from build_video_generation_payload() with keys
                 model, prompt, image_urls.

    Returns:
        dict with keys video_status, video_job_id, video_url, video_error.
    """
    return {
        "video_status": "not_configured",
        "video_job_id": "",
        "video_url": "",
        "video_error": f"视频模型供应商 {config.provider} 已配置，但真实提交逻辑尚未实现。",
    }


def _poll_provider_status(config: VideoGenerationConfig, payload: dict[str, Any]) -> dict:
    """API docking point: implement provider-specific status polling here.

    Called by check_video_generation_status() when config.is_configured is True
    and video_job_id is non-empty.

    Args:
        config: VideoGenerationConfig with provider, api_url, api_key, model.
        payload: dict from build_video_status_payload() with keys
                 provider, job_id.

    Returns:
        dict with keys video_status, video_job_id, video_url, video_error.
    """
    return {
        "video_status": "not_configured",
        "video_job_id": payload.get("job_id", ""),
        "video_url": "",
        "video_error": f"视频模型供应商 {config.provider} 已配置，但状态查询逻辑尚未实现。",
    }


# ── Public API (called by engine.py and server.py) ─────────────────────────
# Do NOT change the signatures or return shapes of these two functions.
# They are the stable contract consumed by the rest of the system.

def submit_video_generation(video_prompt: str, image_urls: list[str] | None = None) -> dict:
    """Submit a new video generation job. Called by WorkflowEngine Step 7.

    When no provider is configured, returns a non-failing placeholder so the
    workflow completes and the user can still see the final video prompt.
    """
    config = load_video_generation_config()
    if not config.is_configured:
        return {
            "video_status": "not_configured",
            "video_job_id": "",
            "video_url": "",
            "video_error": "视频模型 API 位置已预留，尚未配置供应商、地址或密钥。",
        }

    payload = build_video_generation_payload(video_prompt, image_urls, config)
    return _submit_to_provider(config, payload)


def check_video_generation_status(video_job_id: str) -> dict:
    """Query the status of a submitted video job.

    Called by POST /api/workflow/video-status/{workflow_id} (server.py)
    and can be used by a future polling loop in the engine.
    """
    config = load_video_generation_config()
    if not video_job_id:
        return {
            "video_status": "not_configured",
            "video_job_id": "",
            "video_url": "",
            "video_error": "视频任务 ID 为空，无法查询状态。",
        }
    if not config.is_configured:
        return {
            "video_status": "not_configured",
            "video_job_id": video_job_id,
            "video_url": "",
            "video_error": "视频模型 API 位置已预留，尚未配置供应商、地址或密钥。",
        }

    payload = build_video_status_payload(video_job_id, config)
    return _poll_provider_status(config, payload)
