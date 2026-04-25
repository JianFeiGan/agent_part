"""
素材优化 Agent。

Description:
    根据各平台规范，对原始图片进行裁剪、压缩、格式转换，
    生成符合平台要求的素材包。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
from typing import Any

from src.agents.listing_platform_specs import get_platform_spec
from src.graph.listing_state import ListingState
from src.models.listing import AssetPackage, Platform

logger = logging.getLogger(__name__)


class AssetOptimizerAgent:
    """素材优化 Agent。

    为每个目标平台生成标准化素材包。
    当前阶段：传递原始图片路径，标记平台规范信息。
    后续阶段：集成 Pillow 进行实际图片处理。

    Attributes:
        _settings: 可选配置对象。

    Example:
        >>> agent = AssetOptimizerAgent()
        >>> state = ListingState(product=product, target_platforms=[Platform.AMAZON])
        >>> result = agent.execute_sync(state)
        >>> assert Platform.AMAZON in result["asset_packages"]
    """

    def __init__(self, settings: Any | None = None) -> None:
        """初始化素材优化 Agent。

        Args:
            settings: 可选配置。
        """
        self._settings = settings

    def execute_sync(self, state: ListingState) -> dict:
        """同步执行素材优化。

        Args:
            state: 工作流状态，包含 product 和 target_platforms。

        Returns:
            包含 asset_packages 的字典。
        """
        product = state.product
        if not product:
            return {"asset_packages": {}}

        asset_packages: dict[Platform, AssetPackage] = {}

        for platform in state.target_platforms:
            spec = get_platform_spec(platform)
            logger.info(f"优化素材: platform={platform.value}, spec={spec}")

            main_image = None
            variant_images = []

            if product.source_images:
                main = product.main_image
                if main:
                    main_image = main.url

                for img in product.source_images:
                    if not img.is_main and img.url != main_image:
                        variant_images.append(img.url)
                        if len(variant_images) >= spec.max_images - 1:
                            break

            asset_packages[platform] = AssetPackage(
                listing_task_id=0,
                platform=platform,
                main_image=main_image,
                variant_images=variant_images[: spec.max_images - 1],
            )

        return {"asset_packages": asset_packages}

    async def execute(self, state: ListingState) -> dict:
        """异步执行（工作流节点接口）。

        Args:
            state: 工作流状态。

        Returns:
            包含 asset_packages 的字典。
        """
        return self.execute_sync(state)