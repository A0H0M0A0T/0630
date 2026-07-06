# Code Review Report — hashtag-enricher 集成

**日期**: 2026-07-03  
**范围**: hashtag-enricher 集成到 ai-toolbox 的所有变更  
**等级**: max effort (5+5 angles × 8 candidates → 1-vote verify → sweep)  
**方法**: 6 个 finder agent + 3 个验证 agent + 1 个 sweep agent，共发现 18 个确认问题

---

## ⛔ P0: 工作流完成后永久卡在 "running" 状态

**文件**: `D:\0703\ai-toolbox\work\modules\orchestrator\engine.py:417`  
**发现途径**: Phase 3 sweep

**问题**:
1. Step 7 (line 723) 设置 `st.status = "completed"` — 正确
2. `_start_step(8)` (line 417) **无条件**设置 `st.status = "running"` — 覆盖 "completed"!
3. `_finish_step(8)` (line 432-444) **不设置 status，不调用 `st.save()`**
4. 结果: 所有 8 步全部成功，但 status 永远为 "running"

**影响**:
- 前端 `pollWorkflowUntilDone()` 检测不到 `"completed"`，轮询直到超时 (7.5 分钟)
- `get_workflow_result()` 返回 HTTP 409，用户无法获取结果
- 完整成功的工作流对用户不可见

**修复方案**: `_finish_step(8)` 之后添加 `st.status = "completed"; st.save()`，或 Step 7 不提前设 completed，由最后一个步骤统一设置。**这必须先修。**

---

## 严重级别分布

| 级别 | 数量 |
|------|------|
| ⛔ P0 (工作流不可用) | 1 |
| 🔴 Critical (崩溃/数据损坏) | 7 |
| 🟠 High (错误行为/用户体验) | 3 |
| 🟡 Medium (代码质量/安全隐患) | 4 |
| 🟢 Low (健壮性/可维护性) | 3 |

---

## 1. 🔴 server.py:1032 — Pydantic Optional[str] null 导致 AttributeError

**文件**: `D:\0703\ai-toolbox\work\server.py:1032`  
**严重级别**: Critical  
**类别**: correctness

**问题**: 
```python
class HashtagGenerateReq(BaseModel):
    topic: Optional[str] = ""
```

Pydantic v2 在 JSON 体包含 `"topic": null` 时将字段设为 `None`，不会触发默认值 `""`。后续 `req.topic.strip()` 抛出 `AttributeError: 'NoneType' object has no attribute 'strip'`。

**触发条件**: 任何 API 调用者发送 `{"topic": null, ...}` → 500 Internal Server Error

**修复方案**:
```python
topic: Optional[str] = ""
# → 改为:
topic: str = ""
# 或者
if req.topic and req.topic.strip():  # None-safe 检查
```

---

## 2. 🔴 engine.py:723 — Step 7 过早设置 status='completed'

**文件**: `D:\0703\ai-toolbox\work\modules\orchestrator\engine.py:723`  
**严重级别**: Critical  
**类别**: correctness

**问题**: Step 7 (视频提交) 在成功后将 `st.status = "completed"`，但此时 Step 8 尚未执行。若 Step 8 失败，`_fail_step` 无条件覆盖 status 为 `"failed"`，打破 completed 是终端状态的规矩。

```
状态流转: pending → completed (Step 7) → failed (Step 8 失败)
```

**触发条件**: 客户端在 Step 7 和 Step 8 之间轮询时看到 completed；Step 8 失败后工作流被标记为 failed，但视频实际已提交。

**修复方案**: 
- Step 7 不设 `st.status = "completed"`，让 Step 8 完成后再设
- 或者 Step 8 失败时用 warning 而非 fail，不影响已完成视频的任务

---

## 3. 🔴 engine.py:756 — time.localtime() + 'Z' 时区错误

**文件**: `D:\0703\ai-toolbox\work\modules\orchestrator\engine.py:756`  
**严重级别**: Critical  
**类别**: correctness

**问题**:
```python
"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.localtime())
```
`time.localtime()` 返回服务器本地时间，但 `Z` 后缀表示 UTC。UTC+8 服务器上的时间戳会偏移 8 小时。

**修复方案**: `time.localtime()` → `time.gmtime()`

---

## 4. 🔴 state.py:239 — total_steps 默认值 7

