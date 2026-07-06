"""
Workflow engine — runs the 8-step pipeline in a background thread.
"""
import sys, os, time, random, threading, requests, base64, re, traceback, json
from PIL import Image

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "modules", "hashtag_enricher"))

from .state import WorkflowState, init_workflow_db, record_workflow_event
from modules.tupian.logger import get_logger
from modules.common.sanitize import sanitize_text
from modules.common.text_utils import trigram_jaccard
from modules.storyboard.generator import generate_storyboard
from modules.keyframe.extractor import extract_keyframe_prompts, build_image_prompt_pack
from modules.scorer.scorer import score_all_images
from modules.video_prompt.assembler import assemble_video_prompt
from modules.video_generation.client import submit_video_generation

from model_config import GPT_IMAGE, TUPIAN


# In-memory registry of running engines (for status polling)
_engines: dict = {}

# ── Reference context (loaded once at module import) ──
_REFERENCE_CONTEXT: dict = {}
_REFERENCE_LOADED = False


def load_video_reference_context() -> dict:
    """Load all reference files for video prompt generation. Cached after first call."""
    global _REFERENCE_CONTEXT, _REFERENCE_LOADED
    if _REFERENCE_LOADED:
        return _REFERENCE_CONTEXT

    video_dir = os.path.join(_ROOT, "static", "video")
    ctx = {}

    def _read(relpath: str) -> str:
        p = os.path.join(video_dir, relpath)
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    ctx["product_data"] = _read("公司产品数据.txt")
    ctx["video_prompt_template"] = _read("模板视频分析结果/适用于视频模型理解的提示词.txt")
    ctx["original_storyboard"] = _read("模板视频分析结果/原片分镜.txt")
    ctx["deep_analysis"] = _read("模板视频分析结果/视频深度分析结果.txt")
    ctx["product_image_analysis"] = _read("模板图分析结果/S101素材图分析结果.txt")

    # Default product image for video workflow
    default_product = os.path.join(video_dir, "2.png")
    if os.path.isfile(default_product):
        ctx["default_product_path"] = default_product

    _REFERENCE_CONTEXT = ctx
    _REFERENCE_LOADED = True
    logger.info("video reference context loaded: %d files", len([v for v in ctx.values() if v]))
    return ctx

logger = get_logger("workflow")

# ── Product description cache (per path + prompt version, invalidated when prompt changes) ──
_PRODUCT_DESC_PROMPT_VERSION = 3  # bump to invalidate old (incorrect) caches — v3 adds sanitization
_product_desc_cache: dict = {}


PRODUCT_ANALYSIS_PROMPT = """You are a product photographer's assistant. Analyze this product image and output an EXTREMELY DETAILED description to be used as a text reference for AI image generation (gpt-image-2).

FIRST: Identify the product type — is it a glass bottle, aluminum can, plastic bottle, etc.? Look carefully at the material, reflections, and shape.

Include EVERY detail — an artist must be able to reproduce this exact product from your words alone:

1. CONTAINER TYPE & MATERIAL: aluminum tall can / glass bottle / etc., exact material finish (matte, metallic, glossy)
2. SHAPE: exact silhouette, height-to-width proportions, slim/tall vs short/wide, any ridges or contours
3. COLOR: exact body color(s), label background color(s), top/cap color, any gradients
4. LABEL DESIGN: every element — text content (copy EXACT Chinese characters), logo, graphics, border patterns, placement
5. CLOSURE: pull-tab ring, crown cap, screw cap — exact color and type
6. TEXT: write out every visible character/word exactly as it appears (Chinese, numbers, English)
7. SIZE/VOLUME: if any ml/L info is visible, copy it exactly
8. DISTINCTIVE FEATURES: anything unique — color combinations, patterns, shapes

CRITICAL: Be accurate about container type. Aluminum can ≠ glass bottle. Yellow ≠ brown. Get the colors right.

Output format: One paragraph in Chinese, then one paragraph in English. Keep under 400 words total. NO markdown, NO bullet points."""


def _analyze_product_image(image_path: str) -> str:
    """Return the approved S101 product description instead of trusting OCR."""
    cache_key = f"v{_PRODUCT_DESC_PROMPT_VERSION}:{os.path.normcase(os.path.abspath(image_path or 's101'))}"
    _product_desc_cache[cache_key] = _SAFE_PRODUCT_DESC
    logger.info(
        "product_desc forced safe path=%s desc_len=%d chars",
        os.path.basename(image_path) if image_path else "none",
        len(_SAFE_PRODUCT_DESC),
    )
    return _SAFE_PRODUCT_DESC

    if not image_path or not os.path.isfile(image_path):
        return ""

    cache_key = f"v{_PRODUCT_DESC_PROMPT_VERSION}:{os.path.normcase(os.path.abspath(image_path))}"
    if cache_key in _product_desc_cache:
        logger.info("product_desc cache hit path=%s", os.path.basename(image_path))
        return _product_desc_cache[cache_key]

    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as exc:
        logger.warning("product_desc read failed path=%s error=%s", image_path, exc)
        return ""

    try:
        from openai import OpenAI
        client = OpenAI(base_url=TUPIAN["base_url"], api_key=TUPIAN["api_key"])
        response = client.chat.completions.create(
            model=TUPIAN["model"],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": PRODUCT_ANALYSIS_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                ],
            }],
            max_tokens=800,
            temperature=0.3,
        )
        desc = (response.choices[0].message.content or "").strip()
        # ── Sanitize: if AI hallucinated wrong product details, use hardcoded safe description ──
        _DESC_BANNED = ["SIOI", "si01", "s1o1", "S I O I", "苦苣", "绿色罐", "绿罐", "玻璃瓶", "瓶身"]
        desc_lower = desc.lower()
        if any(b.lower() in desc_lower for b in _DESC_BANNED):
            logger.warning(
                "product_desc contains banned terms, replacing with safe default. "
                "original_len=%d banned_found=%s",
                len(desc),
                [b for b in _DESC_BANNED if b.lower() in desc_lower],
            )
            desc = _SAFE_PRODUCT_DESC

        _product_desc_cache[cache_key] = desc
        logger.info(
            "product_desc analyzed path=%s desc_len=%d chars",
            os.path.basename(image_path),
            len(desc),
        )
        return desc
    except Exception as exc:
        logger.warning("product_desc vision API failed path=%s error=%s", image_path, exc)
        return ""


# ── Safe product description — used when AI hallucinates wrong details ──
_SAFE_PRODUCT_DESC = (
    "S101 苦荞精酿啤酒，黄色铝制高罐易拉罐（yellow aluminum tall can），"
    "罐身主色黄色，黑色 S 标识在罐身上部，银色金属易拉盖和拉环（silver pull-tab lid），"
    "1L 容量标识，10°P 酒精度标识，"
    "苦荞精酿啤酒字样在罐身正面。罐体为细长圆柱形铝罐，表面哑光磨砂质感。"
)

