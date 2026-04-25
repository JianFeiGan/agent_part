# 刊登工具迭代设计文档 (Phase 3-5 增强)

> 日期: 2026-04-25
> 状态: 已确认
> 涉及模块: src/agents/, src/api/, src/db/, src/graph/, frontend/

---

## 1. 概述

在现有刊登工具（平台适配器 + 推送 API + 前端）基础上，完成四项增强：

1. **真实工作流执行** — 将 LangGraph 工作流中的占位节点替换为真实 Agent 调用
2. **AI 文案生成** — 集成 LLM（通义千问 / Claude 切换）生成高质量文案
3. **适配器配置管理** — 数据库存储平台凭证，支持多店铺
4. **数据库持久化** — 用 SQLAlchemy + PostgreSQL 替换所有内存字典

## 2. 架构设计

### 2.1 三层架构

```
┌─────────────────────────────────────────────────┐
│              前端 (Vue 3 + Element Plus)          │
│  商品导入 | 任务列表 | 任务详情 | 配置管理        │
├─────────────────────────────────────────────────┤
│              API 层 (FastAPI)                     │
│  /listing/import-product                          │
│  /listing/tasks (POST with auto_execute)         │
│  /listing/tasks/{id}/execute (手动触发)          │
│  /listing/tasks/{id}/status                      │
│  /listing/tasks/{id}/push (使用已生成数据)       │
│  /listing/adapter-configs (CRUD)                │
├─────────────────────────────────────────────────┤
│              业务层                               │
│  ┌─────────────┐  ┌──────────────┐               │
│  │ LangGraph   │  │ AICopywriter │               │
│  │ Workflow    │  │ (Multi-LLM)  │               │
│  └─────────────┘  └──────────────┘               │
│  ┌─────────────┐  ┌──────────────┐               │
│  │ Adapter     │  │ Compliance   │               │
│  │ Registry    │  │ Checker      │               │
│  └─────────────┘  └──────────────┘               │
├─────────────────────────────────────────────────┤
│              持久层 (PostgreSQL + SQLAlchemy)     │
│  7 张表: products, tasks, assets, copywriting,  │
│         compliance, results, adapter_configs     │
└─────────────────────────────────────────────────┘
```

### 2.2 API 端点变更

| 端点 | 方法 | 变更 |
|------|------|------|
| `POST /tasks` | 修改 | 新增 `auto_execute` 参数，为 true 则自动启动工作流 |
| `POST /tasks/{id}/execute` | 新增 | 手动触发工作流 |
| `GET /tasks/{id}/status` | 新增 | 查询工作流进度 |
| `POST /tasks/{id}/push` | 修改 | 从数据库读取已生成的素材/文案，不再创建空包 |
| `POST /adapter-configs` | 新增 | 创建适配器配置 |
| `GET /adapter-configs` | 新增 | 列出所有配置（脱敏） |
| `PUT /adapter-configs/{id}` | 新增 | 更新配置 |
| `DELETE /adapter-configs/{id}` | 新增 | 删除配置 |

## 3. 组件详细设计

### 3.1 AI 文案生成器 (AICopywritingAgent)

**文件**: `src/agents/listing_copywriter.py` (改造)

- 继承 `BaseAgent`，使用 `invoke_llm()` 能力
- `LLMProvider` 枚举: `TONGYI` / `CLAUDE` / `FALLBACK`
- 生成流程: 规则草稿 → LLM 润色 → 最终输出
- LLM 降级策略: 通义千问(主) → Claude(备选) → 规则模式(兜底)
- 每次 LLM 调用 10 秒超时，超时自动降级
- 配置从 `settings.py` 读取 `llm_model`，支持运行时切换

### 3.2 适配器配置管理器

**文件**: `src/agents/adapter_config.py` (新建)

- 从 `adapter_configs` 表读取凭证
- 支持多店铺（同平台多配置，`shop_id` 区分）
- `get_config(platform, shop_id)` → `dict`
- 内存缓存 + 5 分钟过期
- `AdapterRegistry.get()` 改为从此管理器读取配置

### 3.3 数据库持久化层

**文件**: `src/db/models.py`, `src/db/repository.py`, `src/db/session.py` (新建)

7 张表 ORM 映射:

| 表名 | ORM 类 | 说明 |
|------|--------|------|
| `listing_products` | `ListingProductPO` | 商品主表 |
| `listing_tasks` | `ListingTaskPO` | 任务表，含 `workflow_state` |
| `asset_packages` | `AssetPackagePO` | 素材包，图片存 OSS URL |
| `copywriting_packages` | `CopywritingPackagePO` | 文案包 |
| `compliance_reports` | `ComplianceReportPO` | 合规报告 JSONB |
| `task_results` | `TaskResultPO` | 推送结果 JSONB |
| `adapter_configs` | `AdapterConfigPO` | 适配器配置 JSON |

**关键设计**:
- 图片统一存 OSS URL，不存二进制
- 合规报告/推送结果用 JSONB 存储
- LangGraph Checkpointer 从 `MemorySaver` 改为 `PostgresSaver`

## 4. 数据流

```
用户导入商品 → POST /import-product → 写入 listing_products
    │
创建任务 (auto_execute) → 写入 listing_tasks → 启动 LangGraph
    │
    ├── _asset_optimize_node (真实调用视觉 Agent)
    ├── _copy_node (LLM 文案生成)
    └── _compliance_node (合规检查)
            │
            ▼
    结果写入 asset_packages / copywriting_packages / compliance_reports
    task status = generated
            │
            ▼
    用户推送 → POST /tasks/{id}/push → 读取已生成数据 → push_listing()
            │
            ▼
    结果写入 task_results
```

## 5. 错误处理

| 层级 | 策略 |
|------|------|
| LLM 超时/错误 | 10s → 备选 LLM → 规则降级 |
| 平台 API 错误 | 返回 PushResult(success=False)，不抛异常 |
| 数据库错误 | 连接池重连 3 次，唯一约束冲突返回 409 |
| 工作流节点异常 | 标记 task=failed，不影响并行节点 |

## 6. 测试策略

| 类型 | 工具 | 范围 |
|------|------|------|
| 单元测试 | pytest + AsyncMock | AICopywritingAgent, AdapterConfigManager |
| LLM Mock | pytest-mock | 模拟 Tongyi/Claude/超时/降级 |
| 数据库测试 | 测试库 + fixture | ORM CRUD |
| 集成测试 | TestClient + mock 平台 API | 完整工作流 |
| 回归测试 | 现有 93 个 listing 测试 | 确保不破坏 |

## 7. 实现顺序

1. 数据库层 (models, repository, session)
2. 适配器配置管理器
3. AI 文案生成器改造
4. 工作流真实接线
5. API 层改造 (双写 → 数据库)
6. 前端配置管理页面
7. 全面测试 + 清理内存代码
