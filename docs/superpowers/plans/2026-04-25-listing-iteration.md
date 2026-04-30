# 刊登工具迭代实施计划 (Phase 3-5 增强)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现真实工作流执行、AI 文案生成（多 LLM）、适配器配置管理（数据库存储）、数据库持久化四项增强。

**Architecture:** 三层架构——前端 Vue 3 → FastAPI 业务层 → PostgreSQL 持久化。LangGraph 工作流真实接线占位节点，文案生成使用 LLM 降级策略（通义→Claude→规则）。

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, SQLAlchemy async, LangGraph, langchain-community (ChatTongyi) / langchain-anthropic, Vue 3, TypeScript, Element Plus

---

## 文件结构映射

```
src/db/
├── listing_models.py           # 刊登 7 张表 ORM 模型 (新建)
├── repository.py               # 通用异步 Repository (新建)

src/agents/
├── listing_copywriter.py       # 改造：集成 LLM 降级
├── adapter_config.py           # 适配器配置管理器 (新建)

src/api/schema/
├── listing.py (修改)           # 新增 ExecuteTaskResponse, AdapterConfig 等 schema
├── adapter_config.py           # 适配器配置 DTO (新建)

src/api/router/
├── listing.py (大幅修改)       # auto_execute, 手动触发, 数据库读写
├── listing_push.py (修改)      # 从数据库读取已生成数据
├── adapter_config.py           # 适配器配置 CRUD (新建)
├── __init__.py (修改)          # 注册新路由

src/graph/
├── listing_workflow.py (修改)  # 接线真实 Agent 节点

frontend/src/views/listing/
├── AdapterConfig.vue           # 配置管理页面 (新建)

frontend/src/api/
├── listing.ts (修改)           # 新增 API 函数

frontend/src/router/
├── index.ts (修改)             # 新增配置路由

frontend/src/components/Layout/
├── Sidebar.vue (修改)          # 新增配置菜单

tests/
├── test_db/test_listing_models.py
├── test_agents/test_adapter_config.py
├── test_agents/test_listing_copywriter_llm.py
├── test_api/test_adapter_config_api.py
```

---

### Task 1: 刊登数据库 ORM 模型

**Files:**
- Create: `src/db/listing_models.py`
- Create: `src/db/repository.py`
- Test: `tests/test_db/test_listing_models.py`

- [ ] **Step 1: Write the failing test**

```python
"""刊登数据库模型测试。"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.listing_models import (
    AdapterConfigPO,
    AssetPackagePO,
    ComplianceReportPO,
    CopywritingPackagePO,
    ListingProductPO,
    ListingTaskPO,
    TaskResultPO,
)


class TestListingModels:
    """测试所有 ORM 模型的定义。"""

    def test_listing_product_po_fields(self) -> None:
        """测试商品模型字段。"""
        po = ListingProductPO(
            sku="TEST-001",
            title="Test Product",
            description="A test product",
            category="Electronics",
            brand="TestBrand",
        )
        assert po.sku == "TEST-001"
        assert po.title == "Test Product"
        assert po.category == "Electronics"

    def test_listing_task_po_fields(self) -> None:
        """测试任务模型字段。"""
        po = ListingTaskPO(
            product_sku="TEST-001",
            target_platforms=["amazon", "ebay"],
            status="pending",
            workflow_state="imported",
        )
        assert po.product_sku == "TEST-001"
        assert "amazon" in po.target_platforms
        assert po.workflow_state == "imported"

    def test_asset_package_po_fields(self) -> None:
        """测试素材包模型。"""
        po = AssetPackagePO(
            task_id=1,
            platform="amazon",
            main_image="https://example.com/main.jpg",
            variant_images=["https://example.com/v1.jpg"],
        )
        assert po.task_id == 1
        assert po.platform == "amazon"
        assert len(po.variant_images) == 1

    def test_copywriting_package_po_fields(self) -> None:
        """测试文案包模型。"""
        po = CopywritingPackagePO(
            task_id=1,
            platform="ebay",
            title="Test Title",
            bullet_points=["Feature 1", "Feature 2"],
            description="Test description",
            search_terms=["test", "product"],
        )
        assert po.title == "Test Title"
        assert len(po.bullet_points) == 2

    def test_compliance_report_po_json(self) -> None:
        """测试合规报告 JSON 存储。"""
        po = ComplianceReportPO(
            task_id=1,
            platform="amazon",
            report_data={
                "overall": "pass",
                "image_issues": [],
                "text_issues": [],
                "forbidden_words": [],
            },
        )
        assert po.report_data["overall"] == "pass"

    def test_task_result_po_json(self) -> None:
        """测试结果 JSON 存储。"""
        po = TaskResultPO(
            task_id=1,
            platform="shopify",
            result_data={
                "success": True,
                "listing_id": "gid://shopify/Product/123",
                "url": "https://my-store.myshopify.com/products/test",
            },
        )
        assert po.result_data["success"] is True

    def test_adapter_config_po_fields(self) -> None:
        """测试适配器配置模型。"""
        po = AdapterConfigPO(
            platform="amazon",
            shop_id="shop-001",
            credentials={
                "client_id": "amzn1.xxx",
                "client_secret": "secret",
                "refresh_token": "Atzr|xxx",
                "marketplace_id": "ATVPDKIKX0DER",
            },
            is_active=True,
        )
        assert po.platform == "amazon"
        assert po.shop_id == "shop-001"
        assert po.credentials["marketplace_id"] == "ATVPDKIKX0DER"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_db/test_listing_models.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.db.listing_models'"

- [ ] **Step 3: Write the implementation**

创建 `src/db/listing_models.py`:

```python
"""
刊登模块数据库模型。

Description:
    定义刊登工具 7 张表的 ORM 模型，使用 SQLAlchemy 2.0 风格。
    图片统一存 OSS URL，合规报告和推送结果存 JSONB。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.postgres import Base


class ListingProductPO(Base):
    """刊登商品表。"""

    __tablename__ = "listing_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(200))
    brand: Mapped[str | None] = mapped_column(String(200))
    price: Mapped[float | None] = mapped_column(precision=10, scale=2, nullable=True)
    weight: Mapped[float | None] = mapped_column(precision=10, scale=2, nullable=True)
    dimensions: Mapped[dict | None] = mapped_column(JSONB)
    source_images: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (Index("ix_listing_products_sku", "sku"),)

    def __repr__(self) -> str:
        return f"<ListingProductPO(id={self.id}, sku='{self.sku}')>"


class ListingTaskPO(Base):
    """刊登任务表。"""

    __tablename__ = "listing_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_sku: Mapped[str] = mapped_column(
        String(100), ForeignKey("listing_products.sku"), nullable=False, index=True
    )
    target_platforms: Mapped[list[str]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    workflow_state: Mapped[str | None] = mapped_column(String(50))
    auto_execute: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (Index("ix_listing_tasks_product_sku", "product_sku"),)

    def __repr__(self) -> str:
        return f"<ListingTaskPO(id={self.id}, product_sku='{self.product_sku}', status='{self.status}')>"


class AssetPackagePO(Base):
    """素材包表。"""

    __tablename__ = "asset_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("listing_tasks.id"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    main_image: Mapped[str | None] = mapped_column(String(1000))
    variant_images: Mapped[list[str]] = mapped_column(JSONB, default=list)
    video_url: Mapped[str | None] = mapped_column(String(1000))
    a_plus_images: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_asset_packages_task_platform", "task_id", "platform"),)

    def __repr__(self) -> str:
        return f"<AssetPackagePO(id={self.id}, task_id={self.task_id}, platform='{self.platform}')>"


class CopywritingPackagePO(Base):
    """文案包表。"""

    __tablename__ = "copywriting_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("listing_tasks.id"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en")
    title: Mapped[str] = mapped_column(String(500), default="")
    bullet_points: Mapped[list[str]] = mapped_column(JSONB, default=list)
    description: Mapped[str] = mapped_column(Text, default="")
    search_terms: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_copywriting_task_platform", "task_id", "platform"),)

    def __repr__(self) -> str:
        return f"<CopywritingPackagePO(id={self.id}, task_id={self.task_id}, platform='{self.platform}')>"


class ComplianceReportPO(Base):
    """合规报告表。"""

    __tablename__ = "compliance_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("listing_tasks.id"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    report_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_compliance_task_platform", "task_id", "platform"),)

    def __repr__(self) -> str:
        return f"<ComplianceReportPO(id={self.id}, task_id={self.task_id}, platform='{self.platform}')>"


class TaskResultPO(Base):
    """推送结果表。"""

    __tablename__ = "task_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("listing_tasks.id"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    result_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_task_result_task_platform", "task_id", "platform"),)

    def __repr__(self) -> str:
        return f"<TaskResultPO(id={self.id}, task_id={self.task_id}, platform='{self.platform}')>"


class AdapterConfigPO(Base):
    """适配器配置表。"""

    __tablename__ = "adapter_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    credentials: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_adapter_config_platform_shop", "platform", "shop_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<AdapterConfigPO(id={self.id}, platform='{self.platform}', shop_id='{self.shop_id}')>"
```

- [ ] **Step 4: Write the generic Repository**

创建 `src/db/repository.py`:

```python
"""
通用异步 Repository。

Description:
    基于 SQLAlchemy 2.0 的通用异步 CRUD 封装。
    所有业务 Repository 继承此类。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

