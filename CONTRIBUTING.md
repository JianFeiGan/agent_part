# 贡献指南

感谢你对 Agent Part 项目的关注！我们欢迎各种形式的贡献。

## 目录

- [如何贡献](#如何贡献)
- [开发环境搭建](#开发环境搭建)
- [前端开发指南](#前端开发指南)
- [数据库迁移](#数据库迁移)
- [代码规范](#代码规范)
- [分支命名规范](#分支命名规范)
- [提交信息格式](#提交信息格式)
- [Pull Request 规范](#pull-request-规范)
- [行为准则](#行为准则)

---

## 如何贡献

### 报告 Bug

使用 [Bug Report](https://github.com/JianFeiGan/agent_part/issues/new?template=bug_report.md) 模板提交 Issue。

### 提交功能请求

使用 [Feature Request](https://github.com/JianFeiGan/agent_part/issues/new?template=feature_request.md) 模板提交 Issue。

### 提交代码

1. Fork 本仓库
2. 创建你的特性分支（参见[分支命名规范](#分支命名规范)）
3. 提交你的改动（参见[提交信息格式](#提交信息格式)）
4. 推送到分支
5. 创建 Pull Request（参见 [PR 检查清单](#pr-检查清单)）

---

## 开发环境搭建

### 方式一：本地开发（推荐日常开发）

**前置要求：** Python 3.11+、[uv](https://docs.astral.sh/uv/)、Node.js 20+、PostgreSQL 16（含 pgvector 扩展）、Redis 6+

```bash
# 1. 克隆仓库
git clone https://github.com/JianFeiGan/agent_part.git
cd agent_part

# 2. 安装 Python 依赖
uv sync

# 3. 安装开发依赖
uv sync --group dev

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填入实际的 API Key 和数据库连接信息

# 5. 启动后端服务
uv run python main.py

# 6. 运行测试
uv run pytest

# 7. 代码质量检查
uv run ruff format .
uv run ruff check .
uv run mypy src/
```

### 方式二：Docker 开发模式（推荐集成测试）

适用于不想本地安装 PostgreSQL/Redis 的场景，使用 Docker Compose 一键启动完整环境。

**前置要求：** Docker、Docker Compose

```bash
# 1. 克隆仓库
git clone https://github.com/JianFeiGan/agent_part.git
cd agent_part

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，至少填入 API Key（数据库/Redis 地址会被 docker-compose.yml 覆盖）

# 3. 启动所有服务（后端 + 前端 + PostgreSQL + Redis）
docker compose up -d

# 4. 查看服务状态
docker compose ps

# 5. 查看后端日志
docker compose logs -f app

# 6. 仅重启后端（修改代码后需重新构建）
docker compose up -d --build app

# 7. 停止所有服务
docker compose down

# 8. 停止并清除数据卷（重置数据库）
docker compose down -v
```

服务端口说明：

| 服务 | 端口 | 说明 |
|------|------|------|
| 后端 API | `8000` | FastAPI 服务 |
| 前端页面 | `3000` | Vue 3 前端（Nginx 代理） |
| PostgreSQL | `5432` | 数据库（需暴露端口才能本地连接） |
| Redis | `6379` | 缓存（需暴露端口才能本地连接） |

**混合模式**（Docker 仅运行数据库，本地运行后端便于调试）：

```bash
# 仅启动 PostgreSQL 和 Redis
docker compose up -d postgres redis

# 本地连接数据库（需在 docker-compose.yml 中暴露端口）
# PostgreSQL: localhost:5432, 用户: postgres, 密码: postgres, 数据库: agent_part
# Redis: localhost:6379

# 本地运行后端（.env 中 DATABASE_URL 和 REDIS_URL 指向 localhost）
uv run python main.py
```

---

## 前端开发指南

前端基于 Vue 3 + TypeScript + Vite + Element Plus 构建。

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器（热更新，默认 http://localhost:5173）
npm run dev

# 构建生产版本
npm run build

# 预览构建结果
npm run preview

# 代码检查与自动修复
npm run lint
```

开发时后端 API 代理配置在 `frontend/vite.config.ts` 中，开发服务器会自动将 API 请求代理到后端 `8000` 端口。

---

## 数据库迁移

### 迁移脚本规范

迁移脚本存放在 `scripts/migrations/` 目录，文件命名格式：

```
p<序号><阶段标识>_<简要描述>.sql
```

示例：`p1a_tenant_auth.sql`、`p1b_assets.sql`

**关键要求：**

- 所有迁移脚本必须**幂等**——使用 `IF NOT EXISTS`、`IF NOT EXISTS (SELECT ...)` 等条件判断
- 文件头部注释包含：Description、作者、版本号、日期
- 按逻辑分块，每块有清晰的注释分隔

### 执行迁移

**Docker 环境**（首次启动自动执行 `init.sql`）：

```bash
# 重置数据库（删除数据卷并重建）
docker compose down -v
docker compose up -d
```

**手动执行迁移**：

```bash
# 连接数据库
docker compose exec postgres psql -U postgres -d agent_part

# 或使用本地 psql
psql -U postgres -d agent_part -f scripts/migrations/p1a_tenant_auth.sql
psql -U postgres -d agent_part -f scripts/migrations/p1b_assets.sql
```

**ORM 表结构**由 `src/db/models.py` 定义，应用启动时 SQLAlchemy 会自动创建新表。对于已有表的 Schema 变更（加字段、改索引等），需编写迁移脚本。

### 新增迁移步骤

1. 在 `scripts/migrations/` 下创建新的 `.sql` 文件
2. 确保脚本幂等
3. 在本地 Docker 环境中测试迁移
4. PR 中说明迁移内容与影响

---

## 代码规范

### Python 代码规范

| 规范 | 说明 |
|------|------|
| 代码风格 | 遵循 PEP 8，使用 `ruff format` 格式化 |
| 类型注解 | **强制使用** type hints**，所有公共函数必须有类型注解 |
| 文档字符串 | 使用 Google 风格 docstring |
| 导入顺序 | 标准库 -> 第三方库 -> LangChain -> 本地模块（由 ruff isort 自动管理） |
| 测试覆盖率 | **>= 80%**，核心链和工具 100% |

### Ruff 配置

配置定义在 `pyproject.toml` 中，关键项：

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "ARG", "SIM"]
ignore = ["E501", "B008", "B904", "ARG001"]
```

启用的规则集说明：

| 规则集 | 说明 |
|--------|------|
| `E`, `W` | pycodestyle 错误与警告 |
| `F` | Pyflakes（未使用导入/变量等） |
| `I` | isort（导入排序） |
| `B` | flake8-bugbear（常见 Bug 模式） |
| `C4` | flake8-comprehensions（推导式简化） |
| `UP` | pyupgrade（现代化语法） |
| `ARG` | flake8-unused-arguments |
| `SIM` | flake8-simplify（代码简化） |

常用命令：

```bash
# 格式化
uv run ruff format .

# Lint 检查（不自动修复）
uv run ruff check .

# Lint 检查并自动修复
uv run ruff check --fix .
```

### MyPy 配置

配置定义在 `pyproject.toml` 中，使用 strict 模式：

```toml
[tool.mypy]
python_version = "3.11"
strict = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
```

以下第三方库因缺少类型存根已配置 `ignore_missing_imports`：`dashscope.*`、`langchain.*`、`langgraph.*`、`pydantic.*`、`redis.*`

```bash
# 类型检查
uv run mypy src/
```

### 测试规范

| 要求 | 说明 |
|------|------|
| 框架 | pytest + pytest-asyncio |
| 覆盖率 | **>= 80%**（`pyproject.toml` 中 `fail_under = 80`） |
| 异步测试 | `asyncio_mode = "auto"`，无需手动标记 `@pytest.mark.asyncio` |
| 测试标记 | `slow`（慢速测试）、`integration`（集成测试）、`e2e`（端到端测试） |

```bash
# 运行所有测试
uv run pytest

# 带覆盖率报告（终端，显示未覆盖行）
uv run pytest --cov=src --cov-report=term-missing

# 带覆盖率报告（HTML）
uv run pytest --cov=src --cov-report=html

# 仅运行单元测试（跳过慢速/集成测试）
uv run pytest -m "not slow and not integration"

# 运行指定测试文件
uv run pytest tests/test_agent.py -v
```

### 完整检查流程

提交代码前，请确保通过以下检查：

```bash
uv run ruff format . && uv run ruff check . && uv run mypy src/ && uv run pytest --cov
```

---

## 分支命名规范

| 类型 | 格式 | 示例 |
|------|------|------|
| 新功能 | `feat/<简短描述>` | `feat/add-rag-pipeline` |
| Bug 修复 | `fix/<简短描述>` | `fix/conversation-history-bug` |
| 文档更新 | `docs/<简短描述>` | `docs/update-api-reference` |
| 重构 | `refactor/<简短描述>` | `refactor/simplify-agent-graph` |
| 测试 | `test/<简短描述>` | `test/add-retriever-tests` |
| 构建/工具 | `chore/<简短描述>` | `chore/upgrade-langchain` |

规则：

- 使用小写英文，单词间用连字符 `-` 分隔
- 描述简短准确，不超过 5 个单词
- 从 `master` 分支创建

---

## 提交信息格式

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <subject>

<body>

<footer>
```

类型：

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档更新 |
| `refactor` | 代码重构（不改变功能） |
| `test` | 测试相关 |
| `chore` | 构建/工具相关 |
| `style` | 代码格式调整（不影响逻辑） |
| `perf` | 性能优化 |

scope 可选，指明影响范围，如 `rag`、`agent`、`api`、`frontend`、`db` 等。

示例：

```
feat(rag): 添加知识检索缓存机制

- 使用 Redis 缓存高频查询结果
- 缓存 TTL 默认 300 秒
- 新增 RAG_REDIS_CACHE_TTL 环境变量

Closes #42
```

---

## Pull Request 规范

### PR 标题

格式与提交信息一致：`<type>(<scope>): <subject>`

### PR 描述

- 说明改动的原因和内容
- 关联相关的 Issue（如 `Closes #42`）
- 如涉及数据库迁移，注明迁移文件和影响

### PR 检查清单

提交 PR 前请逐项确认：

- [ ] 代码通过 `ruff format` 格式化
- [ ] 代码通过 `ruff check` 检查，无报错
- [ ] 代码通过 `mypy` 类型检查，无报错
- [ ] 所有测试通过（`uv run pytest`）
- [ ] 测试覆盖率 >= 80%（`uv run pytest --cov`）
- [ ] 如有新功能，已补充对应的测试用例
- [ ] 如有数据库变更，已编写幂等迁移脚本
- [ ] 如有环境变量变更，已更新 `.env.example`
- [ ] 如有 API 变更，已更新相关文档
- [ ] 提交信息遵循 Conventional Commits 规范
- [ ] 无调试代码（`print()`、`breakpoint()` 等）

---

## 行为准则

- 尊重他人，保持友善
- 建设性地讨论问题
- 欢迎新手提问
