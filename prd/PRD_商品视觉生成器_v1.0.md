# PRD：商品视觉生成器（Product Visual Generator）

| 字段 | 内容 |
|------|------|
| **文档版本** | v1.0 |
| **产品版本** | v0.1.0（Late Prototype / Early MVP） |
| **作者** | 产品经理（AI 辅助生成） |
| **创建日期** | 2026-06-10 |
| **状态** | 草稿 |

---

## 1. 概述

商品视觉生成器是一个基于 LangGraph/LangChain 构建的**多 Agent 协作商品视觉内容自动生成系统**。系统通过 7 个专业 Agent 协同工作，实现跨境电商商品营销图片和视频的自动化生成，同时支持多平台（Amazon/eBay/Shopify）刊登文案生成与合规检查。

核心价值主张：**将商品信息输入后，自动产出可直接上架的营销视觉素材和平台刊登内容，降低跨境电商卖家的内容制作成本和人力投入。**

---

## 2. 背景与证据

### 2.1 业务背景

跨境电商卖家在多平台运营中面临以下痛点：

1. **视觉内容制作成本高**：每个商品需要主图、场景图、卖点图、视频等多种素材，外包设计单价高、周期长。
2. **多平台适配重复劳动**：Amazon、eBay、Shopify 各有不同的图片规格、文案格式和合规要求，同一商品需要多次手动适配。
3. **合规风险**：各平台广告法和规则差异大，人工检查容易遗漏禁词或违规内容。
4. **品牌一致性难维护**：大量 SKU 的视觉风格、配色、文案调性难以统一管理。

### 2.2 技术背景

- 大语言模型（通义千问 qwen3.5-flash）可用于商品分析、创意策划、文案生成。
- 图像生成模型（通义万象 wanx-v1）可用于营销图片自动生成。
- 视频生成模型（可灵 AI kling-v1）可用于商品短视频自动生成。
- RAG（检索增强生成）可注入品牌规范、类目知识和合规规则，提升生成质量和一致性。
- LangGraph 提供了成熟的多 Agent 状态图编排能力，适合流水线式的协作任务。

### 2.3 当前项目成熟度

| 模块 | 状态 | 说明 |
|------|------|------|
| 核心工作流引擎 | 已实现 | 7 节点 LangGraph StateGraph，条件路由 |
| 7 个核心 Agent | 已实现 | LLM 驱动的分析/策划 Agent 已接入通义千问 |
| 图片生成 Agent | **Mock 状态** | 结构完整，API 调用未接入真实 DashScope |
| 视频生成 Agent | **Mock 状态** | 结构完整，API 调用未接入真实可灵 AI |
| 刊登工作流 | 已实现 | 4 节点独立流水线，LLM 文案生成可用 |
| 平台适配器 | 结构实现 | Amazon/eBay/Shopify 适配器已有认证流程和格式转换，未连接真实 API |
| RAG 模块 | 已实现 | BGE-large-zh + PGVector 向量检索 |
| REST API | 已实现 | 8 个路由模块，完整 CRUD |
| 前端管理 UI | 已实现 | Vue 3 + Element Plus，含商品管理、任务管理、知识库、刊登工具 |
| 测试 | 已实现 | 112 个测试通过 |
| API 认证/授权 | **未实现** | 所有端点无认证 |
| 文件上传 | **未实现** | 返回 Mock URL |
| OSS 存储 | **未实现** | 配置存在但无集成代码 |
| 两个工作流联通 | **未实现** | 视觉生成与刊登流程独立运行 |

---

## 3. 目标与成功标准

### 3.1 产品目标

| 编号 | 目标 | 描述 |
|------|------|------|
| G1 | 自动化视觉内容生成 | 输入商品信息，自动输出主图、场景图、卖点图和商品短视频 |
| G2 | 多平台一键刊登 | 自动生成符合各平台规范的文案和素材包，支持推送至 Amazon/eBay/Shopify |
| G3 | 品牌一致性保障 | 通过 RAG 知识库注入品牌规范，确保生成内容的视觉和文案风格统一 |
| G4 | 合规风险降低 | 内置广告法禁词检测和平台规则验证，减少人工审核负担 |
| G5 | 降低内容制作门槛 | 无需专业设计技能即可产出可商用级别的营销素材 |

### 3.2 成功标准

| 指标 | 目标值 | 度量方式 |
|------|--------|----------|
| 图片生成成功率 | >= 90% | 质量审核通过率（overall_score >= 0.7） |
| 视频生成成功率 | >= 80% | 视频生成任务完成率 |
| 文案合规通过率 | >= 95% | 合规检查 PASS 比例 |
| 单商品素材生成时间 | <= 10 分钟 | 从任务创建到 AssetCollection 完成 |
| 端到端刊登流程可用 | 完整闭环 | 商品输入 → 素材生成 → 文案生成 → 合规检查 → 平台推送 |

