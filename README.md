<div align="center">

# 🤖 Agent Part

### 从商品分析到多平台刊登，多个 AI Agent 协作完成视觉内容生产--**你能实时看到每个 Agent 的思考与协作过程**

**基于 LangGraph 的多 Agent 协作 · 跨境电商视觉生成 · 可观测 Agent 工作台**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue-3.4-42b883.svg?logo=vue.js&logoColor=white)](https://vuejs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-powered-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

[![GitHub stars](https://img.shields.io/github/stars/JianFeiGan/agent_part?style=social)](https://github.com/JianFeiGan/agent_part/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/JianFeiGan/agent_part?style=social)](https://github.com/JianFeiGan/agent_part/network/members)
[![GitHub issues](https://img.shields.io/github/issues/JianFeiGan/agent_part)](https://github.com/JianFeiGan/agent_part/issues)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**[中文](#中文) · [English](#english)**

</div>

> 💡 **一句话介绍**：Agent Part 用一张 LangGraph 状态图编排 7+ 个专业 Agent，自动完成跨境电商的商品分析、AI 文案、图片/视频生成、合规检查、多平台刊登全流程；并通过一个 DevTools 风格的可观测工作台，让你实时看到每个 Agent 的提示词、传递参数与协作轨迹。

---

<a name="中文"></a>

## 📑 目录

- [✨ 这是什么](#-这是什么)
- [🎯 为什么选 Agent Part](#-为什么选-agent-part)
- [📸 效果展示](#-效果展示)
- [🚀 核心特性](#-核心特性)
- [🏗️ 系统架构](#-系统架构)
- [⚡ 快速开始](#-快速开始)
- [⚙️ 环境变量](#-环境变量)
- [📁 项目结构](#-项目结构)
- [🛠️ 技术栈](#-技术栈)
- [🧪 开发与测试](#-开发与测试)
- [🗺️ 路线图](#-路线图)
- [🤝 贡献](#-贡献)
- [👥 贡献者](#-贡献者)
- [🙏 致谢](#-致谢)
- [📄 许可证](#-许可证)

---

## ✨ 这是什么

Agent Part 是一个面向跨境电商的 **多 Agent 协作系统**，利用 LangGraph 状态图驱动多个专业 Agent 协同工作，自动完成从商品分析到视觉内容生成、合规检查、多平台刊登的全流程。

- 📦 **商品信息分析** - Agent 自动提取卖点、分析竞品、识别目标人群
- ✍️ **AI 文案生成** - 多语言商品描述、平台风格适配、LLM 降级策略
- 🖼️ **图片生成** - DashScope 万象 API（`wanx-v1` / `wan2.7-image-pro`）
- 🎬 **视频生成** - 可灵 AI 分镜设计 + 视频生成
- ✅ **合规检查** - 广告法禁词检测、平台规则验证
- 🌐 **多平台刊登** - Amazon / eBay / Shopify 适配器，凭证加密存储
- 📚 **RAG 知识增强** - PGVector 向量检索 + Graph RAG + CategoryMemory
- 📊 **AI 会话追踪** - Token 消耗统计、双币种费用预算、内容检索
- 🔬 **Agent 可观测工作台** - DAG 流程图 + 提示词轨迹 + 实时协作视图

> 💡 **适合谁？** 跨境电商从业者、AI 应用开发者、LangChain/LangGraph 学习者、对 Agent 可观测性感兴趣的研究者。

---

## 🎯 为什么选 Agent Part

与单链路 LLM 应用或通用 Agent 框架相比，Agent Part 提供了三个独特价值：

| | 单链路 LLM | 通用 Agent 框架 | **Agent Part** |
|---|---|---|---|
| **多 Agent 编排** | ❌ | ⚠️ 需自行搭建 | ✅ 开箱即用的 LangGraph 工作流 |
| **垂直场景闭环** | ❌ | ❌ | ✅ 分析->生成->合规->刊登一站式 |
| **可观测性** | ❌ 黑盒 | ⚠️ 基础日志 | ✅ DAG 流程图 + 提示词轨迹 + 实时协作 |
| **国产大模型生态** | ❌ | ⚠️ | ✅ 千问百炼 + DashScope 万象 + 可灵 AI |
| **RAG 知识增强** | ❌ | ⚠️ 单一向量 | ✅ PGVector + Graph RAG + 混合检索 |
| **生产就绪** | ❌ | ❌ | ✅ 认证鉴权 + 多租户 + 优雅降级 |

---

## 📸 效果展示

> 🎬 **Agent 可观测工作台**（v0.2.0 新增）- 这是 Agent Part 最与众不同的部分。

**DAG 流程图视图**：每个 Agent 作为一个节点，实时显示执行状态（等待 / 运行中 / 完成 / 失败），节点间连线展示数据流向。

**DevTools 风格详情面板**：点击任意节点，右侧分 4 个 Tab 查看该 Agent 的完整工作过程：
- **概览** - 状态、耗时、Token 消耗、费用、上下游 Agent
- **提示词** - 完整的 System / Human Prompt（不截断，可一键复制）
- **输入输出** - 该 Agent 接收的参数与产出的结构化结果
- **子调用** - LLM / 工具调用的详细记录

**实时协作**：通过 WebSocket 推送，Agent 状态变化即时反映到流程图，无需刷新。

<!-- 截图待补充：欢迎贡献！请将工作台截图放入 docs/images/ 目录 -->
<!-- 建议截图：1) DAG 全景  2) 提示词 Tab  3) 运行中脉冲动画  4) 仪表盘 -->

```
┌─────────────────────────────────────────────────────────────┐
│  🤖 Agent 工作台                            ● WS 已连接      │
│  任务 task_xxxx · 运行中 · 进度 ▓▓▓▓▓░░░░ 62%               │
├──────────────────────────────┬──────────────────────────────┤
│                              │ [概览] [提示词] [IO] [子调用] │
│        ┌──────────┐          │                              │
│        │ Orchestr │ ✅        │  Agent: CreativePlanner      │
│        └────┬─────┘          │  状态: ● 运行中 (脉冲)        │
│             │                 │  耗时: 3.2s · Token: 1,840   │
│        ┌────▼─────┐          │  费用: ¥0.018                │
│        │ ReqAnaly │ ✅        │                              │
│        └────┬─────┘          │  📥 上游: RequirementAnalyzer│
│             │                 │  📤 下游: VisualDesigner     │
│        ┌────▼─────┐          │                              │
│        │ Creative │ 🔄 运行中 │  System Prompt:             │
│        │ Planner  │ ●●●       │  你是一位资深跨境电商创意... │
│        └────┬─────┘          │  [完整展示 · 📋 复制]         │
│             │                 │                              │
│        ┌────▼─────┐          │                              │
│        │ VisualD  │ ⏳ 等待   │                              │
│        └──────────┘          │                              │
└──────────────────────────────┴──────────────────────────────┘
```

---

## 🚀 核心特性

| 特性 | 描述 |
|------|------|
| 🔬 **Agent 可观测工作台** | DAG 流程图（AntV G6）+ 提示词轨迹 + WebSocket 实时协作 |
| 🤖 **多 Agent 协作** | 7 个视觉生成 Agent + 4 个刊登 Agent + 3 个 RAG 增强 Agent + 3 个知识库 Agent |
| 🔄 **LangGraph 工作流** | 条件路由、并行执行、状态检查点、stream 模式实时回调、RAG 动态注入 |
| 🖼️ **图片生成** | DashScope 万象（`wanx-v1` / `wan2.7-image-pro`），async_call + wait 模式 |
| 🎬 **视频生成** | 可灵 AI（`kling-v1`），HS256 JWT 鉴权 + 异步任务轮询 |
| 📚 **RAG 增强** | PGVector + BGE-large-zh / 千问 text-embedding-v3 双通道 Embedding |
| 🕸️ **Graph RAG** | 知识图谱实体/边 + CategoryMemory + 混合检索（RRF 融合） |
| ✅ **合规检查** | 广告法禁词检测 + 平台规则验证 |
| 🌐 **多平台刊登** | Amazon / eBay / Shopify 适配器 |
| 🔄 **双 LLM 通道** | 百炼 OpenAI 兼容（ChatOpenAI）+ DashScope SDK（ChatTongyi） |
| 📊 **会话追踪** | Token 统计、双币种（USD/CNY）费用预算、内容搜索 |
| 🔐 **认证鉴权** | API Token（SHA256 + Scope 权限）+ 多租户隔离 |
| 🛡️ **优雅降级** | 无 API Key 时自动 Mock，LLM 降级链（通义 -> Claude -> 规则） |
| 🎨 **管理后台** | Vue 3 + Element Plus，15 个页面 |

---

## 🏗️ 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                     Vue 3 管理后台 (15 页面)                  │
│  仪表盘 │ 商品管理 │ 任务管理 │ 知识库 │ 刊登工具 │ AI 会话    │
│         │          │ 可观测工作台 │          │                │
└──────────────────────────┬───────────────────────────────────┘
                           │ REST API / WebSocket
┌──────────────────────────▼───────────────────────────────────┐
│                     FastAPI API 层 (40+ 端点)                 │
│  认证: API Token (SHA256 + Scope)    租户隔离: tenant_id      │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                   LangGraph 工作流引擎                         │
│                                                               │
│  视觉生成工作流:                                                │
│  Orchestrator -> ReqAnalyzer -> CreativePlanner -> VisualDesigner│
│       -> [ImageGen | VideoGen] -> QualityReviewer -> END          │
│                                                               │
│  刊登工作流:                                                    │
│  ImportProduct -> [AssetOptimizer | Copywriter] -> Compliance   │
│                                                               │
│  知识库 Agent 工作流:                                           │
│  QueryAnalyzer -> StrategyRouter -> HybridRetriever -> Fuser      │
└───────┬──────────────┬──────────────┬────────────────────────┘
        │              │              │
 ┌──────▼──────┐ ┌─────▼─────┐ ┌─────▼──────┐
 │  千问百炼    │ │  DashScope │ │  可灵 AI    │
 │ (OpenAI兼容) │ │  (万象图片) │ │  (视频生成)  │
 └──────┬──────┘ └─────┬─────┘ └─────┬──────┘
        │              │              │
 ┌──────▼──────────────▼──────────────▼────────┐
 │  PostgreSQL + PGVector  │  Redis  │  Storage │
 │  15+ 表 (向量/图谱/记忆)  │  缓存   │  本地/OSS │
 └─────────────────────────────────────────────┘
```

> 📊 更详细的类图与时序图见 [`docs/class-diagram.mermaid`](docs/class-diagram.mermaid) 与 [`docs/sequence-diagram.mermaid`](docs/sequence-diagram.mermaid)。

---

## ⚡ 快速开始

### 方式一：Docker 启动（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/JianFeiGan/agent_part.git
cd agent_part

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，至少配置 QWEN_API_KEY

# 3. 启动所有服务
docker compose up -d

# 4. 访问
#   前端:        http://localhost:3000
#   后端 API 文档: http://localhost:8000/docs
```

### 方式二：本地开发

```bash
# 后端
git clone https://github.com/JianFeiGan/agent_part.git
cd agent_part
uv sync
cp .env.example .env  # 编辑 .env
uv run python main.py

# 前端
cd frontend
npm install
npm run dev
```

> 🛡️ **没有 API Key？** 设置 `ALLOW_MOCK_ASSETS=true`，系统会自动降级为 Mock 模式，无需真实 Key 即可体验完整工作流。

---

## ⚙️ 环境变量

### 必填

| 变量 | 说明 |
|------|------|
| `QWEN_API_KEY` | 百炼 API Key（同时支持 OpenAI 兼容和 DashScope 原生协议） |

### 可选

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_PROVIDER` | `dashscope` | LLM 提供商：`qwen`（百炼 OpenAI 兼容）或 `dashscope` |
| `QWEN_API_BASE` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 百炼 OpenAI 兼容端点 |
| `DASHSCOPE_API_KEY` | - | DashScope API Key（可与 QWEN_API_KEY 共用） |
| `QWEN_LLM_MODEL` | `qwen-plus` | LLM 模型名称 |
| `KLING_ACCESS_KEY` | - | 可灵 AI Access Key |
| `KLING_SECRET_KEY` | - | 可灵 AI Secret Key |
| `EMBEDDING_PROVIDER` | `local` | Embedding 提供商：`local`（BGE-large-zh）或 `qwen` |
| `EMBEDDING_MODEL` | `BAAI/bge-large-zh` | 本地 Embedding 模型名称 |
| `RAG_ENABLED` | `true` | 启用 RAG 知识检索 |
| `RETRIEVAL_TOP_K` | `5` | 检索返回数量 |
| `SIMILARITY_THRESHOLD` | `0.7` | 相似度阈值 |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL 连接 URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接 URL |
| `STORAGE_TYPE` | `local` | 存储类型：`local` 或 `oss` |
| `ALLOW_MOCK_ASSETS` | `true` | 无 API Key 时允许 Mock 降级 |

完整配置见 [`.env.example`](.env.example)。

---

## 📁 项目结构

```
agent_part/
├── src/                          # 后端源码
│   ├── agents/                   # Agent 实现
│   │   ├── orchestrator.py       #   编排调度 Agent
│   │   ├── requirement_analyzer.py  # 需求分析 Agent
│   │   ├── creative_planner.py   #   创意策划 Agent
│   │   ├── visual_designer.py    #   视觉设计 Agent
│   │   ├── image_generator.py    #   图片生成 Agent
│   │   ├── video_generator.py    #   视频生成 Agent
│   │   ├── quality_reviewer.py   #   质量审核 Agent
│   │   ├── rag_*.py              #   RAG 增强 Agent (3个)
│   │   └── listing_*.py          #   刊登 Agent (5个)
│   ├── graph/                    # LangGraph 状态图与工作流
│   │   ├── workflow.py           #   视觉生成工作流
│   │   └── listing_workflow.py   #   刊登工作流
│   ├── api/                      # FastAPI 路由 + Schema + Service
│   │   ├── router/               #   路由模块 (12个)
│   │   ├── schema/               #   请求/响应模型
│   │   └── service/              #   业务服务
│   ├── clients/                  # 外部服务客户端
│   │   ├── dashscope_image_client.py  # DashScope 图片生成
│   │   ├── kling_video_client.py      # 可灵 AI 视频生成
│   │   ├── qwen_llm_client.py         # 千问 LLM
│   │   └── qwen_embedding_client.py   # 千问 Embedding
│   ├── rag/                      # RAG 检索管道
│   │   ├── retriever.py          #   知识检索器
│   │   ├── embeddings.py         #   双通道 Embedding
│   │   ├── chunker.py            #   语义分块
│   │   └── graph_memory.py       #   Graph RAG 记忆
│   ├── knowledge/                # 知识图谱 + 混合检索
│   │   ├── hybrid_retriever.py   #   RRF 融合检索
│   │   ├── agent_workflow.py     #   知识库 Agent 工作流
│   │   └── agents/               #   查询分析/策略路由/结果融合
│   ├── config/                   # 配置管理 (pydantic-settings)
│   ├── db/                       # 数据库 (15+ 表)
│   ├── auth/                     # API Token 认证 + 多租户
│   ├── models/                   # Pydantic 数据模型
│   └── storage/                  # 文件存储 (本地/OSS)
├── frontend/                     # Vue 3 前端
│   └── src/
│       ├── views/                # 页面组件 (15个)
│       ├── components/workbench/ #   Agent 可观测工作台组件
│       ├── api/                  # API 调用层
│       ├── types/                # TypeScript 类型
│       ├── stores/               # Pinia 状态管理
│       └── styles/               # 全局样式 (CSS 变量设计系统)
├── tests/                        # 测试用例
├── docs/                         # 设计文档与图表
├── docs-site/                    # 文档站
├── docker-compose.yml            # Docker 编排
├── Dockerfile                    # 后端镜像
├── Dockerfile.frontend           # 前端镜像
└── pyproject.toml                # 项目配置
```

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **工作流引擎** | LangChain, LangGraph |
| **后端框架** | FastAPI, Pydantic v2, SQLAlchemy 2.0 (async) |
| **语言模型** | 千问百炼 (OpenAI 兼容 + DashScope SDK) |
| **图片生成** | DashScope 万象 (`wanx-v1`, `wan2.7-image-pro`) |
| **视频生成** | 可灵 AI (`kling-v1`) |
| **向量检索** | PGVector, BGE-large-zh, 千问 text-embedding-v3 |
| **图谱检索** | Graph RAG (实体/关系/社区/摘要) |
| **前端框架** | Vue 3, TypeScript, Element Plus, Pinia, AntV G6 |
| **数据库** | PostgreSQL 16 + PGVector, Redis 6 |
| **存储** | 本地文件系统 / 阿里云 OSS |
| **部署** | Docker Compose, Nginx |

---

## 🧪 开发与测试

```bash
# 运行测试
uv run pytest

# 带覆盖率报告
uv run pytest --cov=src --cov-report=html

# 代码格式化
uv run ruff format .

# Lint 检查
uv run ruff check .

# 类型检查
uv run mypy src/
```

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 🗺️ 路线图

- [x] **v0.1.0** - LangGraph 7-Agent 视觉生成工作流 + RAG 知识库 + 合规检查 + Vue 3 管理后台
- [x] **v0.2.0** - 千问百炼对接 + AI 会话追踪 + Agent 可观测工作台（DAG + 提示词轨迹）
- [ ] **v0.3.0** - 高级 RAG（HyDE / 多查询重写）+ GraphRAG 增强 + 生产级刊登 + 图片 RAG
- [ ] **v0.4.0** - Agent 自适应重试与自愈 + 工作流可视化编辑器
- [ ] **v1.0.0** - 多租户 SaaS 化 + 插件式 Agent 市场 + 全面生产就绪

> 💬 有想要的功能？欢迎在 [Issues](https://github.com/JianFeiGan/agent_part/issues) 中提出，或直接提交 PR。

---

## 🤝 贡献

我们欢迎各种形式的贡献！

- 🐛 [报告 Bug](https://github.com/JianFeiGan/agent_part/issues/new?template=bug_report.md)
- ✨ [提交功能请求](https://github.com/JianFeiGan/agent_part/issues/new?template=feature_request.md)
- 📸 补充工作台 / 仪表盘截图（放入 `docs/images/`）
- 💻 提交 Pull Request

请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解开发环境搭建、代码规范与提交格式。

---

## 👥 贡献者

感谢所有为 Agent Part 贡献代码的人 ✨

<a href="https://github.com/JianFeiGan/agent_part/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=JianFeiGan/agent_part" />
</a>

---

## 🙏 致谢

本项目站在巨人的肩膀上，感谢以下开源项目与服务：

- [LangChain](https://github.com/langchain-ai/langchain) / [LangGraph](https://github.com/langchain-ai/langgraph) - Agent 编排框架
- [FastAPI](https://github.com/tiangolo/fastapi) - 高性能 API 框架
- [Vue.js](https://github.com/vuejs/core) / [Element Plus](https://github.com/element-plus/element-plus) - 前端框架与组件库
- [AntV G6](https://github.com/antvis/G6) - DAG 流程图渲染
- [PGVector](https://github.com/pgvector/pgvector) - PostgreSQL 向量扩展
- [阿里云百炼 / DashScope / 可灵 AI](https://help.aliyun.com/) - 大模型与多模态生成能力

---

## 📄 许可证

本项目基于 [Apache License 2.0](LICENSE) 开源。

---

<div align="center">

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=JianFeiGan/agent_part&type=Date)](https://star-history.com/#JianFeiGan/agent_part&Date)

**如果这个项目对你有帮助，欢迎 Star 支持一下！** ⭐

</div>

---

<a name="english"></a>

<div align="center">

# 🤖 Agent Part

### From product analysis to multi-platform listing - multiple AI Agents collaborate on visual content generation, **and you can watch each Agent's reasoning in real time**

**Multi-Agent collaboration via LangGraph · Cross-border e-commerce visual generation · Observable Agent workbench**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue-3.4-42b883.svg?logo=vue.js&logoColor=white)](https://vuejs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-powered-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

</div>

> A multi-agent collaboration system that automates cross-border e-commerce visual content - product analysis, AI copywriting, image/video generation, compliance checks, and multi-platform listing - all orchestrated by a LangGraph state graph, with a DevTools-style workbench to observe every Agent's prompts and collaboration in real time.

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔬 **Observable Workbench** | DAG flowchart (AntV G6) + prompt traces + real-time WebSocket collaboration |
| 🤖 **Multi-Agent** | 7 visual + 4 listing + 3 RAG + 3 knowledge agents |
| 🔄 **LangGraph Workflows** | Conditional routing, parallel execution, state checkpoints, stream-mode callbacks |
| 🖼️ **Image Gen** | DashScope Wanx (`wanx-v1` / `wan2.7-image-pro`), async_call + wait |
| 🎬 **Video Gen** | Kling AI (`kling-v1`), JWT auth + async task polling |
| 📚 **RAG** | PGVector + BGE-large-zh / Qwen text-embedding-v3 |
| 🕸️ **Graph RAG** | Knowledge graph entities/edges + CategoryMemory + RRF fusion |
| ✅ **Compliance** | Ad law forbidden words + platform rule validation |
| 🌐 **Multi-Platform** | Amazon / eBay / Shopify adapters |
| 🔄 **Dual LLM** | Bailian OpenAI-compatible (ChatOpenAI) + DashScope SDK (ChatTongyi) |
| 📊 **Tracking** | Token stats, dual-currency (USD/CNY) budgeting, content search |
| 🔐 **Auth** | API Token (SHA256 + Scope) + Multi-tenant isolation |
| 🛡️ **Graceful Degradation** | Auto-mock without API keys, LLM fallback chain |
| 🎨 **Dashboard** | Vue 3 + Element Plus, 15 pages |

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Vue 3 Dashboard (15 pages)                │
│  Dashboard │ Products │ Tasks │ Knowledge │ Listing │ AI Chat │
│         │          │ Observable Workbench │          │        │
└──────────────────────────┬───────────────────────────────────┘
                           │ REST API / WebSocket
┌──────────────────────────▼───────────────────────────────────┐
│                     FastAPI API Layer (40+ endpoints)          │
│  Auth: API Token (SHA256 + Scope)   Tenant: tenant_id         │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                   LangGraph Workflow Engine                    │
│                                                               │
│  Visual: Orchestrator -> ReqAnalyzer -> CreativePlanner         │
│        -> VisualDesigner -> [ImageGen | VideoGen] -> Reviewer     │
│                                                               │
│  Listing: ImportProduct -> [AssetOptimizer | Copywriter]       │
│         -> Compliance                                            │
│                                                               │
│  Knowledge: QueryAnalyzer -> StrategyRouter -> HybridRetriever  │
│           -> Fuser                                               │
└───────┬──────────────┬──────────────┬────────────────────────┘
        │              │              │
 ┌──────▼──────┐ ┌─────▼─────┐ ┌─────▼──────┐
 │ Qwen/Bailian│ │  DashScope │ │  Kling AI   │
 │ (OpenAI cmp)│ │  (Wanx)    │ │  (Video)    │
 └──────┬──────┘ └─────┬─────┘ └─────┬──────┘
        │              │              │
 ┌──────▼──────────────▼──────────────▼────────┐
 │  PostgreSQL + PGVector  │  Redis  │  Storage │
 └─────────────────────────────────────────────┘
```

## ⚡ Quick Start

```bash
git clone https://github.com/JianFeiGan/agent_part.git
cd agent_part
cp .env.example .env  # Edit with your API keys
docker compose up -d
# Frontend:  http://localhost:3000
# API Docs:  http://localhost:8000/docs
```

> 🛡️ No API key? Set `ALLOW_MOCK_ASSETS=true` to auto-fallback to Mock mode and explore the full workflow without real keys.

## ⚙️ Environment Variables

**Required:**

| Variable | Description |
|----------|-------------|
| `QWEN_API_KEY` | Bailian API Key (supports both OpenAI-compatible and DashScope) |

**Optional:** See [`.env.example`](.env.example) for the full list (LLM provider, embedding, RAG, storage, etc.).

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Workflow** | LangChain, LangGraph |
| **Backend** | FastAPI, Pydantic v2, SQLAlchemy 2.0 (async) |
| **LLM** | Qwen/Bailian (OpenAI-compatible + DashScope SDK) |
| **Image** | DashScope Wanx (`wanx-v1`, `wan2.7-image-pro`) |
| **Video** | Kling AI (`kling-v1`) |
| **Vector** | PGVector, BGE-large-zh, Qwen text-embedding-v3 |
| **Graph** | Graph RAG (entities/relations/communities/summaries) |
| **Frontend** | Vue 3, TypeScript, Element Plus, Pinia, AntV G6 |
| **Database** | PostgreSQL 16 + PGVector, Redis 6 |
| **Storage** | Local filesystem / Alibaba Cloud OSS |
| **Deploy** | Docker Compose, Nginx |

## 🧪 Development

```bash
uv run pytest                    # Run tests
uv run pytest --cov=src          # With coverage
uv run ruff format .             # Format code
uv run ruff check .              # Lint
uv run mypy src/                 # Type check
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## 🗺️ Roadmap

- [x] **v0.1.0** - LangGraph 7-Agent visual workflow + RAG + compliance + Vue 3 dashboard
- [x] **v0.2.0** - Qwen/Bailian integration + AI conversation tracking + observable workbench
- [ ] **v0.3.0** - Advanced RAG (HyDE / multi-query) + GraphRAG + production listing + image RAG
- [ ] **v1.0.0** - Multi-tenant SaaS + plugin Agent marketplace + full production readiness

## 🤝 Contributing

Contributions welcome! Read [CONTRIBUTING.md](CONTRIBUTING.md), then open an [Issue](https://github.com/JianFeiGan/agent_part/issues) or submit a PR.

## 📄 License

[Apache License 2.0](LICENSE)

---

<div align="center">

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=JianFeiGan/agent_part&type=Date)](https://star-history.com/#JianFeiGan/agent_part&Date)

**If this project helps you, please consider giving it a star!** ⭐

</div>
