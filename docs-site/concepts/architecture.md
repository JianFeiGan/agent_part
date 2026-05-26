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
