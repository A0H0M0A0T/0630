"""
Shared platform type constants for social-auto-upload.

Used by both:
- sau_backend.py  (/postVideo, /postVideoBatch, /login routes)
- sau_cli.py       (CLI platform name resolution)

Single source of truth for platform-to-type mapping.
"""

XIAOHONGSHU = 1
TENCENT = 2
DOUYIN = 3
KUAISHOU = 4

PLATFORM_TYPE_MAP = {
    "xiaohongshu": XIAOHONGSHU,
    "tencent": TENCENT,
    "douyin": DOUYIN,
    "kuaishou": KUAISHOU,
}

TYPE_NAME_MAP = {v: k for k, v in PLATFORM_TYPE_MAP.items()}
