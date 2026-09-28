"""
刊登适配器覆盖率补齐测试。

Description:
    补齐 Amazon / Shopify / eBay 刊登适配器与基类的形状映射、鉴权头拼装、
    失败重试与最终失败语义、部分成功终态相关的行为级测试。
    全部通过 mock 隔离外部 HTTP 调用，不发起真实请求。
@author ganjianfei
@version 1.0.0
2026-09-28
"""

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.agents.listing_amazon_adapter import AmazonAdapter
from src.agents.listing_ebay_adapter import EbayAdapter
from src.agents.listing_platform_adapter import (
    BasePlatformAdapter,
    PushConfig,
    PushResult,
)
from src.agents.listing_retry import PermanentPushError, RetryablePushError
from src.agents.listing_shopify_adapter import ShopifyAdapter
from src.models.listing import (
    AssetPackage,
    CopywritingPackage,
    ListingProduct,
    ListingTask,
    Platform,
    TaskStatus,
)

# ==================== 公共 fixture 与工具 ====================


@pytest.fixture
def push_config() -> PushConfig:
    """创建低延迟测试用推送配置。"""
    return PushConfig(max_retries=1, retry_base_delay=0.01, rate_limit_rpm=0)


@pytest.fixture
def product() -> ListingProduct:
    """创建测试用商品。"""
    return ListingProduct(
        sku="COV-SKU-001",
        title="Coverage Test Product",
        description="A product used for adapter coverage tests.",
        category="Electronics",
        brand="CovBrand",
        price=Decimal("19.99"),
    )


@pytest.fixture
def asset_package() -> AssetPackage:
    """创建测试用素材包。"""
    return AssetPackage(
        listing_task_id=1,
        platform=Platform.AMAZON,
        main_image="https://cdn.example.com/main.jpg",
        variant_images=["https://cdn.example.com/v1.jpg", "https://cdn.example.com/v2.jpg"],
    )


@pytest.fixture
def copywriting() -> CopywritingPackage:
    """创建测试用文案包。"""
    return CopywritingPackage(
        listing_task_id=1,
        platform=Platform.AMAZON,
        title="Coverage Title",
        bullet_points=["Point one", "Point two", "Point three"],
        description="Coverage description.",
        search_terms=["alpha", "beta", "gamma"],
    )


@pytest.fixture
def listing_task() -> ListingTask:
    """创建测试用刊登任务（刊登任务 TaskStatus，非生成任务）。"""
    return ListingTask(
        product_id=1,
        target_platforms=[Platform.AMAZON],
        status=TaskStatus.PUSHING,
    )


def _httpx_response(
    status_code: int = 200,
    json_data: dict[str, Any] | None = None,
    text: str = "",
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """构造 httpx.Response 测试替身。"""
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


def _mock_client(response: httpx.Response) -> AsyncMock:
    """构造返回指定响应的异步 HTTP 客户端 mock。"""
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.put = AsyncMock(return_value=response)
    client.delete = AsyncMock(return_value=response)
    return client


# ==================== Amazon 适配器 ====================


class TestAmazonAuthenticateBranches:
    """Amazon LWA 认证分支测试。"""

    @pytest.mark.asyncio
    async def test_rate_limited_raises_retryable(self, push_config: PushConfig) -> None:
        """429 响应应抛 RetryablePushError。"""
        adapter = AmazonAdapter(
            config={
                "client_id": "id",
                "client_secret": "secret",
                "refresh_token": "refresh",
            },
            push_config=push_config,
        )
        response = _httpx_response(status_code=429, text="slow down")
        with (
            patch.object(adapter, "_get_client", return_value=_mock_client(response)),
            pytest.raises(RetryablePushError, match="LWA rate limited"),
        ):
            await adapter.authenticate()

    @pytest.mark.asyncio
    async def test_unexpected_status_raises_permanent(self, push_config: PushConfig) -> None:
        """非 200/400/429/5xx 状态码应抛 PermanentPushError。"""
        adapter = AmazonAdapter(
            config={
                "client_id": "id",
                "client_secret": "secret",
                "refresh_token": "refresh",
            },
            push_config=push_config,
        )
        response = _httpx_response(status_code=403, text="forbidden")
        with (
            patch.object(adapter, "_get_client", return_value=_mock_client(response)),
            pytest.raises(PermanentPushError, match="LWA authentication failed"),
        ):
            await adapter.authenticate()

    @pytest.mark.asyncio
    async def test_network_error_raises_retryable(self, push_config: PushConfig) -> None:
        """底层网络异常应包装为 RetryablePushError。"""
        adapter = AmazonAdapter(
            config={
                "client_id": "id",
                "client_secret": "secret",
                "refresh_token": "refresh",
            },
            push_config=push_config,
        )
        client = AsyncMock()
        client.post = AsyncMock(side_effect=ConnectionError("boom"))
        with (
            patch.object(adapter, "_get_client", return_value=client),
            pytest.raises(RetryablePushError, match="LWA request error"),
        ):
            await adapter.authenticate()


class TestAmazonShapeMapping:
    """Amazon 素材/文案形状映射测试。"""

    @pytest.mark.asyncio
    async def test_transform_assets_without_main_image(
        self,
        product: ListingProduct,
    ) -> None:
        """无主图时只输出变体图。"""
        adapter = AmazonAdapter(config={}, push_config=PushConfig(rate_limit_rpm=0))
        assets = AssetPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            main_image=None,
            variant_images=["https://cdn.example.com/only.jpg"],
        )
        result = await adapter.transform_assets(product, assets)
        assert result == {"images": ["https://cdn.example.com/only.jpg"]}

    @pytest.mark.asyncio
    async def test_transform_assets_truncates_to_max_images(
        self,
        product: ListingProduct,
    ) -> None:
        """图片数量应被限制在 AMAZON_SPEC.max_images 以内。"""
        adapter = AmazonAdapter(config={}, push_config=PushConfig(rate_limit_rpm=0))
        assets = AssetPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            main_image="https://cdn.example.com/main.jpg",
            variant_images=[f"https://cdn.example.com/v{i}.jpg" for i in range(20)],
        )
        result = await adapter.transform_assets(product, assets)
        from src.agents.listing_platform_specs import AMAZON_SPEC

        assert len(result["images"]) == AMAZON_SPEC.max_images

    @pytest.mark.asyncio
    async def test_search_terms_truncated_at_byte_limit(self) -> None:
        """搜索词总字节数超限时应截断而非丢弃全部。"""
        adapter = AmazonAdapter(config={}, push_config=PushConfig(rate_limit_rpm=0))
        long_term = "x" * 200
        copy = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            title="T",
            search_terms=[long_term, "short", "another"],
        )
        result = await adapter.transform_copywriting(copy)
        total = sum(len(t.encode("utf-8")) for t in result["search_terms"])
        assert total <= 249
        assert result["search_terms"], "截断后应至少保留部分内容"

    @pytest.mark.asyncio
    async def test_transform_copywriting_limits_bullets_and_title(self) -> None:
        """标题截断到 max_title_length、bullet_points 截断到 5 条。"""
        adapter = AmazonAdapter(config={}, push_config=PushConfig(rate_limit_rpm=0))
        from src.agents.listing_platform_specs import AMAZON_SPEC

        copy = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            title="T" * (AMAZON_SPEC.max_title_length + 50),
            bullet_points=[f"bp{i}" for i in range(10)],
            description="desc",
        )
        result = await adapter.transform_copywriting(copy)
        assert len(result["title"]) == AMAZON_SPEC.max_title_length
        assert len(result["bullet_points"]) == 5