---

## 4. 目标用户与场景

### 4.1 目标用户

| 用户角色 | 描述 | 核心诉求 |
|----------|------|----------|
| **跨境电商卖家** | 在 Amazon/eBay/Shopify 上运营店铺的中小卖家 | 快速生成商品图片和视频，降低设计外包成本 |
| **营销团队** | 负责商品推广和视觉内容制作的团队 | 批量生成风格统一的营销素材，提升效率 |
| **品牌管理者** | 需要维护品牌视觉一致性的品牌方 | 通过知识库确保生成内容符合品牌规范 |
| **运营人员** | 负责多平台上架和日常运营的人员 | 一键多平台刊登，减少重复劳动 |

### 4.2 核心使用场景

**场景 S1：新品上架视觉生成**
- 卖家上新一个商品，录入商品名称、类目、描述、卖点
- 选择生成类型（图片+视频）、风格偏好
- 系统自动分析卖点 → 策划创意方案 → 生成主图/场景图/卖点图 + 商品视频
- 质量审核通过后，卖家下载素材用于上架

**场景 S2：多平台刊登文案生成**
- 运营人员导入商品信息，选择目标平台（如 Amazon + Shopify）
- 系统自动生成各平台规范的标题、五点描述、长描述、搜索关键词
- 合规检查后输出文案包，运营人员确认后推送到平台

**场景 S3：品牌规范增强生成**
- 品牌管理者上传品牌指南、视觉规范文档到知识库
- 后续所有生成任务自动检索品牌规范，确保配色、风格、文案调性一致
- 合规审核 Agent 加载合规规则，拦截违规内容

**场景 S4：批量商品视觉更新**
- 营销团队需要为一批商品更新季节性营销图片
- 批量录入商品，统一选择风格和主题（如"圣诞促销"）
- 系统批量生成并输出素材集合

---

## 5. 范围

### 5.1 本期范围（In Scope）

| 模块 | 范围 |
|------|------|
| 视觉生成工作流 | Orchestrator → RequirementAnalyzer → CreativePlanner → VisualDesigner → ImageGenerator/VideoGenerator → QualityReviewer |
| 刊登工作流 | ImportProduct → [AssetOptimizer + Copywriter] → ComplianceCheck |
| Agent 层 | 7 个核心 Agent + 3 个 RAG 增强变体 + 4 个刊登 Agent + 3 个平台适配器 |
| RAG 知识库 | 文档上传、分块、向量化、检索，支持品牌规范/类目知识/案例/合规规则 |
| REST API | 商品管理、任务管理、知识库管理、刊登工具、RAG 评估 |
| 前端 UI | 商品管理、任务管理（含 WebSocket 实时状态）、知识库管理、刊登工具 |
| 部署 | Docker Compose（Backend + Frontend + PostgreSQL + Redis） |

### 5.2 非目标（Non-Goals）

| 编号 | 非目标 | 原因 |
|------|--------|------|
| NG1 | 实时图片/视频编辑 | 系统定位为自动生成，非设计工具 |
| NG2 | 用户社交/协作功能 | MVP 阶段聚焦单人操作 |
| NG3 | 多租户 SaaS 平台 | 当前为单租户部署 |
| NG4 | 自建图像/视频生成模型 | 依赖第三方 API（DashScope、可灵 AI） |
| NG5 | 移动端 App | 当前仅提供 Web 管理后台 |
| NG6 | 商品数据爬取/竞品监控 | 不在当前产品边界内 |

---

## 6. 用户流程

### 6.1 视觉内容生成主流程

```
用户录入商品信息
    │
    ▼
选择生成类型和参数
（图片类型、数量、视频时长、风格偏好）
    │
    ▼
提交生成任务 ──▶ 任务状态: pending
    │
    ▼
┌─────────────────────────────────────────────┐
│          LangGraph 工作流自动执行             │
│                                              │
│  1. Orchestrator: 校验输入，分解任务          │
│  2. RequirementAnalyzer: 分析商品，提取卖点    │
│  3. CreativePlanner: 生成创意方案 + 配色       │
│  4. VisualDesigner: 设计图片 Prompt + 分镜     │
│  5. ImageGenerator: 调用图像 API 生成图片      │
│  6. VideoGenerator: 调用视频 API 生成视频      │
│  7. QualityReviewer: 质量评分 + 问题检测       │
│                                              │
│  [WebSocket 实时推送进度到前端]                │
└─────────────────────────────────────────────┘
    │
    ▼
任务完成 ──▶ 展示 AssetCollection
    │
    ├── 查看生成的图片（主图/场景图/卖点图）
    ├── 查看生成的视频
    ├── 查看质量报告（评分、问题、建议）
    └── 下载素材包
```

