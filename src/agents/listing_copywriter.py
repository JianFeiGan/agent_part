"""
文案生成 Agent。

Description:
    基于商品信息，为各平台生成符合规范的文案，
    包括标题、五点描述、长描述、搜索关键词。
    当前阶段使用规则生成，后续接入 LLM 优化。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
from typing import Any

from src.agents.listing_platform_specs import get_platform_spec
from src.graph.listing_state import ListingState
from src.models.listing import CopywritingPackage, ListingProduct, Platform

logger = logging.getLogger(__name__)


class CopywriterAgent:
    """文案生成 Agent。

    为每个目标平台生成标准化文案包。
    当前阶段：基于规则生成基础文案。
    后续阶段：接入 LLM 生成更优质的文案。

    Attributes:
        _settings: 可选配置对象。

    Example:
        >>> agent = CopywriterAgent()
        >>> state = ListingState(product=product, target_platforms=[Platform.AMAZON])
        >>> result = agent.execute_sync(state)
        >>> assert Platform.AMAZON in result["copywriting_packages"]
    """

    def __init__(self, settings: Any | None = None) -> None:
        """初始化文案生成 Agent。

        Args:
            settings: 可选配置。
        """
        self._settings = settings

    def execute_sync(self, state: ListingState) -> dict:
        """同步执行文案生成。

        Args:
            state: 工作流状态，包含 product 和 target_platforms。

        Returns:
            包含 copywriting_packages 的字典。
        """
        product = state.product
        if not product:
            return {"copywriting_packages": {}}

        copywriting_packages: dict[Platform, CopywritingPackage] = {}

        for platform in state.target_platforms:
            spec = get_platform_spec(platform)
            logger.info(f"生成文案: platform={platform.value}")

            title = self._generate_title(product, spec)
            bullet_points = self._generate_bullet_points(product, platform)
            description = self._generate_description(product)
            search_terms = self._generate_search_terms(product)

            copywriting_packages[platform] = CopywritingPackage(
                listing_task_id=0,
                platform=platform,
                language="en",
                title=title,
                bullet_points=bullet_points,
                description=description,
                search_terms=search_terms,
            )

        return {"copywriting_packages": copywriting_packages}

    def _generate_title(self, product: ListingProduct, spec: Any) -> str:
        """生成平台兼容标题。

        Args:
            product: 商品信息。
            spec: 平台规范。

        Returns:
            符合平台长度限制的标题。
        """
        base_title = product.title or ""
        if product.brand:
            base_title = f"{product.brand} {base_title}"
        if spec.max_title_length > 0:
            base_title = base_title[: spec.max_title_length].rstrip()
        return base_title

    def _generate_bullet_points(self, product: ListingProduct, _platform: Platform) -> list[str]:
        """生成五点描述。

        Args:
            product: 商品信息。
            platform: 目标平台。

        Returns:
            不超过5条的卖点列表。
        """
        bullets = []
        desc = product.description or ""
        if desc:
            sentences = [s.strip() for s in desc.replace(".", "\n").split("\n") if s.strip()]
            bullets = sentences[:5]
        if not bullets:
            bullets = [f"Premium quality {product.category or 'product'}"]
            if product.brand:
                bullets.append(f"Brand: {product.brand}")
        return bullets[:5]

    def _generate_description(self, product: ListingProduct) -> str:
        """生成长描述。

        Args:
            product: 商品信息。

        Returns:
            商品详细描述文本。
        """
        parts = []
        if product.description:
            parts.append(product.description)
        if product.brand:
            parts.append(f"Brand: {product.brand}")
        if product.category:
            parts.append(f"Category: {product.category}")
        return "\n".join(parts) if parts else ""

    def _generate_search_terms(self, product: ListingProduct) -> list[str]:
        """生成搜索关键词。

        Args:
            product: 商品信息。

        Returns:
            唯一的搜索关键词列表。
        """
        terms = []
        if product.category:
            terms.append(product.category.lower())
        if product.brand:
            terms.append(product.brand.lower())
        if product.title:
            words = product.title.lower().split()
            terms.extend([w for w in words if len(w) > 3][:5])
        return list(dict.fromkeys(terms))

    async def execute(self, state: ListingState) -> dict:
        """异步执行（工作流节点接口）。

        Args:
            state: 工作流状态。

        Returns:
            包含 copywriting_packages 的字典。
        """
        return self.execute_sync(state)
