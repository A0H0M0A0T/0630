# AI Toolbox — Work

AI 短视频广告全链条生成系统（主项目）。

## 快速启动

```bash
# 后端 (FastAPI, 端口 8000)
python server.py               # → http://localhost:8000

# 前端 (Vite + React 19, 端口 5173)
npm run dev                    # → http://localhost:5173
```

## 核心功能

**8 步 Workflow 流水线**：剧情分镜 → 关键帧提示词 → 图片生成 → AI 评分 → 口播文案 → 视频提示词组装 → 视频生成提交 → 标签生成。

**辅助模块**：AI 绘图（提示词生成 + 图片生成）、AI 识图（GPT-4o Vision）、AI 文案批量生成、AI 词牌匹配。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI + SQLite（3 个 DB：auth / workflows / history） |
| 前端 | React 19 + Vite + Tailwind CSS + Motion + lucide-react |
| AI 模型 | DeepSeek + GPT-4o Vision + GPT Image-2 |
| 认证 | PBKDF2 密码哈希 + Token（7 天过期） |

## 目录结构

```
work/
├── server.py                    # FastAPI 后端（~1234 行），全部 REST API 注册
├── src/                         # React 前端源码（16 个文件）
│   ├── App.tsx                  # Tab 导航、认证、共享状态管理
│   ├── components/              # 5 个功能 Tab + 认证页
│   ├── api/                     # HTTP 客户端 + 认证/服务/Workflow API
│   └── workflowDiagnostics.ts   # 诊断工具
├── modules/                     # 后端流水线模块
│   ├── orchestrator/            # WorkflowEngine 编排器（~1578 行）
│   ├── storyboard/              # 剧情分镜生成
│   ├── keyframe/                # 关键帧提取
│   ├── scorer/                  # AI 评分 + 闸门
│   ├── video_prompt/            # 视频提示词组装
│   ├── video_generation/        # 视频生成 Plug-in 架构
│   ├── hashtag_enricher/        # 标签生成（独立 hashtag-enricher 的周期性拷贝）
│   ├── wenan/                   # 文案批量生成（~732 行）
│   ├── tupian/                  # 图像识别（GPT-4o Vision）
│   ├── tishici/                 # 多模型 AIClient + PromptDatabase
│   └── common/                  # 共享工具（sanitize / text_utils）
├── static/                      # 静态资源（产品图 / 模板视频 / 生成输出）
├── tests/                       # 测试文件
└── dist/                        # Vite 构建产物（生产模式）
```

## 相关文档

| 文档 | 内容 |
|------|------|
| 根 `readme.md` | 完整项目文档：8 步流水线详解、全部 40+ API 路由、前端架构、跨模块导入机制 |
| 根 `PROJECT_MAP.md` | 模块到文件映射、常见问题定位指南 |
| 根 `SYSTEM_BOUNDARY.md` | 系统职责边界与子项目协作关系 |
| `hashtag-enricher/` | 独立标签生成器 CLI 源码（本模块的 canonical source） |
