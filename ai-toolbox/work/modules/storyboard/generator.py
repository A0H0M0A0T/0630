"""
Storyboard generator — calls the 总导演 model to produce a 4-scene storyboard.
"""
import sys, os, random, re
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _ROOT)
from model_config import WENAN
from openai import OpenAI

from .prompts import STORY_PROMPTS
from .scene_pool import SCENE_POOL


def _get_client():
    return OpenAI(base_url=WENAN["base_url"], api_key=WENAN["api_key"])


def generate_storyboard(
    story_type: str,
    gender: str,
    scene: str,
    audience: str = "",
    weather: str = "随机",
    style: str = "随机",
    action: str = "随机",
    extra: str = "",
) -> dict:
    """
    Returns:
        {
            "story_type": "趣味性",
            "gender": "女",
            "scene": "出租屋小木桌",
            "storyboard_text": "完整原文...",
            "overview": "剧情概述...",
            "keyframes": [
                {"index": 1, "description": "...", "camera": "...", "composition": "..."},
                ...
            ]
        }
    """
    if story_type not in STORY_PROMPTS:
        story_type = "正常性"

    if not scene or scene == "随机":
        scene = random.choice(SCENE_POOL)

    if gender == "随机":
        gender = random.choice(["男", "女"])

    system_prompt = STORY_PROMPTS[story_type]

    # Build user message with all params
    extra_lines = []
    if audience and "随机" not in audience:
        extra_lines.append(f"目标人群：{audience}")
    if weather and weather != "随机":
        extra_lines.append(f"光线天气：{weather}")
    if style and style != "随机":
        extra_lines.append(f"视觉风格：{style}")
    if action and action != "随机":
        extra_lines.append(f"动作姿态：{action}")
    if extra:
        extra_lines.append(f"附加要求：{extra}")
    user_msg = f"场景：{scene}\n性别：{gender}"
    if extra_lines:
        user_msg += "\n" + "\n".join(extra_lines)
    user_msg += "\n请开始创作："

    client = _get_client()
    response = client.chat.completions.create(
        model=WENAN["model"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=2048,
        temperature=0.9,
        seed=random.randint(1, 99999),
    )

    full_text = (response.choices[0].message.content or "").strip()

    # Parse structured output
    overview = _extract_field(full_text, "剧情概述")
    parsed_scene = _extract_field(full_text, "场景") or scene
    parsed_gender = _extract_field(full_text, "性别") or gender

    keyframes = []
    for i in range(1, 5):
        kf_text = _extract_field(full_text, f"分镜{i}")
        if not kf_text:
            # Try alternative parsing: look for numbered sections
            alt_match = re.search(rf'(?:分镜|镜头|场景)\s*{i}[：:]\s*(.+?)(?=(?:分镜|镜头|场景)\s*{i+1}|$)', full_text, re.DOTALL)
            if alt_match:
                kf_text = alt_match.group(1).strip()
        if kf_text:
            kf_text = _normalize_keyframe_text(kf_text)
            # Split into description / camera / composition
            parts = re.split(r'[，,][\s]*运镜[：:]?|[\s]+运镜[：:]?|[，,][\s]*构图[：:]?|[\s]+构图[：:]?', kf_text, maxsplit=2)
            desc = parts[0].strip() if parts else kf_text
            cam = parts[1].strip() if len(parts) > 1 else ""
            comp = parts[2].strip() if len(parts) > 2 else ""
            keyframes.append({
                "index": i,
                "description": desc,
                "camera": cam,
                "composition": comp,
            })

    # Pad to 4 if parsing missed some
    while len(keyframes) < 4:
        idx = len(keyframes) + 1
        keyframes.append({
            "index": idx,
            "description": f"第{idx}个分镜：S101产品在{parsed_scene}中的画面",
            "camera": "固定镜头",
            "composition": "中景",
        })

    return {
        "story_type": story_type,
        "gender": parsed_gender,
        "scene": parsed_scene,
        "storyboard_text": full_text,
        "overview": overview,
        "keyframes": keyframes[:4],
    }


def _extract_field(text: str, field: str) -> str:
    """Extract field value from structured text like 【field】value"""
    # Try 【field】value format
    m = re.search(rf'【{field}】\s*(.+?)(?=\n【|\Z)', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Try field：value format
    m = re.search(rf'{field}[：:]\s*(.+?)(?=\n(?:【|[A-Za-z一-鿿]{{2,}}[：:])|\Z)', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


def _normalize_keyframe_text(text: str) -> str:
    """Remove placeholder headers and keep actual shot content."""
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^镜头描述\s*\+\s*运镜\s*\+\s*构图\s*[\r\n：:：-]*", "", cleaned).strip()
    cleaned = re.sub(r"^镜头描述\s*\+\s*[\r\n：:：-]*", "", cleaned).strip()

    desc = ""
    cam = ""
    comp = ""
    for line in cleaned.splitlines():
        item = line.strip().lstrip("-").strip()
        if not item:
            continue
        if item.startswith("镜头描述"):
            desc = re.sub(r"^镜头描述\s*[：:]\s*", "", item).strip()
        elif item.startswith("运镜"):
            cam = re.sub(r"^运镜\s*[：:]\s*", "", item).strip()
        elif item.startswith("构图"):
            comp = re.sub(r"^构图\s*[：:]\s*", "", item).strip()

    if desc:
        parts = [desc]
        if cam:
            parts.append(f"运镜：{cam}")
        if comp:
            parts.append(f"构图：{comp}")
        return "。".join(parts)
    return cleaned


def generate_batch():
    return None