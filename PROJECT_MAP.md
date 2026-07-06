# PROJECT_MAP.md

工作区路径：`D:\0703`

---

## 一、项目总览

```
D:\0703\
├── ai-toolbox/                  # 主项目 — AI 短视频广告全链条生成
│   ├── work/                    # ← 主工作目录 (FastAPI + React 19)
│   │   └── modules/hashtag_enricher/  # 话题标签生成（已内嵌，无独立副本）
│   └── alxuanchuan/             # Express + Gemini 独立服务器
├── social-auto-upload-main/     # 多平台视频发布自动化 (Flask + Vue 3)
├── TrendRadar-master/           # 热点新闻聚合分析与推送 (Python + SQLite)
├── model_config.py              # 共享 AI 模型配置（含密钥，勿提交）
├── model_config.example.py      # 配置模板
├── CLAUDE.md                    # Claude Code 工作规则
├── readme.md                    # 项目详细文档
├── PROJECT_MAP.md               # 本文件 — 项目地图
├── TASK.md                      # 当前任务上下文
├── SYSTEM_BOUNDARY.md           # 系统职责边界与协作关系
├── .plan.md                     # 历史遗留（D:\0630 计划文档，待核实或归档）
├── start-all.bat                # 一键启动全部开发服务
└── stop-all.bat                 # 停止全部服务
```

### 一键启动

```
start-all.bat   →  5 个服务窗口
stop-all.bat    →  全部停止
```

| 服务 | 端口 | 技术栈 |
|------|------|--------|
| AI-Toolbox 后端 | 8000 | FastAPI (Python) |
| AI-Toolbox 前端 | 5173 | Vite + React 19 |
| 上传服务 后端 | 5409 | Flask (Python) |
| 上传服务 前端 | 5174 | Vite + Vue 3 + Element Plus |

> **端口说明**：`vite.config.js` 默认端口为 **5173**。`start-all.bat` 通过 `npx vite --port 5174` 显式覆盖为 5174。两个端口均为正确值，取决于启动方式：直接 `npm run dev` → 5173，通过 `start-all.bat` → 5174。`CLAUDE.md` 写的是 5173（对应 `npm run dev`）。

各子项目 README/CLAUDE 分布：

| 子项目 | 文档文件 |
|--------|---------|
| `ai-toolbox/work/` | `README.md` |
| `ai-toolbox/alxuanchuan/` | `README.md` |
| `social-auto-upload-main/` | `CLAUDE.md`、`README.md`、`sau_backend/README.md`、`sau_frontend/README.md` |
| `TrendRadar-master/` | `CLAUDE.md`、`README.md`、`README-EN.md`、`README-MCP-FAQ.md`、`README-Cherry-Studio.md` |
| 根目录 | `SYSTEM_BOUNDARY.md`（系统边界）|

---

## 二、ai-toolbox/work/ — 短视频广告生成（主项目）

### 入口

| 文件 | 职责 |
|------|------|
| `server.py` | FastAPI 后端，全部 REST API |
| `src/main.tsx` | React 前端入口 |
| `src/App.tsx` | Tab 导航、认证、共享状态 |

### 8 步 Workflow 核心链路

```
Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Step 6 → Step 7 → Step 8
剧情分镜  → 关键帧  → 图片   → AI   → 口播   → 视频   → 视频   → 标签
生成      提示词    生成    评分    文案    提示词  生成提交  生成
```

| 步骤 | 核心文件 | 外部依赖 |
|------|---------|---------|
| 1 剧情分镜 | `modules/storyboard/generator.py` | DeepSeek |
| 1 提示词 | `modules/storyboard/prompts.py` | — |
| 1 场景池 | `modules/storyboard/scene_pool.py` | — |
| 2 关键帧 | `modules/keyframe/extractor.py` | LLM |
| 3 图片生成 | `modules/orchestrator/engine.py:_generate_image()` | GPT Image-2 |
| 4 AI 评分 | `modules/scorer/scorer.py` | GPT-4o Vision |
| 5 口播文案 | `modules/orchestrator/engine.py:_generate_copy()` | DeepSeek |
| 6 视频提示词 | `modules/video_prompt/assembler.py` | — |
| 7 视频提交 | `modules/video_generation/client.py` | 外部视频 API |
| 8 标签生成 | `modules/hashtag_enricher/enricher/llm.py` | LLM |