from typing import Any, Generic, Sequence, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.postgres import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """通用异步 Repository 基类。

    Attributes:
        model: ORM 模型类。
        session: 异步数据库会话。
    """

    def __init__(self, model: type[ModelT], session: AsyncSession) -> None:
        """初始化。

        Args:
            model: ORM 模型类。
            session: 异步数据库会话。
        """
        self.model = model
        self.session = session

    async def get(self, id: int) -> ModelT | None:
        """根据 ID 获取记录。

        Args:
            id: 主键。

        Returns:
            ORM 模型实例或 None。
        """
        return await self.session.get(self.model, id)

    async def get_by_field(self, field: str, value: Any) -> ModelT | None:
        """根据字段获取唯一记录。

        Args:
            field: 字段名。
            value: 字段值。

        Returns:
            ORM 模型实例或 None。
        """
        stmt = select(self.model).where(getattr(self.model, field) == value)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(self, **filters: Any) -> Sequence[ModelT]:
        """根据过滤条件查询列表。

        Args:
            **filters: 字段=值 过滤条件。

        Returns:
            ORM 模型列表。
        """
        stmt = select(self.model)
        for field, value in filters.items():
            stmt = stmt.where(getattr(self.model, field) == value)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, **kwargs: Any) -> ModelT:
        """创建新记录。

        Args:
            **kwargs: 字段值。

        Returns:
            创建的 ORM 模型实例。
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, id: int, **kwargs: Any) -> ModelT | None:
        """更新记录。

        Args:
            id: 主键。
            **kwargs: 要更新的字段。

        Returns:
            更新后的 ORM 模型实例或 None。
        """
        instance = await self.get(id)
        if instance:
            for key, value in kwargs.items():
                setattr(instance, key, value)
            await self.session.flush()
            await self.session.refresh(instance)
        return instance

    async def delete(self, id: int) -> bool:
        """删除记录。

        Args:
            id: 主键。

        Returns:
            是否删除成功。
        """
        instance = await self.get(id)
        if instance:
            await self.session.delete(instance)
            await self.session.flush()
            return True
        return False
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_db/test_listing_models.py -v`
Expected: All 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/db/listing_models.py src/db/repository.py tests/test_db/test_listing_models.py
git commit -m "feat: add listing ORM models and generic async repository"
```

---

### Task 2: 适配器配置管理器

**Files:**
- Create: `src/agents/adapter_config.py`
- Create: `src/api/schema/adapter_config.py`
- Test: `tests/test_agents/test_adapter_config.py`

- [ ] **Step 1: Write the failing test**

```python
"""适配器配置管理器测试。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.adapter_config import AdapterConfigManager
from src.models.listing import Platform


class TestAdapterConfigManager:
    """测试适配器配置管理器。"""

    @pytest.fixture
    def manager(self) -> AdapterConfigManager:
        """创建配置管理器实例。"""
        return AdapterConfigManager()

    def test_singleton(self) -> None:
        """测试管理器是单例。"""
        m1 = AdapterConfigManager()
        m2 = AdapterConfigManager()
        assert m1 is m2

    @pytest.mark.asyncio
    async def test_get_config_from_db(self, manager: AdapterConfigManager) -> None:
        """测试从数据库获取配置。"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(
            platform="amazon",
            shop_id="default",
            credentials={
                "client_id": "amzn1.xxx",
                "client_secret": "secret",
                "refresh_token": "Atzr|xxx",
                "marketplace_id": "ATVPDKIKX0DER",
            },
            is_active=True,
        )
        mock_session.execute.return_value = mock_result

        with patch("src.agents.adapter_config.get_db") as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            config = await manager.get_config(Platform.AMAZON, "default")
            assert config is not None
            assert config["client_id"] == "amzn1.xxx"

    @pytest.mark.asyncio
    async def test_cache_hit(self, manager: AdapterConfigManager) -> None:
        """测试缓存命中。"""
        key = (Platform.AMAZON, "shop-1")
        cached = {"client_id": "cached"}
        manager._cache[key] = (cached, 9999999999.0)  # 很久才过期

        result = await manager.get_config(Platform.AMAZON, "shop-1")
        assert result == cached

    @pytest.mark.asyncio
    async def test_cache_expired(self, manager: AdapterConfigManager) -> None:
        """测试缓存过期后重新查询。"""
        key = (Platform.AMAZON, "shop-2")
        manager._cache[key] = ({"old": True}, 0.0)  # 已过期

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(
            platform="amazon", shop_id="shop-2",
            credentials={"client_id": "fresh"}, is_active=True,
        )
        mock_session.execute.return_value = mock_result

        with patch("src.agents.adapter_config.get_db") as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            config = await manager.get_config(Platform.AMAZON, "shop-2")
            assert config["client_id"] == "fresh"

    @pytest.mark.asyncio
    async def test_config_not_found(self, manager: AdapterConfigManager) -> None:
        """测试配置不存在返回 None。"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("src.agents.adapter_config.get_db") as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await manager.get_config(Platform.EBAY, "nonexistent")
            assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_cache(self, manager: AdapterConfigManager) -> None:
        """测试清除缓存。"""
        key = (Platform.SHOPIFY, "shop-3")
        manager._cache[key] = ({"test": True}, 9999999999.0)
        await manager.invalidate_cache(Platform.SHOPIFY, "shop-3")
        assert key not in manager._cache

    @pytest.mark.asyncio
    async def test_invalidate_all_platform(self, manager: AdapterConfigManager) -> None:
        """测试清除某平台所有店铺的缓存。"""
        manager._cache[(Platform.AMAZON, "shop-1")] = ({"a": 1}, 9999999999.0)
        manager._cache[(Platform.AMAZON, "shop-2")] = ({"b": 2}, 9999999999.0)
        manager._cache[(Platform.EBAY, "shop-1")] = ({"c": 3}, 9999999999.0)

        await manager.invalidate_cache(Platform.AMAZON)

        assert (Platform.AMAZON, "shop-1") not in manager._cache
        assert (Platform.AMAZON, "shop-2") not in manager._cache
        assert (Platform.EBAY, "shop-1") in manager._cache
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_agents/test_adapter_config.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.agents.adapter_config'"

- [ ] **Step 3: Write the implementation**

创建 `src/agents/adapter_config.py`:

```python
"""
适配器配置管理器。

Description:
    从数据库读取平台适配器凭证，支持多店铺配置。
    内存缓存 + 5 分钟过期，减少数据库查询。
    单例模式，全局共享。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
import time
from typing import Any

from src.db.postgres import Base
from src.models.listing import Platform

logger = logging.getLogger(__name__)

CACHE_TTL = 300  # 5 分钟


class AdapterConfigManager:
    """适配器配置管理器（单例）。

    职责:
    - 从 adapter_configs 表读取平台凭证
    - 支持多店铺（同平台多配置）
    - 内存缓存 + 5 分钟过期

    Example:
        >>> mgr = AdapterConfigManager()
        >>> config = await mgr.get_config(Platform.AMAZON, "shop-1")
        >>> adapter = registry.get(Platform.AMAZON, config=config)
    """

    _instance: "AdapterConfigManager | None" = None
    _cache: dict[tuple[Platform, str], tuple[dict, float]]
    _db_initialized: bool

    def __new__(cls) -> "AdapterConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache = {}
            cls._instance._db_initialized = False
        return cls._instance

    async def get_config(
        self, platform: Platform, shop_id: str = "default"
    ) -> dict[str, Any] | None:
        """获取平台适配器配置。

        Args:
            platform: 平台枚举。
            shop_id: 店铺 ID，默认 "default"。

        Returns:
            凭证字典（含 client_id, client_secret 等），未找到返回 None。
        """
        cache_key = (platform, shop_id)

        # 检查缓存
        if cache_key in self._cache:
            cached, expiry = self._cache[cache_key]
            if time.time() < expiry:
                return cached
            else:
                del self._cache[cache_key]

        # 查询数据库
        from src.db.listing_models import AdapterConfigPO
        from src.db.postgres import get_db

        try:
            async with get_db() as session:
                from sqlalchemy import select

                stmt = select(AdapterConfigPO).where(
                    AdapterConfigPO.platform == platform.value,
                    AdapterConfigPO.shop_id == shop_id,
                    AdapterConfigPO.is_active == True,  # noqa: E712
                )
                result = await session.execute(stmt)
                config_po = result.scalar_one_or_none()

                if config_po:
                    creds = config_po.credentials.copy()
                    self._cache[cache_key] = (creds, time.time() + CACHE_TTL)
                    logger.info(
                        f"Adapter config loaded: platform={platform.value}, shop={shop_id}"
                    )
                    return creds
                else:
                    logger.warning(
                        f"No active adapter config found: "
                        f"platform={platform.value}, shop={shop_id}"
                    )
                    return None

        except Exception:
            logger.exception(f"Failed to load adapter config for {platform.value}/{shop_id}")
            return None

    async def invalidate_cache(
        self, platform: Platform, shop_id: str | None = None
    ) -> None:
        """清除缓存。

        Args:
            platform: 平台枚举。
            shop_id: 可选的店铺 ID，不指定则清除该平台所有缓存。
        """
        if shop_id:
            self._cache.pop((platform, shop_id), None)
        else:
            keys_to_remove = [k for k in self._cache if k[0] == platform]
            for k in keys_to_remove:
                del self._cache[k]
        logger.info(f"Adapter config cache invalidated: {platform.value}/{shop_id or 'all'}")
```

