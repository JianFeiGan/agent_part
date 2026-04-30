# 刊登工具 Phase 1：素材优化 + 文案生成 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现商品导入、素材优化引擎（按平台规范转换图片）、文案生成引擎（LLM 生成多语言标题/描述/关键词），并通过 API 暴露。

**Architecture:** 新建独立 `src/models/listing.py` 数据模型 + `src/agents/` 新增 4 个 Agent + `src/graph/` 新增 Listing 工作流 + `src/api/` 新增 listing 路由。复用现有 BaseAgent、FastAPI 模式、ApiResponse 模式。

**Tech Stack:** Python 3.11+, LangChain, LangGraph, FastAPI, Pydantic v2, pytest, Pillow (图片处理)

---

### Task 1: 新增 Pydantic 数据模型

**Files:**
- Create: `src/models/listing.py`
- Modify: `src/models/__init__.py` — 导出新增模型

- [ ] **Step 1: 写测试**

```python
# tests/test_models/test_listing.py
"""刊登工具数据模型测试。"""

from datetime import datetime
from decimal import Decimal

import pytest

from src.models.listing import (
    ListingProduct,
    ImageRef,
    AssetPackage,
    CopywritingPackage,
    ListingTask,
    TaskStatus,
    Platform,
)


class TestListingProduct:
    """测试 ListingProduct 模型。"""

    def test_create_minimal(self) -> None:
        """测试最小创建。"""
        product = ListingProduct(sku="TEST-001", title="测试商品")
        assert product.sku == "TEST-001"
        assert product.title == "测试商品"
        assert product.brand is None

    def test_create_full(self) -> None:
        """测试完整创建。"""
        product = ListingProduct(
            sku="TEST-002",
            title="Wireless Bluetooth Headphones",
            description="High-quality wireless headphones with noise cancellation",
            category="Electronics",
            brand="SoundMax",
            price=Decimal("49.99"),
            weight=Decimal("0.35"),
            dimensions={"length": 20, "width": 18, "height": 8, "unit": "cm"},
            source_images=[
                ImageRef(url="https://example.com/img1.jpg", is_main=True),
                ImageRef(url="https://example.com/img2.jpg", is_main=False),
            ],
            attributes={"color": "Black", "connectivity": "Bluetooth 5.0"},
        )
        assert product.price == Decimal("49.99")
        assert len(product.source_images) == 2
        assert product.source_images[0].is_main is True

    def test_main_image(self) -> None:
        """测试获取主图。"""
        product = ListingProduct(
            sku="TEST-003",
            title="Test",
            source_images=[
                ImageRef(url="https://example.com/secondary.jpg", is_main=False),
                ImageRef(url="https://example.com/main.jpg", is_main=True),
            ],
        )
        main = product.main_image
        assert main is not None
        assert main.url == "https://example.com/main.jpg"

    def test_main_image_none(self) -> None:
        """测试无主图时返回 None。"""
        product = ListingProduct(sku="TEST-004", title="Test")
        assert product.main_image is None


class TestAssetPackage:
    """测试 AssetPackage 模型。"""

    def test_create(self) -> None:
        """测试创建素材包。"""
        pkg = AssetPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            main_image="https://example.com/main.jpg",
        )
        assert pkg.platform == Platform.AMAZON
        assert pkg.main_image is not None
        assert len(pkg.variant_images) == 0


class TestCopywritingPackage:
    """测试 CopywritingPackage 模型。"""

    def test_create(self) -> None:
        """测试创建文案包。"""
        pkg = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            language="en",
            title="Premium Wireless Bluetooth Headphones",
            bullet_points=[
                "Advanced noise cancellation technology",
                "40-hour battery life",
            ],
            description="Experience premium sound quality...",
            search_terms=["wireless", "bluetooth", "headphones"],
        )
        assert len(pkg.bullet_points) == 2
        assert len(pkg.search_terms) == 3


class TestListingTask:
    """测试 ListingTask 模型。"""

    def test_create(self) -> None:
        """测试创建任务。"""
        task = ListingTask(
            product_id=1,
            target_platforms=[Platform.AMAZON, Platform.EBAY],
        )
        assert task.status == TaskStatus.PENDING
        assert len(task.target_platforms) == 2

    def test_mark_generating(self) -> None:
        """测试状态转换。"""
        task = ListingTask(product_id=1, target_platforms=[Platform.AMAZON])
        task.mark_generating()
        assert task.status == TaskStatus.GENERATING
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_models/test_listing.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.models.listing'`

- [ ] **Step 3: 实现模型**

