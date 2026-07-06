"""核心文案生成模块 — 批量生产版。
特性：多样性池（只给写法角度，不注入假体验）/ trigram去重+accept-reject流水线 /
       outputs增量落盘 / 指数退避重试 / 失败不中断批次
"""
import os
import re
import io
import csv
import json
import time
import random
import hashlib
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
import sys, os
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

from modules.common.text_utils import trigram_jaccard
from model_config import WENAN
DEEPSEEK_API_KEY = WENAN["api_key"]
DEEPSEEK_BASE_URL = WENAN["base_url"]
DEEPSEEK_MODEL = WENAN["model"]
INTRO_FILE = os.path.join(_HERE, "介绍.txt")

# ══════════════════════════════════════════════════════════════
#  多样性池 — 只提供「写法角度」，不注入假体验 / 医疗承诺 / 饮后承诺
# ══════════════════════════════════════════════════════════════

_HOOK_STYLES = [
    "痛点反问", "场景切入", "数据/工艺反差", "个人感受开场",
    "对比反差", "疑问开场", "直接推荐", "自嘲/真实开场",
]

_ANGLE_POOL = [
    # 口感向（客观方向，不编体验）
    "强调入口绵柔的口感层次",
    "聊聊回味的荞麦香气",
    "对比工业啤酒的寡淡与精酿的饱满",
    "从泡沫细腻度说酿造工艺",
    # 工艺向（产品事实）
    "28天慢发酵意味着什么",
    "纯粮酿造和工业勾兑的本质区别",
    "德国发酵工艺+中国苦荞的结合",
    "拉环盖设计的便利性",
    # 场景向（不提具体经历，只给场景方向）
    "露营/户外场景的饮酒需求",
    "朋友小聚时的酒水选择",
    "日常自饮的性价比和口感追求",
    "送礼场景的产品差异化",
    # 差异化向（客观对比）
    "精酿vs工业啤酒的生产逻辑",
    "苦荞作为原料的独特之处",
    "为什么发酵周期决定啤酒品质",
    "东西方原料结合的产品思路",
]

_CTA_VARIANTS = [
    "左下角试试", "链接放主页了", "点我头像进橱窗",
    "趁现在有活动冲一波", "试试又不会亏", "主页有链接",
    "想试的来我主页看看", "链接在评论区", "橱窗有，自己去翻",
    "有兴趣的点个关注进主页", "链接放这了，需要的自己看",
]

_PERSONA_POOL = [
    "对啤酒有一点了解、但不说教，用普通人视角聊的消费者",
    "以前觉得啤酒都差不多、最近发现精酿确实不一样的普通人",
    "喜欢户外活动、对随身饮品有一定要求的爱好者",
    "对入口的东西比较在意、会看配料表的消费者",
    "愿意尝试新品类、对各种精酿保持好奇心的酒友",
    "对啤酒没有深度研究、但能喝出好坏的路人",
    "喝过不少精酿、不会被营销话术忽悠的老酒客",
]

# ══════════════════════════════════════════════════════════════
#  文案类型定义
# ══════════════════════════════════════════════════════════════

_ANTI_AI_RULES = """
【核心准则】
- 只抓一个主感受，最多带一个产品事实。别把资料背完。
- 真实的人说"这个还行""我挺意外的"，不说"匠心之作""味蕾盛宴"。
- 允许犹豫和留白："我也说不上来""可能是那个荞麦味吧"。
- 禁止编造经历：不写查了/百度/资料显示/官方说/已经回购/囤一箱/朋友都说好。
- 不用三连四连形容词叠楼，说人话。
- emoji只在情绪到了自然带一个。
"""

_KOUHUO_RULES = """
【核心准则】
- 真心推荐的人，不是念稿导购。卖东西也像人说话。
- 禁止套话："家人们""重磅来袭""错过等一年""天花板"。
- 禁止喊麦："太绝了！""太顶了！"。
- 引导下单要自然，像告诉朋友"你可以试试"，不是电视购物。
- 严格50-80字，短句多，气口多。
"""