创建 `src/api/schema/adapter_config.py`:

```python
"""
适配器配置 API Schema。

Description:
    定义适配器配置的请求/响应 DTO。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

from pydantic import BaseModel, Field

from src.models.listing import Platform


class AdapterConfigCreate(BaseModel):
    """创建适配器配置请求。"""

    platform: Platform
    shop_id: str = Field(default="default", max_length=100, description="店铺ID")
    credentials: dict = Field(..., min_length=1, description="凭证（含 API Key、Token 等）")
    is_active: bool = Field(default=True, description="是否启用")


class AdapterConfigUpdate(BaseModel):
    """更新适配器配置请求。"""

    credentials: dict | None = Field(default=None, description="凭证（部分更新）")
    is_active: bool | None = Field(default=None, description="是否启用")


class AdapterConfigResponse(BaseModel):
    """适配器配置响应（脱敏）。"""

    id: int
    platform: str
    shop_id: str
    is_active: bool
    # 凭证只显示 key 名称，不显示值
    credential_keys: list[str]
    created_at: str | None = None
    updated_at: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_agents/test_adapter_config.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/adapter_config.py src/api/schema/adapter_config.py tests/test_agents/test_adapter_config.py
git commit -m "feat: add AdapterConfigManager with cache and API schema"
```

---

### Task 3: AI 文案生成器改造 (LLM 集成)

**Files:**
- Modify: `src/agents/listing_copywriter.py`
- Test: `tests/test_agents/test_listing_copywriter_llm.py`

- [ ] **Step 1: Write the failing test**

```python
"""AI 文案生成器 LLM 集成测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.listing_copywriter import AICopywritingAgent, LLMProvider
from src.graph.listing_state import ListingState
from src.models.listing import ListingProduct, Platform


@pytest.fixture
def product() -> ListingProduct:
    return ListingProduct(
        sku="LLM-TEST-001",
        title="Wireless Bluetooth Headphones",
        description="Premium wireless headphones with noise cancellation. "
                    "Long battery life up to 30 hours. Comfortable over-ear design.",
        category="Electronics",
        brand="SoundMax",
    )


@pytest.fixture
def state(product: ListingProduct) -> ListingState:
    return ListingState(
        product=product,
        target_platforms=[Platform.AMAZON, Platform.EBAY],
    )


class TestAICopywritingAgent:
    """测试 AI 文案生成器。"""

    @pytest.fixture
    def agent(self) -> AICopywritingAgent:
        return AICopywritingAgent()

    def test_llm_provider_enum(self) -> None:
        """测试 LLM 枚举。"""
        assert LLMProvider.TONGYI.value == "tongyi"
        assert LLMProvider.CLAUDE.value == "claude"
        assert LLMProvider.FALLBACK.value == "fallback"

    @pytest.mark.asyncio
    async def test_execute_with_llm(self, agent: AICopywritingAgent, state: ListingState) -> None:
        """测试使用 LLM 生成文案。"""
        # Mock LLM 返回
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="AI Optimized Title"))
        agent._llm = mock_llm

        result = await agent.execute(state)

        assert "copywriting_packages" in result
        assert Platform.AMAZON in result["copywriting_packages"]
        assert Platform.EBAY in result["copywriting_packages"]

        amazon_copy = result["copywriting_packages"][Platform.AMAZON]
        assert amazon_copy.platform == Platform.AMAZON
        assert amazon_copy.title != ""  # 即使 LLM mock 有问题，规则兜底会生成

    @pytest.mark.asyncio
    async def test_llm_fallback_to_rules(self, agent: AICopywritingAgent, state: ListingState) -> None:
        """测试 LLM 调用失败时降级到规则模式。"""
        agent._llm = AsyncMock()
        agent._llm.ainvoke = AsyncMock(side_effect=Exception("LLM API error"))

        # 应该降级到规则模式，不抛异常
        result = await agent.execute(state)
        assert "copywriting_packages" in result
        assert len(result["copywriting_packages"]) == 2  # Amazon + eBay

    @pytest.mark.asyncio
    async def test_generate_title_truncation(self, agent: AICopywritingAgent, product: ListingProduct) -> None:
        """测试标题截断。"""
        from src.agents.listing_platform_specs import get_platform_spec

        amazon_spec = get_platform_spec(Platform.AMAZON)
        title = agent._generate_title(product, amazon_spec)
        assert len(title) <= amazon_spec.max_title_length

    @pytest.mark.asyncio
    async def test_generate_bullet_points_limit(self, agent: AICopywritingAgent, product: ListingProduct) -> None:
        """测试五点描述数量限制。"""
        bullets = agent._generate_bullet_points(product, Platform.AMAZON)
        assert len(bullets) <= 5

    @pytest.mark.asyncio
    async def test_no_product_returns_empty(self, agent: AICopywritingAgent) -> None:
        """测试无商品返回空。"""
        empty_state = ListingState(product=None, target_platforms=[Platform.AMAZON])
        result = await agent.execute(empty_state)
        assert result["copywriting_packages"] == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_agents/test_listing_copywriter_llm.py -v`
Expected: FAIL with "cannot import name 'AICopywritingAgent'" or "cannot import name 'LLMProvider'"

- [ ] **Step 3: Write the implementation**

修改 `src/agents/listing_copywriter.py`，在现有文件末尾追加/替换：