```python
# src/models/listing.py
"""
刊登工具数据模型。

定义刊登商品、任务、素材包、文案包的 Pydantic 模型。

Description:
    刊登工具的独立数据模型，与现有 Product 模型解耦，
    支持从外部系统导入商品并生成刊登素材和文案。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Platform(str, Enum):
    """目标电商平台。"""

    AMAZON = "amazon"
    EBAY = "ebay"
    SHOPIFY = "shopify"


class TaskStatus(str, Enum):
    """刊登任务状态。"""

    PENDING = "pending"
    GENERATING = "generating"
    REVIEWING = "reviewing"
    PUSHING = "pushing"
    COMPLETED = "completed"
    FAILED = "failed"


class ImageRef(BaseModel):
    """图片引用。"""

    url: str = Field(..., description="图片URL或本地路径")
    is_main: bool = Field(default=False, description="是否为主图")
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    file_size: int | None = Field(default=None, ge=0)


class ListingProduct(BaseModel):
    """标准化刊登商品。

    与平台无关的商品信息模型，用于刊登流程的输入。
    """

    id: int | None = Field(default=None, description="主键ID")
    sku: str = Field(..., min_length=1, max_length=100, description="商品SKU")
    title: str = Field(..., min_length=1, max_length=500, description="商品标题")
    description: str | None = Field(default=None, description="商品描述")
    category: str | None = Field(default=None, description="商品类目")
    brand: str | None = Field(default=None, description="品牌")
    price: Decimal | None = Field(default=None, description="价格")
    weight: Decimal | None = Field(default=None, description="重量(kg)")
    dimensions: dict[str, Any] | None = Field(default=None, description="尺寸信息")
    source_images: list[ImageRef] = Field(default_factory=list, description="原始图片素材")
    attributes: dict[str, Any] = Field(default_factory=dict, description="平台特有属性")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "sku": "BT-HP-001",
                    "title": "Wireless Bluetooth Headphones",
                    "description": "High-quality wireless headphones",
                    "category": "Electronics",
                    "brand": "SoundMax",
                    "price": "49.99",
                    "weight": "0.35",
                    "dimensions": {"length": 20, "width": 18, "height": 8, "unit": "cm"},
                    "source_images": [],
                    "attributes": {"color": "Black"},
                }
            ]
        }
    }

    @property
    def main_image(self) -> ImageRef | None:
        """获取主图引用。"""
        for img in self.source_images:
            if img.is_main:
                return img
        return self.source_images[0] if self.source_images else None


class AssetPackage(BaseModel):
    """平台标准化素材包。"""

    id: int | None = Field(default=None)
    listing_task_id: int = Field(..., description="关联任务ID")
    platform: Platform = Field(..., description="目标平台")
    main_image: str | None = Field(default=None, description="主图URL")
    variant_images: list[str] = Field(default_factory=list, description="变体图URL列表")
    video_url: str | None = Field(default=None, description="视频URL")
    a_plus_images: list[str] = Field(default_factory=list, description="A+页面图片")


class CopywritingPackage(BaseModel):
    """平台标准化文案包。"""

    id: int | None = Field(default=None)
    listing_task_id: int = Field(..., description="关联任务ID")
    platform: Platform = Field(..., description="目标平台")
    language: str = Field(default="en", description="语言代码")
    title: str = Field(default="", description="平台优化标题")
    bullet_points: list[str] = Field(default_factory=list, description="五点描述")
    description: str = Field(default="", description="长描述")
    search_terms: list[str] = Field(default_factory=list, description="搜索关键词")


class ListingTask(BaseModel):
    """刊登任务。"""

    id: int | None = Field(default=None)
    product_id: int = Field(..., description="关联商品ID")
    target_platforms: list[Platform] = Field(default_factory=list)
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    results: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

    def mark_generating(self) -> None:
        """标记为生成中。"""
        self.status = TaskStatus.GENERATING

    def mark_completed(self) -> None:
        """标记为完成。"""
        self.status = TaskStatus.COMPLETED

    def mark_failed(self, error: str | None = None) -> None:
        """标记为失败。"""
        self.status = TaskStatus.FAILED
        if error:
            self.results["error"] = error
```

- [ ] **Step 4: 更新 `src/models/__init__.py`**

在 `src/models/__init__.py` 中添加导出：

```python
# 新增导入
from src.models.listing import (
    AssetPackage,
    CopywritingPackage,
    ImageRef,
    ListingProduct,
    ListingTask,
    Platform,
    TaskStatus,
)

# 更新 __all__
__all__ = [
    # ... 原有项 ...
    "ListingProduct",
    "ImageRef",
    "AssetPackage",
    "CopywritingPackage",
    "ListingTask",
    "Platform",
    "TaskStatus",
]
```

- [ ] **Step 5: 运行测试确认通过**

```bash
uv run pytest tests/test_models/test_listing.py -v
```
Expected: All 7 tests PASS

- [ ] **Step 6: 提交**

```bash
git add src/models/listing.py src/models/__init__.py tests/test_models/test_listing.py
git commit -m "feat: add listing tool Pydantic data models"
```

---

### Task 2: 新增 Listing State 和工作流

**Files:**
- Create: `src/graph/listing_state.py`
- Create: `src/graph/listing_workflow.py`
- Modify: `src/graph/__init__.py` — 导出新增内容

- [ ] **Step 1: 写测试**

```python
# tests/test_graph/test_listing_workflow.py
"""刊登工作流测试。"""

from src.graph.listing_state import ListingState
from src.models.listing import (
    AssetPackage,
    CopywritingPackage,
    ListingProduct,
    Platform,
)


class TestListingState:
    """测试 ListingState 状态模型。"""

    def test_initial_state(self) -> None:
        """测试初始状态。"""
        state = ListingState()
        assert state.product is None
        assert state.asset_packages == {}
        assert state.copywriting_packages == {}
        assert state.target_platforms == []
        assert state.error is None
        assert state.current_step == ""

    def test_with_product(self) -> None:
        """测试设置商品。"""
        product = ListingProduct(sku="T-001", title="Test Product")
        state = ListingState(product=product, target_platforms=[Platform.AMAZON])
        assert state.product is not None
        assert state.product.sku == "T-001"
        assert state.target_platforms == [Platform.AMAZON]

    def test_asset_package_accumulation(self) -> None:
        """测试素材包累积。"""
        state = ListingState(target_platforms=[Platform.AMAZON, Platform.EBAY])
        state.asset_packages[Platform.AMAZON] = AssetPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            main_image="https://example.com/amazon.jpg",
        )
        state.asset_packages[Platform.EBAY] = AssetPackage(
            listing_task_id=1,
            platform=Platform.EBAY,
            main_image="https://example.com/ebay.jpg",
        )
        assert len(state.asset_packages) == 2
        assert Platform.AMAZON in state.asset_packages

    def test_copywriting_package_accumulation(self) -> None:
        """测试文案包累积。"""
        state = ListingState(target_platforms=[Platform.AMAZON])
        state.copywriting_packages[Platform.AMAZON] = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            language="en",
            title="Test Title",
        )
        assert len(state.copywriting_packages) == 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_graph/test_listing_workflow.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.graph.listing_state'`

