"""
eBay Trading API 刊登适配器。

Description:
    实现 eBay Trading API 的刊登推送。
    使用 OAuth2 认证 + XML 格式请求。
    Phase 3-5 使用 HTTP 请求模拟，后续可接入真实 eBay SDK。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
import xml.etree.ElementTree as ET
from typing import Any

import requests

from src.agents.listing_platform_adapter import BasePlatformAdapter, PushResult
from src.models.listing import (
    AssetPackage,
    CopywritingPackage,
    ListingProduct,
    ListingTask,
    Platform,
)

logger = logging.getLogger(__name__)

# eBay Trading API 常量
EBAY_OAUTH_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_TRADING_API_URL = "https://api.ebay.com/ws/api.dll"
EBAY_XML_NS = "urn:ebay:apis:eBLBaseComponents"
DEFAULT_SITE_ID = "0"  # US Site
DEFAULT_CURRENCY = "USD"
EBAY_MAX_TITLE_LENGTH = 80


class EbayAdapter(BasePlatformAdapter):
    """eBay Trading API 刊登适配器。

    负责与 eBay Trading API 交互，包括：
    - OAuth2 认证（refresh_token 方式）
    - XML 格式素材/文案转换
    - 刊登推送/更新/删除（AddItem / ReviseItem / EndItem）

    Attributes:
        _config: 平台配置（client_id, client_secret, refresh_token 等）。
        _auth_token: OAuth2 访问令牌。
    """

    def authenticate(self) -> str:
        """执行 eBay OAuth2 认证，获取访问令牌。

        使用 refresh_token 方式交换访问令牌。

        Returns:
            OAuth2 访问令牌字符串。

        Raises:
            RuntimeError: 认证失败时抛出。
        """
        client_id = self._config.get("client_id", "")
        client_secret = self._config.get("client_secret", "")
        refresh_token = self._config.get("refresh_token", "")

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }

        response = requests.post(EBAY_OAUTH_TOKEN_URL, data=payload)

        if response.status_code != 200:
            error_msg = (
                f"eBay OAuth2 authentication failed: "
                f"status={response.status_code}, body={response.text}"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        token_data = response.json()
        self._auth_token = token_data["access_token"]
        logger.info("eBay OAuth2 authentication successful")
        return self._auth_token

    def transform_assets(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
    ) -> dict[str, Any]:
        """将素材转换为 eBay 要求的格式。

        Args:
            product: 源商品。
            asset_package: 优化后的素材包。

        Returns:
            eBay 要求的素材格式 {"pictures": [...]}。
        """
        pictures: list[str] = []

        if asset_package.main_image:
            pictures.append(asset_package.main_image)

        for img_url in asset_package.variant_images:
            pictures.append(img_url)

        # eBay 最多支持 12 张图片
        pictures = pictures[:12]

        return {"pictures": pictures}

    def transform_copywriting(
        self,
        copywriting: CopywritingPackage,
    ) -> dict[str, Any]:
        """将文案转换为 eBay 要求的格式。

        - 标题截断到 80 字符（eBay 限制）。
        - bullet_points 包装为 HTML 列表。

        Args:
            copywriting: 优化后的文案。

        Returns:
            eBay 要求的文案格式。
        """
        title = copywriting.title[:EBAY_MAX_TITLE_LENGTH]

        # 将 bullet points 包装为 HTML 列表
        bullet_html = ""
        if copywriting.bullet_points:
            items = "".join(
                f"<li>{self._escape_xml(bp)}</li>"
                for bp in copywriting.bullet_points
            )
            bullet_html = f"<ul>{items}</ul>"

        return {
            "title": title,
            "bullet_points_html": bullet_html,
            "description": copywriting.description,
            "search_terms": copywriting.search_terms,
        }

    def push_listing(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        task: ListingTask,
    ) -> PushResult:
        """推送新刊登到 eBay。

        Args:
            product: 源商品。
            asset_package: 优化后的素材。
            copywriting: 优化后的文案。
            task: 刊登任务。

        Returns:
            推送结果。
        """
        try:
            if not self._auth_token:
                self.authenticate()

            assets = self.transform_assets(product, asset_package)
            copy = self.transform_copywriting(copywriting)

            xml_body = self._build_add_item_xml(
                product, assets, copy, task
            )

            headers = self._build_trading_headers("AddItem")

            response = requests.post(
                EBAY_TRADING_API_URL,
                data=xml_body.encode("utf-8"),
                headers=headers,
            )

            ack, item_id, errors = self._parse_xml_response(response.text)

            if ack == "Success":
                return PushResult(
                    success=True,
                    platform=Platform.EBAY,
                    listing_id=item_id,
                    url=f"https://www.ebay.com/itm/{item_id}" if item_id else None,
                    raw_response={"Ack": ack, "ItemID": item_id},
                )

            error_msg = "; ".join(errors) if errors else "eBay AddItem failed"
            logger.error(f"eBay push_listing failed: {error_msg}")
            return PushResult(
                success=False,
                platform=Platform.EBAY,
                error=error_msg,
                raw_response={"Ack": ack, "Errors": errors},
            )

        except RuntimeError:
            raise
        except Exception as e:
            error_msg = f"eBay push_listing error: {e}"
            logger.exception(error_msg)
            return PushResult(
                success=False,
                platform=Platform.EBAY,
                error=error_msg,
            )

    def update_listing(
        self,
        listing_id: str,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> PushResult:
        """更新 eBay 已有刊登。

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

            assets = self.transform_assets(product, asset_package)
            copy = self.transform_copywriting(copywriting)

            xml_body = self._build_revise_item_xml(
                product, assets, copy, listing_id
            )

            headers = self._build_trading_headers("ReviseItem")

            response = requests.post(
                EBAY_TRADING_API_URL,
                data=xml_body.encode("utf-8"),
                headers=headers,
            )

            ack, item_id, errors = self._parse_xml_response(response.text)

            if ack == "Success":
                return PushResult(
                    success=True,
                    platform=Platform.EBAY,
                    listing_id=item_id or listing_id,
                    raw_response={"Ack": ack, "ItemID": item_id},
                )

            error_msg = "; ".join(errors) if errors else "eBay ReviseItem failed"
            logger.error(f"eBay update_listing failed: {error_msg}")
            return PushResult(
                success=False,
                platform=Platform.EBAY,
                error=error_msg,
                raw_response={"Ack": ack, "Errors": errors},
            )

        except RuntimeError:
            raise
        except Exception as e:
            error_msg = f"eBay update_listing error: {e}"
            logger.exception(error_msg)
            return PushResult(
                success=False,
                platform=Platform.EBAY,
                error=error_msg,
            )

    def delete_listing(self, listing_id: str) -> PushResult:
        """删除 eBay 已有刊登。

        Args:
            listing_id: 平台刊登ID。

        Returns:
            删除结果。
        """
        try:
            if not self._auth_token:
                self.authenticate()

            xml_body = self._build_end_item_xml(listing_id)

            headers = self._build_trading_headers("EndItem")

            response = requests.post(
                EBAY_TRADING_API_URL,
                data=xml_body.encode("utf-8"),
                headers=headers,
            )

            ack, item_id, errors = self._parse_xml_response(response.text)

            if ack == "Success":
                return PushResult(
                    success=True,
                    platform=Platform.EBAY,
                    listing_id=listing_id,
                    raw_response={"Ack": ack, "ItemID": item_id},
                )

            error_msg = "; ".join(errors) if errors else "eBay EndItem failed"
            logger.error(f"eBay delete_listing failed: {error_msg}")
            return PushResult(
                success=False,
                platform=Platform.EBAY,
                error=error_msg,
                raw_response={"Ack": ack, "Errors": errors},
            )

        except RuntimeError:
            raise
        except Exception as e:
            error_msg = f"eBay delete_listing error: {e}"
            logger.exception(error_msg)
            return PushResult(
                success=False,
                platform=Platform.EBAY,
                error=error_msg,
            )

    # ------------------------------------------------------------------
    # XML 构建辅助方法
    # ------------------------------------------------------------------

    def _build_add_item_xml(
        self,
        product: ListingProduct,
        assets: dict[str, Any],
        copy: dict[str, Any],
        task: ListingTask,
    ) -> str:
        """构建 AddItem XML 请求。

        Args:
            product: 源商品。
            assets: 转换后的素材。
            copy: 转换后的文案。
            task: 刊登任务。

        Returns:
            XML 字符串。
        """
        site_id = self._config.get("site_id", DEFAULT_SITE_ID)
        price = str(product.price) if product.price else "0.00"
        category = self._escape_xml(product.category or "Other")

        pictures_xml = self._build_pictures_xml(assets["pictures"])

        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<AddItemRequest xmlns="{EBAY_XML_NS}">
  <RequesterCredentials>
    <eBayAuthToken>{self._escape_xml(self._auth_token or "")}</eBayAuthToken>
  </RequesterCredentials>
  <ErrorLanguage>en_US</ErrorLanguage>
  <WarningLevel>High</WarningLevel>
  <Item>
    <Title>{self._escape_xml(copy["title"])}</Title>
    <Description>{self._escape_xml(copy["description"])}</Description>
    <PrimaryCategory>
      <CategoryID>{category}</CategoryID>
    </PrimaryCategory>
    <StartPrice>{price}</StartPrice>
    <Currency>{DEFAULT_CURRENCY}</Currency>
    <SKU>{self._escape_xml(product.sku)}</SKU>
    <ListingDuration>Days_30</ListingDuration>
    <Site>{site_id}</Site>
    <ListingType>FixedPriceItem</ListingType>
    <PictureDetails>
      {pictures_xml}
    </PictureDetails>
    <ConditionID>1000</ConditionID>
    <Country>US</Country>
    <ShippingDetails>
      <ShippingType>Flat</ShippingType>
    </ShippingDetails>
    <ReturnPolicy>
      <ReturnsAcceptedOption>ReturnsAccepted</ReturnsAcceptedOption>
      <RefundOption>MoneyBack</RefundOption>
      <ReturnsWithinOption>Days_30</ReturnsWithinOption>
    </ReturnPolicy>
  </Item>
