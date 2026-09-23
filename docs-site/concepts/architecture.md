# 系统架构

## 整体架构

Agent Part 采用分层架构，由前端管理后台、API 层、LangGraph 工作流引擎、外部服务四层组成。

```
┌──────────────────────────────────────────────────────────────────┐
│                     Vue 3 管理后台 (17 页面)                      │
│  仪表盘 │ 商品管理 │ 任务管理 │ 知识库 │ 刊登工具 │ AI 会话       │
└──────────────────────────┬───────────────────────────────────────┘
                           │ REST API / WebSocket
┌──────────────────────────▼───────────────────────────────────────┐
│                     FastAPI API 层 (40+ 端点)                     │
│  认证: API Token (SHA256 + Scope)    租户隔离: tenant_id         │
│  路由: products / tasks / knowledge / listing / assets / ai      │
│        / dashboard / evaluation / graph-rag / memory-proposals   │
│        / model-providers / health                                │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│                   LangGraph 工作流引擎                             │
│                                                                   │
│  视觉生成工作流:                                                    │
│  Orchestrator → ReqAnalyzer → CreativePlanner → VisualDesigner   │
│       → [ImageGen | VideoGen] → QualityReviewer → END             │
│                                                                   │
│  刊登工作流:                                                        │
│  ImportProduct → [AssetOptimizer | Copywriter] → ComplianceCheck   │
│       → PlatformPush → END                                         │
│                                                                   │
│  知识库 Agent 工作流:                                               │
│  QueryAnalyzer → StrategyRouter → HybridRetriever → ResultFuser  │
│       → AnswerGenerator → END                                     │
└───────┬──────────────┬──────────────┬────────────────────────────┘
        │              │              │
 ┌──────▼──────┐ ┌─────▼─────┐ ┌─────▼──────┐
 │ 千问/SenseNova│ │  DashScope │ │  可灵 AI    │
 │  (LLM 通道)  │ │  (万象图片) │ │  (视频生成)  │
 └──────┬──────┘ └─────┬─────┘ └─────┬──────┘
        │              │              │
 ┌──────▼──────────────▼──────────────▼────────┐
 │  PostgreSQL + PGVector  │  Redis  │  Storage │
 │  15+ 表 (向量/图谱/记忆) │  缓存   │  本地/OSS │
 └─────────────────────────────────────────────┘
```

## 工作流详解

### 视觉生成工作流

7 个专业 Agent 协同完成商品视觉内容生成：

1. **Orchestrator** — 编排调度，初始化工作流，任务分解
2. **RequirementAnalyzer** — 分析商品信息，提取卖点、关键特性、目标人群
3. **CreativePlanner** — 生成创意方案、配色方案、风格方向
4. **VisualDesigner** — 设计图片提示词、分镜脚本
5. **ImageGenerator** — 调用图片生成 API（DashScope 万象 wanx-v1 / SenseNova sensenova-u1-fast，Provider 可配）
6. **VideoGenerator** — 调用可灵 AI API 生成视频（kling-v1, HS256 JWT 鉴权）
7. **QualityReviewer** — 审核生成质量，评分、问题检测

条件路由：

```
task_type = image_only       → 视觉设计 → 图片生成 → 质量审核
task_type = video_only       → 视觉设计 → 视频生成 → 质量审核
task_type = image_and_video  → 视觉设计 → 图片生成 → 视频生成 → 质量审核
```

RAG 增强：当 `rag_enabled=true` 时，需求分析、创意策划、质量审核三个 Agent 自动注入 RAG 增强版本：

- **RAGEnhancedRequirementAnalyzer** — 检索类目知识 + 品牌规范 + 历史案例
- **RAGEnhancedCreativePlanner** — 检索品牌视觉规范 + 风格模板
- **RAGEnhancedQualityReviewer** — 检索合规规则辅助审核

### 刊登工作流

4 个 Agent + 推送服务协同完成商品刊登：

1. **ImportProduct** — 商品导入与标准化（可复用视觉生成的 AI 图片）
2. **AssetOptimizer** — 素材优化（裁剪/压缩/格式转换，适配各平台规格）
3. **AICopywriting** — AI 文案生成（规则草稿 → LLM 润色，LLM 失败时保留规则草稿）
4. **ComplianceChecker** — 合规检查（禁词检测 + 平台规则校验）
5. **PlatformPush**（ListingPushService）— 并行推送到未阻断平台，非永久错误自动重试一次

素材优化和文案生成并行执行，完成后汇聚到合规检查；任一平台合规 FAIL 时任务挂起人工审核（reviewing），不执行推送。

支持的平台适配器：

- **Amazon** — 标题/五点(bullet_points)/描述/搜索词(search_terms)
- **eBay** — 标题/要点 HTML 列表/描述/搜索词
- **Shopify** — 标题/body_html(描述+Features)/搜索词

### 知识库 Agent 工作流

五阶段管道协同完成智能检索与问答（`src/knowledge/agent_workflow.py`）：

1. **QueryAnalyzer** — 分析查询意图（FACT/REASONING/COMPARISON/AGGREGATION），提取实体（LLM 优先，关键词规则兜底）
2. **StrategyRouter** — 按规则路由到最佳检索策略
3. **Retriever** — 执行向量检索（KnowledgeRetriever）和/或图谱检索（GraphSearchService）
4. **ResultFuser** — RRF 融合多路检索结果
5. **AnswerGenerator** — 基于融合上下文生成答案（LLM 优先，Top-1 摘录兜底）

策略路由规则：

