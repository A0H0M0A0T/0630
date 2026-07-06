# README — 项目文档

工作规则见 CLAUDE.md（自动注入），任务规划见 TASK.md，模块映射见 PROJECT_MAP.md。

## 工作区概览

这是一个 AI 辅助短视频生产与社交媒体自动化的多项目工作区，在 `D:\0703\` 下包含三个独立子项目：

| 目录 | 技术栈 | 用途 |
|-----------|---------|---------|
| `ai-toolbox/` | FastAPI + React 19 + SQLite | **主项目** — AI 短视频广告全链条生成 |
| `social-auto-upload-main/` | Flask + Vue 3 + Playwright | 多平台视频发布自动化 |
| `TrendRadar-master/` | Python + SQLite + LiteLLM | 热点新闻聚合分析与多渠道推送 |

## 环境

- **操作系统:** Windows 10 Pro，Shell 为 Git Bash（POSIX sh 语法）
- **Python 包管理器:** `uv`（推荐），也可用 `pip`（venv）
- **Node.js:** 可用于前端项目
- **Python 版本要求:** `>=3.10`（social-auto-upload），`>=3.12`（TrendRadar）
- **⚠️ 根目录 `model_config.py` 和 `ai-toolbox/work/modules/tishici/ai_client.py` 包含硬编码 API 密钥 — 切勿提交到版本控制**

---

# ai-toolbox/ — AI 短视频广告全链条生成（主项目）

## 项目定位

为 S101 苦荞精酿啤酒自动生成短视频广告素材。核心流程：输入产品图 → AI 编排剧情分镜 → GPT Image-2 生成四宫格素材图 → AI 评分 → 生成口播文案 → 组装最终视频提示词 → 提交视频模型生成 → 标签生成。全流程 8 步，由 `WorkflowEngine` 在后台线程中驱动。

## 启动应用

```bash
cd ai-toolbox/work

# 前端开发 (Vite + React + Tailwind CSS)
npm run dev                    # Vite dev server

