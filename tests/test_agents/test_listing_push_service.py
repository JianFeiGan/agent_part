"""
统一刊登推送服务测试。

Description:
    测试 ListingPushService 的多平台并行推送、失败重试、并发控制等功能。
    使用 unittest.mock 模拟适配器，不依赖真实 API。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.listing_platform_adapter import AdapterRegistry, PushResult
from src.agents.listing_push_service import ListingPushService
from src.models.listing import (
    AssetPackage,
    CopywritingPackage,
    ListingProduct,
    ListingTask,
    Platform,
    TaskStatus,
)


@pytest.fixture
def product() -> ListingProduct:
    """创建测试用商品。"""
    return ListingProduct(
        sku="TEST-SKU-001",
        title="Test Product",
        description="Test description",
        category="Electronics",
        brand="TestBrand",
        price=Decimal("29.99"),
    )


@pytest.fixture
def asset_packages() -> dict[Platform, AssetPackage]:
    """创建各平台素材包。"""
    return {
        Platform.AMAZON: AssetPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            main_image="https://cdn.example.com/main.jpg",
        ),
        Platform.SHOPIFY: AssetPackage(
            listing_task_id=1,
            platform=Platform.SHOPIFY,
            main_image="https://cdn.example.com/main.jpg",
        ),
    }


@pytest.fixture
def copywriting_packages() -> dict[Platform, CopywritingPackage]:
    """创建各平台文案包。"""
    return {
        Platform.AMAZON: CopywritingPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            title="Amazon Title",
            description="Amazon description",
        ),
        Platform.SHOPIFY: CopywritingPackage(
            listing_task_id=1,
            platform=Platform.SHOPIFY,
            title="Shopify Title",
            description="Shopify description",
        ),
    }


def _create_mock_adapter(platform: Platform, success: bool = True) -> MagicMock:
    """创建模拟适配器。"""
    adapter = MagicMock()
    adapter.push_listing = AsyncMock(
        return_value=PushResult(
            success=success,
            platform=platform,
            listing_id=f"listing-{platform.value}" if success else None,
            error=None if success else f"Push to {platform.value} failed",
            error_code=None if success else "RETRY_EXHAUSTED",
        )
    )
    return adapter


class TestPushToMultiplePlatforms:
    """多平台并行推送测试。"""

    @pytest.mark.asyncio
    async def test_push_to_multiple_platforms(
        self,
        product: ListingProduct,
        asset_packages: dict[Platform, AssetPackage],
        copywriting_packages: dict[Platform, CopywritingPackage],
    ) -> None:
        """测试并行推送到多个平台。"""
        mock_amazon = _create_mock_adapter(Platform.AMAZON, success=True)
        mock_shopify = _create_mock_adapter(Platform.SHOPIFY, success=True)

        registry = AdapterRegistry()
        # 清除单例中的旧实例
        registry._instances = {}
        registry._adapters = {}

        # 注册模拟适配器类
        mock_amazon_cls = MagicMock(return_value=mock_amazon)
        mock_shopify_cls = MagicMock(return_value=mock_shopify)
        registry.register(Platform.AMAZON, mock_amazon_cls)
        registry.register(Platform.SHOPIFY, mock_shopify_cls)

        service = ListingPushService(registry=registry)
        task = ListingTask(
            product_id=1,
            target_platforms=[Platform.AMAZON, Platform.SHOPIFY],
            status=TaskStatus.PUSHING,
        )

        results = await service.push_to_platforms(
            product=product,
            asset_packages=asset_packages,
            copywriting_packages=copywriting_packages,
            task=task,
        )

        assert len(results) == 2
        assert results["amazon"].success is True
        assert results["shopify"].success is True

    @pytest.mark.asyncio
    async def test_push_partial_failure(
        self,
        product: ListingProduct,
        asset_packages: dict[Platform, AssetPackage],
        copywriting_packages: dict[Platform, CopywritingPackage],
    ) -> None:
        """测试部分平台推送失败。"""
        mock_amazon = _create_mock_adapter(Platform.AMAZON, success=True)
        mock_shopify = _create_mock_adapter(Platform.SHOPIFY, success=False)

        registry = AdapterRegistry()
        registry._instances = {}
        registry._adapters = {}

        mock_amazon_cls = MagicMock(return_value=mock_amazon)
        mock_shopify_cls = MagicMock(return_value=mock_shopify)
        registry.register(Platform.AMAZON, mock_amazon_cls)
        registry.register(Platform.SHOPIFY, mock_shopify_cls)

        service = ListingPushService(registry=registry)
        task = ListingTask(
            product_id=1,
            target_platforms=[Platform.AMAZON, Platform.SHOPIFY],
            status=TaskStatus.PUSHING,
        )

        results = await service.push_to_platforms(
            product=product,
            asset_packages=asset_packages,
            copywriting_packages=copywriting_packages,
            task=task,
        )

        assert results["amazon"].success is True
        assert results["shopify"].success is False


class TestRetryFailed:
    """失败重试测试。"""

    @pytest.mark.asyncio
    async def test_retry_failed(
        self,
        product: ListingProduct,
        asset_packages: dict[Platform, AssetPackage],
        copywriting_packages: dict[Platform, CopywritingPackage],
    ) -> None:
        """测试重试非 PERMANENT 错误的平台。"""
        previous_results = {
            "amazon": PushResult(
                success=True,
                platform=Platform.AMAZON,
                listing_id="listing-amazon",
            ),
            "shopify": PushResult(
                success=False,
                platform=Platform.SHOPIFY,
                error="Rate limited",
                error_code="RETRY_EXHAUSTED",
            ),
        }

        # 重试时 Shopify 成功
        mock_shopify = _create_mock_adapter(Platform.SHOPIFY, success=True)

        registry = AdapterRegistry()
        registry._instances = {}
        registry._adapters = {}

        mock_shopify_cls = MagicMock(return_value=mock_shopify)
        registry.register(Platform.SHOPIFY, mock_shopify_cls)

        service = ListingPushService(registry=registry)
        task = ListingTask(
            product_id=1,
            target_platforms=[Platform.AMAZON, Platform.SHOPIFY],
            status=TaskStatus.PUSHING,
        )

        merged = await service.retry_failed(
            product=product,
            asset_packages=asset_packages,
            copywriting_packages=copywriting_packages,
            task=task,
            previous_results=previous_results,
        )

        # Amazon 保持成功，Shopify 重试后成功
        assert merged["amazon"].success is True
        assert merged["shopify"].success is True

    @pytest.mark.asyncio
    async def test_retry_skips_permanent_errors(
        self,
        product: ListingProduct,
        asset_packages: dict[Platform, AssetPackage],
        copywriting_packages: dict[Platform, CopywritingPackage],
    ) -> None:
        """测试 PERMANENT_ERROR 不被重试。"""
        previous_results = {
            "amazon": PushResult(
                success=False,
                platform=Platform.AMAZON,
                error="Auth failed",
                error_code="PERMANENT_ERROR",
            ),
        }

        registry = AdapterRegistry()
        registry._instances = {}
        registry._adapters = {}

        service = ListingPushService(registry=registry)
        task = ListingTask(
            product_id=1,
            target_platforms=[Platform.AMAZON],
            status=TaskStatus.PUSHING,
        )

        merged = await service.retry_failed(
            product=product,
            asset_packages=asset_packages,
            copywriting_packages=copywriting_packages,
            task=task,
            previous_results=previous_results,
        )

        # PERMANENT_ERROR 不重试，结果不变
        assert merged["amazon"].success is False
        assert merged["amazon"].error_code == "PERMANENT_ERROR"


class TestMaxConcurrent:
    """并发控制测试。"""

    @pytest.mark.asyncio
    async def test_max_concurrent(
        self,
        product: ListingProduct,
        asset_packages: dict[Platform, AssetPackage],
        copywriting_packages: dict[Platform, CopywritingPackage],
    ) -> None:
        """测试并发数限制。"""
        call_times: list[float] = []

        async def _slow_push(*args, **kwargs):
            call_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.05)
            return PushResult(success=True, platform=Platform.AMAZON, listing_id="test")

        mock_adapter = MagicMock()
        mock_adapter.push_listing = _slow_push

        registry = AdapterRegistry()
        registry._instances = {}
        registry._adapters = {}

        mock_cls = MagicMock(return_value=mock_adapter)
        registry.register(Platform.AMAZON, mock_cls)

        # 最大并发为 1
        service = ListingPushService(registry=registry, max_concurrent=1)
        task = ListingTask(
            product_id=1,
            target_platforms=[Platform.AMAZON],
            status=TaskStatus.PUSHING,
        )

        results = await service.push_to_platforms(
            product=product,
            asset_packages=asset_packages,
            copywriting_packages=copywriting_packages,
            task=task,
        )

        assert results["amazon"].success is True
