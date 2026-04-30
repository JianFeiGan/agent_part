"""
eBay Trading API 刊登适配器测试。

Description:
    测试 EbayAdapter 的认证、素材转换、文案转换、刊登推送/更新/删除功能。
    使用 unittest.mock 模拟 HTTP 请求。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.agents.listing_ebay_adapter import EbayAdapter
from src.agents.listing_platform_adapter import PushResult
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
    """创建 eBay 平台配置。"""
    return {
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "refresh_token": "test_refresh_token",
        "site_id": "0",
    }


@pytest.fixture
def adapter(config: dict) -> EbayAdapter:
    """创建 eBay 适配器实例。"""
    return EbayAdapter(config=config)


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
        platform=Platform.EBAY,
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
        platform=Platform.EBAY,
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
        target_platforms=[Platform.EBAY],
    )


class TestEbayAdapterAuthenticate:
    """EbayAdapter 认证测试。"""

    def test_authenticate_returns_token(self, adapter: EbayAdapter) -> None:
        """测试认证成功返回访问令牌。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test_access_token_123",
            "token_type": "Bearer",
            "expires_in": 7200,
        }

        with patch("src.agents.listing_ebay_adapter.requests.post") as mock_post:
            mock_post.return_value = mock_response
            token = adapter.authenticate()

        assert token == "test_access_token_123"
        assert adapter._auth_token == "test_access_token_123"
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args.kwargs["data"]["grant_type"] == "refresh_token"

    def test_authenticate_failure_raises(self, adapter: EbayAdapter) -> None:
        """测试认证失败抛出 RuntimeError。"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = '{"error": "invalid_grant"}'

        with patch("src.agents.listing_ebay_adapter.requests.post") as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises(RuntimeError, match="authentication failed"):
                adapter.authenticate()


class TestEbayAdapterTransformCopywriting:
    """EbayAdapter 文案转换测试。"""

    def test_transform_copywriting_truncates_title(
        self, adapter: EbayAdapter, copywriting: CopywritingPackage
    ) -> None:
        """测试标题截断到 80 字符。"""
        result = adapter.transform_copywriting(copywriting)

        assert len(result["title"]) <= 80
        assert result["title"] == copywriting.title[:80]

    def test_transform_copywriting_wraps_bullets_in_html(
        self, adapter: EbayAdapter, copywriting: CopywritingPackage
    ) -> None:
        """测试 bullet points 包装为 HTML 列表。"""
        result = adapter.transform_copywriting(copywriting)

        assert "<ul>" in result["bullet_points_html"]
        assert "<li>" in result["bullet_points_html"]
        assert "</ul>" in result["bullet_points_html"]
        for bp in copywriting.bullet_points:
            assert f"<li>{bp}</li>" in result["bullet_points_html"]

    def test_transform_copywriting_empty_bullets(self, adapter: EbayAdapter) -> None:
        """测试空 bullet points 返回空字符串。"""
        copy = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.EBAY,
            title="Test",
            bullet_points=[],
            description="Test description",
        )
        result = adapter.transform_copywriting(copy)
        assert result["bullet_points_html"] == ""

    def test_transform_copywriting_title_shorter_than_limit(self, adapter: EbayAdapter) -> None:
        """测试短标题不被截断。"""
        copy = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.EBAY,
            title="Short Title",
            description="Desc",
        )
        result = adapter.transform_copywriting(copy)
        assert result["title"] == "Short Title"


class TestEbayAdapterTransformAssets:
    """EbayAdapter 素材转换测试。"""

    def test_transform_assets_format(
        self,
        adapter: EbayAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
    ) -> None:
        """测试素材返回 "pictures" 键。"""
        result = adapter.transform_assets(product, asset_package)

        assert "pictures" in result
        assert isinstance(result["pictures"], list)

    def test_transform_assets_includes_main_image(
        self,
        adapter: EbayAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
    ) -> None:
        """测试素材包含主图。"""
        result = adapter.transform_assets(product, asset_package)

        assert asset_package.main_image in result["pictures"]

    def test_transform_assets_includes_variant_images(
        self,
        adapter: EbayAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
    ) -> None:
        """测试素材包含变体图。"""
        result = adapter.transform_assets(product, asset_package)

        for variant in asset_package.variant_images:
            assert variant in result["pictures"]

    def test_transform_assets_limits_to_12(
        self, adapter: EbayAdapter, product: ListingProduct
    ) -> None:
        """测试素材最多返回 12 张图片。"""
        many_variants = AssetPackage(
            listing_task_id=1,
            platform=Platform.EBAY,
            main_image="https://cdn.example.com/main.jpg",
            variant_images=[f"https://cdn.example.com/v{i}.jpg" for i in range(20)],
        )
        result = adapter.transform_assets(product, many_variants)
        assert len(result["pictures"]) == 12


class TestEbayAdapterPushListing:
    """EbayAdapter 刊登推送测试。"""

    SUCCESS_XML_RESPONSE = """<?xml version="1.0" encoding="utf-8"?>