### 状态与编排

| 文件 | 职责 |
|------|------|
| `modules/orchestrator/engine.py` | WorkflowEngine：8 步流水线、品牌保护三层防线、闸门逻辑 |
| `modules/orchestrator/state.py` | WorkflowState + DB：workflows 表 + workflow_events 表 |
| `modules/orchestrator/routes.py` | 编排器路由定义 |

### 辅助模块

| 文件 | 职责 |
|------|------|
| `modules/wenan/generator.py` | 文案批量生成：4 种类型、trigram 去重、风控规则 |
| `modules/tishici/ai_client.py` | 多模型 AIClient（含 API 密钥，勿提交） |
| `modules/tishici/database.py` | PromptDatabase + SimilarityChecker |
| `modules/tupian/services/recognize.py` | GPT-4o Vision 识图 |
| `modules/tupian/database/db.py` | 识图历史 SQLite |
| `modules/hashtag_enricher/enricher/` | 标签生成（config/llm/reader/writer/postprocess/logger） |

### 前端

| 组件 | 职责 |
|------|------|
| `src/components/HandDrawnTab.tsx` | AI 绘图工作区（最大组件） |
| `src/components/WorkflowPage.tsx` | 短视频导演台 |
| `src/components/ImageRecognitionTab.tsx` | AI 识图 |
| `src/components/CopywritingTab.tsx` | AI 文案 |
| `src/components/LyricMatchingTab.tsx` | AI 词牌匹配（已构建，未挂载） |
| `src/components/AuthPage.tsx` | 登录/注册 |
| `src/api/client.ts` | HTTP 客户端（认证注入、错误处理） |
| `src/api/workflow.ts` | Workflow API（启动/状态/轮询/继续） |
| `src/api/services.ts` | 非 workflow 服务 API |
| `src/api/auth.ts` | 认证 API |
| `src/types.ts` | TS 类型定义 |
| `src/workflowDiagnostics.ts` | 诊断工具 |

### 新增（CLAUDE.md 未覆盖）

