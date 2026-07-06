"""
Final video prompt assembler — produces structured prompts matching template format
for video generation models (Seedance, Kling, etc.).
"""
import sys, os, re

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _ROOT)

from modules.common.sanitize import sanitize_text


# ── Assembler-specific sanitize entries (common entries live in modules/common/sanitize.py) ──
_ASSEMBLER_EXTRA_SANITIZE: dict[str, str] = {
    "S l 0 l": "S101",
    "瓶子": "罐子",
}


def _sanitize_text(text: str) -> str:
    """Replace known AI hallucination patterns with correct terms."""
    result = sanitize_text(text, extra_map=_ASSEMBLER_EXTRA_SANITIZE)
    result = re.sub(r"S101(?:S101)+", "S101", result)
    result = re.sub(r"拉环盖(?:盖)+", "拉环盖", result)
    result = result.replace("啤酒杯靠近镜头", "饮用")
    result = result.replace("S101在桌面上", "手持S101")
    result = result.replace("S101和啤酒杯在桌面上", "手持S101和啤酒杯")
    result = result.replace("啤酒杯中金色啤酒泡沫丰富泡沫溢出", "啤酒倒入杯中，金色酒液和白色泡沫翻涌")
    result = result.replace("无人手部入镜", "无人露脸，仅手部入镜")
    result = result.replace("黑色S101拉环盖", "银色金属拉环盖")
    result = result.replace("黑色拉环盖", "银色金属拉环盖")
    result = result.replace("black pull-tab", "silver metal pull-tab")
    result = result.replace("好饮用", "好喝")
    result = result.replace("饮用又解腻", "好喝又解腻")
    return result


def _load_reference_context() -> dict:
    """Lazy-load reference files (avoids circular imports)."""
    from modules.orchestrator.engine import load_video_reference_context
    return load_video_reference_context()


def _clip_text(text: str, limit: int) -> str:
    """Keep reference snippets useful without flooding the final video prompt."""
    if not text:
        return ""
    cleaned = re.sub(r"\n{3,}", "\n\n", text.strip())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "\n……"


def _build_reference_brief(ref: dict) -> str:
    """Summarize local video/product references as execution constraints."""
    return (
        "【产品卖点参考】\n"
        "只使用这些安全卖点：S101苦荞精酿啤酒、黄色铝制1L高罐、10°P、"
        "苦荞风味、入口绵柔、回味荞香、28天左右发酵、纯粮酿造、"
        "适合家里厨房、出租屋木桌、背包旁、零食袋旁、普通玻璃杯等日常小酌场景。"
        "不得使用医疗功效、饮后承诺、三高、养生、保健等表述。\n\n"
        "【模板视频节奏参考】\n"
        "只学习快节奏结构、镜头组织、第一视角手部动作、开罐声、倒酒泡沫、"
        "冰块碰撞、产品特写和口播节奏；不要继承模板中的其他品牌、其他颜色包装、"
        "水果配料、小容量规格、低价卖点、全开盖设定或模板原文。"
        "四宫格必须像普通用户手机相册里的连续动作关键帧，不像啤酒广告海报。\n\n"
        "【S101素材图风格参考】\n"
        f"参考本地商品正视图 {os.path.join(_ROOT, 'static', 'video', '2.png')}。"
        "产品必须是黄色铝制高罐，黑色S标识，正面含S101、苦荞精酿啤酒、"
        "10°P、1L净含量，罐顶为银色金属易拉盖和拉环。"
    )


def _extract_scene_descriptions(keyframes: list, scores: list) -> list[str]:
    """Build per-panel description lines explaining the 4-grid layout."""
    positions = ["左上", "右上", "左下", "右下"]
    lines = []
    for i, kf in enumerate(keyframes):
        pos = positions[i] if i < 4 else f"第{i+1}"
        desc = kf.get("description", f"分镜{i+1}")
        if desc.strip() in ("镜头描述 +", "镜头描述 + 运镜 + 构图"):
            desc = "请参考对应四宫格画面，保持产品、场景、手部动作和构图一致。"
        desc = _sanitize_text(desc)
        image_url = ""
        if isinstance(kf, dict) and kf.get("image_url"):
            image_url = f"，素材地址：{kf.get('image_url')}"
        score_info = ""
        if i < len(scores):
            s = scores[i] if isinstance(scores, list) else scores
            if isinstance(s, dict):
                score_info = f" [评分:{s.get('score', '-')}]"
        lines.append(f"图{i+1}（{pos}格）：{desc}{image_url}{score_info}")
    return lines


def _merge_image_urls_into_keyframes(keyframes: list, image_urls: list | None) -> list:
    """Attach generated image URLs to keyframes without mutating workflow state."""
    if not image_urls:
        return keyframes
    merged = []
    for index, kf in enumerate(keyframes):
        item = dict(kf) if isinstance(kf, dict) else {"description": str(kf)}
        if index < len(image_urls):
            item["image_url"] = image_urls[index]
        elif len(image_urls) == 1:
            item["image_url"] = image_urls[0]
        merged.append(item)
    return merged