class TestAmazonPushFailureSemantics:
    """Amazon 推送失败语义：PERMANENT_ERROR 与 RETRY_EXHAUSTED。"""

    @pytest.mark.asyncio
    async def test_permanent_error_maps_to_permanent_error_code(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        listing_task: ListingTask,
    ) -> None:
        """400 响应应产生 error_code=PERMANENT_ERROR 的失败 PushResult。"""
        adapter = AmazonAdapter(
            config={"client_id": "id", "client_secret": "s", "refresh_token": "r"},
            push_config=PushConfig(max_retries=1, retry_base_delay=0.01, rate_limit_rpm=0),
        )
        adapter._auth_token = "tok"
        response = _httpx_response(status_code=400, text="bad request")
        with patch.object(adapter, "_get_client", return_value=_mock_client(response)):
            result = await adapter.push_listing(product, asset_package, copywriting, listing_task)
        assert result.success is False
        assert result.error_code == "PERMANENT_ERROR"

    @pytest.mark.asyncio
    async def test_network_error_maps_to_retry_exhausted(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        listing_task: ListingTask,
    ) -> None:
        """网络异常重试耗尽后应产生 error_code=RETRY_EXHAUSTED。"""
        adapter = AmazonAdapter(
            config={"client_id": "id", "client_secret": "s", "refresh_token": "r"},
            push_config=PushConfig(max_retries=1, retry_base_delay=0.01, rate_limit_rpm=0),
        )
        adapter._auth_token = "tok"
        client = AsyncMock()
        client.post = AsyncMock(side_effect=ConnectionError("down"))
        with patch.object(adapter, "_get_client", return_value=client):
            result = await adapter.push_listing(product, asset_package, copywriting, listing_task)
        assert result.success is False
        assert result.error_code == "RETRY_EXHAUSTED"

    @pytest.mark.asyncio
    async def test_push_auto_authenticates_when_no_token(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        listing_task: ListingTask,
    ) -> None:
        """未缓存令牌时 push 应先走 authenticate。"""
        adapter = AmazonAdapter(
            config={"client_id": "id", "client_secret": "s", "refresh_token": "r"},
            push_config=PushConfig(max_retries=1, retry_base_delay=0.01, rate_limit_rpm=0),
        )
        auth_response = _httpx_response(
            status_code=200,
            json_data={"access_token": "tok", "expires_in": 3600},
        )
        push_response = _httpx_response(status_code=201, json_data={"listingId": "B0XYZ"})
        client = AsyncMock()
        client.post = AsyncMock(side_effect=[auth_response, push_response])
        with patch.object(adapter, "_get_client", return_value=client):
            result = await adapter.push_listing(product, asset_package, copywriting, listing_task)
        assert result.success is True
        assert client.post.call_count == 2