### 6.2 刊登流程

```
用户导入商品信息（SKU、标题、描述、图片）
    │
    ▼
选择目标平台（Amazon / eBay / Shopify）
    │
    ▼
提交刊登任务 ──▶ 任务状态: pending
    │
    ▼
┌─────────────────────────────────────────────┐
│          刊登工作流自动执行                    │
│                                              │
│  1. ImportProduct: 标准化商品数据              │
│  2a. AssetOptimizer: 按平台规格优化素材        │
│  2b. Copywriter: LLM 生成平台文案（并行）      │
│  3. ComplianceCheck: 禁词 + 规则检查           │
└─────────────────────────────────────────────┘
    │
    ▼
用户审核文案包和合规报告
    │
    ├── 通过 ──▶ 推送到目标平台
    └── 不通过 ──▶ 手动修改后重新检查
```

### 6.3 异常状态处理

| 异常 | 处理方式 |
|------|----------|
| LLM 调用失败 | 记录错误日志，任务标记为 failed，返回错误信息 |
| 图像/视频 API 超时 | 任务标记失败，支持重试（TODO: 需实现重试机制） |
| 合规检查不通过 | 输出 ComplianceReport 列出所有问题和建议，阻止推送 |
| 工作流中途出错 | error 字段记录错误，条件路由直接到 END |
| 平台推送失败 | 记录失败原因，任务结果中标记推送状态 |

---

## 7. 功能需求

### 7.1 商品管理模块

#### Requirement R1: 商品信息录入与管理

- **用户故事**: 作为跨境电商卖家，我想录入商品的名称、类目、描述、卖点和规格信息，以便系统能基于这些信息生成视觉内容。
- **功能行为**:
  - 支持创建、查询、更新、删除商品
  - 商品字段包含：名称、品牌、类目（9 类）、描述、短描述、卖点列表、规格列表、目标人群、价格区间、已有素材、标签
  - 卖点支持 4 种类型：功能卖点、情感卖点、差异化卖点、场景卖点
  - 卖点优先级 1-5 级
- **数据模型**: `Product`, `ProductCategory`, `SellingPoint`, `SellingPointType`, `ProductSpec`
- **边界情况**:
  - 名称 2-100 字符，描述 10-2000 字符
  - 卖点标题 2-50 字符，描述 5-500 字符
- **验收标准**:
  - 能通过 API 成功创建商品并返回 product_id
  - 能通过 GET 接口查询商品详情
  - 字段校验不通过时返回明确错误信息
- **优先级**: P0

#### Requirement R2: 商品图片上传

- **用户故事**: 作为卖家，我想上传商品的已有图片作为参考素材，以便系统在设计时参考。
- **功能行为**:
  - 支持商品图片上传，返回图片 URL
  - 图片存储到本地或 OSS
- **当前状态**: **未实现（Mock URL）**
- **验收标准**:
  - 上传图片后返回可访问的 URL
  - 图片可在商品详情中查看
- **优先级**: P1

### 7.2 视觉生成工作流模块

#### Requirement R3: 生成任务创建与配置

- **用户故事**: 作为卖家，我想为指定商品创建一个视觉生成任务，选择要生成的内容类型和风格偏好。
- **功能行为**:
  - 任务类型：仅图片 / 仅视频 / 图片+视频
  - 图片配置：图片类型（main/scene/selling_point）、每种类型数量
  - 视频配置：时长（秒）、风格
  - 风格偏好：自由文本描述
  - 配色偏好：自由文本描述
  - 质量等级：standard / high
- **数据模型**: `GenerationRequest`
- **验收标准**:
  - 提交任务后返回 task_id 和初始状态
  - 任务配置参数正确传递到工作流
- **优先级**: P0

#### Requirement R4: 编排调度（Orchestrator Agent）

- **用户故事**: 作为系统，我需要一个编排 Agent 来校验输入、分解任务、规划执行顺序。
- **功能行为**:
  - 验证商品信息和生成请求的完整性
  - 使用 LLM 进行任务分解和执行顺序规划
  - 初始化工作流状态
- **验收标准**:
  - 输入不完整时返回明确的错误信息
  - 成功初始化 AgentState 并标记当前步骤
- **优先级**: P0

#### Requirement R5: 需求分析（RequirementAnalyzer Agent）

- **用户故事**: 作为系统，我需要一个分析 Agent 来深入理解商品信息，提取核心卖点和关键词。
- **功能行为**:
  - 分析商品描述，提取关键特性
  - 分类整理卖点（功能/情感/差异化/场景）
  - 识别目标人群
  - 生成风格推荐和关键词
  - 输出 `RequirementReport`
