"""
Shopify GraphQL 刊登适配器。

Description:
    实现 Shopify Admin GraphQL API 的刊登推送。
    使用 API Key 认证 + GraphQL mutations。
    集成速率限制、重试策略和 GraphQL cost tracking。
@author ganjianfei
@version 2.0.0
2026-07-14
"""

import contextlib
import logging
import time
from typing import Any

from src.agents.listing_platform_adapter import BasePlatformAdapter, PushConfig, PushResult
from src.agents.listing_rate_limiter import RateLimiter
from src.agents.listing_retry import (
    PermanentPushError,
    RetryablePushError,
    create_push_retry_decorator,
)
from src.models.listing import (
    AssetPackage,
    CopywritingPackage,
    ListingProduct,
    ListingTask,
    Platform,
)

logger = logging.getLogger(__name__)

# Shopify GraphQL API 常量
DEFAULT_API_VERSION = "2024-01"

CREATE_PRODUCT_MUTATION = """
mutation productCreate($input: ProductInput!) {
  productCreate(input: $input) {
    product { id title handle }
    userErrors { field message }
  }
}
"""

UPDATE_PRODUCT_MUTATION = """
mutation productUpdate($input: ProductInput!) {
  productUpdate(input: $input) {
    product { id title }
    userErrors { field message }
  }
}
"""

DELETE_PRODUCT_MUTATION = """
mutation productDelete($id: ID!) {
  productDelete(id: $id) {
    deletedProductId
    userErrors { field message }
  }
}
"""

SHOP_HEALTH_QUERY = """
query {
  shop { name }
}
"""


