# TASK.md

当前阶段任务上下文。

---

## 阶段定位

当前工作区 `D:\0703` 是多项目工作区，包含 3 个独立子项目 + 1 个同构变体。本阶段目标：**整理文档与系统边界，消除高风险重复点。**

---

## 子项目清单

| 目录 | 用途 | 独立程度 |
|------|------|---------|
| `ai-toolbox/work/` | AI 短视频广告全链条生成（主项目） | 独立前后端 + 独立 DB |
| `ai-toolbox/alxuanchuan/` | 同功能 Gemini 变体 | 独立 Express 服务器 |
| `social-auto-upload-main/` | 多平台视频发布自动化 | 独立 Flask + Vue 3 + 独立 DB |
| `TrendRadar-master/` | 热点新闻聚合分析与推送 | 独立 Python 项目（v6.10.0） |

> 话题标签生成已内嵌到 `ai-toolbox/work/modules/hashtag_enricher/`，无独立副本。

详细架构见 `PROJECT_MAP.md` 和 `readme.md`。

---

## 当前阶段任务

### 1. 确认子项目间关系

- [x] ~~确认 `ai-toolbox/work/modules/hashtag_enricher/` 与独立 `hashtag-enricher/` 的关系和同步策略~~
  - **已过时**：独立 `hashtag-enricher/` 已删除。标签生成仅保留 `ai-toolbox/work/modules/hashtag_enricher/` 一处。
- [x] 确认 `ai-toolbox/work/` 与 `ai-toolbox/alxuanchuan/` 的维护策略
  - **结论**：功能同构但**独立维护**，代码不共享。work/ 使用 DeepSeek+GPT，alxuanchuan/ 使用 Gemini。
  - 前端组件结构相同但独立代码库。当前无同步机制，修改需手动镜像。
  - **决策**：保持现状并说明原因 — 模型供应商不同导致 prompt/API 调用差异较大，强行统一成本高。
- [x] ~~确认 `hashtag-enricher/social-auto-upload/` 空 git 子模块的用途~~
  - **已过时**：随 `hashtag-enricher/` 一并删除。
- [x] 确认 ai-toolbox 产出（视频+标签）到 social-auto-upload 发布是否有自动化衔接需求
  - **结论**：当前**无自动化管道**。用户手动从 A 取产出（视频+标签）→ 用 C 的 CLI/Web 发布。
  - 两个系统的 `--tags` 参数可接收标签但格式要求不同（A 出 JSON，C 需逗号分隔字符串）。
  - **决策**：当前阶段不建自动化管道。待业务量增大后再评估。
- [x] 确认 TrendRadar 热点数据是否需接入 ai-toolbox 选题流程
  - **结论**：当前**无数据连接**。D 独立分析热点推送到通知渠道，A 选题流程不消费 D 的输出。
  - **决策**：当前阶段不接入。两个系统面向不同场景（D 面向内容运营发现热点，A 面向素材生产）。

### 2. 高风险重复点 — 已全部处理

- [x] ~~**标签系统双份**~~ → **已解决**：独立 `hashtag-enricher/` 已删除。
- [x] **发布路径双份** → **已修复**：创建 `utils/platforms.py`（`XIAOHONGSHU`/`TENCENT`/`DOUYIN`/`KUAISHOU` 常量 + `PLATFORM_TYPE_MAP`），`sau_backend.py` 3 处 match 语句改用命名常量，消除平台类型魔数。
- [x] **model_config 多份** → **已修复**：`ai_client.py` 内嵌 `MODELS` 字典改为 `from model_config import TISHICI_MODELS`。根目录 `model_config.py` 从未提交（`.gitignore` 排除）。
- [x] **sanitize 规则双份** → 已抽离 `modules/common/sanitize.py`。
- [x] **合规检查规则双份** → **已修复**：创建 `modules/common/compliance.py`，提供 `COMPLIANCE_SHARED_RULES`（36 条分类规则）和 `COMPLIANCE_BANNED_WORDS`（27 条禁用词）。`generator.py` 和 `engine.py` 各保留自有执行逻辑。
- [x] **文档信息重叠** → 保持现状，两文档服务不同读者。

### 3. 文档待修正项（仅标记，暂不修改）

