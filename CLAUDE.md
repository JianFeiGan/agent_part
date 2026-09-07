# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目是什么

`product-visual-generator`（README 对外称 **Agent Part**）——基于 LangGraph 的多 Agent 跨境电商内容生成系统：商品分析 → AI 文案 → 图片/视频生成 → 合规检查 → 多平台（Amazon/eBay/Shopify）刊登，配一个 DevTools 风格的可观测工作台（DAG + 提示词轨迹 + WebSocket 实时推送）。

- 包名 `product-visual-generator`，版本 0.2.0，Python ≥3.11（开发目标 3.11，非 3.13）
- 详细架构文档在 `AGENTS.md`（22.8K）与 `docs-site/concepts/architecture.md`；本文件只覆盖**动手前必须知道**的部分，不重复二者。

## 常用命令

```bash
# 后端
uv sync                      # 安装依赖（含 dev extra）
uv run python main.py        # 启动 API（:8000，/docs）
uv run python run_workflow.py # 无 API 直接跑一遍视觉生成工作流（rich 输出）
cp .env.example .env         # 首次：至少配 QWEN_API_KEY

# 前端（frontend/）
npm install && npm run dev   # :5173，vite 已代理 /api → :8000、/ws → :8000
npm run build                # vite build

# 测试
uv run pytest                          # 全量
uv run pytest tests/test_api/test_auth_deps.py -v      # 单文件
uv run pytest -k "test_xxx" -v                          # 单用例
uv run pytest --cov=src --cov-report=html               # 覆盖率（fail_under=80）

# 质量检查
uv run ruff format . && uv run ruff check .
uv run mypy src/                       # strict=true

# 数据库 schema
uv run alembic upgrade head            # 全新库
uv run alembic stamp head              # 已用 create_all 建过表的存量库
```

Docker：`docker compose up -d`（app :8000 / frontend :3000 / postgres pgvector / redis）。

## 架构骨架（跨文件才能拼出的部分）

**三条独立的 LangGraph 工作流**，不要混用它们的 state：

| 工作流 | 入口 | State | 节点 |
|---|---|---|---|
| 视觉生成 | `src/graph/workflow.py` `ProductVisualWorkflow` | `graph/state.py` `AgentState` | Orchestrator → RequirementAnalyzer → CreativePlanner → VisualDesigner → [ImageGen \| VideoGen] → QualityReviewer |
| 刊登 | `src/graph/listing_workflow.py` `ListingWorkflow` | `graph/listing_state.py` `ListingState` | ImportProduct → [AssetOptimizer ‖ Copywriter] → ComplianceCheck → PlatformPush |
| 知识库问答 | `src/knowledge/agent_workflow.py` | GraphRAGState | QueryAnalyzer → StrategyRouter → HybridRetriever → ResultFuser → AnswerGenerator |

三者统一从 `src/graph/__init__.py` 导入（`AgentState` / `ListingState` / `ProductVisualWorkflow` / `ListingWorkflow`）。

**分层**：`src/api/router`（FastAPI 路由，全部挂在 `/api/v1`，见 `router/__init__.py`）→ `src/api/service`（`task_manager` 异步任务 + `redis_client` 状态 + `asset_persister`）→ `src/agents` / `src/graph` → `src/clients`（外部厂商）→ `src/db` / `src/storage` / `src/rag`。

**Providers 走数据库而非环境变量**：`src/clients/provider_factory.py` 的 `ProviderFactory.get_llm_provider/get_image_provider/get_video_provider` 从 `model_providers` 表读配置，按 `tenant_id` 隔离，支持任务级 `provider_id` 覆盖；**只有 DB 无配置时才 fallback 到 Settings**。新增厂商客户端见 `.claude/commands/add-or-update-provider-client.md`。

