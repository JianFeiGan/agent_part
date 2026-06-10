# MVP 聚焦迭代计划：商品视觉生成器

| 字段 | 内容 |
|------|------|
| **版本** | v1.0 |
| **日期** | 2026-06-10 |
| **状态** | 草稿 |

---

## 0. 核心原则

> **一个场景做透 > 全链路做到 60 分。**

当前项目同时做了图片生成、视频生成、文案生成、合规检查、多平台推送、RAG 知识库、前端管理后台。MVP 阶段必须大幅收敛：

| 砍掉 | 保留 | 原因 |
|------|------|------|
| 视频生成 | **图片生成** | 视频 API 成本高、质量难控，非最小闭环必需 |
| 多平台刊登推送 | **单品图片生成 + 下载** | 平台对接周期长，MVP 阶段用手动下载替代 |
| AI 文案生成 | 后续迭代 | 文案生成独立价值大，但不在视觉 MVP 闭环内 |
| RAG 知识库管理 UI | **RAG 检索能力保留** | 知识库通过 API/文件管理即可，UI 可后补 |
| 合规检查 | 后续迭代 | 合规是增值功能，非核心生成链路 |

---

## 1. MVP 目标用户（聚焦）

### 目标画像

**中小跨境电商卖家**，满足以下特征：
- 在 Amazon 或独立站运营，月上新 10-50 个 SKU
- 目前用 Canva/外包设计师制作商品主图，单张成本 5-30 元，周期 1-3 天
- 核心痛点：上新速度慢、设计成本高、主图风格不统一
- 愿意尝试 AI 工具，但对图片质量有底线要求（至少达到"白底主图可上架"水平）

### 不做谁

- 大品牌（有专属设计团队，不需要 AI 生图）
- 超大量卖家（1000+ SKU/月，需要 ERP 级集成）
- 非电商用户（社交营销、个人用途）

---

## 2. MVP 最小闭环定义

```
输入商品信息
    │
    ▼
自动生成 3 张 Amazon 主图（白底产品图）
    │
    ▼
用户查看 → 选择满意的 → 下载
```

**就这一个场景。** 不涉及场景图、卖点图、视频、文案、刊登。

### 为什么是 Amazon 白底主图？

1. Amazon 主图有明确规范（纯白背景 RGB 255,255,255，商品占比 85%+，无文字/水印）
2. 规范明确 = 质量可衡量
3. 需求量最大 = 每个 SKU 必须有
4. 技术难度相对可控 = 比场景图更容易达到可商用水平

---

## 3. 迭代计划

### Sprint 0：真实 API 验证（3 天）

**目标**: 回答最核心的问题——**通义万象生成的图片质量能否达到 Amazon 主图标准？**

**做什么**:

1. 编写一个独立脚本（不改动现有代码），直接调用 DashScope 图像生成 API
2. 准备 5 个典型商品（数码、服装、美妆、家居、食品各一个）
3. 每个商品用 3 组 prompt 生成主图，共 15 张
4. 人工评估：与 Amazon 在售同类商品主图对比打分

**评估维度**:

| 维度 | 及格线 | 说明 |
|------|--------|------|
| 背景纯净度 | 白色背景无明显杂色 | Amazon 硬性要求 |
| 商品还原度 | 能认出是什么商品 | 最低可用标准 |
| 细节质量 | 无严重变形/穿帮 | 手指数量、文字乱码等 |
| 光影质感 | 接近真实产品摄影 | 与 Canva AI 对比 |
| 尺寸合规 | 1000x1000 或 1600x1600 | Amazon 主图规格 |

**Exit Gate（决策点）**:

| 结果 | 决策 |
|------|------|
| >= 60% 图片达到及格线 | 继续 MVP 迭代 |
| 30%-60% 及格 | 调整 prompt 策略后重新验证，或评估备用模型 |
| < 30% 及格 | 重新评估技术路线（换模型/混合方案/项目止损） |

**交付物**:
- `scripts/validate_image_quality.py` — 验证脚本
- `docs/image_quality_report.md` — 质量评估报告（含对比图）
- 成本记录：每张图的 API 调用费用

**关键改动（代码层面）**:

```python
# scripts/validate_image_quality.py（新文件）
# 直接调用 DashScope API，不走现有 Agent 框架
import dashscope
from dashscope import ImageSynthesis

# 关键：验证真实 API 的 prompt 格式、参数、返回格式、耗时、费用
result = ImageSynthesis.call(
    model="wanx-v1",
    input={"prompt": "..."},
    parameters={"size": "1024*1024", "n": 1}
)
```