class TestAmazonUpdateDelete:
    """Amazon update_listing / delete_listing 行为测试。"""

    @pytest.mark.asyncio
    async def test_update_listing_success(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> None:
        """PUT 200 应返回 success=True 且保留 listing_id。"""
        adapter = AmazonAdapter(
            config={},
            push_config=PushConfig(max_retries=1, retry_base_delay=0.01, rate_limit_rpm=0),
        )
        adapter._auth_token = "tok"
        response = _httpx_response(status_code=200, json_data={"result": "ok"})
        with patch.object(adapter, "_get_client", return_value=_mock_client(response)):
            result = await adapter.update_listing("B0EXISTING", product, asset_package, copywriting)
        assert result.success is True
        assert result.listing_id == "B0EXISTING"

    @pytest.mark.asyncio
    async def test_update_listing_retry_exhausted(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> None:
        """PUT 5xx 重试耗尽应产生 RETRY_EXHAUSTED。"""
        adapter = AmazonAdapter(
            config={},
            push_config=PushConfig(max_retries=1, retry_base_delay=0.01, rate_limit_rpm=0),
        )
        adapter._auth_token = "tok"
        response = _httpx_response(status_code=503, text="unavailable")
        with patch.object(adapter, "_get_client", return_value=_mock_client(response)):
            result = await adapter.update_listing("B0EXISTING", product, asset_package, copywriting)
        assert result.success is False
        assert result.error_code == "RETRY_EXHAUSTED"

    @pytest.mark.asyncio
    async def test_update_listing_permanent_error(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> None:
        """PUT 400 应产生 PERMANENT_ERROR。"""
        adapter = AmazonAdapter(
            config={},
            push_config=PushConfig(max_retries=1, retry_base_delay=0.01, rate_limit_rpm=0),
        )
        adapter._auth_token = "tok"
        response = _httpx_response(status_code=400, text="bad")
        with patch.object(adapter, "_get_client", return_value=_mock_client(response)):
            result = await adapter.update_listing("B0EXISTING", product, asset_package, copywriting)
        assert result.success is False
        assert result.error_code == "PERMANENT_ERROR"

    @pytest.mark.asyncio
    async def test_delete_listing_success(self) -> None:
        """DELETE 204 应返回 success=True。"""
        adapter = AmazonAdapter(
            config={},
            push_config=PushConfig(max_retries=1, retry_base_delay=0.01, rate_limit_rpm=0),
        )
        adapter._auth_token = "tok"
        response = _httpx_response(status_code=204, text="")
        with patch.object(adapter, "_get_client", return_value=_mock_client(response)):
            result = await adapter.delete_listing("B0DELETE")
        assert result.success is True
        assert result.listing_id == "B0DELETE"

    @pytest.mark.asyncio
    async def test_delete_listing_retry_exhausted(self) -> None:
        """DELETE 429 重试耗尽应产生 RETRY_EXHAUSTED。"""
        adapter = AmazonAdapter(
            config={},
            push_config=PushConfig(max_retries=1, retry_base_delay=0.01, rate_limit_rpm=0),
        )
        adapter._auth_token = "tok"
        response = _httpx_response(status_code=429, text="limited")
        with patch.object(adapter, "_get_client", return_value=_mock_client(response)):
            result = await adapter.delete_listing("B0DELETE")
        assert result.success is False
        assert result.error_code == "RETRY_EXHAUSTED"

    @pytest.mark.asyncio
    async def test_delete_listing_permanent_error(self) -> None:
        """DELETE 400 应产生 PERMANENT_ERROR。"""
        adapter = AmazonAdapter(
            config={},
            push_config=PushConfig(max_retries=1, retry_base_delay=0.01, rate_limit_rpm=0),
        )
        adapter._auth_token = "tok"
        response = _httpx_response(status_code=400, text="bad")
        with patch.object(adapter, "_get_client", return_value=_mock_client(response)):
            result = await adapter.delete_listing("B0DELETE")
        assert result.success is False
        assert result.error_code == "PERMANENT_ERROR"


class TestAmazonSigV4SessionToken:
    """AWS SigV4 会话令牌分支测试。"""

    def test_sign_request_includes_session_token(self, push_config: PushConfig) -> None:
        """提供 aws_session_token 时签名结果应包含 X-Amz-Security-Token。"""
        adapter = AmazonAdapter(
            config={
                "aws_access_key": "AKIAEXAMPLE",
                "aws_secret_key": "secret",
                "aws_session_token": "session-token-abc",
            },
            push_config=push_config,
        )
        adapter._auth_token = "tok"
        headers = adapter._build_headers("POST", "/path", {"a": 1})
        assert headers.get("X-Amz-Security-Token") == "session-token-abc"
        assert headers["Authorization"].startswith("AWS4-HMAC-SHA256")

    def test_sign_request_without_session_token(self, push_config: PushConfig) -> None:
        """未提供 aws_session_token 时不应出现安全令牌头。"""
        adapter = AmazonAdapter(
            config={
                "aws_access_key": "AKIAEXAMPLE",
                "aws_secret_key": "secret",
            },
            push_config=push_config,
        )
        adapter._auth_token = "tok"
        headers = adapter._build_headers("POST", "/path", {"a": 1})
        assert "X-Amz-Security-Token" not in headers


class TestAmazonErrorHandling:
    """Amazon _handle_error_response 与 _safe_json 边界测试。"""

    def test_5xx_raises_retryable(self, push_config: PushConfig) -> None:
        """5xx 错误应抛 RetryablePushError。"""
        adapter = AmazonAdapter(config={}, push_config=push_config)
        response = _httpx_response(status_code=502, text="bad gateway")
        with pytest.raises(RetryablePushError):
            adapter._handle_error_response(response, "push_listing")

    def test_400_raises_permanent(self, push_config: PushConfig) -> None:
        """400 错误应抛 PermanentPushError。"""
        adapter = AmazonAdapter(config={}, push_config=push_config)
        response = _httpx_response(status_code=400, text="bad")
        with pytest.raises(PermanentPushError):
            adapter._handle_error_response(response, "push_listing")

    def test_other_status_raises_permanent(self, push_config: PushConfig) -> None:
        """403 等其他状态码也视为不可重试。"""
        adapter = AmazonAdapter(config={}, push_config=push_config)
        response = _httpx_response(status_code=403, text="forbidden")
        with pytest.raises(PermanentPushError):
            adapter._handle_error_response(response, "push_listing")

    def test_safe_json_invalid_body_returns_empty(self) -> None:
        """非 JSON 响应体应返回空 dict 而非抛异常。"""
        response = _httpx_response(status_code=200, text="not json")
        result = AmazonAdapter._safe_json(response)
        assert result == {}

    def test_safe_json_non_dict_returns_empty(self) -> None:
        """JSON 顶层非 dict 时应返回空 dict。"""
        request = MagicMock(spec=httpx.Request)
        request.method = "GET"
        request.url = httpx.URL("https://example.com")
        response = httpx.Response(status_code=200, json=["a", "b"], request=request)
        result = AmazonAdapter._safe_json(response)
        assert result == {}


# ==================== Shopify 适配器 ====================


class TestShopifyAuthenticate:
    """Shopify API Key 认证测试。"""

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_permanent(self) -> None:
        """未配置 api_key 应抛 PermanentPushError。"""
        adapter = ShopifyAdapter(config={}, push_config=PushConfig(rate_limit_rpm=0))
        with pytest.raises(PermanentPushError, match="api_key is not configured"):
            await adapter.authenticate()

    @pytest.mark.asyncio
    async def test_authenticate_returns_api_key(self) -> None:
        """认证成功应返回 api_key 并缓存。"""
        adapter = ShopifyAdapter(
            config={"api_key": "shpat_abc"},
            push_config=PushConfig(rate_limit_rpm=0),
        )
        token = await adapter.authenticate()
        assert token == "shpat_abc"
        assert adapter._auth_token == "shpat_abc"


class TestShopifyShapeMapping:
    """Shopify 素材/文案/handle 形状映射测试。"""

    @pytest.mark.asyncio
    async def test_transform_assets_without_main_image(self) -> None:
        """无主图时只输出变体图的 src 形状。"""
        adapter = ShopifyAdapter(config={}, push_config=PushConfig(rate_limit_rpm=0))
        assets = AssetPackage(
            listing_task_id=1,
            platform=Platform.SHOPIFY,
            main_image=None,
            variant_images=["https://cdn.example.com/v.jpg"],
        )
        result = await adapter.transform_assets(ListingProduct(sku="S1", title="T"), assets)
        assert result == {"images": [{"src": "https://cdn.example.com/v.jpg"}]}

    @pytest.mark.asyncio
    async def test_transform_copywriting_without_bullets(self) -> None:
        """无 bullet_points 时 body_html 不应包含 Features 段。"""
        adapter = ShopifyAdapter(config={}, push_config=PushConfig(rate_limit_rpm=0))
        copy = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.SHOPIFY,
            title="Title",
            bullet_points=[],
            description="Plain description",
        )
        result = await adapter.transform_copywriting(copy)
        assert "Features" not in result["body_html"]
        assert "Plain description" in result["body_html"]

    @pytest.mark.asyncio
    async def test_transform_copywriting_escapes_html(self) -> None:
        """bullet_points 中的 HTML 特殊字符应被转义。"""
        adapter = ShopifyAdapter(config={}, push_config=PushConfig(rate_limit_rpm=0))
        copy = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.SHOPIFY,
            title="Title",
            bullet_points=['<script>alert("x")</script>'],
            description="desc",
        )
        result = await adapter.transform_copywriting(copy)
        assert "<script>" not in result["body_html"]
        assert "&lt;script&gt;" in result["body_html"]

    def test_generate_handle_sanitizes_special_chars(self) -> None:
        """handle 生成应去掉非法字符并压缩连字符。"""
        product = ListingProduct(sku="S1", title="  Hello,  World!! -- Test  ")
        handle = ShopifyAdapter._generate_handle(product)
        assert handle == "hello-world-test"

    def test_generate_handle_empty_title_fallback(self) -> None:
        """标题为空白时 handle 兜底为 product。"""
        product = ListingProduct(sku="S1", title="   ")
        assert ShopifyAdapter._generate_handle(product) == "product"

    def test_escape_html_empty_string(self) -> None:
        """空字符串转义应返回空字符串。"""
        assert ShopifyAdapter._escape_html("") == ""


class TestShopifyPushUpdateDelete:
    """Shopify push / update / delete 行为测试。"""

    @pytest.mark.asyncio
    async def test_push_auto_authenticates_and_builds_input(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        listing_task: ListingTask,
    ) -> None:
        """未缓存令牌时 push 应先认证，成功后返回 listing_id 与 url。"""
        adapter = ShopifyAdapter(
            config={
                "shop_url": "https://cov.myshopify.com",
                "api_key": "shpat_key",
            },
            push_config=PushConfig(max_retries=1, retry_base_delay=0.01, rate_limit_rpm=0),
        )
        graphql_response = {
            "data": {
                "productCreate": {
                    "product": {"id": "gid://shopify/Product/1", "handle": "cov"},
                    "userErrors": [],
                }
            }
        }
        with patch.object(
            adapter, "_execute_graphql", new=AsyncMock(return_value=graphql_response)
        ) as mock_exec:
            result = await adapter.push_listing(product, asset_package, copywriting, listing_task)
        assert result.success is True
        assert result.listing_id == "gid://shopify/Product/1"
        assert result.url == "https://cov.myshopify.com/products/cov"
        assert adapter._auth_token == "shpat_key"
        mock_exec.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_push_user_errors_maps_to_permanent_error(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        listing_task: ListingTask,
    ) -> None:
        """GraphQL userErrors 应在 push 层映射为 PERMANENT_ERROR。"""
        adapter = ShopifyAdapter(
            config={"shop_url": "https://cov.myshopify.com", "api_key": "k"},
            push_config=PushConfig(max_retries=1, retry_base_delay=0.01, rate_limit_rpm=0),
        )
        adapter._auth_token = "k"
        graphql_response = {
            "data": {
                "productCreate": {
                    "product": None,
                    "userErrors": [{"field": ["title"], "message": "too long"}],
                }
            }
        }
        with patch.object(
            adapter, "_execute_graphql", new=AsyncMock(return_value=graphql_response)
        ):
            result = await adapter.push_listing(product, asset_package, copywriting, listing_task)
        assert result.success is False
        assert result.error_code == "PERMANENT_ERROR"

    @pytest.mark.asyncio
    async def test_push_retryable_maps_to_retry_exhausted(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        listing_task: ListingTask,
    ) -> None:
        """可重试错误重试耗尽后应映射为 RETRY_EXHAUSTED。"""
        adapter = ShopifyAdapter(
            config={"shop_url": "https://cov.myshopify.com", "api_key": "k"},
            push_config=PushConfig(max_retries=1, retry_base_delay=0.01, rate_limit_rpm=0),
        )
        adapter._auth_token = "k"
        with patch.object(
            adapter,
            "_execute_graphql",
            new=AsyncMock(side_effect=RetryablePushError("rate limited")),
        ):
            result = await adapter.push_listing(product, asset_package, copywriting, listing_task)
        assert result.success is False
        assert result.error_code == "RETRY_EXHAUSTED"

    @pytest.mark.asyncio
    async def test_update_listing_success(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> None:
        """productUpdate 成功应保留 existing_id（响应无 id 时）。"""
        adapter = ShopifyAdapter(
            config={"shop_url": "https://cov.myshopify.com", "api_key": "k"},
            push_config=PushConfig(max_retries=1, retry_base_delay=0.01, rate_limit_rpm=0),
        )
        adapter._auth_token = "k"
        graphql_response = {
            "data": {
                "productUpdate": {
                    "product": {"id": "gid://shopify/Product/9"},
                    "userErrors": [],
                }
            }
        }
        with patch.object(
            adapter, "_execute_graphql", new=AsyncMock(return_value=graphql_response)
        ) as mock_exec:
            result = await adapter.update_listing(
                "gid://shopify/Product/9", product, asset_package, copywriting
            )
        assert result.success is True
        assert result.listing_id == "gid://shopify/Product/9"
        assert result.url is None  # 响应无 handle
        mock_exec.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_listing_permanent_error(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> None:
        """update userErrors 应映射为 PERMANENT_ERROR。"""
        adapter = ShopifyAdapter(
            config={"shop_url": "https://cov.myshopify.com", "api_key": "k"},
            push_config=PushConfig(max_retries=1, retry_base_delay=0.01, rate_limit_rpm=0),
        )
        adapter._auth_token = "k"
        graphql_response = {
            "data": {
                "productUpdate": {
                    "product": None,
                    "userErrors": [{"field": ["id"], "message": "not found"}],
                }
            }
        }
        with patch.object(
            adapter, "_execute_graphql", new=AsyncMock(return_value=graphql_response)
        ):
            result = await adapter.update_listing(
                "gid://shopify/Product/9", product, asset_package, copywriting
            )
        assert result.success is False
        assert result.error_code == "PERMANENT_ERROR"

    @pytest.mark.asyncio
    async def test_delete_listing_success(self) -> None:
        """productDelete 无 userErrors 应返回 success。"""
        adapter = ShopifyAdapter(
            config={"shop_url": "https://cov.myshopify.com", "api_key": "k"},
            push_config=PushConfig(max_retries=1, retry_base_delay=0.01, rate_limit_rpm=0),
        )
        adapter._auth_token = "k"
        graphql_response = {
            "data": {"productDelete": {"deletedProductId": "gid://shopify/Product/1"}}
        }
        with patch.object(
            adapter, "_execute_graphql", new=AsyncMock(return_value=graphql_response)
        ):
            result = await adapter.delete_listing("gid://shopify/Product/1")
        assert result.success is True
        assert result.listing_id == "gid://shopify/Product/1"

    @pytest.mark.asyncio
    async def test_delete_listing_user_errors_raises_permanent(self) -> None:
        """productDelete 的 userErrors 应在重试包装后映射为 PERMANENT_ERROR。"""
        adapter = ShopifyAdapter(
            config={"shop_url": "https://cov.myshopify.com", "api_key": "k"},
            push_config=PushConfig(max_retries=1, retry_base_delay=0.01, rate_limit_rpm=0),
        )
        adapter._auth_token = "k"
        graphql_response = {
            "data": {
                "productDelete": {
                    "deletedProductId": None,
                    "userErrors": [{"field": ["id"], "message": "not found"}],
                }
            }
        }
        with patch.object(
            adapter, "_execute_graphql", new=AsyncMock(return_value=graphql_response)
        ):
            result = await adapter.delete_listing("gid://shopify/Product/1")
        assert result.success is False
        assert result.error_code == "PERMANENT_ERROR"


class TestShopifyGraphqlExecution:
    """Shopify _execute_graphql 状态码与 cost tracking 测试。"""

    @pytest.mark.asyncio
    async def test_cost_tracking_header_parsed(self) -> None:
        """X-Shopify-Shop-Api-Call-Limit 头应解析出剩余额度。"""
        adapter = ShopifyAdapter(
            config={"shop_url": "https://cov.myshopify.com", "api_key": "k"},
            push_config=PushConfig(rate_limit_rpm=0),
        )
        adapter._auth_token = "k"
        response = _httpx_response(
            status_code=200,
            json_data={"data": {"shop": {"name": "cov"}}},
            headers={"X-Shopify-Shop-Api-Call-Limit": "32/40"},
        )
        with patch.object(adapter, "_get_client", return_value=_mock_client(response)):
            result = await adapter._execute_graphql("query { shop { name } }")
        assert result["data"]["shop"]["name"] == "cov"
        assert adapter._graphql_cost_remaining == 40.0

    @pytest.mark.asyncio
    async def test_cost_tracking_malformed_header_ignored(self) -> None:
        """畸形的 cost 头不应导致请求失败。"""
        adapter = ShopifyAdapter(
            config={"shop_url": "https://cov.myshopify.com", "api_key": "k"},
            push_config=PushConfig(rate_limit_rpm=0),
        )
        adapter._auth_token = "k"
        response = _httpx_response(
            status_code=200,
            json_data={"data": {}},
            headers={"X-Shopify-Shop-Api-Call-Limit": "bad-format"},
        )
        with patch.object(adapter, "_get_client", return_value=_mock_client(response)):
            result = await adapter._execute_graphql("query { x }")
        assert result == {"data": {}}
        assert adapter._graphql_cost_remaining is None

    @pytest.mark.asyncio
    async def test_status_429_raises_retryable(self) -> None:
        """HTTP 429 应抛 RetryablePushError。"""
        adapter = ShopifyAdapter(
            config={"shop_url": "https://cov.myshopify.com", "api_key": "k"},
            push_config=PushConfig(rate_limit_rpm=0),
        )
        adapter._auth_token = "k"
        response = _httpx_response(status_code=429, text="limited")
        with (
            patch.object(adapter, "_get_client", return_value=_mock_client(response)),
            pytest.raises(RetryablePushError, match="rate limited"),
        ):
            await adapter._execute_graphql("query { x }")

    @pytest.mark.asyncio
    async def test_non_dict_json_raises_permanent(self) -> None:
        """JSON 顶层非 dict 应抛 PermanentPushError。"""
        adapter = ShopifyAdapter(
            config={"shop_url": "https://cov.myshopify.com", "api_key": "k"},
            push_config=PushConfig(rate_limit_rpm=0),
        )
        adapter._auth_token = "k"
        request = MagicMock(spec=httpx.Request)
        request.method = "POST"
        request.url = httpx.URL("https://example.com")
        response = httpx.Response(status_code=200, json=["list"], request=request)
        with (
            patch.object(adapter, "_get_client", return_value=_mock_client(response)),
            pytest.raises(PermanentPushError, match="not a JSON object"),
        ):
            await adapter._execute_graphql("query { x }")

    @pytest.mark.asyncio
    async def test_graphql_cost_limit_raises_retryable(self) -> None:
        """GraphQL cost 余额耗尽应抛 RetryablePushError。"""
        adapter = ShopifyAdapter(
            config={"shop_url": "https://cov.myshopify.com", "api_key": "k"},
            push_config=PushConfig(rate_limit_rpm=0),
        )
        adapter._auth_token = "k"
        response = _httpx_response(
            status_code=200,
            json_data={
                "data": {},
                "extensions": {"cost": {"throttleStatus": {"currentlyAvailable": 0}}},
            },
        )
        with (
            patch.object(adapter, "_get_client", return_value=_mock_client(response)),
            pytest.raises(RetryablePushError, match="cost limit"),
        ):
            await adapter._execute_graphql("query { x }")

    @pytest.mark.asyncio
    async def test_network_error_wrapped_as_retryable(self) -> None:
        """底层网络异常应包装为 RetryablePushError。"""
        adapter = ShopifyAdapter(
            config={"shop_url": "https://cov.myshopify.com", "api_key": "k"},
            push_config=PushConfig(rate_limit_rpm=0),
        )
        adapter._auth_token = "k"
        client = AsyncMock()
        client.post = AsyncMock(side_effect=ConnectionError("down"))
        with (
            patch.object(adapter, "_get_client", return_value=client),
            pytest.raises(RetryablePushError, match="GraphQL request error"),
        ):
            await adapter._execute_graphql("query { x }")


class TestShopifyProductInput:
    """Shopify ProductInput 构建测试。"""

    def test_product_input_includes_id_when_updating(self) -> None:
        """更新时 ProductInput 应包含 id 字段。"""
        adapter = ShopifyAdapter(
            config={"shop_url": "https://cov.myshopify.com", "api_key": "k"},
            push_config=PushConfig(rate_limit_rpm=0),
        )
        product = ListingProduct(
            sku="S1", title="Title", brand="B", category="C", price=Decimal("9.99")
        )
        result = adapter._build_product_input(
            product,
            {"images": [{"src": "https://x/1.jpg"}]},
            {"title": "T", "body_html": "H"},
            product_id="gid://shopify/Product/5",
        )
        assert result["id"] == "gid://shopify/Product/5"
        assert result["images"] == [{"src": "https://x/1.jpg"}]
        assert result["variants"][0]["price"] == "9.99"

    def test_product_input_omits_images_when_empty(self) -> None:
        """无图片时 ProductInput 不应包含 images 键。"""
        adapter = ShopifyAdapter(
            config={"shop_url": "https://cov.myshopify.com", "api_key": "k"},
            push_config=PushConfig(rate_limit_rpm=0),
        )
        product = ListingProduct(sku="S1", title="Title")
        result = adapter._build_product_input(
            product, {"images": []}, {"title": "T", "body_html": "H"}
        )
        assert "images" not in result
        assert "id" not in result


# ==================== eBay 适配器 ====================


class TestEbayFailurePaths:
    """eBay push/update/delete 异常路径测试。"""

    @pytest.mark.asyncio
    async def test_push_listing_network_error_returns_failure(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        listing_task: ListingTask,
    ) -> None:
        """push 网络异常应返回 success=False 而非抛出。"""
        adapter = EbayAdapter(config={"client_id": "id"}, push_config=PushConfig())
        adapter._auth_token = "tok"
        with patch(
            "src.agents.listing_ebay_adapter.requests.post",
            side_effect=ConnectionError("down"),
        ):
            result = await adapter.push_listing(product, asset_package, copywriting, listing_task)
        assert result.success is False
        assert result.platform == Platform.EBAY
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_update_listing_network_error_returns_failure(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> None:
        """update 网络异常应返回 success=False。"""
        adapter = EbayAdapter(config={"client_id": "id"}, push_config=PushConfig())
        adapter._auth_token = "tok"
        with patch(
            "src.agents.listing_ebay_adapter.requests.post",
            side_effect=ConnectionError("down"),
        ):
            result = await adapter.update_listing("12345", product, asset_package, copywriting)
        assert result.success is False
        assert result.platform == Platform.EBAY

    @pytest.mark.asyncio
    async def test_delete_listing_network_error_returns_failure(self) -> None:
        """delete 网络异常应返回 success=False。"""
        adapter = EbayAdapter(config={"client_id": "id"}, push_config=PushConfig())
        adapter._auth_token = "tok"
        with patch(
            "src.agents.listing_ebay_adapter.requests.post",
            side_effect=ConnectionError("down"),
        ):
            result = await adapter.delete_listing("12345")
        assert result.success is False
        assert result.platform == Platform.EBAY


class TestEbayXmlParsing:
    """eBay XML 响应解析测试（含无命名空间回退）。"""

    def test_parse_response_without_namespace(self) -> None:
        """无命名空间的 XML 应正确解析 Ack 与 Errors。"""
        xml = """<?xml version="1.0" encoding="utf-8"?>
        <AddItemResponse>
          <Ack>Failure</Ack>
          <Errors>
            <Error><ShortMessage>Invalid title</ShortMessage></Error>
          </Errors>
        </AddItemResponse>
        """
        ack, item_id, errors = EbayAdapter._parse_xml_response(xml)
        assert ack == "Failure"
        assert item_id is None
        assert errors == ["Invalid title"]

    def test_parse_response_with_namespace(self) -> None:
        """带命名空间的 XML 应优先走命名空间解析路径。"""
        ns = "urn:ebay:apis:eBLBaseComponents"
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
        <AddItemResponse xmlns="{ns}">
          <Ack>Success</Ack>
          <ItemID>98765</ItemID>
        </AddItemResponse>
        """
        ack, item_id, errors = EbayAdapter._parse_xml_response(xml)
        assert ack == "Success"
        assert item_id == "98765"
        assert errors == []

    def test_parse_response_malformed_xml(self) -> None:
        """XML 解析失败应返回 Failure 而非抛异常。"""
        ack, item_id, errors = EbayAdapter._parse_xml_response("not xml at all")
        assert ack == "Failure"
        assert item_id is None
        assert any("XML parse error" in e for e in errors)

    def test_build_pictures_xml_empty(self) -> None:
        """空图片列表应返回空字符串。"""
        adapter = EbayAdapter(config={}, push_config=PushConfig())
        assert adapter._build_pictures_xml([]) == ""


# ==================== 基类行为 ====================


class TestBasePlatformAdapterBehavior:
    """BasePlatformAdapter 健康检查、客户端生命周期测试。"""

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_auth_error(self) -> None:
        """authenticate 抛异常时 health_check 应返回 False。"""

        class _StubAdapter(BasePlatformAdapter):
            async def authenticate(self) -> str:
                raise PermanentPushError("nope")

            async def transform_assets(
                self, product: ListingProduct, asset_package: AssetPackage
            ) -> dict[str, Any]:
                return {}

            async def transform_copywriting(
                self, copywriting: CopywritingPackage
            ) -> dict[str, Any]:
                return {}

            async def push_listing(
                self,
                product: ListingProduct,
                asset_package: AssetPackage,
                copywriting: CopywritingPackage,
                task: ListingTask,
            ) -> PushResult:
                return PushResult(success=True, platform=Platform.AMAZON)

            async def update_listing(
                self,
                listing_id: str,
                product: ListingProduct,
                asset_package: AssetPackage,
                copywriting: CopywritingPackage,
            ) -> PushResult:
                return PushResult(success=True, platform=Platform.AMAZON)

            async def delete_listing(self, listing_id: str) -> PushResult:
                return PushResult(success=True, platform=Platform.AMAZON)

        adapter = _StubAdapter()
        assert await adapter.health_check() is False

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_auth_success(self) -> None:
        """authenticate 成功时 health_check 应返回 True。"""

        class _StubAdapter(BasePlatformAdapter):
            async def authenticate(self) -> str:
                return "tok"

            async def transform_assets(
                self, product: ListingProduct, asset_package: AssetPackage
            ) -> dict[str, Any]:
                return {}

            async def transform_copywriting(
                self, copywriting: CopywritingPackage
            ) -> dict[str, Any]:
                return {}

            async def push_listing(
                self,
                product: ListingProduct,
                asset_package: AssetPackage,
                copywriting: CopywritingPackage,
                task: ListingTask,
            ) -> PushResult:
                return PushResult(success=True, platform=Platform.AMAZON)

            async def update_listing(
                self,
                listing_id: str,
                product: ListingProduct,
                asset_package: AssetPackage,
                copywriting: CopywritingPackage,
            ) -> PushResult:
                return PushResult(success=True, platform=Platform.AMAZON)

            async def delete_listing(self, listing_id: str) -> PushResult:
                return PushResult(success=True, platform=Platform.AMAZON)

        adapter = _StubAdapter()
        assert await adapter.health_check() is True

    @pytest.mark.asyncio
    async def test_get_listing_status_default_returns_none(self) -> None:
        """默认 get_listing_status 应返回 None。"""

        class _StubAdapter(BasePlatformAdapter):
            async def authenticate(self) -> str:
                return "tok"

            async def transform_assets(
                self, product: ListingProduct, asset_package: AssetPackage
            ) -> dict[str, Any]:
                return {}

            async def transform_copywriting(
                self, copywriting: CopywritingPackage
            ) -> dict[str, Any]:
                return {}

            async def push_listing(
                self,
                product: ListingProduct,
                asset_package: AssetPackage,
                copywriting: CopywritingPackage,
                task: ListingTask,
            ) -> PushResult:
                return PushResult(success=True, platform=Platform.AMAZON)

            async def update_listing(
                self,
                listing_id: str,
                product: ListingProduct,
                asset_package: AssetPackage,
                copywriting: CopywritingPackage,
            ) -> PushResult:
                return PushResult(success=True, platform=Platform.AMAZON)

            async def delete_listing(self, listing_id: str) -> PushResult:
                return PushResult(success=True, platform=Platform.AMAZON)

        adapter = _StubAdapter()
        assert await adapter.get_listing_status("x") is None

    @pytest.mark.asyncio
    async def test_close_releases_client(self) -> None:
        """close 应关闭并清空 HTTP 客户端。"""
        adapter = AmazonAdapter(config={}, push_config=PushConfig(rate_limit_rpm=0))
        client = adapter._get_client()
        assert adapter._client is client
        await adapter.close()
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_get_client_recreates_after_close(self) -> None:
        """close 后再次获取客户端应创建新实例。"""
        adapter = AmazonAdapter(config={}, push_config=PushConfig(rate_limit_rpm=0))
        first = adapter._get_client()
        await adapter.close()
        second = adapter._get_client()
        assert second is not first
        await adapter.close()