# ── Engine-specific sanitize entries (common entries live in modules/common/sanitize.py) ──
_ENGINE_EXTRA_SANITIZE: dict[str, str] = {
    "深绿色": "黄色",
    "瓶上": "罐上",
    "瓶内": "罐内",
    "瓶": "罐",
    "健康": "清爽",
    # ── Cleanup for polluted historical/generated phrases ──
    "S101在桌面上": "手持S101",
    "S101和啤酒杯在桌面上": "手持S101和啤酒杯",
    "啤酒杯靠近镜头": "饮用",
    "两只啤酒杯碰在一起泡沫溢出": "碰杯",
    "两只啤酒杯泡沫溢出": "碰杯",
    "啤酒杯中金色啤酒泡沫丰富泡沫溢出": "啤酒倒入杯中，金色酒液和白色泡沫翻涌",
    # ── Brand exclusivity: any mention of other brands → S101 ──
    "其他啤酒": "S101",
    "其他品牌": "S101",
    "竞品": "S101",
    "别的酒": "S101",
    "别的品牌": "S101",
}


def _sanitize_workflow_text(text: str) -> str:
    if not text:
        return ""
    result = sanitize_text(text, extra_map=_ENGINE_EXTRA_SANITIZE)
    result = re.sub(r"S101(?:S101)+", "S101", result)
    result = re.sub(r"拉环盖(?:盖)+", "拉环盖", result)
    result = result.replace("无人手部入镜", "无人露脸，仅手部入镜")
    result = result.replace("黑色S101拉环盖", "银色金属拉环盖")
    result = result.replace("黑色拉环盖", "银色金属拉环盖")
    result = result.replace("black pull-tab", "silver metal pull-tab")
    result = result.replace("好饮用", "好喝")
    result = result.replace("饮用又解腻", "好喝又解腻")
    result = re.sub(r"靠近镜头[^，。；\n]*模拟[^，。；\n]*", "杯口靠近镜头，手部完成饮用动作暗示", result)
    return result


_OUTPUT_POLLUTION_PATTERNS = [
    "S101S101",
    "盖盖盖",
    "啤酒杯靠近镜头",
    "S101在桌面上",
    "无人手部入镜",
    "德恩堡",
    "青柠片",
    "250ml",
    "绿色易拉罐",
    "绿色罐",
    "黑色拉环盖",
    "黑色S101拉环盖",
]


def _find_output_pollution(*texts: str) -> list[str]:
    joined = "\n".join(t for t in texts if isinstance(t, str))
    return [p for p in _OUTPUT_POLLUTION_PATTERNS if p in joined]


def _sanitize_workflow_outputs_or_raise(stage: str, *texts: str) -> None:
    found = _find_output_pollution(*texts)
    if found:
        raise ValueError(f"{stage}仍包含污染词: {', '.join(found)}")


def _sanitize_keyframes(keyframes: list) -> list:
    cleaned = []
    for item in keyframes or []:
        if isinstance(item, dict):
            cleaned.append({k: _sanitize_workflow_text(v) if isinstance(v, str) else v for k, v in item.items()})
        else:
            cleaned.append(item)
    return cleaned


def _sanitize_workflow_payload(data: dict) -> dict:
    """Sanitize workflow API/output payloads, including old records already stored in DB."""
    if not isinstance(data, dict):
        return data
    cleaned = dict(data)
    for key in ("scene", "gender", "storyboard_text", "copy_text", "video_prompt", "error_message"):
        if isinstance(cleaned.get(key), str):
            cleaned[key] = _sanitize_workflow_text(cleaned[key])
    if isinstance(cleaned.get("image_prompts"), list):
        cleaned["image_prompts"] = [
            _sanitize_workflow_text(item) if isinstance(item, str) else item
            for item in cleaned["image_prompts"]
        ]
    if isinstance(cleaned.get("keyframes"), list):
        cleaned["keyframes"] = _sanitize_keyframes(cleaned["keyframes"])
    return cleaned