# 后端 (FastAPI, 端口 8000)，同时挂载 dist/ 静态文件
python server.py               # → http://localhost:8000
```

启动时 `server.py` 会自动通过 PowerShell 查端口占用并 taskkill 清理旧的 `server.py` 进程。

## 项目文件结构

```
ai-toolbox/
├── work/                                    # ← 主工作目录
│   ├── server.py                            # FastAPI 后端（~1234 行），全部 REST API 注册
│   ├── model_config.py                      # AI 模型配置（独立的本地副本）
│   ├── auth.db                              # 用户认证 SQLite (users + sessions 表, PBKDF2 密码哈希)
│   ├── workflows.db                         # Workflow 状态+事件 SQLite (workflows + workflow_events 表)
│   ├── history.db                           # 图像识别历史 SQLite (history 表)
│   ├── package.json                         # React 19 + Vite 6 + Tailwind 4 + Motion + lucide-react
│   ├── vite.config.ts                       # Vite 配置 (host 0.0.0.0, proxy none)
│   ├── tsconfig.json                        # TypeScript 5.8 配置
│   ├── index.html                           # 开发模式入口
│   │
│   ├── src/                                 # React 前端源码 (16 个文件)
│   │   ├── main.tsx                         # ReactDOM.createRoot 入口
│   │   ├── App.tsx                          # 主组件 (~319 行): Tab导航, 认证, 共享状态管理
│   │   ├── types.ts                         # 全部 TS 类型定义 (~264 行)
│   │   ├── index.css                        # Tailwind 入口
│   │   ├── api/
│   │   │   ├── client.ts                    # HTTP 客户端: apiUrl(), requestJson<T>(), ApiError
│   │   │   ├── auth.ts                      # 认证: register/login/logout/getCurrentUser
│   │   │   ├── services.ts                  # 非 workflow 服务: prompt/image/recognition/copywriting
│   │   │   └── workflow.ts                  # Workflow API: start/status/result/poll/continue/regenerate
│   │   ├── workflowDiagnostics.ts           # 诊断工具: 步骤状态渲染, 日志行构建, 诊断文本生成
│   │   ├── workflowDiagnostics.test.ts      # 诊断逻辑单元测试
│   │   └── components/
│   │       ├── AuthPage.tsx                 # 登录/注册页 (~146 行)
│   │       ├── HandDrawnTab.tsx             # AI 绘图工作区 (~1286 行, 最大组件)
│   │       ├── ImageRecognitionTab.tsx      # AI 识图 (~335 行)
│   │       ├── CopywritingTab.tsx           # AI 文案 (~236 行)
│   │       ├── LyricMatchingTab.tsx         # AI 词牌匹配 (~319 行, 已构建但未挂载到 App)
│   │       └── WorkflowPage.tsx             # 短视频导演台 (~989 行, 第二大)
│   │
│   ├── modules/                             # 后端流水线模块
│   │   ├── orchestrator/
│   │   │   ├── engine.py                    # WorkflowEngine (~1578 行): 8步流水线编排
│   │   │   └── state.py                     # WorkflowState + DB (~371 行): 状态持久化
│   │   ├── storyboard/
│   │   │   ├── generator.py                 # 剧情生成 (~175 行): 调 LLM 输出【剧情概述】【场景】【分镜】
│   │   │   ├── prompts.py                   # 三大类 system prompt (~158 行): 趣味性/休闲性/正常性
│   │   │   └── scene_pool.py                # 19 个室内场景词列表 (~26 行)
│   │   ├── keyframe/
│   │   │   └── extractor.py                 # 分镜→生图提示词 (~129 行): 4分镜合并为单段四宫格 prompt
│   │   ├── scorer/
│   │   │   └── scorer.py                    # GPT-4o Vision 评分 (~113 行): 5 维度打分
│   │   ├── video_prompt/
│   │   │   └── assembler.py                 # 最终视频提示词组装 (~267 行): 5段模板格式
│   │   ├── video_generation/
│   │   │   └── client.py                    # 视频生成 Provider 壳 (~297 行): Plug-in 架构
│   │   ├── tishici/
│   │   │   ├── ai_client.py                 # 多模型 AIClient: 火山引擎+DeepSeek, 50+场景/人群/风格/动作选项
│   │   │   └── database.py                  # PromptDatabase + SimilarityChecker (SQLite + N-gram)
│   │   ├── tupian/
│   │   │   ├── services/recognize.py        # GPT-4o Vision 识图: _call_vision_api()
│   │   │   ├── database/db.py               # 识图历史 SQLite (init_db/save_record/get_all_records)
│   │   │   ├── models/schemas.py            # Pydantic 模型
│   │   │   └── logger.py                    # 日志
│   │   ├── wenan/
│   │   │   ├── generator.py                 # 文案批量生成 (~732 行): trigram去重+accept-reject流水线
│   │   │   └── 介绍.txt                     # 产品介绍参考文本
│   │   └── hashtag_enricher/
│   │       └── enricher/
│   │           ├── config.py                # Bridge 到 model_config.WENAN
│   │           ├── llm.py                   # LLM 调用 (~428 行): detect_language/generate_hashtags/detect_and_generate
│   │           ├── reader.py                # 视频元数据解析: resolve_meta() + VideoMeta
│   │           ├── writer.py                # JSON 输出: build_hashtags_block() + atomic write
│   │           ├── postprocess.py           # 标签后处理: validate_and_filter + 平台限流
│   │           └── logger.py                # RotatingFileHandler 日志
│   │
│   ├── static/
│   │   ├── product/                         # 用户上传+默认产品图
│   │   ├── video/                           # 参考数据: 公司产品数据.txt, 模板视频分析结果/, 模板图分析结果/
│   │   └── generated/                       # AI 生成图片输出
│   └── dist/                                # Vite 构建产物 (生产模式由 server.py 挂载)
│
├── alxuanchuan/                             # 独立 Node.js 服务器 (Express + Gemini)
│   ├── server.ts                            # Express 后端 (~532 行): 6 个 Gemini API 路由
│   ├── src/                                 # React 前端 (与 work/ 同构但用 Gemini 而非 DeepSeek)
│   ├── package.json                         # @google/genai + React 19 + Vite 6
│   └── .env.example                         # GEMINI_API_KEY
├── uv.lock
├── readme.md                                # 产品需求文档（中文, 约 286 行，⚠️ 含 D:\0000 等旧绝对路径，待核实）
├── PROJECT_MAP.md                           # 模块到文件的映射与调试指南
├── .agents/
│   └── agent.md                             # Agent 行为规则（最小改动、不运行测试、不写长篇汇报）
└── .plan.md
```

## 8 步流水线核心架构

### 状态管理 (`modules/orchestrator/state.py`)

- **Workflows 表**: 42 个字段（id, user_id, story_type, gender, scene, status, current_step, step_index, total_steps, product_image, model, audience, weather, style_param, action_param, extra, aspect_ratio, storyboard_text, keyframes_json, image_prompts_json, image_urls_json, scores_json, copy_text, video_prompt, video_status, video_job_id, video_url, video_error, hashtags_json, error_message, created_at, updated_at）
- **WorkflowEvents 表**: 15 个字段（id, workflow_id, step_index, step_name, event_type, message, duration_ms, error_type, error_traceback, input_summary, output_summary, created_at）
- SQLite WAL 模式
- `WorkflowState(workflow_id)` 从 DB 加载; `WorkflowState()` 创建新状态（`wf_` 前缀 + uuid4 hex 12位）
- `_safe_json_loads()` 防御式 JSON 解析，损坏时返回 None
- `_trim_text()` 所有文本字段写入前截断（event message 1000字, error_type 200字, traceback 8000字）
- 数据库迁移: ALTER TABLE 逐个添加缺失列，`OperationalError` 忽略（列已存在）

### Step 1 — 剧情分镜生成 (`modules/storyboard/`)

- `generate_storyboard(story_type, gender, scene, audience, weather, style, action, extra)` → `{story_type, gender, scene, storyboard_text, overview, keyframes}`
- 调 DeepSeek (`model_config.WENAN`), temperature=0.9, max_tokens=2048
- 固定四格动作序列: 1产品放木桌(带房间背景+零食杂物) → 2手从背包拿出(背包口/内衬可见) → 3手拉开银色拉环(保留木桌和背景) → 4普通倒一杯(泡沫自然)
- System prompt 三大类（`STORY_PROMPTS` 字典）：
  - 趣味性: 脑洞反转
  - 休闲性: 生活气息+杂乱桌面
  - 正常性: 专业带货展示
- System prompt 包含约 30 行硬约束: 产品身份锁定(黄色铝罐+黑色S+银色拉环)、禁用词列表(绿色罐/玻璃瓶/SIOI/苦苣/夜市/露营/嘴唇/喝一口)、无人露脸约束、广告节奏规则
- 解析逻辑: 正则提取 `【剧情概述】`/`【场景】`/`【性别】`/`【分镜1~4】`，`_extract_field()` 支持 `【field】value` 和 `field：value` 两种格式
- `_normalize_keyframe_text()` 处理 "镜头描述 + 运镜 + 构图" 占位符
- 50+ 随机因素: `SCENE_OPTIONS` (50+场景如大学食堂/烧烤大排档等), `AUDIENCE_OPTIONS` (3类人群比例), `WEATHER_OPTIONS`, `STYLE_OPTIONS`, `ACTION_OPTIONS`, `random_person()`
- 相似度检查: trigram Jaccard >60% 自动重试最多 2 次

### Step 2 — 关键帧生图提示词 (`modules/keyframe/extractor.py`)

- `extract_keyframe_prompts(storyboard_text, keyframes, gender, aspect_ratio, extra)` → `list[str]` (单元素列表)
- 将 4 个分镜合并为 1 段四宫格提示词: `"1024x1536竖版四宫格，每格约512x768 2:3竖版手机照片，左上方格=分镜1..."`
- 性别提示注入: "女性手部入镜（美甲/纤细手型）" 或 "男性手部入镜（骨感手型/手表）"
- Fallback 文本 (~12行) 硬编码，当 LLM 返回空时使用
- `KEYFRAME_SYSTEM` 常量 (~34行) 包含: 产品身份锁定、无人露脸约束、四宫格布局规则、场景规则、负面约束列表
- `build_image_prompt_pack()`: 在提示词外再包装 format 模板

### Step 3 — 图片生成: Canvas+Mask 方式 (`engine.py:_generate_image()`)

**Placement Planner** (`_plan_product_poses()`):
- 根据分镜动作关键词（倒酒/开罐/手持/放在/特写/展示）确定每格产品的 rotation/scale/offset
- 不可能姿势（碰杯）降级为安全展示姿势
- 返回 `(poses[], conflicts[], extra_scene_hint)`

**Build Canvas** (`_build_product_canvas()`):
- PIL 将产品 PNG resize 到 400px 宽后粘贴到 1024x1536 透明画布的 4 个象限
- 每格按 pose 旋转/缩放/偏移后再粘贴
- Mask 反向生成: 产品区=白(保护)，背景区=黑(生成)
- Mask 膨胀 15px（ImageFilter.MaxFilter）

**API 调用**:
- POST `{base_url}/v1/images/edits`
- multipart/form-data: image (canvas.png) + mask (mask.png) + prompt (scene_prompt) + model="gpt-image-2" + size="1024x1536" + quality="low" + n=1
- Scene prompt (~50行) 包含: CRITICAL ASSET RULES（容器类型/颜色/标签/拉环/品牌约束）、BRAND CONSISTENCY（只能有S101一个品牌）、STYLE RULES（手机随手拍/低中像素/木头桌子/杂乱背景）
- `verify=False, proxies={"http": None, "https": None}`（禁用系统代理）
- 最多 3 次重试

**产品描述缓存**:
- `_analyze_product_image()` 直接返回 `_SAFE_PRODUCT_DESC` 硬编码描述（黄色铝罐+黑色S+银色拉环+1L+10°P），不再信任 Vision API 的 OCR
- 原因: 历史上出现过 SIOI/si01/苦苣/绿色罐/玻璃瓶等幻觉

### Step 3 — 品牌保护三层防线

1. **Sanitization Map** (`_WORKFLOW_SANITIZE_MAP`, ~60 组替换规则): 自动替换 "玻璃瓶"→"黄色铝制高罐易拉罐"、"绿色罐"→"黄色铝罐"、"瓶身"→"罐身"、"苦苣"→"苦荞"、"SIOI"→"S101"、"不上头"→"口感绵柔"、"三高"→"聚会小酌" 等
2. **Banned Words** (`storyboard/prompts.py`): System prompt 中明确禁止
3. **Output Pollution Detection**: `_OUTPUT_POLLUTION_PATTERNS` 检查 + `_sanitize_workflow_outputs_or_raise()` 发现污染词抛异常

### Step 4 — AI 评分 + 闸门 (`modules/scorer/scorer.py`)

- `score_image(image_url, keyframes)` → `{score, reason, dimensions}`
- 调 GPT-4o Vision (`model_config.TUPIAN` → yunwu.ai → gpt-4o)，temperature=0.3
- 5 维度各 1-5 分: scene_match / product_visibility / realism / composition / style_consistency
- 评分等级: 总分 22+→超高, 18+→高, 13+→中, 8+→低, <8→超低
- 解析: 优先 JSON 解析 → Markdown fence 处理 → 正则兜底
- **闸门逻辑**: 任何一格评分"低"或"超低" → status=`needs_review`，流水线暂停
- 前端选择:
  - `/api/workflow/continue/{id}`: 从 Step 5 恢复（保留当前图片）
  - `/api/workflow/regenerate/{id}`: 清空 scores+image_urls，从 Step 3 重来

### Step 5 — 口播文案生成 (`engine.py:_generate_copy()`)

- 调 DeepSeek (`model_config.WENAN`), temperature=0.85, max_tokens=300
- System prompt (~80行) 含完整合规规则:
  - 合规红线: 禁止医疗功效(降血压/降血糖/降血脂等)、禁止饮后承诺(不上头/不头疼等)、禁止疾病相关(三高/糖尿病等)、禁止健康暗示
  - 写法规范: 50-100字、口语化、短句多、反问句/直呼/场景画面开头
  - 严禁写法: 禁止文艺腔(润到心坎/夕阳/黄昏/诗意)、禁止假大空(别整那些虚的)、禁止抽象形容词堆砌、禁止带货八股腔(家人们/yyds/绝绝子)、禁止散文句式
  - 参考范例 ×2
  - CTA 结尾必须
- 三重后处理:
  1. Banned words 检测（~30词），命中则用安全 fallback
  2. 字数检查（<20 字用 fallback）
  3. CTA 关键词检测（15个关键词），没有则追加"想尝鲜的点我头像进主页看看！"
- 与历史记录 trigram 相似度检查（60%），超标最多重试 2 次

### Step 6 — 最终视频提示词组装 (`modules/video_prompt/assembler.py`)

- `assemble_video_prompt(storyboard_text, keyframes, scores, copy_text, gender, image_urls)` → `str`
- 模板格式：《帮我生成一个视频：(1)素材图解析 → (2)排版编排剧情 → (3)文案诵读 → (4)参考资料约束 → (5)视频模型执行要求》
- (1) 素材图解析: 说明是 1 张四宫格（非 4 张独立图），左上=图1...右下=图4，每格约 2:3 竖版
- (2) 排版编排剧情: `_inject_image_refs()` 自动注入 `@图N` 引用
- (3) 文案诵读: "第一秒开始，{男女声}旁白：\"{文案}\" 最后一秒人声结束"
- (4) 参考资料约束: 产品卖点只使用安全描述 + 模板视频节奏参考 + S101 素材图风格参考
- (5) 视频模型执行要求: 竖屏9:16, 15秒, 前3秒钩子, ASMR音效, 产品外观硬约束, 画质要求
- 完整的 `_SANITIZE_MAP` (~60 条): 与 `engine.py` 的 `_WORKFLOW_SANITIZE_MAP` 重复但独立维护

### Step 7 — 视频生成提交 (`modules/video_generation/client.py`)

- **Plug-in 架构**: 只需重写 `_submit_to_provider()` 和 `_poll_provider_status()` 两个私有函数
- 环境变量驱动: `VIDEO_PROVIDER`/`VIDEO_API_URL`/`VIDEO_API_KEY`/`VIDEO_MODEL`
- `VideoGenerationConfig` 不可变 dataclass，`is_configured` 属性检查 provider+api_url+api_key 都非空
- Shell 实现: 当前返回 `video_status="not_configured"`
- 公共接口不可变: `submit_video_generation(video_prompt, image_urls)` 和 `check_video_generation_status(video_job_id)` 的签名和返回 shape 已冻结
- 返回 shape 契约: `{video_status, video_job_id, video_url, video_error}`
- 标准 video_status: not_configured → submitted → running → completed/failed

### Step 8 — 发布标签生成

- 从 copy_text + storyboard_text 提取 topic，调用 `modules/hashtag_enricher/enricher/llm.py`
- Platform 固定 "youtube"，language 固定 "Chinese"
- 生成结果序列化为 `hashtags_json` 字段存入 DB

## WorkflowEngine 核心机制 (`engine.py`)

- `_engines: dict` 内存注册表，用于状态轮询和 stop 控制
- `_stop_flag: threading.Event` 可中断流水线
- 每一步:
  1. `_start_step(step_index)` → 更新 DB status+step，记录 workflow_events
  2. 执行生成逻辑
  3. `_finish_step(step_index, started_at, output_summary)` → 记录 duration_ms + output
  4. 异常时 `_fail_step()` → 记录 error_type + error_traceback + 状态 → failed
- `start_workflow(state)` → 存 DB → 创建 engine → `threading.Thread(target=engine.run, daemon=True).start()`
- `continue_workflow_from_review()` → 加载 needs_review 状态 → 从 Step 5 开始
- `regenerate_workflow_image()` → 清空 scores+image_urls → 从 Step 3 开始
- `stop_workflow()` → 设置 stop_flag → 标记 cancelled → 记录 event

## 跨模块导入机制

- `server.py` 用 `sys.path.insert` 动态注入子模块路径
- 导入顺序关键: `tishici` 必须在 `tupian` 之前导入（两者都有 `database` 模块冲突）
- `tishici` 的 `database.py` 注册为 `'database'` 模块名，使用时立即 `del sys.modules['database']` 清除

## 文案批量生成 (`modules/wenan/generator.py`)

- 4 种文案类型: 15秒带货口播 / 朋友圈/社群 / 小红书种草 / 产品详情/公众号
- 多样性池: 8 种 hook 风格 × 16 种角度 × 10 种 CTA × 7 种 persona
- 去重引擎: trigram Jaccard 相似度，阈值 40%
- Accept-Reject 流水线: 主循环 pending → 并发生成候选 → 主线程 accept/reject → 失败重试（最多 5 次）
- 内容风控: `_CONTENT_BLOCK_RULES` (~200行，regex+literal 双层)，拦截类别: 饮后承诺/养生暗示/违规功效/假体验/编造数量
- `find_copy_issues()` 主检查函数，含文案类型特定检查（口播超 100 字/朋友圈 28 天亮红灯）
- 多样性池自检: `_check_diversity_pool_issues()` 确保池本身不命中风控规则
- API 调用: 指数退避重试（最多 4 次，不可重试: invalid_api_key/authentication/insufficient_quota）
- 输出: JSONL 增量落盘 + CSV 导出（UTF-8 BOM, Excel 友好）

## 图像识别模块 (`modules/tupian/`)

- `services/recognize.py`: `recognize_by_url(image_url)` 和 `recognize_by_upload_data(file_data, filename)`
- 模型: GPT-4o Vision via yunwu.ai，temperature=0.3
- `RecognizeError` 异常: message + status_code
- `ANALYSIS_PROMPT` (~15行): 引导 AI 分析主体/画面/背景/产品参数/整体意图/风格总结
- `database/db.py`: SQLite 单表 history (id, image_source, image_thumb, result_json, created_at)
- 分页查询: `get_all_records(page, page_size)` → `(items, total)`

## 提示词生成模块 (`modules/tishici/`)

- `AIClient(model_key)`: 支持 4 种模型（main/model2/model3=火山 ark-code-latest, deepseek4=DeepSeek V4-Pro）
- `generate_prompt(params, temperature, seed)`: 调用 OpenAI 兼容 API
- 50+ 随机选项: `SCENE_OPTIONS` (50+场景), `AUDIENCE_OPTIONS` (3类), `WEATHER_OPTIONS`, `STYLE_OPTIONS`, `ACTION_OPTIONS`, `random_person()`
- `PromptDatabase`: SQLite prompts 表 (id, prompt, created_at, params, copy_count)，支持搜索/分页/排序/批量删除/复制计数
- `SimilarityChecker`: 双重相似度（30% token overlap + 70% trigram n-gram），`find_max_similarity()` 返回最高分

## 前端架构

### Tab 管理
- 所有 Tab 保持挂载（CSS `display:none`），不卸载，保证异步操作不中断
- Tab 切换保护: 生成中途切换弹出确认对话框（`pendingSwitch` + `confirmSwitch`/`cancelSwitch`）
- `generatingTab` 跟踪哪个 Tab 正在生成，header 中对应按钮显示黄色脉冲点
- 跨 Tab 数据流: HandDrawnTab → CopywritingTab（导出文案）、ImageRecognitionTab → HandDrawnTab（导入识别因素）

### 组件详解
- **HandDrawnTab**（1286行）: 6个创意因素输入+3个预设(精酿麦浪/冰爽夏日/赛博蒸汽)+比例/质量选择+3步流水线(生成提示词→生成图片→反编译视觉)+提示词历史面板(搜索/排序/批量删除/复制计数)+批量生图(1-20张)+色彩色板+反编译蓝图+导出到文案
- **WorkflowPage**（989行）: 配置面板(剧情类型/性别/场景下拉+产品图上传+高级参数折叠)+运行控制(启动/停止)+300次轮询(1.5s间隔)+结果展示(视频播放器/视频URL回填/标签/图片/关键帧网格/评分/生图prompt/文案/剧情文本)+历史面板+诊断日志覆盖层+needs_review闸门处理(继续/重新生成按钮)
- **ImageRecognitionTab**: 拖拽上传区+分析按钮+结果6因素卡片+导入回 HandDrawnTab
- **CopywritingTab**: 平台选择(抖音15s/小红书/微信)+内容输入+手机预览+复制按钮
- **LyricMatchingTab**（319行, 未挂载在 App.tsx 中）: 诗配艺术海报+标题选择+标签徽章

### API 层
- `api/client.ts`: 所有请求经过 `requestJson<T>(path, init?)` → 自动带 `Authorization: Bearer <token>` header → 自动 JSON 解析 → 非成功状态抛 `ApiError`
- `api/workflow.ts`: `pollWorkflowUntilDone(workflowId, onStatus?, maxAttempts=300, intervalMs=1500)` — 复杂的轮询逻辑，含 409 竞态重试和失败时部分结果获取
- `api/services.ts`: `pollPromptUntilDone()` + `runCopyJob()` — 异步任务轮询模式

### 诊断工具 (`workflowDiagnostics.ts` + `workflowDiagnostics.test.ts`)
- `getWorkflowStepRows()`: 根据 activeStep + events + failedEvent 渲染 8 步骤状态行
- `buildWorkflowDiagnosticText()`: 生成可读的诊断文本，**关键安全防护** — failedEvent 存在时强制覆盖 status="failed"（即使调用方传错了）
- `getWorkflowLogRows()`: 将 WorkflowEvent[] 映射为日志行（含 duration 格式化）
- 单元测试: 纯断言风格，验证步骤状态分配、诊断文本生成、回归测试（failedEvent 覆盖逻辑）
- `shouldRefreshWorkflowDiagnostics(isOpen, workflowId)`: 仅在诊断面板打开且有 workflowId 时返回 true

## REST API 完整列表

| 方法 | 路由 | 功能 |
|------|------|------|
| POST | `/api/auth/register` | 注册 (username≥2, password≥4) |
| POST | `/api/auth/login` | 登录 → token (PBKDF2, 7天过期) |
| GET | `/api/auth/me` | 验证 token 返回用户信息 |
| POST | `/api/auth/logout` | 删除 session |
| POST | `/api/workflow/start` | 启动 8 步 workflow (story_type/gender/scene/product_image/高级参数) |
| GET | `/api/workflow/status/{id}` | 查询进度 (status/current_step/step_index/error_message) |
| GET | `/api/workflow/logs/{id}` | 获取事件日志 (limit=200, 最多 500) |
| GET | `/api/workflow/history` | 列出有生成图片的历史记录 (limit=20, 最多 100) |
| GET | `/api/workflow/result/{id}` | 获取完整结果 (completed/failed/needs_review) |
| POST | `/api/workflow/stop/{id}` | 中止运行中的 workflow |
| GET | `/api/product-images` | 列出 static/product/ 中的产品图 |
| POST | `/api/workflow/upload-product` | 上传产品参考图 (.png/.jpg/.jpeg) |
| POST | `/api/workflow/video-status/{id}` | 刷新视频生成任务状态 (调 provider) |
| POST | `/api/workflow/video-url/{id}` | 手动回填视频地址 |
| POST | `/api/workflow/continue/{id}` | needs_review → 从 Step 5 继续 |
| POST | `/api/workflow/regenerate/{id}` | needs_review → 从 Step 3 重新生成 |
| GET | `/api/gpt-image/config` | 返回 GPT Image API 配置 |
| POST | `/api/gpt-image/generate` | 调用 GPT Image-2 生成图片 (prompt/aspectRatio/n/quality) |
| GET | `/api/image/config` | 返回图像识别 API 配置 |
| GET | `/api/image/health` | 测试 GPT-4o Vision 连接 |
| POST | `/api/image/recognize/url` | 通过 URL 识图 |
| POST | `/api/image/recognize/upload` | 通过文件上传识图 |
| POST | `/api/image/recognize/batch` | 批量 URL 识图 (信号量 MAX_CONCURRENCY=5) |
| POST | `/api/image/recognize/batch/upload` | 批量文件识图 (最多 MAX_BATCH_SIZE=20) |
| GET | `/api/image/history` | 分页查询识图历史 (需 X-App-Key) |
| GET | `/api/image/history/{rid}` | 获取单条识图记录 |
| DELETE | `/api/image/history/{rid}` | 删除识图记录 |
| GET | `/api/prompt/config` | 返回模型列表+场景/人群/天气/风格/动作选项 |
| POST | `/api/prompt/generate` | 开始批量提示词生成 (后台线程, 5 次去重重试) |
| POST | `/api/prompt/stop` | 停止批量生成 |
| GET | `/api/prompt/status` | 轮询生成进度 |
| GET | `/api/prompt/history` | 分页查询提示词历史 (搜索/排序) |
| GET | `/api/prompt/history/{pid}` | 获取单条提示词 |
| DELETE | `/api/prompt/history/{pid}` | 删除提示词 |
| POST | `/api/prompt/history/batch-delete` | 批量删除提示词 |
| POST | `/api/prompt/history/{pid}/copy` | 标记已复制 (copy_count++) |
| POST | `/api/prompt/generate-single` | 单图提示词生成 (TS 前端全链条专用) |
| GET | `/api/copy/types` | 返回 4 种文案类型 |
| GET | `/api/copy/health` | 文案服务健康检查 |
| POST | `/api/copy/generate` | 开始批量文案生成 (ThreadPoolExecutor, cancel_event) |
| POST | `/api/copy/stop` | 取消生成 |
| GET | `/api/copy/status` | 轮询生成进度 |
| GET | `/api/copy/result` | 获取生成结果 (含 avg_similarity/max_similarity/job_file) |
| GET | `/api/copy/jobs` | 列出历史任务 |
| GET | `/api/copy/jobs/{prefix}/csv` | 下载 CSV 导出 |
| GET | `/api/copy/jobs/{prefix}/jsonl` | 下载 JSONL 导出 |
| GET | `/api/scene-pool` | 返回 19 个室内场景列表 |
| GET | `/api/hashtag/config` | 返回标签生成配置 (3 平台 + 限制 + 模型) |
| POST | `/api/hashtag/generate` | 标签生成 (topic 模式 / dir 扫描模式, 路径遍历防护) |
| GET | `/api/health` | 健康检查 |

---

# alxuanchuan/ — Express + Gemini 独立服务器

- 与 `ai-toolbox/work/` 功能同构但使用 **Google Gemini** 而非 DeepSeek+GPT
- Express 端口 3000，20MB body limit
- 6 个端点: `/api/generate-prompt` (gemini-3.5-flash), `/api/generate-image` (gemini-3.1-flash-lite-image), `/api/deconstruct-visual`, `/api/recognize-image`, `/api/match-lyrics`, `/api/explosive-copywriting`
- 所有端点用 structured JSON schema 约束输出
- PRESET_FALLBACKS: 3 个中文主题预设，各含 Unsplash 图片 URL
- 前端 4 Tab: hand-drawn/recognition/lyrics/copywriting（无 workflow Tab）
- 与 ai-toolbox/work/src 共享相同组件结构和类型定义

---

# social-auto-upload-main/

多平台视频发布自动化。**有独立的详细 CLAUDE.md** — 参见 `social-auto-upload-main/CLAUDE.md`。

**快速启动:**
```bash
cd social-auto-upload-main
pip install -r requirements.txt && playwright install chromium
python db/createTable.py                            # 初始化 SQLite
python sau_backend.py                               # Flask → :5409
cd sau_frontend && npm install && npm run dev       # Vue 3 + Element Plus → :5173
sau douyin login --account <name>                   # CLI 登录
sau douyin upload-video --account <name> --file <video> --title <title>
```

## 项目文件结构

```
social-auto-upload-main/
├── sau_backend.py                    # Flask 后端（~724 行）: 20+ REST 路由
├── sau_cli.py                        # CLI 入口（~1022 行）: 6 个平台的 login/check/upload 子命令
├── conf.example.py → conf.py         # 配置: BASE_DIR, LOCAL_CHROME_PATH, HEADLESS, DEBUG, XHS_SERVER, YT_PROXY
├── pyproject.toml                    # Python >=3.10,<3.13, patchright 1.58.2
├── Dockerfile                        # 两阶段构建: Node builder + Python 3.10 runtime
├── db/
│   └── createTable.py               # SQLite schema: user_info (4列) + file_records (5列)
├── uploader/                         # ← 新代代码（优先使用）
│   ├── base_video.py                # BaseVideoUploader: 视频/图片验证, 发布时间验证(MIN 2h ahead)
│   ├── douyin_uploader/main.py      # DouYinVideo + DouYinNote (867行): cookie_auth(3重试), QR生成, 定时/商品链接/封面
│   ├── ks_uploader/main.py          # KSVideo + KSNote (735行): 快手图文/视频, ant-design DatePicker
│   ├── xiaohongshu_uploader/main.py # XiaoHongShuVideo + XiaoHongShuNote (767行): 话题标签(max10), 原创声明
│   ├── tencent_uploader/main.py     # TencentVideo (1018行, Note未实现): 短标题, 合集, 原创声明(多路径)
│   ├── youtube_uploader/main.py     # YouTubeVideo (334行): 5步向导, contenteditable填充, 缩略图, playlist
│   ├── bilibili_uploader/runtime.py # biliup CLI管理 (191行): 自动下载/更新 Rust 二进制
│   ├── baijiahao_uploader/main.py   # BaiJiaHaoVideo (507行): 百家号, AI成片实验功能
│   ├── tk_uploader/main.py          # TiktokVideo Firefox版 (268行): page.pause() 手动登录
│   ├── tk_uploader/main_chrome.py   # TiktokVideo Chrome版 (310行): 缩略图, 语言切换, video ID提取
│   ├── tk_uploader/tk_config.py     # Tk_Locator: iframe selector
│   ├── xhs_uploader/main.py         # XHS API签名 (59行): Playwright执行 window._webmsxyw()
│   └── xhs_uploader/xhs_login_qrcode.py # xhs package QR登录 (34行)
├── utils/
│   ├── base_social_media.py         # set_init_script(context): 注入 stealth.min.js (+ 平台常量)
│   ├── browser_hook.py              # get_browser_options(): 反检测浏览器参数
│   ├── constant.py                  # TencentZoneTypes枚举(29类), VideoZoneTypes枚举(完整的B站tid映射)
│   ├── files_times.py               # generate_schedule_time_next_day(): 定时发布时间表生成
│   ├── log.py                       # loguru: 9个平台独立logger (rotation=10MB, retention=10天)
│   ├── login_qrcode.py              # QR: save_data_url_image, decode_qrcode_from_path(OpenCV), print_terminal_qrcode(segno)
│   └── network.py                   # @async_retry 装饰器
├── myUtils/                          # ← 旧代代码（遗留）
│   ├── auth.py                      # 4个 cookie_auth_*(): 同步 Playwright, 单次检查, 泄漏浏览器
│   ├── login.py                     # 4个 *_cookie_gen(): 同步 QR 登录, asyncio.Event等待
│   └── postVideo.py                 # 4个 post_video_*(): 同步封装, 循环文件×账号
├── sau_frontend/src/                 # Vue 3 + Element Plus + Pinia
│   ├── App.vue                      # 侧边栏导航 (Home/Account/Material/Publish/About)
│   ├── Dashboard.vue                # 首页: 账号统计/平台统计/快捷操作卡片
│   ├── AccountManagement.vue        # 账号管理 (1055行): CRUD + SSE QR登录弹窗
│   ├── MaterialManagement.vue       # 素材管理: 拖拽上传+进度条
│   ├── PublishCenter.vue            # 发布中心 (1399行): 多Tab(文件/账号/平台/标题/话题/定时/批量)
│   └── About.vue                    # 关于页
└── skills/                           # Claude Code skills
    ├── douyin-upload/               # sau douyin 命令模板
    ├── kuaishou-upload/             # sau kuaishou 命令模板
    ├── xiaohongshu-upload/          # sau xiaohongshu 命令模板
    └── bilibili-upload/             # sau bilibili --tid --schedule 模板