COPY_TYPES = {
    "15秒带货口播": {
        "label": "15秒带货口播",
        "prompt": f"""你是一个短视频带货博主，拍15秒推荐视频。只输出口播正文，不要任何思考过程或括号注释。

三段式：
第1句 钩子（5-10字）：痛点/场景/反差
第2-3句 卖点+事实（30-40字）：为什么不一样
第4句 下单引导（8-15字）：告诉去哪买

{_KOUHUO_RULES}""",
    },
    "朋友圈/社群": {
        "label": "朋友圈/社群文案",
        "prompt": f"""你是一个普通人在朋友圈/微信群里随手说一句最近喝到的酒。不是营销号。

写法：
- 80-180字，像临时发的一段话，不追求完整
- 从一个小感受切入，不要完整交代场景
- 不列一二三四，不要"卖点如下"
- 可以有日常废话："怎么说呢""我之前还真没喝过这种"
- 只挑一个明显的点，别贪多
- 别主动讲28天发酵，别解释工业啤酒和精酿区别

{_ANTI_AI_RULES}""",
    },
    "小红书种草": {
        "label": "小红书种草笔记",
        "prompt": f"""你是一个小红书普通用户，写的是一次具体的饮酒体验。

写法：
- 250-500字，标题像真人随手起的
- 开头不固定"朋友带了/上周末/逛超市"
- 不用"绝绝子""挖到宝了""姐妹们冲""谁懂啊"
- 段落可以不均匀，不要每段都像小标题
- 结尾加2-3个标签

{_ANTI_AI_RULES}""",
    },
    "产品详情/公众号": {
        "label": "产品详情/公众号文章",
        "prompt": f"""你是一个懂啤酒、说话实在的内容写手。文章介绍产品，不写成招商稿。

写法：
- 450-800字，可有小标题但别太工整
- 引用资料数据时解释要朴素
- 品牌调性"懂行、实在、有脾气"
- 不在段首写"首先...其次...再者..."
- 结尾点到为止，不强行升华

{_ANTI_AI_RULES}""",
    },
}

# ══════════════════════════════════════════════════════════════
#  内容风控系统
# ══════════════════════════════════════════════════════════════

_CASUAL_COPY_TYPES = {"朋友圈/社群"}
_SELLING_COPY_TYPES = {"15秒带货口播"}

# 格式: (regex_or_literal, category_tag)
_CONTENT_BLOCK_RULES = [
    # ── 饮后承诺 ──
    (r"喝完.{0,5}不(上头|头疼|头痛|难受|口干|胀|晕|困|肿)", "饮后承诺"),
    (r"(不上头|不头疼|头不疼|不难受|不口干|不胀肚|不胀头|没负担)", "饮后承诺"),
    ("第二天照样精神", "饮后承诺"),
    ("第二天不", "饮后承诺"),
    ("没有宿醉", "饮后承诺"),
    ("喝完不胀", "饮后承诺"),
    ("喝再多也不上头", "饮后承诺"),
    ("不胀肚子", "饮后承诺"),
    ("不会难受", "饮后承诺"),
    ("不会头疼", "饮后承诺"),
    ("不会上头", "饮后承诺"),
    ("喝了不头疼", "饮后承诺"),
    ("喝了一点事没有", "饮后承诺"),
    # ── 养生暗示 ──
    (r"(养生|健康).{0,4}?(啤酒|好酒|好喝|精酿|饮品|选择)", "养生暗示"),
    (r"(顾健康|对身体好|对自己好点)", "养生暗示"),
    ("健康啤酒", "养生暗示"),
    ("健康属性", "养生暗示"),
    ("适合三高", "养生暗示"),
    ("三高也能", "养生暗示"),
    ("三高人群", "养生暗示"),
    ("三高朋友", "养生暗示"),
    ("怕三高", "养生暗示"),
    ("怕尿酸", "养生暗示"),
    ("嘌呤高", "养生暗示"),
    ("尿酸高", "养生暗示"),
    ("伤身体", "养生暗示"),
    (r"三高.{0,3}(能|适合|可以|来一杯|喝|放心)", "养生暗示"),
    (r"怕.{0,3}(三高|尿酸|嘌呤|伤身体)", "养生暗示"),
    # ── 违规功效 ──
    ("降血压", "违规功效"),
    ("降血糖", "违规功效"),
    ("降血脂", "违规功效"),
    ("降三高", "违规功效"),
    ("软化血管", "违规功效"),
    ("苦荞精华全融进去", "违规功效"),
    ("苦荞养生的好处", "违规功效"),
    ("喝酒不心虚", "违规功效"),
    ("喝酒没负担", "违规功效"),
    # ── 假体验 ──
    ("查了", "假体验"),
    ("百度", "假体验"),
    ("资料显示", "假体验"),
    ("官方说", "假体验"),
    ("已经回购", "假体验"),
    ("回购好几次", "假体验"),
    ("囤了一箱", "假体验"),
    ("囤一箱", "假体验"),
    ("朋友都说好", "假体验"),
    ("喝了一辈子啤酒", "假体验"),
    ("喝过几十种精酿", "假体验"),
    ("喝过几十款精酿", "假体验"),
    ("第一次遇到", "假体验"),
    ("头一回见到", "假体验"),
    ("念念不忘", "假体验"),
    # ── 编造数量 ──
    ("喝了三瓶", "编造数量"),
    ("喝了两罐", "编造数量"),
    ("连喝了三", "编造数量"),
    ("一口气喝了三", "编造数量"),
    ("喝了四五", "编造数量"),
    ("喝了五六", "编造数量"),
    ("连干三", "编造数量"),
]

