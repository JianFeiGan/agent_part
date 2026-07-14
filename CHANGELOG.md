# Changelog

本文件记录项目的所有重要变更。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/)。

## [0.2.0] - 2026-07-13

### Added

- 千问百炼 API 对接 — OpenAI 兼容模式（ChatOpenAI）+ DashScope SDK（ChatTongyi）双通道路由
- 百炼平台单一 API Key 同时支持 OpenAI 兼容和 DashScope 原生协议
- DashScope 新图片模型（wan2.7-image-pro）支持，async_call + wait 模式，旧模型 call 模式自动切换
- AI 会话追踪系统 — 5 个 API 端点：会话记录查询、详情、内容搜索、使用量概览、费用预算
- 费用预算系统 — 模型定价表 + 双币种（USD/CNY）+ 日/月预算 + 预估月费
- AI 会话记录前端页面 — 记录列表 + 使用分析 + 费用预算三 Tab
- Listing 工作流 — create_task 端点异步触发 ListingWorkflow 执行
- 前端样式升级 — 深空蓝配色体系、玻璃拟态头部、DM Sans 字体

### Changed

- 前端样式体系全面升级为深空蓝配色

### Fixed

- Visual Designer JSON 解析容错、selling_points 格式兼容
- SimpleNamespace mock 兼容问题
- asyncpg SQL 兼容性 — `:param::vector` 改为 `CAST(:param AS vector)`，可空参数显式类型声明
- Embedding 异步调用 — retriever 中 `embed_single()` 改为 `await aembed_single()`

## [0.1.0] - 2026-03-23

### Added

- LangGraph 7-Agent 协作视觉生成工作流（Orchestrator → 需求分析 → 创意策划 → 视觉设计 → 图片/视频生成 → 质量审核）
- RAG 知识库（PGVector + BGE-large-zh Embedding）
- 合规检查系统（广告法禁词 + 平台规则）
- 多平台刊登适配器骨架（Amazon / eBay / Shopify）
- Vue 3 管理后台（商品管理、任务管理、知识库、刊登工具）
- FastAPI API 服务（40+ REST API 端点）
- Docker Compose 部署（app + frontend + postgres + redis）
