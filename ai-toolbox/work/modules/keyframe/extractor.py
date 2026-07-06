"""
Keyframe extractor — converts storyboard keyframes into a single 4-panel gpt-image-2 prompt.
"""
import sys, os, random
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _ROOT)
from model_config import WENAN
from openai import OpenAI


KEYFRAME_SYSTEM = """你是一个为 gpt-image-2 写图片生成提示词的专业AI。给你一段剧情分镜描述，你需要把它转化为一张四宫格图片的中文生图提示词。

【产品身份 — 绝对不允许偏离】
S101 苦荞精酿啤酒 = 黄色铝制高罐易拉罐（yellow aluminum tall can），罐身主色黄色，黑色 S 标识，银色金属易拉盖和拉环，1L / 10°P。
禁止出现：绿色罐、绿罐、深绿色、玻璃瓶、瓶身、瓶口、瓶盖、酒瓶、啤酒瓶、一瓶、浅棕色、棕色瓶、SIOI、苦苣、si01、s1o1。
如果剧情原文中出现了上述禁用词，忽略它们，输出时只用「黄色 S101 铝制高罐易拉罐、罐身、罐口、拉环盖、一罐」。

【无人露脸 — 硬约束】
禁止出现：下巴、半张脸、侧脸、表情、笑容、面孔、露脸、嘴唇、喝一口。
只能用手部/袖口/美甲暗示人物存在。POV 视角。
如果剧情原文写到嘴唇或饮用动作，改写为「杯口靠近镜头，手部动作暗示饮用」。

规则：
1. 输出 1 段描述，用于生成一张 1024x1536 竖版四宫格图片（2x2 grid layout）
2. 左上格=分镜1，右上格=分镜2，左下格=分镜3，右下格=分镜4
3. 四个格子必须像同一部手机拍下的连续动作关键帧，不是广告海报；每格都是约 512x768 的竖版手机照片比例（2:3），不要正方形镜头
4. 描述中必须重复「黄色铝制高罐 S101 苦荞精酿啤酒，黑色 S 标识，银色金属易拉盖和拉环」
5. 必须按固定四格动作写：左上产品放普通室内木桌上并带房间背景；右上手从打开的背包里拿出产品且背包口/内衬可见；左下手拉开银色金属拉环但不要极端微距；右下普通倒一杯到透明玻璃杯，泡沫自然
6. 场景必须是普通室内日常：厨房木桌、出租屋木桌、零食袋、塑料袋、背包、杂乱桌面、普通玻璃杯、普通室内光
7. 风格关键词：真实手机随手拍、环境低中像素、背景轻微模糊、构图不完美、普通室内光、不精致、不像广告、像用户相册里的4张生活照片、木桌纹理、房间背景
8. 产品文字要求：背景可以轻微模糊，但罐身主视觉必须清楚；可见正面必须清楚画出黑色大 S、素材图同款下方黑色品牌字标、中文「苦荞精酿啤酒」、底部「10°P」「1L」
9. 负面约束必须写入：不要夜市烧烤广告感，不要精致商业摄影，不要电影感，不要户外露营，不要人群，不要氛围灯，不要过度虚化，不要夸张泡沫，不要每格都倒酒，不要黑色拉环，不要乱码伪文字，不要把品牌字标写成 si01/s1o1/随机假字，不要干净厨房台面特写，不要水槽边台面，不要石英石台面
10. 用中文输出，控制在 260 字以内"""