---

### Sprint 1：接入真实图片生成 API（1 周）

**前提**: Sprint 0 Exit Gate 通过。

**目标**: 将 `_call_image_api()` 从 mock 替换为真实 DashScope 调用，跑通"输入商品 → 出图"最小链路。

**做什么**:

1. **实现 DashScope 图像生成客户端**

```python
# src/services/dashscope_image_client.py（新文件）
class DashScopeImageClient:
    """DashScope 图像生成客户端。"""
    
    async def generate(
        self,
        prompt: str,
        negative_prompt: str | None,
        width: int,
        height: int,
        model: str = "wanx-v1",
    ) -> DashScopeImageResult:
        """调用真实 API 生成图片。"""
        ...
    
    async def poll_result(self, task_id: str) -> DashScopeImageResult:
        """轮询异步任务结果。"""
        ...
```

2. **替换 ImageGeneratorAgent 的 mock 调用**

```python
# src/agents/image_generator.py 修改
# 删除 line 273-293 的 mock 逻辑
# 替换为：
async def _call_image_api(self, prompt, negative_prompt, width, height, image_type):
    client = DashScopeImageClient(api_key=self.settings.dashscope_api_key)
    result = await client.generate(prompt, negative_prompt, width, height)
    
    image = GeneratedImage(
        image_id=result.task_id,
        image_type=image_type,
        prompt=prompt,
        negative_prompt=negative_prompt,
        url=result.image_url,  # 真实 URL
        local_path=None,
        format=ImageFormat.PNG,
        width=width,
        height=height,
        status=AssetStatus.COMPLETED if result.success else AssetStatus.FAILED,
        model=self.settings.image_model,
    )
    return [image]
```

3. **实现图片本地下载**
   - DashScope 返回的是临时 URL（有效期有限）
   - 必须下载到本地 `./output/{task_id}/` 目录
   - 返回本地可访问路径

4. **添加重试和错误处理**
   - DashScope 异步任务可能超时
   - 实现 3 次重试 + 指数退避
   - 记录每次调用的耗时和费用

5. **编写集成测试**
   - `tests/test_agents/test_image_generator_integration.py`
   - 使用真实 API（标记 `@pytest.mark.integration`，默认 skip）
   - 验证：返回的 URL 可访问、图片尺寸正确、格式正确

**Exit Gate**:
- 通过 API 创建商品 → 提交图片生成任务 → 拿到真实图片 URL → 本地可查看图片
- 至少成功生成 10 张图片，无 API 级错误

**成本记录**:
- 建立 `docs/cost_model.md`，记录每张图的 API 费用
- 计算单商品（3 张主图）的总生成成本

---

### Sprint 2：Prompt 工程优化（1 周）

**前提**: Sprint 1 完成，能出图但质量不稳定。

**目标**: 通过 prompt 优化，将 Amazon 白底主图的及格率从 Sprint 0 基线提升到 >= 80%。

**做什么**:

1. **建立 Prompt 模板体系**

```python
# src/prompts/amazon_main_image.py（新文件）
class AmazonMainImagePrompts:
    """Amazon 白底主图 Prompt 模板。"""
    
    BASE_TEMPLATE = """
    Professional product photography of {product_name},
    pure white background (RGB 255,255,255),
    product centered, occupying 85% of frame,
    studio lighting, high resolution,
    commercial product photo style,
    no text, no watermark, no logo
    """
    
    CATEGORY_ENHANCEMENTS = {
        "digital": "clean tech product, subtle reflection, matte finish",
        "clothing": "flat lay or mannequin display, fabric texture visible",
        "beauty": "luxury cosmetics, soft shadows, premium packaging",
        "food": "appetizing presentation, natural lighting feel",
        "home": "lifestyle product isolated on white, clean composition",
    }
    
    NEGATIVE_PROMPT = """
    text, watermark, logo, blurry, deformed, low quality,
    colored background, shadows on background, multiple products,
    human hands, human face, cartoon, illustration, painting
    """
```

2. **优化 VisualDesigner Agent 的 prompt 生成逻辑**
   - 当前 `visual_designer.py` 用 LLM 自由生成 prompt
   - 改为：LLM 生成商品描述 → 套入模板 → 附加类目增强词
   - 确保 negative prompt 覆盖 Amazon 禁项

3. **建立 Prompt 效果评估流程**