<AddItemResponse xmlns="urn:ebay:apis:eBLBaseComponents">
  <Timestamp>2026-04-25T00:00:00.000Z</Timestamp>
  <Ack>Success</Ack>
  <Version>967</Version>
  <Build>E967_CORE_API_12345</Build>
  <ItemID>123456789</ItemID>
  <Fees></Fees>
</AddItemResponse>"""

    FAILURE_XML_RESPONSE = """<?xml version="1.0" encoding="utf-8"?>
<AddItemResponse xmlns="urn:ebay:apis:eBLBaseComponents">
  <Timestamp>2026-04-25T00:00:00.000Z</Timestamp>
  <Ack>Failure</Ack>
  <Version>967</Version>
  <Errors>
    <Error>
      <ShortMessage>Invalid category</ShortMessage>
      <LongMessage>The category ID is not valid.</LongMessage>
      <ErrorCode>10001</ErrorCode>
    </Error>
  </Errors>
</AddItemResponse>"""

    def test_push_listing_success(
        self,
        adapter: EbayAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        task: ListingTask,
    ) -> None:
        """测试刊登推送成功。"""
        adapter._auth_token = "test_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = self.SUCCESS_XML_RESPONSE

        with patch("src.agents.listing_ebay_adapter.requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = adapter.push_listing(product, asset_package, copywriting, task)

        assert result.success is True
        assert result.platform == Platform.EBAY
        assert result.listing_id == "123456789"
        assert result.url == "https://www.ebay.com/itm/123456789"

    def test_push_listing_failure(
        self,
        adapter: EbayAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        task: ListingTask,
    ) -> None:
        """测试刊登推送失败。"""
        adapter._auth_token = "test_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = self.FAILURE_XML_RESPONSE

        with patch("src.agents.listing_ebay_adapter.requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = adapter.push_listing(product, asset_package, copywriting, task)

        assert result.success is False
        assert result.platform == Platform.EBAY
        assert "Invalid category" in result.error

    def test_push_listing_triggers_auth_if_needed(
        self,
        adapter: EbayAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        task: ListingTask,
    ) -> None:
        """测试未认证时自动触发认证。"""
        mock_token_response = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            "access_token": "auto_token",
        }

        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.text = self.SUCCESS_XML_RESPONSE

        with patch("src.agents.listing_ebay_adapter.requests.post") as mock_post:
            mock_post.side_effect = [mock_token_response, mock_api_response]
            result = adapter.push_listing(product, asset_package, copywriting, task)

        assert mock_post.call_count == 2
        assert result.success is True


class TestEbayAdapterUpdateListing:
    """EbayAdapter 刊登更新测试。"""

    SUCCESS_XML_RESPONSE = """<?xml version="1.0" encoding="utf-8"?>
<ReviseItemResponse xmlns="urn:ebay:apis:eBLBaseComponents">
  <Timestamp>2026-04-25T00:00:00.000Z</Timestamp>
  <Ack>Success</Ack>
  <Version>967</Version>
  <ItemID>987654321</ItemID>