```

## 两种调用路径

```
Web路径:   POST /postVideo → myUtils/postVideo.py → uploader/*/main.py (UPLOAD CLASSES)
CLI路径:   sau <platform> upload-video → sau_cli.py:dispatch() → uploader/*/main.py (DIRECT)
```

两个路径**不共享 dispatch 逻辑**。修复必须镜像到两处。

## 平台上传器类层次

```
BaseVideoUploader (uploader/base_video.py)
├── DouYinBaseUploader → DouYinVideo, DouYinNote
├── KSBaseUploader → KSVideo, KSNote
├── XiaoHongShuBaseUploader → XiaoHongShuVideo, XiaoHongShuNote
├── TencentBaseUploader → TencentVideo, TencentNote (Note 未实现)
├── YouTubeVideo (直接继承 BaseVideoUploader)
├── BaiJiaHaoVideo
├── TiktokVideo (Firefox/Chrome 两个变体, 独立类层次)
```

每个 Video 类: `__init__(params) → validate_upload_args() → upload(playwright)`，Note 类额外有 `upload_note_content(page)` 方法。

## Playwright 约定

- **库**: `patchright`（Playwright 分支） — 新代 `from patchright.async_api import ...`
- **Stealth**: 每个 context 必须 `await set_init_script(context)` 注入 `utils/stealth.min.js`
- **Cookie**: Playwright `storage_state` JSON，两套存储位置：
  - 新代: `cookies/{platform}_{account_name}.json`
  - 旧代: `cookiesFile/{uuid}.json`
- **QR 登录流**: 导航→提取QR img src(data URL)→终端/文件保存→轮询URL变化→storage_state保存→user_info INSERT
- **Browser cleanup**: `try/finally` 中 `context.close()` + `browser.close()`
- **日志**: 新代用 `_msg(emoji, text)` + per-platform logger (loguru)，旧代用 `print()`

## 平台类型映射

| type | 平台 | 前端名称 | db表 |
|------|------|---------|------|
| 1 | 小红书 | 小红书 | user_info |
| 2 | 视频号 | 视频号 | user_info |
| 3 | 抖音 | 抖音 | user_info |
| 4 | 快手 | 快手 | user_info |

## CLI 使用

```bash
sau <平台> login --account <名称>              # QR 登录
sau <平台> check --account <名称>              # Cookie 有效检查
sau <平台> upload-video --account <名称> \     # 发布视频
  --file <视频路径> --title <标题> \
  [--tags tag1,tag2] [--schedule "YYYY-MM-DD HH:MM"] [--debug]