```
准备 10 个测试商品（覆盖 5 个类目）
    │
    ▼
每个商品生成 3 张图（共 30 张）
    │
    ▼
人工评分（5 分制）
    │
    ▼
调整 prompt → 重新生成 → 对比效果
```

4. **Prompt 版本管理**
   - 每个 prompt 版本有唯一 ID
   - 记录每个版本的生成成功率
   - 后续迭代可回滚到效果最好的版本

**Exit Gate**:
- 30 张测试图中 >= 80%（24 张）达到 Amazon 主图及格线
- 建立了可重复使用的 prompt 模板库
- 每个类目的 prompt 增强策略已验证

---

### Sprint 3：最小可用 API + 前端（1.5 周）

**目标**: 用户可以通过 Web 界面完成"录入商品 → 生成主图 → 下载"全流程。

**做什么**:

1. **精简 API 端点**（只保留 MVP 必需的）

| 保留 | 暂时下线 |
|------|----------|
| `POST /api/v1/products` | 知识库相关 API |
| `GET /api/v1/products/{id}` | 刊登相关 API |
| `POST /api/v1/tasks`（仅 image_only） | RAG 评估 API |
| `GET /api/v1/tasks/{id}` | 适配器配置 API |
| `GET /api/v1/tasks/{id}/images`（新增） | |
| `GET /api/v1/tasks/{id}/download`（新增） | |

2. **实现图片下载 API**

```python
# src/api/router/tasks.py 新增
@router.get("/{task_id}/download")
async def download_images(task_id: str):
    """下载任务生成的所有图片，返回 ZIP 包。"""
    ...
```

3. **实现基础认证**
   - 最简单的方案：API Key 认证（Header 传入）
   - 不做用户系统，只做一个全局 API Key
   - 防止接口被无限制调用

```python
# src/api/middleware/auth.py（新文件）
class APIKeyAuth:
    """简单 API Key 认证中间件。"""
    
    async def __call__(self, request):
        api_key = request.headers.get("X-API-Key")
        if api_key != settings.api_key:
            raise HTTPException(401, "Invalid API Key")
```

4. **前端 MVP 页面**（只保留 3 个页面）

| 页面 | 功能 |
|------|------|
| 商品录入页 | 名称 + 类目 + 描述 + 卖点（简化表单） |
| 任务列表页 | 查看任务状态 + 进度 |
| 任务详情页 | 查看生成图片 + 下载按钮 |

5. **裁剪工作流节点**

MVP 不需要全部 7 个 Agent。精简为 4 个：

```
Orchestrator（简化：仅做输入校验，跳过 LLM 任务分解）
    │
    ▼
RequirementAnalyzer（保留：提取卖点和关键词）
    │
    ▼
VisualDesigner（简化：使用模板 prompt，LLM 只生成商品描述部分）
    │
    ▼
ImageGenerator（核心：真实 DashScope 调用）
```

**砍掉的节点**:
- CreativePlanner — MVP 阶段用固定模板替代创意策划
- VideoGenerator — 不在 MVP 范围
- QualityReviewer — 暂时用人工审核替代（Sprint 4 再加回）

**Exit Gate**:
- 一个不了解系统的用户，能在 5 分钟内完成：录入商品 → 提交任务 → 等待生成 → 查看并下载图片
- 全流程无报错
- 图片可通过下载按钮保存到本地

---

### Sprint 4：质量审核 + 重新生成（1 周）

**目标**: 自动过滤不合格图片，支持用户对不满意的图重新生成。

**做什么**:

1. **实现轻量级质量审核**

不用 LLM 做图片质量审核（LLM 判断图像质量不可靠），改为：

```python
# src/services/image_quality_checker.py（新文件）
class ImageQualityChecker:
    """基于规则 + 传统 CV 的图片质量检查。"""
    
    async def check(self, image_path: str, image_type: str) -> QualityResult:
        checks = []
        
        # 1. 基础检查：文件大小、尺寸
        checks.append(self._check_file_valid(image_path))
        
        # 2. 白底检查（Amazon 主图专用）
        if image_type == "main":
            checks.append(self._check_white_background(image_path))
        
        # 3. 清晰度检查（拉普拉斯方差）
        checks.append(self._check_sharpness(image_path))
        
        return QualityResult(checks=checks)
    
    def _check_white_background(self, image_path: str) -> CheckResult:
        """检查背景是否为纯白。"""
        # 采样图片四角像素，判断是否接近白色
        ...
    
    def _check_sharpness(self, image_path: str) -> CheckResult:
        """检查图片清晰度（拉普拉斯方差）。"""
        # 使用 OpenCV 或 Pillow 计算
        ...
```