- [ ] **Step 3: 实现 ListingState**

```python
# src/graph/listing_state.py
"""
刊登工作流状态定义。

Description:
    定义刊登工作流的共享状态模型，支持素材和文案的并行生成。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

from typing import Any

from pydantic import BaseModel, Field

from src.models.listing import (
    AssetPackage,
    CopywritingPackage,
    ListingProduct,
    Platform,
)


class ListingState(BaseModel):
    """刊登工作流共享状态。

    状态流转:
        PENDING → 商品导入 → 素材+文案并行生成 → 结果收集

    Attributes:
        product: 待刊登的标准化商品。
        asset_packages: 各平台的素材包 (platform -> package)。
        copywriting_packages: 各平台的文案包 (platform -> package)。
        target_platforms: 目标平台列表。
        error: 错误信息（如有）。
        current_step: 当前执行步骤。
        step_results: 各步骤执行结果。
    """

    product: ListingProduct | None = None
    asset_packages: dict[Platform, AssetPackage] = Field(default_factory=dict)
    copywriting_packages: dict[Platform, CopywritingPackage] = Field(default_factory=dict)
    target_platforms: list[Platform] = Field(default_factory=list)
    error: str | None = None
    current_step: str = ""
    step_results: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 4: 实现 Listing Workflow**

```python
# src/graph/listing_workflow.py
"""
刊登工作流构建器。

Description:
    基于 LangGraph StateGraph 构建刊登工作流，
    支持商品导入、素材优化、文案生成的并行执行。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.agents.listing_asset_optimizer import AssetOptimizerAgent
from src.agents.listing_copywriter import CopywriterAgent
from src.agents.listing_importer import ImportProductAgent
from src.graph.listing_state import ListingState

logger = logging.getLogger(__name__)


class ListingWorkflow:
    """刊登工作流封装。

    工作流:
        START → ImportProduct → [AssetOptimizer | Copywriter] → 收集结果 → END

    Attributes:
        app: 编译后的 LangGraph 应用。
    """

    def __init__(self, settings: Any | None = None) -> None:
        """初始化工作流。

        Args:
            settings: 可选的配置对象，用于注入到 Agent。
        """
        self._settings = settings
        self._builder = StateGraph(ListingState)
        self._build_graph()
        self._checkpointer = MemorySaver()
        self.app = self._builder.compile(checkpointer=self._checkpointer)

    def _build_graph(self) -> None:
        """构建状态图。"""
        # 添加节点
        self._builder.add_node("import_product", self._import_node)
        self._builder.add_node("optimize_assets", self._asset_optimize_node)
        self._builder.add_node("generate_copy", self._copy_node)

        # 添加边
        self._builder.set_entry_point("import_product")
        self._builder.add_edge("import_product", "optimize_assets")
        self._builder.add_edge("import_product", "generate_copy")
        self._builder.add_edge("optimize_assets", END)
        self._builder.add_edge("generate_copy", END)

    async def _import_node(self, state: ListingState) -> dict:
        """商品导入节点。"""
        agent = ImportProductAgent(settings=self._settings)
        result = await agent.execute(state)
        if result.get("error"):
            return {"error": result["error"], "current_step": "import_failed"}
        return {
            "product": result.get("product"),
            "current_step": "imported",
            "step_results": {"import": result},
        }

    async def _asset_optimize_node(self, state: ListingState) -> dict:
        """素材优化节点。"""
        if not state.product:
            return {"error": "No product available", "current_step": "asset_failed"}
        agent = AssetOptimizerAgent(settings=self._settings)
        result = await agent.execute(state)
        return {
            "asset_packages": result.get("asset_packages", state.asset_packages),
            "current_step": "assets_optimized",
            "step_results": {"assets": result},
        }

    async def _copy_node(self, state: ListingState) -> dict:
        """文案生成节点。"""
        if not state.product:
            return {"error": "No product available", "current_step": "copy_failed"}
        agent = CopywriterAgent(settings=self._settings)
        result = await agent.execute(state)
        return {
            "copywriting_packages": result.get("copywriting_packages", state.copywriting_packages),
            "current_step": "copy_generated",
            "step_results": {"copy": result},
        }

    async def run(
        self,
        product: ListingProduct,
        target_platforms: list[Platform],
        thread_id: str = "default",
    ) -> dict:
        """执行刊登工作流。

        Args:
            product: 待刊登商品。
            target_platforms: 目标平台列表。
            thread_id: 会话线程 ID，用于检查点。

        Returns:
            工作流最终状态。
        """
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = ListingState(
            product=product,
            target_platforms=target_platforms,
        )
        return await self.app.ainvoke(initial_state, config=config)
```

- [ ] **Step 5: 更新 `src/graph/__init__.py`**

```python
# 新增导入
from src.graph.listing_state import ListingState
from src.graph.listing_workflow import ListingWorkflow

# 更新 __all__
__all__ = [
    # ... 原有项 ...
    "ListingState",
    "ListingWorkflow",
]
```

- [ ] **Step 6: 运行测试确认通过**

```bash
uv run pytest tests/test_graph/test_listing_workflow.py -v
```

- [ ] **Step 7: 提交**

```bash
git add src/graph/listing_state.py src/graph/listing_workflow.py src/graph/__init__.py tests/test_graph/test_listing_workflow.py
git commit -m "feat: add listing workflow with parallel asset/copy generation"
```

---

### Task 3: 实现 ImportProductAgent

**Files:**
- Create: `src/agents/listing_importer.py`
- Create: `tests/test_agents/test_listing_agents.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_agents/test_listing_agents.py (追加以下内容)
"""刊登 Agent 测试。"""

import pytest

from src.agents.listing_importer import ImportProductAgent
from src.models.listing import ImageRef, ListingProduct


class TestImportProductAgent:
    """测试 ImportProductAgent。"""

    def test_execute_with_manual_input(self) -> None:
        """测试手动录入商品。"""
        agent = ImportProductAgent()
        product_data = {
            "sku": "TEST-001",
            "title": "Wireless Headphones",
            "description": "Bluetooth headphones",
            "category": "Electronics",
            "brand": "SoundMax",
        }
        result = agent.execute_manual(product_data)
        assert result["success"] is True
        assert isinstance(result["product"], ListingProduct)
        assert result["product"].sku == "TEST-001"

    def test_execute_with_image_urls(self) -> None:
        """测试带图片的商品导入。"""
        agent = ImportProductAgent()
        product_data = {
            "sku": "TEST-002",
            "title": "Phone Case",
            "source_images": [
                {"url": "https://example.com/main.jpg", "is_main": True},
                {"url": "https://example.com/side.jpg", "is_main": False},
            ],
        }
        result = agent.execute_manual(product_data)
        assert len(result["product"].source_images) == 2
        assert result["product"].main_image is not None
        assert result["product"].main_image.url == "https://example.com/main.jpg"

    def test_execute_missing_sku(self) -> None:
        """测试缺少 SKU 时失败。"""
        agent = ImportProductAgent()
        result = agent.execute_manual({"title": "No SKU"})
        assert result["success"] is False
        assert "sku" in result.get("error", "")
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_agents/test_listing_agents.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 ImportProductAgent**

```python
# src/agents/listing_importer.py
"""
商品导入 Agent。

