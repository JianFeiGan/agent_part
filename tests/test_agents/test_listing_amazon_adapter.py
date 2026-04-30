"""
Amazon SP-API 刊登适配器测试。

Description:
    测试 Amazon 适配器的认证、素材转换、文案转换、刊登推送等功能。
    使用 unittest.mock 模拟 HTTP 请求。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from src.agents.listing_amazon_adapter import AmazonAdapter
from src.models.listing import (
    AssetPackage,
    CopywritingPackage,
    ImageRef,
    ListingProduct,
    ListingTask,
    Platform,
    TaskStatus,
)


@pytest.fixture
def adapter() -> AmazonAdapter:
    """创建 Amazon 适配器实例。"""
    return AmazonAdapter(
        config={
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "refresh_token": "test_refresh_token",
            "marketplace_id": "ATVPDKIKX0DER",
        }
    )


@pytest.fixture
def product() -> ListingProduct:
    """创建测试用商品。"""
    return ListingProduct(
        sku="TEST-SKU-001",
        title="Test Product Title",
        description="Test product description",
        category="Electronics",
        brand="TestBrand",
        price=Decimal("29.99"),
        source_images=[
            ImageRef(url="https://example.com/img1.jpg", is_main=True),
            ImageRef(url="https://example.com/img2.jpg"),
        ],
    )


@pytest.fixture
def asset_package() -> AssetPackage:
    """创建测试用素材包。"""
    return AssetPackage(
        listing_task_id=1,
        platform=Platform.AMAZON,
        main_image="https://cdn.example.com/main.jpg",
        variant_images=[
            "https://cdn.example.com/var1.jpg",
            "https://cdn.example.com/var2.jpg",
        ],
    )


@pytest.fixture
def copywriting() -> CopywritingPackage:
    """创建测试用文案包。"""
    return CopywritingPackage(
        listing_task_id=1,
        platform=Platform.AMAZON,
        language="en",
        title="Test Optimized Title",
        bullet_points=[
            "High quality material",
            "Easy to use",
            "Durable construction",
            "Compact design",
            "Great value",
        ],
        description="Detailed product description here.",
        search_terms=["wireless", "bluetooth", "headphones"],
    )


class TestAuthenticate:
    """AmazonAdapter 认证测试。"""

    def test_authenticate_returns_token(self, adapter: AmazonAdapter) -> None:
        """测试认证成功返回访问令牌。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "test_token_123"}

        with patch("src.agents.listing_amazon_adapter.requests.post", return_value=mock_response):
            token = adapter.authenticate()

            assert token == "test_token_123"
            assert adapter._auth_token == "test_token_123"

    def test_authenticate_failure(self, adapter: AmazonAdapter) -> None:
        """测试认证失败抛出异常。"""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"error": "invalid_grant"}'

        with patch("src.agents.listing_amazon_adapter.requests.post", return_value=mock_response):
            with pytest.raises(RuntimeError, match="LWA authentication failed"):
                adapter.authenticate()


class TestTransformAssets:
    """AmazonAdapter 素材转换测试。"""

    def test_transform_assets_format(
        self,
        adapter: AmazonAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
    ) -> None:
        """测试素材转换输出格式正确。"""
        result = adapter.transform_assets(product, asset_package)

        assert "images" in result
        assert isinstance(result["images"], list)
        # 应包含主图和变体图
        assert len(result["images"]) == 3
        assert result["images"][0] == "https://cdn.example.com/main.jpg"

    def test_transform_assets_empty_main_image(
        self,
        adapter: AmazonAdapter,
        product: ListingProduct,
    ) -> None:
        """测试主图为空时只返回变体图。"""
        empty_asset = AssetPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            main_image=None,
            variant_images=["https://cdn.example.com/v1.jpg"],
        )
        result = adapter.transform_assets(product, empty_asset)

        assert "images" in result
        assert len(result["images"]) == 1


