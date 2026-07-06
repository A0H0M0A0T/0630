"""
Image scorer — evaluates generated 4-panel image against storyboard expectations.
Uses GPT-4o Vision for multimodal analysis.
"""
import sys, os, json, random
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _ROOT)
from model_config import TUPIAN
from openai import OpenAI


SCORE_LEVELS = ["超低", "低", "中", "高", "超高"]

SCORING_PROMPT = """Analyze this 4-panel image (2x2 grid). It should represent 4 consecutive scenes from a storyboard.

Expected scenes:
- Panel 1 (top-left): {scene1}
- Panel 2 (top-right): {scene2}
- Panel 3 (bottom-left): {scene3}
- Panel 4 (bottom-right): {scene4}

Evaluate these dimensions (1-5 each):
1. Scene match: Do all 4 panels match their expected descriptions?
2. Product visibility: Is the S101 beer product clearly visible in at least 2 panels?
3. Realism: Does it look like real smartphone photos (not AI-generated)? Are there 4 distinct panels?
4. Composition: Is the 2x2 grid layout clear? Are the 4 scenes visually coherent as a sequence?
5. Style consistency: Do all 4 panels share the same lighting, color tone, and POV?

Output ONLY a JSON object (no markdown, no extra text):
{{"total_score": <sum of 5 dimensions>, "level": "<超低|低|中|高|超高>", "reason": "<brief Chinese reason covering all 4 panels>", "dimensions": {{"scene_match": <1-5>, "product_visibility": <1-5>, "realism": <1-5>, "composition": <1-5>, "style_consistency": <1-5>}}}}"""


def _score_to_level(total: int) -> str:
    if total >= 22: return "超高"
    if total >= 18: return "高"
    if total >= 13: return "中"
    if total >= 8: return "低"
    return "超低"


def score_image(image_url: str, keyframes: list) -> dict:
    """
    Returns: {"score": "高", "reason": "...", "dimensions": {...}}
    """
    client = OpenAI(base_url=TUPIAN["base_url"], api_key=TUPIAN["api_key"])

    # Build scene descriptions for each panel
    scene_parts = {}
    for i in range(4):
        label = f"scene{i+1}"
        if i < len(keyframes):
            kf = keyframes[i]
            scene_parts[label] = kf.get("description", f"分镜{i+1}")
        else:
            scene_parts[label] = f"分镜{i+1}（未提供）"

    prompt = SCORING_PROMPT.format(**scene_parts)

    response = client.chat.completions.create(
        model=TUPIAN["model"],
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
        max_tokens=600,
        temperature=0.3,
    )

    text = (response.choices[0].message.content or "").strip()

    try:
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)
    except json.JSONDecodeError:
        for level in SCORE_LEVELS:
            if level in text:
                return {"score": level, "reason": text[:200], "dimensions": {}}
        return {"score": "中", "reason": f"评分解析失败，默认中等。原始输出: {text[:200]}", "dimensions": {}}

    level = result.get("level", _score_to_level(result.get("total_score", 15)))
    return {
        "score": level,
        "reason": result.get("reason", ""),
        "dimensions": result.get("dimensions", {}),
    }


def score_all_images(image_urls: list, keyframes: list) -> list:
    """
    Score the 4-panel image. Returns a list with 1 score dict.
    If scoring fails, defaults to "中".
    """
    results = []
    for i, url in enumerate(image_urls):
        if not url:
            results.append({"score": "超低", "reason": "图片生成失败，无URL", "dimensions": {}, "index": 1})
            continue
        try:
            s = score_image(url, keyframes)
        except Exception as e:
            s = {"score": "中", "reason": f"评分异常: {str(e)[:100]}", "dimensions": {}}
        s["index"] = 1
        results.append(s)
    return results