sau <平台> upload-note --account <名称> \      # 发布图文 (douyin/kuaishou/xiaohongshu)
  --images <图1> <图2> --title <标题> --note <正文>
sau skill install                                # 安装 Claude Code skills
```

平台: `douyin`, `kuaishou`, `xiaohongshu`, `bilibili`, `tencent`, `youtube`

## 关键注意事项

- `daily_times` 参数期望整数小时如 `[6, 11, 14]`，**不是** "HH:MM" 字符串
- `TencentNote` 为 stub（NotImplementedError）
- YouTube: `_fill_editable()` 用 `fill()` 避免触发 contenteditable 的 autocomplete
- Bilibili: 使用 Rust 二进制 `biliup`（自动从 GitHub Release 下载），不走 Playwright
- TikTok Firefox版用 `page.pause()` 手动登录，Chrome版可自动化
- `generate_schedule_time_next_day(total, per_day, times, timestamps, start_days)` — times 是整数小时列表

---

# TrendRadar-master/

热点新闻聚合与分析。**有独立的详细 CLAUDE.md** — 参见 `TrendRadar-master/CLAUDE.md`。

**快速启动:**
```bash
cd TrendRadar-master
pip install -e .
python -m trendradar                        # 主流水线: 爬取→分析→报告→推送
python -m trendradar --doctor               # 环境诊断
python -m trendradar --show-schedule        # 查看当前调度状态
python -m trendradar --test-notification    # 测试全部通知渠道
python -m mcp_server.server                 # MCP stdio 模式
python -m mcp_server.server --http 8080     # MCP HTTP 模式
```

## 项目文件结构

```
TrendRadar-master/
├── pyproject.toml                        # Python >=3.12, 11个依赖 (fastmcp, litellm, boto3, feedparser...)
├── config/
│   ├── config.yaml                       # 主配置 (~501行): 11平台, 3 RSS源, 9通知渠道, AI/存储/调度
│   ├── timeline.yaml                     # 时间线调度方案 (~560行): 4预设+自定义, periods/day_plans/week_map
│   ├── frequency_words.txt               # 关键词组 (空行分隔组, +必需词, !过滤词, /regex/)
│   └── ai_interests.txt                  # AI筛选兴趣描述
├── trendradar/                           # 主应用包
│   ├── __main__.py                       # NewsAnalyzer类 (~1716行): crawl→analysis→report→notify
│   ├── context.py                        # AppContext: 依赖注入中心 (~538行), 消除全局状态
│   ├── core/
│   │   ├── loader.py                     # 配置加载器 (~613行): 20+ 私有loader, YAML+env合并
│   │   ├── config.py                     # 多账号解析: parse_multi_account_config(;分隔)
│   │   ├── frequency.py                  # 关键词解析 (~310行): regex/alias/group匹配
│   │   ├── analyzer.py                   # 统计分析 (~780行): 加权计算/词频统计/platform转换
│   │   ├── data.py                       # 数据读取: read_all_today_titles/detect_latest_new_titles
│   │   └── scheduler.py                  # 时间线调度器 (~432行): periods+day_plans+week_map+once去重
│   ├── crawler/
│   │   ├── fetcher.py                    # DataFetcher: NewsNow API, HTTPS域名校验, 指数退避重试
│   │   └── rss/
│   │       ├── parser.py                 # RSSParser: RSS2.0/Atom/JSON Feed 1.1 三种格式
│   │       └── fetcher.py                # RSSFetcher: 批量抓取, freshness过滤, RSSFeedConfig
│   ├── ai/
│   │   ├── client.py                     # AIClient: LiteLLM封装, 100+供应商, provider/model_name格式
│   │   ├── analyzer.py                   # AIAnalyzer: 5段分析(core_trends/sentiment/signals/rss/outlook)
│   │   ├── filter.py                     # AIFilter: PhaseA标签提取 + PhaseB新闻分类
│   │   ├── filter_pipeline.py            # AIFilterPipeline: 完整流程(extract→update→classify→convert)
│   │   ├── translator.py                 # AITranslator: 批量翻译(编号格式), BatchTranslationResult
│   │   ├── formatter.py                  # 7种频道AI分析渲染器 (markdown/feishu/dingtalk/telegram/html/plain)
│   │   └── prompt_loader.py              # [system]/[user] 分段 prompt 文件加载
│   ├── notification/
│   │   ├── dispatcher.py                 # NotificationDispatcher (~834行): dispatch_all() + 每频道send
│   │   ├── senders.py                    # 9频道发送器 (~1328行): 每频道含分批/header/footer
│   │   ├── splitter.py                   # 消息分批器 (~1872行): 原子news保持, 7格式支持, 区域排序
│   │   ├── batch.py                      # 分批工具: truncate_to_bytes/at_line_boundary/preserving_footer
│   │   ├── renderer.py                   # Feishu/DingTalk专用渲染 (colored font tags, #### headings)
│   │   └── formatters.py                 # Markdown→mrkdwn(Slack), strip_markdown(plain)
│   ├── storage/
│   │   ├── base.py                       # NewsItem/RSSItem/NewsData/RSSData dataclass + StorageBackend抽象
│   │   ├── sqlite_mixin.py               # SQLite操作mixin (~1766行): upsert/rank_history/title_changes/AI filter表
│   │   ├── local.py                      # LocalStorageBackend: output/news/{date}.db + TXT + HTML
│   │   ├── remote.py                     # RemoteStorageBackend: S3(boto3) + batch模式 + SigV2/SigV4
│   │   └── manager.py                    # StorageManager单例: auto检测(GitHub Actions→remote else local)
│   ├── report/
│   │   ├── generator.py                  # prepare_report_data + generate_html_report + latest副本
│   │   ├── html.py                       # 富HTML报告 (~2515行): 暗色模式/搜索/折叠/tabs/快捷键/html2canvas
│   │   ├── rss_html.py                   # RSS独立HTML报告
│   │   ├── formatter.py                  # 7频道标题格式化 (feishu/dingtalk/wework/bark/telegram/ntfy/slack)
│   │   └── helpers.py                    # rank_trend计算, rank_display格式化, html_escape
│   ├── commands/
│   │   ├── doctor.py                     # 环境健康检查 → output/meta/doctor_report.json
│   │   ├── status.py                     # 调度状态展示
│   │   ├── test_notification.py          # 测试全部通知渠道
│   │   └── version.py                    # 双组件版本检查 (CDN fallback)
│   └── utils/
│       ├── time.py                       # DEFAULT_TIMEZONE=Asia/Shanghai, get_configured_time, is_within_days
│       └── url.py                        # normalize_url: 移除tracking参数+平台特定参数+sorted query
├── mcp_server/                           # MCP协议服务器 (FastMCP 2.0)
│   ├── server.py                         # 26个MCP tools + 4个resources注册 (~1258行)
│   ├── services/
│   │   ├── data_service.py               # DataService (~841行): 统一数据访问, 日期解析, 缓存集成
│   │   ├── parser_service.py             # ParserService: 直接SQLite读取(bypass StorageManager)
│   │   └── cache_service.py              # TTL cache: mtime-based config缓存, 线程安全
│   ├── tools/
│   │   ├── data_query.py                 # get_latest_news/get_news_by_date/get_trending_topics
│   │   ├── analytics.py                  # 趋势/生命周期/病毒传播/预测/平台对比/关键词共现/情感分析/周期对比
│   │   ├── search_tools.py               # 关键词/模糊/实体搜索 + 相关新闻发现 (SequenceMatcher)
│   │   ├── config_mgmt.py                # get_current_config (all/crawler/push/keywords/weights)
│   │   ├── system.py                     # get_system_status + trigger_crawl(按需爬取)
│   │   ├── storage_sync.py               # sync_from_remote + get_storage_status + list_available_dates
│   │   ├── article_reader.py             # Jina AI Reader (r.jina.ai): 单篇+批量(最多5,5s节流)
│   │   └── notification.py               # 9频道发送: 格式适配/分批/多账号 (完整独立实现)
│   └── utils/
│       ├── date_parser.py                # 自然语言日期解析: 今天/昨天/本周/上周/N天前/YYYY-MM-DD
│       ├── validators.py                 # 参数验证: platform/date_range/limit/top_n/mode/threshold/entity
│       └── errors.py                     # MCPError基类: code+message+suggestion → to_dict()
├── docker/
│   └── manage.py                         # 容器管理 (~735行): manual_run/show_status/start_webserver(:8080)
└── _image/                               # Docker/文档图片资源
```

## 核心数据流

```
config.yaml + timeline.yaml
        │
        ▼
  load_config() ──► AppContext ──► NewsAnalyzer.run()
                                        │
           ┌────────────────────────────┼──────────────────────────┐
           ▼                            ▼                          ▼
    DataFetcher.crawl_websites()  RSSFetcher.fetch_all()   StorageManager
    (NewsNow API → hotlists)      (feedparser → RSS items) (SQLite+TXT+HTML)
           │                            │
           └──────────┬─────────────────┘
                      ▼
           ┌─────────────────────┐
           │  Filter Strategy:   │
           │  keyword → count_word_frequency()    │
           │  ai     → AIFilterPipeline.run()     │
           └─────────────────────┘
                      │
           ┌──────────┼──────────┐
           ▼          ▼          ▼
    generate_html()  dispatch_all()  translate_content()
    (HTML报告)       (9渠道)        (AI翻译)