def extract_keyframe_prompts(
    storyboard_text: str,
    keyframes: list,
    gender: str,
    aspect_ratio: str = "1:1",
    extra: str = "",
) -> list:
    """
    Returns: list of 1 string — the single 4-panel image prompt.
    """
    kf_lines = []
    for kf in keyframes:
        parts = [kf.get("description", "")]
        if kf.get("camera"):
            parts.append(f"运镜: {kf['camera']}")
        if kf.get("composition"):
            parts.append(f"构图: {kf['composition']}")
        kf_lines.append(f"分镜{kf['index']}: " + " | ".join(parts))

    gender_hint = ""
    if "女" in gender:
        gender_hint = "女性手部入镜（美甲/纤细手型），无人脸。Show feminine hands with neat nails or subtle nail polish, NO face."
    elif "男" in gender:
        gender_hint = "男性手部入镜（骨感手型/手表/纯色袖口），无人脸。Show masculine hands, possibly with a watch or plain nails, NO face."

    aspect_hint = ""
    if aspect_ratio and aspect_ratio != "1:1":
        aspect_hint = f"\nAspect ratio: {aspect_ratio}."
    extra_hint = ""
    if extra:
        extra_hint = f"\nAdditional requirements: {extra}"

    user_msg = f"""剧情原文：
{storyboard_text}

分镜要点：
{chr(10).join(kf_lines)}

{gender_hint}{aspect_hint}{extra_hint}

请把以上 4 个分镜合并为 1 张竖版四宫格（1024x1536，2x2 grid，每格约512x768竖版手机照片）的中文生图提示词，用于 gpt-image-2。重点是视频关键帧参考，不是成片海报："""

    client = OpenAI(base_url=WENAN["base_url"], api_key=WENAN["api_key"])
    response = client.chat.completions.create(
        model=WENAN["model"],
        messages=[
            {"role": "system", "content": KEYFRAME_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=600,
        temperature=0.8,
        seed=random.randint(1, 99999),
    )

    text = (response.choices[0].message.content or "").strip()

    fallback = (
        "1024x1536竖版四宫格真实手机随手拍，每格约512x768、2:3竖版手机照片比例，不要正方形镜头，像用户相册里的4张普通生活照片，不像广告。"
        "黄色铝制高罐 S101 苦荞精酿啤酒，黑色 S 标识，银色金属易拉盖和拉环，1L/10°P。"
        "左上格：产品放在普通室内木桌上，旁边有零食袋和塑料袋，画面带到房间背景。"
        "右上格：手从打开的背包里拿出产品，背包口和内衬清楚可见，构图不完美。"
        "左下格：手拉开银色金属拉环，保留木桌和背景，不要极端微距。"
        "右下格：普通倒一杯到透明玻璃杯，泡沫自然不过分。"
        "环境低中像素、背景轻微模糊，产品主视觉清楚，黑色大S、素材图同款下方黑色品牌字标、苦荞精酿啤酒、10°P、1L尽量清晰；普通室内光、杂乱木桌，不要乱码伪文字、不要夜市烧烤广告感、不要商业摄影、不要电影感、不要夸张泡沫、不要每格都倒酒、不要黑色拉环、不要干净厨房台面特写、无人脸。"
    )

    return [text if text and len(text) > 30 else fallback]


def build_image_prompt_pack(prompts: list, product_ref: str = "") -> str:
    """
    Build the final formatted prompt pack for gpt-image-2 (single 4-panel image).
    """
    clean = prompts[0] if prompts else ""
    import re
    clean = re.sub(r'^Image\s*\d+[：:]\s*', '', clean).strip()

    product_line = ""
    if product_ref:
        product_line = f"，请参考上传的产品图({product_ref})生成准确的产品外观"

    return (
        f"帮我生成1张1024x1536竖版四宫格图片：\n{clean}\n\n"
        f"注意：这张图分为4个均等的格子（2x2布局），左上/右上/左下/右下各一个镜头，"
        f"每格约512x768，必须是2:3竖版手机照片比例，不要正方形镜头，"
        f"四个格子是同一个普通室内场景的连续动作关键帧，不是广告海报。"
        f"固定动作顺序：1产品放普通木桌建立场景并带房间背景，2手从打开的背包里拿出产品且背包口/内衬清楚，3手拉开银色金属拉环但不要极端微距，4普通倒一杯到透明玻璃杯且泡沫自然。"
        f"画质必须是手机随手拍，环境低中像素、背景轻微模糊、普通室内光、构图不完美、杂乱木桌、房间背景，不像广告；但产品主视觉必须清楚。"
        f"可见罐身正面要清楚绘制黑色大S、素材图同款下方黑色品牌字标、中文“苦荞精酿啤酒”、底部“10°P”“1L”，不要乱码伪文字，不要把品牌字标写成 si01/s1o1/随机假字。"
        f"不要夜市烧烤广告感，不要户外露营，不要人群，不要氛围灯，不要精致商业摄影，不要电影感，不要过度虚化，不要夸张泡沫，不要每格都倒酒，不要干净厨房台面特写，不要水槽边台面，不要石英石台面。"
        f"产品必须是黄色铝制高罐 S101 苦荞精酿啤酒，黑色 S 标识，银色金属易拉盖和银色拉环；不要黑色拉环。{product_line}"
    )