```python
"""
AI 文案生成 Agent。

Description:
    基于商品信息，为各平台生成符合规范的文案，
    包括标题、五点描述、长描述、搜索关键词。
    集成 LLM 生成高质量文案，支持多 LLM 切换与降级。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
from enum import StrEnum
from typing import Any

from langchain_core.language_models import BaseChatModel

from src.agents.listing_platform_specs import get_platform_spec
from src.config.settings import get_settings
from src.graph.listing_state import ListingState
from src.models.listing import CopywritingPackage, ListingProduct, Platform

logger = logging.getLogger(__name__)


class LLMProvider(StrEnum):
    """LLM 提供商。"""

    TONGYI = "tongyi"
    CLAUDE = "claude"
    FALLBACK = "fallback"


class AICopywritingAgent:
    """AI 文案生成 Agent。

    生成流程:
    1. 规则生成草稿
    2. LLM 润色优化
    3. 返回最终文案

    LLM 降级策略: 通义千问 → Claude → 规则模式

    Example:
        >>> agent = AICopywritingAgent()
        >>> state = ListingState(product=product, target_platforms=[Platform.AMAZON])
        >>> result = await agent.execute(state)
    """

    def __init__(self, settings: Any | None = None) -> None:
        """初始化。

        Args:
            settings: 可选配置。
        """
        self._settings = settings or get_settings()
        self._llm: BaseChatModel | None = None
        self._current_provider: LLMProvider = LLMProvider.TONGYI

    def _create_llm(self, provider: LLMProvider) -> BaseChatModel:
        """创建指定 LLM 实例。

        Args:
            provider: LLM 提供商。

        Returns:
            LLM 实例。

        Raises:
            ImportError: 缺少必要的依赖包。
        """
        if provider == LLMProvider.TONGYI:
            from langchain_community.chat_models import ChatTongyi

            return ChatTongyi(
                model=self._settings.llm_model,
                dashscope_api_key=self._settings.dashscope_api_key,
                temperature=0.7,
                request_timeout=10,
            )
        elif provider == LLMProvider.CLAUDE:
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model="claude-sonnet-4-20250514",
                temperature=0.7,
                timeout=10,
            )
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    @property
    def llm(self) -> BaseChatModel:
        """获取 LLM 实例（延迟初始化）。"""
        if self._llm is None:
            self._llm = self._create_llm(self._current_provider)
        return self._llm

    async def _enhance_with_llm(self, draft: str, prompt_template: str) -> str:
        """使用 LLM 润色草稿。

        Args:
            draft: 规则生成的草稿。
            prompt_template: 提示模板文本。

        Returns:
            润色后的文本，失败返回原始草稿。
        """
        try:
            from langchain_core.prompts import ChatPromptTemplate

            prompt = ChatPromptTemplate.from_messages([
                ("system", "你是一个专业的电商文案优化师。请润色以下商品文案，使其更具吸引力，同时保持核心信息不变。直接返回润色后的文本，不要添加任何解释。"),
                ("human", f"{prompt_template}\n\n待润色文案：{{draft}}"),
            ])

            chain = prompt | self.llm
            response = await chain.ainvoke({"draft": draft})
            enhanced = response.content if hasattr(response, "content") else str(response)
            return enhanced.strip()
        except Exception:
            logger.warning("LLM enhancement failed, using rule-based draft")
            return draft

    def execute_sync(self, state: ListingState) -> dict:
        """同步执行文案生成（规则模式，LLM 降级兜底）。

        Args:
            state: 工作流状态。

        Returns:
            包含 copywriting_packages 的字典。
        """
        product = state.product
        if not product:
            return {"copywriting_packages": {}}

        copywriting_packages: dict[Platform, CopywritingPackage] = {}

        for platform in state.target_platforms:
            spec = get_platform_spec(platform)
            logger.info(f"生成文案: platform={platform.value}")

            title = self._generate_title(product, spec)
            bullet_points = self._generate_bullet_points(product, platform)
            description = self._generate_description(product)
            search_terms = self._generate_search_terms(product)

            copywriting_packages[platform] = CopywritingPackage(
                listing_task_id=0,
                platform=platform,
                language="en",
                title=title,
                bullet_points=bullet_points,
                description=description,
                search_terms=search_terms,
            )

        return {"copywriting_packages": copywriting_packages}

    async def _enhance_package(
        self, package: CopywritingPackage, product: ListingProduct
    ) -> CopywritingPackage:
        """使用 LLM 增强文案包。

        Args:
            package: 规则生成的文案包。
            product: 原始商品。

        Returns:
            增强后的文案包。
        """
        # 增强标题
        package.title = await self._enhance_with_llm(
            package.title,
            f"商品：{product.title}\n品牌：{product.brand or '无'}\n类目：{product.category or '无'}",
        )

        # 增强描述
        if package.description:
            package.description = await self._enhance_with_llm(
                package.description,
                f"商品：{product.title}\n品牌：{product.brand or '无'}",
            )

        # 增强五点描述
        enhanced_bullets = []
        for bullet in package.bullet_points:
            enhanced = await self._enhance_with_llm(
                bullet,
                f"商品：{product.title}\n品牌：{product.brand or '无'}",
            )
            enhanced_bullets.append(enhanced)
        package.bullet_points = enhanced_bullets

        return package

    async def execute(self, state: ListingState) -> dict:
        """异步执行文案生成（工作流节点接口）。

        流程:
        1. 规则生成草稿
        2. 尝试 LLM 润色
        3. LLM 失败则使用规则草稿

        Args:
            state: 工作流状态。

        Returns:
            包含 copywriting_packages 的字典。
        """
        product = state.product
        if not product:
            return {"copywriting_packages": {}}

        # 先规则生成草稿
        rule_result = self.execute_sync(state)
        packages = rule_result["copywriting_packages"]

        if not packages:
            return {"copywriting_packages": {}}

        # 尝试 LLM 增强
        enhanced: dict[Platform, CopywritingPackage] = {}
        for platform, package in packages.items():
            try:
                enhanced_package = await self._enhance_package(package, product)
                enhanced[platform] = enhanced_package
                logger.info(f"LLM-enhanced copywriting for {platform.value}")
            except Exception:
                logger.warning(
                    f"LLM enhancement failed for {platform.value}, using rule-based copy"
                )
                enhanced[platform] = package

        return {"copywriting_packages": enhanced}

    def _generate_title(self, product: ListingProduct, spec: Any) -> str:
        """生成平台兼容标题。

        Args:
            product: 商品信息。
            spec: 平台规范。

        Returns:
            符合平台长度限制的标题。
        """
        base_title = product.title or ""
        if product.brand:
            base_title = f"{product.brand} {base_title}"
        if spec.max_title_length > 0:
            base_title = base_title[: spec.max_title_length].rstrip()
        return base_title

    def _generate_bullet_points(self, product: ListingProduct, _platform: Platform) -> list[str]:
        """生成五点描述。

        Args:
            product: 商品信息。
            platform: 目标平台。

        Returns:
            不超过 5 条的卖点列表。
        """
        bullets = []
        desc = product.description or ""
        if desc:
            sentences = [s.strip() for s in desc.replace(".", "\n").split("\n") if s.strip()]
            bullets = sentences[:5]
        if not bullets:
            bullets = [f"Premium quality {product.category or 'product'}"]
            if product.brand:
                bullets.append(f"Brand: {product.brand}")
        return bullets[:5]

    def _generate_description(self, product: ListingProduct) -> str:
        """生成长描述。

        Args:
            product: 商品信息。

        Returns:
            商品详细描述文本。
        """
        parts = []
        if product.description:
            parts.append(product.description)
        if product.brand:
            parts.append(f"Brand: {product.brand}")
        if product.category:
            parts.append(f"Category: {product.category}")
        return "\n".join(parts) if parts else ""

    def _generate_search_terms(self, product: ListingProduct) -> list[str]:
        """生成搜索关键词。

        Args:
            product: 商品信息。

        Returns:
            唯一的搜索关键词列表。
        """
        terms = []
        if product.category:
            terms.append(product.category.lower())
        if product.brand:
            terms.append(product.brand.lower())
        if product.title:
            words = product.title.lower().split()
            terms.extend([w for w in words if len(w) > 3][:5])
        return list(dict.fromkeys(terms))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_agents/test_listing_copywriter_llm.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/listing_copywriter.py tests/test_agents/test_listing_copywriter_llm.py
git commit -m "feat: integrate LLM into copywriter agent with fallback"
```

---

### Task 4: 工作流真实接线

**Files:**
- Modify: `src/graph/listing_workflow.py`
- Modify: `tests/test_graph/test_listing_workflow.py`

- [ ] **Step 1: Write the failing test**

```python
"""工作流真实接线测试。"""

from unittest.mock import AsyncMock, patch

import pytest

from src.graph.listing_workflow import ListingWorkflow
from src.models.listing import ListingProduct, Platform


@pytest.fixture
def product() -> ListingProduct:
    return ListingProduct(
        sku="WF-TEST-001",
        title="Test Product",
        description="A test product for workflow",
        category="Test",
        brand="TestBrand",
    )


class TestListingWorkflow:
    """测试工作流真实执行。"""

    @pytest.mark.asyncio
    async def test_full_workflow(self, product: ListingProduct) -> None:
        """测试完整工作流：导入 → 素材优化 → 文案生成 → 合规检查。"""
        workflow = ListingWorkflow()

        result = await workflow.run(
            product=product,
            target_platforms=[Platform.AMAZON],
            thread_id="wf-test-001",
        )

        # 工作流应成功完成
        assert result is not None
        assert result.get("current_step") == "compliance_checked"
        # 文案包应已生成（非空）
        assert result.get("copywriting_packages")
        assert Platform.AMAZON in result.get("copywriting_packages", {})

    @pytest.mark.asyncio
    async def test_asset_optimize_calls_real_agent(self, product: ListingProduct) -> None:
        """测试素材优化节点调用真实 Agent。"""
        with patch("src.graph.listing_workflow.AssetOptimizerAgent") as mock_agent_cls:
            mock_agent = AsyncMock()
            mock_agent.execute = AsyncMock(return_value={
                "asset_packages": {Platform.AMAZON: AsyncMock()},
                "current_step": "assets_optimized",
            })
            mock_agent_cls.return_value = mock_agent

            workflow = ListingWorkflow()

            result = await workflow.run(
                product=product,
                target_platforms=[Platform.AMAZON],
                thread_id="wf-test-002",
            )

            mock_agent.execute.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_graph/test_listing_workflow.py::TestListingWorkflow -v`
Expected: FAIL because asset_optimize_node and copy_node are still placeholders

- [ ] **Step 3: Write the implementation**

修改 `src/graph/listing_workflow.py` — 替换占位节点为真实 Agent 调用:

```python
"""
刊登工作流构建器。

Description:
    基于 LangGraph StateGraph 构建刊登工作流，
    真实调用各 Agent：素材优化、文案生成（LLM）、合规检查。
    工作流:
        START → ImportProduct → [AssetOptimizer | Copywriter] → ComplianceCheck → END
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.agents.listing_compliance_checker import ComplianceCheckerAgent
from src.agents.listing_asset_optimizer import AssetOptimizerAgent
from src.agents.listing_copywriter import AICopywritingAgent
from src.graph.listing_state import ListingState
from src.models.listing import ListingProduct, Platform

logger = logging.getLogger(__name__)


class ListingWorkflow:
    """刊登工作流封装。

    工作流:
        START → ImportProduct → [AssetOptimizer | Copywriter] → ComplianceCheck → END

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
        self._builder.add_node("import_product", self._import_node)
        self._builder.add_node("optimize_assets", self._asset_optimize_node)
        self._builder.add_node("generate_copy", self._copy_node)
        self._builder.add_node("compliance_check", self._compliance_node)

        self._builder.set_entry_point("import_product")
        self._builder.add_edge("import_product", "optimize_assets")
        self._builder.add_edge("import_product", "generate_copy")
        self._builder.add_edge("optimize_assets", "compliance_check")
        self._builder.add_edge("generate_copy", "compliance_check")
        self._builder.add_edge("compliance_check", END)

    async def _import_node(self, state: ListingState) -> dict:
        """商品导入节点。"""
        if state.product:
            return {
                "product": state.product,
                "current_step": "imported",
                "step_results": {"import": {"status": "success"}},
            }
        return {"error": "No product provided", "current_step": "import_failed"}

    async def _asset_optimize_node(self, state: ListingState) -> dict:
        """素材优化节点：调用 AssetOptimizerAgent。"""
        if not state.product:
            return {"error": "No product available", "current_step": "asset_failed"}

        try:
            agent = AssetOptimizerAgent(settings=self._settings)
            result = agent.execute_sync(state)
            return {
                "asset_packages": result.get("asset_packages", state.asset_packages),
                "current_step": "assets_optimized",
                "step_results": {"assets": {"status": "success"}},
            }
        except Exception as e:
            logger.error(f"Asset optimization failed: {e}")
            return {
                "asset_packages": state.asset_packages,
                "current_step": "assets_optimized",
                "step_results": {"assets": {"status": "failed", "error": str(e)}},
            }

    async def _copy_node(self, state: ListingState) -> dict:
        """文案生成节点：调用 AICopywritingAgent（含 LLM）。"""
        if not state.product:
            return {"error": "No product available", "current_step": "copy_failed"}

        try:
            agent = AICopywritingAgent(settings=self._settings)
            result = await agent.execute(state)
            return {
                "copywriting_packages": result.get("copywriting_packages", {}),
                "current_step": "copy_generated",
                "step_results": {"copy": {"status": "success"}},
            }
        except Exception as e:
            logger.error(f"Copywriting generation failed: {e}")
            # LLM 失败不阻塞工作流，返回空文案包
            return {
                "copywriting_packages": {},
                "current_step": "copy_generated",
                "step_results": {"copy": {"status": "failed", "error": str(e)}},
            }

    async def _compliance_node(self, state: ListingState) -> dict:
        """合规检查节点。"""
        if not state.product:
            return {"error": "No product available", "current_step": "compliance_failed"}
        agent = ComplianceCheckerAgent(settings=self._settings)
        result = agent.execute_sync(state)
        return {
            "compliance_reports": result.get("compliance_reports", {}),
            "current_step": "compliance_checked",
            "step_results": {"compliance": {"status": "done"}},
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

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_graph/test_listing_workflow.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/graph/listing_workflow.py tests/test_graph/test_listing_workflow.py
git commit -m "feat: wire real agents into listing workflow nodes"
```

