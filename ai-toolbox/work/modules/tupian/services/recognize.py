"""
图像识别服务 — 使用 OpenAI 兼容的视觉 API
"""

import base64
import time
from pathlib import Path
from openai import OpenAI

import sys, os
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)
from model_config import TUPIAN, ALLOWED_EXTENSIONS
IMAGE_RECOGNIZE_TOKEN = TUPIAN["api_key"]
API_BASE_URL = TUPIAN["base_url"]
VISION_MODEL = TUPIAN["model"]
sys.path.insert(0, os.path.join(_ROOT, "modules", "tupian"))
from logger import get_logger

log = get_logger("recognize")


class RecognizeError(Exception):
    """识别 API 错误"""

    def __init__(self, message: str, status_code: int = 0):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _get_client() -> OpenAI:
    return OpenAI(
        base_url=API_BASE_URL,
        api_key=IMAGE_RECOGNIZE_TOKEN,
    )


# 分析图片的提示词
ANALYSIS_PROMPT = """请分析这张图片，用自然流畅的中文输出以下内容。禁止使用任何 Markdown 符号（不要用 **、#、- 等）。

提取图片主体内容：用简洁但完整的语言描述画面中最重要的主体，包括产品、人物、道具、服装、动作等。

画面主体：分点说明图片里出现了哪些核心元素，例如产品外观、包装文字、人物状态、随身物品等。

背景场景：分析图片拍摄地点、时间氛围、光线、环境信息、店铺、街景、室内外场景等。

产品参数：如果图片中有明显文字标注，请提取容量、高度、宽度、规格、品牌名、型号等信息。如果看不清，请说明图片中未清晰显示。

整体意图：判断这张图片可能用于什么场景，比如产品种草、广告宣传、生活方式展示、小红书抖音种草图、街拍宣传图等。

风格总结：总结图片的视觉风格，例如手机随拍感、生活纪实感、街头感、夜市氛围、暖色调、真实消费场景等。

要求：不要输出 JSON，不要输出代码，不要只做物体检测，像广告创意策划一样分析画面，语言自然适合给设计师、摄影师或 AI 生图工具参考。"""


async def _call_vision_api(image_data: str) -> str:
    """调用视觉 API 获取文字描述"""
    t0 = time.time()

    log.debug("Vision API call start | model=%s image_len=%d", VISION_MODEL, len(image_data))

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": ANALYSIS_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_data},
                        },
                    ],
                }
            ],
            max_tokens=2000,
        )

        elapsed = time.time() - t0
        text = response.choices[0].message.content or ""
        log.debug("Vision API done | elapsed=%.2fs text_len=%d", elapsed, len(text))
        return text

    except Exception as e:
        elapsed = time.time() - t0
        log.error("Vision API error | elapsed=%.2fs error=%s", elapsed, str(e))
        raise RecognizeError(f"Vision API error: {e}")


def _image_to_base64_data_url(file_path: Path) -> str:
    suffix = file_path.suffix.lower().lstrip(".")
    mime = f"image/{suffix}"
    if mime == "image/jpg":
        mime = "image/jpeg"
    with open(file_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{data}"


async def recognize_by_url(image_url: str) -> dict:
    """通过图片 URL 识别 — 把 URL 传给视觉模型"""
    t0 = time.time()
    log.debug("Vision URL start | url=%s", image_url[:200])

    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": ANALYSIS_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url},
                        },
                    ],
                }
            ],
            max_tokens=2000,
        )
        elapsed = time.time() - t0
        text = response.choices[0].message.content or ""
        log.debug("Vision URL done | elapsed=%.2fs text_len=%d", elapsed, len(text))
        return {"analysis": text}
    except Exception as e:
        elapsed = time.time() - t0
        log.error("Vision URL error | elapsed=%.2fs error=%s", elapsed, str(e))
        raise RecognizeError(f"Vision API error: {e}")


async def recognize_by_file(file_path: str) -> dict:
    path = Path(file_path)
    image_data = _image_to_base64_data_url(path)
    text = await _call_vision_api(image_data)
    return {"analysis": text}


async def recognize_by_upload_data(file_data: bytes, filename: str) -> dict:
    suffix = Path(filename).suffix.lower().lstrip(".")
    mime = f"image/{suffix}"
    if mime == "image/jpg":
        mime = "image/jpeg"
    encoded = base64.b64encode(file_data).decode("utf-8")
    image_data = f"data:{mime};base64,{encoded}"

    if len(file_data) > 10 * 1024 * 1024:
        raise RecognizeError("File too large (max 10MB)")

    text = await _call_vision_api(image_data)
    return {"analysis": text}
