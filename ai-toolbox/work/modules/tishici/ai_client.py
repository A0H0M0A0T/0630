"""
AI Client module - OpenAI-compatible API client for multiple models
Supports Volcengine, DeepSeek, and more with easy switching
"""
import json
import time
import random
from typing import Optional, List, Dict, Any, Tuple
from openai import OpenAI


# Default model configurations
MODELS = {
    "main": {
        "name": "大号火山 (ark-code-latest)",
        "api_key": "REDACTED_VOLC1",
        "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
        "model": "ark-code-latest"
    },
    "model2": {
        "name": "小号1火山 (ahmat2)",
        "api_key": "REDACTED_VOLC2",
        "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
        "model": "ark-code-latest"
    },
    "model3": {
        "name": "小号2火山 (api-key-maierdan)",
        "api_key": "REDACTED_VOLC3",
        "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
        "model": "ark-code-latest"
    },
    "deepseek4": {
        "name": "DeepSeek V4-Pro",
        "api_key": "REDACTED_DEEPSEEK",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-pro"
    }
}


# ====== 🎯 目标人群选项 ======
AUDIENCE_OPTIONS = [
    "女大学生/年轻女生日常 (55%)",
    "男大学生/年轻男生日常 (15%)",
    "年轻上班族/社会新人日常 (30%)"
]

# ====== 🏙 超丰富现实场景 (50+) ======
SCENE_OPTIONS = [
    "大学食堂", "大学宿舍", "宿舍阳台", "教学楼走廊", "图书馆门口",
    "考研自习室", "学校操场边", "篮球场边", "学校后门小吃街",
    "学校门口奶茶店", "宿舍楼下快递站", "课间教室后排", "学校草坪",
    "学生活动中心", "实验室", "校外租房客厅", "外卖柜旁边",
    "烧烤大排档", "夜市小吃摊", "火锅店", "麻辣烫店", "炸鸡店",
    "学校附近小酒馆", "便利店里", "便利店门口", "电影院休息区",
    "商场负一楼美食街", "KTV包厢", "咖啡店", "奶茶店",
    "出租车上", "地铁车厢", "公交车站", "共享单车旁",
    "放学路上人行道", "天桥上", "地下通道",
    "公园草坪", "江边步道", "小区楼下", "天台晾衣处",
    "超市货架旁", "快递驿站", "自动售货机前", "外卖取餐柜",
    "实习工位", "公司茶水间", "公司楼下便利店", "下班路上",
    "周末逛街路边", "商场试衣间外", "电梯里", "楼梯间转角",
    "家门口鞋柜旁", "客厅沙发", "卧室书桌前", "家里餐桌",
    "出租屋小厨房", "阳台晾衣架旁", "洗手台前", "冰箱前面",
    "毕业旅行民宿", "周末公园野餐", "河堤散步", "音乐节现场草坪",
    "漫展现场", "游乐园排队区", "夜市套圈摊", "密室逃脱等候区"
]

# ====== 👤 超丰富现实人物选项(50+) ======
FEMALE_COLLEGE = [
    "女大学生", "考研党女生", "应届毕业女生", "正在实习的女生",
    "学生会女生", "社团活动女生", "宿舍追剧女生", "期末复习女生",
    "兼职打工女生", "校园情侣女生", "大二女生", "大三女生",
    "大四写论文的女生", "刚考完试的女生", "军训休息中的女生",
    "周末回家的女生", "和闺蜜逛街的女生", "参加社团活动的女生",
    "图书馆自习女生", "去食堂路上的女生"
]

MALE_COLLEGE = [
    "男大学生", "篮球场打球的男生", "社团男生", "宿舍开黑男生",
    "考研党男生", "学生会男生", "期末冲刺的男生", "健身的男生",
    "兼职送外卖的男生", "校园情侣男生", "打游戏累了的男生"
]

YOUNG_WORKERS = [
    "刚下班的年轻女生", "通勤路上的女生", "租房独居的上班族",
    "自由职业女生", "刚毕业入职新人", "职场新人女生",
    "周末放松的上班族", "加班结束的白领", "下班回家路上的人",
    "周末逛街的女生", "周末约会的女生", "独自在外打拼的女生",
    "和同事聚餐的年轻人", "周末一个人逛超市的女生",
    "刚搬到新城市的年轻人", "休息日做饭的独居女生",
    "周末宅家追剧的女生", "晚上遛弯的女生"
]

