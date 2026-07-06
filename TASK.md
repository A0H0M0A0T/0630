# TASK.md

当前阶段任务上下文。

---

## 阶段定位

当前工作区 `D:\0703` 是多项目工作区，包含 3 个独立子项目 + 1 个同构变体。本阶段目标：**整理文档与系统边界，不做代码重构。**

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

### 2. 标记高风险重复点（仅标记，不修改代码）

- [x] ~~**标签系统双份**~~ → **已解决**：独立 `hashtag-enricher/` 已删除，仅保留 `ai-toolbox/work/modules/hashtag_enricher/` 一处。
- [x] **发布路径双份**：`social-auto-upload-main` Web 路径（`myUtils/postVideo.py`）和 CLI 路径（`sau_cli.py:dispatch()`）不共享 dispatch 逻辑
  - 已核实：CLAUDE.md 明确标注"不共享 dispatch 逻辑。修复必须镜像到两处"。
  - **决策**：保持现状。两条路径面向不同场景（Web 多账号批量、CLI 单次快速），统一 dispatch 需较大重构。
- [x] **model_config 多份**：根目录、`ai-toolbox/work/`、`ai-toolbox/work/modules/tishici/ai_client.py` 三处含硬编码 API 密钥
  - 已核实：三处均含真实 API 密钥。根目录 `model_config.py` 已通过 `.gitignore` 排除。
  - **决策**：保持现状。不修改业务代码。长期建议统一到单一配置源（如 `.env`）。
- [x] **sanitize 规则双份**：`engine.py:_WORKFLOW_SANITIZE_MAP` 与 `assembler.py:_SANITIZE_MAP` → 已抽离 `modules/common/sanitize.py`（`COMMON_SANITIZE_MAP`），各自保留扩展规则
- [x] **合规检查规则双份**（已验证存在）：`wenan/generator.py`（`_CONTENT_BLOCK_RULES` 59条）与 `orchestrator/engine.py:_generate_copy()`（`_COPY_BANNED` + CTA）各自独立实现，在「饮后承诺/养生暗示/疾病术语/违规功效」4 类重叠，修改需同步两处
  - 已核实：两文件互不调用，规则独立维护。
  - **决策**：保持现状。两处服务于不同使用场景（批量文案风控 vs 口播合规），语义重叠但检查粒度不同。
- [x] **文档信息重叠**：`readme.md`（根）与 `PROJECT_MAP.md` 大量重复描述子项目架构
  - 已核实：`readme.md` 偏向产品级叙述（748 行），`PROJECT_MAP.md` 偏向结构化速查（315 行）。约 60% 内容重叠。
  - **决策**：保持现状。两文档服务不同读者（readme.md 新成员入门，PROJECT_MAP.md 日常开发定位）。不合并。

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

## 允许修改范围

- `TASK.md`（本文件）
- 其他 `.md` 文档文件（修正冲突、补充缺失信息）
- 根目录 `readme.md`、`PROJECT_MAP.md`

## 禁止修改范围

- **不修改任何业务代码**（`.py`、`.ts`、`.tsx`、`.vue`、`.js` 等）
- **不修改任何配置文件**（`config.yaml`、`conf.py`、`model_config.py`、`.env` 等）
- **不修改数据库文件**（`*.db`）
- **不修改 `CLAUDE.md` 行为规则文件**（除非用户明确要求）

## 验收标准

- [x] 每个子项目的关系和协作方式有文档记录（→ `SYSTEM_BOUNDARY.md` + 本文件 Section 1）
- [x] 高风险重复点已标记并有明确的处理决策（→ `SYSTEM_BOUNDARY.md` Section 四 + 本文件 Section 2）
- [x] 文档冲突（端口号、路径引用）已核实并记录（→ 本文件 Section 3）
- [x] 缺失的 README 已补充或决策不补充（→ 本文件 Section 4）

## 本次不执行项

- 不运行测试
- 不启动任何服务
- 不执行数据库迁移
- 不运行 npm/pip/uv install
- 不修改业务代码
- 不触发任何 workflow
- 不重构代码
- 不提交 git commit