```

## NewsAnalyzer 类 (~1716行)

- `MODE_STRATEGIES`: incremental(增量/无新增不推) / current(当前榜单+新增+按时推) / daily(全天累计+按时推)
- `run()` → `_initialize_and_check_config()` → `_crawl_data()` → `_crawl_rss_data()` → `_execute_mode_strategy()`
- `_execute_mode_strategy()`: 加载历史数据 → `_run_analysis_pipeline()` → `_send_notification_if_needed()`
- `_run_analysis_pipeline()`: 选择 filter 策略 → count_frequency → convert_to_platform → AI analysis → translate → HTML

## AppContext 类 (~538行)

依赖注入中心，所有操作通过它路由：
- 时间: `get_time()`, `format_date()`, `format_time()`
- 存储: `get_storage_manager()` (lazy singleton)
- 报告: `generate_html()`, `render_html()`, `render_feishu()`, `render_dingtalk()`
- 通知: `create_notification_dispatcher()`, `split_content()`
- 调度: `create_scheduler()` (lazy singleton)
- AI: `run_ai_filter()`, `convert_ai_filter_to_report_data()`

## 通知系统

**9 种渠道，均支持多账号 (`;` 分隔):**
- 飞书: text格式(www.feishu.cn) vs card 2.0交互式(其他endpoint)
- 钉钉: Markdown msgtype
- 企微: markdown(群机器人) vs text(个人) 双模式
- Telegram: HTML parse_mode, web_page_preview=false
- Email: MIME multipart(HTML+plain), SMTP 14供应商自动配置
- Slack: mrkdwn格式 via Incoming Webhooks
- Bark: iOS APNs, device_key提取, 倒序发送
- ntfy: 倒序发送, 429重试, 4KB限制
- Generic Webhook: `{title}`/`{content}` 模板替换

**添加新渠道需修改**: splitter.py + renderer.py + formatters.py + senders.py 4个文件

## 存储系统

- SQLite `output/news/{date}.db` (hotlists) + `output/rss/{date}.db` (RSS)
- 每张表由 `schema.sql`/`rss_schema.sql`/`ai_filter_schema.sql` 定义
- `sqlite_mixin.py` (~1766行): upsert逻辑, rank_history追踪, title_changes检测, 离线检测(rank=0)
- 可选 S3 远程同步 (boto3, SigV2 for COS/OSS, SigV4 otherwise), batch模式
- `StorageManager` 单例: GitHub Actions+remote→remote, else→local
- **⚠️ Bug**: `LOCAL_RETENTION_DAYS`/`REMOTE_RETENTION_DAYS` 通过 env var 设为 0 被 `or` 链忽略
- **⚠️ Bug**: `MAX_NEWS_PER_KEYWORD`/`MAX_ACCOUNTS_PER_CHANNEL` 同理

## MCP 服务器 (26 Tools)

- Group 0: `resolve_date_range` (自然语言→标准日期范围)
- Group 1: `get_latest_news`, `get_news_by_date`, `get_trending_topics`
- Group 2: `get_latest_rss`, `search_rss`, `get_rss_feeds_status`
- Group 3: `search_news` (keyword/fuzzy/entity), `find_related_news` (SequenceMatcher+Jaccard)
- Group 4: `analyze_topic_trend` (trend/lifecycle/viral/predict), `analyze_data_insights` (platform_compare/activity/keyword_cooccurrence), `analyze_sentiment`, `aggregate_news`, `compare_periods`, `generate_summary_report`
- Group 5: `get_current_config`, `get_system_status`, `check_version`, `trigger_crawl`
- Group 6: `sync_from_remote`, `get_storage_status`, `list_available_dates`
- Group 7: `read_article` (Jina AI Reader), `read_articles_batch` (max 5, 5s throttle)
- Group 8: `get_channel_format_guide`, `get_notification_channels`, `send_notification`
- 4 Resources: `config://platforms`, `config://rss-feeds`, `data://available-dates`, `config://keywords`
- stdio + HTTP 双传输模式
- `date_parser.py`: 支持中文(今天/昨天/本周/上周一/N天前)和英文日期表达式