# Weighted person selection
def random_person(audience: str = "随机") -> str:
    """Choose a person based on audience weighting."""
    if audience == "女大学生/年轻女生日常 (55%)":
        return random.choice(FEMALE_COLLEGE)
    elif audience == "男大学生/年轻男生日常 (15%)":
        return random.choice(MALE_COLLEGE)
    elif audience == "年轻上班族/社会新人日常 (30%)":
        return random.choice(YOUNG_WORKERS)
    else:  # 随机 - follow the 55/15/30 distribution
        roll = random.random() * 100
        if roll < 55:
            return random.choice(FEMALE_COLLEGE)
        elif roll < 70:
            return random.choice(MALE_COLLEGE)
        else:
            return random.choice(YOUNG_WORKERS)

PERSON_OPTIONS = AUDIENCE_OPTIONS + ["完全随机（按比例）"]

# ====== 🌤 超丰富天气选项 (50+) ======
WEATHER_OPTIONS = [
    "随机(适合场景)", "晴朗蓝天", "多云", "阴天", "小雨",
    "雨后初晴", "黄昏傍晚", "金色夕阳", "日落时分", "清晨日出",
    "午后阳光正好", "傍晚华灯初上", "夜间路灯下", "室内暖光",
    "室内白光", "商场冷光", "宿舍台灯下", "咖啡店暖黄灯光",
    "教室日光灯", "便利店白光", "路边暖色路灯", "阳台自然光",
    "窗边逆光", "树荫斑驳", "夕阳余晖", "夜晚霓虹灯",
    "春日下午", "夏天的午后", "秋天的傍晚", "冬天的中午",
    "傍晚六点的夏天（天还没全暗）", "午休时间阳光直射",
    "晚自习后的夜晚", "清晨赶早课的路上", "周末懒散的下午",
    "深夜便利店灯光", "电影散场后的夜晚", "商场打烊的灯光",
    "大晴天阳光刺眼", "樱花季的柔和光线", "初夏微热的傍晚",
    "深秋凉风中的黄昏", "初春乍暖还寒的午后", "梅雨季的潮湿下午",
    "学校路灯下", "电梯里的灯光", "地铁车厢的白光",
    "出租车的车内灯", "火锅店的暖光", "烧烤摊的烟火光线"
]

# ====== 🎨 超丰富现实风格选项 (50+) ======
STYLE_OPTIONS = [
    "普通手机随手拍真实风格",
    "第一人称vlog随手拍风格",
    "小红书生活记录风",
    "抖音日常分享风",
    "ins故事随手拍风",
    "手机前置镜头自拍感",
    "后置摄像头日常记录",
    "窗边自然光柔焦",
    "暖色台灯氛围",
    "宿舍灯光真实记录",
    "教室日光灯下",
    "咖啡店暖光氛围",
    "路边自然光抓拍",
    "吃饭前随手拍",
    "刚拿到东西拍一张",
    "开箱时拍一张",
    "和朋友的合影视角",
    "一个人吃饭的视角",
    "逛街时的随手拍",
    "外卖到了先拍照",
    "新买的东西拍个照",
    "出去玩时记录一下",
    "学习累了拍一下",
    "桌面上乱中有序的真实感",
    "生活碎片记录风格",
    "真实的日常感",
    "没有刻意构图的生活照",
    "好友聚会随手记录",
    "周末日常碎片",
    "旅行随手记",
    "第一人称吃播视角", "第一人称逛街视角",
    "第一人称做家务视角", "第一人称收拾房间视角",
    "第一人称准备出门视角", "第一人称回家视角",
    "第一人称做饭视角", "第一人称超市购物视角",
    "第一人称取快递视角", "第一人称下班路上视角",
    "第一人称周末宅家视角", "第一人称等车视角",
    "第一人称坐地铁视角", "第一人称和朋友吃饭视角",
    "第一人称逛夜市视角", "真实的镜头晃动感",
    "随手举起手机拍的即时感", "没有任何滤镜的真实色调",
    "日常生活碎片拼接感", "发朋友圈的九宫格风格"
]

