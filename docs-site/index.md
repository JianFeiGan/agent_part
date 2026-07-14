# Agent Part 文档

基于 LangGraph 的多 Agent 协作商品视觉生成与刊登系统。

## 快速开始

- [安装指南](getting-started/installation.md) — Docker 与手动安装，完整环境变量配置
- [5 分钟上手](getting-started/quickstart.md) — 快速体验视觉生成、知识库、刊登全流程

## 核心概念

- [系统架构](concepts/architecture.md) — 三大工作流、技术栈、认证与多租户

## 功能模块

| 模块 | 说明 |
|------|------|
| 视觉生成 | 7 Agent 协作：编排→需求分析→创意策划→视觉设计→图片/视频生成→质量审核 |
| 多平台刊登 | 4 Agent 协作：商品导入→素材优化+文案生成(并行)→合规检查→推送 |
| 知识库 Agent | 3 Agent 协作：查询分析→策略路由→混合检索→结果融合→答案生成 |
| RAG 增强 | 向量检索 + Graph RAG + 类目记忆，为视觉生成 Agent 注入知识 |
| AI 会话追踪 | Token 消耗、费用估算、按模型/Agent 分解的使用分析 |
| 认证与多租户 | API Token (SHA256 + Scope) + tenant_id 数据隔离 |

## 更多资源

- [API 文档](http://localhost:8000/docs) — FastAPI 自动生成的交互式 API 文档
- [CHANGELOG](https://github.com/JianFeiGan/agent_part/blob/master/CHANGELOG.md) — 版本变更记录
- [CONTRIBUTING](https://github.com/JianFeiGan/agent_part/blob/master/CONTRIBUTING.md) — 贡献指南