**Agent 基类**：`src/agents/base.py` 的 `BaseAgent`（泛型于 `AgentRuntimeState`），`AgentRole` 枚举决定角色，`_create_llm` 懒加载 LLM。带 `rag_` 前缀的（`rag_creative_planner.py` 等）是同角色的 RAG 增强变体，由 `RAG_ENABLED` 控制注入。LLM 输出统一用 `src/agents/llm_json.py` 的 `extract_json()` 解析（能处理 ```json 围栏与夹带说明文字），失败返回 `None` 由调用方兜底。

**数据层**：三套模型文件都要注册，否则 Alembic 漏表——`src/db/models.py`（知识库/任务/GraphRAG/记忆/model_providers）、`listing_models.py`（刊登）、`conversation_models.py`（AI 会话日志）。`migrations/env.py` 已 `import` 三者汇总到 `Base.metadata`。

## 必须遵守的约定

**多租户**：所有业务表都有 `tenant_id`，API 层通过 `AuthDep = Depends(require_auth)` 拿到 `AuthContext`（普通类而非 Pydantic 模型，故意避免被 FastAPI 当请求体解析），每个查询都要按 `tenant_id` 过滤。测试见 `tests/test_api/test_tenant_api_isolation.py`。

**鉴权**：Token 注册表是 `AUTH_API_TOKENS_JSON`，存 **sha256 哈希**（不接受明文 `token` 字段），用 `secrets.compare_digest` 恒定时间比较；注册表 JSON 解析失败会 **fail closed 抛 503**。支持 `Authorization: Bearer` / `X-API-Key` / WebSocket（header 或 query，后者需 `AUTH_ALLOW_WS_QUERY_TOKEN=true`）。`AUTH_ENABLED=false` 时用 `tenant_id=dev`。

**凭证加密**：平台适配器凭证用 `src/db/encrypted_json.py` 的 `EncryptedJSONB`（Fernet），只存 `{"_encrypted": true, "v": 1, "ciphertext": ...}`；无 `_encrypted` 标记的旧数据原样返回（兼容，别改成抛异常）。返回给前端前必须脱敏（参考 `model_providers.py` 的 `_mask_api_key`）。

**CORS**：`main.py` 启动时 `validate_cors_settings()` 会**直接拒绝**空列表或含 `*` 的配置并抛 RuntimeError。这是有意为之，别为了跑通而放宽——改 `CORS_ALLOW_ORIGINS` 为具体域名。

**Mock 降级**：`ALLOW_MOCK_ASSETS` 默认 **false（fail-closed）**——Provider 不可用就明确失败，不产假资产。仅本地/CI 无 Key 时设 true，产物会标 `is_mock=True`。注意与 README 里"没有 API Key？设 true 即可体验"的说法区分：那是用户向引导，不是代码默认。

**代码风格**：Google 风格 docstring + 全量 type hints（mypy `strict`）。每个文件头部沿用现有格式：三引号 Description 段落 + `@author ganjianfei` + `@version` + 日期。**不要**照抄常见 LangChain 教程里的 `ChatAnthropic` / `langchain_anthropic`——本项目不在依赖里，实际用 `langchain-openai` 兼容端点 + 千问/DashScope/SenseNova/可灵。

## 踩过的坑

- **测试环境被 conftest 强制隔离**：`tests/conftest.py` 有两个 autouse fixture，会把 `ALLOW_MOCK_ASSETS=true`、`RAG_ENABLED=true`、`AUTH_ENABLED=false`，并 monkeypatch 掉 `ProviderFactory.get_image_provider/get_video_provider`（返回 None）与 `BaseAgent._create_llm`（抛 ImportError）。目的是**杜绝测试发起真实外部调用**。所以：新增的 API 测试默认免鉴权；要验证真实路径需在用例内自行 patch 覆盖。
- **`get_settings()` 是 `lru_cache` 单例**：改环境变量后必须 `get_settings.cache_clear()`，否则读不到新值。
- **Postgres 连接串由 `POSTGRES_*` 分项拼出**（`settings.postgres_url` property），**没有** `DATABASE_URL` 字段。但 `docker-compose.yml` 里给 app 传了 `DATABASE_URL` 环境变量——它对应用代码无效，实际靠 compose 网络 + 分项默认值的组合生效（compose 未覆盖 POSTGRES_HOST，仍是 localhost，容器内连不上 DB）。Alembic 的 `env.py` 里"支持 DATABASE_URL 覆盖"的注释同样是过期信息，真实来源就是 `settings.postgres_url`。
- **`src/knowledge/graph.py` 是占位实现**（docstring 明说），真实图谱在 `src/rag/graph_builder.py` / `graph_search.py` / `graph_memory.py`。
- 仓库根目录有 `README.md.bak`、`frontend/dump.rdb` 等遗留文件，不是活跃资产。