2. **实现重新生成流程**

```
用户查看生成结果
    │
    ├── 满意 → 下载
    └── 不满意 → 点击"重新生成"
                    │
                    ▼
              可选：调整参数（换风格/换 prompt）
                    │
                    ▼
              重新调用 ImageGenerator（只重新生成不满意的图）
```

```python
# src/api/router/tasks.py 新增
@router.post("/{task_id}/regenerate/{image_id}")
async def regenerate_image(task_id: str, image_id: str, params: RegenerateParams):
    """重新生成单张图片。"""
    ...
```

3. **加回 QualityReviewer Agent**
   - 使用 `ImageQualityChecker`（规则+CV）而非 LLM
   - 自动标记不合格图片为 `status=rejected`
   - 合格图片标记为 `status=approved`

**Exit Gate**:
- 白底不合格的图被自动拦截，不展示给用户作为"可用结果"
- 用户可以针对单张图触发重新生成
- 重新生成的图替换原图，保持任务完整性

---

### Sprint 5：成本优化 + 可用性加固（1 周）

**目标**: 确保系统在成本和稳定性上可支撑小规模使用。

**做什么**:

1. **成本监控**

```python
# src/services/cost_tracker.py（新文件）
class CostTracker:
    """API 调用成本追踪。"""
    
    # DashScope 定价（需确认最新价格）
    PRICING = {
        "wanx-v1": {"per_image": 0.16},  # 元/张（示例，需确认实际价格）
        "qwen3.5-flash": {"per_1k_tokens": 0.002},
    }
    
    async def record(self, service: str, usage: dict, cost: float):
        """记录一次 API 调用成本。"""
        ...
    
    async def get_task_cost(self, task_id: str) -> float:
        """获取单个任务的总成本。"""
        ...
    
    async def get_daily_cost(self) -> float:
        """获取当日总成本。"""
        ...
```

2. **设置成本上限**
   - 单任务成本上限（如 5 元）
   - 日成本上限（如 100 元）
   - 超限自动拒绝新任务

3. **缓存策略**
   - 相同商品 + 相同参数 → 返回缓存结果
   - Prompt 模板缓存（避免每次重新生成）
   - Redis 缓存，TTL 24 小时

4. **错误处理加固**
   - DashScope API 超时 → 重试 3 次 + 指数退避
   - 网络错误 → 记录并返回友好提示
   - 任务状态一致性 → 任何异常都标记为 failed，不留中间态

5. **基础监控面板**（前端新增一个简单 Dashboard）
   - 今日生成图片数
   - 今日任务数（成功/失败）
   - 今日成本
   - 平均生成耗时

**Exit Gate**:
- 单商品（3 张主图）生成成本已量化，记录在 `docs/cost_model.md`
- 有成本上限保护，不会意外超支
- 连续运行 24 小时无未处理异常

---

## 4. 迭代总览

```
Week 1        Week 2         Week 3          Week 4        Week 5
┌──────────┐ ┌───────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐
│ Sprint 0 │ │ Sprint 1  │ │  Sprint 2  │ │  Sprint 3  │ │ Sprint 4 │
│ API 验证  │→│ 接入真实   │→│  Prompt    │→│  最小可用   │→│ 质量审核  │
│ 3 天     │ │ API 1 周  │ │ 优化 1 周  │ │ 前端 1.5 周│ │ 重试 1 周│
│          │ │           │ │            │ │            │ │          │
│ 决策：   │ │ 出真图    │ │ 出好图     │ │ 用户可用   │ │ 自动筛选 │
│ 图片质量 │ │ 跑通链路   │ │ >= 80%    │ │ 全流程     │ │ 可重生成 │
│ 能否商用 │ │           │ │ 及格率     │ │ 闭环       │ │          │
└──────────┘ └───────────┘ └────────────┘ └────────────┘ └──────────┘
                                                             │
                                                        Week 6
                                                        ┌──────────┐
                                                        │ Sprint 5 │
                                                        │ 成本优化  │
                                                        │ 加固 1 周 │
                                                        │          │
                                                        │ 可支撑   │
                                                        │ 小规模   │
                                                        │ 使用     │
                                                        └──────────┘
```

**总周期：5-6 周**

---

## 5. MVP 之后的路线图（仅方向，不展开）

MVP 验证通过后，按以下优先级扩展：