| 查询意图 | 实体数 | 检索策略 |
|----------|--------|----------|
| FACT | >= 2 | hybrid |
| FACT | < 2 | vector |
| REASONING | — | graph |
| COMPARISON | — | hybrid |
| AGGREGATION | — | hybrid |

## 数据流

### 视觉生成

```
Product → GenerationRequest → AgentState (状态流转)
    → requirement_report → selling_points
    → creative_plan → color_palette
    → generation_prompts → storyboard
    → generated_images → generated_video
    → quality_reports → quality_score → issues
    → asset_collection → final_results
```

### 刊登

```
ListingProduct → ListingState (状态流转)
    → asset_packages (素材优化结果)
    → copywriting_packages (文案生成结果)
    → compliance_reports (合规检查结果)
    → push_results (推送结果)
```

### 知识库

```
Query → GraphRAGState (状态流转)
    → query_intent + entities
    → retrieval_strategy (vector/graph/hybrid)
    → vector_results + graph_results
    → fused_results
    → final_answer + sources
```

## 技术栈

| 层级 | 技术 |
|------|------|
| **工作流引擎** | LangChain, LangGraph |
| **后端** | FastAPI, Pydantic v2, SQLAlchemy 2.0 (async) |
| **语言模型** | 千问百炼 (OpenAI 兼容 + DashScope SDK 双通道) |
| **图片生成** | DashScope 万象 (wanx-v1) / SenseNova (sensenova-u1-fast)，Provider 可配 |
| **视频生成** | 可灵 AI (kling-v1, HS256 JWT 鉴权) |
| **向量检索** | PGVector, BGE-large-zh (本地), 千问 text-embedding-v3 (API) |
| **图谱检索** | Graph RAG (实体/关系/社区/摘要) |
| **前端** | Vue 3, TypeScript, Element Plus, Pinia |
| **数据库** | PostgreSQL 16 + PGVector, Redis 6 |
| **存储** | 本地文件系统 / 阿里云 OSS |
| **部署** | Docker Compose, Nginx |

## 认证与多租户

### API Token 认证

- **注册表** — JSON 格式配置，存储 token 的 SHA256 哈希（非明文）
- **验证** — `secrets.compare_digest` 恒定时间比较，防止时序攻击
- **传递方式** — `Authorization: Bearer <token>` 或 `X-API-Key` 头
- **WebSocket** — 支持 Header 和查询参数两种传递方式

### Scope 权限

| Scope | 说明 |
|-------|------|
| `products:read` | 读取商品 |
| `products:write` | 创建/修改商品 |
| `tasks:read` | 读取任务 |
| `tasks:write` | 创建/管理任务 |
| `assets:read` | 读取资产 |
| `assets:write` | 上传/管理资产 |
| `memory:write` | 记忆提炼提案审核 |
| `*` | 通配符，拥有所有权限 |

### 多租户隔离

- 所有数据表均有 `tenant_id` 字段
- API 层通过 `AuthContext` 强制隔离，每个请求自动注入租户信息
- 向量检索、图谱查询、RAG 检索均按 `tenant_id` 过滤
- 开发模式（`AUTH_ENABLED=false`）自动使用 `tenant_id=dev`

### 凭证加密

- 适配器配置（Amazon/eBay/Shopify 凭证）使用 `EncryptedJSONB` 透明加密
- 基于 `cryptography.fernet` 对称加密
- 兼容旧明文数据（无 `_encrypted` 标记时原样返回）

## 数据库模型

系统包含 15+ 张数据表，核心模型：

| 表名 | 说明 |
|------|------|
| `products` | 商品信息 |
| `generation_tasks` | 视觉生成任务 |
| `knowledge_docs` | 知识库文档 |
| `knowledge_chunks` | 文档分块 + 向量嵌入 (1024维) |
| `rag_usage_logs` | RAG 检索使用日志 |
| `graph_rag_entities` | 知识图谱实体 |
| `graph_rag_edges` | 知识图谱关系 |
| `category_memories` | 类目累积记忆 |
| `ai_conversation_logs` | AI 会话记录 (Token/费用) |
| `listing_products` | 刊登商品 |
| `listing_tasks` | 刊登任务 |
| `asset_packages` | 素材包 |
| `copywriting_packages` | 文案包 |
| `compliance_reports` | 合规报告 |
| `task_results` | 推送结果 |
| `adapter_configs` | 适配器配置 (加密) |
| `generated_assets` | 生成资产 (图片/视频/文档) |

## 优雅降级

| 场景 | 降级策略 |
|------|----------|
| 无图片 Provider Key 且 `ALLOW_MOCK_ASSETS=true` | 图片生成降级为 Mock 占位（`is_mock=True`）；默认 `false` 时任务明确失败（fail-closed） |
| 无可灵 AI Key 且 `ALLOW_MOCK_ASSETS=true` | 视频生成降级为 Mock 占位（`is_mock=True`）；默认 `false` 时任务明确失败 |
| LLM 不可用 | SettingsFallbackLLMProvider 按配置兜底（SenseNova → DashScope）；文案场景调用失败回退规则草稿 |
| Embedding | 由 `EMBEDDING_PROVIDER` 选择通道（`local` 默认 / `qwen`），无自动跨通道降级 |
| Graph RAG | `GRAPH_RAG_ENABLED` 默认 `false`，未启用时图谱检索策略降级为向量检索 |
| 无数据库 | RAG 功能禁用，Agent 使用基础版本 |

> **生产环境注意**：`ALLOW_MOCK_ASSETS` 默认 `false`（fail-closed）。仅本地/CI 无 Key 体验时设为 `true`，此时占位资产会被明确标记 `is_mock=True`。