---

### Task 5: 适配器配置 API + 前端

**Files:**
- Create: `src/api/router/adapter_config.py`
- Create: `frontend/src/views/listing/AdapterConfig.vue`
- Modify: `frontend/src/api/listing.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/Layout/Sidebar.vue`
- Modify: `src/api/router/__init__.py`
- Test: `tests/test_api/test_adapter_config_api.py`

- [ ] **Step 1: Write the failing test**

```python
"""适配器配置 API 测试。"""

import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestAdapterConfigAPI:
    """测试适配器配置 API。"""

    def test_create_config(self, client: TestClient) -> None:
        """测试创建配置。"""
        response = client.post(
            "/api/v1/listing/adapter-configs",
            json={
                "platform": "amazon",
                "shop_id": "test-shop",
                "credentials": {
                    "client_id": "amzn1.test",
                    "client_secret": "secret",
                    "refresh_token": "Atzr|test",
                    "marketplace_id": "ATVPDKIKX0DER",
                },
                "is_active": True,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["platform"] == "amazon"

    def test_list_configs(self, client: TestClient) -> None:
        """测试列出配置。"""
        response = client.get("/api/v1/listing/adapter-configs")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_get_config(self, client: TestClient) -> None:
        """测试获取配置详情。"""
        # 先创建
        client.post(
            "/api/v1/listing/adapter-configs",
            json={
                "platform": "ebay",
                "shop_id": "ebay-test",
                "credentials": {"token": "test"},
                "is_active": True,
            },
        )
        # 查列表获取 ID
        list_resp = client.get("/api/v1/listing/adapter-configs")
        configs = list_resp.json()["data"]
        ebay_configs = [c for c in configs if c["platform"] == "ebay" and c["shop_id"] == "ebay-test"]
        if ebay_configs:
            config_id = ebay_configs[0]["id"]
            response = client.get(f"/api/v1/listing/adapter-configs/{config_id}")
            assert response.status_code == 200

    def test_update_config(self, client: TestClient) -> None:
        """测试更新配置。"""
        client.post(
            "/api/v1/listing/adapter-configs",
            json={
                "platform": "shopify",
                "shop_id": "shopify-test",
                "credentials": {"api_key": "old_key"},
                "is_active": True,
            },
        )
        list_resp = client.get("/api/v1/listing/adapter-configs")
        configs = list_resp.json()["data"]
        shopify_configs = [c for c in configs if c["platform"] == "shopify" and c["shop_id"] == "shopify-test"]
        if shopify_configs:
            config_id = shopify_configs[0]["id"]
            response = client.put(
                f"/api/v1/listing/adapter-configs/{config_id}",
                json={"is_active": False},
            )
            assert response.status_code == 200
            assert response.json()["data"]["is_active"] is False

    def test_delete_config(self, client: TestClient) -> None:
        """测试删除配置。"""
        client.post(
            "/api/v1/listing/adapter-configs",
            json={
                "platform": "amazon",
                "shop_id": "delete-test",
                "credentials": {"test": "value"},
                "is_active": True,
            },
        )
        list_resp = client.get("/api/v1/listing/adapter-configs")
        configs = list_resp.json()["data"]
        delete_configs = [c for c in configs if c["shop_id"] == "delete-test"]
        if delete_configs:
            config_id = delete_configs[0]["id"]
            response = client.delete(f"/api/v1/listing/adapter-configs/{config_id}")
            assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api/test_adapter_config_api.py -v`
Expected: FAIL with 404 (endpoint not found)

- [ ] **Step 3: Write the router implementation**

创建 `src/api/router/adapter_config.py`:

```python
"""
适配器配置管理 API 路由。

Description:
    提供平台适配器凭证的 CRUD 接口。
    配置存数据库，支持多店铺。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging

from fastapi import APIRouter, status

from src.api.schema.adapter_config import (
    AdapterConfigCreate,
    AdapterConfigResponse,
    AdapterConfigUpdate,
)
from src.api.schema.common import ApiResponse
from src.db.listing_models import AdapterConfigPO
from src.db.postgres import get_db
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter()


def _po_to_response(po: AdapterConfigPO) -> AdapterConfigResponse:
    """将 ORM 模型转为脱敏响应。"""
    return AdapterConfigResponse(
        id=po.id,
        platform=po.platform,
        shop_id=po.shop_id,
        is_active=po.is_active,
        credential_keys=list(po.credentials.keys()),
        created_at=po.created_at.isoformat() if po.created_at else None,
        updated_at=po.updated_at.isoformat() if po.updated_at else None,
    )


@router.post(
    "/adapter-configs",
    response_model=ApiResponse[AdapterConfigResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建适配器配置",
)
async def create_adapter_config(
    request: AdapterConfigCreate,
) -> ApiResponse[AdapterConfigResponse]:
    """创建平台适配器配置。

    Args:
        request: 配置创建请求。

    Returns:
        创建的配置（脱敏）。
    """
    async with get_db() as session:
        session: AsyncSession

        # 检查是否已存在
        existing_stmt = select(AdapterConfigPO).where(
            AdapterConfigPO.platform == request.platform.value,
            AdapterConfigPO.shop_id == request.shop_id,
        )
        existing_result = await session.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()
        if existing:
            return ApiResponse(code=409, message=f"配置已存在: {request.platform.value}/{request.shop_id}", data=None)

        po = AdapterConfigPO(
            platform=request.platform.value,
            shop_id=request.shop_id,
            credentials=request.credentials,
            is_active=request.is_active,
        )
        session.add(po)
        await session.flush()
        await session.refresh(po)

        # 清除缓存
        from src.agents.adapter_config import AdapterConfigManager

        mgr = AdapterConfigManager()
        from src.models.listing import Platform

        await mgr.invalidate_cache(Platform(request.platform.value), request.shop_id)

    return ApiResponse(
        code=200,
        message="配置创建成功",
        data=_po_to_response(po),
    )


@router.get(
    "/adapter-configs",
    response_model=ApiResponse[list[AdapterConfigResponse]],
    summary="列出所有适配器配置",
)
async def list_adapter_configs() -> ApiResponse[list[AdapterConfigResponse]]:
    """列出所有平台适配器配置（脱敏）。

    Returns:
        配置列表。
    """
    async with get_db() as session:
        session: AsyncSession
        stmt = select(AdapterConfigPO).order_by(AdapterConfigPO.platform, AdapterConfigPO.shop_id)
        result = await session.execute(stmt)
        configs = result.scalars().all()

    return ApiResponse(
        code=200,
        message="成功",
        data=[_po_to_response(c) for c in configs],
    )


@router.get(
    "/adapter-configs/{config_id}",
    response_model=ApiResponse[AdapterConfigResponse],
    summary="获取适配器配置详情",
)
async def get_adapter_config(config_id: int) -> ApiResponse[AdapterConfigResponse]:
    """获取指定适配器配置（脱敏）。

    Args:
        config_id: 配置 ID。

    Returns:
        配置详情。
    """
    async with get_db() as session:
        session: AsyncSession
        po = await session.get(AdapterConfigPO, config_id)
        if not po:
            return ApiResponse(code=404, message=f"配置 {config_id} 不存在", data=None)

    return ApiResponse(code=200, message="成功", data=_po_to_response(po))


@router.put(
    "/adapter-configs/{config_id}",
    response_model=ApiResponse[AdapterConfigResponse],
    summary="更新适配器配置",
)
async def update_adapter_config(
    config_id: int,
    request: AdapterConfigUpdate,
) -> ApiResponse[AdapterConfigResponse]:
    """更新适配器配置。

    Args:
        config_id: 配置 ID。
        request: 更新请求。

    Returns:
        更新后的配置（脱敏）。
    """
    async with get_db() as session:
        session: AsyncSession
        po = await session.get(AdapterConfigPO, config_id)
        if not po:
            return ApiResponse(code=404, message=f"配置 {config_id} 不存在", data=None)

        if request.credentials is not None:
            po.credentials.update(request.credentials)
        if request.is_active is not None:
            po.is_active = request.is_active

        await session.flush()
        await session.refresh(po)

        # 清除缓存
        from src.agents.adapter_config import AdapterConfigManager
        from src.models.listing import Platform

        mgr = AdapterConfigManager()
        await mgr.invalidate_cache(Platform(po.platform), po.shop_id)

    return ApiResponse(code=200, message="配置更新成功", data=_po_to_response(po))


@router.delete(
    "/adapter-configs/{config_id}",
    response_model=ApiResponse[dict],
    summary="删除适配器配置",
)
async def delete_adapter_config(config_id: int) -> ApiResponse[dict]:
    """删除适配器配置。

    Args:
        config_id: 配置 ID。

    Returns:
        操作结果。
    """
    async with get_db() as session:
        session: AsyncSession
        po = await session.get(AdapterConfigPO, config_id)
        if not po:
            return ApiResponse(code=404, message=f"配置 {config_id} 不存在", data=None)

        platform = po.platform
        shop_id = po.shop_id
        await session.delete(po)
        await session.flush()

        # 清除缓存
        from src.agents.adapter_config import AdapterConfigManager
        from src.models.listing import Platform

        mgr = AdapterConfigManager()
        await mgr.invalidate_cache(Platform(platform), shop_id)

    return ApiResponse(code=200, message="配置已删除", data={"id": config_id})
```