class ShopifyAdapter(BasePlatformAdapter):
    """Shopify Admin GraphQL API 刊登适配器。

    负责与 Shopify Admin GraphQL API 交互，包括：
    - API Key 认证（X-Shopify-Access-Token）
    - JSON 格式素材/文案转换
    - 刊登推送/更新/删除（productCreate / productUpdate / productDelete）
    - GraphQL cost tracking
    - 速率限制和重试策略

    Attributes:
        _config: 平台配置（shop_url, api_key, api_version 等）。
        _auth_token: API Key 访问令牌。
        _rate_limiter: 速率限制器。
        _retry_decorator: 重试装饰器。
        _graphql_cost_remaining: GraphQL 操作剩余额度。
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        push_config: PushConfig | None = None,
    ) -> None:
        """初始化 Shopify 适配器。

        Args:
            config: 平台配置。
            push_config: 推送配置。
        """
        super().__init__(config=config, push_config=push_config)
        self._rate_limiter = RateLimiter(rpm=self._push_config.rate_limit_rpm)
        self._retry_decorator = create_push_retry_decorator(
            max_retries=self._push_config.max_retries,
            base_delay=self._push_config.retry_base_delay,
        )
        self._graphql_cost_remaining: float | None = None

    async def authenticate(self) -> str:
        """执行 Shopify API Key 认证。

        Shopify 使用 API Key（shpat_xxx）作为访问令牌，无需 OAuth 交换。

        Returns:
            API Key 令牌字符串。

        Raises:
            PermanentPushError: API Key 未配置。
        """
        api_key = self._config.get("api_key", "")
        if not api_key:
            raise PermanentPushError("Shopify authentication failed: api_key is not configured")

        self._auth_token = api_key
        logger.info("Shopify API Key authentication successful")
        return self._auth_token

    async def transform_assets(
        self,
        _product: ListingProduct,
        asset_package: AssetPackage,
    ) -> dict[str, Any]:
        """将素材转换为 Shopify 要求的格式。

        Args:
            _product: 源商品（Shopify 素材转换不使用此参数）。
            asset_package: 优化后的素材包。

        Returns:
            Shopify 要求的素材格式 {"images": [{"src": "..."}]}。
        """
        images: list[dict[str, str]] = []

        if asset_package.main_image:
            images.append({"src": asset_package.main_image})

        for img_url in asset_package.variant_images:
            images.append({"src": img_url})

        return {"images": images}

    async def transform_copywriting(
        self,
        copywriting: CopywritingPackage,
    ) -> dict[str, Any]:
        """将文案转换为 Shopify 要求的格式。

        - body_html 包含标题和 bullet points HTML features section。

        Args:
            copywriting: 优化后的文案。

        Returns:
            Shopify 要求的文案格式 {"title": "...", "body_html": "..."}.
        """
        # 构建 body_html：bullet points 包装为 HTML features section
        features_html = ""
        if copywriting.bullet_points:
            items = "".join(f"<li>{self._escape_html(bp)}</li>" for bp in copywriting.bullet_points)
            features_html = f"<h3>Features</h3><ul>{items}</ul>"

        body_html = f"{copywriting.description}\n{features_html}".strip()

        return {
            "title": copywriting.title,
            "body_html": body_html,
            "search_terms": copywriting.search_terms,
        }

    async def push_listing(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        task: ListingTask,
    ) -> PushResult:
        """推送新刊登到 Shopify。

        Args:
            product: 源商品。
            asset_package: 优化后的素材。
            copywriting: 优化后的文案。
            task: 刊登任务。

        Returns:
            推送结果。
        """
        try:
            return await self._retry_decorator(self._do_push_listing)(
                product, asset_package, copywriting, task
            )
        except RetryablePushError as e:
            return PushResult(
                success=False,
                platform=Platform.SHOPIFY,
                error=str(e),
                error_code="RETRY_EXHAUSTED",
            )
        except PermanentPushError as e:
            return PushResult(
                success=False,
                platform=Platform.SHOPIFY,
                error=str(e),
                error_code="PERMANENT_ERROR",
            )

    async def _do_push_listing(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        _task: ListingTask,
    ) -> PushResult:
        """执行刊登推送（内部方法，被重试装饰器包装）。

        Args:
            product: 源商品。
            asset_package: 优化后的素材。
            copywriting: 优化后的文案。
            _task: 刊登任务（Shopify 推送不使用此参数）。

        Returns:
            推送结果。

        Raises:
            RetryablePushError: 可重试错误。
            PermanentPushError: 不可重试错误。
        """
        if not self._auth_token:
            await self.authenticate()

        assets = await self.transform_assets(product, asset_package)
        copy = await self.transform_copywriting(copywriting)

        # 构建 product input
        shopify_input = self._build_product_input(product, assets, copy)

        start_time = time.monotonic()
        response = await self._execute_graphql(CREATE_PRODUCT_MUTATION, {"input": shopify_input})
        latency_ms = (time.monotonic() - start_time) * 1000

        return self._parse_product_response(
            response, "productCreate", Platform.SHOPIFY, latency_ms=latency_ms
        )

    async def update_listing(
        self,
        listing_id: str,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> PushResult:
        """更新 Shopify 已有刊登。

        Args:
            listing_id: 平台刊登ID（Shopify GID）。
            product: 源商品。
            asset_package: 优化后的素材。
            copywriting: 优化后的文案。

        Returns:
            更新结果。
        """
        try:
            return await self._retry_decorator(self._do_update_listing)(
                listing_id, product, asset_package, copywriting
            )
        except RetryablePushError as e:
            return PushResult(
                success=False,
                platform=Platform.SHOPIFY,
                error=str(e),
                error_code="RETRY_EXHAUSTED",
            )
        except PermanentPushError as e:
            return PushResult(
                success=False,
                platform=Platform.SHOPIFY,
                error=str(e),
                error_code="PERMANENT_ERROR",
            )

    async def _do_update_listing(
        self,
        listing_id: str,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> PushResult:
        """执行刊登更新（内部方法，被重试装饰器包装）。

        Args:
            listing_id: 平台刊登ID（Shopify GID）。
            product: 源商品。
            asset_package: 优化后的素材。
            copywriting: 优化后的文案。

        Returns:
            更新结果。

        Raises:
            RetryablePushError: 可重试错误。
            PermanentPushError: 不可重试错误。
        """
        if not self._auth_token:
            await self.authenticate()

        assets = await self.transform_assets(product, asset_package)
        copy = await self.transform_copywriting(copywriting)

        shopify_input = self._build_product_input(product, assets, copy, product_id=listing_id)

        start_time = time.monotonic()
        response = await self._execute_graphql(UPDATE_PRODUCT_MUTATION, {"input": shopify_input})
        latency_ms = (time.monotonic() - start_time) * 1000

        return self._parse_product_response(
            response,
            "productUpdate",
            Platform.SHOPIFY,
            existing_id=listing_id,
            latency_ms=latency_ms,
        )

    async def delete_listing(self, listing_id: str) -> PushResult:
        """删除 Shopify 已有刊登。

        Args:
            listing_id: 平台刊登ID（Shopify GID）。

        Returns:
            删除结果。
        """
        try:
            return await self._retry_decorator(self._do_delete_listing)(listing_id)
        except RetryablePushError as e:
            return PushResult(
                success=False,
                platform=Platform.SHOPIFY,
                error=str(e),
                error_code="RETRY_EXHAUSTED",
            )
        except PermanentPushError as e:
            return PushResult(
                success=False,
                platform=Platform.SHOPIFY,
                error=str(e),
                error_code="PERMANENT_ERROR",
            )

    async def _do_delete_listing(self, listing_id: str) -> PushResult:
        """执行刊登删除（内部方法，被重试装饰器包装）。

        Args:
            listing_id: 平台刊登ID（Shopify GID）。

        Returns:
            删除结果。

        Raises:
            RetryablePushError: 可重试错误。
            PermanentPushError: 不可重试错误。
        """
        if not self._auth_token:
            await self.authenticate()

        start_time = time.monotonic()
        response = await self._execute_graphql(DELETE_PRODUCT_MUTATION, {"id": listing_id})
        latency_ms = (time.monotonic() - start_time) * 1000

        data = response.get("data", {})
        result_data = data.get("productDelete", {})
        user_errors = result_data.get("userErrors", [])

        if user_errors:
            error_msg = "; ".join(err.get("message", "Unknown error") for err in user_errors)
            raise PermanentPushError(f"Shopify delete_listing failed: {error_msg}")

        return PushResult(
            success=True,
            platform=Platform.SHOPIFY,
            listing_id=listing_id,
            latency_ms=latency_ms,
            raw_response=response,
        )

    async def health_check(self) -> bool:
        """检查 Shopify API 健康状态。

        执行 { shop { name } } 查询来验证连通性和认证。

        Returns:
            True 表示健康，False 表示不可用。
        """
        try:
            if not self._auth_token:
                await self.authenticate()

            response = await self._execute_graphql(SHOP_HEALTH_QUERY)
            shop_data = response.get("data", {}).get("shop", {})
            return bool(shop_data.get("name"))
        except Exception:
            return False

    # ------------------------------------------------------------------
    # GraphQL 辅助方法
    # ------------------------------------------------------------------

    @property
    def graphql_url(self) -> str:
        """构建 GraphQL 端点 URL。

        Returns:
            GraphQL 端点 URL。
        """
        shop_url = self._config.get("shop_url", "").rstrip("/")
        api_version = self._config.get("api_version", DEFAULT_API_VERSION)
        return f"{shop_url}/admin/api/{api_version}/graphql.json"

    def _build_headers(self) -> dict[str, str]:
        """构建 GraphQL 请求头。

        Returns:
            请求头字典。
        """
        return {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self._auth_token or "",
        }

    async def _execute_graphql(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行 GraphQL 请求。

        使用速率限制器控制请求频率，并跟踪 GraphQL cost。

        Args:
            query: GraphQL 查询/mutation 字符串。
            variables: 查询变量。

        Returns:
            解析后的 JSON 响应。

        Raises:
            RetryablePushError: 429 限流或 5xx 服务端错误。
            PermanentPushError: userErrors 导致的不可重试错误。
        """
        await self._rate_limiter.acquire()

        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            client = self._get_client()
            response = await client.post(
                self.graphql_url,
                json=payload,
                headers=self._build_headers(),
            )

            # 更新 GraphQL cost tracking
            cost_remaining = response.headers.get("X-Shopify-Shop-Api-Call-Limit")
            if cost_remaining:
                with contextlib.suppress(ValueError, IndexError):
                    # 格式如 "32/40"，取当前值
                    self._graphql_cost_remaining = float(cost_remaining.split("/")[1])

            if response.status_code == 429:
                raise RetryablePushError(
                    f"Shopify GraphQL rate limited: status=429, body={response.text}"
                )

            if response.status_code >= 500:
                raise RetryablePushError(
                    f"Shopify GraphQL server error: status={response.status_code}, body={response.text}"
                )

            if response.status_code != 200:
                raise PermanentPushError(
                    f"Shopify GraphQL request failed: status={response.status_code}, body={response.text}"
                )

            result = response.json()

            # 检查 GraphQL 层面的限流
            extensions = result.get("extensions", {})
            cost = extensions.get("cost", {})
            throttle_status = cost.get("throttleStatus", {})
            if throttle_status.get("currentlyAvailable", 1) <= 0:
                raise RetryablePushError("Shopify GraphQL cost limit reached")

            return result

        except (RetryablePushError, PermanentPushError):
            raise
        except Exception as e:
            raise RetryablePushError(f"Shopify GraphQL request error: {e}") from e

    def _build_product_input(
        self,
        product: ListingProduct,
        assets: dict[str, Any],
        copy: dict[str, Any],
        product_id: str | None = None,
    ) -> dict[str, Any]:
        """构建 Shopify ProductInput。

        Args:
            product: 源商品。
            assets: 转换后的素材。
            copy: 转换后的文案。
            product_id: 可选的 Shopify 产品 GID（更新时使用）。

        Returns:
            Shopify ProductInput 字典。
        """
        price = str(product.price) if product.price else "0.00"

        product_input: dict[str, Any] = {
            "title": copy["title"],
            "bodyHtml": copy["body_html"],
            "vendor": product.brand or "",
            "productType": product.category or "",
            "handle": self._generate_handle(product),
            "variants": [
                {
                    "price": price,
                    "sku": product.sku,
                    "inventoryManagement": "SHOPIFY",
                    "inventoryQuantity": 100,
                }
            ],
        }

        if product_id:
            product_input["id"] = product_id

        if assets["images"]:
            product_input["images"] = assets["images"]

        return product_input

    def _parse_product_response(
        self,
        response: dict[str, Any],
        mutation_key: str,
        platform: Platform,
        existing_id: str | None = None,
        latency_ms: float = 0.0,
    ) -> PushResult:
        """解析产品 mutation 响应。

        Args:
            response: GraphQL 响应。
            mutation_key: mutation 结果键（productCreate/productUpdate）。
            platform: 平台枚举。
            existing_id: 已有 ID（更新时使用）。
            latency_ms: 请求耗时。

        Returns:
            PushResult 推送结果。

        Raises:
            PermanentPushError: userErrors 导致的不可重试错误。
        """
        data = response.get("data", {})
        result_data = data.get(mutation_key, {})
        product_data = result_data.get("product", {})
        user_errors = result_data.get("userErrors", [])

        if user_errors:
            error_msg = "; ".join(err.get("message", "Unknown error") for err in user_errors)
            raise PermanentPushError(f"Shopify {mutation_key} failed: {error_msg}")

        shopify_id = product_data.get("id", existing_id)
        handle = product_data.get("handle", "")
        shop_url = self._config.get("shop_url", "").rstrip("/")
        url = f"{shop_url}/products/{handle}" if handle else None

        return PushResult(
            success=True,
            platform=platform,
            listing_id=shopify_id,
            url=url,
            latency_ms=latency_ms,
            raw_response=response,
        )

    @staticmethod
    def _generate_handle(product: ListingProduct) -> str:
        """生成 Shopify product handle。

        Args:
            product: 源商品。

        Returns:
            URL 友好的 handle 字符串。
        """
        handle = product.title.lower().strip()
        handle = handle.replace(" ", "-")
        # 保留字母、数字、连字符
        handle = "".join(c for c in handle if c.isalnum() or c == "-")
        # 压缩多个连字符
        while "--" in handle:
            handle = handle.replace("--", "-")
        handle = handle.strip("-")
        return handle or "product"

    @staticmethod
    def _escape_html(text: str) -> str:
        """转义 HTML 特殊字符（用于安全插入）。

        Args:
            text: 原始文本。

        Returns:
            转义后的文本。
        """
        if not text:
            return ""
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace('"', "&quot;")
        return text
