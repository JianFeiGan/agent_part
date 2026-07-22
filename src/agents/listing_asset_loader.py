"""刊登资产加载器。

Description:
    根据视觉商品的 product_id 从 generated_assets 表拉取 AI 生成图片，
    构造 ImageRef 列表填充到 ListingProduct.source_images，
    使刊登工作流的 AssetOptimizerAgent 能直接消费 AI 生成图。
@author ganjianfei
@version 1.0.0
2026-07-22
"""

import logging
from typing import Any

from src.db.asset_repository import AssetRepository
from src.models.listing import ImageRef

logger = logging.getLogger(__name__)


class ListingAssetLoader:
    """刊登资产加载器。

    从 generated_assets 表按 product_id 拉取图片资产，
    构造 ImageRef 列表。

    Attributes:
        _repo: AssetRepository 实例。
    """

    def __init__(self, *, repo: AssetRepository | Any = None, session: Any = None) -> None:
        """初始化。

        Args:
            repo: 可选的 AssetRepository 实例（测试注入）。
            session: 可选的数据库会话。
        """
        if repo is not None:
            self._repo = repo
        elif session is not None:
            self._repo = AssetRepository(session)
        else:
            raise ValueError("必须提供 repo 或 session")

    async def load_images(
        self, *, tenant_id: str, product_id: str, limit: int = 10
    ) -> list[ImageRef]:
        """拉取商品的 AI 生成图片。

        优先将 image_type=main 的资产作为主图，其余作为变体图。
        仅返回 asset_type=image 的资产。

        Args:
            tenant_id: 租户 ID。
            product_id: 视觉商品 ID。
            limit: 最大返回数量。

        Returns:
            ImageRef 列表，第一张为主图。
        """
        assets = await self._repo.list_by_product(tenant_id, product_id)
        image_assets = [a for a in assets if a.asset_type == "image"]

        if not image_assets:
            logger.info(f"商品 {product_id} 无 AI 生成图片资产")
            return []

        # image_type=main 优先排前
        image_assets.sort(
            key=lambda a: 0 if (a.extra_data or {}).get("image_type") == "main" else 1
        )
        image_assets = image_assets[:limit]

        refs: list[ImageRef] = []
        for i, asset in enumerate(image_assets):
            refs.append(
                ImageRef(
                    url=asset.url,
                    is_main=(i == 0),
                    width=asset.width,
                    height=asset.height,
                    file_size=asset.file_size,
                )
            )
        logger.info(f"商品 {product_id} 加载 {len(refs)} 张 AI 生成图片")
        return refs