## 已知问题

- **⚠️** env var 0 值 bug: loader.py 93/112/384/392 行 `or` 链中 `0` 被当 falsy 忽略
- **⚠️** camelCase vs snake_case: 存储层用 camelCase(mobileUrl/sourceName), 处理后用 snake_case, AI filter pipeline 产出 snake_case 直接导致不匹配
- **⚠️** 通知格式分派用 `if/elif` 链，新增渠道需改 4 个文件 ~20 处
- Windows Notepad BOM 损坏 config/frequency 文件 (frequency.py:136 用 utf-8 而非 utf-8-sig)

---

## 跨项目注意事项

- `ai-toolbox/work/modules/hashtag_enricher/` 和独立 `hashtag-enricher/` 功能相同但独立维护 — 前者 bridge 到 `model_config.WENAN`，后者读 `.env` + `config.yaml`
- `ai-toolbox/work/modules/wenan/generator.py` 和 `ai-toolbox/work/modules/orchestrator/engine.py:_generate_copy()` 都有独立的合规检查 — 更新规则时需同步
- `social-auto-upload-main/` 与 `hashtag-enricher/social-auto-upload/`（git 子模块）是独立 checkout
- `model_config.py` 同时存在于根目录、`ai-toolbox/work/`、`ai-toolbox/work/modules/tishici/ai_client.py` — 三处需同
- **根目录 `model_config.py` 和 `ai-toolbox/work/modules/tishici/ai_client.py` 包含硬编码 API 密钥 — 切勿提交到版本控制**
- 多个 `.venv`/`venv` 目录 — 各项目独立管理依赖
- `claude-settings.json` 配置为 DeepSeek V4-Pro 通过 Anthropic 兼容 API
- `ai-toolbox/.agents/agent.md` 规则: 只改代码和必要分析，不运行测试/构建/迁移/启动服务，不写长篇汇报，完成后只回复 1-2 行摘要