- **RAG 增强**: `RAGEnhancedRequirementAnalyzer` 检索品牌规范和类目知识辅助分析
- **验收标准**:
  - 输出的 RequirementReport 包含 product_summary, key_features, selling_points, target_audience, style_recommendations, keywords
  - RAG 启用时检索来源被记录到 rag_sources
- **优先级**: P0

#### Requirement R6: 创意策划（CreativePlanner Agent）

- **用户故事**: 作为系统，我需要一个创意 Agent 来基于需求分析结果，生成创意方案和配色方案。
- **功能行为**:
  - 生成创意主题和风格方案
  - 设计配色方案（主色、辅色、强调色）
  - 确定视觉元素和排版方向
  - 输出 `CreativePlan` 和 `ColorPalette`
- **支持风格**: 8 种预设视觉风格（modern/minimalist/luxury/playful/natural/tech/vintage/artistic）
- **RAG 增强**: `RAGEnhancedCreativePlanner` 检索品牌视觉规范和类目风格参考
- **验收标准**:
  - 输出的 CreativePlan 包含 theme, style, color_scheme, visual_elements
  - ColorPalette 包含主色/辅色/强调色的 HEX 值
- **优先级**: P0

#### Requirement R7: 视觉设计（VisualDesigner Agent）

- **用户故事**: 作为系统，我需要一个设计 Agent 来将创意方案转化为具体的图片生成提示词和视频分镜脚本。
- **功能行为**:
  - 为每种图片类型设计 prompt 和 negative_prompt
  - 设计视频分镜脚本（Storyboard），包含场景、镜头类型、转场、文字叠加
  - 输出 `generation_prompts` 和 `Storyboard`
- **分镜支持**: 8 种镜头类型（wide/medium/close_up/extreme_close_up/over_shoulder/pov/aerial/macro），6 种转场类型
- **验收标准**:
  - 每种请求的图片类型都有对应的 prompt
  - Storyboard 包含完整的场景列表，每个场景有 duration, description, visual_prompt
- **优先级**: P0

#### Requirement R8: 图片生成（ImageGenerator Agent）

- **用户故事**: 作为系统，我需要调用图像生成 API 来根据 prompt 生成营销图片。
- **功能行为**:
  - 调用通义万象（wanx-v1）API 生成图片
  - 支持主图（白底产品图）、场景图（使用场景）、卖点图（带文字标注）
  - 记录生成参数（模型、seed、style）
  - 输出 `GeneratedImage` 列表
- **当前状态**: **Mock 状态 — 返回模拟 URL，未接入真实 API**
- **验收标准**:
  - 调用真实 DashScope API 并返回可访问的图片 URL
  - 图片尺寸和格式符合请求参数
  - 生成失败时记录 error_message 并标记 status=failed
- **优先级**: P0（**核心功能缺口**）

#### Requirement R9: 视频生成（VideoGenerator Agent）

- **用户故事**: 作为系统，我需要调用视频生成 API 来根据分镜脚本生成商品短视频。
- **功能行为**:
  - 调用可灵 AI（kling-v1）API 生成视频
  - 按分镜脚本组织视频内容
  - 支持进度跟踪（progress 0-100）
  - 输出 `GeneratedVideo`
- **当前状态**: **Mock 状态 — 返回模拟 URL，未接入真实 API**
- **验收标准**:
  - 调用真实可灵 AI API 并返回可访问的视频 URL
  - 视频时长和分辨率符合请求参数
  - 生成失败时记录错误并标记状态
- **优先级**: P0（**核心功能缺口**）

#### Requirement R10: 质量审核（QualityReviewer Agent）

- **用户故事**: 作为系统，我需要一个审核 Agent 来评估生成图片和视频的质量，识别问题并给出改进建议。
- **功能行为**:
  - 对每张图片/视频生成质量评分（overall/clarity/composition/color/relevance，0-1 分）
  - 检测问题类型（模糊、色彩偏差、构图问题、相关性不足等）
  - 问题严重度分级（low/medium/high）
  - 给出改进建议
  - 判断是否通过（overall_score >= 0.7）
  - 输出 `QualityReport`
- **RAG 增强**: `RAGEnhancedQualityReviewer` 加载合规规则进行内容审核
- **验收标准**:
  - 每个生成资源都有对应的 QualityReport
  - passed=true 的资源可直接使用
  - passed=false 的资源有明确的问题描述和改进建议
- **优先级**: P0

### 7.3 刊登工具模块

#### Requirement R11: 刊登商品导入

- **用户故事**: 作为运营人员，我想导入商品信息（SKU、标题、描述、图片），以便创建刊登任务。
- **功能行为**:
  - 支持手动录入或 API 导入标准化商品数据
  - 商品数据包含：SKU、标题、描述、类目、品牌、价格、重量、尺寸、原始图片
  - 输出 `ListingProduct`
