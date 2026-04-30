"""
Shopify GraphQL 刊登适配器测试。

Description:
    测试 ShopifyAdapter 的认证、素材转换、文案转换、刊登推送/更新/删除功能。
    使用 unittest.mock 模拟 HTTP 请求。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.agents.listing_platform_adapter import PushResult
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
def config() -> dict:
    """创建 Shopify 平台配置。"""
    return {
        "shop_url": "https://test-store.myshopify.com",
        "api_key": "shpat_test_api_key_12345",
        "api_version": "2024-01",
    }


@pytest.fixture
def adapter(config: dict) -> ShopifyAdapter:
    """创建 Shopify 适配器实例。"""
    return ShopifyAdapter(config=config)


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


class TestShopifyAdapterAuthenticate:
    """ShopifyAdapter 认证测试。"""

    def test_authenticate_returns_api_key(self, adapter: ShopifyAdapter) -> None:
        """测试认证成功返回 API Key。"""
        token = adapter.authenticate()

        assert token == "shpat_test_api_key_12345"
        assert adapter._auth_token == "shpat_test_api_key_12345"

    def test_authenticate_missing_key_raises(self) -> None:
        """测试缺少 api_key 时抛出 RuntimeError。"""
        adapter = ShopifyAdapter(config={})
        with pytest.raises(RuntimeError, match="api_key is not configured"):
            adapter.authenticate()


class TestShopifyAdapterTransformCopywriting:
    """ShopifyAdapter 文案转换测试。"""

    def test_transform_copywriting_format(
        self, adapter: ShopifyAdapter, copywriting: CopywritingPackage
    ) -> None:
        """测试文案返回 title 和 body_html 键。"""
        result = adapter.transform_copywriting(copywriting)

        assert "title" in result
        assert "body_html" in result
        assert result["title"] == copywriting.title

    def test_transform_copywriting_body_contains_features(
        self, adapter: ShopifyAdapter, copywriting: CopywritingPackage
    ) -> None:
        """测试 body_html 包含 Features section。"""
        result = adapter.transform_copywriting(copywriting)

        assert "<h3>Features</h3>" in result["body_html"]
        assert "<ul>" in result["body_html"]
        assert "<li>" in result["body_html"]
        for bp in copywriting.bullet_points:
            assert bp in result["body_html"]

    def test_transform_copywriting_empty_bullets(self, adapter: ShopifyAdapter) -> None:
        """测试空 bullet points 不包含 Features section。"""
        copy = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.SHOPIFY,
            title="Test",
            bullet_points=[],
            description="Test description",
        )
        result = adapter.transform_copywriting(copy)
        assert "<h3>Features</h3>" not in result["body_html"]
        assert result["body_html"] == "Test description"


class TestShopifyAdapterTransformAssets:
    """ShopifyAdapter 素材转换测试。"""

    def test_transform_assets_format(
        self,
        adapter: ShopifyAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
    ) -> None:
        """测试素材返回 "images" 键。"""
        result = adapter.transform_assets(product, asset_package)

        assert "images" in result
        assert isinstance(result["images"], list)

    def test_transform_assets_includes_main_image(
        self,
        adapter: ShopifyAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
    ) -> None:
        """测试素材包含主图。"""
        result = adapter.transform_assets(product, asset_package)

        assert any(img["src"] == asset_package.main_image for img in result["images"])

    def test_transform_assets_includes_variant_images(
        self,
        adapter: ShopifyAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
    ) -> None:
        """测试素材包含变体图。"""
        result = adapter.transform_assets(product, asset_package)

        urls = {img["src"] for img in result["images"]}
        for variant in asset_package.variant_images:
            assert variant in urls

    def test_transform_assets_empty(self, adapter: ShopifyAdapter, product: ListingProduct) -> None:
        """测试空素材包返回空 images 列表。"""
        empty_pkg = AssetPackage(
            listing_task_id=1,
            platform=Platform.SHOPIFY,
            main_image=None,
            variant_images=[],
        )
        result = adapter.transform_assets(product, empty_pkg)
        assert result["images"] == []


class TestShopifyAdapterPushListing:
    """ShopifyAdapter 刊登推送测试。"""

    def test_graphql_url(self, adapter: ShopifyAdapter) -> None:
        """测试 GraphQL URL 包含 shop_url 和 graphql。"""
        url = adapter.graphql_url

        assert "test-store.myshopify.com" in url
        assert "graphql" in url

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

    def test_push_listing_success(
        self,
        adapter: ShopifyAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        task: ListingTask,
    ) -> None:
        """测试刊登推送成功。"""
        adapter._auth_token = "shpat_test_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.SUCCESS_GRAPHQL_RESPONSE

        with patch("src.agents.listing_shopify_adapter.requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = adapter.push_listing(product, asset_package, copywriting, task)

        assert result.success is True
        assert result.platform == Platform.SHOPIFY
        assert result.listing_id == "gid://shopify/Product/123456789"
        assert result.url is not None
        assert "test-product" in result.url

    def test_push_listing_with_errors(
        self,
        adapter: ShopifyAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        task: ListingTask,
    ) -> None:
        """测试刊登推送返回 userErrors 时 success=False。"""
        adapter._auth_token = "shpat_test_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.ERROR_GRAPHQL_RESPONSE

        with patch("src.agents.listing_shopify_adapter.requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = adapter.push_listing(product, asset_package, copywriting, task)

        assert result.success is False
        assert result.platform == Platform.SHOPIFY
        assert "Title is too long" in result.error

    def test_push_listing_http_error(
        self,
        adapter: ShopifyAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        task: ListingTask,
    ) -> None:
        """测试 HTTP 错误时返回失败 PushResult。"""
        adapter._auth_token = "shpat_test_token"

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("src.agents.listing_shopify_adapter.requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = adapter.push_listing(product, asset_package, copywriting, task)

        assert result.success is False
        assert "error" in result.error.lower()


class TestShopifyAdapterUpdateListing:
    """ShopifyAdapter 刊登更新测试。"""

    SUCCESS_UPDATE_RESPONSE = {
        "data": {
            "productUpdate": {
                "product": {
                    "id": "gid://shopify/Product/987654321",
                    "title": "Updated Product",
                },
                "userErrors": [],
            }
        }
    }

    def test_update_listing(
        self,
        adapter: ShopifyAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> None:
        """测试刊登更新成功。"""
        adapter._auth_token = "shpat_test_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.SUCCESS_UPDATE_RESPONSE

        with patch("src.agents.listing_shopify_adapter.requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = adapter.update_listing(
                "gid://shopify/Product/987654321",
                product,
                asset_package,
                copywriting,
            )

        assert result.success is True
        assert result.platform == Platform.SHOPIFY
        assert result.listing_id == "gid://shopify/Product/987654321"

    def test_update_listing_with_errors(
        self,
        adapter: ShopifyAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> None:
        """测试刊登更新失败。"""
        adapter._auth_token = "shpat_test_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "productUpdate": {
                    "product": None,
                    "userErrors": [{"field": ["id"], "message": "Product not found"}],
                }
            }
        }

        with patch("src.agents.listing_shopify_adapter.requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = adapter.update_listing(
                "gid://shopify/Product/nonexistent",
                product,
                asset_package,
                copywriting,
            )

        assert result.success is False
        assert "Product not found" in result.error


class TestShopifyAdapterDeleteListing:
    """ShopifyAdapter 刊登删除测试。"""

    SUCCESS_DELETE_RESPONSE = {
        "data": {
            "productDelete": {
                "deletedProductId": "gid://shopify/Product/123456789",
                "userErrors": [],
            }
        }
    }

    def test_delete_listing(self, adapter: ShopifyAdapter) -> None:
        """测试刊登删除成功。"""
        adapter._auth_token = "shpat_test_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.SUCCESS_DELETE_RESPONSE

        with patch("src.agents.listing_shopify_adapter.requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = adapter.delete_listing("gid://shopify/Product/123456789")

        assert result.success is True
        assert result.platform == Platform.SHOPIFY
        assert result.listing_id == "gid://shopify/Product/123456789"

    def test_delete_listing_with_errors(self, adapter: ShopifyAdapter) -> None:
        """测试刊登删除失败。"""
        adapter._auth_token = "shpat_test_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "productDelete": {
                    "deletedProductId": None,
                    "userErrors": [{"field": ["id"], "message": "Product not found"}],
                }
            }
        }

        with patch("src.agents.listing_shopify_adapter.requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = adapter.delete_listing("gid://shopify/Product/nonexistent")

        assert result.success is False
        assert "Product not found" in result.error


class TestShopifyAdapterHelpers:
    """ShopifyAdapter 辅助方法测试。"""

    def test_generate_handle_basic(self, adapter: ShopifyAdapter) -> None:
        """测试 handle 生成：空格转连字符。"""
        product = ListingProduct(sku="SKU", title="My Cool Product")
        handle = adapter._generate_handle(product)
        assert handle == "my-cool-product"

    def test_generate_handle_special_chars(self, adapter: ShopifyAdapter) -> None:
        """测试 handle 生成：移除特殊字符。"""
        product = ListingProduct(sku="SKU", title="Product <with> special & chars!")
        handle = adapter._generate_handle(product)
        assert handle == "product-with-special-chars"

    def test_generate_handle_empty_title(self, adapter: ShopifyAdapter) -> None:
        """测试空标题生成默认 handle。"""
        product = ListingProduct(sku="SKU", title="   ")
        handle = adapter._generate_handle(product)
        assert handle == "product"

    def test_escape_html(self, adapter: ShopifyAdapter) -> None:
        """测试 HTML 转义。"""
        assert adapter._escape_html("<script>") == "&lt;script&gt;"
        assert adapter._escape_html("A & B") == "A &amp; B"
        assert adapter._escape_html("") == ""