| 阶段 | 方向 | 前提 |
|------|------|------|
| **V1.1** | 场景图 + 卖点图 | 主图质量已稳定 |
| **V1.2** | 视频生成 | 可灵 API 已验证（独立做 Sprint 0 验证） |
| **V1.3** | 刊登文案 + 合规检查 | 图片流程已闭环 |
| **V1.4** | Amazon 平台推送 | 文案+图片都可用 |
| **V2.0** | RAG 品牌规范增强 + 多平台 | 单平台已验证 |

---

## 6. 风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| Sprint 0 图片质量不达标 | 中 | **致命** | 备选方案：FLUX.1 / Stable Diffusion 3 / Midjourney API；或混合方案（AI 生成 + 模板合成） |
| DashScope API 不稳定 | 低 | 高 | 重试 + 备用模型 + 本地缓存 |
| 生成成本过高（>10 元/商品） | 中 | 高 | 换更便宜的模型；减少 LLM 调用次数；缓存策略 |
| Prompt 优化效果有限 | 中 | 中 | 引入 human-in-the-loop：人工微调 prompt 后系统学习 |
| Amazon 主图规范变更 | 低 | 低 | 模板化 prompt，规范变更只需更新模板 |

---

## 7. 关键指标看板

MVP 阶段持续跟踪以下指标：

| 指标 | 目标 | 度量方式 |
|------|------|----------|
| 图片及格率 | >= 80% | 人工评审 + 自动检测 |
| 单商品生成耗时 | <= 60 秒 | 任务创建到图片可下载 |
| 单商品生成成本 | <= 3 元 | CostTracker 统计 |
| 系统可用性 | >= 95% | 任务成功率 |
| 用户完成全流程率 | >= 70% | 提交任务到下载 |

---

## 8. Sprint 0 立即行动清单

**今天就可以开始的事情**：

1. **确认 DashScope API Key 可用** — 检查 `.env` 中 `DASHSCOPE_API_KEY` 是否已配置
2. **查阅 DashScope 图像生成最新文档** — 确认 wanx-v1 的调用方式、参数、定价
3. **编写验证脚本** — 5 个商品 × 3 组 prompt = 15 张图
4. **准备评估标准** — 打印 Amazon 主图规范对照表
5. **记录结果** — 填写质量评估报告

**验证脚本示例框架**：

```python
"""scripts/validate_image_quality.py"""

PRODUCTS = [
    {"name": "无线蓝牙耳机", "category": "digital", "desc": "入耳式降噪耳机，黑色"},
    {"name": "运动T恤", "category": "clothing", "desc": "速干透气面料，圆领短袖"},
    {"name": "保湿面霜", "category": "beauty", "desc": "50ml 玻璃瓶装，白色乳霜"},
    {"name": "不锈钢保温杯", "category": "home", "desc": "500ml，银色金属质感"},
    {"name": "坚果礼盒", "category": "food", "desc": "混合坚果，红色礼盒包装"},
]

PROMPT_VERSIONS = [
    "v1_basic",     # 简单描述
    "v1_enhanced",  # 加专业摄影术语
    "v1_amazon",    # 加 Amazon 规范约束
]

# 对每个商品 × 每个 prompt 版本生成图片
# 下载所有图片到 ./validation_output/
# 输出评估表格供人工打分
```

---

## 附录：MVP 阶段文件改动范围

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `src/services/dashscope_image_client.py` | **新增** | 真实 API 客户端 |
| `src/services/image_quality_checker.py` | **新增** | 图片质量检查 |
| `src/services/cost_tracker.py` | **新增** | 成本追踪 |
| `src/prompts/amazon_main_image.py` | **新增** | Prompt 模板 |
| `src/agents/image_generator.py` | **修改** | 替换 `_call_image_api()` mock |
| `src/agents/orchestrator.py` | **修改** | 简化为输入校验 |
| `src/agents/visual_designer.py` | **修改** | 接入模板 prompt |
| `src/graph/workflow.py` | **修改** | MVP 模式裁剪节点 |
| `src/api/router/tasks.py` | **修改** | 新增下载和重新生成端点 |
| `src/api/middleware/auth.py` | **新增** | API Key 认证 |
| `frontend/src/views/` | **修改** | 精简为 3 个页面 |
| `scripts/validate_image_quality.py` | **新增** | Sprint 0 验证脚本 |
| `docs/image_quality_report.md` | **新增** | 质量评估报告 |
| `docs/cost_model.md` | **新增** | 成本模型 |