</AddItemRequest>"""
        return xml

    def _build_revise_item_xml(
        self,
        product: ListingProduct,
        assets: dict[str, Any],
        copy: dict[str, Any],
        listing_id: str,
    ) -> str:
        """构建 ReviseItem XML 请求。

        Args:
            product: 源商品。
            assets: 转换后的素材。
            copy: 转换后的文案。
            listing_id: 刊登ID。

        Returns:
            XML 字符串。
        """
        price = str(product.price) if product.price else "0.00"
        category = self._escape_xml(product.category or "Other")
        pictures_xml = self._build_pictures_xml(assets["pictures"])

        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ReviseItemRequest xmlns="{EBAY_XML_NS}">
  <RequesterCredentials>
    <eBayAuthToken>{self._escape_xml(self._auth_token or "")}</eBayAuthToken>
  </RequesterCredentials>
  <ErrorLanguage>en_US</ErrorLanguage>
  <WarningLevel>High</WarningLevel>
  <Item>
    <ItemID>{self._escape_xml(listing_id)}</ItemID>
    <Title>{self._escape_xml(copy["title"])}</Title>
    <Description>{self._escape_xml(copy["description"])}</Description>
    <PrimaryCategory>
      <CategoryID>{category}</CategoryID>
    </PrimaryCategory>
    <StartPrice>{price}</StartPrice>
    <Currency>{DEFAULT_CURRENCY}</Currency>
    <SKU>{self._escape_xml(product.sku)}</SKU>
    <PictureDetails>
      {pictures_xml}
    </PictureDetails>
  </Item>
</ReviseItemRequest>"""
        return xml

    def _build_end_item_xml(self, listing_id: str) -> str:
        """构建 EndItem XML 请求。

        Args:
            listing_id: 刊登ID。

        Returns:
            XML 字符串。
        """
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<EndItemRequest xmlns="{EBAY_XML_NS}">
  <RequesterCredentials>
    <eBayAuthToken>{self._escape_xml(self._auth_token or "")}</eBayAuthToken>
  </RequesterCredentials>
  <ErrorLanguage>en_US</ErrorLanguage>
  <WarningLevel>High</WarningLevel>
  <ItemID>{self._escape_xml(listing_id)}</ItemID>
  <EndingReason>NotSpecified</EndingReason>