| 路径 | 说明 |
|------|------|
| `tests/` | 3 个测试文件（待确认是否需维护） |
| `docs/superpowers/plans/` | 1 个方案文档（⚠️ 内部路径指向 `D:\0630\work\`，待核实）|
| `plan/code-review-report.md` | Code review 报告（一次性文件） |
| `logs/app.log` | 运行时日志 |
| `static/gpt-image/` | GPT Image API 样式 |

### 常见问题定位

| 问题 | 先查文件 |
|------|---------|
| 品牌污染词（S101S101、盖盖盖 等） | `modules/common/sanitize.py` → `COMMON_SANITIZE_MAP` + `modules/orchestrator/engine.py` → `_ENGINE_EXTRA_SANITIZE` |
| 原始参考资料进入最终提示词 | `modules/video_prompt/assembler.py` |
| 分镜内容方向不对 | `modules/storyboard/prompts.py` |
| 生图产品外观不对 | `modules/keyframe/extractor.py` |
| 口播文案卖点/合规/CTA 不对 | `modules/orchestrator/engine.py` → `_generate_copy()` |
| 图片评分误判 | `modules/scorer/scorer.py` |
| 视频提交参数不对 | `modules/video_generation/client.py` |
| 前端诊断面板异常 | `src/workflowDiagnostics.ts` |
| 批量文案风控拦截异常 | `modules/wenan/generator.py` → `_CONTENT_BLOCK_RULES` |

---

## 三、ai-toolbox/alxuanchuan/ — Express + Gemini 独立服务器

### 入口

| 文件 | 职责 |
|------|------|
| `server.ts` | Express 后端：6 个 Gemini API 路由 |
| `src/main.tsx` → `src/App.tsx` | React 前端：4 Tab（无 Workflow） |

### 端点

```
POST /api/generate-prompt         → gemini-3.5-flash
POST /api/generate-image          → gemini-3.1-flash-lite-image
POST /api/deconstruct-visual      → Gemini vision
POST /api/recognize-image         → Gemini vision
POST /api/match-lyrics            → Gemini
POST /api/explosive-copywriting   → Gemini
```

前端组件与 `work/src/` 同构但使用 Gemini API。

---

---

## 四、social-auto-upload-main/ — 多平台视频发布

### 入口

| 文件 | 职责 |
|------|------|
| `sau_backend.py` | Flask 后端：20+ REST 路由 |
| `sau_cli.py` | CLI 入口：6 平台 login/check/upload |
| `sau_frontend/src/` | Vue 3 + Element Plus + Pinia |

新代代码在 `uploader/`，旧代代码在 `myUtils/`。

### 两条调用路径（不共享 dispatch，修复需镜像）

```
Web:  POST /postVideo → myUtils/postVideo.py → uploader/*/main.py
CLI:  sau <platform> upload-video → sau_cli.py:dispatch() → uploader/*/main.py
```

### 上传器

```
BaseVideoUploader (uploader/base_video.py)
├── douyin_uploader/     → DouYinVideo, DouYinNote
├── ks_uploader/         → KSVideo, KSNote
├── xiaohongshu_uploader/ → XiaoHongShuVideo/Note
├── xhs_uploader/        → XHS API 签名（独立实现）
├── tencent_uploader/    → TencentVideo
├── youtube_uploader/    → YouTubeVideo
├── baijiahao_uploader/  → BaiJiaHaoVideo
├── tk_uploader/         → TiktokVideo (Firefox + Chrome 双变体)
└── bilibili_uploader/   → biliup CLI 管理
```

### 辅助模块

| 文件 | 职责 |
|------|------|
| `utils/base_social_media.py` | Stealth.js 注入 + 平台常量 |
| `utils/browser_hook.py` | 反检测浏览器参数 |
| `utils/constant.py` | TencentZoneTypes + VideoZoneTypes |
| `utils/log.py` | loguru：9 平台独立 logger |
| `utils/login_qrcode.py` | QR 码生成/解析 |
| `db/createTable.py` | SQLite schema |

### Claude Code Skills

`skills/{douyin,kuaishou,xiaohongshu,bilibili}-upload/`
每个含 SKILL.md + references/ + scripts/examples/

### 新增（CLAUDE.md 未覆盖）

| 路径 | 说明 |
|------|------|
| `docs/` | 7 个文档文件（待确认是否维护） |
| `examples/` | 16 个示例脚本 |
| `tests/` | 4 个测试文件 |
| `findings.json` | 代码审查发现（一次性文件） |

---

## 五、TrendRadar-master/ — 热点新闻聚合分析

### 入口

| 文件 | 职责 |
|------|------|
| `trendradar/__main__.py` | NewsAnalyzer：爬取→分析→报告→推送 |
| `mcp_server/server.py` | FastMCP 2.0：26 tools + 3 resources |

### 核心数据流

```
config.yaml + timeline.yaml → AppContext → NewsAnalyzer.run()
                                   │
              ┌───────────────────┼───────────────────┐
              ▼                    ▼                    ▼
       DataFetcher           RSSFetcher          StorageManager
       (newsnow API)         (feedparser)        (SQLite+TXT+HTML)
              │                    │
              └────────┬───────────┘
                       ▼
              keyword 或 AI filter
                       │
              ┌────────┼──────────┐
              ▼        ▼          ▼
       generate_html()  dispatch_all()  translate_content()
```

### 关键类

| 类 | 文件 | 职责 |
|----|------|------|
| NewsAnalyzer | `trendradar/__main__.py` | 主编排器 |
| AppContext | `trendradar/context.py` | 依赖注入中心 |
| StorageManager | `trendradar/storage/manager.py` | 存储单例（local/remote） |
| Scheduler | `trendradar/core/scheduler.py` | 时间线调度 |
| AIClient | `trendradar/ai/client.py` | LiteLLM 封装 |
| NotificationDispatcher | `trendradar/notification/dispatcher.py` | 多频道推送 |

### 模块目录速查

| 目录 | 职责 |
|------|------|
| `trendradar/core/` | 配置加载、关键词、统计、调度 |
| `trendradar/crawler/` | 热榜爬取 + RSS 抓取 |
| `trendradar/ai/` | AI 分析、筛选、翻译 |
| `trendradar/notification/` | 9 渠道分发 |
| `trendradar/report/` | HTML 报告生成 |
| `trendradar/storage/` | SQLite / S3 存储 |
| `trendradar/commands/` | doctor/status/version/test-notification |
| `mcp_server/` | MCP 协议服务器 |

### 已知问题

无 — 4 个历史 bug 已修复（`is not None` 守卫、mobileUrl 统一、`utf-8-sig` 编码）。