def assemble_video_prompt(
    storyboard_text: str,
    keyframes: list,
    scores: list,
    copy_text: str,
    gender: str,
    image_urls: list = None,
) -> str:
    """
    Build the final structured video prompt per template format:

    《帮我生成一个视频：
    （1）素材图解析：说明这是一张四宫格图片（非4张独立图），图1-图4对应左上/右上/左下/右下
    （2）排版编排剧情：原文（含@图引用、音效< >、旁白{ }）
    （3）文案诵读：男/女声 → 文案 → 结束
    （4）参考资料约束
    （5）视频模型执行要求：15秒快节奏，前3秒钩子，开罐/倒酒/泡沫/水珠特写，ASMR音效》
    """
    ref = _load_reference_context()

    # ── Voice gender: use substring match to avoid "男（手部...）" being misgendered ──
    if "女" in gender and "男" not in gender:
        voice = "女声"
    elif "男" in gender:
        voice = "男声"
    else:
        voice = "女声"  # default to female when ambiguous

    keyframes_with_urls = _merge_image_urls_into_keyframes(keyframes, image_urls)
    num = len(keyframes_with_urls)
    reference_brief = _build_reference_brief(ref)

    # ── Sanitize all inputs ──
    storyboard_text = _sanitize_text(storyboard_text)
    copy_text = _sanitize_text(copy_text)

    # ── (1) 素材图解析 (with 4-grid explanation) ──
    image_lines = _extract_scene_descriptions(keyframes_with_urls, scores)
    grid_explanation = (
        "【重要说明】以下素材图是 1 张四宫格图片（文件路径如 /generated/wf_xxx_img1.png），"
        "不是 4 张独立图片。这张四宫格图被均分为 2x2 四个格子："
        "左上格=图1、右上格=图2、左下格=图3、右下格=图4。"
        "整张四宫格为竖版，每格都是约2:3的竖版手机照片比例，不是正方形镜头。"
        "请按此对应关系理解各图的内容描述。"
    )
    image_analysis = grid_explanation + "\n" + "\n".join(image_lines)

    # ── (2) 排版编排剧情 ──
    storyboard_with_refs = _inject_image_refs(storyboard_text, num)

    # ── (3) 文案诵读 ──
    voiceover = f"第一秒开始，{voice}旁白：\n\"{copy_text}\"\n最后一秒人声结束"

    # ── (4) 视频模型执行要求 (15s fast rhythm, ASMR, product close-ups) ──
    exec_req = (
        "竖屏9:16，15秒左右，快节奏短视频广告。\n"
        "\n"
        "【前3秒强力钩子】必须包含以下至少一种特写：\n"
        "· 普通室内桌面上的 S101 黄色铝罐\n"
        "· 手从背包或塑料袋旁拿出产品\n"
        "· 手拉开银色金属拉环盖\n"
        "· 普通倒一杯到透明玻璃杯，泡沫自然\n"
        "\n"
        "【3-10秒场景展开】产品自然融入环境，镜头切换配合旁白节奏。\n"
        "\n"
        "【10-15秒高潮/CTA】产品成为画面绝对焦点，配合下单引导文案。\n"
        "\n"
        "【ASMR音效要求】开罐「噗嗤」声、倒酒气泡滋滋声、冰块碰杯叮当声、"
        "环境底噪（餐厅/户外/街道），旁白音量略大于环境音。\n"
        "\n"
        "【产品外观硬约束】S101 品牌 = 黄色铝制高罐易拉罐（yellow aluminum tall can），"
        "罐身主色黄色，黑色 S 标识在罐身上部，银色金属易拉盖和拉环，1L 容量，10°P 酒精度。"
        "严禁改成其他颜色或其他容器。\n"
        "\n"
        "【画质要求】真人实拍广告质感，第一视角（POV），无人露脸；"
        "画面像中低像素手机刚拍摄，有轻微真实模糊、自然手抖、普通室内光、构图不完美；"
        "重点保持 S101 黄色罐身、黑色 S 标识、苦荞精酿啤酒字样和 1L/10°P 信息稳定；"
        "不要字幕，不要水印，不要虚构其他品牌；不要夜市烧烤广告感、不要露营户外聚会、不要电影感、不要精致商业摄影、不要夸张泡沫。"
    )

    # ── Assemble ──
    final = f"""《帮我生成一个视频：

（1）素材图解析：
{image_analysis}

（2）排版编排剧情：
{storyboard_with_refs}

（3）文案诵读：
{voiceover}

（4）参考资料约束：
{reference_brief}

（5）视频模型执行要求：
{exec_req}》"""

    return _sanitize_text(final).replace("绿色§罐", "绿色罐")


def _inject_image_refs(storyboard: str, num_images: int) -> str:
    """Add @图N references to storyboard text where keyframes are mentioned."""
    lines = storyboard.split("\n")
    result = []
    for line in lines:
        injected = line
        for i in range(1, num_images + 1):
            if f"分镜{i}" in line and f"@图{i}" not in line:
                injected = injected.replace(f"分镜{i}", f"分镜{i}（@图{i}）")
        result.append(injected)
    return "\n".join(result)
