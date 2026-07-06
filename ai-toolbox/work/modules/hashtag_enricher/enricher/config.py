"""
config.py — bridge to ai-toolbox's model_config.py.

Replaces the original .env + config.yaml setup with model_config.WENAN.
Exposes a `settings` object with the same interface as the original hashtag-enricher config.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Navigate to project root to import model_config
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))  # 3 levels up = work/
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from model_config import WENAN


class _HashtagSettings:
    """Drop-in replacement for the original Settings class, reading from model_config."""

    def __init__(self):
        # ── LLM configuration (from model_config.WENAN) ──
        self.api_key: str = WENAN.get("api_key", "")
        self.base_url: str = WENAN.get("base_url", "https://api.deepseek.com/v1")
        self.model: str = WENAN.get("model", "deepseek-chat")

        # ── Tag configuration (hard-coded defaults; adjustable via env) ──
        self.platform: str = os.getenv("HASHTAG_PLATFORM", "youtube")
        self.min_tags: int = int(os.getenv("HASHTAG_MIN_TAGS", "3"))
        self.max_tags: int = int(os.getenv("HASHTAG_MAX_TAGS", "5"))
        self.max_tag_length: int = int(os.getenv("HASHTAG_MAX_TAG_LENGTH", "20"))
        self.supports_temperature: bool = os.getenv("HASHTAG_SUPPORTS_TEMPERATURE", "true").lower() == "true"

        # ── Always-include tags (list preserves insertion order, deduplicated) ──
        raw_tags = [tag.strip() for tag in os.getenv("HASHTAG_ALWAYS_INCLUDE", "#shorts").split(",") if tag.strip()]
        self.always_include: list[str] = list(dict.fromkeys(raw_tags)) or ["#shorts"]

        # ── Banned tags ──
        banned_raw = os.getenv("HASHTAG_BANNED_TAGS", "")
        self.banned_tags: frozenset[str] = frozenset(
            tag.strip().lower() for tag in banned_raw.split(",") if tag.strip()
        )

        # ── Logging ──
        self.log_file: Path = Path(_ROOT) / "logs" / "hashtag_enricher.log"
        self.max_log_size: int = 10 * 1024 * 1024  # 10 MB

        # ── Prompt templates (same as original config.yaml.example) ──
        self.prompt_detect_language: str = (
            'What language is the following text written in or intended for?\n'
            'Reply with ONLY the language name in English (e.g. "English", "Spanish", "Russian").\n'
            'Do not add any explanation or punctuation — just the language name.\n'
            'Text: "{text}"'
        )

        self.prompt_detect_and_generate: str = (
            'You are a {platform} short-form video SEO specialist.\n\n'
            'Video topic: "{video_subject}"\n\n'
            "Task 1: Detect the language this content is in or intended for.\n"
            "Task 2: Generate between {min_tags} and {max_tags} SEO hashtags for {platform}.\n\n"
            "Hashtag rules:\n"
            "- Primary tags (2-3): highly specific to THIS video's unique angle\n"
            "- Secondary tags (1-2): niche-specific, medium competition\n"
            "- All tags in the detected language\n"
            "- Lowercase only, no CamelCase\n"
            "- Preserve diacritics (e.g. #recuperación, #astronomía)\n"
            "- Max {max_tag_length} characters per tag (after #)\n"
            "- Tags to EXCLUDE (already included automatically): {excluded_tags}\n\n"
            "Respond ONLY with a JSON object — no markdown, no explanation:\n"
            '{{"language": "English", "tags": ["#tag1", "#tag2", "#tag3"]}}\n\n'
            "Few-shot examples:\n"
            'topic "ostriches never bury heads" →\n'
            '{{"language": "English", "tags": ["#ostrichfacts", "#ostrichmyths", "#birdmyths", "#animalscience"]}}\n'
            'topic "nadie puede oír tus gritos en el espacio" →\n'
            '{{"language": "Spanish", "tags": ["#silencioenelespacio", "#sonidoenelespacio", "#vacíoespacial", "#curiosidadescósmicas"]}}'
        )

        self.prompt_generate: str = (
            'You are a {platform} short-form video SEO specialist applying 2026 best practices.\n\n'
            'Video topic: "{video_subject}"\n'
            "Target language: {language}\n"
            "Target platform: {platform}\n\n"
            "Generate between {min_tags} and {max_tags} CONTENT hashtags.\n\n"
            "── PRIORITY ORDER (most to least important) ──────────────────────────────────\n\n"
            "PRIMARY tags (generate 2-3):\n"
            '  Highly specific to THIS video\'s unique angle.\n'
            '  Ask yourself: "What would someone type into {platform} search to find exactly this video?"\n'
            "  Good examples:\n"
            '    topic "ostriches don\'t bury heads"    → #ostrichfacts  #ostrichmyths  #birdmyths\n'
            '    topic "sound impossible in space"     → #silencioenelespacio  #sonidoenelespacio\n'
            '    topic "opossum involuntarily faints"  → #involuntaryfainting  #opossumfacts\n'
            "  Bad examples (do NOT generate these):\n"
            "    ❌ #animals  ❌ #nature  ❌ #wildlife  ❌ #science  ❌ #espacio  ❌ #ciencia\n\n"
            "SECONDARY tags (generate 1-2):\n"
            '  Describe the broader niche — medium competition level (not mega-popular, not obscure).\n'
            '  Think: "What community or sub-topic does this video belong to?"\n'
            "  Good examples: #animalscience  #astronomía  #curiosidadesdeluniverso  #animalbehavior\n\n"
            "── STRICT FORMATTING RULES ──────────────────────────────────────────────────\n"
            "- All hashtags in {language} — never mix languages\n"
            "- Every hashtag starts with #, no spaces inside\n"
            "- ALL LOWERCASE — no CamelCase, no capitals\n"
            "- Preserve native diacritics: #recuperación, #astronomía, #ñoño (NOT stripped)\n"
            "- Max {max_tag_length} characters per hashtag (counting only the part after #)\n"
            "- No duplicate tags\n\n"
            "── QUALITY RULES ────────────────────────────────────────────────────────────\n"
            "- Relevance over volume — a niche tag beats a mega-tag every time\n"
            "- NO off-topic tags (don't add #astronautas to a video about sound in a vacuum)\n"
            "- NO awkward keyword-stuffed compounds (#didyouknowostriches, #funfactsaboutanimals)\n\n"
            "Tags to EXCLUDE entirely (they are added automatically — do NOT include them):\n"
            "{excluded_tags}\n\n"
            "── OUTPUT FORMAT ────────────────────────────────────────────────────────────\n"
            "Return ONLY a valid JSON array of strings — no markdown fences, no explanation, nothing else.\n\n"
            "Few-shot examples:\n\n"
            'English / youtube / topic "ostriches don\'t bury heads":\n'
            '["#ostrichfacts", "#ostrichmyths", "#birdmyths", "#animalscience"]\n\n'
            'Spanish / youtube / topic "sound impossible in space":\n'
            '["#silencioenelespacio", "#sonidoenelespacio", "#vacíoespacial", "#curiosidadescósmicas"]\n\n'
            'English / tiktok / topic "opossum involuntarily faints":\n'
            '["#opossumfacts", "#involuntaryfainting", "#animalbiology", "#wildlifefacts"]\n\n'
            'Spanish / instagram / topic "moon fits inside Russia":\n'
            '["#lalunacaberusia", "#curiosidadesdeluniverso", "#astronomía", "#datoscuriosos"]'
        )


settings = _HashtagSettings()


def validate_tag_budget(platform: str, max_tags: int, always_include_count: int) -> None:
    """
    Validate that max_tags + always_include fits within the platform hard limit.
    Raises ValueError if not.
    """
    from .postprocess import platform_hard_limit
    limit = platform_hard_limit(platform)
    total = max_tags + always_include_count
    if total > limit:
        raise ValueError(
            f"max_tags ({max_tags}) + always_include ({always_include_count}) = {total} "
            f"exceeds {platform} hard limit of {limit}"
        )
