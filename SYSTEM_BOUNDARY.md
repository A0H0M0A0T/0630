# SYSTEM_BOUNDARY.md

本文件描述 `D:\0703` 工作区各独立系统的职责边界和协作关系。

**信息来源**：基于 `PROJECT_MAP.md`、`readme.md`（根）、各子项目 `CLAUDE.md` 和 `README.md` 的实际内容归纳，不依赖口头描述或目录名推测。

---

## 一、系统总览

```
D:\0703\
├── ai-toolbox/work/              ← 系统 A：AI 短视频广告全链条生成
│   └── modules/hashtag_enricher/  ← 话题标签生成（已内嵌于 A，无独立副本）
├── social-auto-upload-main/      ← 系统 B：多平台视频发布自动化
└── TrendRadar-master/            ← 系统 C：热点新闻聚合分析与推送
```

**当前耦合程度：松耦合 / 手动协作**。3 个系统均无程序化数据管道。

---

## 二、各系统职责边界

### 系统 A：ai-toolbox/work/ — AI 短视频广告全链条生成

| 维度 | 说明 |
|------|------|
| **入口** | `server.py`（FastAPI，端口 8000）+ `src/main.tsx`（React 19 前端，端口 5173） |
| **核心能力** | 输入产品图 → 8 步流水线（剧情分镜 → 关键帧提示词 → GPT Image-2 生图 → AI 评分 → 口播文案 → 视频提示词组装 → 视频提交 → 标签生成） |
| **目标产品** | S101 苦荞精酿啤酒（黄色铝罐 + 黑色 S 标识 + 银色拉环） |
| **辅助模块** | AI 识图（GPT-4o Vision）、AI 文案批量生成、AI 绘图（提示词生成 + 图片生成）、词牌匹配（已开发但未挂载） |
| **数据存储** | 3 个 SQLite DB（`auth.db` / `workflows.db` / `history.db`）+ 文件系统资产（`static/product/` / `static/generated/` / `static/video/`） |
| **职责边界** | 只负责**素材生成**（图片 + 视频提示词 + 口播文案 + 标签） |

### 系统 B：social-auto-upload-main/ — 多平台视频发布自动化

| 维度 | 说明 |
|------|------|
| **入口** | `sau_backend.py`（Flask，端口 5409）+ `sau_cli.py`（CLI）+ `sau_frontend/`（Vue 3，端口 5174） |
| **核心能力** | 使用 Playwright（patchright）驱动 Chromium 浏览器，自动化 8 个平台的 Web 上传流程：抖音、B站、小红书、快手、视频号、百家号、TikTok、YouTube |
| **两代代码** | 新代 `uploader/`（async/await + dataclass，优先使用） + 旧代 `myUtils/`（同步包装，遗留） |
| **两条调用路径** | Web 路径（Flask → myUtils/postVideo.py → uploader/）和 CLI 路径（sau_cli.py:dispatch() → uploader/）**不共享 dispatch 逻辑** |
| **数据存储** | SQLite `db/database.db`：`user_info` 表（账号）+ `file_records` 表（上传记录） |
| **Cookie 管理** | 新代 `cookies/{platform}_{name}.json`，旧代 `cookiesFile/{uuid}.json` |
| **职责边界** | 只负责**账号登录 + 视频发布**。不负责视频生成、不负责标签生成、不负责文案生成 |

### 系统 C：TrendRadar-master/ — 热点新闻聚合分析与推送

| 维度 | 说明 |
|------|------|
| **入口** | `trendradar/__main__.py`（NewsAnalyzer 主编排器）+ `mcp_server/server.py`（FastMCP 2.0） |
| **核心能力** | 从 11 个中文平台 + RSS 源爬取热榜 → 关键词/AI 筛选 → 生成 HTML 报告 → 推送到 9+ 通知渠道（飞书/钉钉/企微/Telegram/邮件/Slack/Bark/ntfy/通用 Webhook） |
| **AI 能力** | AI 分析（5 段报告）、AI 筛选（自然语言兴趣描述 → 标签分类）、AI 翻译（多语言推送） |
| **MCP 服务器** | 26 个工具 + 4 个资源，stdio/HTTP 双传输模式 |
| **数据存储** | SQLite `output/news/{date}.db` + `output/rss/{date}.db`，可选 S3 远程同步 |
| **职责边界** | 只负责**热点发现 + 分析 + 推送**。不负责广告素材生成、不负责视频发布、不负责账号管理 |

---

## 三、系统间协作关系

### 当前状态：松耦合 / 手动协作

| 关系 | 文档依据 | 当前实际 |
|------|---------|---------|
| 系统 A → 系统 B | `ai-toolbox/work/` 第 8 步生成标签，`social-auto-upload-main/` 支持发布时传入 `--tags` | **手动**：A 产出视频文件和标签后，用户手动用 B 的 CLI 或 Web 界面发布 |
| 系统 C → 系统 A | `TrendRadar-master/` 发现热点趋势 | **无数据连接**：C 分析热点的结果没有程序化传给 A 作为选题参考 |
| 系统 A 内嵌 | `ai-toolbox/work/modules/hashtag_enricher/` 内嵌了标签生成模块 | **已内嵌**：A 自带标签生成能力（`modules/hashtag_enricher/`），桥接到 `model_config.WENAN`，无需外部依赖 |
| `start-all.bat` | `readme.md`（根）描述了 5 个服务窗口的一键启动 | **仅进程启动**：同时启动各服务进程，不建立运行时数据通道 |

### 禁止越界

| 系统 | 不负责 |
|------|--------|
| **系统 A**（ai-toolbox） | 不负责账号登录、浏览器自动化、平台发布 |
| **系统 B**（social-auto-upload） | 不负责图片生成、视频生成、剧情编排、文案生成、热点发现 |
| **系统 C**（TrendRadar） | 不负责广告素材生成、视频发布、标签生成 |

---

## 四、文档参考

| 文档 | 位置 | 用途 |
|------|------|------|
| `PROJECT_MAP.md` | 根目录 | 模块到文件的映射与调试指南 |
| `readme.md` | 根目录 | 综合性项目文档（含各子项目架构详解） |
| `CLAUDE.md` | 根目录 | 整个工作区 Agent 行为规则 |
| `TASK.md` | 根目录 | 当前阶段任务上下文 |
| `SYSTEM_BOUNDARY.md` | 根目录 | 本文件 — 系统边界与协作关系 |