# ====== 🔄 超丰富现实动作选项 (50+) ======
ACTION_OPTIONS = [
    "拿着酒杯", "拿着目标产品", "放着酒杯", "放着目标产品",
    "举杯畅饮", "和朋友碰杯", "正在倒酒", "手指夹着酒杯沿",
    "拧开瓶盖", "把酒从袋子里拿出来", "把酒放在桌上",
    "酒杯和酒瓶并排放着", "吃串时顺手拿起酒",
    "火锅旁放着酒", "烧烤配啤酒", "吃小龙虾配啤酒",
    "和朋友干杯大笑", "微醺托腮", "靠在椅背上喝酒",
    "坐在椅子上喝啤酒", "站着喝酒看手机", "边走边喝",
    "把酒放在窗台上", "酒瓶放在书架旁边",
    "摆在宿舍书桌上", "放在外卖旁边", "放进冰箱里",
    "从冰箱里拿出来", "放在购物车里", "在收银台结账",
    "和朋友分享一箱酒", "一手拿串一手拿酒",
    "碰杯前举起酒瓶", "喝了一大口放下", "慢慢喝了一小口",
    "对瓶喝", "倒在杯子里喝", "和朋友一起干杯",
    "配着炸鸡喝", "配着烧烤喝", "配着火锅喝",
    "在夜市边逛边喝", "坐在路边喝", "在天台上喝",
    "在宿舍和室友喝", "自己一个人小酌", "看着剧喝啤酒",
    "配着零食喝啤酒", "写完论文奖励自己", "考完试放松一下",
    "周末放松来一瓶", "和好久不见的朋友碰杯"
]

# ====== 场景氛围增强描述 ======
SCENE_EXTRA_MAP = {
    "大学食堂": "（大学食堂的嘈杂感，不锈钢餐盘，人多热闹）",
    "宿舍": "（宿舍上下铺/上床下桌，墙上贴海报，桌上堆满东西的真实感）",
    "烧烤大排档": "（路边烤串摊，烟火缭绕，塑料矮凳，暖黄灯泡）",
    "夜市": "（霓虹闪烁，各种小吃摊，人声鼎沸）",
    "小酒馆": "（灯光昏暗有氛围，木质桌子，酒瓶子多）",
    "便利店": "（冷白光的货架，冰柜门开着，门口夜灯）",
    "KTV包厢": "（霓虹灯光，大屏幕在放歌，桌上摆满零食）",
    "教室": "（课桌上一堆书和笔，典型的大学教室）",
    "图书馆": "（安静，书架林立，台灯下学习）",
    "出租屋": "（小小的房间但布置温馨，有生活气息）",
    "家": "（家里很随意，客厅茶几上堆着零食遥控器）",
    "办公室": "（工位上有电脑、文件、水杯，典型的格子间）",
}


def get_scene_extra(scene: str) -> str:
    for key, desc in SCENE_EXTRA_MAP.items():
        if key in scene:
            return desc
    return ""