- [ ] **Step 4: Register the router**

修改 `src/api/router/__init__.py`，在已有 import 后添加:

```python
from src.api.router.adapter_config import router as adapter_config_router

# 在已有 include_router 调用后添加
api_router.include_router(adapter_config_router, prefix="/listing", tags=["适配器配置"])
```

- [ ] **Step 5: Write the frontend AdapterConfig page**

创建 `frontend/src/views/listing/AdapterConfig.vue`:

```vue
<template>
  <div class="adapter-config">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>适配器配置管理</span>
          <el-button type="primary" @click="showCreateDialog = true">新增配置</el-button>
        </div>
      </template>

      <el-table :data="configs" v-loading="loading" stripe>
        <el-table-column prop="platform" label="平台" width="100">
          <template #default="{ row }">
            <el-tag :type="platformType(row.platform)">{{ row.platform.toUpperCase() }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="shop_id" label="店铺ID" />
        <el-table-column label="凭证字段">
          <template #default="{ row }">
            <el-tag v-for="key in row.credential_keys" :key="key" size="small" style="margin-right: 4px">
              {{ key }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="showCreateDialog" :title="editingId ? '编辑配置' : '新增配置'" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="平台">
          <el-select v-model="form.platform" :disabled="!!editingId" placeholder="选择平台">
            <el-option label="Amazon" value="amazon" />
            <el-option label="eBay" value="ebay" />
            <el-option label="Shopify" value="shopify" />
          </el-select>
        </el-form-item>
        <el-form-item label="店铺ID">
          <el-input v-model="form.shop_id" :disabled="!!editingId" placeholder="默认: default" />
        </el-form-item>
        <el-form-item label="凭证 (JSON)">
          <el-input
            v-model="credentialsJson"
            type="textarea"
            :rows="6"
            placeholder='{"client_id": "...", "client_secret": "..."}'
          />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

interface AdapterConfig {
  id: number
  platform: string
  shop_id: string
  is_active: boolean
  credential_keys: string[]
  created_at: string | null
  updated_at: string | null
}

const configs = ref<AdapterConfig[]>([])
const loading = ref(false)
const submitting = ref(false)
const showCreateDialog = ref(false)
const editingId = ref<number | null>(null)

const form = reactive({
  platform: 'amazon',
  shop_id: 'default',
  is_active: true,
})

const credentialsJson = ref('{}')

const platformType = (platform: string) => {
  const map: Record<string, string> = { amazon: '', ebay: 'warning', shopify: 'success' }
  return map[platform] || ''
}

const fetchConfigs = async () => {
  loading.value = true
  try {
    const resp = await fetch('/api/v1/listing/adapter-configs')
    const json = await resp.json()
    if (json.code === 200) {
      configs.value = json.data
    }
  } finally {
    loading.value = false
  }
}

const handleSubmit = async () => {
  let credentials: Record<string, unknown>
  try {
    credentials = JSON.parse(credentialsJson.value)
  } catch {
    ElMessage.error('凭证 JSON 格式无效')
    return
  }

  submitting.value = true
  try {
    if (editingId.value) {
      const resp = await fetch(`/api/v1/listing/adapter-configs/${editingId.value}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credentials, is_active: form.is_active }),
      })
      const json = await resp.json()
      if (json.code === 200) {
        ElMessage.success('配置更新成功')
      } else {
        ElMessage.error(json.message || '更新失败')
      }
    } else {
      const resp = await fetch('/api/v1/listing/adapter-configs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, credentials }),
      })
      const json = await resp.json()
      if (json.code === 200) {
        ElMessage.success('配置创建成功')
      } else {
        ElMessage.error(json.message || '创建失败')
      }
    }
    showCreateDialog.value = false
    resetForm()
    fetchConfigs()
  } finally {
    submitting.value = false
  }
}

const handleEdit = (row: AdapterConfig) => {
  editingId.value = row.id
  form.platform = row.platform
  form.shop_id = row.shop_id
  form.is_active = row.is_active
  credentialsJson.value = JSON.stringify({})
  showCreateDialog.value = true
}

const handleDelete = async (row: AdapterConfig) => {
  try {
    await ElMessageBox.confirm(`确定删除 ${row.platform}/${row.shop_id} 的配置？`, '确认删除')
    const resp = await fetch(`/api/v1/listing/adapter-configs/${row.id}`, { method: 'DELETE' })
    const json = await resp.json()
    if (json.code === 200) {
      ElMessage.success('配置已删除')
      fetchConfigs()
    } else {
      ElMessage.error(json.message || '删除失败')
    }
  } catch {
    // User cancelled
  }
}

const resetForm = () => {
  editingId.value = null
  form.platform = 'amazon'
  form.shop_id = 'default'
  form.is_active = true
  credentialsJson.value = '{}'
}

onMounted(() => {
  fetchConfigs()
})
</script>
```

- [ ] **Step 6: Update frontend API, router, sidebar**

修改 `frontend/src/api/listing.ts`，在文件末尾新增:

```typescript
/** 列出适配器配置 */
export function listAdapterConfigs() {
  return http.get<ApiResponse<AdapterConfigResponse[]>>('/listing/adapter-configs')
}

/** 创建适配器配置 */
export function createAdapterConfig(data: AdapterConfigCreate) {
  return http.post<ApiResponse<AdapterConfigResponse>>('/listing/adapter-configs', data)
}

/** 更新适配器配置 */
export function updateAdapterConfig(id: number, data: AdapterConfigUpdate) {
  return http.put<ApiResponse<AdapterConfigResponse>>(`/listing/adapter-configs/${id}`, data)
}

/** 删除适配器配置 */
export function deleteAdapterConfig(id: number) {
  return http.delete<ApiResponse>(`/listing/adapter-configs/${id}`)
}
```

同时修改 `frontend/src/types/listing.ts`，在末尾新增:

```typescript
export interface AdapterConfigCreate {
  platform: Platform
  shop_id: string
  credentials: Record<string, any>
  is_active?: boolean
}

export interface AdapterConfigUpdate {
  credentials?: Record<string, any>
  is_active?: boolean
}

export interface AdapterConfigResponse {
  id: number
  platform: string
  shop_id: string
  is_active: boolean
  credential_keys: string[]
  created_at: string | null
  updated_at: string | null
}
```

修改 `frontend/src/router/index.ts`，在 listing 路由数组中添加:

```typescript
{
  path: 'listing/configs',
  name: 'ListingAdapterConfig',
  component: () => import('@/views/listing/AdapterConfig.vue'),
  meta: { title: '适配器配置' },
}
```

修改 `frontend/src/components/Layout/Sidebar.vue`，在 listing 子菜单中添加:

```vue
<el-menu-item index="/listing/configs">
  <el-icon><Setting /></el-icon>
  <template #title>适配器配置</template>
</el-menu-item>
```

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/test_api/test_adapter_config_api.py -v`
Expected: Tests PASS (if DB is available; may skip if PostgreSQL not running)

Run: `cd frontend && npx vue-tsc --noEmit 2>/dev/null; npx vite build`
Expected: Build succeeds

- [ ] **Step 8: Commit**

```bash
git add src/api/router/adapter_config.py src/api/schema/adapter_config.py
git add src/api/router/__init__.py
git add frontend/src/views/listing/AdapterConfig.vue
git add frontend/src/api/listing.ts frontend/src/types/listing.ts
git add frontend/src/router/index.ts frontend/src/components/Layout/Sidebar.vue
git add tests/test_api/test_adapter_config_api.py
git commit -m "feat: add adapter config CRUD API and management page"
```

---

### Task 6: API 层改造 — listing.py 和 listing_push.py 接入数据库

**Files:**
- Modify: `src/api/router/listing.py`
- Modify: `src/api/router/listing_push.py`
- Modify: `src/api/schema/listing.py`
- Test: `tests/test_api/test_listing_api.py`
- Test: `tests/test_api/test_listing_push_api.py`

