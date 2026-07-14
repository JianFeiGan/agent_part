"""
Amazon SP-API 刊登适配器。

Description:
    实现 Amazon Selling Partner API 的刊登推送。
    包含 LWA OAuth2 认证 + AWS SigV4 签名。
    使用 httpx.AsyncClient 进行异步 HTTP 请求，
    集成速率限制和重试策略。
@author ganjianfei
@version 2.0.0
2026-07-14
"""

import hashlib
import hmac
import logging
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from src.agents.listing_platform_adapter import BasePlatformAdapter, PushConfig, PushResult
from src.agents.listing_platform_specs import AMAZON_SPEC
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

# Amazon SP-API 常量
LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
SP_API_BASE_URL = "https://sellingpartnerapi-na.amazon.com"
LISTINGS_API_VERSION = "2021-08-01"
DEFAULT_MARKETPLACE_ID = "ATVPDKIKX0DER"  # US marketplace

# AWS SigV4 常量
AWS_SERVICE = "execute-api"
AWS_REGION = "us-east-1"
AWS_ALGORITHM = "AWS4-HMAC-SHA256"


class AmazonAdapter(BasePlatformAdapter):
    """Amazon SP-API 刊登适配器。

    负责与 Amazon Selling Partner API 交互，包括：
    - LWA (Login with Amazon) OAuth2 认证（支持令牌缓存）
    - AWS SigV4 请求签名
    - 素材格式转换
    - 文案格式转换
    - 刊登推送/更新/删除（含重试和限流）

    Attributes:
        _config: 平台配置（client_id, client_secret, refresh_token, aws_access_key 等）。
        _auth_token: LWA 访问令牌。
        _token_expires_at: 令牌过期时间戳。
        _rate_limiter: 速率限制器。
        _retry_decorator: 重试装饰器。
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        push_config: PushConfig | None = None,
    ) -> None:
        """初始化 Amazon 适配器。

        Args:
            config: 平台配置。
            push_config: 推送配置。
        """
        super().__init__(config=config, push_config=push_config)
        self._token_expires_at: float = 0.0
        self._rate_limiter = RateLimiter(rpm=self._push_config.rate_limit_rpm)
        self._retry_decorator = create_push_retry_decorator(
            max_retries=self._push_config.max_retries,
            base_delay=self._push_config.retry_base_delay,
        )

    async def authenticate(self) -> str:
        """执行 LWA OAuth2 认证，获取访问令牌。

        支持令牌缓存：如果令牌未过期，直接返回缓存的令牌。
        使用 refresh_token 方式交换令牌。

        Returns:
            LWA 访问令牌字符串。

        Raises:
            PermanentPushError: 认证凭据无效（400 响应）。
            RetryablePushError: 认证服务临时不可用（5xx 响应）。
        """
        # 检查令牌缓存
        if self._auth_token and time.monotonic() < self._token_expires_at:
            return self._auth_token

        client_id = self._config.get("client_id", "")
        client_secret = self._config.get("client_secret", "")
        refresh_token = self._config.get("refresh_token", "")

        payload = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }

        start_time = time.monotonic()
        try:
            client = self._get_client()
            response = await client.post(LWA_TOKEN_URL, data=payload)
            latency_ms = (time.monotonic() - start_time) * 1000

            if response.status_code == 200:
                token_data = response.json()
                self._auth_token = token_data["access_token"]
                # 缓存令牌，提前 60 秒过期
                expires_in = token_data.get("expires_in", 3600)
                self._token_expires_at = time.monotonic() + expires_in - 60
                logger.info("LWA authentication successful, latency=%.0fms", latency_ms)
                return self._auth_token

            error_body = response.text
            if response.status_code == 400:
                raise PermanentPushError(
                    f"LWA authentication failed: status=400, body={error_body}"
                )

            if response.status_code == 429:
                raise RetryablePushError(f"LWA rate limited: status=429, body={error_body}")

            if response.status_code >= 500:
                raise RetryablePushError(
                    f"LWA server error: status={response.status_code}, body={error_body}"
                )

            raise PermanentPushError(
                f"LWA authentication failed: status={response.status_code}, body={error_body}"
            )

        except (PermanentPushError, RetryablePushError):
            raise
        except Exception as e:
            raise RetryablePushError(f"LWA request error: {e}") from e

    async def transform_assets(
        self,
        _product: ListingProduct,
        asset_package: AssetPackage,
    ) -> dict[str, Any]:
        """将素材转换为 Amazon 要求的格式。

        Args:
            _product: 源商品（Amazon 素材转换不使用此参数）。
            asset_package: 优化后的素材包。

        Returns:
            Amazon 要求的素材格式 {"images": [...]}。
        """
        images: list[str] = []

        # 主图
        if asset_package.main_image:
            images.append(asset_package.main_image)

        # 变体图
        for img_url in asset_package.variant_images:
            images.append(img_url)

        # 限制最大图片数
        images = images[: AMAZON_SPEC.max_images]

        return {"images": images}

    async def transform_copywriting(
        self,
        copywriting: CopywritingPackage,
    ) -> dict[str, Any]:
        """将文案转换为 Amazon 要求的格式。

        - 标题截断到 200 字符。
        - bullet_points 限制到 5 条。
        - search_terms 总长度限制到 249 字节。

        Args:
            copywriting: 优化后的文案。

        Returns:
            Amazon 要求的文案格式。
        """
        # 截断标题
        title = copywriting.title[: AMAZON_SPEC.max_title_length]

        # 限制 bullet points
        bullet_points = copywriting.bullet_points[:5]

        # 限制 search_terms 到 249 bytes
        search_terms = self._limit_search_terms(copywriting.search_terms, max_bytes=249)

        return {
            "title": title,
            "bullet_points": bullet_points,
            "description": copywriting.description,
            "search_terms": search_terms,
        }

    @staticmethod
    def _limit_search_terms(terms: list[str], max_bytes: int = 249) -> list[str]:
        """限制搜索词总字节数。

        Args:
            terms: 搜索词列表。
            max_bytes: 最大字节数。

        Returns:
            截断后的搜索词列表。
        """
        result: list[str] = []
        total_bytes = 0

        for term in terms:
            term_bytes = term.encode("utf-8")
            if total_bytes + len(term_bytes) > max_bytes:
                # 截断当前词
                remaining = max_bytes - total_bytes
                if remaining > 0:
                    truncated = term_bytes[:remaining].decode("utf-8", errors="ignore")
                    if truncated:
                        result.append(truncated)
                break
            result.append(term)
            total_bytes += len(term_bytes)

        return result

    async def push_listing(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        task: ListingTask,
    ) -> PushResult:
        """推送新刊登到 Amazon。

        使用重试装饰器和速率限制器保护请求。

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
                platform=Platform.AMAZON,
                error=str(e),
                error_code="RETRY_EXHAUSTED",
            )
        except PermanentPushError as e:
            return PushResult(
                success=False,
                platform=Platform.AMAZON,
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
            _task: 刊登任务（Amazon 推送不使用此参数）。

        Returns:
            推送结果。

        Raises:
            RetryablePushError: 可重试错误。
            PermanentPushError: 不可重试错误。
        """
        # 确保已认证
        if not self._auth_token:
            await self.authenticate()

        await self._rate_limiter.acquire()

        marketplace_id = self._config.get("marketplace_id", DEFAULT_MARKETPLACE_ID)
        sku = product.sku
        url_path = f"/listings/{LISTINGS_API_VERSION}/items/{marketplace_id}/{sku}"
        full_url = f"{SP_API_BASE_URL}{url_path}"

        # 构建 payload
        assets = await self.transform_assets(product, asset_package)
        copy = await self.transform_copywriting(copywriting)
        payload = {
            "attributes": {
                "item_name": [{"value": copy["title"], "language_tag": "en_US"}],
                "bullet_point": [
                    {"value": bp, "language_tag": "en_US"} for bp in copy["bullet_points"]
                ],
                "product_description": [{"value": copy["description"], "language_tag": "en_US"}],
                "generic_keyword": [
                    {"value": " ".join(copy["search_terms"]), "language_tag": "en_US"}
                ],
                "main_image": [
                    {"value": img, "language_tag": "en_US"} for img in assets["images"][:1]
                ],
            },
        }

        headers = self._build_headers("POST", url_path, payload)
        start_time = time.monotonic()

        try:
            client = self._get_client()
            response = await client.post(full_url, json=payload, headers=headers)
            latency_ms = (time.monotonic() - start_time) * 1000

            if response.status_code in (200, 201):
                data = response.json()
                listing_id = data.get("listingId", sku)
                return PushResult(
                    success=True,
                    platform=Platform.AMAZON,
                    listing_id=listing_id,
                    url=f"https://www.amazon.com/dp/{listing_id}",
                    latency_ms=latency_ms,
                    raw_response=data,
                )

            return self._handle_error_response(response, "push_listing")

        except (RetryablePushError, PermanentPushError):
            raise
        except Exception as e:
            raise RetryablePushError(f"Amazon push_listing request error: {e}") from e

    async def update_listing(
        self,
        listing_id: str,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> PushResult:
        """更新 Amazon 已有刊登。

        Args:
            listing_id: 平台刊登ID。
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
                platform=Platform.AMAZON,
                error=str(e),
                error_code="RETRY_EXHAUSTED",
            )
        except PermanentPushError as e:
            return PushResult(
                success=False,
                platform=Platform.AMAZON,
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
            listing_id: 平台刊登ID。
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

        await self._rate_limiter.acquire()

        marketplace_id = self._config.get("marketplace_id", DEFAULT_MARKETPLACE_ID)
        sku = product.sku
        url_path = f"/listings/{LISTINGS_API_VERSION}/items/{marketplace_id}/{sku}"
        full_url = f"{SP_API_BASE_URL}{url_path}"

        _ = await self.transform_assets(product, asset_package)
        copy = await self.transform_copywriting(copywriting)
        payload = {
            "attributes": {
                "item_name": [{"value": copy["title"], "language_tag": "en_US"}],
                "bullet_point": [
                    {"value": bp, "language_tag": "en_US"} for bp in copy["bullet_points"]
                ],
                "product_description": [{"value": copy["description"], "language_tag": "en_US"}],
            },
        }

        headers = self._build_headers("PUT", url_path, payload)
        start_time = time.monotonic()

        try:
            client = self._get_client()
            response = await client.put(full_url, json=payload, headers=headers)
            latency_ms = (time.monotonic() - start_time) * 1000

            if response.status_code in (200, 201):
                data = response.json()
                return PushResult(
                    success=True,
                    platform=Platform.AMAZON,
                    listing_id=listing_id,
                    latency_ms=latency_ms,
                    raw_response=data,
                )

            return self._handle_error_response(response, "update_listing")

        except (RetryablePushError, PermanentPushError):
            raise
        except Exception as e:
            raise RetryablePushError(f"Amazon update_listing request error: {e}") from e

    async def delete_listing(self, listing_id: str) -> PushResult:
        """删除 Amazon 已有刊登。

        Args:
            listing_id: 平台刊登ID。

        Returns:
            删除结果。
        """
        try:
            return await self._retry_decorator(self._do_delete_listing)(listing_id)
        except RetryablePushError as e:
            return PushResult(
                success=False,
                platform=Platform.AMAZON,
                error=str(e),
                error_code="RETRY_EXHAUSTED",
            )
        except PermanentPushError as e:
            return PushResult(
                success=False,
                platform=Platform.AMAZON,
                error=str(e),
                error_code="PERMANENT_ERROR",
            )

    async def _do_delete_listing(self, listing_id: str) -> PushResult:
        """执行刊登删除（内部方法，被重试装饰器包装）。

        Args:
            listing_id: 平台刊登ID。

        Returns:
            删除结果。

        Raises:
            RetryablePushError: 可重试错误。
            PermanentPushError: 不可重试错误。
        """
        if not self._auth_token:
            await self.authenticate()

        await self._rate_limiter.acquire()

        marketplace_id = self._config.get("marketplace_id", DEFAULT_MARKETPLACE_ID)
        url_path = f"/listings/{LISTINGS_API_VERSION}/items/{marketplace_id}/{listing_id}"
        full_url = f"{SP_API_BASE_URL}{url_path}"

        headers = self._build_headers("DELETE", url_path)
        start_time = time.monotonic()

        try:
            client = self._get_client()
            response = await client.delete(full_url, headers=headers)
            latency_ms = (time.monotonic() - start_time) * 1000

            if response.status_code in (200, 204):
                return PushResult(
                    success=True,
                    platform=Platform.AMAZON,
                    listing_id=listing_id,
                    latency_ms=latency_ms,
                    raw_response=self._safe_json(response),
                )

            return self._handle_error_response(response, "delete_listing")

        except (RetryablePushError, PermanentPushError):
            raise
        except Exception as e:
            raise RetryablePushError(f"Amazon delete_listing request error: {e}") from e

    def _build_headers(
        self,
        method: str,
        url_path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """构建请求头，支持 AWS SigV4 签名。

        如果配置了 aws_access_key 和 aws_secret_key，使用完整 SigV4 签名；
        否则回退到 Bearer token 模式。

        Args:
            method: HTTP 方法。
            url_path: 请求路径。
            payload: 请求体（可选）。

        Returns:
            请求头字典。
        """
        aws_access_key = self._config.get("aws_access_key", "")
        aws_secret_key = self._config.get("aws_secret_key", "")
        aws_session_token = self._config.get("aws_session_token", "")

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "x-amz-access-token": self._auth_token or "",
        }

        if aws_access_key and aws_secret_key:
            # 使用 AWS SigV4 签名
            signed_headers = self._sign_request(
                method=method,
                url_path=url_path,
                headers=headers,
                payload=payload,
                aws_access_key=aws_access_key,
                aws_secret_key=aws_secret_key,
                aws_session_token=aws_session_token,
            )
            headers.update(signed_headers)
        else:
            # 回退到 Bearer token 模式
            headers["Authorization"] = f"Bearer {self._auth_token or ''}"

        return headers

    def _sign_request(
        self,
        method: str,
        url_path: str,
        headers: dict[str, str],
        payload: dict[str, Any] | None,
        aws_access_key: str,
        aws_secret_key: str,
        aws_session_token: str = "",
    ) -> dict[str, str]:
        """实现 AWS SigV4 签名。

        签名步骤：
        1. 构建规范请求（Canonical Request）
        2. 构建待签字符串（String to Sign）
        3. 计算签名密钥（Signing Key）
        4. 计算签名（Signature）

        Args:
            method: HTTP 方法。
            url_path: 请求路径。
            headers: 已有请求头。
            payload: 请求体。
            aws_access_key: AWS 访问密钥。
            aws_secret_key: AWS 秘密密钥。
            aws_session_token: AWS 会话令牌（可选）。

        Returns:
            包含 Authorization 和 X-Amz-Security-Token 的签名头。
        """
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        # 计算请求体哈希
        import json

        payload_str = json.dumps(payload) if payload else ""
        payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

        # 添加必要的签名头
        headers["host"] = urlparse(SP_API_BASE_URL).netloc
        headers["x-amz-date"] = amz_date
        headers["x-amz-content-sha256"] = payload_hash
        if aws_session_token:
            headers["x-amz-security-token"] = aws_session_token

        # 步骤 1: 构建规范请求
        # 排序头部名称
        signed_header_names = sorted(headers.keys())
        canonical_headers = ""
        for name in signed_header_names:
            canonical_headers += f"{name}:{headers[name].strip()}\n"
        signed_headers_str = ";".join(signed_header_names)

        canonical_request = "\n".join(
            [
                method,
                url_path,
                "",  # 查询字符串（SP-API 通常为空）
                canonical_headers,
                signed_headers_str,
                payload_hash,
            ]
        )

        # 步骤 2: 构建待签字符串
        credential_scope = f"{date_stamp}/{AWS_REGION}/{AWS_SERVICE}/aws4_request"
        canonical_request_hash = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()

        string_to_sign = "\n".join(
            [
                AWS_ALGORITHM,
                amz_date,
                credential_scope,
                canonical_request_hash,
            ]
        )

        # 步骤 3: 计算签名密钥
        signing_key = self._get_signing_key(aws_secret_key, date_stamp)

        # 步骤 4: 计算签名
        signature = hmac.new(
            signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        # 构建授权头
        authorization = (
            f"{AWS_ALGORITHM} Credential={aws_access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers_str}, "
            f"Signature={signature}"
        )

        result: dict[str, str] = {
            "Authorization": authorization,
            "X-Amz-Date": amz_date,
            "x-amz-content-sha256": payload_hash,
        }
        if aws_session_token:
            result["X-Amz-Security-Token"] = aws_session_token

        return result

    @staticmethod
    def _get_signing_key(secret_key: str, date_stamp: str) -> bytes:
        """计算 AWS SigV4 签名密钥。

        Args:
            secret_key: AWS 秘密密钥。
            date_stamp: 日期字符串（YYYYMMDD）。

        Returns:
            签名密钥字节。
        """
        k_date = hmac.new(
            f"AWS4{secret_key}".encode(), date_stamp.encode("utf-8"), hashlib.sha256
        ).digest()
        k_region = hmac.new(k_date, AWS_REGION.encode("utf-8"), hashlib.sha256).digest()
        k_service = hmac.new(k_region, AWS_SERVICE.encode("utf-8"), hashlib.sha256).digest()
        k_signing = hmac.new(k_service, b"aws4_request", hashlib.sha256).digest()
        return k_signing

    def _handle_error_response(
        self,
        response: httpx.Response,
        operation: str,
    ) -> None:
        """处理错误响应，区分可重试和不可重试错误。

        Args:
            response: HTTP 响应。
            operation: 操作名称。

        Raises:
            RetryablePushError: 429 或 5xx 错误。
            PermanentPushError: 400 错误。
        """
        status_code = response.status_code
        error_body = response.text
        error_msg = f"Amazon {operation} failed: status={status_code}, body={error_body}"
        logger.error(error_msg)

        if status_code == 429:
            raise RetryablePushError(error_msg)

        if status_code >= 500:
            raise RetryablePushError(error_msg)

        if status_code == 400:
            raise PermanentPushError(error_msg)

        # 其他错误码视为不可重试
        raise PermanentPushError(error_msg)

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict[str, Any]:
        """安全解析 JSON 响应。

        Args:
            response: HTTP 响应。

        Returns:
            解析后的字典，失败时返回空字典。
        """
        try:
            return response.json()
        except Exception:
            return {}
