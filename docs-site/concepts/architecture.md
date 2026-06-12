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
| 图像生成 | Mock Provider（预留通义万象接入） |
| 视频生成 | Mock Provider（预留可灵 AI 接入） |

## Graph RAG / 分类记忆

当前采用 **P0 最小底座** 实现：

- **存储**：PostgreSQL + PGVector 向量检索，不依赖 Neo4j 等图数据库。
- **分类记忆**：基于文档类型标签（brand_guide / category_knowledge / case_study / compliance_rule）进行检索过滤，属于轻量分类能力。
- **暂不包含**：Neo4j 图存储、自动实体抽取、图谱可视化编辑器。这些属于后续阶段规划。