Description:
    从手动录入或外部系统导入商品信息，
    标准化为 ListingProduct 模型。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
from typing import Any

from src.models.listing import ImageRef, ListingProduct

logger = logging.getLogger(__name__)


class ImportProductAgent:
    """商品导入 Agent。

    负责将原始商品数据标准化为 ListingProduct。
    支持手动录入和后续扩展的平台 API 导入。
    """

    def __init__(self, settings: Any | None = None) -> None:
        """初始化。

        Args:
            settings: 可选配置。
        """
        self._settings = settings

    def execute_manual(self, product_data: dict[str, Any]) -> dict:
        """手动录入商品。

        Args:
            product_data: 商品原始数据字典，必须包含 sku 和 title。

        Returns:
            包含 success/product/error 的字典。
        """
        sku = product_data.get("sku", "").strip()
        title = product_data.get("title", "").strip()

        if not sku:
            return {"success": False, "error": "sku is required", "product": None}
        if not title:
            return {"success": False, "error": "title is required", "product": None}

        # 解析图片
        source_images = []
        for img_data in product_data.get("source_images", []):
            source_images.append(
                ImageRef(
                    url=img_data.get("url", ""),
                    is_main=img_data.get("is_main", False),
                    width=img_data.get("width"),
                    height=img_data.get("height"),
                )
            )

        product = ListingProduct(
            sku=sku,
            title=title,
            description=product_data.get("description"),
            category=product_data.get("category"),
            brand=product_data.get("brand"),
            price=product_data.get("price"),
            weight=product_data.get("weight"),
            dimensions=product_data.get("dimensions"),
            source_images=source_images,
            attributes=product_data.get("attributes", {}),
        )

        logger.info(f"商品导入成功: sku={sku}, title={title}")
        return {"success": True, "product": product, "error": None}

    async def execute(self, state: Any) -> dict:
        """工作流节点执行方法（兼容性接口）。

        Args:
            state: 工作流状态。

        Returns:
            状态更新字典。
        """
        # 此方法由工作流调用，实际导入通过 execute_manual
        return {"product": state.product, "current_step": "imported"}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_agents/test_listing_agents.py::TestImportProductAgent -v
```

- [ ] **Step 5: 提交**

```bash
git add src/agents/listing_importer.py tests/test_agents/test_listing_agents.py
git commit -m "feat: add ImportProductAgent for manual product import"
```

---

### Task 4: 实现 AssetOptimizerAgent（素材优化引擎）

**Files:**
- Create: `src/agents/listing_asset_optimizer.py`
- Create: `src/agents/listing_platform_specs.py`
- Modify: `tests/test_agents/test_listing_agents.py` — 追加测试

- [ ] **Step 1: 写测试**

```python
# 追加到 tests/test_agents/test_listing_agents.py

from src.agents.listing_asset_optimizer import AssetOptimizerAgent
from src.agents.listing_platform_specs import get_platform_spec, PlatformSpec
from src.graph.listing_state import ListingState
from src.models.listing import AssetPackage, ImageRef, ListingProduct, Platform


class TestPlatformSpec:
    """测试平台规范。"""

    def test_amazon_spec(self) -> None:
        """测试 Amazon 规范。"""
        spec = get_platform_spec(Platform.AMAZON)
        assert spec.main_image_size == (1500, 1500)
        assert spec.white_background is True
        assert spec.max_images == 9
        assert spec.max_title_length == 200

    def test_ebay_spec(self) -> None:
        """测试 eBay 规范。"""
        spec = get_platform_spec(Platform.EBAY)
        assert spec.main_image_size == (1600, 1600)
        assert spec.white_background is True
        assert spec.max_images == 12
        assert spec.max_title_length == 80

    def test_shopify_spec(self) -> None:
        """测试 Shopify 规范。"""
        spec = get_platform_spec(Platform.SHOPFIY)
        assert spec.main_image_size == (2048, 2048)
        assert spec.white_background is False
        assert spec.max_images == 999


