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
# 编辑 .env，至少配置 QWEN_API_KEY 或 DASHSCOPE_API_KEY

# 启动所有服务（后端 + 前端 + PostgreSQL + Redis）
docker compose up -d

# 访问
# 前端: http://localhost:3000
# 后端 API 文档: http://localhost:8000/docs
```

Docker Compose 包含以下服务：

| 服务 | 镜像 | 端口 |
|------|------|------|
| app | 自建 (Dockerfile) | 8000 |
| frontend | 自建 (Dockerfile.frontend) | 3000 |
| postgres | pgvector/pgvector:pg16 | 5432 |
| redis | redis:6-alpine | 6379 |

## 方式二：本地开发

### 后端

```bash
git clone https://github.com/JianFeiGan/agent_part.git
cd agent_part

# 安装 Python 依赖（使用 uv）
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env，配置必要的 API Key

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

### LLM 与 AI 服务（必填至少一项）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `QWEN_API_KEY` | — | 千问 API Key（阿里云百炼平台），同时支持 OpenAI 兼容和 DashScope 原生协议 |
| `DASHSCOPE_API_KEY` | — | DashScope API Key，未配置时回退到 QWEN_API_KEY |
| `LLM_PROVIDER` | `dashscope` | LLM 提供商：`dashscope`（DashScope SDK）或 `qwen`（OpenAI 兼容） |
| `QWEN_API_BASE` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 千问 OpenAI 兼容端点 |
| `QWEN_LLM_MODEL` | `qwen-plus` | LLM 模型名称 |

### 图片与视频生成

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `KLING_ACCESS_KEY` | — | 可灵 AI Access Key（视频生成） |
| `KLING_SECRET_KEY` | — | 可灵 AI Secret Key（视频生成） |
| `IMAGE_MODEL` | `wanx-v1` | 图片生成模型（DashScope 万象） |
| `VIDEO_MODEL` | `kling-v1` | 视频生成模型（可灵 AI） |

### Embedding 与 RAG

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `EMBEDDING_PROVIDER` | `local` | Embedding 提供商：`local`（BGE-large-zh 本地）或 `qwen`（千问 text-embedding-v3 API） |
| `EMBEDDING_MODEL` | `BAAI/bge-large-zh` | 本地 Embedding 模型名称 |
| `EMBEDDING_DEVICE` | `auto` | Embedding 设备：`auto`/`cuda`/`cpu` |
| `QWEN_EMBEDDING_MODEL` | `text-embedding-v3` | 千问 Embedding 模型名称 |
| `QWEN_EMBEDDING_DIMENSIONS` | `1024` | 千问 Embedding 向量维度 |
| `RAG_ENABLED` | `true` | 启用 RAG 知识检索增强 |
| `CHUNK_SIZE` | `512` | 文档分块大小 (tokens) |
| `CHUNK_OVERLAP` | `64` | 分块重叠大小 (tokens) |
| `RETRIEVAL_TOP_K` | `5` | 检索返回文档数量 |
| `SIMILARITY_THRESHOLD` | `0.7` | 相似度阈值 |

### 数据库

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `POSTGRES_HOST` | `localhost` | PostgreSQL 主机 |
| `POSTGRES_PORT` | `5432` | PostgreSQL 端口 |
| `POSTGRES_USER` | `postgres` | PostgreSQL 用户名 |
| `POSTGRES_PASSWORD` | — | PostgreSQL 密码 |
| `POSTGRES_DB` | `pvg` | PostgreSQL 数据库名 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接 URL |
| `REDIS_PREFIX` | `pvg:` | Redis Key 前缀 |

### 存储

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `STORAGE_TYPE` | `local` | 存储类型：`local` 或 `oss` |
| `STORAGE_PATH` | `./output` | 本地存储路径 |
| `OSS_ENDPOINT` | — | 阿里云 OSS Endpoint |
| `OSS_BUCKET` | — | 阿里云 OSS Bucket |
| `OSS_ACCESS_KEY` | — | 阿里云 OSS Access Key |
| `OSS_SECRET_KEY` | — | 阿里云 OSS Secret Key |

### 认证与安全

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AUTH_ENABLED` | `true` | 是否启用 API Token 鉴权 |
| `AUTH_API_TOKENS_JSON` | `[]` | API Token 注册表 JSON，格式见下方说明 |
| `AUTH_ALLOW_WS_QUERY_TOKEN` | `false` | 是否允许 WebSocket 查询参数传递 token |
| `CORS_ALLOW_ORIGINS` | `http://localhost:5173,http://localhost:3000` | CORS 允许的来源，逗号分隔 |
| `CREDENTIALS_ENCRYPTION_KEY` | — | 适配器配置凭证加密密钥（Fernet） |

Token 注册表格式：

```json
[
  {
    "token_hash": "<sha256-hex>",
    "tenant_id": "tenant_001",
    "user_id": "user_001",
    "scopes": ["products:read", "tasks:write", "assets:read"]
  }
]
```

生成 token hash：

```bash
echo -n "your-secret-token" | sha256sum
```

### 服务与日志

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | `0.0.0.0` | 服务主机 |
| `PORT` | `8000` | 服务端口 |
| `DEBUG` | `false` | 调试模式 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

### LangSmith 追踪（可选）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LANGCHAIN_TRACING_V2` | `false` | 启用 LangSmith 追踪 |
| `LANGCHAIN_API_KEY` | — | LangSmith API Key |
| `LANGCHAIN_PROJECT` | `product-visual-generator` | LangSmith 项目名 |

### 降级配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ALLOW_MOCK_ASSETS` | `true` | 无 API Key 时允许 Mock 降级生成占位资产 |

## 优雅降级

Agent Part 支持在缺少 API Key 时自动降级：

- **无 DashScope API Key** → 图片生成降级为 Mock 占位（标记 `is_mock=True`）
- **无可灵 AI Key** → 视频生成降级为 Mock 占位（标记 `is_mock=True`）
- **LLM 降级链** → DashScope SDK → 千问 → OpenAI 兼容千问 → 规则生成
- **Embedding 降级** → 千问 API → 本地 BGE-large-zh

> **注意**：生产环境必须设置 `ALLOW_MOCK_ASSETS=false`，否则会静默产出标记为"已完成"的假图/假视频。

## 验证安装

```bash
# 运行测试
uv run pytest

# 检查 API 服务健康状态
curl http://localhost:8000/api/v1/health
```
