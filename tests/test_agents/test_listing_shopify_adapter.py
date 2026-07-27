"""
Shopify GraphQL 刊登适配器测试。

Description:
    测试 ShopifyAdapter 的 GraphQL 请求、错误处理、健康检查等功能。
    使用 unittest.mock 模拟 HTTP 请求，不依赖真实 API。
@author ganjianfei
@version 2.0.0
2026-07-14
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.agents.listing_platform_adapter import PushConfig
from src.agents.listing_shopify_adapter import ShopifyAdapter
from src.models.listing import (
    AssetPackage,
    CopywritingPackage,
    ImageRef,
    ListingProduct,
    ListingTask,
    Platform,
)


@pytest.fixture
def push_config() -> PushConfig:
    """创建测试用推送配置。"""
    return PushConfig(max_retries=2, retry_base_delay=0.01, rate_limit_rpm=0)


@pytest.fixture
def config() -> dict:
    """创建 Shopify 平台配置。"""
    return {
        "shop_url": "https://test-store.myshopify.com",
        "api_key": "shpat_test_api_key_12345",
        "api_version": "2024-01",
    }


@pytest.fixture
def adapter(config: dict, push_config: PushConfig) -> ShopifyAdapter:
    """创建 Shopify 适配器实例。"""
    return ShopifyAdapter(config=config, push_config=push_config)


@pytest.fixture
def product() -> ListingProduct:
    """创建测试商品。"""
    return ListingProduct(
        sku="TEST-SKU-001",
        title="Wireless Bluetooth Headphones with Noise Cancellation",
        description="High-quality wireless headphones with active noise cancellation",
        category="Electronics",
        brand="SoundMax",
        price=Decimal("49.99"),
        source_images=[
            ImageRef(url="https://example.com/main.jpg", is_main=True),
            ImageRef(url="https://example.com/variant1.jpg", is_main=False),
        ],
    )


@pytest.fixture
def asset_package() -> AssetPackage:
    """创建测试素材包。"""
    return AssetPackage(
        listing_task_id=1,
        platform=Platform.SHOPIFY,
        main_image="https://cdn.example.com/main_1000x1000.jpg",
        variant_images=[
            "https://cdn.example.com/variant_1.jpg",
            "https://cdn.example.com/variant_2.jpg",
        ],
    )


@pytest.fixture
def copywriting() -> CopywritingPackage:
    """创建测试文案包。"""
    return CopywritingPackage(
        listing_task_id=1,
        platform=Platform.SHOPIFY,
        title="Wireless Bluetooth Headphones with Active Noise Cancellation",
        bullet_points=[
            "Premium sound quality with deep bass",
            "Up to 30 hours battery life",
            "Comfortable over-ear design",
        ],
        description="Experience premium audio with our wireless headphones",
        search_terms=["wireless", "bluetooth", "headphones", "noise cancelling"],
    )


@pytest.fixture
def task() -> ListingTask:
    """创建测试刊登任务。"""
    return ListingTask(
        product_id=1,
        target_platforms=[Platform.SHOPIFY],
    )


def _make_httpx_response(
    status_code: int = 200,
    json_data: dict | None = None,
    text: str = "",
    headers: dict | None = None,
) -> httpx.Response:
    """创建模拟的 httpx.Response。"""
    request = MagicMock(spec=httpx.Request)
    request.method = "POST"
    request.url = httpx.URL("https://example.com")
    if json_data is not None:
        return httpx.Response(
            status_code=status_code,
            json=json_data,
            headers=headers or {},
            request=request,
        )
    return httpx.Response(
        status_code=status_code,
        text=text,
        headers=headers or {},
        request=request,
    )


SUCCESS_GRAPHQL_RESPONSE = {
    "data": {
        "productCreate": {
            "product": {
                "id": "gid://shopify/Product/123456789",
                "title": "Test Product",
                "handle": "test-product",
            },
            "userErrors": [],
        }
    }
}

ERROR_GRAPHQL_RESPONSE = {
    "data": {
        "productCreate": {
            "product": None,
            "userErrors": [{"field": ["title"], "message": "Title is too long"}],
        }
    }
}


class TestShopifyAdapterGraphQL:
    """ShopifyAdapter GraphQL 请求测试。"""

    @pytest.mark.asyncio
    async def test_graphql_success(
        self,
        adapter: ShopifyAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        task: ListingTask,
    ) -> None:
        """测试 GraphQL 请求成功。"""
        adapter._auth_token = "shpat_test_token"

        mock_response = _make_httpx_response(
            status_code=200,
            json_data=SUCCESS_GRAPHQL_RESPONSE,
        )

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await adapter.push_listing(product, asset_package, copywriting, task)

            assert result.success is True
            assert result.platform == Platform.SHOPIFY
            assert result.listing_id == "gid://shopify/Product/123456789"
            assert result.url is not None
            assert "test-product" in result.url

    @pytest.mark.asyncio
    async def test_graphql_user_errors(
        self,
        adapter: ShopifyAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        task: ListingTask,
    ) -> None:
        """测试 GraphQL 返回 userErrors 时抛出 PermanentPushError。"""
        adapter._auth_token = "shpat_test_token"

        mock_response = _make_httpx_response(
            status_code=200,
            json_data=ERROR_GRAPHQL_RESPONSE,
        )

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await adapter.push_listing(product, asset_package, copywriting, task)

            assert result.success is False
            assert result.error_code == "PERMANENT_ERROR"
            assert "Title is too long" in result.error

    @pytest.mark.asyncio
    async def test_graphql_throttled(
        self,
        adapter: ShopifyAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        task: ListingTask,
    ) -> None:
        """测试 GraphQL 429 限流，重试耗尽后返回失败结果。"""
        adapter._auth_token = "shpat_test_token"

        mock_response = _make_httpx_response(
            status_code=429,
            text="Throttled",
        )

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await adapter.push_listing(product, asset_package, copywriting, task)

            assert result.success is False
            assert result.error_code == "RETRY_EXHAUSTED"


class TestShopifyAdapterHealthCheck:
    """ShopifyAdapter 健康检查测试。"""

    @pytest.mark.asyncio
    async def test_health_check_success(self, adapter: ShopifyAdapter) -> None:
        """测试健康检查成功。"""
        adapter._auth_token = "shpat_test_token"

        mock_response = _make_httpx_response(
            status_code=200,
            json_data={"data": {"shop": {"name": "Test Store"}}},
        )

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await adapter.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, adapter: ShopifyAdapter) -> None:
        """测试健康检查失败。"""
        adapter._auth_token = "shpat_test_token"

        mock_response = _make_httpx_response(
            status_code=401,
            text="Unauthorized",
        )

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await adapter.health_check()

            assert result is False
