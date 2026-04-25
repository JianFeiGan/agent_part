# 跨境电商刊登工具系统设计文档

> **日期**: 2026-04-25  
> **作者**: ganjianfei  
> **版本**: 1.0.0

---

## 1. 需求概述

### 1.1 背景

当前"跨境电商商品视觉生成系统"已实现多 Agent 协作生成商品图片和视频，但核心外部 API（通义万相、可灵AI）尚未真实对接，且缺少电商刊登能力。运营人员需要将商品信息、素材、文案一次性推送到 Amazon、eBay、Shopify 等多个平台，手动操作繁琐且容易出错。

### 1.2 目标

构建一个**独立刊登工具**，支持：
1. **刊登素材优化** — 按各平台规范自动生成/转换图片视频
2. **刊登文案生成** — 多语言标题、描述、关键词、五点描述
3. **刊登合规检查** — 自动检测素材和文案是否符合平台规范
4. **多平台刊登推送** — 一键推送到 Amazon SP-API、eBay Trading API、Shopify GraphQL

### 1.3 约束

- 商品数据从外部导入（不依赖当前系统的 Product 模型）
- 首批支持平台：Amazon、eBay、Shopify
- 独立部署，可与现有视觉生成系统并存

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 Vue 3                           │
│  商品导入 │ 素材生成 │ 文案生成 │ 合规报告 │ 刊登管理       │
├─────────────────────────────────────────────────────────────┤
│                     FastAPI API 层                          │
├─────────────────────────────────────────────────────────────┤
│              Listing Orchestrator (LangGraph)               │
│  Import → Standardize → [素材 | 文案 | 合规] → Platform Push│
├──────────────┬──────────────┬───────────────┬───────────────┤
│ 素材优化引擎 │ 文案生成引擎  │ 合规检查引擎   │ 平台适配器层   │
│ 图片规范器   │ 标题生成器    │ 图片合规       │ Amazon SP-API │
│ 视频规范器   │ 描述生成器    │ 文案合规       │ eBay Trading  │
│ 尺寸裁剪器   │ 关键词生成    │ 类目合规       │ Shopify GQL   │
│ 格式转换器   │ 多语言翻译    │ 禁词检测       │               │
└──────────────┴──────────────┴───────────────┴───────────────┘
```

### 2.1 核心设计原则

- **标准化中间产物**：素材引擎产出平台无关的标准素材，由适配器转换
- **插件式平台适配**：统一接口，新增平台只需添加适配器
- **并行执行**：素材优化和文案生成并行，多平台推送并行
- **失败隔离**：单平台失败不影响其他平台

---

## 3. 数据模型

### 3.1 ListingProduct（标准化商品）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| sku | str | 商品SKU（唯一） |
| title | str | 商品标题 |
| description | str | 商品描述 |
| category | str | 商品类目 |
| brand | str | 品牌 |
| price | decimal | 价格 |
| weight | decimal | 重量 |
| dimensions | dict | 尺寸 (长x宽x高+单位) |
| source_images | list[ImageRef] | 原始图片素材 |
| attributes | dict | 平台特有属性（键值对） |

### 3.2 ListingTask（刊登任务）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| product_id | int | 关联商品 |
| target_platforms | list[str] | ["amazon","ebay","shopify"] |
| status | enum | PENDING/GENERATING/REVIEWING/PUSHING/COMPLETED/FAILED |
| results | dict | 各平台推送结果 |
| created_at | datetime | 创建时间 |

### 3.3 AssetPackage（素材包）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| listing_task_id | int | 关联任务 |
| platform | str | 目标平台 |
| main_image | str | 主图URL（白底、标准尺寸） |
| variant_images | list[str] | 变体图URL列表 |
| video_url | str | 视频URL |
| a_plus_images | list[str] | A+页面图片 |

### 3.4 CopywritingPackage（文案包）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| listing_task_id | int | 关联任务 |
| platform | str | 目标平台 |
| language | str | 语言代码 |
| title | str | 平台优化标题 |
| bullet_points | list[str] | 五点描述 |
| description | str | 长描述 |
| search_terms | list[str] | 搜索关键词 |

### 3.5 ComplianceReport（合规报告）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| listing_task_id | int | 关联任务 |
| platform | str | 目标平台 |
| overall | enum | PASS/FAIL/WARNING |
| image_issues | list[dict] | 图片不合规项 |
| text_issues | list[dict] | 文案不合规项 |
| forbidden_words | list[str] | 禁词命中 |

### 3.6 PlatformCredential（平台凭证）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| platform | str | amazon/ebay/shopify |
| seller_id | str | 卖家ID |
| marketplace_id | str | 市场ID |
| auth_token | str | 访问令牌 |
| refresh_token | str | 刷新令牌 |
| expires_at | datetime | 过期时间 |

---

## 4. 工作流设计

### 4.1 LangGraph StateGraph

```
START → ImportProductAgent → StandardizeProduct
    → 并行分支:
        ├→ 素材优化分支 (ImageOptimizer + VideoOptimizer)
        └→ 文案生成分支 (Copywriter + Translator)
    → 等待合并 (join)
    → ComplianceChecker (合规卡点)
    → 条件路由:
        ├→ PASS → 并行推送 (Amazon + eBay + Shopify)
        └→ FAIL → END (记录失败原因)
    → 收集结果 → 生成报告 → END