# 预编译：regex vs literal
_REGEX_CHARS = set(r".^$*+?{}[]\|()")
_REGEX_RULES = []
_LITERAL_RULES = []
for _p, _tag in _CONTENT_BLOCK_RULES:
    if any(c in _p for c in _REGEX_CHARS):
        _REGEX_RULES.append((re.compile(_p), _tag))
    else:
        _LITERAL_RULES.append((_p, _tag))


def load_intro() -> str:
    if not os.path.exists(INTRO_FILE):
        raise FileNotFoundError(f"介绍文件不存在: {INTRO_FILE}")
    with open(INTRO_FILE, "r", encoding="utf-8") as f:
        return f.read()


def clean_think_leak(text: str) -> str:
    text = re.sub(r'^[（(]选[^）)]*[）)]\s*', '', text)
    text = re.sub(r'^[（(][^）)]*主攻[^）)]*[）)]\s*', '', text)
    text = re.sub(r'^选主攻方向[：:].*?\n+', '', text)
    text = re.sub(r'^(开头勾人|中间一个卖点|结尾引导下单)[：:]\s*', '', text, flags=re.MULTILINE)
    return text.strip()


def find_copy_issues(copy_type: str, text: str) -> list[str]:
    """内容风控。所有文案类型统一拦截。返回问题列表，空=通过。"""
    issues = []

    if copy_type in _SELLING_COPY_TYPES:
        if len(text) > 100:
            issues.append("口播超过100字")
        if re.search(r'[（(]选|主攻方向|开头勾人|中间.*卖点|结尾引导', text):
            issues.append("输出了思考过程")

    # regex 优先
    for compiled_re, tag in _REGEX_RULES:
        if compiled_re.search(text) and tag not in issues:
            issues.append(tag)

    # literal 兜底
    for literal, tag in _LITERAL_RULES:
        if literal in text and tag not in issues:
            issues.append(tag)

    if copy_type in _CASUAL_COPY_TYPES:
        compact = text.replace(" ", "")
        if "28天" in compact or "二十八天" in compact:
            issues.append(f"{copy_type}别主动讲28天发酵")
        if "发酵周期" in compact:
            issues.append(f"{copy_type}别解释发酵周期")

    return issues


def _check_diversity_pool_issues() -> list[str]:
    """自检：多样性池不得命中任何风控规则。"""
    issues = []
    all_texts = _ANGLE_POOL + _PERSONA_POOL + _CTA_VARIANTS
    for idx, text in enumerate(all_texts):
        found = find_copy_issues("15秒带货口播", text)
        for f in found:
            issues.append(f"pool item[{idx}] '{text[:50]}' 命中: {f}")
    return issues


# ══════════════════════════════════════════════════════════════
#  去重引擎
# ══════════════════════════════════════════════════════════════

_SIMILARITY_THRESHOLD = 0.40


def max_similarity(text: str, candidates: list[str]) -> float:
    """返回 text 与 candidates 中最高的相似度"""
    if not candidates:
        return 0.0
    return max(trigram_jaccard(text, c) for c in candidates)


# ══════════════════════════════════════════════════════════════
#  多样性注入
# ══════════════════════════════════════════════════════════════

