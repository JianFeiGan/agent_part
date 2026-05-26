# GitHub 可见性提升与开源产品化 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 通过 GitHub 展示优化、产品化包装、社区推广三阶段，将 agent_part 项目从 5 stars 提升到 100+ stars

**Architecture:** 三阶段递进 — Phase 1 优化展示提升转化率，Phase 2 降低门槛吸引使用者，Phase 3 主动推广带来流量

**Tech Stack:** Markdown, YAML, Docker, MkDocs Material, GitHub API

**Design Spec:** `docs/superpowers/specs/2026-05-26-github-visibility-design.md`

---

## Phase 1: GitHub 展示优化（优先级最高）

### Task 1: 创建 GitHub 社区文件

**Files:**
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `.github/ISSUE_TEMPLATE/bug_report.md`
- Create: `.github/ISSUE_TEMPLATE/feature_request.md`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`

- [ ] **Step 1: 创建 CONTRIBUTING.md**

```markdown
# 贡献指南

感谢你对 Agent Part 项目的关注！我们欢迎各种形式的贡献。

## 如何贡献

### 报告 Bug

使用 [Bug Report](https://github.com/JianFeiGan/agent_part/issues/new?template=bug_report.md) 模板提交 Issue。

### 提交功能请求

使用 [Feature Request](https://github.com/JianFeiGan/agent_part/issues/new?template=feature_request.md) 模板提交 Issue。

### 提交代码

1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交你的改动 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 开发环境

```bash
# 克隆仓库
git clone https://github.com/JianFeiGan/agent_part.git
cd agent_part

# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env

# 运行测试
uv run pytest

# 代码格式化
uv run ruff format .

# Lint 检查
uv run ruff check .
```

## 代码规范

- 遵循 PEP 8，使用 `ruff format` 格式化
- 所有公共函数必须有类型注解
- 使用 Google 风格 docstring
- 提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范

## 提交信息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

类型：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建/工具相关

## Pull Request 规范

- PR 标题简洁明了
- 描述中说明改动的原因和内容
- 确保所有测试通过
- 确保代码格式符合规范
- 关联相关的 Issue

## 行为准则

- 尊重他人，保持友善
- 建设性地讨论问题
- 欢迎新手提问
```

- [ ] **Step 2: 创建 SECURITY.md**

```markdown
# 安全策略

## 报告漏洞

如果你发现安全漏洞，请**不要**在公开 Issue 中报告。

请发送邮件至 [security@example.com]，包含：

1. 漏洞描述
2. 复现步骤
3. 影响范围
4. 建议的修复方案（如有）

我们会在 48 小时内回复，并在修复后发布安全更新。

## 支持的版本

| 版本 | 支持状态 |
|------|----------|
| 1.0.x | ✅ 支持 |
| < 1.0  | ❌ 不支持 |

## 安全最佳实践

- 不要在代码中硬编码 API Key
- 使用环境变量管理敏感配置
- 定期更新依赖以获取安全补丁
- 在生产环境中使用 HTTPS
```

- [ ] **Step 3: 创建 Bug Report 模板**

创建目录 `.github/ISSUE_TEMPLATE/`，然后创建文件：

```markdown
---
name: Bug Report
about: 报告一个 Bug
title: '[Bug] '
labels: bug
assignees: ''
---

## Bug 描述

简要描述 Bug 是什么。

## 复现步骤

1. 运行 '...'
2. 点击 '...'
3. 看到错误 '...'

## 期望行为

描述你期望发生什么。

## 实际行为

描述实际发生了什么。

## 环境信息

- OS: [e.g., macOS 14.0]
- Python: [e.g., 3.13]
- Agent Part 版本: [e.g., 1.0.0]

## 日志/错误信息

```
粘贴相关的日志或错误信息
```

## 补充信息

其他有助于诊断问题的信息。
```

- [ ] **Step 4: 创建 Feature Request 模板**

```markdown
---
name: Feature Request
about: 提出一个新功能建议
title: '[Feature] '
labels: enhancement
assignees: ''
---

## 功能描述

简要描述你希望添加的功能。

## 使用场景

描述这个功能解决什么问题，或者在什么场景下需要它。

## 建议方案

描述你希望如何实现这个功能。

## 替代方案

描述你考虑过的其他解决方案。

## 补充信息

其他有助于理解需求的信息。
```

- [ ] **Step 5: 创建 PR 模板**

```markdown
## 改动说明

简要描述这个 PR 做了什么。

## 改动类型

- [ ] 新功能
- [ ] Bug 修复
- [ ] 文档更新
- [ ] 代码重构
- [ ] 测试相关
- [ ] 其他

## 关联 Issue

Closes #___

## 测试

- [ ] 所有现有测试通过
- [ ] 添加了新测试（如适用）

## 检查清单

- [ ] 代码格式符合规范 (`ruff format .`)
- [ ] Lint 检查通过 (`ruff check .`)
- [ ] 提交信息遵循 Conventional Commits 规范
```

- [ ] **Step 6: 提交社区文件**

```bash
git add CONTRIBUTING.md SECURITY.md .github/
git commit -m "docs: add community files (contributing, security, issue/PR templates)"
```

---

### Task 2: 重构 README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 备份当前 README**

```bash
cp README.md README.md.bak
```

- [ ] **Step 2: 编写新 README**

完整的 README 内容：

```markdown
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
        UI[商品录入 | 任务管理 | 结果展示]
    end

    subgraph API["⚡ API 层 (FastAPI)"]
        Routes[REST API 端点]
    end

    subgraph Workflow["🔄 工作流引擎 (LangGraph)"]
        O[Orchestrator] --> RA[需求分析]
        RA --> CP[创意策划]
        CP --> VD[视觉设计]
        VD --> IG[图片生成]
        VD --> VG[视频生成]
        IG --> QC[质量审核]
        VG --> QC
    end

    subgraph Agents["🤖 Agent 层"]
        direction LR
        A1[ImportProduct]
        A2[AssetOptimizer]
        A3[Copywriter]
        A4[ComplianceChecker]
        A5[PlatformAdapter]
    end

    subgraph External["☁️ 外部服务"]
        DS[DashScope]
        KL[可灵 AI]
        PG[(PostgreSQL)]
        RD[(Redis)]
    end

    Frontend --> API
    API --> Workflow
    Workflow --> Agents
    Agents --> External
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
```

- [ ] **Step 3: 验证 README 渲染**

在 GitHub 上预览 README，确认：
- Badges 正确显示
- Mermaid 图正确渲染
- 链接可点击
- 中英文切换正常

- [ ] **Step 4: 提交 README**

```bash
git add README.md
git commit -m "docs: redesign README with badges, architecture diagram, and feature comparison"
```

---

### Task 3: GitHub SEO 优化

**说明**: 这一步需要在 GitHub 网页上手动操作，无法通过代码完成。

- [ ] **Step 1: 更新 GitHub Topics**

在 GitHub 仓库页面 → Settings → General → Topics，添加：
```
langchain langgraph multi-agent ecommerce cross-border-ecommerce ai-image-generation python fastapi vue3 postgresql pgvector product-automation ai-generated-content
```

- [ ] **Step 2: 更新仓库描述**

在 GitHub 仓库页面 → Settings → General → Description：
```
基于 LangGraph 的多Agent协作商品视觉生成系统 | Multi-Agent E-commerce Visual Content Generator
```

- [ ] **Step 3: 添加 Website（可选）**

如果有文档站点，在 Settings → General → Website 填入 URL。

---

## Phase 2: 产品化包装

### Task 4: Docker Compose 一键启动

**Files:**
- Create: `Dockerfile`
- Create: `Dockerfile.frontend`
- Create: `docker-compose.yml`
- Create: `nginx.conf`
- Create: `init.sql`

- [ ] **Step 1: 创建后端 Dockerfile**

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# 安装 uv
RUN pip install uv

# 复制依赖文件
COPY pyproject.toml uv.lock ./

# 安装依赖
RUN uv sync --frozen --no-dev

# 复制源码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uv", "run", "python", "main.py"]
```

- [ ] **Step 2: 创建前端 Dockerfile**

```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

- [ ] **Step 3: 创建 nginx 配置**

```nginx
server {
    listen 80;
    server_name localhost;

    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://app:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

- [ ] **Step 4: 创建数据库初始化脚本**

```sql
-- init.sql
CREATE EXTENSION IF NOT EXISTS vector;

-- 创建数据库表（根据 src/db/models.py 的定义）
-- 这里列出核心表结构
```

- [ ] **Step 5: 创建 docker-compose.yml**

```yaml
version: "3.8"

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/agent_part
      REDIS_URL: redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    volumes:
      - ./output:/app/output

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "3000:80"
    depends_on:
      - app

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: agent_part
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

- [ ] **Step 6: 更新 .env.example**

在现有 `.env.example` 中添加 Docker 相关注释：

```bash
# === Docker 部署配置 ===
# 使用 Docker 时，数据库和 Redis 连接由 docker-compose 自动配置
# 只需要填写以下 API Key：

# 必填
DASHSCOPE_API_KEY=your_dashscope_api_key
KLING_ACCESS_KEY=your_kling_access_key
KLING_SECRET_KEY=your_kling_secret_key

# === 手动部署配置 ===
# DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/agent_part
# REDIS_URL=redis://localhost:6379/0
```

- [ ] **Step 7: 提交 Docker 配置**

```bash
git add Dockerfile Dockerfile.frontend docker-compose.yml nginx.conf init.sql .env.example
git commit -m "feat: add Docker Compose for one-click deployment"
```

---

### Task 5: MkDocs 文档站点

**Files:**
- Create: `mkdocs.yml`
- Create: `docs-site/index.md`
- Create: `docs-site/getting-started/installation.md`
- Create: `docs-site/getting-started/quickstart.md`
- Create: `docs-site/concepts/architecture.md`

- [ ] **Step 1: 添加 MkDocs 依赖**

```bash
uv add --dev mkdocs mkdocs-material
```

- [ ] **Step 2: 创建 mkdocs.yml**

```yaml
site_name: Agent Part
site_description: 多Agent协作商品视觉生成系统
site_url: https://jianfeigan.github.io/agent_part/
repo_url: https://github.com/JianFeiGan/agent_part
repo_name: JianFeiGan/agent_part

theme:
  name: material
  language: zh
  palette:
    - scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-7
        name: 切换到暗色模式
    - scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-4
        name: 切换到亮色模式
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.expand
    - search.suggest
    - search.highlight
    - content.code.copy

nav:
  - 首页: index.md
  - 快速开始:
    - 安装指南: getting-started/installation.md
    - 5分钟上手: getting-started/quickstart.md
  - 核心概念:
    - 系统架构: concepts/architecture.md
    - Agent 详解: concepts/agents.md
    - 工作流引擎: concepts/workflow.md
    - RAG 知识增强: concepts/rag.md
  - 实战指南:
    - Amazon 刊登: guides/amazon.md
    - eBay 刊登: guides/ebay.md
    - Shopify 刊登: guides/shopify.md
  - API 参考:
    - REST API: api/rest-api.md
    - 数据模型: api/models.md
  - 开发:
    - 贡献指南: development/contributing.md
    - 测试指南: development/testing.md

markdown_extensions:
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.superfences
  - pymdownx.tabbed:
      alternate_style: true
  - admonition
  - pymdownx.details
  - attr_list
  - md_in_html
```

- [ ] **Step 3: 创建文档首页**

```markdown
# Agent Part 文档

欢迎使用 Agent Part — 基于 LangGraph 的多Agent协作商品视觉生成系统。

## 快速开始

- [安装指南](getting-started/installation.md) — 如何安装和配置
- [5分钟上手](getting-started/quickstart.md) — 快速体验核心功能

## 核心概念

- [系统架构](concepts/architecture.md) — 了解整体设计
- [Agent 详解](concepts/agents.md) — 7个专业Agent的工作原理
- [工作流引擎](concepts/workflow.md) — LangGraph 状态图驱动
- [RAG 知识增强](concepts/rag.md) — 知识库检索增强生成

## 实战指南

- [Amazon 刊登](guides/amazon.md) — Amazon SP-API 集成
- [eBay 刊登](guides/ebay.md) — eBay Trading API 集成
- [Shopify 刊登](guides/shopify.md) — Shopify GraphQL 集成
```

- [ ] **Step 4: 创建安装指南**

```markdown
# 安装指南

## 系统要求

- Python 3.11+
- PostgreSQL 14+ (with pgvector extension)
- Redis 7+
- Node.js 18+ (前端开发)

## 方式一：uv 安装（推荐）

```bash
# 克隆仓库
git clone https://github.com/JianFeiGan/agent_part.git
cd agent_part

# 安装 Python 依赖
uv sync

# 配置环境变量
cp .env.example .env
```

## 方式二：Docker 安装

```bash
git clone https://github.com/JianFeiGan/agent_part.git
cd agent_part
cp .env.example .env
docker compose up -d
```

## 环境变量配置

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `DASHSCOPE_API_KEY` | ✅ | 阿里云 DashScope API Key |
| `KLING_ACCESS_KEY` | ✅ | 可灵 AI Access Key |
| `KLING_SECRET_KEY` | ✅ | 可灵 AI Secret Key |
| `DATABASE_URL` | ❌ | PostgreSQL 连接 URL |
| `REDIS_URL` | ❌ | Redis 连接 URL |

## 验证安装

```bash
# 运行测试
uv run pytest

# 启动 API 服务
uv run python main.py

# 访问 http://localhost:8000/health
```
```

- [ ] **Step 5: 创建快速上手指南**

```markdown
# 5分钟上手

## 1. 启动服务

```bash
uv run python main.py
```

## 2. 创建商品

```bash
curl -X POST http://localhost:8000/api/v1/products \
  -H "Content-Type: application/json" \
  -d '{
    "name": "智能运动手表",
    "category": "digital",
    "description": "支持心率监测、睡眠追踪的智能手表"
  }'
```

## 3. 创建生成任务

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "prod_001",
    "task_type": "image_and_video",
    "platform": "amazon"
  }'
```

## 4. 查看任务状态

```bash
curl http://localhost:8000/api/v1/tasks/{task_id}
```

## 下一步

- 了解 [系统架构](../concepts/architecture.md)
- 查看 [Amazon 刊登指南](../guides/amazon.md)
```

- [ ] **Step 6: 创建架构文档**

```markdown
# 系统架构

## 整体架构

Agent Part 采用分层架构：

```
┌─────────────────────────────────────────┐
│           Frontend (Vue 3)              │
│      商品录入 | 任务管理 | 结果展示       │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│           API Layer (FastAPI)            │
│         /api/v1/products | /tasks        │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│      LangGraph Workflow Engine          │
│  Orchestrator → Analyzer → Planner      │
│  → Designer → Generator → Reviewer      │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│         External Services               │
│  DashScope | 可灵 AI | PostgreSQL | Redis│
└─────────────────────────────────────────┘
```

## Agent 协作流程

1. **Orchestrator** — 编排调度，初始化工作流
2. **RequirementAnalyzer** — 分析商品信息，提取卖点
3. **CreativePlanner** — 生成创意方案和配色
4. **VisualDesigner** — 设计图片提示词和分镜
5. **ImageGenerator** — 调用图像生成 API
6. **VideoGenerator** — 调用视频生成 API
7. **QualityReviewer** — 审核生成质量

## 数据流

```
Product → GenerationRequest → AgentState (状态流转)
    → requirement_report → creative_plan
    → generation_prompts → generated_images/video
    → quality_reports → final_results
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3, TypeScript, Element Plus |
| API | FastAPI, Pydantic v2 |
| 工作流 | LangChain, LangGraph |
| 数据库 | PostgreSQL, PGVector, Redis |
| LLM | 通义千问, Claude |
| 图像 | 通义万象 |
| 视频 | 可灵 AI |
```

- [ ] **Step 7: 提交 MkDocs 配置**

```bash
git add mkdocs.yml docs-site/
git commit -m "docs: add MkDocs documentation site with getting-started guides"
```

---

### Task 6: 添加 .gitignore 更新

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: 更新 .gitignore**

在 `.gitignore` 中添加：

```gitignore
# MkDocs
site/

# Docker
docker-compose.override.yml

# Backup files
*.bak
```

- [ ] **Step 2: 提交**

```bash
git add .gitignore
git commit -m "chore: update .gitignore for MkDocs and Docker"
```

---

## Phase 3: 社区推广（内容创作，非代码任务）

### Task 7: 技术文章撰写（手动任务）

**说明**: 以下为内容创作任务，需要手动完成。

- [ ] **Step 1: 撰写掘金文章**

标题：「LangGraph 实战：如何用 7 个 Agent 自动化跨境电商商品刊登」

内容结构：
1. 背景：跨境电商商品刊登的痛点
2. 方案：多 Agent 协作架构设计
3. 实现：核心代码讲解
4. 效果：实际运行演示
5. 总结：架构优势和扩展性

- [ ] **Step 2: 撰写知乎文章**

标题：「从零搭建多 Agent 系统：LangGraph + RAG 的实践之路」

内容结构：
1. 为什么需要多 Agent？
2. LangGraph 状态图设计
3. RAG 知识库增强
4. 踩坑记录和最佳实践

- [ ] **Step 3: 在 LangChain 社区分享**

- LangChain Discord #showcase 频道
- LangGraph GitHub Discussions

---

## 任务依赖关系

```
Task 1 (社区文件) ──┐
                     ├──→ Task 3 (SEO) ──→ Task 7 (推广)
Task 2 (README)  ──┘
                     
Task 4 (Docker)  ──┐
                     ├──→ Task 7 (推广)
Task 5 (MkDocs)  ──┘
```

## 完成标准

- [ ] Phase 1 完成：README 重构、社区文件、SEO 优化
- [ ] Phase 2 完成：Docker Compose、MkDocs 文档站点
- [ ] Phase 3 启动：至少发布 1 篇技术文章