- **验收标准**:
  - 导入的商品数据存入 PostgreSQL
  - SKU 唯一性校验
- **优先级**: P1

#### Requirement R12: 多平台文案生成

- **用户故事**: 作为运营人员，我想为商品自动生成符合各平台规范的文稿（标题、五点描述、长描述、搜索关键词）。
- **功能行为**:
  - LLM 驱动的多语言文案生成
  - 多 LLM 降级策略：通义千问 → Claude → 规则模板
  - 按平台规格输出文案包（CopywritingPackage）
  - 每个平台独立的标题、bullet_points、description、search_terms
- **验收标准**:
  - 文案包含各平台要求的完整字段
  - LLM 不可用时降级到规则模板仍能输出
- **优先级**: P1

#### Requirement R13: 合规检查

- **用户故事**: 作为运营人员，我想在推送前自动检查文案和图片是否符合广告法和平台规则。
- **功能行为**:
  - 广告法禁词检测
  - 平台特有规则验证（Amazon/eBay/Shopify 各有规则集）
  - 图片规格合规检查（尺寸、比例）
  - 输出 `ComplianceReport`，包含 pass/fail/warning 三级问题
  - 每条问题附带修复建议
- **验收标准**:
  - 包含禁词的文案被标记为 FAIL
  - 合规报告列出所有问题及建议
  - 合规不通过时阻止平台推送
- **优先级**: P1

#### Requirement R14: 平台推送

- **用户故事**: 作为运营人员，我想将审核通过的素材和文案一键推送到目标电商平台。
- **功能行为**:
  - Amazon SP-API 推送（LWA OAuth2 认证）
  - eBay Trading API 推送（OAuth2 + XML）
  - Shopify GraphQL 推送（API Key 认证）
  - 适配器注册表模式，可扩展新平台
  - 适配器配置管理（CRUD + 5 分钟 TTL 缓存）
- **当前状态**: 结构实现，未连接真实平台 API
- **验收标准**:
  - 推送成功后返回平台侧 ID 或链接
  - 推送失败时记录原因，不影响其他平台推送
- **优先级**: P2

### 7.4 RAG 知识库模块

#### Requirement R15: 知识库文档管理

- **用户故事**: 作为品牌管理者，我想上传品牌指南、类目知识、成功案例和合规规则文档，以便系统在生成时参考。
- **功能行为**:
  - 支持文档上传（.md, .txt, .json, .pdf, .docx）
  - 文档类型分类：brand_guide / category_knowledge / case_study / compliance_rule
  - 自动语义分块 + BGE-large-zh 向量化
  - 存入 PGVector（1024 维）
  - 文档 CRUD 管理
- **验收标准**:
  - 上传文档后成功分块并向量化
  - 能通过搜索接口检索到相关文档片段
- **优先级**: P1

#### Requirement R16: RAG 检索增强

- **用户故事**: 作为系统，我想在需求分析、创意策划和质量审核时自动检索知识库，提升生成质量。
- **功能行为**:
  - RAG 开关（rag_enabled）控制是否启用
  - 启用时 3 个 Agent 自动切换为 RAG 增强变体
  - 检索结果注入 Agent Prompt 上下文
  - 记录检索来源到 rag_sources
- **验收标准**:
  - RAG 启用后生成结果中 rag_sources 非空
  - 知识库中有品牌规范时，生成结果体现品牌风格一致性
- **优先级**: P1

#### Requirement R17: RAG 效果评估

- **用户故事**: 作为产品经理，我想评估 RAG 检索的命中率和增强效果，以便优化知识库。
- **功能行为**:
  - 命中率统计
  - RAG vs 非 RAG 对比评估
  - 评估报告生成
  - 优化建议输出
- **验收标准**:
  - 评估报告包含命中率、召回率等指标
  - 优化建议可操作
- **优先级**: P2

### 7.5 前端管理界面模块

#### Requirement R18: 商品管理页面

- **用户故事**: 作为用户，我想通过 Web 界面管理商品信息（增删改查）。
- **功能行为**: 商品列表、创建表单、详情查看、编辑、删除
- **验收标准**: 所有 CRUD 操作可通过 UI 完成
- **优先级**: P1

#### Requirement R19: 任务管理与实时监控

- **用户故事**: 作为用户，我想创建生成任务并实时查看执行进度。
- **功能行为**:
  - 任务创建表单（选择商品、配置参数）
  - 任务列表和详情
  - WebSocket 实时推送 Agent 执行进度
  - 任务取消功能
- **验收标准**:
  - 任务进度在前端实时更新
  - 可查看每个 Agent 的执行日志
- **优先级**: P1

#### Requirement R20: 知识库管理页面

- **用户故事**: 作为品牌管理者，我想通过 Web 界面上传和管理知识库文档。
- **功能行为**: 文档上传、列表、删除、搜索测试
- **验收标准**: 文档管理全流程可通过 UI 完成
- **优先级**: P1