def _pick_variety(idx: int, total: int) -> dict:
    hook = _HOOK_STYLES[idx % len(_HOOK_STYLES)]
    angle = _ANGLE_POOL[idx % len(_ANGLE_POOL)]
    cta = _CTA_VARIANTS[idx % len(_CTA_VARIANTS)]
    persona = _PERSONA_POOL[idx % len(_PERSONA_POOL)]
    if idx > 0 and random.random() < 0.3:
        hook = random.choice(_HOOK_STYLES)
    if idx > 0 and random.random() < 0.3:
        angle = random.choice(_ANGLE_POOL)
    if idx > 0 and random.random() < 0.3:
        cta = random.choice(_CTA_VARIANTS)
    return {"hook": hook, "angle": angle, "cta": cta, "persona": persona, "idx": idx + 1}


def _inject_variety(base_prompt: str, variety: dict) -> str:
    v = variety
    lines = [
        f"\n\n【第{v['idx']}条独特要求】",
        f"- 开场风格：{v['hook']}",
        f"- 主攻角度：{v['angle']}",
    ]
    if "带货" in base_prompt or "口播" in base_prompt:
        lines.append(f"- 下单话术：{v['cta']}")
    lines.append(f"- 说话身份：{v['persona']}")
    lines.append("- 如果这条跟之前任何一条雷同，刻意换说法、换角度。")
    return base_prompt + "\n".join(lines)


# ══════════════════════════════════════════════════════════════
#  API 调用（带指数退避）
# ══════════════════════════════════════════════════════════════

_RETRY_BASE_DELAY = 2.0   # 秒
_RETRY_MAX_DELAY = 60.0
_RETRY_MAX_TRIES = 4


def _api_call_with_retry(client: OpenAI, messages: list,
                         temperature: float = 0.95) -> str:
    """调用 API，带指数退避。成功返回文本，失败抛异常。"""
    last_error = None
    for attempt in range(_RETRY_MAX_TRIES):
        try:
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=2048,
            )
            return clean_think_leak(response.choices[0].message.content.strip())
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            # 不可重试的错误
            if any(kw in err_str for kw in ["invalid_api_key", "authentication", "insufficient_quota"]):
                raise
            if attempt < _RETRY_MAX_TRIES - 1:
                delay = min(_RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1),
                            _RETRY_MAX_DELAY)
                time.sleep(delay)
    raise last_error


# ══════════════════════════════════════════════════════════════
#  单条生成
# ══════════════════════════════════════════════════════════════

def build_system_prompt(copy_type: str, custom_style: str = "") -> str:
    info = COPY_TYPES.get(copy_type)
    if not info:
        raise ValueError(f"未知文案类型: {copy_type}")
    base = info["prompt"]
    if custom_style:
        base += f"\n\n额外风格要求：{custom_style}"
    return base


def build_user_prompt(intro: str, copy_type: str, custom_topic: str = "",
                      variety: dict = None) -> str:
    if copy_type == "15秒带货口播":
        base = f"""下面是啤酒资料。读后直接输出一条15秒带货口播正文。

---
{intro}
---

直接开口播，不要任何前缀或括号说明。严格50-80字。"""
    else:
        base = f"""下面是啤酒资料。读后写一条{copy_type}文案。

---
{intro}
---

只选1-2个事实或感受点，不完整复述。像真实的人随手表达。"""

    if custom_topic:
        base += f"\n\n本次可偏向：{custom_topic}"
    if variety:
        base = _inject_variety(base, variety)
    return base


def generate_single(client: OpenAI, intro: str, copy_type: str,
                    custom_style: str = "", custom_topic: str = "",
                    variety: dict = None, max_attempts: int = 3) -> str:
    """生成单条，带 issue 自检重试。失败返回 "【生成失败】..." """
    system_prompt = build_system_prompt(copy_type, custom_style)
    user_prompt = build_user_prompt(intro, copy_type, custom_topic, variety)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    last_result = ""
    for attempt in range(max_attempts):
        try:
            last_result = _api_call_with_retry(client, messages,
                                               temperature=0.92 + attempt * 0.03)
        except Exception as e:
            if attempt == max_attempts - 1:
                return f"【生成失败】{str(e)}"
            continue

        issues = find_copy_issues(copy_type, last_result)
        if not issues or attempt == max_attempts - 1:
            return last_result

        messages.append({"role": "assistant", "content": last_result})
        messages.append({
            "role": "user",
            "content": f"上一版问题：{'、'.join(issues)}。请重写，避开这些问题。",
        })

    return last_result


# ══════════════════════════════════════════════════════════════
#  Candidate — Accept/Reject 流水线
# ══════════════════════════════════════════════════════════════

_MAX_DEDUP_RETRIES = 5


