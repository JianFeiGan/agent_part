# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目是什么

`product-visual-generator`（README 对外称 **Agent Part**）——基于 LangGraph 的多 Agent 跨境电商内容生成系统：商品分析 → AI 文案 → 图片/视频生成 → 合规检查 → 多平台（Amazon/eBay/Shopify）刊登，配一个 DevTools 风格的可观测工作台（DAG + 提示词轨迹 + WebSocket 实时推送）。

- 包名 `product-visual-generator`，版本 0.3.0，Python ≥3.11（开发目标 3.11，非 3.13）
- 详细架构文档在 `AGENTS.md`（约 25K）与 `docs-site/concepts/architecture.md`；本文件只覆盖**动手前必须知道**的部分，不重复二者。

## 常用命令

```bash
# 后端
uv sync                      # 安装依赖（默认含 dev dependency-group；pytest/ruff/mypy 在 dev extra，需 uv sync --extra dev）
uv run python main.py        # 启动 API（:8000，/docs）
uv run python run_workflow.py # 无 API 直接跑一遍视觉生成工作流（rich 输出）
cp .env.example .env         # 首次：至少配 QWEN_API_KEY

# 前端（frontend/）
npm install && npm run dev   # :5173，vite 代理 /api → :8000（ws:true，REST 与 WebSocket 共用 /api 前缀，无独立 /ws 代理）
# frontend/.npmrc 已设 legacy-peer-deps=true（vitest@4 + vite@5 的 npm peer 解析会崩）
npm run build                # typecheck + vite build


# 测试
uv run pytest                          # 全量
uv run pytest tests/test_api/test_auth_deps.py -v      # 单文件
uv run pytest -k "test_xxx" -v                          # 单用例
uv run pytest --cov=src --cov-report=html               # 覆盖率（fail_under=80）

# 质量检查
uv run ruff format . && uv run ruff check .
uv run mypy src/                       # strict=true

# 前端检查（frontend/ 下）
npm run lint / typecheck / test        # eslint 9 / vue-tsc / vitest

# 数据库 schema
uv run alembic upgrade head            # 全新库
uv run alembic stamp head              # 已用 create_all 建过表的存量库
```

`DB_AUTO_CREATE` 默认 true（启动时自动 create_all），生产环境应设 false 并改用 Alembic 管理迁移。仓库**没有 CI**——ruff + mypy + pytest 四连是提交前唯一的把关，需手动跑。

Docker：`docker compose up -d`（app :8000 / frontend :3000 / postgres pgvector / redis）。

## 架构骨架（跨文件才能拼出的部分）

**两条 LangGraph 工作流 + 一条知识库问答管道**（后者是普通 Python 五阶段管道，非 LangGraph 状态机），不要混用它们的 state：

| 工作流 | 入口 | State | 节点 |
|---|---|---|---|
| 视觉生成 | `src/graph/workflow.py` `ProductVisualWorkflow` | `graph/state.py` `AgentState` | Orchestrator → RequirementAnalyzer → CreativePlanner → VisualDesigner → [ImageGen \| VideoGen] → QualityReviewer |
| 刊登 | `src/graph/listing_workflow.py` `ListingWorkflow` | `graph/listing_state.py` `ListingState` | ImportProduct → [AssetOptimizer ‖ Copywriter] → ComplianceCheck（任一平台 FAIL 则挂起人工审核）→ PlatformPush（失败自动重试一次）→ Finalize（持久化终态） |
| 知识库问答 | `src/knowledge/agent_workflow.py` `KnowledgeAgentWorkflow` | `KnowledgeAgentState`（dataclass） | QueryAnalyzer → StrategyRouter → Retriever（vector/graph/hybrid）→ ResultFuser → AnswerGenerator |

前两者统一从 `src/graph/__init__.py` 导入（`AgentState` / `ListingState` / `ProductVisualWorkflow` / `ListingWorkflow`）；知识库管道在 `src/knowledge`，不经该入口导出。

**分层**：`src/api/router`（FastAPI 路由，全部挂在 `/api/v1`，见 `router/__init__.py`）→ `src/api/service`（`task_manager` 异步任务 + `redis_client` 状态 + `asset_persister`）→ `src/agents` / `src/graph` → `src/clients`（外部厂商）→ `src/db` / `src/storage` / `src/rag`。

