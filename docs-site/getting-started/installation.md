# 安装指南

## 系统要求

- Python 3.11+
- PostgreSQL 14+ (with pgvector extension)
- Redis 6+
- Node.js 18+ (前端开发)
- Docker & Docker Compose (推荐)

## 方式一：Docker 启动（推荐）

```bash
# 克隆仓库
git clone https://github.com/JianFeiGan/agent_part.git
cd agent_part

# 配置环境变量
cp .env.example .env
# 编辑 .env，至少配置 QWEN_API_KEY

# 启动所有服务
docker compose up -d

# 访问
# 前端: http://localhost:3000
# 后端 API 文档: http://localhost:8000/docs
```

## 方式二：本地开发

### 后端

```bash
git clone https://github.com/JianFeiGan/agent_part.git
cd agent_part

# 安装 Python 依赖
uv sync

# 配置环境变量
cp .env.example .env

# 启动 API 服务
uv run python main.py
```

### 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务（自动代理到后端 8000 端口）
npm run dev
```

## 环境变量配置

### 必填

| 变量 | 说明 |
|------|------|
| `LLM_PROVIDER` | LLM 提供商：`qwen`（百炼 OpenAI 兼容）或 `dashscope` |
| `QWEN_API_KEY` | 百炼 API Key（同时支持 OpenAI 兼容和 DashScope 原生协议） |
| `QWEN_API_BASE` | 百炼 OpenAI 兼容端点 |

### 可选

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DASHSCOPE_API_KEY` | — | DashScope API Key（可与 QWEN_API_KEY 共用） |
| `QWEN_LLM_MODEL` | `qwen-plus` | LLM 模型名称 |
| `KLING_ACCESS_KEY` | — | 可灵 AI Access Key |
| `KLING_SECRET_KEY` | — | 可灵 AI Secret Key |
| `EMBEDDING_PROVIDER` | `qwen` | Embedding 提供商：`local`（BGE-large-zh）或 `qwen` |
| `EMBEDDING_MODEL` | `BAAI/bge-large-zh` | 本地 Embedding 模型名称 |
| `RAG_ENABLED` | `true` | 启用 RAG 知识检索 |
| `RETRIEVAL_TOP_K` | `5` | 检索返回数量 |
| `SIMILARITY_THRESHOLD` | `0.5` | 相似度阈值 |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL 连接 URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接 URL |
| `STORAGE_TYPE` | `local` | 存储类型：`local` 或 `oss` |
| `ALLOW_MOCK_ASSETS` | `true` | 无 API Key 时允许 Mock 降级 |

## 优雅降级

Agent Part 支持在缺少 API Key 时自动降级：

- **无 DashScope API Key** → 图片生成降级为 Mock 占位
- **无可灵 AI Key** → 视频生成降级为 Mock 占位
- **LLM 降级链** → 通义千问 → Claude → 规则生成

设置 `ALLOW_MOCK_ASSETS=true`（默认）即可启用降级模式，适合本地开发和测试。

## 验证安装

```bash
# 运行测试
uv run pytest

# 检查 API 服务
curl http://localhost:8000/api/v1/health
```
