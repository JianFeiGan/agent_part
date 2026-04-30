# Changelog

## [v1.0.0] - 2026-04-30

### 新增功能

#### 刊登工具核心
- 新增 LangGraph 工作流引擎，支持商品导入 → 素材优化 → 文案生成 → 合规检查全流程
- 实现 7 个专业 Agent：ImportProduct、AssetOptimizer、Copywriter、ComplianceChecker 等
- 支持 Amazon、eBay、Shopify 三大平台的刊登推送

#### 数据库持久化层
- 新增 7 张 ORM 模型表：listing_products、listing_tasks、asset_packages、copywriting_packages、compliance_reports、task_results、adapter_configs
- 实现通用异步 `BaseRepository` 基类，支持 CRUD 操作
- 将 API 层从内存字典迁移到 PostgreSQL 数据库

#### 适配器配置管理
- 实现 `AdapterConfigManager` 单例 + 5 分钟 TTL 缓存
- 新增适配器配置 CRUD API（创建、查询、更新、删除）
- 新增 Vue 3 前端管理页面（AdapterConfig.vue）

#### 平台适配器
- 实现 `BasePlatformAdapter` 抽象基类 + `AdapterRegistry` 注册表
- 实现 Amazon SP-API 适配器（LWA OAuth2 认证）
- 实现 eBay Trading API 适配器（OAuth2 + XML）
- 实现 Shopify GraphQL 适配器（API Key 认证）

#### AI 文案生成
- 实现 `AICopywritingAgent`，支持多 LLM 降级策略（Tongyi → Claude → Rules）
- 支持多语言文案生成和平台风格适配

#### 合规检查
- 实现 `ComplianceCheckerAgent`，支持图片和文本合规检查
- 支持禁词检测和平台规则验证

#### 前端管理界面
- 新增商品导入页面（ProductImport.vue）
- 新增任务列表页面（TaskList.vue）
- 新增任务详情页面（TaskDetail.vue，含合规报告和推送结果）
- 新增适配器配置管理页面（AdapterConfig.vue）

### 测试覆盖
- 112 个刊登模块相关测试全部通过
- API 测试采用 mock 数据库层模式，无需真实数据库
- 前端构建成功

### 技术栈
- Python 3.13, FastAPI, SQLAlchemy 2.0, Pydantic v2
- LangGraph, LangChain
- Vue 3, TypeScript, Element Plus
- PostgreSQL + pgvector
