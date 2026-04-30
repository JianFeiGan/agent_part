"""
商品导入 Agent。

Description:
    从手动录入或外部系统导入商品信息，
    标准化为 ListingProduct 模型。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
from typing import Any

from src.models.listing import ImageRef, ListingProduct

logger = logging.getLogger(__name__)


class ImportProductAgent:
    """商品导入 Agent。

    负责将原始商品数据标准化为 ListingProduct。
    支持手动录入和后续扩展的平台 API 导入。

    Attributes:
        _settings: 可选配置对象。

    Example:
        >>> agent = ImportProductAgent()
        >>> result = agent.execute_manual({"sku": "T-001", "title": "Test"})
        >>> assert result["success"]
    """

    def __init__(self, settings: Any | None = None) -> None:
        """初始化商品导入 Agent。

        Args:
            settings: 可选配置。
        """
        self._settings = settings

    def execute_manual(self, product_data: dict[str, Any]) -> dict:
        """手动录入商品。

        Args:
            product_data: 商品原始数据字典，必须包含 sku 和 title。

        Returns:
            包含 success/product/error 的字典。
        """
        sku = product_data.get("sku", "").strip()
        title = product_data.get("title", "").strip()

        if not sku:
            return {"success": False, "error": "sku is required", "product": None}
        if not title:
            return {"success": False, "error": "title is required", "product": None}

        source_images = []
        for img_data in product_data.get("source_images", []):
            source_images.append(
                ImageRef(
                    url=img_data.get("url", ""),
                    is_main=img_data.get("is_main", False),
                    width=img_data.get("width"),
                    height=img_data.get("height"),
                )
            )

        product = ListingProduct(
            sku=sku,
            title=title,
            description=product_data.get("description"),
            category=product_data.get("category"),
            brand=product_data.get("brand"),
            price=product_data.get("price"),
            weight=product_data.get("weight"),
            dimensions=product_data.get("dimensions"),
            source_images=source_images,
            attributes=product_data.get("attributes", {}),
        )

        logger.info(f"商品导入成功: sku={sku}, title={title}")
        return {"success": True, "product": product, "error": None}

    async def execute(self, state: Any) -> dict:
        """工作流节点执行方法（兼容性接口）。

        Args:
            state: 工作流状态对象。

        Returns:
            包含 product 和 current_step 的字典。
        """
        return {"product": state.product, "current_step": "imported"}
