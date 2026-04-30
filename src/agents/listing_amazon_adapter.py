"""
Amazon SP-API 刊登适配器。

Description:
    实现 Amazon Selling Partner API 的刊登推送。
    包含 LWA OAuth2 认证 + AWS SigV4 签名（框架）。
    Phase 3-5 使用 HTTP 请求模拟，后续替换为真实 SP-API SDK。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
from dataclasses import asdict
from typing import Any

import requests

from src.agents.listing_platform_adapter import BasePlatformAdapter, PushResult
from src.agents.listing_platform_specs import AMAZON_SPEC
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


class AmazonAdapter(BasePlatformAdapter):
    """Amazon SP-API 刊登适配器。

    负责与 Amazon Selling Partner API 交互，包括：
    - LWA (Login with Amazon) OAuth2 认证
    - 素材格式转换
    - 文案格式转换
    - 刊登推送/更新/删除

    Attributes:
        _config: 平台配置（client_id, client_secret, refresh_token 等）。
        _auth_token: LWA 访问令牌。
    """

    def authenticate(self) -> str:
        """执行 LWA OAuth2 认证，获取访问令牌。

        使用 client_credentials 或 refresh_token 方式交换令牌。

        Returns:
            LWA 访问令牌字符串。

        Raises:
            RuntimeError: 认证失败时抛出。
        """
        client_id = self._config.get("client_id", "")
        client_secret = self._config.get("client_secret", "")
        refresh_token = self._config.get("refresh_token", "")

        payload = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }

        response = requests.post(LWA_TOKEN_URL, data=payload)

        if response.status_code != 200:
            error_msg = (
                f"LWA authentication failed: status={response.status_code}, body={response.text}"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        token_data = response.json()
        self._auth_token = token_data["access_token"]
        logger.info("LWA authentication successful")
        return self._auth_token

    def transform_assets(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
    ) -> dict[str, Any]:
        """将素材转换为 Amazon 要求的格式。

        Args:
            product: 源商品。
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

    def transform_copywriting(
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

    def push_listing(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        task: ListingTask,
    ) -> PushResult:
        """推送新刊登到 Amazon。

        Args:
            product: 源商品。
            asset_package: 优化后的素材。
            copywriting: 优化后的文案。
            task: 刊登任务。

        Returns:
            推送结果。
        """
        try:
            # 确保已认证
            if not self._auth_token:
                self.authenticate()

            marketplace_id = self._config.get("marketplace_id", DEFAULT_MARKETPLACE_ID)
            sku = product.sku
            url = f"{SP_API_BASE_URL}/listings/{LISTINGS_API_VERSION}/items/{marketplace_id}/{sku}"

            # 构建 payload
            assets = self.transform_assets(product, asset_package)
            copy = self.transform_copywriting(copywriting)
            payload = {
                "attributes": {
                    "item_name": [{"value": copy["title"], "language_tag": "en_US"}],
                    "bullet_point": [
                        {"value": bp, "language_tag": "en_US"} for bp in copy["bullet_points"]
                    ],
                    "product_description": [
                        {"value": copy["description"], "language_tag": "en_US"}
                    ],
                    "generic_keyword": [
                        {"value": " ".join(copy["search_terms"]), "language_tag": "en_US"}
                    ],
                    "main_image": [
                        {"value": img, "language_tag": "en_US"} for img in assets["images"][:1]
                    ],
                },
            }

            headers = {
                "Authorization": f"Bearer {self._auth_token}",
                "Content-Type": "application/json",
                "x-amz-access-token": self._auth_token,
            }

            response = requests.post(url, json=payload, headers=headers)

            if response.status_code in (200, 201):
                data = response.json()
                listing_id = data.get("listingId", sku)
                return PushResult(
                    success=True,
                    platform=Platform.AMAZON,
                    listing_id=listing_id,
                    url=f"https://www.amazon.com/dp/{listing_id}",
                    raw_response=data,
                )

            error_msg = (
                f"Amazon push_listing failed: status={response.status_code}, body={response.text}"
            )
            logger.error(error_msg)
            return PushResult(
                success=False,
                platform=Platform.AMAZON,
                error=error_msg,
                raw_response=self._safe_json(response),
            )

        except RuntimeError:
            raise
        except Exception as e:
            error_msg = f"Amazon push_listing error: {e}"
            logger.exception(error_msg)
            return PushResult(
                success=False,
                platform=Platform.AMAZON,
                error=error_msg,
            )

    def update_listing(
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
            if not self._auth_token:
                self.authenticate()

            marketplace_id = self._config.get("marketplace_id", DEFAULT_MARKETPLACE_ID)
            sku = product.sku
            url = f"{SP_API_BASE_URL}/listings/{LISTINGS_API_VERSION}/items/{marketplace_id}/{sku}"

            assets = self.transform_assets(product, asset_package)
            copy = self.transform_copywriting(copywriting)
            payload = {
                "attributes": {
                    "item_name": [{"value": copy["title"], "language_tag": "en_US"}],
                    "bullet_point": [
                        {"value": bp, "language_tag": "en_US"} for bp in copy["bullet_points"]
                    ],
                    "product_description": [
                        {"value": copy["description"], "language_tag": "en_US"}
                    ],
                },
            }

            headers = {
                "Authorization": f"Bearer {self._auth_token}",
                "Content-Type": "application/json",
                "x-amz-access-token": self._auth_token,
            }

            response = requests.put(url, json=payload, headers=headers)

            if response.status_code in (200, 201):
                data = response.json()
                return PushResult(
                    success=True,
                    platform=Platform.AMAZON,
                    listing_id=listing_id,
                    raw_response=data,
                )

            error_msg = (
                f"Amazon update_listing failed: status={response.status_code}, body={response.text}"
            )
            logger.error(error_msg)
            return PushResult(
                success=False,
                platform=Platform.AMAZON,
                error=error_msg,
                raw_response=self._safe_json(response),
            )

        except RuntimeError:
            raise
        except Exception as e:
            error_msg = f"Amazon update_listing error: {e}"
            logger.exception(error_msg)
            return PushResult(
                success=False,
                platform=Platform.AMAZON,
                error=error_msg,
            )

    def delete_listing(self, listing_id: str) -> PushResult:
        """删除 Amazon 已有刊登。

        Args:
            listing_id: 平台刊登ID。

        Returns:
            删除结果。
        """
        try:
            if not self._auth_token:
                self.authenticate()

            marketplace_id = self._config.get("marketplace_id", DEFAULT_MARKETPLACE_ID)
            url = (
                f"{SP_API_BASE_URL}/listings/{LISTINGS_API_VERSION}"
                f"/items/{marketplace_id}/{listing_id}"
            )

            headers = {
                "Authorization": f"Bearer {self._auth_token}",
                "x-amz-access-token": self._auth_token,
            }

            response = requests.delete(url, headers=headers)

            if response.status_code in (200, 204):
                return PushResult(
                    success=True,
                    platform=Platform.AMAZON,
                    listing_id=listing_id,
                    raw_response=self._safe_json(response),
                )

            error_msg = (
                f"Amazon delete_listing failed: status={response.status_code}, body={response.text}"
            )
            logger.error(error_msg)
            return PushResult(
                success=False,
                platform=Platform.AMAZON,
                error=error_msg,
                raw_response=self._safe_json(response),
            )

        except RuntimeError:
            raise
        except Exception as e:
            error_msg = f"Amazon delete_listing error: {e}"
            logger.exception(error_msg)
            return PushResult(
                success=False,
                platform=Platform.AMAZON,
                error=error_msg,
            )

    @staticmethod
    def _safe_json(response: requests.Response) -> dict[str, Any]:
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