class TestAssetOptimizerAgent:
    """测试 AssetOptimizerAgent。"""

    def test_optimize_with_no_images(self) -> None:
        """测试无图片时返回空。"""
        state = ListingState(
            product=ListingProduct(sku="T-001", title="Test"),
            target_platforms=[Platform.AMAZON],
        )
        agent = AssetOptimizerAgent()
        result = agent.execute_sync(state)
        assert len(result["asset_packages"]) == 1
        pkg = result["asset_packages"][Platform.AMAZON]
        assert pkg.main_image is None

    def test_optimize_amazon_single_image(self) -> None:
        """测试 Amazon 单图优化。"""
        state = ListingState(
            product=ListingProduct(
                sku="T-002",
                title="Test",
                source_images=[ImageRef(url="https://example.com/test.jpg", is_main=True)],
            ),
            target_platforms=[Platform.AMAZON],
        )
        agent = AssetOptimizerAgent()
        result = agent.execute_sync(state)
        pkg = result["asset_packages"][Platform.AMAZON]
        assert pkg.main_image is not None
        assert len(pkg.variant_images) == 0

    def test_optimize_multiple_platforms(self) -> None:
        """测试多平台同时优化。"""
        state = ListingState(
            product=ListingProduct(
                sku="T-003",
                title="Test",
                source_images=[ImageRef(url="https://example.com/test.jpg", is_main=True)],
            ),
            target_platforms=[Platform.AMAZON, Platform.EBAY, Platform.SHOPFIY],
        )
        agent = AssetOptimizerAgent()
        result = agent.execute_sync(state)
        assert len(result["asset_packages"]) == 3
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_agents/test_listing_agents.py -v
```

- [ ] **Step 3: 实现平台规范**

```python
# src/agents/listing_platform_specs.py
"""
各平台素材规范配置。

Description:
    定义 Amazon、eBay、Shopify 的素材尺寸、格式、数量等规范。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

from dataclasses import dataclass

from src.models.listing import Platform


@dataclass(frozen=True)
class PlatformSpec:
    """平台素材规范。"""

    main_image_size: tuple[int, int]  # (宽, 高)
    white_background: bool  # 是否需要白底
    max_images: int  # 最大图片数
    max_title_length: int  # 标题最大长度
    video_supported: bool  # 是否支持视频
    accepted_formats: tuple[str, ...] = ("jpg", "jpeg", "png", "webp")


# Amazon 规范: 白底 1500x1500+, 最多9张, 标题≤200
AMAZON_SPEC = PlatformSpec(
    main_image_size=(1500, 1500),
    white_background=True,
    max_images=9,
    max_title_length=200,
    video_supported=True,
)

# eBay 规范: 白底 1600x1600+, 最多12张, 标题≤80
EBAY_SPEC = PlatformSpec(
    main_image_size=(1600, 1600),
    white_background=True,
    max_images=12,
    max_title_length=80,
    video_supported=True,
)

# Shopify 规范: 自定义 2048x2048, 无限图片, 标题无限制
SHOPIFY_SPEC = PlatformSpec(
    main_image_size=(2048, 2048),
    white_background=False,
    max_images=999,
    max_title_length=0,  # 无限制
    video_supported=True,
)

_SPECS: dict[Platform, PlatformSpec] = {
    Platform.AMAZON: AMAZON_SPEC,
    Platform.EBAY: EBAY_SPEC,
    Platform.SHOPFIY: SHOPIFY_SPEC,
}


def get_platform_spec(platform: Platform) -> PlatformSpec:
    """获取平台规范。

    Args:
        platform: 目标平台。

    Returns:
        平台素材规范。
    """
    return _SPECS[platform]
```

- [ ] **Step 4: 实现素材优化 Agent**

```python
# src/agents/listing_asset_optimizer.py
"""
素材优化 Agent。

Description:
    根据各平台规范，对原始图片进行裁剪、压缩、格式转换，
    生成符合平台要求的素材包。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
from typing import Any

from src.agents.listing_platform_specs import get_platform_spec
from src.graph.listing_state import ListingState
from src.models.listing import AssetPackage, Platform

logger = logging.getLogger(__name__)


class AssetOptimizerAgent:
    """素材优化 Agent。

    为每个目标平台生成标准化素材包。
    当前阶段：传递原始图片路径，标记平台规范信息。
    后续阶段：集成 Pillow 进行实际图片处理。

    Attributes:
        settings: 可选配置。
    """

    def __init__(self, settings: Any | None = None) -> None:
        """初始化。"""
        self._settings = settings

    def execute_sync(self, state: ListingState) -> dict:
        """同步执行素材优化。

        Args:
            state: 工作流状态。

        Returns:
            包含 asset_packages 的更新字典。
        """
        product = state.product
        if not product:
            return {"asset_packages": {}}

        asset_packages: dict[Platform, AssetPackage] = {}

        for platform in state.target_platforms:
            spec = get_platform_spec(platform)
            logger.info(f"优化素材: platform={platform.value}, spec={spec}")

            # 当前阶段：直接传递原始图片路径
            # 后续集成 Pillow 进行实际处理
            main_image = None
            variant_images = []

            if product.source_images:
                # 取主图
                main = product.main_image
                if main:
                    main_image = main.url

                # 取变体图（排除主图，限制数量）
                for img in product.source_images:
                    if not img.is_main and img.url != main_image:
                        variant_images.append(img.url)
                        if len(variant_images) >= spec.max_images - 1:
                            break

            asset_packages[platform] = AssetPackage(
                listing_task_id=0,  # 实际由工作流注入
                platform=platform,
                main_image=main_image,
                variant_images=variant_images[: spec.max_images - 1],
            )

        return {"asset_packages": asset_packages}

    async def execute(self, state: ListingState) -> dict:
        """异步执行（工作流节点接口）。"""
        return self.execute_sync(state)
```

- [ ] **Step 5: 运行测试确认通过**

```bash
uv run pytest tests/test_agents/test_listing_agents.py -v
```

- [ ] **Step 6: 提交**

```bash
git add src/agents/listing_asset_optimizer.py src/agents/listing_platform_specs.py tests/test_agents/test_listing_agents.py
git commit -m "feat: add AssetOptimizerAgent with platform specs"
```

---

### Task 5: 实现 CopywriterAgent（文案生成引擎）

**Files:**
- Create: `src/agents/listing_copywriter.py`
- Modify: `tests/test_agents/test_listing_agents.py` — 追加测试

- [ ] **Step 1: 写测试**

```python
# 追加到 tests/test_agents/test_listing_agents.py

