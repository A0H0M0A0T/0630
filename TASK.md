# TASK.md

当前阶段任务上下文。

---

## 阶段定位

当前工作区 `D:\0703` 是多项目工作区，包含 4 个独立子项目 + 1 个同构变体。本阶段目标：**整理文档与系统边界，不做代码重构。**

---

## 子项目清单

| 目录 | 用途 | 独立程度 |
|------|------|---------|
| `ai-toolbox/work/` | AI 短视频广告全链条生成（主项目） | 独立前后端 + 独立 DB |
| `ai-toolbox/alxuanchuan/` | 同功能 Gemini 变体 | 独立 Express 服务器 |
| `hashtag-enricher/` | LLM 话题标签生成器 CLI | 独立 Python 包 + 独立 git 仓库 |
| `social-auto-upload-main/` | 多平台视频发布自动化 | 独立 Flask + Vue 3 + 独立 DB |
| `TrendRadar-master/` | 热点新闻聚合分析与推送 | 独立 Python 项目（v6.10.0） |

详细架构见 `PROJECT_MAP.md` 和 `readme.md`。

---

## 当前阶段任务

### 1. 确认子项目间关系

- [ ] 确认 `ai-toolbox/work/modules/hashtag_enricher/` 与独立 `hashtag-enricher/` 的关系和同步策略
- [ ] 确认 `ai-toolbox/work/` 与 `ai-toolbox/alxuanchuan/` 的维护策略（是否长期双维护）
- [ ] 确认 `hashtag-enricher/social-auto-upload/` 空 git 子模块的用途（当前为空仓库）
- [ ] 确认 ai-toolbox 产出（视频+标签）到 social-auto-upload 发布是否有自动化衔接需求
- [ ] 确认 TrendRadar 热点数据是否需接入 ai-toolbox 选题流程

### 2. 标记高风险重复点（仅标记，不修改代码）

- [ ] **标签系统双份**：`ai-toolbox/work/modules/hashtag_enricher/` 与 `hashtag-enricher/` 功能相同、独立维护，一处修改需手动同步
- [ ] **发布路径双份**：`social-auto-upload-main` Web 路径（`myUtils/postVideo.py`）和 CLI 路径（`sau_cli.py:dispatch()`）不共享 dispatch 逻辑
- [ ] **model_config 多份**：根目录、`ai-toolbox/work/`、`ai-toolbox/work/modules/tishici/ai_client.py` 三处含硬编码 API 密钥
- [x] **sanitize 规则双份**：`engine.py:_WORKFLOW_SANITIZE_MAP` 与 `assembler.py:_SANITIZE_MAP` → 已抽离 `modules/common/sanitize.py`（`COMMON_SANITIZE_MAP`），各自保留扩展规则
- [ ] **合规检查规则双份**（已验证存在）：`wenan/generator.py`（`_CONTENT_BLOCK_RULES` 59条）与 `orchestrator/engine.py:_generate_copy()`（`_COPY_BANNED` + CTA）各自独立实现，在「饮后承诺/养生暗示/疾病术语/违规功效」4 类重叠，修改需同步两处
- [ ] **文档信息重叠**：`readme.md`（根）与 `PROJECT_MAP.md` 大量重复描述子项目架构

### 3. 文档待修正项（仅标记，暂不修改）

- [ ] `social-auto-upload-main/CLAUDE.md` 前端端口 5173 vs `PROJECT_MAP.md` 及 `start-all.bat` 的 5174，需核实实际配置后统一
- [ ] `ai-toolbox/alxuanchuan/README.md` 只有 AI Studio 模板默认文本，缺项目说明
- [ ] `sau_frontend/README.md` 是通用 Vue3 模板，缺项目特有信息
- [ ] `.plan.md` 描述的是 `D:\0630` 的历史任务，与当前 `D:\0703` 无关
- [ ] `ai-toolbox/readme.md` 引用绝对路径 `D:\0000\模板视频分析结果`，当前环境可能不存在
- [x] `ai-toolbox/work/docs/superpowers/plans/2026-07-02-workflow-diagnostic-logging.md`：已添加 `[ARCHIVED — 计划已实施]` 头部标注，说明路径指向旧工作区且功能已上线
- [ ] `social-auto-upload-main/docs/`：目录下 7 个文档文件（CLI.md、agent-bootstrap.md、legacy-web.md、skill-distribution.md、update.md + 3 个 plans）是否纳入本次整理范围，待确认
- [ ] `social-auto-upload-main/findings.json`：PROJECT_MAP 标注为"代码审查发现（一次性文件）"，是否归档或保留，待确认

### 4. 待补充文档

- [ ] `ai-toolbox/work/` 无独立 README/CLAUDE.md（PROJECT_MAP 标注"详见根目录 CLAUDE.md"）
- [x] `SYSTEM_BOUNDARY.md` 已创建，后续仅做核对和小修

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

- [ ] 每个子项目的关系和协作方式有文档记录
- [ ] 高风险重复点已标记并有明确的处理决策（保留/合并/保持现状并说明原因）
- [ ] 文档冲突（端口号、路径引用）已核实并记录，不要求本阶段统一
- [ ] 缺失的 README 已补充

## 本次不执行项

- 不运行测试
- 不启动任何服务
- 不执行数据库迁移
- 不运行 npm/pip/uv install
- 不修改业务代码
- 不触发任何 workflow
- 不重构代码
- 不提交 git commit