</EndItemRequest>"""
        return xml

    def _build_pictures_xml(self, pictures: list[str]) -> str:
        """构建图片 XML 片段。

        Args:
            pictures: 图片 URL 列表。

        Returns:
            XML 图片节点字符串。
        """
        if not pictures:
            return ""

        items = "".join(
            f"<GalleryType>Gallery</GalleryType>"
            f"<PictureURL>{self._escape_xml(url)}</PictureURL>"
            for url in pictures
        )
        return items

    @staticmethod
    def _escape_xml(text: str) -> str:
        """转义 XML 特殊字符。

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
        text = text.replace("'", "&apos;")
        return text

    def _build_trading_headers(self, call_name: str) -> dict[str, str]:
        """构建 Trading API 请求头。

        Args:
            call_name: API 调用名称（AddItem, ReviseItem, EndItem）。

        Returns:
            请求头字典。
        """
        site_id = self._config.get("site_id", DEFAULT_SITE_ID)
        return {
            "Content-Type": "text/xml",
            "X-EBAY-API-CALL-NAME": call_name,
            "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
            "X-EBAY-API-SITEID": str(site_id),
        }

    @staticmethod
    def _parse_xml_response(
        xml_text: str,
    ) -> tuple[str, str | None, list[str]]:
        """解析 eBay XML 响应。

        提取 Ack 状态、ItemID 和错误信息。

        Args:
            xml_text: XML 响应文本。

        Returns:
            (ack, item_id, errors) 三元组。
        """
        try:
            root = ET.fromstring(xml_text)

            ns = {"eBay": EBAY_XML_NS}
            bare_ns = "{" + EBAY_XML_NS + "}"

            # 提取 Ack — 优先使用 {namespace}Ack，再尝试无命名空间
            ack_elem = root.find(f".//{bare_ns}Ack")
            if ack_elem is None:
                ack_elem = root.find(".//Ack")
            ack = ack_elem.text.strip() if ack_elem is not None else "Unknown"

            # 提取 ItemID
            item_id_elem = root.find(f".//{bare_ns}ItemID")
            if item_id_elem is None:
                item_id_elem = root.find(".//ItemID")
            item_id = (
                item_id_elem.text.strip()
                if item_id_elem is not None and item_id_elem.text
                else None
            )

            # 提取错误信息
            errors: list[str] = []
            for error_elem in root.findall(f".//{bare_ns}Errors/{bare_ns}Error"):
                short_msg = error_elem.find(f"{bare_ns}ShortMessage")
                if short_msg is not None and short_msg.text:
                    errors.append(short_msg.text.strip())

            # 也尝试无命名空间的情况
            if not errors:
                for error_elem in root.findall(".//Errors/Error"):
                    short_msg = error_elem.find("ShortMessage")
                    if short_msg is not None and short_msg.text:
                        errors.append(short_msg.text.strip())

            return ack, item_id, errors

        except ET.ParseError:
            logger.exception("Failed to parse eBay XML response")
            return "Failure", None, [f"XML parse error: {xml_text[:200]}"]
