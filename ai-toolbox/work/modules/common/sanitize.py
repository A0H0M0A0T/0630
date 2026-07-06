"""
Shared sanitization rules for AI-generated text across the workflow pipeline.

Used by both the orchestrator engine and the video prompt assembler.
Each consumer may extend with its own stage-specific entries.
"""

# ── Common sanitize map — entries shared between engine.py and assembler.py ──
# Both files import this and append their own stage-specific entries.

COMMON_SANITIZE_MAP: dict[str, str] = {
    # ── Brand name corrections ──
    "SIOI": "S101",
    "si01": "S101",
    "s1o1": "S101",
    "S I O I": "S101",
    # ── Product name ──
    "苦苣": "苦荞",
    # ── Container type negation ──
    "不是玻璃瓶": "严禁改成其他容器",
    "不是绿色罐": "严禁改成其他颜色容器",
    "不是绿色瓶": "严禁改成其他颜色容器",
    "不是棕色瓶": "严禁改成其他颜色容器",
    # ── Color corrections ──
    "浅棕色瓶身": "黄色铝制高罐易拉罐罐身",
    "浅棕色": "黄色",
    "棕色瓶": "黄色铝制高罐易拉罐",
    "绿色罐": "黄色铝罐",
    "绿罐": "黄色铝罐",
    "绿色铝罐": "黄色铝罐",
    # ── Must precede "绿色罐" to avoid "深绿色罐" → "深黄色铝罐" ──
    "深绿色罐": "黄色铝罐",
    # ── Container type ──
    "玻璃瓶": "黄色铝制高罐易拉罐",
    "啤酒瓶": "啤酒罐",
    "酒瓶": "易拉罐",
    "一瓶S101": "一罐S101",
    "一瓶 S101": "一罐 S101",
    "一瓶": "一罐",
    "瓶身": "罐身",
    "瓶口": "罐口",
    "瓶盖": "拉环盖",
    # ── Face / body → no-face policy ──
    "靠近嘴唇": "靠近镜头",
    "嘴唇": "镜头前方",
    "喝一口": "杯口靠近镜头，手部动作暗示饮用",
    "下巴": "面部",
    "半张脸": "面部",
    "侧脸": "面部",
    "表情": "手部动作",
    # ── Health claims → compliant phrasing ──
    "健康劲儿": "荞香口感",
    "健康清爽": "清爽",
    "不上头": "口感绵柔",
    "不头疼": "口感绵柔",
    "三高": "聚会小酌",
    "养生": "风味",
    "降血压": "风味独特",
    "降血糖": "风味独特",
    "降血脂": "风味独特",
    "软化血管": "风味独特",
}


def sanitize_text(text: str, extra_map: dict[str, str] | None = None) -> str:
    """Apply common sanitization rules, then any stage-specific extras.

    Returns empty string for falsy input.
    """
    if not text:
        return ""
    result = text
    for wrong, correct in COMMON_SANITIZE_MAP.items():
        result = result.replace(wrong, correct)
    if extra_map:
        for wrong, correct in extra_map.items():
            result = result.replace(wrong, correct)
    return result