class TestTransformCopywriting:
    """AmazonAdapter 文案转换测试。"""

    def test_transform_copywriting_format(
        self,
        adapter: AmazonAdapter,
        copywriting: CopywritingPackage,
    ) -> None:
        """测试文案转换输出包含所有必需字段。"""
        result = adapter.transform_copywriting(copywriting)

        assert "title" in result
        assert "bullet_points" in result
        assert "description" in result
        assert "search_terms" in result

    def test_transform_copywriting_truncates_title(
        self,
        adapter: AmazonAdapter,
    ) -> None:
        """测试标题截断到 200 字符。"""
        long_title = "A" * 300
        long_copywriting = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            title=long_title,
        )
        result = adapter.transform_copywriting(long_copywriting)

        assert len(result["title"]) == 200

    def test_transform_copywriting_limits_bullet_points(
        self,
        adapter: AmazonAdapter,
    ) -> None:
        """测试 bullet points 限制到 5 条。"""
        many_bullets = [f"Bullet {i}" for i in range(10)]
        copy = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            bullet_points=many_bullets,
        )
        result = adapter.transform_copywriting(copy)

        assert len(result["bullet_points"]) == 5

    def test_transform_copywriting_limits_search_terms_bytes(
        self,
        adapter: AmazonAdapter,
    ) -> None:
        """测试搜索词总字节数限制到 249。"""
        # 每个字符大约 1 字节 (ASCII)
        long_terms = ["a" * 100, "b" * 100, "c" * 100]
        copy = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            search_terms=long_terms,
        )
        result = adapter.transform_copywriting(copy)

        total_bytes = sum(len(t.encode("utf-8")) for t in result["search_terms"])
        assert total_bytes <= 249


class TestPushListing:
    """AmazonAdapter 刊登推送测试。"""

    def test_push_listing_success(
        self,
        adapter: AmazonAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> None:
        """测试刊登推送成功。"""
        # Mock authenticate
        adapter._auth_token = "test_token"

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"listingId": "B0ABCD1234"}

        with patch("src.agents.listing_amazon_adapter.requests.post", return_value=mock_response):
            task = ListingTask(
                product_id=1,
                target_platforms=[Platform.AMAZON],
                status=TaskStatus.PUSHING,
            )
            result = adapter.push_listing(product, asset_package, copywriting, task)

            assert result.success is True
            assert result.listing_id == "B0ABCD1234"
            assert result.platform == Platform.AMAZON

    def test_push_listing_failure(
        self,
        adapter: AmazonAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> None:
        """测试刊登推送失败返回 PushResult(success=False)。"""
        adapter._auth_token = "test_token"

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"errors": ["Invalid SKU"]}'
        mock_response.json.return_value = {"errors": ["Invalid SKU"]}

        with patch("src.agents.listing_amazon_adapter.requests.post", return_value=mock_response):
            task = ListingTask(
                product_id=1,
                target_platforms=[Platform.AMAZON],
                status=TaskStatus.PUSHING,
            )
            result = adapter.push_listing(product, asset_package, copywriting, task)

            assert result.success is False
            assert result.error is not None
            assert "400" in result.error


class TestUpdateListing:
    """AmazonAdapter 刊登更新测试。"""

    def test_update_listing(
        self,
        adapter: AmazonAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> None:
        """测试刊登更新成功。"""
        adapter._auth_token = "test_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ACCEPTED"}

        with patch("src.agents.listing_amazon_adapter.requests.put", return_value=mock_response):
            result = adapter.update_listing("B0EXIST123", product, asset_package, copywriting)

            assert result.success is True
            assert result.listing_id == "B0EXIST123"


class TestDeleteListing:
    """AmazonAdapter 刊登删除测试。"""

    def test_delete_listing(self, adapter: AmazonAdapter) -> None:
        """测试刊登删除成功。"""
        adapter._auth_token = "test_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        with patch("src.agents.listing_amazon_adapter.requests.delete", return_value=mock_response):
            result = adapter.delete_listing("B0DELETE456")

            assert result.success is True
            assert result.listing_id == "B0DELETE456"

    def test_delete_listing_no_content(self, adapter: AmazonAdapter) -> None:
        """测试删除返回 204 No Content 也视为成功。"""
        adapter._auth_token = "test_token"

        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.text = ""
        mock_response.json.side_effect = Exception("No content")

        with patch("src.agents.listing_amazon_adapter.requests.delete", return_value=mock_response):
            result = adapter.delete_listing("B0DELETE789")

            assert result.success is True
            assert result.listing_id == "B0DELETE789"