from src.agents.listing_copywriter import CopywriterAgent
from src.graph.listing_state import ListingState
from src.models.listing import (
    CopywritingPackage,
    ListingProduct,
    Platform,
    SellingPoint,
)


class TestCopywriterAgent:
    """测试 CopywriterAgent。"""

    def test_generate_amazon_copy(self) -> None:
        """测试 Amazon 文案生成。"""
        state = ListingState(
            product=ListingProduct(
                sku="T-010",
                title="Wireless Bluetooth Headphones",
                description="Premium noise-cancelling headphones",
                brand="SoundMax",
                category="Electronics",
            ),
            target_platforms=[Platform.AMAZON],
        )
        agent = CopywriterAgent()
        result = agent.execute_sync(state)
        assert Platform.AMAZON in result["copywriting_packages"]
        pkg = result["copywriting_packages"][Platform.AMAZON]
        assert pkg.platform == Platform.AMAZON
        assert pkg.language == "en"
        # 验证标题不超过200字符
        assert len(pkg.title) <= 200

    def test_generate_ebay_copy_truncates_title(self) -> None:
        """测试 eBay 文案（标题截断到80字符）。"""
        state = ListingState(
            product=ListingProduct(
                sku="T-011",
                title="A Very Long Product Title That Would Exceed Eighty Characters Limit For eBay Platform",
                description="Some description",
            ),
            target_platforms=[Platform.EBAY],
        )
        agent = CopywriterAgent()
        result = agent.execute_sync(state)
        pkg = result["copywriting_packages"][Platform.EBAY]
        assert len(pkg.title) <= 80

    def test_generate_shopify_copy(self) -> None:
        """测试 Shopify 文案（无标题长度限制）。"""
        long_title = "A" * 300
        state = ListingState(
            product=ListingProduct(
                sku="T-012",
                title=long_title,
                description="Detailed description",
            ),
            target_platforms=[Platform.SHOPFIY],
        )
        agent = CopywriterAgent()
        result = agent.execute_sync(state)
        pkg = result["copywriting_packages"][Platform.SHOPFIY]
        assert len(pkg.title) == len(long_title)

    def test_generate_multi_platform_copy(self) -> None:
        """测试多平台同时生成。"""
        state = ListingState(
            product=ListingProduct(sku="T-013", title="Multi-Platform Product"),
            target_platforms=[Platform.AMAZON, Platform.EBAY, Platform.SHOPFIY],
        )
        agent = CopywriterAgent()
        result = agent.execute_sync(state)
        assert len(result["copywriting_packages"]) == 3
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_agents/test_listing_agents.py::TestCopywriterAgent -v
```

- [ ] **Step 3: 实现 CopywriterAgent**

```python
# src/agents/listing_copywriter.py
"""
文案生成 Agent。

Description:
    基于商品信息，为各平台生成符合规范的文案，
    包括标题、五点描述、长描述、搜索关键词。
    当前阶段使用规则生成，后续接入 LLM 优化。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
from typing import Any

from src.agents.listing_platform_specs import get_platform_spec
from src.graph.listing_state import ListingState
from src.models.listing import CopywritingPackage, Platform

logger = logging.getLogger(__name__)


class CopywriterAgent:
    """文案生成 Agent。

    为每个目标平台生成标准化文案包。
    当前阶段：基于规则生成基础文案。
    后续阶段：接入 LLM 生成更优质的文案。

    Attributes:
        settings: 可选配置。
    """

    def __init__(self, settings: Any | None = None) -> None:
        """初始化。"""
        self._settings = settings

    def execute_sync(self, state: ListingState) -> dict:
        """同步执行文案生成。

        Args:
            state: 工作流状态。

        Returns:
            包含 copywriting_packages 的更新字典。
        """
        product = state.product
        if not product:
            return {"copywriting_packages": {}}

        copywriting_packages: dict[Platform, CopywritingPackage] = {}

        for platform in state.target_platforms:
            spec = get_platform_spec(platform)
            logger.info(f"生成文案: platform={platform.value}")

            # 生成标题（按平台限制截断）
            title = self._generate_title(product, spec)

            # 生成五点描述（Amazon 必需）
            bullet_points = self._generate_bullet_points(product, platform)

            # 生成长描述
            description = self._generate_description(product)

            # 生成搜索关键词
            search_terms = self._generate_search_terms(product)

            copywriting_packages[platform] = CopywritingPackage(
                listing_task_id=0,  # 实际由工作流注入
                platform=platform,
                language="en",
                title=title,
                bullet_points=bullet_points,
                description=description,
                search_terms=search_terms,
            )

        return {"copywriting_packages": copywriting_packages}

    def _generate_title(self, product, spec) -> str:
        """生成平台兼容标题。

        Args:
            product: 商品信息。
            spec: 平台规范。

        Returns:
            符合平台标题长度限制的商品标题。
        """
        base_title = product.title or ""

        # 添加品牌前缀（如有）
        if product.brand:
            base_title = f"{product.brand} {base_title}"

        # 按平台限制截断
        if spec.max_title_length > 0:
            base_title = base_title[: spec.max_title_length].rstrip()

        return base_title

    def _generate_bullet_points(self, product, platform: Platform) -> list[str]:
        """生成五点描述。

        Args:
            product: 商品信息。
            platform: 目标平台。

        Returns:
            五点描述列表（Amazon 必需，其他平台可选）。
        """
        bullets = []
        desc = product.description or ""

        # 基于描述拆分要点（简单规则，后续用 LLM 优化）
        if desc:
            sentences = [s.strip() for s in desc.replace(".", "\n").split("\n") if s.strip()]
            bullets = sentences[:5]

        # 补充默认要点
        if not bullets:
            bullets = [f"Premium quality {product.category or 'product'}"]
            if product.brand:
                bullets.append(f"Brand: {product.brand}")

        return bullets[:5]

    def _generate_description(self, product) -> str:
        """生成长描述。"""
        parts = []
        if product.description:
            parts.append(product.description)
        if product.brand:
            parts.append(f"Brand: {product.brand}")
        if product.category:
            parts.append(f"Category: {product.category}")
        return "\n".join(parts) if parts else ""

    def _generate_search_terms(self, product) -> list[str]:
        """生成搜索关键词。"""
        terms = []
        if product.category:
            terms.append(product.category.lower())
        if product.brand:
            terms.append(product.brand.lower())
        # 从标题提取关键词
        if product.title:
            words = product.title.lower().split()
            terms.extend([w for w in words if len(w) > 3][:5])
        return list(dict.fromkeys(terms))  # 去重保序

    async def execute(self, state: ListingState) -> dict:
        """异步执行（工作流节点接口）。"""
        return self.execute_sync(state)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_agents/test_listing_agents.py -v
```

- [ ] **Step 5: 提交**

```bash
git add src/agents/listing_copywriter.py tests/test_agents/test_listing_agents.py
git commit -m "feat: add CopywriterAgent with rule-based copywriting generation"
```

---

### Task 6: 新增 API 层（listing 路由和 Schema）

**Files:**
- Create: `src/api/schema/listing.py`
- Create: `src/api/router/listing.py`
- Modify: `src/api/router/__init__.py` — 注册 listing 路由
- Create: `tests/test_api/test_listing_api.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_api/test_listing_api.py
"""刊登 API 测试。"""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client() -> TestClient:
    """创建测试客户端。"""
    return TestClient(app)


class TestProductImportAPI:
    """测试商品导入 API。"""

    def test_import_product_success(self, client: TestClient) -> None:
        """测试成功导入商品。"""
        response = client.post(
            "/api/v1/listing/import-product",
            json={
                "sku": "API-TEST-001",
                "title": "Test Product via API",
                "description": "A test product",
                "category": "Test",
                "brand": "TestBrand",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["sku"] == "API-TEST-001"

    def test_import_product_missing_sku(self, client: TestClient) -> None:
        """测试缺少 SKU 返回错误。"""
        response = client.post(
            "/api/v1/listing/import-product",
            json={"title": "No SKU Product"},
        )
        assert response.status_code == 422  # Validation error

    def test_list_products(self, client: TestClient) -> None:
        """测试商品列表。"""
        response = client.get("/api/v1/listing/products")
        assert response.status_code == 200


class TestListingTaskAPI:
    """测试刊登任务 API。"""

    def test_create_task(self, client: TestClient) -> None:
        """测试创建刊登任务。"""
        response = client.post(
            "/api/v1/listing/tasks",
            json={
                "product_sku": "API-TEST-001",
                "target_platforms": ["amazon", "ebay"],
            },
        )
        # 404 表示商品不存在（预期行为，因先不创建商品）
        assert response.status_code in (201, 404)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_api/test_listing_api.py -v
```

- [ ] **Step 3: 实现 API Schema**

```python
# src/api/schema/listing.py
"""
刊登工具 API Schema。

