"""AI 文案生成器 LLM 集成测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.listing_copywriter import AICopywritingAgent, LLMProvider
from src.graph.listing_state import ListingState
from src.models.listing import ListingProduct, Platform


@pytest.fixture
def product() -> ListingProduct:
    return ListingProduct(
        sku="LLM-TEST-001",
        title="Wireless Bluetooth Headphones",
        description="Premium wireless headphones with noise cancellation. "
                    "Long battery life up to 30 hours. Comfortable over-ear design.",
        category="Electronics",
        brand="SoundMax",
    )


@pytest.fixture
def state(product: ListingProduct) -> ListingState:
    return ListingState(
        product=product,
        target_platforms=[Platform.AMAZON, Platform.EBAY],
    )


class TestAICopywritingAgent:
    """测试 AI 文案生成器。"""

    @pytest.fixture
    def agent(self) -> AICopywritingAgent:
        return AICopywritingAgent()

    def test_llm_provider_enum(self) -> None:
        """测试 LLM 枚举。"""
        assert LLMProvider.TONGYI.value == "tongyi"
        assert LLMProvider.CLAUDE.value == "claude"
        assert LLMProvider.FALLBACK.value == "fallback"

    @pytest.mark.asyncio
    async def test_execute_with_llm(self, agent: AICopywritingAgent, state: ListingState) -> None:
        """测试使用 LLM 生成文案。"""
        # Mock LLM 返回
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="AI Optimized Title"))
        agent._llm = mock_llm

        result = await agent.execute(state)

        assert "copywriting_packages" in result
        assert Platform.AMAZON in result["copywriting_packages"]
        assert Platform.EBAY in result["copywriting_packages"]

        amazon_copy = result["copywriting_packages"][Platform.AMAZON]
        assert amazon_copy.platform == Platform.AMAZON
        assert amazon_copy.title != ""

    @pytest.mark.asyncio
    async def test_llm_fallback_to_rules(self, agent: AICopywritingAgent, state: ListingState) -> None:
        """测试 LLM 调用失败时降级到规则模式。"""
        agent._llm = AsyncMock()
        agent._llm.ainvoke = AsyncMock(side_effect=Exception("LLM API error"))

        # 应该降级到规则模式，不抛异常
        result = await agent.execute(state)
        assert "copywriting_packages" in result
        assert len(result["copywriting_packages"]) == 2  # Amazon + eBay

    @pytest.mark.asyncio
    async def test_generate_title_truncation(self, agent: AICopywritingAgent, product: ListingProduct) -> None:
        """测试标题截断。"""
        from src.agents.listing_platform_specs import get_platform_spec

        amazon_spec = get_platform_spec(Platform.AMAZON)
        title = agent._generate_title(product, amazon_spec)
        assert len(title) <= amazon_spec.max_title_length

    @pytest.mark.asyncio
    async def test_generate_bullet_points_limit(self, agent: AICopywritingAgent, product: ListingProduct) -> None:
        """测试五点描述数量限制。"""
        bullets = agent._generate_bullet_points(product, Platform.AMAZON)
        assert len(bullets) <= 5

    @pytest.mark.asyncio
    async def test_no_product_returns_empty(self, agent: AICopywritingAgent) -> None:
        """测试无商品返回空。"""
        empty_state = ListingState(product=None, target_platforms=[Platform.AMAZON])
        result = await agent.execute(empty_state)
        assert result["copywriting_packages"] == {}
