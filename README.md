<div align="center">

# 🤖 Agent Part

**基于 LangGraph 的多Agent协作商品视觉生成系统**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-112%20passed-brightgreen)]()
[![LangGraph](https://img.shields.io/badge/LangGraph-powered-orange)](https://langchain-ai.github.io/langgraph/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal)](https://fastapi.tiangolo.com/)

[English](#english) | [中文](#中文)

</div>

---

<a name="中文"></a>

## ✨ 这是什么？

Agent Part 是一个**多 Agent 协作系统**，能自动完成跨境电商商品的视觉内容生成：

- 📦 **商品信息分析** — 自动提取卖点、分析竞品
- ✍️ **AI 文案生成** — 多语言商品描述、营销文案
- ✅ **合规检查** — 广告法禁词检测、平台规则验证
- 🌐 **多平台刊登** — Amazon / eBay / Shopify 一键推送

> 💡 **适合谁？** 跨境电商从业者、AI 应用开发者、LangChain/LangGraph 学习者

## 🚀 核心特性

| 特性 | 描述 |
|------|------|
| 🤖 **多Agent协作** | 7个专业Agent协同，LangGraph 状态图驱动 |
| 🖼️ **智能图片生成** | 主图、场景图、卖点图自动生成 |
| 🎬 **视频分镜** | 智能分镜设计 + 视频合成 |
| ✅ **合规检查** | 广告法禁词检测、平台规则验证 |
| 📚 **RAG 增强** | 企业知识库检索，提升生成质量 |
| 🌐 **多平台适配** | Amazon/eBay/Shopify 一键刊登 |
| 🔄 **多LLM降级** | Tongyi → Claude → Rules 自动降级 |

## 🏗️ 系统架构

```mermaid
graph TB
    subgraph Frontend["🖥️ 前端 (Vue 3)"]
        UI[商品录入 · 任务管理 · 结果展示]
    end

    subgraph API["⚡ API 层 (FastAPI)"]
        Routes[REST API 端点]
    end

    subgraph Workflow["🔄 工作流引擎 (LangGraph)"]
        O[需求分析] --> CP[创意策划]
        CP --> VD[视觉设计]
        VD --> IG[图片生成]
        VD --> VG[视频生成]
        IG --> QC[质量审核]
        VG --> QC
    end

    subgraph Agents["🤖 Agent 层"]
        A1[ImportProduct]
        A2[AssetOptimizer]
        A3[Copywriter]
        A4[ComplianceChecker]
        A5[PlatformAdapter]
    end

    subgraph External["☁️ 外部服务"]
        DS[DashScope]
        KL[Kling AI]
        PG[(PostgreSQL)]
        RD[(Redis)]
    end

    UI --> Routes
    Routes --> O
    QC --> A1
    QC --> A2
    QC --> A3
    QC --> A4
    QC --> A5
    A1 --> DS
    A1 --> PG
    A2 --> DS
    A3 --> KL
    A4 --> PG
    A5 --> RD
```

## ⚡ 快速开始

### 方式一：手动安装（推荐开发）

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

### 方式二：Docker 启动

```bash
git clone https://github.com/JianFeiGan/agent_part.git
cd agent_part
cp .env.example .env
# 编辑 .env，填入 API Key
docker compose up -d
# 访问 http://localhost
```

### 环境变量

```bash
# 必填
DASHSCOPE_API_KEY=your_dashscope_api_key
KLING_ACCESS_KEY=your_kling_access_key
KLING_SECRET_KEY=your_kling_secret_key

# 可选
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/agent_part
```

## 📊 为什么选择 Agent Part？

| 对比项 | Agent Part | 同类项目 |
|--------|-----------|----------|
| 多Agent协作 | ✅ LangGraph 状态图 | ❌ 单Agent |
| 多平台支持 | ✅ Amazon/eBay/Shopify | ❌ 单平台 |
| 合规检查 | ✅ 内置 | ❌ 需额外集成 |
| RAG 增强 | ✅ PGVector | ❌ 无 |
| 测试覆盖 | ✅ 112 个测试 | ❌ 无测试 |
| 前端界面 | ✅ Vue 3 管理后台 | ❌ 仅 API |

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

## 📖 文档

- [AGENTS.md](AGENTS.md) — 完整架构文档
- [开发计划](documents/商品视觉生成系统开发计划_2026-03-23.md) — 开发路线图
- [操作文档](documents/操作文档.md) — 使用指南

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
- 🖼️ **Smart Image Generation** — Main images, scene images, selling point images
- 🎬 **Video Storyboard** — Intelligent storyboard design + video synthesis
- ✅ **Compliance Check** — Ad law forbidden words, platform rule validation
- 📚 **RAG Enhancement** — Enterprise knowledge base retrieval
- 🌐 **Multi-Platform** — Amazon / eBay / Shopify one-click listing

### Quick Start

```bash
git clone https://github.com/JianFeiGan/agent_part.git
cd agent_part
uv sync
cp .env.example .env
uv run python main.py
```

### Tech Stack

- **Python 3.11+** | **LangChain** | **LangGraph** | **FastAPI**
- **Vue 3** | **TypeScript** | **Element Plus**
- **PostgreSQL** | **PGVector** | **Redis**

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

### License

MIT