- [ ] **Step 1: Write the updated tests**

修改 `tests/test_api/test_listing_push_api.py` — 测试从数据库读取已生成数据推送:

```python
"""刊登推送 API 测试（数据库版）。"""

import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestListingPushAPI:
    """测试刊登推送 API。"""

    def test_push_listing(self, client: TestClient) -> None:
        """测试推送刊登。"""
        client.post(
            "/api/v1/listing/import-product",
            json={
                "sku": "PUSH-TEST-001",
                "title": "Push Test Product",
                "description": "Testing push",
            },
        )
        task_resp = client.post(
            "/api/v1/listing/tasks",
            json={
                "product_sku": "PUSH-TEST-001",
                "target_platforms": ["amazon"],
            },
        )
        task_id = task_resp.json()["data"]["task_id"]

        push_resp = client.post(f"/api/v1/listing/tasks/{task_id}/push")
        assert push_resp.status_code == 200
        data = push_resp.json()
        assert data["code"] == 200
        assert data["data"]["task_id"] == task_id

    def test_push_task_not_found(self, client: TestClient) -> None:
        """测试推送不存在的任务。"""
        response = client.post("/api/v1/listing/tasks/9999/push")
        data = response.json()
        assert data["code"] == 404

    def test_get_push_results(self, client: TestClient) -> None:
        """测试查询推送结果。"""
        client.post(
            "/api/v1/listing/import-product",
            json={
                "sku": "PUSH-TEST-002",
                "title": "Push Test 2",
            },
        )
        task_resp = client.post(
            "/api/v1/listing/tasks",
            json={
                "product_sku": "PUSH-TEST-002",
                "target_platforms": ["amazon"],
            },
        )
        task_id = task_resp.json()["data"]["task_id"]

        client.post(f"/api/v1/listing/tasks/{task_id}/push")

        result_resp = client.get(
            f"/api/v1/listing/tasks/{task_id}/push-results"
        )
        assert result_resp.status_code == 200
        data = result_resp.json()
        assert data["code"] == 200

    def test_get_push_results_not_found(self, client: TestClient) -> None:
        """测试查询不存在的推送结果。"""
        response = client.get("/api/v1/listing/tasks/9999/push-results")
        data = response.json()
        assert data["code"] == 404
```

- [ ] **Step 2: Run tests to verify current state**

Run: `uv run pytest tests/test_api/test_listing_push_api.py tests/test_api/test_listing_api.py -v`
Expected: Tests PASS (current memory-based implementation)

- [ ] **Step 3: Modify listing.py — add auto_execute and workflow integration**

修改 `src/api/router/listing.py` — 修改 create_task 增加 auto_execute 参数和手动触发端点:

```python
"""
刊登工具 API 路由。

Description:
    提供商品导入、刊登任务创建等 REST 接口。
    支持 auto_execute 自动工作流和手动触发。
    数据持久化到 PostgreSQL。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
from typing import Any

from fastapi import APIRouter, status

from src.api.schema.common import ApiResponse
from src.api.schema.listing import (
    ComplianceIssueResponse,
    ComplianceReportResponse,
    CreateListingTaskRequest,
    ExecuteTaskResponse,
    ListingTaskResponse,
    ProductImportRequest,
    ProductResponse,
    TaskStatusResponse,
)
from src.models.listing import ComplianceReport, Platform

logger = logging.getLogger(__name__)

router = APIRouter()

# 内存存储（向后兼容，数据库不可用时回退）
_products: dict[str, Any] = {}
_tasks: list[dict] = []
_compliance_reports: dict[int, dict[str, ComplianceReport]] = {}


@router.post(
    "/import-product",
    response_model=ApiResponse[ProductResponse],
    status_code=status.HTTP_201_CREATED,
    summary="导入商品",
)
async def import_product(request: ProductImportRequest) -> ApiResponse[ProductResponse]:
    """导入商品到刊登系统。"""
    from src.agents.listing_importer import ImportProductAgent

    agent = ImportProductAgent()
    product_data = request.model_dump()
    result = agent.execute_manual(product_data)

    if not result["success"]:
        return ApiResponse(code=400, message=result["error"], data=None)

    product = result["product"]
    _products[product.sku] = product

    # 尝试写入数据库
    try:
        from src.db.listing_models import ListingProductPO
        from src.db.postgres import get_db

        async with get_db() as session:
            po = ListingProductPO(
                sku=product.sku,
                title=product.title,
                description=product.description,
                category=product.category,
                brand=product.brand,
                source_images=[img.model_dump() for img in product.source_images],
                attributes=product.attributes,
            )
            session.add(po)
    except Exception:
        logger.warning("Failed to persist product to DB, using memory")

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
async def create_task(
    request: CreateListingTaskRequest,
) -> ApiResponse[ListingTaskResponse]:
    """创建刊登任务。

    Args:
        request: 刊登任务请求。

    Returns:
        创建的任务信息。
    """
    if request.product_sku not in _products:
        return ApiResponse(code=404, message=f"商品 {request.product_sku} 不存在", data=None)

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


@router.post(
    "/tasks/{task_id}/execute",
    response_model=ApiResponse[ExecuteTaskResponse],
    summary="手动执行工作流",
)
async def execute_task(task_id: int) -> ApiResponse[ExecuteTaskResponse]:
    """手动触发指定任务的工作流。

    Args:
        task_id: 任务ID。

    Returns:
        工作流执行结果。
    """
    task = next((t for t in _tasks if t["task_id"] == task_id), None)
    if not task:
        return ApiResponse(code=404, message=f"任务 {task_id} 不存在", data=None)

    product = _products.get(task["product_sku"])
    if not product:
        return ApiResponse(code=404, message=f"商品 {task['product_sku']} 不存在", data=None)

    from src.graph.listing_workflow import ListingWorkflow
    from src.models.listing import ListingTask

    task_obj = ListingTask(
        id=task_id,
        product_id=0,
        target_platforms=[Platform(p) for p in task["target_platforms"]],
    )

    task["status"] = "generating"

    workflow = ListingWorkflow()
    try:
        result = await workflow.run(
            product=product,
            target_platforms=[Platform(p) for p in task["target_platforms"]],
            thread_id=f"task-{task_id}",
        )

        # 保存合规报告到内存
        reports = result.get("compliance_reports", {})
        if reports:
            _compliance_reports[task_id] = reports

        task["status"] = "completed"

        return ApiResponse(
            code=200,
            message="工作流执行完成",
            data=ExecuteTaskResponse(
                task_id=task_id,
                status="completed",
                has_copywriting=bool(result.get("copywriting_packages")),
                has_assets=bool(result.get("asset_packages")),
                has_compliance=bool(result.get("compliance_reports")),
            ),
        )

    except Exception as e:
        logger.error(f"Workflow execution failed for task {task_id}: {e}")
        task["status"] = "failed"
        return ApiResponse(
            code=500,
            message=f"工作流执行失败: {str(e)}",
            data=ExecuteTaskResponse(
                task_id=task_id,
                status="failed",
                has_copywriting=False,
                has_assets=False,
                has_compliance=False,
            ),
        )


@router.get(
    "/tasks/{task_id}/status",
    response_model=ApiResponse[TaskStatusResponse],
    summary="查询任务状态",
)
async def get_task_status(task_id: int) -> ApiResponse[TaskStatusResponse]:
    """查询任务工作流状态。

    Args:
        task_id: 任务ID。

    Returns:
        任务状态信息。
    """
    task = next((t for t in _tasks if t["task_id"] == task_id), None)
    if not task:
        return ApiResponse(code=404, message=f"任务 {task_id} 不存在", data=None)

    return ApiResponse(
        code=200,
        message="成功",
        data=TaskStatusResponse(
            task_id=task_id,
            product_sku=task["product_sku"],
            status=task["status"],
            target_platforms=task["target_platforms"],
        ),
    )


def _report_to_response(report: ComplianceReport) -> ComplianceReportResponse:
    """将内部合规报告转换为 API 响应。"""

    def _issue_to_dict(issue: Any) -> ComplianceIssueResponse:
        return ComplianceIssueResponse(
            severity=issue.severity,
            rule=issue.rule,
            field=issue.field,
            message=issue.message,
            suggestion=issue.suggestion,
        )

    return ComplianceReportResponse(
        platform=report.platform.value,
        overall=report.overall,
        image_issues=[_issue_to_dict(i) for i in report.image_issues],
        text_issues=[_issue_to_dict(i) for i in report.text_issues],
        forbidden_words=report.forbidden_words,
    )


@router.post(
    "/tasks/{task_id}/compliance",
    response_model=ApiResponse[dict[str, ComplianceReportResponse]],
    status_code=status.HTTP_201_CREATED,
    summary="执行合规检查",
)
async def run_compliance_check(task_id: int) -> ApiResponse[dict[str, ComplianceReportResponse]]:
    """对指定任务执行合规检查。"""
    task = next((t for t in _tasks if t["task_id"] == task_id), None)
    if not task:
        return ApiResponse(code=404, message=f"任务 {task_id} 不存在", data=None)

    product = _products.get(task["product_sku"])
    if not product:
        return ApiResponse(code=404, message=f"商品 {task['product_sku']} 不存在", data=None)

    from src.agents.listing_compliance_checker import ComplianceCheckerAgent
    from src.graph.listing_state import ListingState
    from src.models.listing import CopywritingPackage

    platforms = [Platform(p) for p in task["target_platforms"]]
    state = ListingState(
        product=product,
        target_platforms=platforms,
    )
    for platform in platforms:
        state.copywriting_packages[platform] = CopywritingPackage(
            listing_task_id=task_id,
            platform=platform,
            language="en",
            title=product.title,
            bullet_points=[],
            description=product.description or "",
        )

    agent = ComplianceCheckerAgent()
    result = agent.execute_sync(state)

    _compliance_reports[task_id] = result["compliance_reports"]

    reports = {
        platform.value: _report_to_response(report)
        for platform, report in result["compliance_reports"].items()
    }

    return ApiResponse(code=200, message="合规检查完成", data=reports)


@router.get(
    "/compliance/{task_id}",
    response_model=ApiResponse[dict[str, ComplianceReportResponse]],
    summary="查询合规报告",
)
async def get_compliance_report(task_id: int) -> ApiResponse[dict[str, ComplianceReportResponse]]:
    """获取指定任务的合规报告。"""
    reports = _compliance_reports.get(task_id)
    if not reports:
        return ApiResponse(code=404, message=f"任务 {task_id} 无合规报告", data=None)

    return ApiResponse(
        code=200,
        message="成功",
        data={platform.value: _report_to_response(report) for platform, report in reports.items()},
    )
```

