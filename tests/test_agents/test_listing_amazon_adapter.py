"""
Amazon SP-API 刊登适配器测试。

Description:
    测试 AmazonAdapter 的认证、推送、SigV4 签名等功能。
    使用 unittest.mock 模拟 HTTP 请求，不依赖真实 API。
@author ganjianfei
@version 2.0.0
2026-07-14
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.agents.listing_amazon_adapter import AmazonAdapter
from src.agents.listing_platform_adapter import PushConfig
from src.agents.listing_retry import PermanentPushError, RetryablePushError
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
def push_config() -> PushConfig:
    """创建测试用推送配置。"""
    return PushConfig(max_retries=2, retry_base_delay=0.01, rate_limit_rpm=0)


@pytest.fixture
def adapter(push_config: PushConfig) -> AmazonAdapter:
    """创建 Amazon 适配器实例。"""
    return AmazonAdapter(
        config={
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "refresh_token": "test_refresh_token",
            "marketplace_id": "ATVPDKIKX0DER",
        },
        push_config=push_config,
    )


@pytest.fixture
def adapter_with_aws(push_config: PushConfig) -> AmazonAdapter:
    """创建带 AWS 凭证的 Amazon 适配器实例。"""
    return AmazonAdapter(
        config={
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "refresh_token": "test_refresh_token",
            "marketplace_id": "ATVPDKIKX0DER",
            "aws_access_key": "AKIAIOSFODNN7EXAMPLE",
            "aws_secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        },
        push_config=push_config,
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


def _make_httpx_response(
    status_code: int = 200,
    json_data: dict | None = None,
    text: str = "",
) -> httpx.Response:
    """创建模拟的 httpx.Response。"""
    request = MagicMock(spec=httpx.Request)
    request.method = "POST"
    request.url = httpx.URL("https://example.com")
    if json_data is not None:
        return httpx.Response(
            status_code=status_code,
            json=json_data,
            request=request,
        )
    return httpx.Response(
        status_code=status_code,
        text=text,
        request=request,
    )


class TestAuthenticate:
    """AmazonAdapter 认证测试。"""

    @pytest.mark.asyncio
    async def test_authenticate_success(self, adapter: AmazonAdapter) -> None:
        """测试认证成功返回访问令牌。"""
        mock_response = _make_httpx_response(
            status_code=200,
            json_data={"access_token": "test_token_123", "expires_in": 3600},
        )

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            token = await adapter.authenticate()

            assert token == "test_token_123"
            assert adapter._auth_token == "test_token_123"

    @pytest.mark.asyncio
    async def test_authenticate_permanent_error(self, adapter: AmazonAdapter) -> None:
        """测试认证失败（400）抛出 PermanentPushError。"""
        mock_response = _make_httpx_response(
            status_code=400,
            text='{"error": "invalid_grant"}',
        )

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(PermanentPushError, match="LWA authentication failed"):
                await adapter.authenticate()

    @pytest.mark.asyncio
    async def test_authenticate_retryable_error(self, adapter: AmazonAdapter) -> None:
        """测试认证失败（5xx）抛出 RetryablePushError。"""
        mock_response = _make_httpx_response(
            status_code=503,
            text="Service Unavailable",
        )

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(RetryablePushError, match="LWA server error"):
                await adapter.authenticate()

    @pytest.mark.asyncio
    async def test_authenticate_token_caching(self, adapter: AmazonAdapter) -> None:
        """测试令牌缓存：未过期时不重新请求。"""
        adapter._auth_token = "cached_token"
        adapter._token_expires_at = float("inf")

        token = await adapter.authenticate()

        assert token == "cached_token"


class TestPushListing:
    """AmazonAdapter 刊登推送测试。"""

    @pytest.mark.asyncio
    async def test_push_listing_success(
        self,
        adapter: AmazonAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> None:
        """测试刊登推送成功。"""
        adapter._auth_token = "test_token"

        mock_response = _make_httpx_response(
            status_code=201,
            json_data={"listingId": "B0ABCD1234"},
        )

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            task = ListingTask(
                product_id=1,
                target_platforms=[Platform.AMAZON],
                status=TaskStatus.PUSHING,
            )
            result = await adapter.push_listing(product, asset_package, copywriting, task)

            assert result.success is True
            assert result.listing_id == "B0ABCD1234"
            assert result.platform == Platform.AMAZON
            assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_push_listing_rate_limited(
        self,
        adapter: AmazonAdapter,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> None:
        """测试推送遇到 429 限流，重试耗尽后返回失败结果。"""
        adapter._auth_token = "test_token"

        mock_response = _make_httpx_response(
            status_code=429,
            text="Too Many Requests",
        )

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            task = ListingTask(
                product_id=1,
                target_platforms=[Platform.AMAZON],
                status=TaskStatus.PUSHING,
            )
            result = await adapter.push_listing(product, asset_package, copywriting, task)

            assert result.success is False
            assert result.error_code == "RETRY_EXHAUSTED"


class TestSigV4Signing:
    """AWS SigV4 签名测试。"""

    def test_sign_request_returns_authorization_header(
        self, adapter_with_aws: AmazonAdapter
    ) -> None:
        """测试 SigV4 签名返回 Authorization 头。"""
        adapter_with_aws._auth_token = "test_token"
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "x-amz-access-token": "test_token",
        }

        signed = adapter_with_aws._sign_request(
            method="POST",
            url_path="/listings/2021-08-01/items/ATVPDKIKX0DER/SKU123",
            headers=headers,
            payload={"attributes": {}},
            aws_access_key="AKIAIOSFODNN7EXAMPLE",
            aws_secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        )

        assert "Authorization" in signed
        assert signed["Authorization"].startswith("AWS4-HMAC-SHA256")
        assert "AKIAIOSFODNN7EXAMPLE" in signed["Authorization"]
        assert "X-Amz-Date" in signed
        assert "x-amz-content-sha256" in signed

    def test_get_signing_key_deterministic(self) -> None:
        """测试签名密钥计算是确定性的。"""
        key1 = AmazonAdapter._get_signing_key("secret", "20260714")
        key2 = AmazonAdapter._get_signing_key("secret", "20260714")
        assert key1 == key2

    def test_build_headers_with_aws_credentials(self, adapter_with_aws: AmazonAdapter) -> None:
        """测试有 AWS 凭证时使用 SigV4 签名。"""
        adapter_with_aws._auth_token = "test_token"
        headers = adapter_with_aws._build_headers(
            "POST", "/listings/2021-08-01/items/ATVPDKIKX0DER/SKU123", {"data": "test"}
        )

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("AWS4-HMAC-SHA256")

    def test_build_headers_without_aws_credentials(self, adapter: AmazonAdapter) -> None:
        """测试无 AWS 凭证时回退到 Bearer token 模式。"""
        adapter._auth_token = "test_token"
        headers = adapter._build_headers(
            "POST", "/listings/2021-08-01/items/ATVPDKIKX0DER/SKU123", {"data": "test"}
        )

        assert headers["Authorization"] == "Bearer test_token"
