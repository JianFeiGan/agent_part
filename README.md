<div align="center">

# 🤖 Agent Part

**基于 LangGraph 的多 Agent 协作商品视觉生成系统**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue-3.4-42b883)](https://vuejs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-powered-orange)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED)](https://www.docker.com/)

[English](#english) | [中文](#中文)

</div>

---

<a name="中文"></a>

## ✨ 这是什么？

Agent Part 是一个面向跨境电商的 **多 Agent 协作系统**，利用 LangGraph 状态图驱动多个专业 Agent 协同工作，自动完成从商品分析到视觉内容生成、合规检查、多平台刊登的全流程。

- 📦 **商品信息分析** — Agent 自动提取卖点、分析竞品、识别目标人群
- ✍️ **AI 文案生成** — 多语言商品描述、平台风格适配、LLM 降级策略
- 🖼️ **图片生成** — DashScope 万象 API（wanx-v1 / wan2.7-image-pro）
- 🎬 **视频生成** — 可灵 AI 分镜设计 + 视频生成
- ✅ **合规检查** — 广告法禁词检测、平台规则验证
- 🌐 **多平台刊登** — Amazon / eBay / Shopify 适配器，凭证加密存储
- 📚 **RAG 知识增强** — PGVector 向量检索 + Graph RAG + CategoryMemory
- 📊 **AI 会话追踪** — Token 消耗统计、双币种费用预算、内容检索

> 💡 **适合谁？** 跨境电商从业者、AI 应用开发者、LangChain/LangGraph 学习者

---

## 🚀 核心特性

| 特性 | 描述 |
|------|------|
| 🤖 **多 Agent 协作** | 7 个视觉生成 Agent + 4 个刊登 Agent + 3 个 RAG 增强 Agent + 3 个知识库 Agent |
| 🔄 **LangGraph 工作流** | 条件路由、并行执行、状态检查点、RAG 动态注入 |
| 🖼️ **图片生成** | DashScope 万象（wanx-v1 / wan2.7-image-pro），async_call + wait 模式 |
| 🎬 **视频生成** | 可灵 AI（kling-v1），HS256 JWT 鉴权 + 异步任务轮询 |
| 📚 **RAG 增强** | PGVector + BGE-large-zh / 千问 text-embedding-v3 双通道 Embedding |
| 🕸️ **Graph RAG** | 知识图谱实体/边 + CategoryMemory + 混合检索（RRF 融合） |
| ✅ **合规检查** | 广告法禁词检测 + 平台规则验证 |
| 🌐 **多平台刊登** | Amazon / eBay / Shopify 适配器 |
| 🔄 **双 LLM 通道** | 百炼 OpenAI 兼容（ChatOpenAI）+ DashScope SDK（ChatTongyi） |
| 📊 **会话追踪** | Token 统计、双币种（USD/CNY）费用预算、内容搜索 |
| 🔐 **认证鉴权** | API Token（SHA256 + Scope 权限）+ 多租户隔离 |
| 🛡️ **优雅降级** | 无 API Key 时自动 Mock，LLM 降级链（通义 → Claude → 规则） |
| 🎨 **管理后台** | Vue 3 + Element Plus，14 个页面 |

---

## 🏗️ 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                     Vue 3 管理后台 (14 页面)                  │
│  仪表盘 │ 商品管理 │ 任务管理 │ 知识库 │ 刊登工具 │ AI 会话    │
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
│  Orchestrator → ReqAnalyzer → CreativePlanner → VisualDesigner│
│       → [ImageGen | VideoGen] → QualityReviewer → END         │
│                                                               │
│  刊登工作流:                                                    │
│  ImportProduct → [AssetOptimizer | Copywriter] → Compliance   │
│                                                               │
│  知识库 Agent 工作流:                                           │
│  QueryAnalyzer → StrategyRouter → HybridRetriever → Fuser     │
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
# 前端: http://localhost:3000
# 后端 API 文档: http://localhost:8000/docs
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
| `DASHSCOPE_API_KEY` | — | DashScope API Key（可与 QWEN_API_KEY 共用） |
| `QWEN_LLM_MODEL` | `qwen-plus` | LLM 模型名称 |
| `KLING_ACCESS_KEY` | — | 可灵 AI Access Key |
| `KLING_SECRET_KEY` | — | 可灵 AI Secret Key |
| `EMBEDDING_PROVIDER` | `local` | Embedding 提供商：`local`（BGE-large-zh）或 `qwen` |
| `EMBEDDING_MODEL` | `BAAI/bge-large-zh` | 本地 Embedding 模型名称 |
| `RAG_ENABLED` | `true` | 启用 RAG 知识检索 |
| `RETRIEVAL_TOP_K` | `5` | 检索返回数量 |
| `SIMILARITY_THRESHOLD` | `0.7` | 相似度阈值 |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL 连接 URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接 URL |
| `STORAGE_TYPE` | `local` | 存储类型：`local` 或 `oss` |
| `ALLOW_MOCK_ASSETS` | `true` | 无 API Key 时允许 Mock 降级 |

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
│       ├── views/                # 页面组件 (14个)
│       ├── api/                  # API 调用层
│       ├── types/                # TypeScript 类型
│       ├── stores/               # Pinia 状态管理
│       └── styles/               # 全局样式 (CSS 变量设计系统)
├── tests/                        # 测试用例
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
| **图片生成** | DashScope 万象 (wanx-v1, wan2.7-image-pro) |
| **视频生成** | 可灵 AI (kling-v1) |
| **向量检索** | PGVector, BGE-large-zh, 千问 text-embedding-v3 |
| **图谱检索** | Graph RAG (实体/关系/社区/摘要) |
| **前端框架** | Vue 3, TypeScript, Element Plus, Pinia |
| **数据库** | PostgreSQL 16 + PGVector, Redis 6 |
| **存储** | 本地文件系统 / 阿里云 OSS |
| **部署** | Docker Compose, Nginx |

---

## 🧪 开发

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

## 📄 License

[MIT License](LICENSE)

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=JianFeiGan/agent_part&type=Date)](https://star-history.com/#JianFeiGan/agent_part&Date)

---

<a name="english"></a>

## 🤖 Agent Part

**Multi-Agent E-commerce Visual Content Generator powered by LangGraph**

A multi-agent collaboration system that automates the generation of marketing visual content for cross-border e-commerce products — from product analysis to image/video generation, compliance checking, and multi-platform listing.

- 📦 **Product Analysis** — Agents extract selling points, analyze competitors, identify target audiences
- ✍️ **AI Copywriting** — Multi-language descriptions, platform-style adaptation, LLM fallback chain
- 🖼️ **Image Generation** — DashScope Wanx API (wanx-v1 / wan2.7-image-pro)
- 🎬 **Video Generation** — Kling AI storyboard design + video generation
- ✅ **Compliance Check** — Ad law forbidden words, platform rule validation
- 🌐 **Multi-Platform Listing** — Amazon / eBay / Shopify adapters with encrypted credentials
- 📚 **RAG Enhancement** — PGVector + Graph RAG + CategoryMemory
- 📊 **Conversation Tracking** — Token stats, dual-currency (USD/CNY) budgeting, content search

### Key Features

| Feature | Description |
|---------|-------------|
| 🤖 **Multi-Agent** | 7 visual + 4 listing + 3 RAG + 3 knowledge agents |
| 🔄 **LangGraph Workflows** | Conditional routing, parallel execution, state checkpoints |
| 🖼️ **Image Gen** | DashScope Wanx (wanx-v1 / wan2.7-image-pro), async_call + wait |
| 🎬 **Video Gen** | Kling AI (kling-v1), JWT auth + async task polling |
| 📚 **RAG** | PGVector + BGE-large-zh / Qwen text-embedding-v3 |
| 🕸️ **Graph RAG** | Knowledge graph entities/edges + CategoryMemory + RRF fusion |
| ✅ **Compliance** | Ad law forbidden words + platform rule validation |
| 🌐 **Multi-Platform** | Amazon / eBay / Shopify adapters |
| 🔄 **Dual LLM** | Bailian OpenAI-compatible (ChatOpenAI) + DashScope SDK (ChatTongyi) |
| 📊 **Tracking** | Token stats, dual-currency budgeting, content search |
| 🔐 **Auth** | API Token (SHA256 + Scope) + Multi-tenant isolation |
| 🛡️ **Graceful Degradation** | Auto-mock without API keys, LLM fallback chain |
| 🎨 **Dashboard** | Vue 3 + Element Plus, 14 pages |

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Vue 3 Dashboard (14 pages)                │
│  Dashboard │ Products │ Tasks │ Knowledge │ Listing │ AI Chat │
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
│  Visual Generation:                                            │
│  Orchestrator → ReqAnalyzer → CreativePlanner → VisualDesigner│
│       → [ImageGen | VideoGen] → QualityReviewer → END         │
│                                                               │
│  Listing:                                                      │
│  ImportProduct → [AssetOptimizer | Copywriter] → Compliance   │
│                                                               │
│  Knowledge Agent:                                              │
│  QueryAnalyzer → StrategyRouter → HybridRetriever → Fuser     │
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

### Quick Start

```bash
git clone https://github.com/JianFeiGan/agent_part.git
cd agent_part
cp .env.example .env  # Edit with your API keys
docker compose up -d
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

### Environment Variables

**Required:**

| Variable | Description |
|----------|-------------|
| `QWEN_API_KEY` | Bailian API Key (supports both OpenAI-compatible and DashScope) |

**Optional:**

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `dashscope` | `qwen` (Bailian OpenAI-compatible) or `dashscope` |
| `QWEN_API_BASE` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | Bailian OpenAI-compatible endpoint |
| `DASHSCOPE_API_KEY` | — | DashScope API Key (can share QWEN_API_KEY) |
| `KLING_ACCESS_KEY` | — | Kling AI Access Key |
| `KLING_SECRET_KEY` | — | Kling AI Secret Key |
| `QWEN_LLM_MODEL` | `qwen-plus` | LLM model name |
| `EMBEDDING_PROVIDER` | `local` | `local` (BGE-large-zh) or `qwen` |
| `EMBEDDING_MODEL` | `BAAI/bge-large-zh` | Local Embedding model name |
| `RAG_ENABLED` | `true` | Enable RAG retrieval |
| `RETRIEVAL_TOP_K` | `5` | Number of retrieval results |
| `SIMILARITY_THRESHOLD` | `0.7` | Similarity threshold |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `STORAGE_TYPE` | `local` | `local` or `oss` |
| `ALLOW_MOCK_ASSETS` | `true` | Allow mock fallback without API keys |

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **Workflow** | LangChain, LangGraph |
| **Backend** | FastAPI, Pydantic v2, SQLAlchemy 2.0 (async) |
| **LLM** | Qwen/Bailian (OpenAI-compatible + DashScope SDK) |
| **Image** | DashScope Wanx (wanx-v1, wan2.7-image-pro) |
| **Video** | Kling AI (kling-v1) |
| **Vector** | PGVector, BGE-large-zh, Qwen text-embedding-v3 |
| **Graph** | Graph RAG (entities/relations/communities/summaries) |
| **Frontend** | Vue 3, TypeScript, Element Plus, Pinia |
| **Database** | PostgreSQL 16 + PGVector, Redis 6 |
| **Storage** | Local filesystem / Alibaba Cloud OSS |
| **Deploy** | Docker Compose, Nginx |

### Development

```bash
uv run pytest                    # Run tests
uv run pytest --cov=src          # With coverage
uv run ruff format .             # Format code
uv run ruff check .              # Lint
uv run mypy src/                 # Type check
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

### License

[MIT License](LICENSE)