def build_system_prompt() -> str:
    return """你是产品宣传图提示词生成专家，为gpt-image2生成产品宣传图的提示词。注意：提示词本身是给gpt-image2用的文本，提示词中不要出现①②③④等可视化序号标记，直接用文字说明"第一张""第二张"即可。

## 🔴 绝对禁止（违反即无效）
1. ❌ 禁止出现中老年人、老人、大叔大妈等角色
2. ❌ 禁止第三人称描述（如"一个女生坐在..."），必须是第一人称
3. ❌ 禁止不切实际的场景（游艇、高尔夫、深山老林、异世界等）
4. ❌ 禁止不合理动作（背着啤酒瓶、扛着啤酒箱等）
5. ❌ 禁止4张图之间有关联（必须完全独立的四个场景时段）
6. ❌ 禁止出现清晰人脸
7. ❌ **禁止同款产品尺寸不一致！** 同一张图中如果出现多个s101.png，它们的高宽尺寸必须完全一样，不能一个大一个小
8. ❌ **禁止产品悬空/漂浮/摆放不合物理！** 产品必须放在真实的支撑面上（桌面、地面、货架、手中、袋子里等），不能悬在空中或卡在不可能的位置
9. ❌ **禁止输出①②③④等可视化序号字符！** 提示词中只能用文字"第一张""第二张"等，不得出现①、②、③、④这类Unicode序号符号
10. ❌ **禁止四张图中超过1张是"脚边/鞋旁放产品"的构图！** 四张图的镜头视角必须多样化：至少2张是桌面/手部/柜台第一人称视角，最多1张是腿部/脚边视角

## 🟢 核心要求
1. 受众画像：18-30岁年轻人（女大学生/男大学生/年轻上班族）
2. 第一人称：仿佛是自己在用眼睛看（"镜头前是自己的手/身体部位/衣服"）
3. 场景必须：普通人日常生活能遇到的地方
4. 真实质感：像用手机随便拍的，有生活气和烟火气
5. 4张照片角度不同、地点不同、时间不同、动作不同
6. **物理一致性：** 同一张图里所有目标产品s101.png必须是完全相同尺寸（1L/高22cm/宽7.0cm），不能出现大小不一的同款产品
7. **安全摆放：** 产品必须稳稳地放在实际的支撑面上，不允许悬浮、仅靠边缘卡着、倾斜放置等不合理摆放

## ✅ 第一人称正确写法示例（多样化视角）
✓ "低头看到自己的手正拧开瓶盖，瓶身1L/高22cm/宽7.0cm，穿着浅蓝色牛仔外套"  ← 手部近景
✓ "自己的手举着s101.png（1L/高22cm/宽7.0cm）对着便利店冰柜的自拍视角"  ← 手持自拍
✓ "从自己的视角看出去，桌面摆着烤串和两个s101.png（均为1L/高22cm/宽7.0cm），自己手边是酒杯"  ← 桌前正视
✓ "自己的手从购物袋里拿出s101.png（1L/高22cm/宽7.0cm），袋子里还有一个"  ← 取物视角
✓ "自己低头看到胸口衣服上有食物渍，桌边放着一瓶s101.png（1L/高22cm/宽7.0cm）"  ← 低头看桌
✓ "自己的手搭在冰箱门上，冰箱中层架子上立着两瓶s101.png（均为1L/高22cm/宽7.0cm）"  ← 开冰箱视角

## ❌ 第三人称错误写法示例
✗ "一个女生坐在桌边，她拿着酒杯"
✗ "女生穿着白色T恤，她正在喝酒"

## 📐 产品规格
目标产品："s101.png" (1L装，高22cm，宽7.0cm)
提示词中必须包含尺寸描述：1L/高22cm/宽7.0cm
每张图出现1-3个目标产品
**⚠️ 关键：** 同一张图中所有s101.png产品的尺寸标记必须统一且完全相同！例如"两个并排放着的s101.png（均为1L/高22cm/宽7.0cm）"

## 📝 输出格式
生成4张独立无关联的第一人称实拍照片，全局要求：[全局要求] 第一张：[描述]；第二张：[描述]；第三张：[描述]；第四张：[描述]。
⚠️ 提示词前后不要加《》或任何括号符号！直接用纯文字！只能用文字"第一张""第二张""第三张""第四张"！不要使用①②③④等Unicode序号符号！
全文300-500字，每张场景详细描述光线、背景、动作、产品摆放。

## ✅ 合理摆放示例（必须这样写）
✓ "桌面上放着两瓶s101.png，并排稳稳立在桌面上（均为1L/高22cm/宽7.0cm）"
✓ "一只手从袋子里拿出s101.png，瓶子垂直立于袋中"
✓ "冰箱门开着，s101.png直立放在冰箱中层架子上"

## ❌ 不合理摆放（绝对禁止）
✗ "酒瓶悬浮在桌面上方" ✗ "瓶子斜靠在杯沿上" ✗ "酒瓶卡在桌子边缘摇摇欲坠"
✗ "一个大的s101.png旁边放着一个小的s101.png（同款产品不能大小不一！）"
✗ "瓶子从桌面一角悬空伸出" ✗ "瓶子立在地板边缘" ✗ "瓶子在窗台外沿快掉下去"

## 🎯 视角多样化要求（关键！）
在生成4张图时，必须严格遵循以下视角分配：
- 至少2张必须是：桌前俯拍/手部操作/柜台台面/餐桌桌面/手举物品等中近景视角
- 最多1张可以是：腿部/脚边/鞋子旁边放产品的视角
- 剩余1张自选但不要重复上述视角
**禁止4张中超过1张是"露腿露鞋放产品"的构图！**

**记住：所有产品必须符合现实物理规则，稳稳地立在真实平面上！**"""