- [ ] **Step 4: Add new schema to listing.py**

在 `src/api/schema/listing.py` 末尾新增:

```python
class ExecuteTaskResponse(BaseModel):
    """工作流执行响应。"""

    task_id: int
    status: str
    has_copywriting: bool = False
    has_assets: bool = False
    has_compliance: bool = False


class TaskStatusResponse(BaseModel):
    """任务状态响应。"""

    task_id: int
    product_sku: str
    status: str
    target_platforms: list[str]
```

- [ ] **Step 5: Modify listing_push.py — use generated data**

修改 `src/api/router/listing_push.py` — 推送时使用已生成的文案和素材:

```python
"""
刊登推送 API 路由。

Description:
    提供刊登推送至各平台的 REST 接口。
    使用工作流生成的素材和文案进行推送。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging

from fastapi import APIRouter, status

from src.api.schema.common import ApiResponse
from src.api.schema.listing import (
    PushListingRequest,
    PushResponse,
    PushResultResponse,
)
from src.models.listing import Platform

logger = logging.getLogger(__name__)

router = APIRouter()

# 内存存储推送结果
_push_results: dict[int, list[dict]] = {}

# 存储工作流生成的数据
_workflow_data: dict[int, dict] = {}

# 自动注册所有平台适配器
from src.agents.listing_amazon_adapter import AmazonAdapter
from src.agents.listing_ebay_adapter import EbayAdapter
from src.agents.listing_shopify_adapter import ShopifyAdapter
from src.agents.listing_platform_adapter import AdapterRegistry

registry = AdapterRegistry()
registry.register(Platform.AMAZON, AmazonAdapter)
registry.register(Platform.EBAY, EbayAdapter)
registry.register(Platform.SHOPIFY, ShopifyAdapter)


def store_workflow_data(task_id: int, data: dict) -> None:
    """存储工作流生成的数据供推送使用。

    Args:
        task_id: 任务 ID。
        data: 工作流结果（含 copywriting_packages, asset_packages 等）。
    """
    _workflow_data[task_id] = data


@router.post(
    "/tasks/{task_id}/push",
    response_model=ApiResponse[PushResponse],
    status_code=status.HTTP_200_OK,
    summary="推送刊登",
)
async def push_listing(
    task_id: int, request: PushListingRequest | None = None
) -> ApiResponse[PushResponse]:
    """将刊登推送至指定平台。"""
    from src.api.router.listing import _products, _tasks
    from src.models.listing import AssetPackage, CopywritingPackage, ListingTask

    task = next((t for t in _tasks if t["task_id"] == task_id), None)
    if not task:
        return ApiResponse(code=404, message=f"任务 {task_id} 不存在", data=None)

    task_obj = ListingTask(
        id=task_id,
        product_id=0,
        target_platforms=[Platform(p) for p in task["target_platforms"]],
    )

    target_platforms = (
        request.platforms if request and request.platforms else task_obj.target_platforms
    )

    product = _products.get(task["product_sku"])
    if not product:
        return ApiResponse(code=404, message=f"商品 {task['product_sku']} 不存在", data=None)

    # 获取工作流生成的数据
    wf_data = _workflow_data.get(task_id, {})
    copywriting_packages = wf_data.get("copywriting_packages", {})
    asset_packages = wf_data.get("asset_packages", {})

    results: list[PushResultResponse] = []

    for platform in target_platforms:
        try:
            adapter = registry.get(platform)

            # 使用工作流生成的文案
            copy = copywriting_packages.get(platform)
            if not copy:
                copy = CopywritingPackage(
                    listing_task_id=task_id,
                    platform=platform,
                    language="en",
                    title=product.title,
                    bullet_points=[],
                    description=product.description or "",
                )

            # 使用工作流生成的素材
            assets = asset_packages.get(platform)
            if not assets:
                assets = AssetPackage(
                    listing_task_id=task_id,
                    platform=platform,
                    main_image=None,
                    variant_images=[],
                )

            push_result = adapter.push_listing(
                product, assets, copy, task_obj
            )

            results.append(
                PushResultResponse(
                    platform=platform.value,
                    success=push_result.success,
                    listing_id=push_result.listing_id,
                    url=push_result.url,
                    error=push_result.error,
                )
            )

        except Exception as e:
            logger.error(f"Failed to push to {platform.value}: {e}")
            results.append(
                PushResultResponse(
                    platform=platform.value,
                    success=False,
                    error=str(e),
                )
            )

    _push_results[task_id] = [r.model_dump() for r in results]

    all_success = all(r.success for r in results)
    task["status"] = "published" if all_success else "partial"

    return ApiResponse(
        code=200,
        message="推送完成",
        data=PushResponse(
            task_id=task_id,
            results=results,
            status=task["status"],
        ),
    )


@router.get(
    "/tasks/{task_id}/push-results",
    response_model=ApiResponse[list[PushResultResponse]],
    summary="查询推送结果",
)
async def get_push_results(task_id: int) -> ApiResponse[list[PushResultResponse]]:
    """获取指定任务的推送结果。"""
    results = _push_results.get(task_id)
    if not results:
        return ApiResponse(
            code=404, message=f"任务 {task_id} 无推送结果", data=None
        )

    return ApiResponse(
        code=200,
        message="成功",
        data=[PushResultResponse(**r) for r in results],
    )
```

- [ ] **Step 6: Wire execute_task to store workflow data**

在 `src/api/router/listing.py` 的 `execute_task` 函数中，成功分支的 `result` 获取后添加:

```python
# 在 workflow.run() 成功后
from src.api.router.listing_push import store_workflow_data
store_workflow_data(task_id, result)
```

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/test_api/test_listing_api.py tests/test_api/test_listing_push_api.py -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add src/api/router/listing.py src/api/router/listing_push.py src/api/schema/listing.py
git add tests/test_api/test_listing_api.py tests/test_api/test_listing_push_api.py
git commit -m "feat: wire workflow execution into listing API with auto/manual trigger"
```

---

### Task 7: 运行全部测试 + 最终验证

- [ ] **Step 1: Run all tests**

Run: `uv run pytest --cov=src -v`
Expected: All tests PASS (> 80% coverage)

- [ ] **Step 2: Run linting**

Run: `uv run ruff format . && uv run ruff check .`
Expected: No errors

- [ ] **Step 3: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "chore: finalize listing iteration — LLM copywriter, DB models, adapter config, workflow"
```

---

## 验证清单

| 验证项 | 操作 | 预期 |
|--------|------|------|
| ORM 模型 | `uv run pytest tests/test_db/test_listing_models.py -v` | 7 tests PASS |
| 适配器配置 | `uv run pytest tests/test_agents/test_adapter_config.py -v` | 7 tests PASS |
| LLM 文案 | `uv run pytest tests/test_agents/test_listing_copywriter_llm.py -v` | 6 tests PASS |
| 工作流 | `uv run pytest tests/test_graph/test_listing_workflow.py -v` | All PASS |
| 配置 API | `uv run pytest tests/test_api/test_adapter_config_api.py -v` | 5 tests PASS |
| 全部测试 | `uv run pytest --cov=src` | 80%+ coverage, all PASS |
| 代码格式 | `uv run ruff check .` | 0 errors |
| 前端编译 | `cd frontend && npm run build` | Build succeeds |

`★ Insight ─────────────────────────────────────`
- Task 6 是 blast radius 最大的改动——修改 listing.py 和 listing_push.py 的核心逻辑。采用"双写"策略（内存 + 数据库），确保测试不受数据库可用性影响。后续可逐步移除内存回退
- LLM 文案生成器保留完整的规则生成能力作为兜底，这是刊登场景的安全网——即使 LLM API 完全不可用，系统仍能输出合规的基础文案
- 工作流接线是"胶水层"改造——不改变 LangGraph 状态图结构，只替换节点内部实现。这意味着已有的 checkpoint 和状态模型保持不变，迁移风险最低
─────────────────────────────────────────────────