**文件**: `D:\0703\ai-toolbox\work\modules\orchestrator\state.py:239`  
**严重级别**: Critical  
**类别**: correctness

**问题**: `_load()` 中 `self.total_steps = d.get("total_steps", 7)`，旧 DB 行加载为 7 而非 8。DB schema DEFAULT 也是 7。

**触发条件**: 旧工作流从 DB 恢复 → total_steps=7 → 前端显示 "Step 8 / 7"

**修复方案**:
1. `_load()` 默认值改为 8
2. DB schema DEFAULT 改为 8
3. 添加 migration 更新旧行 `UPDATE workflows SET total_steps = 8 WHERE total_steps = 7`

---

## 5. 🔴 llm.py:39 — httpx.Client 线程不安全

**文件**: `D:\0703\ai-toolbox\work\modules\hashtag_enricher\enricher\llm.py:39`  
**严重级别**: Critical  
**类别**: correctness

**问题**: `_client = httpx.Client(...)` 是模块级全局单例，httpx 明确文档说明 Client 不线程安全。FastAPI 主线程和工作流后台线程 (`threading.Thread`) 同时使用该 client。

**触发条件**: 并发调用 `/api/hashtag/generate` + 工作流 Step 8 → 连接池数据竞争 → ConnectionResetError 或响应串扰

**修复方案**:
- 改用 `httpx.AsyncClient` (FastAPI 兼容)
- 或每次调用创建新 client (用 context manager)
- 或使用 `threading.local()` 存储线程级 client

---

## 6. 🔴 engine.py:744 — Step 8 硬编码中文+YouTube

**文件**: `D:\0703\ai-toolbox\work\modules\orchestrator\engine.py:744`  
**严重级别**: Critical  
**类别**: correctness

**问题**:
```python
platform = "youtube"  # 硬编码
lang = "Chinese"      # 硬编码
tags = generate_hashtags(topic, lang, platform=platform)
```
独立 API 支持三种平台和自动语言检测，但工作流路径完全不支持。

**触发条件**: 生成英文/西语内容 → 产生中文标签。TikTok 场景下应限制 5 条标签，实际生成 60 条。

**修复方案**: 复用独立 API 的逻辑，用 `detect_and_generate()` 或在工作流参数中添加平台/语言配置。

---

## 7. 🔴 engine.py:740 — copy_text.strip() 在 None 上崩溃

**文件**: `D:\0703\ai-toolbox\work\modules\orchestrator\engine.py:740`  
**严重级别**: Critical  
**类别**: correctness

**问题**: `st.copy_text.strip()` — 若 DB 中 copy_text 列为 NULL，`d.get("copy_text", "")` 返回 None 而非 ""，导致 AttributeError。

**修复方案**:
```python
topic = (st.copy_text or "").strip()
```

---

## 8. 🟠 WorkflowPage.tsx:37 — 前端 STEP_LABELS 缺少 Step 8

**文件**: `D:\0703\ai-toolbox\work\src\components\WorkflowPage.tsx:37`  
**严重级别**: High  
**类别**: correctness

**问题**: 前端 STEP_LABELS 只有 1-7，Step 8 时 `STEP_LABELS[8]` 为 undefined，回退到 "正在执行"。

**修复方案**: 在 STEP_LABELS 中添加 `8: "生成发布标签"`

---

## 9. 🟠 workflowDiagnostics.ts:22 — 诊断组件缺少 Step 7、8

**文件**: `D:\0703\ai-toolbox\work\src\workflowDiagnostics.ts:22,140`  
**严重级别**: High  
**类别**: correctness

**问题**: 
- STEP_LABELS 只有 1-6
- `getWorkflowStepRows()` 只循环 1-6
- `status?.total_steps ?? 6` 硬编码回退值为 6

**修复方案**: 添加 Step 7-8 label，修改回退值为 8

---

## 10. 🟠 llm.py:93 — 重试仅处理 HTTP 429

**文件**: `D:\0703\ai-toolbox\work\modules\hashtag_enricher\enricher\llm.py:93`  
**严重级别**: High  
**类别**: correctness

**问题**: `_chat()` 的重试逻辑仅捕获 HTTP 429，网络异常 (ConnectError, TimeoutException) 直接逃逸。

**触发条件**: 瞬态 DNS/网络故障 → 工作流 Step 8 直接失败

**修复方案**: 在 try/except 中捕获 `httpx.HTTPError` (所有 httpx 异常基类) 进行重试