- [x] `social-auto-upload-main/CLAUDE.md` 前端端口 5173 vs `PROJECT_MAP.md` 及 `start-all.bat` 的 5174，需核实实际配置后统一
  - **核实结果**：`vite.config.js` 默认端口为 **5173**。`start-all.bat` 通过 `npx vite --port 5174` 显式覆盖为 5174。
  - `CLAUDE.md` 写的是 `npm run dev`（即 5173），`PROJECT_MAP.md` 表格写的是 5174。
  - **结论**：两者均正确 — 取决于启动方式。已更新 `PROJECT_MAP.md` 注明此差异。
- [x] `ai-toolbox/alxuanchuan/README.md` 只有 AI Studio 模板默认文本，缺项目说明
  - **核实结果**：确认为 Google AI Studio 自动生成模板（"Run and deploy your AI Studio app"），未描述本项目功能和架构。
  - **决策**：待后续补充。当前不修改业务文档内容。
- [x] `sau_frontend/README.md` 是通用 Vue3 模板，缺项目特有信息
  - **核实结果**：确认为通用 Vue3+Vite+ElementPlus 脚手架模板，未描述本项目的多平台发布功能。
  - **决策**：待后续补充。
- [x] `.plan.md` 描述的是 `D:\0630` 的历史任务，与当前 `D:\0703` 无关
  - **核实结果**：内容描述 `D:\0630\work` 的单端口+Frost 设计已完成任务，当前 workspace 在 `D:\0703` 且架构已完全不同。
  - **决策**：归档（添加 `[ARCHIVED]` 头部标注说明此文件为历史遗留）。
- [x] `ai-toolbox/readme.md` 引用绝对路径 `D:\0000\模板视频分析结果`，当前环境可能不存在
  - **核实结果**：第 26 行和第 29 行引用 `D:\0000\模板视频分析结果` 和 `D:\0000\模板图分析结果`。该路径在 D: 盘可能存在但非 workspace 内。
  - **决策**：不修改（该文件为产品需求文档而非技术文档，路径为原始需求记录）。
- [x] `ai-toolbox/work/docs/superpowers/plans/2026-07-02-workflow-diagnostic-logging.md`：已添加 `[ARCHIVED — 计划已实施]` 头部标注，说明路径指向旧工作区且功能已上线
- [x] `social-auto-upload-main/docs/`：目录下 7 个文档文件（CLI.md、agent-bootstrap.md、legacy-web.md、skill-distribution.md、update.md + 3 个 plans）是否纳入本次整理范围，待确认
  - **核实结果**：7 个文件均为技术文档（安装指南、CLI 参考、变更日志、设计文档）。属于子项目自有文档，不在根目录整理范围内。
  - **决策**：不纳入本次整理。由 `social-auto-upload-main/` 自行维护。
- [x] `social-auto-upload-main/findings.json`：PROJECT_MAP 标注为"代码审查发现（一次性文件）"，是否归档或保留，待确认
  - **核实结果**：JSON 数组，包含代码审查发现的 bug（如 `post_video_xhs` 传递 list 而非 datetime 的 bug）。属一次性审查产物，对日常开发无持续价值。
  - **决策**：保留不删（可能含未修复 bug 线索），标注为 `[ONE-TIME — 代码审查发现，不纳入日常维护]`。

### 4. 待补充文档

- [x] `ai-toolbox/work/` 无独立 README/CLAUDE.md（PROJECT_MAP 标注"详见根目录 CLAUDE.md"）
  - **决策变更**：已创建 `ai-toolbox/work/README.md`。内容为项目级概览（快速启动、目录结构、相关文档索引），不重复根 `readme.md` 中的流水线详述。
- [x] `SYSTEM_BOUNDARY.md` 已创建，后续仅做核对和小修
  - 已核对：描述与 `PROJECT_MAP.md` 和实际代码一致。无需修改。

---

## 完成状态

本阶段全部任务已完成。高风险重复点 #2、#3、#5 已通过代码修改解决：

| 修复项 | 变更文件 |
|--------|---------|
| 平台 dispatch 魔数消除 | 新增 `social-auto-upload-main/utils/platforms.py`，修改 `sau_backend.py` |
| model_config 三副本统一 | 修改 `ai-toolbox/work/modules/tishici/ai_client.py`（内嵌字典 → import） |
| 合规检查规则共享 | 新增 `ai-toolbox/work/modules/common/compliance.py`，修改 `wenan/generator.py`、`orchestrator/engine.py` |

所有变更已提交推送。