def _generate_candidate(
    client: OpenAI, intro: str, copy_type: str,
    custom_style: str, custom_topic: str,
    variety: dict,
) -> dict:
    """生成一个候选。返回 {index, text, issues, sim_to_nearest}"""
    text = generate_single(client, intro, copy_type, custom_style, custom_topic, variety)
    issues = find_copy_issues(copy_type, text) if not text.startswith("【生成失败】") else ["api_error"]
    return {"index": variety["idx"], "text": text, "issues": issues, "sim_to_nearest": None}


def _accept_candidate(candidate: dict, accepted: list[dict],
                      threshold: float = _SIMILARITY_THRESHOLD) -> tuple[bool, float]:
    """
    检查候选能否被接受。
    返回 (accepted: bool, sim_to_nearest: float)
    """
    if candidate["issues"]:
        return False, 0.0
    sim = max_similarity(candidate["text"], [a["text"] for a in accepted])
    if sim > threshold:
        return False, sim
    return True, sim


# ══════════════════════════════════════════════════════════════
#  批量生成主函数
# ══════════════════════════════════════════════════════════════

def generate_batch(copy_type: str, count: int = 3,
                   custom_style: str = "", custom_topic: str = "",
                   progress_callback=None, workers: int = 5,
                   output_dir: str = None,
                   cancel_event=None) -> dict:  # threading.Event
    """
    工业级批量生成。

    cancel_event: 传入 threading.Event，set() 后主循环在下一轮退出，已落盘数据不丢。

    返回:
      results:      按编号排序的文案列表（含失败占位）
      failed:       失败条目 [{index, text, reason}]
      dup_rewrites: 因去重重写的次数
      issue_rewrites: 因 find_copy_issues 重写的次数
      avg_similarity: 最终 accepted 文案的两两平均相似度
      max_similarity: 最终 accepted 文案的两两最高相似度
      total_count:  总请求数
      accepted_count: 成功接受的文案数
      cancelled:    是否被取消
      job_file:     outputs 目录下的 job 文件前缀
    """
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("请先在 .env 文件中配置 DEEPSEEK_API_KEY")
    if count < 1:
        raise ValueError("count 必须 >= 1")

    # ── 输出目录 ──
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "outputs")
    os.makedirs(output_dir, exist_ok=True)
    job_ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")  # 微秒防碰撞
    job_prefix = os.path.join(output_dir, f"job_{job_ts}")
    jsonl_path = job_prefix + ".jsonl"
    cancelled = False

    # ── 初始化 ──
    intro = load_intro()
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

    accepted = []          # [{index, text, issues:[], sim_to_nearest}]
    failed = []            # [{index, text, reason}]
    dup_rewrites = 0
    issue_rewrites = 0
    lock = threading.Lock()

    # 待处理队列: {index: remaining_retries}
    pending = {i + 1: _MAX_DEDUP_RETRIES for i in range(count)}
    varieties = {i + 1: _pick_variety(i, count) for i in range(count)}

    def _write_jsonl(entry: dict):
        with lock:
            with open(jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _report_progress():
        if progress_callback:
            done = len(accepted) + len(failed)
            progress_callback(done, count, len(accepted), len(failed),
                              dup_rewrites, issue_rewrites)

    # ── 主循环 ──
    while pending:
        if cancel_event and cancel_event.is_set():
            cancelled = True
            # 未处理条目记为 cancelled
            for idx in list(pending.keys()):
                _write_jsonl({
                    "index": idx, "text": "",
                    "status": "cancelled",
                    "issues": [], "reason": "user_cancelled",
                    "similarity_to_nearest": 0,
                })
            break

        batch_indices = list(pending.keys())[:workers]

        # 并发生成候选
        with ThreadPoolExecutor(max_workers=len(batch_indices)) as executor:
            futures = {}
            for idx in batch_indices:
                fut = executor.submit(
                    _generate_candidate,
                    client, intro, copy_type,
                    custom_style, custom_topic,
                    varieties[idx],
                )
                futures[fut] = idx

            candidates = []
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    cand = future.result()
                except Exception as e:
                    cand = {"index": idx, "text": f"【生成异常】{e}",
                            "issues": ["exception"], "sim_to_nearest": None}
                candidates.append(cand)

        # 主线程 accept/reject
        for cand in candidates:
            idx = cand["index"]
            ok, sim = _accept_candidate(cand, accepted)

            if ok:
                cand["sim_to_nearest"] = sim
                accepted.append(cand)
                del pending[idx]
                _write_jsonl({
                    "index": idx, "text": cand["text"],
                    "status": "accepted",
                    "issues": [],
                    "similarity_to_nearest": round(sim, 3),
                })
            else:
                pending[idx] -= 1
                if cand["issues"]:
                    issue_rewrites += 1
                else:
                    dup_rewrites += 1

                if pending[idx] <= 0:
                    # 最终失败
                    reason = "issues: " + ",".join(cand["issues"]) if cand["issues"] else "dedup_retries_exhausted"
                    failed.append({"index": idx, "text": cand["text"], "reason": reason})
                    del pending[idx]
                    _write_jsonl({
                        "index": idx, "text": cand["text"],
                        "status": "failed",
                        "issues": cand["issues"],
                        "reason": reason,
                        "similarity_to_nearest": round(sim, 3),
                    })
                else:
                    # 重试：保持原 index，换全新角度
                    varieties[idx] = _pick_variety(idx, count)
                    varieties[idx]["idx"] = idx  # 确保 index 不变

        _report_progress()

    # ── 组装结果 ──
    sorted_accepted = sorted(accepted, key=lambda a: a["index"])
    sorted_failed = sorted(failed, key=lambda f: f["index"])

    # results: 按编号排，失败占位
    all_results = []
    ai, fi = 0, 0
    for i in range(1, count + 1):
        if ai < len(sorted_accepted) and sorted_accepted[ai]["index"] == i:
            all_results.append(sorted_accepted[ai]["text"])
            ai += 1
        elif fi < len(sorted_failed) and sorted_failed[fi]["index"] == i:
            all_results.append(f"[FAILED] {sorted_failed[fi]['text']}")
            fi += 1
        else:
            all_results.append("[MISSING]")

    # 相似度统计 (仅 accepted)
    avg_sim, max_sim_val = _compute_similarity_stats([a["text"] for a in accepted])

    # ── 导出 CSV ──
    csv_path = job_prefix + ".csv"
    _write_csv(csv_path, copy_type, sorted_accepted, sorted_failed, count)

    return {
        "results": all_results,
        "failed": [{"index": f["index"], "text": f["text"], "reason": f["reason"]}
                    for f in sorted_failed],
        "dup_rewrites": dup_rewrites,
        "issue_rewrites": issue_rewrites,
        "avg_similarity": round(avg_sim, 3),
        "max_similarity": round(max_sim_val, 3),
        "total_count": count,
        "accepted_count": len(accepted),
        "cancelled": cancelled,
        "job_file": job_prefix,
    }


def _compute_similarity_stats(texts: list[str]) -> tuple[float, float]:
    """计算 accepted 文案的平均和最高两两相似度（抽样）"""
    n = len(texts)
    if n < 2:
        return 0.0, 0.0
    sims = []
    limit = min(n, 100)
    for i in range(limit):
        for j in range(i + 1, limit):
            sims.append(trigram_jaccard(texts[i], texts[j]))
    if not sims:
        return 0.0, 0.0
    return sum(sims) / len(sims), max(sims)


def _write_csv(path: str, copy_type: str, accepted: list[dict],
               failed: list[dict], total: int):
    """写入 CSV（UTF-8 BOM，Excel 可打开）"""
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["编号", "文案类型", "字数", "状态", "相似度", "内容"])
        for a in accepted:
            writer.writerow([
                a["index"], copy_type, len(a["text"]), "accepted",
                a.get("sim_to_nearest", ""), a["text"],
            ])
        for f_item in failed:
            writer.writerow([
                f_item["index"], copy_type, len(f_item["text"]), "failed",
                "", f_item["text"],
            ])
        # 补全 missing（如果有）
        written_indices = {a["index"] for a in accepted} | {f["index"] for f in failed}
        for i in range(1, total + 1):
            if i not in written_indices:
                writer.writerow([i, copy_type, 0, "missing", "", ""])


# ══════════════════════════════════════════════════════════════
#  导出工具
# ══════════════════════════════════════════════════════════════

def export_csv(results: list[str], copy_type: str) -> str:
    """将结果列表导出为 CSV 字符串（UTF-8 BOM）"""
    output = io.StringIO()
    output.write('﻿')
    writer = csv.writer(output)
    writer.writerow(["编号", "文案类型", "字数", "内容"])
    for i, text in enumerate(results, 1):
        writer.writerow([i, copy_type, len(text), text])
    return output.getvalue()