**Providers 走数据库而非环境变量**：`src/clients/provider_factory.py` 的 `ProviderFactory.get_llm_provider/get_image_provider/get_video_provider` 从 `model_providers` 表读配置，按 `tenant_id` 隔离，支持任务级 `provider_id` 覆盖；**只有 DB 无配置时才 fallback 到 Settings**。新增厂商客户端参照 `src/clients/` 现有实现（`qwen_llm_client.py` / `dashscope_image_client.py` / `kling_video_client.py` 等，接口协议在 `protocols.py`）。

**Agent 基类**：`src/agents/base.py` 的 `BaseAgent`（泛型于 `AgentRuntimeState`），`AgentRole` 枚举决定角色，`_create_llm` 懒加载 LLM。带 `rag_` 前缀的（`rag_creative_planner.py` 等）是同角色的 RAG 增强变体，由 `RAG_ENABLED` 控制注入。LLM 输出统一用 `src/agents/llm_json.py` 的 `extract_json()` 解析（能处理 ```json 围栏与夹带说明文字），失败返回 `None` 由调用方兜底。

**数据层**：三套模型文件都要注册，否则 Alembic 漏表——`src/db/models.py`（知识库/任务/GraphRAG/记忆/model_providers）、`listing_models.py`（刊登）、`conversation_models.py`（AI 会话日志）。`migrations/env.py` 已 `import` 三者汇总到 `Base.metadata`。

**记忆写入必须走审核（human-in-the-loop）**：`src/rag/memory_distiller.py` 的 `MemoryDistiller` 从任务结果/合规失败/推送结果提炼候选记忆，只写 staging 表 `category_memory_proposals`（status=pending），经 `/api/v1/memory-proposals` 的 approve/reject 人工审核后才合并进 `CategoryMemory`——**不要直接写 `CategoryMemory`**。提炼仅由 `POST /memory-proposals/distill` 手动触发，无定时任务/自动挂钩。

**租户 CRUD 走门面**：新端点一律用 `src/api/crud` 的 `TenantCRUD` + `ResourceSpec`（scope 校验、404 防枚举、租户过滤、防伪造、IntegrityError→409 都在 seam 后），session 经 `deps.SessionDep` 注入（请求成功自动 commit）。复杂查询走 `scoped_select` 逃生舱并让测试附 `assert_tenant_scoped` 断言；router 里裸写 `select(` 与 `_require_scope` 拷贝是待迁移异味。**`async with get_db()` 会直接 TypeError**（`get_db` 是给 Depends 用的 async generator；`async with` 要用 `get_db_session`）——这是 26+ 处端点曾集体必炸的历史教训。

## 必须遵守的约定

**多租户**：所有业务表都有 `tenant_id`，API 层通过 `AuthDep = Depends(require_auth)` 拿到 `AuthContext`（普通类而非 Pydantic 模型，故意避免被 FastAPI 当请求体解析），每个查询都要按 `tenant_id` 过滤。测试见 `tests/test_api/test_tenant_api_isolation.py`。

**鉴权**：Token 注册表是 `AUTH_API_TOKENS_JSON`，存 **sha256 哈希**（不接受明文 `token` 字段），用 `secrets.compare_digest` 恒定时间比较；注册表 JSON 解析失败会 **fail closed 抛 503**。支持 `Authorization: Bearer` / `X-API-Key` / WebSocket（header 或 query，后者需 `AUTH_ALLOW_WS_QUERY_TOKEN=true`）。`AUTH_ENABLED=false` 时用 `tenant_id=dev`。各 router 内用 `_require_scope` 校验细粒度 scope（如 `memory:write`）；跨租户访问一律返回 **404 而非 403**（防枚举）。

**凭证加密**：平台适配器凭证用 `src/db/encrypted_json.py` 的 `EncryptedJSONB`（Fernet），只存 `{"_encrypted": true, "v": 1, "ciphertext": ...}`；无 `_encrypted` 标记的旧数据原样返回（兼容，别改成抛异常）。返回给前端前必须脱敏（参考 `model_providers.py` 的 `_mask_api_key`）。加密密钥 `CREDENTIALS_ENCRYPTION_KEY` 未配置时 fail closed 抛异常。

**CORS**：`main.py` 启动时 `validate_cors_settings()` 会**直接拒绝**空列表或含 `*` 的配置并抛 RuntimeError。这是有意为之，别为了跑通而放宽——改 `CORS_ALLOW_ORIGINS` 为具体域名。

**Mock 降级**：`ALLOW_MOCK_ASSETS` 默认 **false（fail-closed）**——Provider 不可用就明确失败，不产假资产。仅本地/CI 无 Key 时设 true，产物会标 `is_mock=True`。注意与 README 里"没有 API Key？设 true 即可体验"的说法区分：那是用户向引导，不是代码默认。

**提交规范**（`CONTRIBUTING.md`）：Conventional Commits（`type(scope): subject`，scope 取 rag/agent/api/frontend/db 等），分支命名 `feat|fix|docs|refactor|test|chore/<描述>`。PR 硬性要求：环境变量变更必须同步 `.env.example`；数据库变更必须写幂等迁移脚本（手写 SQL 放 `scripts/migrations/`，`p2c_` 前缀，如记忆提案表的 `p2c_memory_proposals.sql`）；代码不出现 `print()`/`breakpoint()`。

**代码风格**：Google 风格 docstring + 全量 type hints（mypy `strict`）。每个文件头部沿用现有格式：三引号 Description 段落 + `@author ganjianfei` + `@version` + 日期。**不要**照抄常见 LangChain 教程里的 `ChatAnthropic` / `langchain_anthropic`——本项目不在依赖里，实际用 `langchain-openai` 兼容端点 + 千问/DashScope/SenseNova/可灵。

## 踩过的坑

- **两个同名 `TaskStatus`**：生成任务（`frontend/src/types/task.ts:112`，枚举 5 态）与刊登任务（`frontend/src/types/listing.ts:12`，联合类型 8 态，独有 `generating`/`reviewing`/`pushing`/`published`/`partial`，partial=部分平台成功）共享 `pending`/`completed`/`failed` 名字但语义不同、互不可换，误用会静默显示错状态；改状态代码前先确认是哪一套（详见 `CONTEXT.md` 与 `docs/adr/0002-two-taskstatus-types.md`）。
- **测试环境被 conftest 强制隔离**：`tests/conftest.py` 有两个 autouse fixture，会把 `ALLOW_MOCK_ASSETS=true`、`RAG_ENABLED=true`、`AUTH_ENABLED=false`，并 monkeypatch 掉 `ProviderFactory.get_image_provider/get_video_provider`（返回 None）与 `BaseAgent._create_llm`（抛 ImportError）。目的是**杜绝测试发起真实外部调用**。所以：新增的 API 测试默认免鉴权；要验证真实路径需在用例内自行 patch 覆盖。
- **`get_settings()` 是 `lru_cache` 单例**：改环境变量后必须 `get_settings.cache_clear()`，否则读不到新值。
- **Postgres 连接串由 `POSTGRES_*` 分项拼出**（`settings.postgres_url` property），**没有** `DATABASE_URL` 字段。但 `docker-compose.yml` 里给 app 传了 `DATABASE_URL` 环境变量——它对应用代码无效，实际靠 compose 网络 + 分项默认值的组合生效（compose 未覆盖 POSTGRES_HOST，仍是 localhost，容器内连不上 DB）。Alembic 的 `env.py` 里"支持 DATABASE_URL 覆盖"的注释同样是过期信息，真实来源就是 `settings.postgres_url`。
- **`src/knowledge/graph.py` 是占位实现**（docstring 明说），真实图谱在 `src/rag/graph_builder.py` / `graph_search.py` / `graph_memory.py`。
- **前端知识库管理必须用 `/api/v1/knowledge` documents，不要调 `/api/v1/knowledge/graphs`**——后者已标 `deprecated=True`，是进程内内存占位。

## Agent skills

### Issue tracker

Issues 存在 GitHub Issues（JianFeiGan/agent_part），用 `gh` CLI 读写。See `docs/agents/issue-tracker.md`.

### Triage labels

五个默认标签：needs-triage / needs-info / ready-for-agent / ready-for-human / wontfix。See `docs/agents/triage-labels.md`.

### Domain docs

single-context：仓库根 `CONTEXT.md` + `docs/adr/`。See `docs/agents/domain.md`.
