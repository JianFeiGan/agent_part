<div align="center">

# 🤖 Agent Part

**基于 LangGraph 的多Agent协作商品视觉生成系统**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Version 0.2.0](https://img.shields.io/badge/Version-0.2.0-blueviolet)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![LangGraph](https://img.shields.io/badge/LangGraph-powered-orange)](https://langchain-ai.github.io/langgraph/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue-3.4-42b883)](https://vuejs.org/)

[English](#english) | [中文](#中文)

</div>

---

<a name="中文"></a>

## ✨ 这是什么？

Agent Part 是一个**多 Agent 协作系统**，能自动完成跨境电商商品的视觉内容生成：

- 📦 **商品信息分析** — 自动提取卖点、分析竞品
- ✍️ **AI 文案生成** — 多语言商品描述、营销文案
- 🖼️ **图片/视频生成** — 主图、场景图、卖点图 + 分镜视频
- ✅ **合规检查** — 广告法禁词检测、平台规则验证
- 🌐 **多平台刊登** — Amazon / eBay / Shopify 适配器
- 📊 **AI 会话追踪** — Token 消耗统计、费用预算、内容检索

> 💡 **适合谁？** 跨境电商从业者、AI 应用开发者、LangChain/LangGraph 学习者

## 🚀 核心特性

| 特性 | 描述 |
|------|------|
| 🤖 **多Agent协作** | 7个专业Agent协同，LangGraph 状态图驱动 |
| 🖼️ **图片生成** | DashScope 万象图片生成（wanx-v1 / wan2.7-image-pro） |
| 🎬 **视频生成** | 可灵 AI 分镜设计 + 视频生成 |
| ✅ **合规检查** | 广告法禁词检测、平台规则验证 |
| 📚 **RAG 增强** | PGVector 知识库检索，BGE/千问 Embedding |
| 🌐 **多平台适配** | Amazon/eBay/Shopify 适配器 |
| 🔄 **多LLM路由** | 百炼 OpenAI 兼容 / DashScope SDK 双通道 |
| 📊 **会话追踪** | Token 统计、费用预算、内容搜索 |
| 🎨 **管理后台** | Vue 3 + Element Plus 全功能前端 |

## 📋 实现状态

| 功能模块 | 状态 | 说明 |
|----------|------|------|
| FastAPI API 服务 | ✅ 已实现 | 40+ REST API 端点 |
| LangGraph 多 Agent 工作流 | ✅ 已实现 | 7节点状态图 + 条件路由，E2E 验证通过 |
| 千问百炼 LLM 对接 | ✅ 已实现 | OpenAI 兼容模式 + DashScope SDK 双通道 |
| 图片生成 | ✅ 已实现 | DashScope 万象，支持新旧模型自动切换 |
| 视频生成 | ⚠️ Mock | 可灵 AI 客户端已实现，无 Key 时降级为 Mock |
| RAG 检索 | ✅ 已实现 | PGVector + BGE-large-zh / 千问 text-embedding-v3 |
| Graph RAG | ⚠️ P0底座 | 轻量知识图谱，无自动实体抽取 |
| AI 会话追踪 | ✅ 已实现 | Token/费用/延迟统计 + 预算分析 + 内容搜索 |
| 多平台刊登 | ⚠️ 适配器骨架 | Amazon/eBay/Shopify 接口框架 |
| 合规检查 | ✅ 已实现 | 广告法禁词 + 平台规则 |
| 前端界面 | ✅ 已实现 | Vue 3 管理后台（14个页面） |

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    Vue 3 管理后台                         │
│  仪表盘 | 商品管理 | 任务管理 | 知识库 | 刊登工具 | AI会话  │
└────────────────────────┬────────────────────────────────┘
                         │ REST API / WebSocket
┌────────────────────────▼────────────────────────────────┐
│                   FastAPI API 层                          │
│  /products  /tasks  /knowledge  /listing  /ai  /dashboard│
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              LangGraph 工作流引擎                         │
│                                                          │
│  Orchestrator → RequirementAnalyzer → CreativePlanner   │
│       → VisualDesigner → [ImageGen | VideoGen]          │
│       → QualityReviewer → END                            │
│                                                          │
│  ListingWorkflow:                                        │
│  ImportProduct → [AssetOptimizer | Copywriter]           │
│       → ComplianceCheck → END                            │
└──────────┬──────────────┬──────────────┬────────────────┘
           │              │              │
    ┌──────▼──────┐ ┌─────▼─────┐ ┌─────▼──────┐
    │  千问百炼    │ │  DashScope │ │  可灵 AI    │
    │ (OpenAI兼容) │ │  (万象图片) │ │  (视频生成)  │
    └─────────────┘ └───────────┘ └────────────┘
           │              │              │
    ┌──────▼──────────────▼──────────────▼────────┐
    │     PostgreSQL + PGVector  |  Redis          │
    └─────────────────────────────────────────────┘
```

## ⚡ 快速开始

### 方式一：Docker 启动（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/JianFeiGan/agent_part.git
cd agent_part

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 API Key

# 3. 启动所有服务
docker compose up -d

# 4. 访问
# 前端: http://localhost:3000
# 后端: http://localhost:8000
# API 文档: http://localhost:8000/docs
```

### 方式二：手动安装（开发）

```bash
# 1. 克隆仓库
git clone https://github.com/JianFeiGan/agent_part.git
cd agent_part

# 2. 安装依赖
uv sync

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 API Key

# 4. 启动 API 服务
uv run python main.py
```

### 环境变量

```bash
# ===== 必填 =====
# LLM 提供商: qwen (百炼 OpenAI 兼容) 或 dashscope
LLM_PROVIDER=qwen
QWEN_API_KEY=your_qwen_api_key
QWEN_API_BASE=https://your-bailian-endpoint/compatible-mode/v1

# ===== 可选 =====
DASHSCOPE_API_KEY=your_dashscope_api_key
KLING_ACCESS_KEY=your_kling_access_key
KLING_SECRET_KEY=your_kling_secret_key
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/agent_part
REDIS_URL=redis://localhost:6379/0
```

## 📊 版本历史

### v0.2.0 (2026-07-13)

**千问百炼全链路对接 + AI 会话追踪 + 前端升级**

- 🔌 **千问百炼 API 对接** — OpenAI 兼容模式 (ChatOpenAI) + DashScope SDK (ChatTongyi) 双通道路由
- 🔑 **API Key 统一** — 百炼平台单一 Key 同时支持 OpenAI 兼容和 DashScope 原生协议
- 🖼️ **图片生成升级** — DashScope 新模型 (wan2.7-image-pro) async_call + wait 模式，旧模型 call 模式自动切换
- 📊 **AI 会话追踪** — 新增 5 个 API 端点：会话记录查询、详情、内容搜索、使用量概览、费用预算
- 💰 **费用预算系统** — 模型定价表 + 双币种 (USD/CNY) + 日/月预算 + 预估月费
- 🎨 **前端样式升级** — 深空蓝配色体系、玻璃拟态头部、DM Sans 字体、精致微交互
- 📄 **新增页面** — AI 会话记录页（记录列表 + 使用分析 + 费用预算三 Tab）
- 🛡️ **防御性修复** — Visual Designer JSON 解析容错、selling_points 格式兼容、SimpleNamespace mock 兼容
- 🔄 **Listing 工作流** — create_task 端点异步触发 ListingWorkflow 执行

### v0.1.0 (2026-03-23)

**初始版本**

- 🏗️ LangGraph 7-Agent 协作工作流
- 📚 RAG 知识库 (PGVector + BGE-large-zh)
- ✅ 合规检查系统
- 🌐 多平台刊登适配器骨架
- 🖥️ Vue 3 管理后台

## 🧪 运行测试

```bash
# 运行所有测试
uv run pytest

# 带覆盖率报告
uv run pytest --cov=src --cov-report=html

# 代码格式化
uv run ruff format .

# Lint 检查
uv run ruff check .
```

## 📁 项目结构

```
agent_part/
├── src/                          # 后端源码
│   ├── agents/                   # Agent 实现 (7核心 + 3 RAG + 5 Listing)
│   ├── graph/                    # LangGraph 状态图与工作流
│   ├── api/                      # FastAPI 路由 + Schema + Service
│   │   ├── router/               #   路由模块 (conversation, knowledge, listing...)
│   │   ├── schema/               #   请求/响应模型
│   │   └── service/              #   业务服务 (conversation_recorder...)
│   ├── clients/                  # 外部服务客户端
│   │   ├── dashscope_image_client.py  # DashScope 图片生成
│   │   ├── qwen_llm_client.py        # 千问 LLM
│   │   └── qwen_embedding_client.py  # 千问 Embedding
│   ├── config/                   # 配置管理 (pydantic-settings)
│   ├── db/                       # 数据库模型 + 连接池
│   ├── rag/                      # RAG 检索管道
│   ├── knowledge/                # 知识图谱 + 混合检索
│   ├── models/                   # Pydantic 数据模型
│   └── storage/                  # 文件存储 (本地/OSS)
├── frontend/                     # Vue 3 前端
│   └── src/
│       ├── views/                # 页面组件 (14个)
│       ├── components/Layout/    # 布局 (Sidebar + Header)
│       ├── api/                  # API 调用层
│       ├── types/                # TypeScript 类型
│       ├── stores/               # Pinia 状态管理
│       └── styles/               # 全局样式 (CSS 变量设计系统)
├── tests/                        # 测试用例 (223+)
├── docker-compose.yml            # Docker 编排
├── Dockerfile                    # 后端镜像
├── Dockerfile.frontend           # 前端镜像
└── pyproject.toml                # 项目配置
```

## 🤝 贡献

我们欢迎各种形式的贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详情。

## 📄 License

MIT License — 详见 [LICENSE](LICENSE)

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=JianFeiGan/agent_part&type=Date)](https://star-history.com/#JianFeiGan/agent_part&Date)

---

<a name="english"></a>

## 🤖 Agent Part

**Multi-Agent E-commerce Visual Content Generator powered by LangGraph**

A multi-agent collaboration system that automates the generation of marketing visual content for cross-border e-commerce products.

### Key Features

- 🤖 **Multi-Agent Architecture** — 7 specialized agents orchestrated by LangGraph
- 🖼️ **Image Generation** — DashScope Wanx (wanx-v1 / wan2.7-image-pro)
- 🎬 **Video Generation** — Kling AI storyboard + video generation
- ✅ **Compliance Check** — Ad law forbidden words, platform rule validation
- 📚 **RAG Enhancement** — PGVector + BGE/Qwen Embedding
- 🌐 **Multi-Platform** — Amazon / eBay / Shopify adapters
- 🔄 **Dual LLM Channel** — Bailian OpenAI-compatible + DashScope SDK
- 📊 **Conversation Tracking** — Token stats, cost budgeting, content search
- 🎨 **Admin Dashboard** — Vue 3 + Element Plus (14 pages)

### Quick Start

```bash
git clone https://github.com/JianFeiGan/agent_part.git
cd agent_part
cp .env.example .env  # Edit with your API keys
docker compose up -d
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

### Tech Stack

- **Python 3.11+** | **LangChain** | **LangGraph** | **FastAPI**
- **Qwen/Bailian** | **DashScope** | **Kling AI**
- **Vue 3** | **TypeScript** | **Element Plus**
- **PostgreSQL** | **PGVector** | **Redis**

### Version History

- **v0.2.0** — Bailian API integration, AI conversation tracking, frontend upgrade
- **v0.1.0** — Initial release with LangGraph workflow, RAG, compliance check

### License

MIT