def build_user_prompt(params: Dict[str, Any]) -> str:
    """Build user prompt from parameters."""
    scene = params.get("scene", "大学宿舍")
    person = params.get("person", "女大学生")
    weather = params.get("weather", "室内暖光")
    style = params.get("style", "普通手机随手拍真实风格")
    action = params.get("action", "拿着酒杯")
    audience = params.get("audience", "随机")
    count = params.get("count", 4)
    min_product = params.get("min_product", 1)
    max_product = params.get("max_product", 3)
    extra_requirements = params.get("extra", "")
    product_spec = "1L/高22cm/宽7.0cm"

    scene_extra = get_scene_extra(scene)

    parts = [f"请生成{count}张独立无关联的第一人称实拍照片提示词（共4张）。"]

    if audience == "女大学生/年轻女生日常 (55%)":
        audience_detail = "女大学生（18-24岁），穿着日常大学生风格（卫衣/T恤/牛仔裤/裙子等），宿舍或校园常见穿搭"
    elif audience == "男大学生/年轻男生日常 (15%)":
        audience_detail = "男大学生（18-24岁），日常休闲穿搭（运动装/T恤/卫衣/球鞋等）"
    elif audience == "年轻上班族/社会新人日常 (30%)":
        audience_detail = "年轻上班族（22-28岁），简约通勤风格，租房独居或合租的日常生活"
    else:
        audience_detail = "18-30岁年轻人"

    parts.append(f"\n【目标受众】{audience_detail}")
    parts.append(f"【场景】{scene}{scene_extra}")
    parts.append(f"【人物视角】第一人称，画面中出现的是{person}的手/腿/身体局部，不要出现正脸")
    parts.append(f"【天气光线】{weather}")
    parts.append(f"【摄影风格】{style}")
    parts.append(f"【核心动作】{action}")
    parts.append(f"【目标产品】每张出现{min_product}-{max_product}个s101.png ({product_spec})")

    if extra_requirements and extra_requirements not in ["无特殊要求", "无特殊要求，让AI自由发挥", ""]:
        parts.append(f"【附加要求】{extra_requirements}")

    parts.append(f"\n⚠️ 重要提醒：")
    parts.append(f"1. 四张图必须发生在四个完全不同的场景/时间/地点，毫无关联！")
    parts.append(f"2. 必须是第一人称！画面中出现的是自己的手/腿/身体部位")
    parts.append(f"3. 不要出现中老年人，不要出现清晰正脸")
    parts.append(f"4. 场景必须是普通人日常能遇到的，不能离谱")
    parts.append(f"5. 动作要合理，啤酒是用来喝的，不是用来扛的")
    parts.append(f"6. 🚫 同一张图中所有s101.png尺寸必须完全一致！不能一会说高22cm一会说矮的")
    parts.append(f"7. 🚫 产品绝对不能悬空/漂浮！必须稳稳放在桌面/地面/货架/手中等真实支撑面上")
    parts.append(f"直接生成纯文本提示词，不要使用《》或任何括号包裹，全文300-500字。")

    prompt = "\n".join(parts)
    return prompt


ADDITIONAL_RULES = [
    "【本次特别注意】四张图的时间地点必须完全不同，比如第一张中午食堂、第二张傍晚宿舍、第三张晚上便利店、第四张深夜回家路上",
    "【本次特别注意】请重点描写手的动作细节，因为第一人称画面中手是最常见的元素",
    "【本次特别注意】请加入生活化的小细节（比如美甲、手链、手表、戒指等配饰），增强真实感",
    "【本次特别注意】每张图的光线来源要不同：自然光、台灯、路灯、霓虹灯等交替使用",
    "【本次特别注意】注意景别变化：近景（手部特写）、中景（上半身）、远景（环境带人）交替使用",
    "【本次特别注意】加入时间线索：比如手机显示的时间、窗外天色变化，暗示四张图发生在同一天的不同时间",
    "【本次特别注意⚠️】同一个s101.png产品出现在同一张图中时，所有s101.png尺寸必须标注一致！不能说一个大一个小。应写为「两个s101.png并排(均为1L/高22cm/宽7.0cm)」",
    "【本次特别注意⚠️】检查每个s101.png的摆放位置是否合理！只能放在：桌面、地面、货架、购物车、冰箱架、手中、袋子里、背包里等真实水平支撑面，绝对不能悬空",
    "【本次特别注意⚠️双规则】第一：同款产品尺寸统一，s101.png(1L/高22cm/宽7.0cm)标记在所有产品上保持一致；第二：物理摆放合理，产品底端必须接触真实支撑平面，不能浮在半空",
    "【本次特别注意⚠️视角多样化】至少2张必须是桌前俯拍或手部操作视角，最多1张是腿脚边视角！不要总是露腿放产品",
    "【本次特别注意⚠️禁止序号】提示词中禁止使用①②③④等Unicode序号符号，只能用文字「第一张」「第二张」",
    "【本次特别注意⚠️尺寸统一+物理摆放】四张图中每张的产品如果出现多个，所有的s101.png大小尺寸必须一模一样，且都稳稳放在真实平面上",
]