```

### 4.2 并行策略

- 素材优化与文案生成：**并行**（无依赖）
- 合规检查：**阻塞等待**素材+文案都完成后执行
- 多平台推送：**并行**（互不影响）

### 4.3 状态定义

```python
class ListingState(BaseModel):
    product: ListingProduct | None
    asset_packages: dict[str, AssetPackage]    # platform -> package
    copywriting_packages: dict[str, CopywritingPackage]
    compliance_reports: dict[str, ComplianceReport]
    push_results: dict[str, ListingResult]
    target_platforms: list[str]
    error: str | None
    current_step: str
```

---

## 5. 平台适配器设计

### 5.1 统一接口

```python
class PlatformAdapter(ABC):
    @abstractmethod
    async def authenticate(self, credentials: PlatformCredential) -> bool: ...

    @abstractmethod
    async def transform_assets(self, assets: AssetPackage) -> TransformedAssets: ...

    @abstractmethod
    async def transform_copywriting(self, copy: CopywritingPackage) -> PlatformCopy: ...

    @abstractmethod
    async def push_listing(self, product, assets, copy) -> ListingResult: ...

    @abstractmethod
    async def update_listing(self, listing_id, ...) -> ListingResult: ...

    @abstractmethod
    async def delete_listing(self, listing_id) -> bool: ...
```

### 5.2 各平台规范对比

| 要求 | Amazon | eBay | Shopify |
|------|--------|------|---------|
| 主图尺寸 | 白底 1500x1500+ | 白底 1600x1600+ | 自定义 2048x2048 |
| 图片上限 | 9张 | 12张 | 无限 |
| 标题长度 | ≤200字符 | ≤80字符 | 无限制 |
| 五点描述 | 必需 | 无 | 自定义 |
| Search Terms | ≤249字节 | 无 | Tags字段 |

### 5.3 Amazon SP-API 对接

- 认证：LWA OAuth2 + AWS SigV4 签名
- 核心端点：POST /listings/2021-08-01/listings/{sellerId}/{sku}
- 图片上传：createUploadDestinationForResource
- 难点：签名流程复杂，需封装 SigV4 Client

### 5.4 eBay Trading API 对接

- 认证：OAuth2 + RuName
- 核心调用：AddFixedPriceItemCall (XML)
- 图片上传：eBay Picture Service (EPS)
- 难点：XML 格式繁琐，Category Specifics 复杂

### 5.5 Shopify GraphQL 对接

- 认证：API Key 或 OAuth
- 核心操作：productCreate, stagedUploadsCreate, productUpdateMedia
- 难点：无，最灵活的平台

---

## 6. 错误处理与恢复

### 6.1 错误处理策略

| 错误类型 | 策略 |
|----------|------|
| 商品导入失败 | 重试3次 → 记录错误 → 通知用户 |
| 素材生成失败 | 重试2次 → 降级到模板素材 |
| 文案生成失败 | 重试2次 → 使用基础文案模板 |
| 合规检查失败 | 阻断推送 → 标记警告 |
| 平台认证失败 | 刷新token → 重试1次 → 阻断 |
| 平台推送失败 | 记录错误 → 不影响其他平台 |

### 6.2 任务状态机

```
PENDING → GENERATING → REVIEWING → PUSHING → COMPLETED
   │           │            │           │
   │           ▼            │           ▼
   │         FAILED ←───────┘         FAILED
   │           │
   ▼           ▼
RETRY (用户手动触发)
```

### 6.3 部分成功

- 每个平台推送独立事务
- 支持"部分成功"状态（如 Amazon 成功、eBay 失败）
- 提供 `retry_failed()` 方法重新推送失败平台

---

## 7. API 接口设计

### 7.1 商品管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/products/import | 导入商品（手动/平台拉取） |
| GET | /api/v1/products | 商品列表 |
| GET | /api/v1/products/{id} | 商品详情 |
| PUT | /api/v1/products/{id} | 更新商品 |

### 7.2 刊登管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/listings | 创建刊登任务 |
| GET | /api/v1/listings | 刊登任务列表 |
| GET | /api/v1/listings/{id} | 刊登详情（含结果） |
| POST | /api/v1/listings/{id}/retry | 重试失败平台 |
| GET | /api/v1/listings/{id}/compliance | 合规报告 |

### 7.3 平台管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/platforms/authenticate | 平台认证配置 |
| GET | /api/v1/platforms/status | 平台连接状态 |
| DELETE | /api/v1/platforms/{platform} | 移除平台 |

---

## 8. 分期交付计划

### Phase 1: 素材优化 + 文案生成（第1-2周）
- 商品导入与标准化
- 素材优化引擎（图片规范、视频规范、尺寸裁剪）
- 文案生成引擎（标题、描述、关键词、多语言）
- 前端：商品导入、素材预览、文案编辑

### Phase 2: 合规检查（第3周）
- 合规检查引擎（图片合规、文案合规、禁词检测）
- 合规报告展示
- 前端：合规报告查看、修复建议

### Phase 3: Amazon 平台适配器（第4-5周）
- Amazon SP-API 对接
- SigV4 签名封装
- 图片上传与 Listing 推送

### Phase 4: eBay + Shopify 平台适配器（第6周）
- eBay Trading API 对接
- Shopify GraphQL 对接
- 多平台并行推送

### Phase 5: 前端完善与测试（第7-8周）
- 刊登管理界面
- 端到端测试
- 性能优化

---

## 9. 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| AI 框架 | LangChain + LangGraph | 工作流编排 |
| LLM | Qwen3.5-flash | 文案生成 |
| Web | FastAPI | REST API |
| 数据库 | PostgreSQL + PGVector | 关系+向量存储 |
| 缓存 | Redis | 任务状态 |
| 前端 | Vue 3 + TypeScript | 用户界面 |
| 包管理 | uv | Python 依赖 |