#### Requirement R21: 刊登工具页面

- **用户故事**: 作为运营人员，我想通过 Web 界面导入商品、创建刊登任务、查看合规报告和配置平台适配器。
- **功能行为**:
  - 商品导入页面
  - 刊登任务列表和详情页（含合规报告和推送结果）
  - 适配器配置管理页面
- **验收标准**: 刊登全流程可通过 UI 完成
- **优先级**: P1

---

## 8. 非功能需求

### 8.1 性能

| 指标 | 要求 |
|------|------|
| API 响应时间（非生成类） | <= 500ms |
| 单商品图片生成（3 张） | <= 5 分钟 |
| 单商品视频生成（30s） | <= 10 分钟 |
| 刊登文案生成（3 平台） | <= 2 分钟 |
| RAG 检索延迟 | <= 1 秒 |

### 8.2 可靠性

- LLM 调用失败时有明确错误返回，不产生脏数据
- 多 LLM 降级策略确保文案生成可用性（Tongyi → Claude → Rules）
- 工作流错误通过 AgentState.error 字段透传，不静默吞掉
- LangGraph MemorySaver 支持断点恢复

### 8.3 安全性

- **当前状态**: 所有 API 端点无认证，CORS 全开放 — **需要在上线前实现认证/授权**
- 适配器凭证需加密存储（当前仅做掩码展示）
- 知识库文档不应包含敏感凭证信息

### 8.4 可扩展性

- Agent 基类模式支持快速添加新 Agent
- 适配器注册表模式支持快速添加新电商平台
- RAG 知识库支持动态添加新文档类型

### 8.5 可观测性

- 每个 Agent 执行记录 `AgentLog`（开始/结束时间、状态、消息、输出摘要）
- RAG 使用日志记录检索次数、命中率
- 任务状态通过 WebSocket 实时推送

---

## 9. 数据模型概览

### 9.1 视觉生成域

```
Product (商品信息)
├── ProductCategory (9 类: digital/clothing/food/beauty/home/sports/baby/pet/other)
├── SellingPoint[] (卖点: title/description/type/priority/keywords)
│   └── SellingPointType (functional/emotional/differentiation/scenario)
└── ProductSpec[] (规格: name/value/unit)

GenerationRequest (生成请求)
├── task_type (image_only/video_only/image_and_video)
├── image_types[] + image_count_per_type
├── video_duration + video_style
└── style_preference + color_preference

AgentState (工作流状态 — 20+ 字段)
├── 输入: product_info, generation_request
├── 分析: requirement_report, selling_points[]
├── 创意: creative_plan, color_palette
├── 设计: generation_prompts[]
├── 生成: generated_images[], storyboard, generated_video
├── 审核: quality_reports[], quality_score, issues[]
├── 输出: asset_collection, final_results
├── RAG: rag_sources[], rag_context, rag_enabled
└── 元数据: current_step, completed_steps[], agent_logs[]

GeneratedImage (生成图片)
├── image_type (main/scene/selling_point)
├── prompt + negative_prompt
├── url/local_path, format (png/jpeg/webp)
├── width x height, file_size
└── status (pending/generating/completed/failed)

GeneratedVideo (生成视频)
├── storyboard_id, visual_prompt
├── url/local_path, format (mp4/webm/mov)
├── width x height, duration, fps
└── status + progress (0-100)

QualityReport (质量报告)
├── QualityScore (overall/clarity/composition/color/relevance, 0-1)
├── QualityIssue[] (type/severity/description/suggestion)
└── passed (bool)
```

### 9.2 刊登域

```
ListingProduct (刊登商品)
├── sku, title, description, category, brand
├── price, weight, dimensions
└── source_images[] (ImageRef: url/is_main/width/height)

ListingTask (刊登任务)
├── product_id, target_platforms[]
├── status (pending/generating/reviewing/pushing/completed/failed)
└── results

AssetPackage (平台素材包)
├── platform (amazon/ebay/shopify)
├── main_image, variant_images[], video_url
└── a_plus_images[]

CopywritingPackage (平台文案包)
├── platform, language
├── title, bullet_points[], description
└── search_terms[]

ComplianceReport (合规报告)
├── platform, overall (pass/fail/warning)
├── image_issues[], text_issues[]
└── forbidden_words[]
```

### 9.3 知识库域

```
knowledge_docs (知识文档)
├── doc_type (brand_guide/category_knowledge/case_study/compliance_rule)
├── title, content, source_url
└── created_at

knowledge_chunks (文档分块)
├── doc_id, chunk_index
├── content, embedding (PGVector 1024-dim)
└── metadata
```

---

## 10. API 设计摘要

### 10.1 端点列表

