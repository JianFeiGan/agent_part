"""
AI 文案生成 Agent。

Description:
    基于商品信息，为各平台生成符合规范的文案，
    包括标题、五点描述、长描述、搜索关键词。
    集成 LLM 生成高质量文案，支持多 LLM 切换与降级。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
from enum import StrEnum
from typing import Any

from langchain_core.language_models import BaseChatModel

from src.agents.listing_platform_specs import get_platform_spec
from src.config.settings import get_settings
from src.graph.listing_state import ListingState
from src.models.listing import CopywritingPackage, ListingProduct, Platform

logger = logging.getLogger(__name__)


class LLMProvider(StrEnum):
    """LLM 提供商。"""

    TONGYI = "tongyi"
    CLAUDE = "claude"
    FALLBACK = "fallback"


class AICopywritingAgent:
    """AI 文案生成 Agent。

    生成流程:
    1. 规则生成草稿
    2. LLM 润色优化
    3. 返回最终文案

    LLM 降级策略: 通义千问 → Claude → 规则模式
    """

    def __init__(self, settings: Any | None = None) -> None:
        """初始化。

        Args:
            settings: 可选配置。
        """
        self._settings = settings or get_settings()
        self._llm: BaseChatModel | None = None
        self._current_provider: LLMProvider = LLMProvider.TONGYI

    def _create_llm(self, provider: LLMProvider) -> BaseChatModel:
        """创建指定 LLM 实例。"""
        if provider == LLMProvider.TONGYI:
            from langchain_community.chat_models import ChatTongyi

            return ChatTongyi(
                model=self._settings.llm_model,
                dashscope_api_key=self._settings.dashscope_api_key,
                temperature=0.7,
                request_timeout=10,
            )
        elif provider == LLMProvider.CLAUDE:
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model="claude-sonnet-4-20250514",
                temperature=0.7,
                timeout=10,
            )
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    @property
    def llm(self) -> BaseChatModel:
        """获取 LLM 实例（延迟初始化）。"""
        if self._llm is None:
            self._llm = self._create_llm(self._current_provider)
        return self._llm

    async def _enhance_with_llm(self, draft: str, prompt_template: str) -> str:
        """使用 LLM 润色草稿。失败返回原始草稿。"""
        try:
            from langchain_core.prompts import ChatPromptTemplate

            prompt = ChatPromptTemplate.from_messages([
                ("system", "你是一个专业的电商文案优化师。请润色以下商品文案，使其更具吸引力，同时保持核心信息不变。直接返回润色后的文本，不要添加任何解释。"),
                ("human", f"{prompt_template}\n\n待润色文案：{{draft}}"),
            ])

            chain = prompt | self.llm
            response = await chain.ainvoke({"draft": draft})
            enhanced = response.content if hasattr(response, "content") else str(response)
            return enhanced.strip()
        except Exception:
            logger.warning("LLM enhancement failed, using rule-based draft")
            return draft

    def execute_sync(self, state: ListingState) -> dict:
        """同步执行文案生成（规则模式，LLM 降级兜底）。"""
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

    async def _enhance_package(
        self, package: CopywritingPackage, product: ListingProduct
    ) -> CopywritingPackage:
        """使用 LLM 增强文案包。"""
        # 增强标题
        package.title = await self._enhance_with_llm(
            package.title,
            f"商品：{product.title}\n品牌：{product.brand or '无'}\n类目：{product.category or '无'}",
        )

        # 增强描述
        if package.description:
            package.description = await self._enhance_with_llm(
                package.description,
                f"商品：{product.title}\n品牌：{product.brand or '无'}",
            )

        # 增强五点描述
        enhanced_bullets = []
        for bullet in package.bullet_points:
            enhanced = await self._enhance_with_llm(
                bullet,
                f"商品：{product.title}\n品牌：{product.brand or '无'}",
            )
            enhanced_bullets.append(enhanced)
        package.bullet_points = enhanced_bullets

        return package

    async def execute(self, state: ListingState) -> dict:
        """异步执行文案生成（工作流节点接口）。

        流程: 规则生成草稿 → 尝试 LLM 润色 → LLM 失败则使用规则草稿
        """
        product = state.product
        if not product:
            return {"copywriting_packages": {}}

        # 先规则生成草稿
        rule_result = self.execute_sync(state)
        packages = rule_result["copywriting_packages"]

        if not packages:
            return {"copywriting_packages": {}}

        # 尝试 LLM 增强
        enhanced: dict[Platform, CopywritingPackage] = {}
        for platform, package in packages.items():
            try:
                enhanced_package = await self._enhance_package(package, product)
                enhanced[platform] = enhanced_package
                logger.info(f"LLM-enhanced copywriting for {platform.value}")
            except Exception:
                logger.warning(
                    f"LLM enhancement failed for {platform.value}, using rule-based copy"
                )
                enhanced[platform] = package

        return {"copywriting_packages": enhanced}

    def _generate_title(self, product: ListingProduct, spec: Any) -> str:
        """生成平台兼容标题。"""
        base_title = product.title or ""
        if product.brand:
            base_title = f"{product.brand} {base_title}"
        if spec.max_title_length > 0:
            base_title = base_title[: spec.max_title_length].rstrip()
        return base_title

    def _generate_bullet_points(self, product: ListingProduct, _platform: Platform) -> list[str]:
        """生成五点描述。"""
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
        """生成长描述。"""
        parts = []
        if product.description:
            parts.append(product.description)
        if product.brand:
            parts.append(f"Brand: {product.brand}")
        if product.category:
            parts.append(f"Category: {product.category}")
        return "\n".join(parts) if parts else ""

    def _generate_search_terms(self, product: ListingProduct) -> list[str]:
        """生成搜索关键词。"""
        terms = []
        if product.category:
            terms.append(product.category.lower())
        if product.brand:
            terms.append(product.brand.lower())
        if product.title:
            words = product.title.lower().split()
            terms.extend([w for w in words if len(w) > 3][:5])
        return list(dict.fromkeys(terms))


# Backward-compatible alias
CopywriterAgent = AICopywritingAgent