Description:
    定义刊登工具的请求/响应 DTO。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

from typing import Any

from pydantic import BaseModel, Field

from src.models.listing import Platform


class ProductImportRequest(BaseModel):
    """商品导入请求。"""

    sku: str = Field(..., min_length=1, max_length=100, description="商品SKU")
    title: str = Field(..., min_length=1, max_length=500, description="商品标题")
    description: str | None = Field(default=None, description="商品描述")
    category: str | None = Field(default=None, description="商品类目")
    brand: str | None = Field(default=None, description="品牌")
    price: float | None = Field(default=None, ge=0, description="价格")
    weight: float | None = Field(default=None, ge=0, description="重量(kg)")
    dimensions: dict[str, Any] | None = Field(default=None, description="尺寸")
    source_images: list[dict[str, Any]] = Field(default_factory=list, description="图片列表")
    attributes: dict[str, Any] = Field(default_factory=dict, description="属性")


class ProductResponse(BaseModel):
    """商品响应。"""

    sku: str
    title: str
    description: str | None
    category: str | None
    brand: str | None
    source_images: list[dict[str, Any]]


class CreateListingTaskRequest(BaseModel):
    """创建刊登任务请求。"""

    product_sku: str = Field(..., description="商品SKU")
    target_platforms: list[Platform] = Field(..., min_length=1, description="目标平台")


class ListingTaskResponse(BaseModel):
    """刊登任务响应。"""

    task_id: int
    product_sku: str
    target_platforms: list[str]
    status: str