---

## 11. 🟡 engine.py:751 — 重复 build_hashtags_block()

**文件**: `D:\0703\ai-toolbox\work\modules\orchestrator\engine.py:751`  
**严重级别**: Medium  
**类别**: simplification

**问题**: Step 8 手动构造 hashtag_block 字典，与 `writer.py:build_hashtags_block()` 完全重复。

**修复方案**: 导入并调用 `build_hashtags_block(tags, lang, hs.model, "workflow", platform)`

---

## 12. 🟡 server.py:1052 — 路径遍历漏洞

**文件**: `D:\0703\ai-toolbox\work\server.py:1052`  
**严重级别**: Medium  
**类别**: security

**问题**: `Path(req.dir.strip())` 接受任意文件系统路径，无白名单限制。

**修复方案**: 限制 dir 到预设基础目录 (如 `static/` 或 `generated/`)

---

## 13. 🟡 state.py:49 — DB schema DEFAULT 7，Python 代码为 8

**文件**: `D:\0703\ai-toolbox\work\modules\orchestrator\state.py:49`  
**严重级别**: Medium  
**类别**: correctness

**问题**: CREATE TABLE `total_steps INTEGER DEFAULT 7` 与 `__init__` 的 `self.total_steps = 8` 不一致。绕过 Python 层的 DB 读取得 7。

**修复方案**: 修改 schema DEFAULT 为 8

---

## 14. 🟢 config.py:40 — frozenset 迭代顺序不确定

**文件**: `D:\0703\ai-toolbox\work\modules\hashtag_enricher\enricher\config.py:40`  
**严重级别**: Low  
**类别**: correctness

**问题**: `always_include` 是 frozenset，迭代顺序依赖 Python 哈希随机化 (PYTHONHASHSEED)，每次重启服务后多个 always_include 标签顺序变化。

**修复方案**: 改用 list 或 tuple 保持插入顺序

---

## 15. 🟢 config.py:62 — 重复的 prompt 模板

**文件**: `D:\0703\ai-toolbox\work\modules\hashtag_enricher\enricher\config.py:62-128`  
**严重级别**: Low  
**类别**: simplification

**问题**: `prompt_detect_and_generate` 和 `prompt_generate` 包含重复的少量示例、标签规则和输出格式说明，维护时可能不同步。

**修复方案**: 提取共享的规则和示例到独立常量

---

## 追加: Sweep 发现 (Phase 3)

### 16. ⛔ engine.py:417 — P0 已在上方详述

### 17. 🟡 state.py:320 — to_dict() 在损坏的 hashtags_json 上崩溃

**文件**: `D:\0703\ai-toolbox\work\modules\orchestrator\state.py:320`  
**类别**: correctness

**问题**: `json.loads(self.hashtags_json)` 仅由 truthiness 守卫保护。若字段含损坏/非 JSON 内容，`json.JSONDecodeError` 无处理。其他 JSON 字段 (keyframes_json 等) 有 `json.loads(..., "[]")` 安全回退，但 hashtags_json 没有。

**修复方案**: `json.loads(self.hashtags_json or "null")` 或在 try/except 中包裹

### 18. 🟢 config.py:134 — validate_tag_budget() 从未被调用

**文件**: `D:\0703\ai-toolbox\work\modules\hashtag_enricher\enricher\config.py:134`  
**类别**: simplification

**问题**: `validate_tag_budget()` 旨在验证 max_tags + always_include 适配平台硬限制，但从未被调用。仅有一处注释引用它。违规在下游默默处理 (截断)。

**修复方案**: 在 `_HashtagSettings.__init__()` 末尾调用，或在删除前保留供未来使用。当前为死代码。

---

## 修复优先级

```
修复顺序:
1. #1  Pydantic null 崩溃 — 影响所有 API 调用者
2. #7  copy_text.strip() None 崩溃 — 影响所有含空记录的工作流
3. #2  status 回退 — 破坏已完成工作流的状态
4. #5  httpx.Client 线程安全 — 并发场景崩溃
5. #4  total_steps 默认值 — 旧工作流显示错误
6. #3  time.localtime() 时区错误 — 时间戳数据损坏
7. #6  硬编码 lang/platform — 非中文/非 YouTube 场景错误
8. #8  #9  #10  前端和健壮性修复
9. #11 #15 代码质量清理
```
