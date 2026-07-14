# 系统架构

## 整体架构

Agent Part 采用分层架构，由前端管理后台、API 层、LangGraph 工作流引擎、外部服务四层组成。

```
┌──────────────────────────────────────────────────────────────┐
│                     Vue 3 管理后台 (14 页面)                  │
│  仪表盘 │ 商品管理 │ 任务管理 │ 知识库 │ 刊登工具 │ AI 会话    │
└──────────────────────────┬───────────────────────────────────┘
                           │ REST API / WebSocket
┌──────────────────────────▼───────────────────────────────────┐
│                     FastAPI API 层 (40+ 端点)                 │
│  认证: API Token (SHA256 + Scope)    租户隔离: tenant_id      │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                   LangGraph 工作流引擎                         │
│                                                               │
│  视觉生成工作流:                                                │
│  Orchestrator → ReqAnalyzer → CreativePlanner → VisualDesigner│
│       → [ImageGen | VideoGen] → QualityReviewer → END         │
│                                                               │
│  刊登工作流:                                                    │
│  ImportProduct → [AssetOptimizer | Copywriter] → Compliance   │
│                                                               │
│  知识库 Agent 工作流:                                           │
│  QueryAnalyzer → StrategyRouter → HybridRetriever → Fuser     │
└───────┬──────────────┬──────────────┬────────────────────────┘
        │              │              │
 ┌──────▼──────┐ ┌─────▼─────┐ ┌─────▼──────┐
 │  千问百炼    │ │  DashScope │ │  可灵 AI    │
 │ (OpenAI兼容) │ │  (万象图片) │ │  (视频生成)  │
 └──────┬──────┘ └─────┬─────┘ └─────┬──────┘
        │              │              │
 ┌──────▼──────────────▼──────────────▼────────┐
 │  PostgreSQL + PGVector  │  Redis  │  Storage │
 │  15+ 表 (向量/图谱/记忆)  │  缓存   │  本地/OSS │
 └─────────────────────────────────────────────┘
```

## 工作流详解

### 视觉生成工作流

7 个专业 Agent 协同完成商品视觉内容生成：

1. **Orchestrator** — 编排调度，初始化工作流，任务分解
2. **RequirementAnalyzer** — 分析商品信息，提取卖点、关键特性、目标人群
3. **CreativePlanner** — 生成创意方案、配色方案、风格方向
4. **VisualDesigner** — 设计图片提示词、分镜脚本
5. **ImageGenerator** — 调用 DashScope 万象 API 生成图片
6. **VideoGenerator** — 调用可灵 AI API 生成视频
7. **QualityReviewer** — 审核生成质量，评分、问题检测

条件路由：
- `task_type = image_only` → 跳过视频生成
- `task_type = video_only` → 跳过图片生成
- `task_type = image_and_video` → 先图片后视频

RAG 增强：当 `rag_enabled=true` 时，需求分析、创意策划、质量审核三个 Agent 自动注入 RAG 增强版本，从知识库检索品牌规范、类目知识等辅助决策。

### 刊登工作流

5 个 Agent 协同完成商品刊登：

1. **ImportProduct** — 商品导入与标准化
2. **AssetOptimizer** — 素材优化（裁剪/压缩/格式转换）
3. **AICopywriting** — AI 文案生成（LLM 润色 + 规则草稿降级）
4. **ComplianceChecker** — 合规检查（禁词 + 平台规则）
5. **AdapterConfigManager** — 适配器配置管理

素材优化和文案生成并行执行，完成后汇聚到合规检查。

### 知识库 Agent 工作流

3 个 Agent 协同完成智能检索：

1. **QueryAnalyzer** — 分析查询意图（FACT/REASONING/COMPARISON/AGGREGATION）
2. **StrategyRouter** — 路由到最佳检索策略（vector/graph/hybrid）
3. **ResultFuser** — RRF 融合多路检索结果

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
| **工作流引擎** | LangChain, LangGraph |
| **后端框架** | FastAPI, Pydantic v2, SQLAlchemy 2.0 (async) |
| **语言模型** | 千问百炼 (OpenAI 兼容 + DashScope SDK) |
| **图片生成** | DashScope 万象 (wanx-v1, wan2.7-image-pro) |
| **视频生成** | 可灵 AI (kling-v1) |
| **向量检索** | PGVector, BGE-large-zh, 千问 text-embedding-v3 |
| **前端框架** | Vue 3, TypeScript, Element Plus, Pinia |
| **数据库** | PostgreSQL 16 + PGVector, Redis 6 |
| **部署** | Docker Compose, Nginx |

## 认证与多租户

- **API Token** — SHA256 哈希注册表 + 恒定时间比较
- **Scope 权限** — `products:read/write`、`tasks:read/write`、`assets:read/write`
- **多租户隔离** — 所有数据表均有 `tenant_id` 字段，API 层通过 AuthContext 强制隔离
- **凭证加密** — 适配器配置使用 EncryptedJSONB 加密存储

## 优雅降级

- **无 DashScope API Key** → 图片生成降级为 Mock 占位
- **无可灵 AI Key** → 视频生成降级为 Mock 占位
- **LLM 降级链** → 通义千问 → Claude → 规则生成
- **Embedding 降级** → 千问 API → 本地 BGE-large-zh