| 模块 | 端点 | 方法 | 描述 |
|------|------|------|------|
| **健康检查** | `/health` | GET | 系统健康状态 |
| **商品管理** | `/api/v1/products` | POST | 创建商品 |
| | `/api/v1/products/{id}` | GET | 查询商品 |
| | `/api/v1/products/{id}` | PUT | 更新商品 |
| | `/api/v1/products/{id}` | DELETE | 删除商品 |
| **任务管理** | `/api/v1/tasks` | POST | 创建生成任务 |
| | `/api/v1/tasks/{id}` | GET | 查询任务状态 |
| | `/api/v1/tasks/{id}` | DELETE | 删除任务 |
| | `/api/v1/tasks/{id}/cancel` | POST | 取消任务 |
| | `/api/v1/tasks/ws` | WS | 实时任务状态推送 |
| **知识库** | `/api/v1/knowledge` | POST | 创建知识文档 |
| | `/api/v1/knowledge` | GET | 文档列表 |
| | `/api/v1/knowledge/{id}` | DELETE | 删除文档 |
| | `/api/v1/knowledge/search` | POST | 知识检索 |
| | `/api/v1/knowledge/stats` | GET | 知识库统计 |
| **RAG 评估** | `/api/v1/rag/evaluate` | POST | RAG 效果评估 |
| | `/api/v1/rag/compare` | POST | RAG vs 非 RAG 对比 |
| **刊登工具** | `/api/v1/listing/products` | POST | 导入刊登商品 |
| | `/api/v1/listing/tasks` | POST | 创建刊登任务 |
| | `/api/v1/listing/tasks/{id}` | GET | 查询刊登任务 |
| | `/api/v1/listing/compliance/{id}` | GET | 查询合规报告 |
| **平台推送** | `/api/v1/listing/push/{id}` | POST | 推送到平台 |
| **适配器配置** | `/api/v1/listing/adapters` | CRUD | 平台适配器凭证管理 |

---

## 11. 验收标准

### 11.1 端到端验收

| 场景 | 验收条件 |
|------|----------|
| 图片生成全流程 | 输入商品 → 提交任务 → 生成 >=3 张图片 → 质量审核通过 → 可下载 |
| 视频生成全流程 | 输入商品 → 提交任务 → 生成 1 个视频 → 质量审核通过 → 可播放 |
| 图片+视频全流程 | 上述两者同时执行 → 结果在 AssetCollection 中完整呈现 |
| 刊登文案生成 | 导入商品 → 选择 3 个平台 → 生成文案包 → 合规检查通过 |
| 平台推送 | 文案+素材 → 推送到至少 1 个平台 → 返回平台侧确认 |
| RAG 增强 | 上传品牌指南 → 生成结果体现品牌风格 → rag_sources 有记录 |

### 11.2 单模块验收

| 模块 | 验收条件 |
|------|----------|
| 需求分析 | 输入商品 → 输出 RequirementReport，含卖点/人群/关键词 |
| 创意策划 | 输入需求报告 → 输出 CreativePlan + ColorPalette |
| 视觉设计 | 输入创意方案 → 输出 prompts + Storyboard |
| 质量审核 | 输入生成资源 → 输出 QualityReport，含评分和问题列表 |
| 合规检查 | 输入文案 → 检测禁词 → 输出 ComplianceReport |

### 11.3 数据一致性

- AgentState 累加字段（generated_images, quality_reports, agent_logs 等）在 Agent 间正确追加，不丢失
- 任务状态（pending/generating/completed/failed）在 Redis/PostgreSQL 中与实际执行一致
- WebSocket 推送的任务进度与实际 Agent 执行状态同步

---

## 12. 发布计划与里程碑

### Phase 1: 核心功能闭环（当前 → 2 周）

| 任务 | 优先级 | 描述 |
|------|--------|------|
| 接入 DashScope 图像生成 API | P0 | 替换 ImageGenerator 的 Mock 实现 |
| 接入可灵 AI 视频生成 API | P0 | 替换 VideoGenerator 的 Mock 实现 |
| 实现文件上传功能 | P0 | 商品图片上传到本地/OSS |
| 视觉生成与刊登工作流联通 | P0 | 生成的素材可直接流入刊登流程 |

### Phase 2: 安全与可靠性（2 → 4 周）

| 任务 | 优先级 | 描述 |
|------|--------|------|
| API 认证/授权 | P0 | JWT 或 API Key 认证 |
| CORS 收紧 | P0 | 限定允许的 Origin |
| 异步任务重试机制 | P1 | 图像/视频生成失败自动重试 |
| 视觉生成数据持久化到 PostgreSQL | P1 | 从 Redis 迁移到 PostgreSQL |
| OSS 存储集成 | P1 | 图片和视频存储到 OSS |

