"""
Video generation integration module.

## Quick start for wiring a real provider

1. Set these environment variables (or edit model_config.py):

   VIDEO_PROVIDER   — provider name, e.g. "seedance" | "kling" | "jimeng"
   VIDEO_API_URL    — base URL for the provider's API
   VIDEO_API_KEY    — API key or token
   VIDEO_MODEL      — model identifier string

2. Implement two functions in client.py:

   _submit_to_provider(config, payload)
       POST a video generation job to the provider.
       payload keys: model, prompt, image_urls
       Must return: {video_status, video_job_id, video_url, video_error}

   _poll_provider_status(config, payload)
       Query job status from the provider.
       payload keys: provider, job_id
       Must return: {video_status, video_job_id, video_url, video_error}

3. That's it — the workflow engine, REST routes, and frontend
   already handle the rest.

## Frontend capabilities (already built)

- Refresh video status: POST /api/workflow/video-status/{id}
- Manual video URL backfill: POST /api/workflow/video-url/{id}
- Video player: displays when video_url is present
"""

from .client import check_video_generation_status, submit_video_generation

__all__ = ["check_video_generation_status", "submit_video_generation"]