class AIClient:
    """AI client supporting multiple model configurations (Volcengine, DeepSeek, etc.)"""

    def __init__(self, model_key: str = "main"):
        self.model_key = model_key
        self._init_client()

    def _init_client(self):
        cfg = MODELS[self.model_key]
        self.client = OpenAI(
            api_key=cfg["api_key"],
            base_url=cfg["base_url"]
        )
        self.model = cfg["model"]

    def switch_model(self, model_key: str):
        if model_key not in MODELS:
            raise ValueError(f"Unknown model key: {model_key}. Available: {list(MODELS.keys())}")
        self.model_key = model_key
        self._init_client()

    def get_model_name(self) -> str:
        return MODELS[self.model_key]["name"]

    @staticmethod
    def get_available_models() -> Dict[str, str]:
        return {k: v["name"] for k, v in MODELS.items()}

    @staticmethod
    def get_random_person_from_audience(audience: str) -> str:
        return random_person(audience)

    def generate_prompt(self, params: Dict[str, Any], temperature: float = 0.85,
                        seed: Optional[int] = None) -> str:
        """
        Generate a product promotion prompt using the AI model.
        """
        system_prompt = build_system_prompt()
        extra_rule = random.choice(ADDITIONAL_RULES)
        combined = system_prompt + "\n\n" + extra_rule
        user_prompt = build_user_prompt(params)

        if seed is None:
            seed = random.randint(1, 99999)

        messages = [
            {"role": "system", "content": combined},
            {"role": "user", "content": user_prompt}
        ]

        # DeepSeek models use different API format - no extra_body
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4096,
            "seed": seed,
        }
        # Only add extra_body for Volcengine (supports top_p); DeepSeek does not support it
        if "volces" in MODELS[self.model_key]["base_url"]:
            kwargs["extra_body"] = {"top_p": 0.92}

        response = self.client.chat.completions.create(**kwargs)

        result = response.choices[0].message.content.strip()
        result = self._sanitize_result(result)
        return result

    @staticmethod
    def _sanitize_result(result: str) -> str:
        """
        Post-process AI result to remove issues:
        1. Strip ①②③④ Unicode symbols
        2. Warn about potential physics/size issues (logging)
        """
        import re
        # 1. Strip Unicode circled numbers ① ② ③ ④ ⑤ ⑥ ⑦ ⑧
        result = re.sub(r'[\u2460-\u2473]', '', result)
        # Also strip circled negatives (🄌 etc)
        result = re.sub(r'[\u24F9-\u24FF]', '', result)
        # Strip ⓵⓶⓷⓸ (double-circled numbers)
        result = re.sub(r'[\u24D0-\u24E9\u2460-\u2473]', '', result)
        # 2. Strip all types of Chinese/full-width angle brackets
        result = re.sub(r'[《》【】〖〗〈〉「」『』〔〕«»‹›]', '', result)
        # Clean up extra whitespace from removed chars
        result = re.sub(r'  +', ' ', result).strip()
        return result

    def generate_batch(self, params: Dict[str, Any], batch_size: int = 1,
                       temperature_range: tuple = (0.80, 0.95)) -> List[str]:
        results = []
        for i in range(batch_size):
            temp = temperature_range[0] + (temperature_range[1] - temperature_range[0]) * (i / max(batch_size - 1, 1))
            result = self.generate_prompt(params, temperature=round(temp, 2))
            results.append(result)
            time.sleep(0.5)
        return results


if __name__ == "__main__":
    print(f"AI Client Module - Test")
    print(f"Available models: {list(AIClient.get_available_models().keys())}")
    print(f"Scene options: {len(SCENE_OPTIONS)}")
    print(f"Weather options: {len(WEATHER_OPTIONS)}")
    print(f"Style options: {len(STYLE_OPTIONS)}")
    print(f"Action options: {len(ACTION_OPTIONS)}")

    print("\n--- Weighted Random Person Test (10 samples) ---")
    for _ in range(10):
        print(f"  {random_person('随机')}")

    client = AIClient("main")
    print(f"\nUsing model: {client.get_model_name()}")
    print("Module OK")