### Phase 3: 平台集成（4 → 8 周）

| 任务 | 优先级 | 描述 |
|------|--------|------|
| Amazon SP-API 真实对接 | P1 | 完成 LWA OAuth2 和商品推送 |
| eBay Trading API 真实对接 | P1 | 完成 OAuth2 和商品推送 |
| Shopify GraphQL 真实对接 | P1 | 完成商品创建和推送 |
| CI/CD 流水线 | P1 | 自动化测试和部署 |

### Phase 4: 优化与扩展（8+ 周）

| 任务 | 优先级 | 描述 |
|------|--------|------|
| 批量任务处理 | P2 | 支持批量商品视觉生成 |
| 生成质量迭代 | P2 | 基于质量审核反馈优化 prompt |
| 多租户支持 | P2 | 用户隔离和数据隔离 |
| 更多平台适配 | P3 | Lazada, Shopee 等 |

---

## 13. 风险与缓解

| 风险 | 严重度 | 可能性 | 缓解措施 |
|------|--------|--------|----------|
| DashScope/可灵 AI API 不稳定或限额 | 高 | 中 | 实现重试机制 + 备用模型降级 + 本地缓存常用 prompt 结果 |
| 生成图片质量不达商用标准 | 高 | 中 | 质量审核 Agent 拦截低质量输出；持续优化 prompt 模板；提供人工调整入口 |
| 平台 API 认证/政策变更 | 中 | 中 | 适配器模式支持快速更新；监控平台 API 变更通知 |
| 生成成本高（LLM + 图像 + 视频 API 调用） | 中 | 高 | 设置单任务 API 调用上限；缓存相似商品的创意方案；提供不同质量等级 |
| 知识库注入导致 prompt 过长 | 低 | 中 | 语义分块 + Top-K 限制；动态裁剪上下文长度 |
| 无认证导致的安全风险 | 高 | 高 | Phase 2 必须完成认证/授权实现后才可对外服务 |
| 两个工作流未联通导致端到端流程断裂 | 高 | 确定 | Phase 1 优先完成工作流联通 |

---

## 14. 开放问题

| 编号 | 问题 | 影响 | 建议决策人 |
|------|------|------|-----------|
| Q1 | 图像生成 API 的成本预估是多少？是否需要设置用户配额？ | 成本控制和商业化 | 产品负责人 |
| Q2 | 生成的视觉素材的版权归属如何界定？ | 法律合规 | 法务 |
| Q3 | 是否需要支持用户自定义 prompt 模板？ | 产品复杂度和灵活性权衡 | 产品负责人 |
| Q4 | 视频生成是否需要支持多种分辨率/比例（如竖屏 9:16）？ | 技术实现和成本 | 工程负责人 |
| Q5 | 两个工作流联通后，视觉生成失败是否应该阻止刊登流程？ | 用户体验和流程设计 | 产品负责人 |
| Q6 | 是否需要支持商品数据从 ERP/供应链系统自动同步？ | 集成复杂度和用户场景 | 产品负责人 |
| Q7 | 知识库文档是否需要版本管理和审批流程？ | 品牌合规管控 | 品牌管理者 |
| Q8 | 质量审核 Agent 的评分标准是否需要可配置？ | 灵活性和维护成本 | 工程负责人 |

---

## 附录 A: 技术决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| 多 Agent 框架 | LangGraph | 原生状态图、条件路由、checkpoint 支持 |
| 主力 LLM | 通义千问 qwen3.5-flash | 阿里云生态、成本、中文能力 |
| 图像生成 | 通义万象 wanx-v1 | 同一云平台、API 统一 |
| 视频生成 | 可灵 AI kling-v1 | 视频质量、中文场景优化 |
| 向量存储 | PGVector | 与 PostgreSQL 统一基础设施，运维成本低 |
| Embedding | BGE-large-zh | 中文语义理解好、本地部署无额外成本 |
| 前端框架 | Vue 3 + Element Plus | 团队技术栈、组件丰富 |
| 包管理 | uv | 性能优于 pip/poetry |

## 附录 B: 假设清单

| 假设 | 影响 | 验证方式 |
|------|------|----------|
| 通义万象生成的图片质量可满足电商主图要求 | 核心功能可用性 | 接入 API 后进行质量评估 |
| 可灵 AI 生成的视频时长和质量满足商品短视频要求 | 核心功能可用性 | 接入 API 后进行质量评估 |
| 目标用户具备基本的商品信息（名称、描述、卖点） | 系统输入可行性 | 用户调研 |
| BGE-large-zh 的检索精度足够支撑品牌规范匹配 | RAG 增强效果 | RAG 评估模块量化测试 |
| 多 LLM 降级策略可保证文案生成的可用性 | 系统可靠性 | 模拟 LLM 故障测试 |