class WorkflowEngine:
    """Orchestrates the 8-step pipeline for one workflow."""

    STEP_LABELS = {
        1: "生成剧情分镜",
        2: "提取关键帧生图提示词",
        3: "gpt-image-2 生成图片",
        4: "AI 评分图片",
        5: "生成口播文案",
        6: "汇总最终视频提示词",
        7: "提交视频生成任务",
        8: "生成发布标签",
    }

    def __init__(self, state: WorkflowState):
        self.state = state
        self._stop_flag = threading.Event()

    def _get_history_texts(self, column: str) -> list[str]:
        """Get all non-empty historical texts for a given workflow column."""
        from .state import _get_conn
        conn = _get_conn()
        rows = conn.execute(
            f"SELECT DISTINCT {column} FROM workflows WHERE {column} IS NOT NULL AND {column} != '' AND id != ?",
            (self.state.id,),
        ).fetchall()
        conn.close()
        return [r[0] for r in rows if r[0]]

    def _check_similarity_retry(
        self, text: str, column: str, label: str, regenerate_fn, max_retries: int = 2
    ) -> tuple[str, bool]:
        """Check text against history. If >60% similar, retry up to max_retries.

        Returns (final_text, ok). ok=False means all retries exhausted.
        """
        for attempt in range(max_retries + 1):
            history = self._get_history_texts(column)
            if not history:
                return text, True
            max_sim = max(trigram_jaccard(text, h) for h in history)
            if max_sim <= 0.60:
                return text, True
            if attempt < max_retries:
                logger.warning(
                    "workflow=%s %s sim=%.0f%% >60%%, retry %d/%d",
                    self.state.id, label, max_sim * 100, attempt + 1, max_retries,
                )
                try:
                    text = regenerate_fn()
                except Exception:
                    continue
            else:
                logger.warning(
                    "workflow=%s %s sim=%.0f%% >60%%, all retries exhausted",
                    self.state.id, label, max_sim * 100,
                )
        return text, False

    def run(self, start_step: int = 1):
        """Run steps sequentially from start_step. Each step saves state on completion."""
        _engines[self.state.id] = self
        try:
            self._run_steps(start_step)
        except Exception as e:
            self.state.status = "failed"
            self.state.error_message = str(e)[:500]
            self.state.save()
        finally:
            _engines.pop(self.state.id, None)

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

    def _run_steps(self, start_step: int = 1):
        st = self.state
        if start_step == 1:
            st.status = "running"
        else:
            st.status = "running"
        st.storyboard_text = _sanitize_workflow_text(st.storyboard_text)
        st.keyframes = _sanitize_keyframes(st.keyframes)
        st.image_prompts = [_sanitize_workflow_text(p) for p in (st.image_prompts or [])]
        st.copy_text = _sanitize_workflow_text(st.copy_text)
        st.video_prompt = _sanitize_workflow_text(st.video_prompt)

        # ── Product analysis (gpt-4o vision) — only for fresh runs ──
        product_path = None
        product_desc = ""
        GENERATED_DIR = os.path.join(_ROOT, "static", "generated")
        if start_step == 1:
            product_path = self._resolve_product_path()
            product_desc = _analyze_product_image(product_path) if product_path else ""
            if product_desc:
                logger.info(
                    "workflow=%s product_desc ready len=%d path=%s",
                    st.id, len(product_desc),
                    os.path.basename(product_path) if product_path else "none",
                )
            else:
                logger.warning("workflow=%s product_desc unavailable", st.id)
        else:
            product_path = self._resolve_product_path()

        # ── Step 1: Storyboard (with 60% history similarity check) ──
        if start_step <= 1:
            if self._stop_flag.is_set(): return
            started_at = self._start_step(1)
            try:
                def _gen_storyboard():
                    return generate_storyboard(
                        story_type=st.story_type, gender=st.gender, scene=st.scene,
                        audience=st.audience, weather=st.weather,
                        style=st.style, action=st.action, extra=st.extra,
                    )

                sb = _gen_storyboard()
                sb_text, ok = self._check_similarity_retry(
                    _sanitize_workflow_text(sb["storyboard_text"]), "storyboard_text", "剧情分镜",
                    lambda: _sanitize_workflow_text(_gen_storyboard()["storyboard_text"]),
                )
                if not ok:
                    st.storyboard_text = _sanitize_workflow_text(sb_text)
                    st.error_message = f"剧情分镜与历史记录相似度超过60%，重试2次仍失败。"
                    st.status = "failed"
                    st.save()
                    self._finish_step(1, started_at, "similarity_retry_exhausted")
                    return

                st.storyboard_text = _sanitize_workflow_text(sb_text)
                st.keyframes = _sanitize_keyframes(sb["keyframes"])
                st.gender = _sanitize_workflow_text(sb["gender"])
                st.scene = _sanitize_workflow_text(sb["scene"])
                _sanitize_workflow_outputs_or_raise(
                    "剧情分镜",
                    st.storyboard_text,
                    *[
                        v
                        for item in st.keyframes
                        if isinstance(item, dict)
                        for v in item.values()
                        if isinstance(v, str)
                    ],
                )
                st.save()
                self._finish_step(1, started_at, f"gender={st.gender}, scene={st.scene}, keyframes={len(st.keyframes)}")
            except Exception as e:
                self._fail_step(1, started_at, "剧情生成失败", e)
                return

        # ── Step 2: Keyframe prompts ──
        if start_step <= 2:
            if self._stop_flag.is_set(): return
            started_at = self._start_step(2)
            try:
                prompts = extract_keyframe_prompts(
                    storyboard_text=st.storyboard_text,
                    keyframes=st.keyframes,
                    gender=st.gender,
                    aspect_ratio=st.aspect_ratio,
                    extra=st.extra,
                )
                prompts = [_sanitize_workflow_text(p) for p in prompts]
                product_desc = _sanitize_workflow_text(product_desc or _SAFE_PRODUCT_DESC)
                if product_desc and prompts:
                    prompts[0] = (
                        f"【PRODUCT TO SHOW IN EVERY PANEL: {product_desc}】\n"
                        f"【CRITICAL: The product in every panel of the 2x2 grid MUST be exactly "
                        f"as described above — same container type, shape, colors, label text, "
                        f"closure type, proportions. Do NOT draw a generic beer bottle or can. "
                        f"This is a specific branded product.】\n\n"
                        f"{prompts[0]}"
                    )
                    prompts[0] = _sanitize_workflow_text(prompts[0])
                _sanitize_workflow_outputs_or_raise("生图提示词", *(prompts or []))
                st.image_prompts = prompts
                st.save()
                self._finish_step(2, started_at, f"image_prompts={len(st.image_prompts)}")
            except Exception as e:
                self._fail_step(2, started_at, "关键帧提取失败", e)
                return

        # ── Step 3: Generate ONE 4-panel image via gpt-image-2 ──
        if start_step <= 3:
            if self._stop_flag.is_set(): return
            started_at = self._start_step(3)
            os.makedirs(GENERATED_DIR, exist_ok=True)
            image_urls = []
            prompt = _sanitize_workflow_text(st.image_prompts[0]) if st.image_prompts else ""
            if st.image_prompts:
                st.image_prompts[0] = prompt
                st.save()
            try:
                url = self._generate_image(prompt, GENERATED_DIR, 0, product_path, product_desc, keyframes=st.keyframes)
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

        # ── Step 4: Score images (with low-score gate) ──
        if start_step <= 4:
            if self._stop_flag.is_set(): return
            started_at = self._start_step(4)
            try:
                scores = score_all_images(st.image_urls, st.keyframes)
                st.scores = scores
                st.save()

                # Score gate: pause for human review if any score is 低 or 超低
                low_scores = [s for s in scores if isinstance(s, dict) and s.get("score") in ("低", "超低")]
                if low_scores:
                    st.status = "needs_review"
                    st.current_step = "待审核评分"
                    st.error_message = (
                        f"图片评分结果为「{low_scores[0].get('score', '低')}」，"
                        f"需要人工审核。可选择继续使用当前图片或重新生成。"
                    )
                    st.save()
                    record_workflow_event(
                        workflow_id=st.id, step_index=4, step_name=self.STEP_LABELS[4],
                        event_type="warning",
                        message=f"Score gate triggered: {len(low_scores)} panel(s) scored low",
                        output_summary=f"scores={len(st.scores)}, low_count={len(low_scores)}",
                    )
                    logger.warning(
                        "workflow=%s score_gate low_count=%d scores=%s",
                        st.id, len(low_scores),
                        [s.get("score") if isinstance(s, dict) else "?" for s in scores],
                    )
                    self._finish_step(4, started_at, f"needs_review — {len(low_scores)} low score(s)")
                    return
                self._finish_step(4, started_at, f"scores={len(st.scores)}")
            except Exception as e:
                self._fail_step(4, started_at, "评分失败", e)
                return

        # ── Step 5: Generate copy (with reference context + 60% similarity check) ──
        if start_step <= 5:
            if self._stop_flag.is_set(): return
            started_at = self._start_step(5)
            try:
                def _gen_copy():
                    return self._generate_copy()

                copy_text = _gen_copy()
                copy_text, ok = self._check_similarity_retry(
                    _sanitize_workflow_text(copy_text), "copy_text", "口播文案",
                    lambda: _sanitize_workflow_text(self._generate_copy()),
                )
                if not ok:
                    st.copy_text = _sanitize_workflow_text(copy_text)
                    _sanitize_workflow_outputs_or_raise("口播文案", st.copy_text)
                    st.error_message = f"口播文案与历史记录相似度超过60%，重试2次仍失败。"
                    st.save()
                    self._finish_step(5, started_at, "similarity_retry_exhausted — using last attempt")
                else:
                    st.copy_text = _sanitize_workflow_text(copy_text)
                    _sanitize_workflow_outputs_or_raise("口播文案", st.copy_text)
                    st.save()
                    self._finish_step(5, started_at, f"copy_chars={len(st.copy_text)}")
            except Exception as e:
                self._fail_step(5, started_at, "文案生成失败", e)
                return

        # ── Step 6: Assemble final video prompt (with similarity check) ──
        if start_step <= 6:
            if self._stop_flag.is_set(): return
            started_at = self._start_step(6)
            try:
                st.video_prompt = assemble_video_prompt(
                    storyboard_text=st.storyboard_text,
                    keyframes=st.keyframes,
                    scores=st.scores,
                    copy_text=st.copy_text,
                    gender=st.gender,
                    image_urls=st.image_urls,
                )
                st.video_prompt = _sanitize_workflow_text(st.video_prompt)
                _sanitize_workflow_outputs_or_raise("最终视频提示词", st.video_prompt)
                # Similarity check — deterministic assembly, so no retry
                history = self._get_history_texts("video_prompt")
                if history:
                    max_sim = max(trigram_jaccard(st.video_prompt, h) for h in history)
                    if max_sim > 0.60:
                        logger.warning(
                            "workflow=%s video_prompt sim=%.0f%% >60%% against history",
                            st.id, max_sim * 100,
                        )
                st.save()
                self._finish_step(6, started_at, f"video_prompt_chars={len(st.video_prompt)}")
            except Exception as e:
                self._fail_step(6, started_at, "最终提示词组装失败", e)
                return

        # ── Step 7: Submit video generation job (provider shell) ──
        if start_step <= 7:
            if self._stop_flag.is_set(): return
            started_at = self._start_step(7)
            try:
                video_result = submit_video_generation(
                    video_prompt=st.video_prompt,
                    image_urls=st.image_urls,
                )
                st.video_status = video_result.get("video_status", "")
                st.video_job_id = video_result.get("video_job_id", "")
                st.video_url = video_result.get("video_url", "")
                st.video_error = video_result.get("video_error", "")
                st.save()
                self._finish_step(7, started_at, f"video_status={st.video_status}")
            except Exception as e:
                self._fail_step(7, started_at, "视频生成任务提交失败", e)
                return

        # ═══ Step 8: 生成发布标签 ═══
        if start_step <= 8:
            if self._stop_flag.is_set(): return
            started_at = self._start_step(8)
            try:
                from enricher.llm import generate_hashtags
                from enricher.config import settings as hs
                from enricher.writer import build_hashtags_block

                # Build topic from copy_text + storyboard_text
                topic = (st.copy_text or "").strip()
                if not topic:
                    topic = (st.storyboard_text or "AI 工具箱短视频")[:200]

                platform = "youtube"  # default; could be configurable
                lang = "Chinese"      # default for the app's use case
                tags = generate_hashtags(topic, lang, platform=platform)

                if not tags:
                    tags = list(hs.always_include) or ["#shorts"]

                hashtag_block = build_hashtags_block(
                    tags_list=tags,
                    language=lang,
                    model=hs.model,
                    source="workflow",
                    platform=platform,
                )
                st.hashtags_json = json.dumps(hashtag_block, ensure_ascii=False)
                st.save()
                self._finish_step(8, started_at, f"tags={len(tags)} lang={lang}")
                st.status = "completed"
                st.current_step = "完成"
                st.save()
            except Exception as e:
                self._fail_step(8, started_at, "生成发布标签失败", e)
                return

    def _resolve_product_path(self) -> str:
        """Find the best product image to use. Returns absolute path or empty string."""
        PRODUCT_DIR = os.path.join(_ROOT, "static", "product")

        # 1. Explicit path from state
        product_image_path = self.state.product_image
        if product_image_path:
            candidate = os.path.join(
                _ROOT,
                product_image_path.lstrip("/").lstrip("\\"),
            )
            if os.path.isfile(candidate):
                return candidate

        # 2. Scan the product folder
        if os.path.isdir(PRODUCT_DIR):
            images = sorted(
                f for f in os.listdir(PRODUCT_DIR)
                if f.lower().endswith((".png", ".jpg", ".jpeg"))
            )
            if images:
                chosen = os.path.join(PRODUCT_DIR, images[0])
                logger.info(
                    "workflow=%s product_ref auto-picked from folder image=%s",
                    self.state.id,
                    images[0],
                )
                return chosen

        # 3. Fall back to the fixed S101 reference image in static/video
        ref = load_video_reference_context()
        default_product_path = ref.get("default_product_path", "")
        if default_product_path and os.path.isfile(default_product_path):
            logger.info(
                "workflow=%s product_ref fallback to static/video/2.png",
                self.state.id,
            )
            return default_product_path

        logger.warning("workflow=%s product_ref no image found in %s", self.state.id, PRODUCT_DIR)
        return ""

    @staticmethod
    def _build_brand_print_mask(product_image, size: tuple) -> Image:
        """Identify brand-critical print regions (logo, text, labels) on the product.

        The S101 can has a yellow aluminum body. Brand print elements are:
        - Black S logo, black text, black label rectangles
        - White/yellow text within label rectangles
        - Silver pull-tab rim

        Returns (brand_mask, product_resized) where mask=255 for brand pixels.
        Yellow can-body pixels are 0 (safe to let AI relight/shade/reflect).
        """
        from PIL import Image as PILImage
        resized = product_image.convert('RGBA').resize(size, PILImage.LANCZOS)
        w, h = resized.size
        mask = PILImage.new('L', (w, h), 0)

        for y in range(h):
            for x in range(w):
                r, g, b, a = resized.getpixel((x, y))
                if a < 20:
                    continue  # transparent — outside product
                # Yellow body: R>140, G>110, B<110 (yellow = red + green, low blue)
                # Silver rim: R~180, G~180, B~180 (neutral gray, may reflect)
                # Brand print: black (R<60,G<60,B<60) or white text on black
                is_yellow_body = (r > 130 and g > 100 and b < 120)
                is_silver = (abs(r - g) < 30 and abs(g - b) < 30 and r > 130 and r < 220)
                if not is_yellow_body and not is_silver:
                    mask.putpixel((x, y), 255)

        # Dilate to capture edges of print elements
        from PIL import ImageFilter
        mask = mask.filter(ImageFilter.MaxFilter(5))
        return mask, resized

    # ── Alignment thresholds (used by _verify_product_alignment) ──
    _ALIGN_CENTER_PX = 30       # max allowed center drift in pixels
    _ALIGN_SCALE_RATIO = 0.05   # max allowed scale deviation (1.0 ± 5%)
    _ALIGN_ROTATION_DEG = 12    # max allowed rotation drift in degrees

    def _verify_product_alignment(
        self, result_img: Image, canvas_img: Image, placements: list
    ) -> bool:
        """Canvas-based alignment check — compare result pixels vs original canvas
        in each product region.  If the API kept the product where we placed it,
        the pixels should match within a color tolerance.

        Returns True only if ALL panels pass.  False = retry entire generation.
        No offset compensation — if the product moved even slightly, reject.
        """
        import math

        canvas_px = canvas_img.load()
        result_px = result_img.load()
        step = 3  # sample every 3rd pixel for speed

        all_ok = True

        for pl in placements:
            x, y, w, h = pl["x"], pl["y"], pl["w"], pl["h"]
            panel_idx = pl["panel"]

            # Clamp to image bounds
            x1 = max(0, x)
            y1 = max(0, y)
            x2 = min(result_img.width, x + w)
            y2 = min(result_img.height, y + h)

            total = 0
            matched = 0

            for ry in range(y1, y2, step):
                for rx in range(x1, x2, step):
                    # Canvas pixel at this position
                    cr, cg, cb, ca = canvas_px[rx, ry]
                    if ca < 30:
                        continue  # transparent in canvas = outside product
                    total += 1
                    # Result pixel at same position
                    rr, rg, rb = result_px[rx, ry][:3]
                    # Per-channel tolerance: 50 (allows lighting/shading but rejects redrawn pixels)
                    if (abs(cr - rr) <= 50 and abs(cg - rg) <= 50 and abs(cb - rb) <= 50):
                        matched += 1

            if total < 20:
                logger.warning(
                    "workflow=%s alignment_fail panel=%d reason=too_few_product_px(%d)",
                    self.state.id, panel_idx, total,
                )
                all_ok = False
                continue

            match_ratio = matched / total
            # Require at least 60% of product pixels to match canvas
            threshold = 0.60

            if match_ratio < threshold:
                logger.warning(
                    "workflow=%s alignment_fail panel=%d "
                    "match_ratio=%.2f (threshold=%.2f) total=%d matched=%d",
                    self.state.id, panel_idx, match_ratio, threshold,
                    total, matched,
                )
                all_ok = False
            else:
                logger.info(
                    "workflow=%s alignment_ok panel=%d match_ratio=%.2f (%d/%d)",
                    self.state.id, panel_idx, match_ratio, matched, total,
                )

        return all_ok

    @staticmethod
    def _pca_angle(xs: list, ys: list) -> float:
        """Estimate dominant orientation angle (degrees) via 2x2 PCA.
        Pure-Python implementation — no numpy required.
        """
        import math
        n = len(xs)
        if n < 3:
            return 0.0
        # Covariance matrix [[cxx, cxy], [cxy, cyy]]
        cxx = sum(x * x for x in xs) / n
        cyy = sum(y * y for y in ys) / n
        cxy = sum(x * y for x, y in zip(xs, ys)) / n
        # Eigenvalues of 2x2 symmetric matrix
        trace = cxx + cyy
        det = cxx * cyy - cxy * cxy
        disc = max(0, (trace / 2) ** 2 - det)
        sqrt_disc = math.sqrt(disc)
        # Principal eigenvector direction
        lam1 = trace / 2 + sqrt_disc
        if abs(cxy) > 1e-9:
            angle = math.degrees(math.atan2(lam1 - cxx, cxy))
        else:
            angle = 0.0 if cxx >= cyy else 90.0
        return angle % 360

    def _restore_brand_elements(
        self, result_img: Image, product_path: str,
        placements: list,
    ) -> tuple:
        """Restore brand-print pixels at original canvas coordinates.

        Called ONLY after _verify_product_alignment passes (product is in place).
        No offset compensation — writes at exact canvas positions.

        Returns (result_img, pixel_pass, pixel_fail).
        """
        from PIL import Image as PILImage
        product_orig = PILImage.open(product_path).convert('RGBA')
        result_px = result_img.load()
        pixel_pass = 0
        pixel_fail = 0

        for pl in placements:
            x, y, w, h = pl["x"], pl["y"], pl["w"], pl["h"]

            brand_mask, product_resized = self._build_brand_print_mask(product_orig, (w, h))

            from PIL import ImageFilter as _IF
            feathered = brand_mask.filter(_IF.GaussianBlur(radius=3))

            for py in range(h):
                for px in range(w):
                    mval = feathered.getpixel((px, py))
                    if mval < 30:
                        continue

                    ax = x + px
                    ay = y + py
                    if ax < 0 or ay < 0 or ax >= result_img.width or ay >= result_img.height:
                        continue

                    orig = product_resized.getpixel((px, py))
                    curr = result_px[ax, ay]

                    alpha = mval / 255.0
                    blended = (
                        int(orig[0] * alpha + curr[0] * (1 - alpha)),
                        int(orig[1] * alpha + curr[1] * (1 - alpha)),
                        int(orig[2] * alpha + curr[2] * (1 - alpha)),
                        max(orig[3], curr[3]),
                    )
                    result_px[ax, ay] = blended
                    pixel_pass += 1

        return result_img, pixel_pass, pixel_fail

    @staticmethod
    def _detect_panel_pose(keyframe: dict, panel_index: int) -> dict:
        """Determine product x/y/scale/rotation for a panel based on its action.

        The API must NOT redraw or move the product. We pre-position the product
        in the exact pose the scene requires, so the API only fills the background.

        Returns {"rotation": degrees, "scale": float, "offset_x": -0.5..0.5, "offset_y": -0.5..0.5}
        """
        desc = keyframe.get("description", "") + keyframe.get("camera", "")
        desc_lower = desc.lower()

        # Default: upright, centered
        pose = {"rotation": 0, "scale": 1.0, "offset_x": 0.0, "offset_y": 0.0}

        # Detect action from Chinese keywords
        if any(kw in desc for kw in ["倒酒", "倒入", "倾倒", "倒出", "pouring", "pour"]):
            pose = {"rotation": -50, "scale": 0.82, "offset_x": 0.08, "offset_y": -0.16}
        elif any(kw in desc for kw in ["拉环", "开罐", "拉开", "弹开", "打开", "opening", "pull tab", "pull-tab"]):
            pose = {"rotation": -8, "scale": 0.92, "offset_x": 0.06, "offset_y": -0.02}
        elif any(kw in desc for kw in ["手持", "手握", "拿起", "举起", "举杯", "握着", "holding", "hold"]):
            pose = {"rotation": -14, "scale": 0.88, "offset_x": -0.05, "offset_y": -0.06}
        elif any(kw in desc for kw in ["放在", "建立场景", "桌上", "木桌", "establish"]):
            pose = {"rotation": 0, "scale": 0.9, "offset_x": 0.0, "offset_y": 0.06}
        elif any(kw in desc for kw in ["特写", "近景", "close-up", "closeup", "macro", "微距"]):
            pose = {"rotation": 0, "scale": 0.9, "offset_x": 0.0, "offset_y": 0.02}
        elif any(kw in desc for kw in ["展示", "居中", "正面", "display", "showcase"]):
            pose = {"rotation": 0, "scale": 1.05, "offset_x": 0.0, "offset_y": 0.0}

        return pose

    def _plan_product_poses(
        self, keyframes: list
    ) -> tuple[list[dict], list[str], str]:
        """Product Placement Planner.

        The product asset is a fixed upright aluminum can.  Certain keyframe
        actions (pouring, holding, opening) are physically impossible for the
        asset to depict.  This planner:

          1. Detects such conflicts per panel.
          2. Downgrades impossible poses to safe static display poses.
          3. Returns enriched scene-prompt hints so the AI paints the *action*
             via background elements (splashing beer, foam, glass, hands
             reaching toward the can) instead of redrawing the can itself.

        Returns
        -------
        (poses, conflicts, extra_scene_hint)
            poses   : list of pose dicts (one per panel)
            conflicts : list of conflict descriptions
            extra_scene_hint : additional English text to append to scene_prompt
        """
        poses: list[dict] = []
        conflicts: list[str] = []
        action_hints: list[str] = []

        # Actions that should be represented as casual video keyframes.
        # Keep packaging stable, but do not downgrade normal hand/open/pour actions
        # into static product-ad display poses.
        _IMPOSSIBLE = {
            "碰杯|干杯|cheers|clinking": (
                "Clinking requires two cans in contact at an angle",
                "two beer glasses clinking with foam overflow, cans standing nearby",
            ),
        }

        for i, kf in enumerate(keyframes):
            desc = (kf.get("description", "") + kf.get("camera", "")).lower()
            pose = self._detect_panel_pose(kf, i)

            matched_conflict = None
            for keywords, (reason, hint) in _IMPOSSIBLE.items():
                if any(kw in desc for kw in keywords.split("|")):
                    matched_conflict = (reason, hint)
                    break

            if matched_conflict:
                reason, hint = matched_conflict
                conflicts.append(f"Panel {i}: {reason}")
                # Downgrade to safe upright display pose
                pose = {
                    "rotation": 0, "scale": 1.0,
                    "offset_x": 0.0, "offset_y": 0.0,
                }
                action_hints.append(hint)

            poses.append(pose)

        # Deduplicate scene hints
        unique_hints = list(dict.fromkeys(action_hints))
        extra_hint = (
            " IMPORTANT: Keep can label stable. "
            "Depict: " + "; ".join(unique_hints) + "."
            if unique_hints else ""
        )

        if conflicts:
            logger.info(
                "workflow=%s placement_planner conflicts=%d hints=%d: %s",
                self.state.id, len(conflicts), len(unique_hints),
                "; ".join(conflicts),
            )

        return poses, conflicts, extra_hint

    def _build_product_canvas(self, product_path: str, keyframes: list = None, size: tuple[int, int] = (1024, 1536),
                              planned_poses: list = None) -> tuple:
        """Place the product PNG into 4 quadrants with per-panel poses.

        Each panel's product is positioned, scaled, and rotated according to
        the action described in its keyframe. The API is then asked to fill
        ONLY the background/scene around the pre-positioned products.

        Returns (canvas_png_bytes, mask_png_bytes, placements_list).
        placements_list has one dict per panel with pose + bbox info.
        """

        product = Image.open(product_path).convert("RGBA")
        # Resize product to a max of 400px wide before compositing
        pw, ph = product.size
        if pw > 400:
            ratio = 400 / pw
            product = product.resize((400, int(ph * ratio)), Image.LANCZOS)
            pw, ph = product.size

        canvas_w, canvas_h = size
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        # Mask: transparent = generate (background), white opaque = preserve (products)
        mask = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

        panel_w = canvas_w // 2
        panel_h = canvas_h // 2
        base_w = int(panel_w * 0.36)  # enough product pixels for readable label text

        # 4 quadrant centers
        quadrant_centers = [
            (panel_w // 2, panel_h // 2),                                 # top-left
            (panel_w + panel_w // 2, panel_h // 2),                       # top-right
            (panel_w // 2, panel_h + panel_h // 2),                       # bottom-left
            (panel_w + panel_w // 2, panel_h + panel_h // 2),             # bottom-right
        ]

        placements = []

        for i, (cx, cy) in enumerate(quadrant_centers):
            # Get pose for this panel — prefer planned_poses from placement planner
            if planned_poses and i < len(planned_poses):
                pose = planned_poses[i]
            elif keyframes and i < len(keyframes):
                pose = self._detect_panel_pose(keyframes[i], i)
            else:
                pose = {"rotation": 0, "scale": 1.0, "offset_x": 0.0, "offset_y": 0.0}

            product_w = int(base_w * pose["scale"])
            ratio = product_w / pw
            product_h = int(ph * ratio)
            product_panel = product.resize((product_w, product_h), Image.LANCZOS)

            # Apply offset (fraction of the vertical phone-shot panel size)
            offset_x_px = int(pose["offset_x"] * panel_w)
            offset_y_px = int(pose["offset_y"] * panel_h)

            px = cx - product_w // 2 + offset_x_px
            py = cy - product_h // 2 + offset_y_px

            # Apply rotation
            if pose["rotation"] != 0:
                product_panel = product_panel.rotate(
                    pose["rotation"], Image.BICUBIC, expand=True, fillcolor=(0, 0, 0, 0),
                )
                # Re-center after rotation expansion
                rw, rh = product_panel.size
                px = cx - rw // 2 + offset_x_px
                py = cy - rh // 2 + offset_y_px

            # Paste into canvas + mask
            canvas.paste(product_panel, (px, py), product_panel)
            # White opaque in mask = preserve products
            mask_protect = Image.new("RGBA", (product_panel.width, product_panel.height), (255, 255, 255, 255))
            mask.paste(mask_protect, (px, py), product_panel)

            placements.append({
                "panel": i,
                "pose": pose,
                "x": px, "y": py,
                "w": product_panel.width, "h": product_panel.height,
                "center": (cx, cy),
            })

        # Expand preserve zone by 15px around products
        from PIL import ImageFilter
        mask = mask.filter(ImageFilter.MaxFilter(15))

        # Save
        import io
        canvas_buf = io.BytesIO()
        canvas.save(canvas_buf, format="PNG", optimize=True)
        mask_buf = io.BytesIO()
        mask.save(mask_buf, format="PNG", optimize=True)
        return canvas_buf.getvalue(), mask_buf.getvalue(), placements

    def _generate_image(self, prompt: str, output_dir: str, index: int,
                        product_image_path: str = "", product_desc: str = "",
                        keyframes: list = None) -> str:
        """Canvas+mask approach: API generates scene around pre-placed products.

        Pipeline:
          1. Product Placement Planner — calculate positions/sizes/rotations
          2. Build canvas (products on transparent bg) + mask
          3. POST /v1/images/edits — API fills background, naturally integrates products
          4. Save directly — no verification, no restoration, no stickers
        """

        clean_prompt = _sanitize_workflow_text(re.sub(r'^Image\s*\d+[：:]\s*', '', prompt).strip())
        api_base = GPT_IMAGE["base_url"]
        api_key = GPT_IMAGE["default_api_key"]

        product_path = product_image_path or self._resolve_product_path()
        if not product_path or not os.path.isfile(product_path):
            raise RuntimeError("产品图缺失，无法生成。请确保 static/product/ 下有产品图片。")

        # ── Step 1: Product Placement Planner ──
        planned_poses = None
        planner_hint = ""
        if keyframes:
            planned_poses, conflicts, planner_hint = self._plan_product_poses(keyframes)
            if conflicts:
                logger.info(
                    "workflow=%s planner_downgraded %d panels: %s",
                    self.state.id, len(conflicts), "; ".join(conflicts),
                )

        # ── Step 2: Build canvas + mask ──
        canvas_bytes, mask_bytes, placements = self._build_product_canvas(
            product_path, keyframes=keyframes, planned_poses=planned_poses,
        )

        # ── Step 3: Scene prompt ──
        scene_prompt = (
            f"Create one 1024x1536 vertical 2x2 grid that looks like four ordinary phone-shot video keyframes, "
            f"not a finished beer advertisement poster. Use the existing S101 product assets "
            f"as the product identity reference and keep the yellow can, black S logo, "
            f"silver metal lid and pull tab stable.\n\n"
            f"CRITICAL ASSET RULES — VIOLATION WILL CAUSE REJECTION:\n"
            f"- Product must remain a yellow aluminum tall can with black S logo, silver metal lid and silver pull tab.\n"
            f"- Do NOT create a black pull tab. Do NOT change the can to a bottle, short can, green can, or another package.\n"
            f"- When the front label is visible, render the core label clearly from the reference: large black S logo, the same lower black brand wordmark shape as the product reference, Chinese text '苦荞精酿啤酒', and bottom marks '10°P' and '1L'.\n"
            f"- Do NOT generate garbled pseudo-text. Do NOT spell the wordmark as si01, s1o1, or random fake letters.\n"
            f"- Hands may naturally hold the can, take it from a bag, open the silver pull tab, or pour into a glass, "
            f"but hands must not cover the black S logo or make the can look like a different product.\n\n"
            f"BRAND CONSISTENCY — KEEP ONLY S101 PRODUCT IDENTITY:\n"
            f"- S101 is the ONLY brand allowed in the entire image.\n"
            f"- Do NOT draw any other beer, beverage, brand, logo, label, or product.\n"
            f"- If there is a shelf, fridge, bar counter, or display — it must show ONLY S101 cans "
            f"or be empty. NEVER populate it with other brands.\n"
            f"- Backgrounds: ordinary kitchen, rental-room wooden table, backpack, plastic bag, snack bag, "
            f"messy tabletop, normal glass, indoor light — all fine. But NO other branded products.\n"
            f"- Prefer wooden table or dining table surfaces with visible wood grain. Avoid clean stone/quartz countertops, sink-side counters, and sterile kitchen counter close-ups.\n"
            f"- Any readable text on any surface must be S101 or generic (no brand names).\n\n"
            f"STYLE RULES:\n"
            f"- The full image is vertical 1024x1536. Each of the four panels must be a vertical phone-photo crop, about 512x768, 2:3 ratio\n"
            f"- Do NOT make each panel a square crop. Do NOT center-crop the four shots into 1:1 cells\n"
            f"- Must look like a real smartphone photo taken with a mid-to-low-end phone camera\n"
            f"- Background, table, bag, and room may have slight natural motion blur and soft focus; the product's main logo and core label text should stay readable when front-facing\n"
            f"- Realistic amateur indoor lighting: kitchen light, desk lamp, window light, NOT studio lighting\n"
            f"- Subtle noise/grain like a real phone sensor in indoor light\n"
            f"- Imperfect framing and casual composition, like a user's phone album\n"
            f"- Keep wider phone framing in panels 1 and 3: show wood table, room background, and surrounding clutter. The can should not fill the whole panel\n"
            f"- In panels 1, 2, and 3, keep enough front-facing can area for the large S logo, lower black brand wordmark, '苦荞精酿啤酒', '10°P', and '1L' to be legible\n"
            f"- Panel 2 must clearly show an open backpack/bag mouth and inner lining while the hand takes the can out\n"
            f"- Each panel should feel like an executable video keyframe: establish table, take from bag, open tab, ordinary pour\n"
            f"- Do NOT make every panel a dramatic product beauty shot\n"
            f"- No night-market barbecue ad feeling, no outdoor camping, no crowd, no mood lights, no cinematic look\n"
            f"- No refined commercial photography, no over-blurred background, no exaggerated foam, no repeated pouring in every panel\n"
            f"- NO AI artifacts: no plastic skin, no over-smooth textures, no unnatural colors\n"
            f"{planner_hint}\n"
            f"Scene description:\n{clean_prompt}"
        )

        # ── Step 4: Call /v1/images/edits ──
        endpoint_url = f"{api_base}/v1/images/edits"
        import io
        _MAX_RETRIES = 3
        last_error = None

        for attempt in range(_MAX_RETRIES):
            logger.info(
                "workflow=%s calling %s attempt=%d/%d (canvas=%d, mask=%d)",
                self.state.id, endpoint_url, attempt + 1,
                _MAX_RETRIES, len(canvas_bytes), len(mask_bytes),
            )

            api_image_bytes = None
            for api_try in range(3):
                try:
                    resp = requests.post(
                        endpoint_url,
                        files={
                            "image": ("canvas.png", io.BytesIO(canvas_bytes), "image/png"),
                            "mask": ("mask.png", io.BytesIO(mask_bytes), "image/png"),
                            "prompt": (None, scene_prompt),
                            "model": (None, "gpt-image-2"),
                            "size": (None, "1024x1536"),
                            "quality": (None, "low"),
                            "n": (None, "1"),
                        },
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=120,
                        verify=False,
                        proxies={"http": None, "https": None},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        api_image_bytes = self._extract_image_bytes(data)
                        logger.info(
                            "workflow=%s edits OK, image=%d bytes",
                            self.state.id,
                            len(api_image_bytes) if api_image_bytes else 0,
                        )
                        break
                    last_error = RuntimeError(
                        f"Image edits API returned {resp.status_code}: {resp.text[:300]}"
                    )
                except requests.exceptions.SSLError as ssl_err:
                    last_error = ssl_err
                    logger.warning(
                        "workflow=%s SSL error api_try=%d: %s",
                        self.state.id, api_try + 1, ssl_err,
                    )
                    time.sleep(2 * (api_try + 1))
                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        "workflow=%s API error api_try=%d: %s",
                        self.state.id, api_try + 1, exc,
                    )
                    time.sleep(2)

            if api_image_bytes is None:
                logger.warning(
                    "workflow=%s attempt=%d API failed, retrying",
                    self.state.id, attempt + 1,
                )
                continue

            # ── Step 5: Save directly — no verification, no restoration ──
            import io as _io
            result_img = Image.open(_io.BytesIO(api_image_bytes)).convert('RGBA')
            filename = f"wf_{self.state.id}_img{index+1}.png"
            filepath = os.path.join(output_dir, filename)
            result_img.convert('RGB').quantize(colors=256).save(filepath, format='PNG', optimize=True)
            logger.info(
                "workflow=%s saved attempt=%d path=%s size=%d",
                self.state.id, attempt + 1, filepath, os.path.getsize(filepath),
            )
            return f"/generated/{filename}"

        raise RuntimeError(
            f"经过 {_MAX_RETRIES} 次重试，图片生成失败。最后错误: {last_error}"
        )

    def _extract_image_bytes(self, data: dict) -> bytes | None:
        """Extract raw image bytes from API response. Handles URL, b64_json, and data URL."""
        import io as _io
        img_url = None
        items = data.get("data") or data.get("images") or []
        if isinstance(items, dict):
            items = [items]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("url"):
                img_url = item["url"]
                break
            if item.get("b64_json"):
                return base64.b64decode(item["b64_json"])
        if not img_url:
            for key in ("image", "url", "b64_json"):
                if data.get(key):
                    if key == "b64_json":
                        return base64.b64decode(data[key])
                    img_url = str(data[key])
                    break
        if not img_url:
            return None
        if img_url.startswith("data:image/"):
            match = re.match(r"^data:image/[\w.+-]+;base64,(.+)$", img_url, re.S)
            if match:
                return base64.b64decode(match.group(1))
            return None
        # Download URL
        resp = requests.get(img_url, timeout=60, verify=False, proxies={"http": None, "https": None})
        if resp.status_code != 200:
            return None
        return resp.content

    def _generate_copy(self) -> str:
        """Generate 50-100 word marketing copy using DeepSeek directly.

        Reads product info from static/video/公司产品数据.txt (preferred) or
        modules/wenan/介绍.txt (fallback).

        Enforces compliance: no medical claims, no hangover promises, no health claims.
        """
        import random
        from openai import OpenAI
        _ROOT2 = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sys.path.insert(0, _ROOT2)
        from model_config import WENAN

        product_info = (
            "S101苦荞精酿啤酒，黄色铝制1L高罐，10°P，苦荞风味，"
            "入口绵柔，回味荞香，28天左右发酵，纯粮酿造，"
            "适合家里厨房、出租屋木桌、零食旁、普通玻璃杯等日常小酌场景。"
            "不得使用医疗功效、饮后承诺、三高、养生、保健等表述。"
        )

        system_prompt = f"""你是抖音带货口播写手。你不是在写文章，你是在跟一个正在刷抖音的人说话。
对方手指一划就划走了，你必须用最直白的人话在3秒内抓住他。

产品信息：
{product_info}

【合规红线 — 绝对不允许出现以下任何内容】
- 医疗功效：降血压、降血糖、降血脂、软化血管、治疗、保健、养生、药效、疗愈
- 饮后承诺：不上头、不头疼、不口干、不难受、不胀肚、第二天不、没有宿醉、喝了不
- 疾病相关：三高、糖尿病、高血压、高血脂、尿酸、嘌呤、痛风、心血管
- 健康暗示：健康啤酒、对自己好点、养生啤酒、顾健康
- 以上词汇的变体、谐音、近义词也不允许

【写法规范】
1. 50-100字。句句短，句句有信息量。每句不超过15字。
2. 语气：就像你跟朋友坐在烧烤摊聊天，用"你"直接对话。口语到能念出声不尴尬。
3. 结构：痛点或场景引入 → 产品差异化卖点（拉环盖/28天/苦荞/纯粮/1L大罐）→ CTA下单引导。
4. 卖点要落到具体数字和对比，不要空说"好喝"：要说"发酵28天，普通啤酒7天就兑水了""拉环一拉就开，不用开瓶器""1L大罐，够喝不心疼"。
5. 可以在开头用：反问句（"有没有……？"）、直呼（"兄弟们/姐妹们"）、场景画面（"下班回家往沙发一躺……"）。

【严禁写法 — 出现以下任何一种都算不合格】
- 禁止文艺腔：不准出现"润到心坎""夕阳""黄昏""远方""诗意""慰藉""灵魂""治愈""小确幸"
- 禁止假大空：不准出现"别整那些虚的""喝点实在的""生活不过如此""这才是人生"
- 禁止抽象形容词堆砌："醇厚饱满层次丰富" → 换成"喝完嘴里有荞麦香"
- 禁止带货八股腔："家人们谁懂啊""绝绝子""yyds""宝藏""种草""安利"
- 禁止散文句式："就着……""伴着……""让……在……中……"

【参考范例 — 照着这个味儿写】
范例1："有没有喝啤酒第二天头疼的？那是工业勾兑酒！试试S101苦荞精酿，纯粮发酵28天，普通啤酒7天就兑水上市了。入口绵柔，回口荞香。主页有链接。"
范例2："下班回家，往厨房木桌前一坐，拉开一罐S101，荞香扑面。10°P，1L大罐，纯粮28天发酵，比工业啤酒多花三倍时间。拉环一拽就开，倒一杯泡沫绵密，喝一口就知道区别。主页有链接，试试不一样的。"

【必须】结尾必须包含下单引导（CTA），如"主页有链接""点头像进主页""左下角链接""橱窗有货"。没有CTA的文案直接作废。"""

        user_msg = f"场景：{self.state.scene}，剧情类型：{self.state.story_type}，性别视角：{self.state.gender}。请生成一段50-100字的口播文案："

        client = OpenAI(base_url=WENAN["base_url"], api_key=WENAN["api_key"])
        response = client.chat.completions.create(
            model=WENAN["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=300,
            temperature=0.85,
            seed=random.randint(1, 99999),
        )

        text = (response.choices[0].message.content or "").strip()

        # ── Compliance check: if banned words appear, use safe fallback ──
        _COPY_BANNED = [
            "降血压", "降血糖", "降血脂", "软化血管", "不上头", "不头疼", "不口干",
            "不难受", "不胀肚", "三高", "养生", "保健", "治疗", "药效", "疗愈",
            "糖尿病", "高血压", "高血脂", "尿酸", "嘌呤", "痛风", "心血管",
            "健康啤酒", "顾健康", "健康劲儿", "健康清爽", "第二天不", "没有宿醉", "喝了不",
        ]
        has_banned = any(b in text for b in _COPY_BANNED)

        if len(text) < 20 or has_banned:
            # Safe fallback — no medical claims, no hangover promises
            return (
                "试试这款S101苦荞精酿啤酒，跟平时喝的工业啤酒完全不一样。"
                "纯粮发酵28天，比普通啤酒多两三倍的发酵周期，口感绵柔，回味有荞麦香。"
                "拉环盖设计一拉就开，不用开瓶器。想尝鲜的点我头像进主页看看。"
            )

        # ── CTA enforcement: if no purchase guidance, append default CTA ──
        _CTA_KEYWORDS = [
            "主页", "链接", "下单", "购买", "头像", "橱窗", "小黄车",
            "点进去", "进来看看", "去看看", "试试看", "试试吧", "尝尝",
            "下方", "左下角", "评论区", "私信",
        ]
        has_cta = any(kw in text for kw in _CTA_KEYWORDS)
        if not has_cta:
            text = text.rstrip("。！!~～… ") + "。想尝鲜的点我头像进主页看看！"
            logger.info("copy CTA appended: no purchase guidance detected in original")

        return text[:300]


def start_workflow(state: WorkflowState) -> str:
    """Start a workflow in background thread. Returns workflow ID."""
    init_workflow_db()
    state.save()
    engine = WorkflowEngine(state)
    t = threading.Thread(target=engine.run, daemon=True)
    t.start()
    return state.id


def continue_workflow_from_review(workflow_id: str) -> str:
    """Resume a needs_review workflow from Step 5 (copy → video prompt → submit).

    Only valid when the workflow status is 'needs_review'.
    """
    st = WorkflowState(workflow_id)
    if st.status != "needs_review":
        raise ValueError(f"Workflow {workflow_id} is not in needs_review status (current: {st.status})")
    st.error_message = ""
    st.save()
    engine = WorkflowEngine(st)
    t = threading.Thread(target=engine.run, args=(5,), daemon=True)
    t.start()
    return workflow_id


def regenerate_workflow_image(workflow_id: str) -> str:
    """Re-run Step 3-4 for a needs_review workflow (regenerate image + re-score).

    If the new scores pass the gate, continues through Steps 5-7.
    If scores still fail, stops again with needs_review.
    Only valid when the workflow status is 'needs_review'.
    """
    st = WorkflowState(workflow_id)
    if st.status != "needs_review":
        raise ValueError(f"Workflow {workflow_id} is not in needs_review status (current: {st.status})")
    st.error_message = ""
    # Clear old scores and image so the gate is re-evaluated
    st.scores = []
    st.image_urls = []
    st.save()
    engine = WorkflowEngine(st)
    t = threading.Thread(target=engine.run, args=(3,), daemon=True)
    t.start()
    return workflow_id


def get_workflow_status(workflow_id: str) -> dict | None:
    """Get current status of a workflow."""
    try:
        st = WorkflowState(workflow_id)
        return st.to_status_dict()
    except ValueError:
        return None


def get_workflow_result(workflow_id: str) -> dict | None:
    """Get full result of a completed / failed / needs_review workflow."""
    try:
        st = WorkflowState(workflow_id)
        if st.status not in ("completed", "failed", "cancelled", "needs_review"):
            return None
        return _sanitize_workflow_payload(st.to_dict())
    except ValueError:
        return None


def stop_workflow(workflow_id: str) -> bool:
    """Request stop of a running workflow."""
    engine = _engines.get(workflow_id)
    if engine:
        engine.stop()
        return True
    # Not running, but try to mark as cancelled
    try:
        st = WorkflowState(workflow_id)
        if st.status in ("pending", "running"):
            st.status = "cancelled"
            st.save()
        return True
    except ValueError:
        return False
