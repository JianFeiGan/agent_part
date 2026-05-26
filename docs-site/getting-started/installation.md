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