</ReviseItemResponse>"""

    def test_update_listing(
        self,
        adapter: EbayAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> None:
        """测试刊登更新成功。"""
        adapter._auth_token = "test_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = self.SUCCESS_XML_RESPONSE

        with patch("src.agents.listing_ebay_adapter.requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = adapter.update_listing("987654321", product, asset_package, copywriting)

        assert result.success is True
        assert result.platform == Platform.EBAY
        assert result.listing_id == "987654321"

    def test_update_listing_failure(
        self,
        adapter: EbayAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> None:
        """测试刊登更新失败。"""
        adapter._auth_token = "test_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
<ReviseItemResponse xmlns="urn:ebay:apis:eBLBaseComponents">
  <Ack>Failure</Ack>
  <Errors>
    <Error>
      <ShortMessage>Item not found</ShortMessage>
    </Error>
  </Errors>
</ReviseItemResponse>"""

        with patch("src.agents.listing_ebay_adapter.requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = adapter.update_listing("nonexistent", product, asset_package, copywriting)

        assert result.success is False
        assert "Item not found" in result.error


class TestEbayAdapterDeleteListing:
    """EbayAdapter 刊登删除测试。"""

    SUCCESS_XML_RESPONSE = """<?xml version="1.0" encoding="utf-8"?>
<EndItemResponse xmlns="urn:ebay:apis:eBLBaseComponents">
  <Timestamp>2026-04-25T00:00:00.000Z</Timestamp>
  <Ack>Success</Ack>
  <Version>967</Version>
  <EndTime>2026-04-25T12:00:00.000Z</EndTime>
</EndItemResponse>"""

    def test_delete_listing(
        self,
        adapter: EbayAdapter,
    ) -> None:
        """测试刊登删除成功。"""
        adapter._auth_token = "test_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = self.SUCCESS_XML_RESPONSE

        with patch("src.agents.listing_ebay_adapter.requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = adapter.delete_listing("123456789")

        assert result.success is True
        assert result.platform == Platform.EBAY
        assert result.listing_id == "123456789"

    def test_delete_listing_failure(
        self,
        adapter: EbayAdapter,
    ) -> None:
        """测试刊登删除失败。"""
        adapter._auth_token = "test_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
<EndItemResponse xmlns="urn:ebay:apis:eBLBaseComponents">
  <Ack>Failure</Ack>
  <Errors>
    <Error>
      <ShortMessage>Item already ended</ShortMessage>
    </Error>
  </Errors>
</EndItemResponse>"""

        with patch("src.agents.listing_ebay_adapter.requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = adapter.delete_listing("already_ended_id")

        assert result.success is False
        assert "Item already ended" in result.error


class TestEbayAdapterXmlPayload:
    """EbayAdapter XML 载荷结构测试。"""

    def test_xml_payload_structure(
        self,
        adapter: EbayAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        task: ListingTask,
    ) -> None:
        """测试请求头 Content-Type 包含 xml。"""
        adapter._auth_token = "test_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0"?>
<AddItemResponse xmlns="urn:ebay:apis:eBLBaseComponents">
  <Ack>Success</Ack>
  <ItemID>111</ItemID>
</AddItemResponse>"""

        with patch("src.agents.listing_ebay_adapter.requests.post") as mock_post:
            mock_post.return_value = mock_response
            adapter.push_listing(product, asset_package, copywriting, task)

        call_headers = mock_post.call_args.kwargs["headers"]
        assert "xml" in call_headers["Content-Type"]
        assert call_headers["X-EBAY-API-CALL-NAME"] == "AddItem"


class TestEbayAdapterEscapeXml:
    """EbayAdapter XML 转义测试。"""

    def test_escape_xml_special_chars(self, adapter: EbayAdapter) -> None:
        """测试 XML 特殊字符转义。"""
        assert adapter._escape_xml("<tag>") == "&lt;tag&gt;"
        assert adapter._escape_xml("A & B") == "A &amp; B"
        assert adapter._escape_xml('say "hi"') == "say &quot;hi&quot;"
        assert adapter._escape_xml("it's") == "it&apos;s"

    def test_escape_xml_empty_string(self, adapter: EbayAdapter) -> None:
        """测试空字符串转义返回空。"""
        assert adapter._escape_xml("") == ""

    def test_escape_xml_none_like(self, adapter: EbayAdapter) -> None:
        """测试 falsy 值处理。"""
        assert adapter._escape_xml("") == ""


class TestEbayAdapterParseXmlResponse:
    """EbayAdapter XML 解析测试。"""

    def test_parse_success_response(self, adapter: EbayAdapter) -> None:
        """测试成功响应解析。"""
        xml = """<?xml version="1.0"?>
<AddItemResponse xmlns="urn:ebay:apis:eBLBaseComponents">
  <Ack>Success</Ack>
  <ItemID>555666</ItemID>
</AddItemResponse>"""
        ack, item_id, errors = adapter._parse_xml_response(xml)
        assert ack == "Success"
        assert item_id == "555666"
        assert errors == []

    def test_parse_failure_response(self, adapter: EbayAdapter) -> None:
        """测试失败响应解析。"""
        xml = """<?xml version="1.0"?>
<AddItemResponse xmlns="urn:ebay:apis:eBLBaseComponents">
  <Ack>Failure</Ack>
  <Errors>
    <Error>
      <ShortMessage>Invalid data</ShortMessage>
    </Error>
  </Errors>
</AddItemResponse>"""
        ack, item_id, errors = adapter._parse_xml_response(xml)
        assert ack == "Failure"
        assert item_id is None
        assert errors == ["Invalid data"]

    def test_parse_invalid_xml(self, adapter: EbayAdapter) -> None:
        """测试无效 XML 解析返回 Failure。"""
        ack, item_id, errors = adapter._parse_xml_response("not xml at all")
        assert ack == "Failure"
        assert errors
        assert "XML parse error" in errors[0]