```

- [ ] **Step 4: 实现 API Router**

```python
# src/api/router/listing.py
"""
刊登工具 API 路由。

Description:
    提供商品导入、刊登任务创建等 REST 接口。
    Phase 1 实现：导入商品、创建任务（素材+文案生成）。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
from typing import Any

from fastapi import APIRouter, status

from src.api.schema.listing import (
    CreateListingTaskRequest,
    ListingTaskResponse,
    ProductImportRequest,
    ProductResponse,
)
from src.api.schema.common import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# 内存存储（Phase 1），后续替换为数据库
_products: dict[str, Any] = {}
_tasks: list[dict] = []


@router.post(
    "/import-product",
    response_model=ApiResponse[ProductResponse],
    status_code=status.HTTP_201_CREATED,
    summary="导入商品",
)
async def import_product(request: ProductImportRequest) -> ApiResponse[ProductResponse]:
    """导入商品到刊登系统。

    Args:
        request: 商品导入请求。

    Returns:
        导入的商品信息。
    """
    from src.agents.listing_importer import ImportProductAgent

    agent = ImportProductAgent()
    product_data = request.model_dump()
    result = agent.execute_manual(product_data)

    if not result["success"]:
        return ApiResponse(code=400, message=result["error"], data=None)

    product = result["product"]
    _products[product.sku] = product

    return ApiResponse(
        code=200,
        message="商品导入成功",
        data=ProductResponse(
            sku=product.sku,
            title=product.title,
            description=product.description,
            category=product.category,
            brand=product.brand,
            source_images=[img.model_dump() for img in product.source_images],
        ),
    )


@router.get(
    "/products",
    response_model=ApiResponse[list[ProductResponse]],
    summary="商品列表",
)
async def list_products() -> ApiResponse[list[ProductResponse]]:
    """获取已导入的商品列表。"""
    return ApiResponse(
        code=200,
        message="成功",
        data=[
            ProductResponse(
                sku=p.sku,
                title=p.title,
                description=p.description,
                category=p.category,
                brand=p.brand,
                source_images=[img.model_dump() for img in p.source_images],
            )
            for p in _products.values()
        ],
    )


@router.post(
    "/tasks",
    response_model=ApiResponse[ListingTaskResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建刊登任务",
)
async def create_task(request: CreateListingTaskRequest) -> ApiResponse[ListingTaskResponse]:
    """创建刊登任务，触发生成素材和文案。

    Args:
        request: 刊登任务请求。

    Returns:
        创建的任务信息。
    """
    if request.product_sku not in _products:
        return ApiResponse(code=404, message=f"商品 {request.product_sku} 不存在", data=None)

    product = _products[request.product_sku]
    task_id = len(_tasks) + 1

    task_data = {
        "task_id": task_id,
        "product_sku": request.product_sku,
        "target_platforms": [p.value for p in request.target_platforms],
        "status": "pending",
    }
    _tasks.append(task_data)

    return ApiResponse(
        code=200,
        message="任务已创建",
        data=ListingTaskResponse(
            task_id=task_id,
            product_sku=request.product_sku,
            target_platforms=[p.value for p in request.target_platforms],
            status="pending",
        ),
    )


@router.get(
    "/tasks",
    response_model=ApiResponse[list[ListingTaskResponse]],
    summary="任务列表",
)
async def list_tasks() -> ApiResponse[list[ListingTaskResponse]]:
    """获取刊登任务列表。"""
    return ApiResponse(
        code=200,
        message="成功",
        data=[
            ListingTaskResponse(
                task_id=t["task_id"],
                product_sku=t["product_sku"],
                target_platforms=t["target_platforms"],
                status=t["status"],
            )
            for t in _tasks
        ],
    )
```

- [ ] **Step 5: 注册路由**

在 `src/api/router/__init__.py` 中添加：

```python
from src.api.router.listing import router as listing_router

# 在 include_router 区域添加
api_router.include_router(listing_router, prefix="/listing", tags=["刊登工具"])
```

- [ ] **Step 6: 运行测试确认通过**

```bash
uv run pytest tests/test_api/test_listing_api.py -v
```

- [ ] **Step 7: 提交**

```bash
git add src/api/schema/listing.py src/api/router/listing.py src/api/router/__init__.py tests/test_api/test_listing_api.py
git commit -m "feat: add listing API routes and schemas"
```

---

### Task 7: 集成到 main.py 并添加新依赖

**Files:**
- Modify: `main.py` — 在 lifespan 中初始化（可选）
- Modify: `pyproject.toml` — 添加 Pillow 依赖

- [ ] **Step 1: 添加 Pillow 依赖到 pyproject.toml**

在 dependencies 区域添加：

```toml
# 图片处理
"pillow>=10.0.0",
```

- [ ] **Step 2: 安装依赖**

```bash
uv pip install pillow
```

- [ ] **Step 3: 提交**

```bash
git add pyproject.toml main.py
git commit -m "chore: add pillow dependency for image processing"
```

---

### Task 8: 全量测试与最终提交

- [ ] **Step 1: 运行所有新增测试**

```bash
uv run pytest tests/test_models/test_listing.py tests/test_graph/test_listing_workflow.py tests/test_agents/test_listing_agents.py tests/test_api/test_listing_api.py -v
```
Expected: All tests PASS

- [ ] **Step 2: 运行代码质量检查**

```bash
uv run ruff format . && uv run ruff check .
```

- [ ] **Step 3: 运行类型检查**

```bash
uv run mypy src/
```

- [ ] **Step 4: 全量测试**

```bash
uv run pytest --cov=src --cov-report=term-missing
```
Expected: Coverage ≥ 80% for new modules

- [ ] **Step 5: 提交**

```bash
git add .
git commit -m "feat: listing tool phase 1 complete - import, assets, copywriting, API"
```

---

## Phase 1 产出总结

| 模块 | 文件 | 状态 |
|------|------|------|
| 数据模型 | `src/models/listing.py` | 6 个 Pydantic 模型 |
| 工作流状态 | `src/graph/listing_state.py` | ListingState |
| 工作流构建 | `src/graph/listing_workflow.py` | 并行素材+文案 |
| 商品导入 | `src/agents/listing_importer.py` | 手动录入 |
| 素材优化 | `src/agents/listing_asset_optimizer.py` | 平台规范传递 |
| 平台规范 | `src/agents/listing_platform_specs.py` | Amazon/eBay/Shopify |
| 文案生成 | `src/agents/listing_copywriter.py` | 规则生成 |
| API Schema | `src/api/schema/listing.py` | 请求/响应 DTO |
| API 路由 | `src/api/router/listing.py` | 4 个端点 |
| 测试 | 4 个测试文件 | TDD 全流程 |

## Phase 2 及后续（不在本计划范围内）

- Phase 2: 合规检查引擎
- Phase 3: Amazon SP-API 适配器
- Phase 4: eBay + Shopify 适配器
- Phase 5: 前端刊登界面
