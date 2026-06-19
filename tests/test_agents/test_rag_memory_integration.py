"""
RAG Agents 类目记忆接入集成测试。

Description:
    验证 RAG Agents 在 execute() 时正确调用 retrieve_category_memory_context
    并将结果注入 prompt 的 category_memory_context 变量。
@author ganjianfei
@version 1.0.0
2026-06-19
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.rag_creative_planner import RAGEnhancedCreativePlanner
from src.agents.rag_quality_reviewer import RAGEnhancedQualityReviewer
from src.agents.rag_requirement_analyzer import RAGEnhancedRequirementAnalyzer
from src.graph.state import AgentState, GenerationRequest
from src.models.assets import AssetStatus, GeneratedImage
from src.models.product import Product, ProductCategory

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> MagicMock:
    """创建模拟数据库会话。"""
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def mock_retriever() -> MagicMock:
    """创建模拟知识检索器，返回空的常规检索结果。"""
    retriever = MagicMock()

    mock_result = MagicMock()
    mock_result.results = []

    retriever.retrieve = AsyncMock(return_value=mock_result)
    return retriever


@pytest.fixture
def sample_product() -> Product:
    """创建示例商品。"""
    return Product(
        product_id="test_mem_001",
        name="智能手表 Pro",
        brand="TechBrand",
        category=ProductCategory.DIGITAL,
        description="一款高端智能手表，支持健康监测、运动追踪等功能。",
        selling_points=[],
        specifications=[],
    )


@pytest.fixture
def sample_state(sample_product: Product) -> AgentState:
    """创建带 generation_request 的示例状态。"""
    return AgentState(
        product_info=sample_product,
        generation_request=GenerationRequest(task_id="task_001"),
    )


# ---------------------------------------------------------------------------
# Shared helper: build retriever with category memory mock
# ---------------------------------------------------------------------------


def _mock_category_memory_retriever(
    retriever: MagicMock, context_string: str
) -> MagicMock:
    """为 retriever 添加 retrieve_category_memory_context mock。

    Args:
        retriever: 被装饰的 mock retriever。
        context_string: 返回的格式化类目记忆上下文。

    Returns:
        更新后的 mock retriever。
    """
    retriever.retrieve_category_memory_context = AsyncMock(
        return_value=context_string
    )
    return retriever


# ---------------------------------------------------------------------------
# RAGEnhancedRequirementAnalyzer
# ---------------------------------------------------------------------------


class TestRequirementAnalyzerCategoryMemory:
    """验证需求分析 Agent 接入类目记忆。"""

    @pytest.mark.asyncio
    async def test_uses_category_memory_when_present(
        self,
        mock_session: MagicMock,
        mock_retriever: MagicMock,
        sample_state: AgentState,
    ) -> None:
        """当 retriever 返回类目记忆时，invoke_llm 调用应包含该上下文。"""
        memory_text = "【类目记忆：digital】\n摘要：数码产品最佳实践\n"
        _mock_category_memory_retriever(mock_retriever, memory_text)

        agent = RAGEnhancedRequirementAnalyzer(
            session=mock_session,
            retriever=mock_retriever,
        )

        with patch.object(
            agent,
            "invoke_llm",
            new_callable=AsyncMock,
            return_value='{"product_summary": "test"}',
        ) as mock_invoke:
            result = await agent.execute(sample_state)

        assert result.success is True
        call_kwargs = mock_invoke.call_args[0][1]
        assert "category_memory_context" in call_kwargs
        assert call_kwargs["category_memory_context"] == memory_text

    @pytest.mark.asyncio
    async def test_falls_back_when_no_memory(
        self,
        mock_session: MagicMock,
        mock_retriever: MagicMock,
        sample_state: AgentState,
    ) -> None:
        """当 retriever 返回空字符串时，prompt 中使用 fallback 文案。"""
        _mock_category_memory_retriever(mock_retriever, "")

        agent = RAGEnhancedRequirementAnalyzer(
            session=mock_session,
            retriever=mock_retriever,
        )

        with patch.object(
            agent,
            "invoke_llm",
            new_callable=AsyncMock,
            return_value='{"product_summary": "test"}',
        ) as mock_invoke:
            result = await agent.execute(sample_state)

        assert result.success is True
        call_kwargs = mock_invoke.call_args[0][1]
        assert call_kwargs["category_memory_context"] == "（无相关类目记忆）"

    @pytest.mark.asyncio
    async def test_no_session_returns_fallback(
        self,
        mock_retriever: MagicMock,
        sample_state: AgentState,
    ) -> None:
        """无 session 时不调用 retriever，prompt 使用 fallback。"""
        agent = RAGEnhancedRequirementAnalyzer(
            retriever=mock_retriever,
        )

        with patch.object(
            agent,
            "invoke_llm",
            new_callable=AsyncMock,
            return_value='{"product_summary": "test"}',
        ) as mock_invoke:
            result = await agent.execute(sample_state)

        assert result.success is True
        call_kwargs = mock_invoke.call_args[0][1]
        assert call_kwargs["category_memory_context"] == "（无相关类目记忆）"


# ---------------------------------------------------------------------------
# RAGEnhancedCreativePlanner
# ---------------------------------------------------------------------------


class TestCreativePlannerCategoryMemory:
    """验证创意策划 Agent 接入类目记忆。"""

    @pytest.mark.asyncio
    async def test_uses_category_memory(
        self,
        mock_session: MagicMock,
        mock_retriever: MagicMock,
        sample_state: AgentState,
    ) -> None:
        """创意策划 Agent 应在 invoke_llm 调用中包含类目记忆上下文。"""
        memory_text = "【类目记忆：digital】\n风格指南：科技蓝\n"
        _mock_category_memory_retriever(mock_retriever, memory_text)

        agent = RAGEnhancedCreativePlanner(
            session=mock_session,
            retriever=mock_retriever,
        )

        with patch.object(
            agent,
            "invoke_llm",
            new_callable=AsyncMock,
            return_value='{"theme_name": "科技先锋", "visual_style": "tech"}',
        ) as mock_invoke:
            result = await agent.execute(sample_state)

        assert result.success is True
        call_kwargs = mock_invoke.call_args[0][1]
        assert "category_memory_context" in call_kwargs
        assert call_kwargs["category_memory_context"] == memory_text


# ---------------------------------------------------------------------------
# RAGEnhancedQualityReviewer
# ---------------------------------------------------------------------------


class TestQualityReviewerCategoryMemory:
    """验证质量审核 Agent 接入类目记忆。"""

    @pytest.mark.asyncio
    async def test_uses_category_memory(
        self,
        mock_session: MagicMock,
        mock_retriever: MagicMock,
        sample_state: AgentState,
    ) -> None:
        """质量审核 Agent 应在审核图片/视频时传递类目记忆上下文。"""
        memory_text = "【类目记忆：digital】\n避坑：避免过度P图\n"
        _mock_category_memory_retriever(mock_retriever, memory_text)

        # 添加一张生成图片到状态以触发 invoke_llm

        sample_state.generated_images = [
            GeneratedImage(
                image_id="img_001",
                prompt="test prompt",
                image_type="main",
                width=1024,
                height=1024,
                status=AssetStatus.COMPLETED,
                image_url="http://example.com/img.png",
                created_at="2026-06-19T00:00:00",
            )
        ]

        agent = RAGEnhancedQualityReviewer(
            session=mock_session,
            retriever=mock_retriever,
        )

        with patch.object(
            agent,
            "invoke_llm",
            new_callable=AsyncMock,
            return_value='{"overall_score": 0.9}',
        ) as mock_invoke:
            result = await agent.execute(sample_state)

        assert result.success is True
        # invoke_llm 被调用时 category_memory_context 应在参数中
        call_kwargs = mock_invoke.call_args[0][1]
        assert "category_memory_context" in call_kwargs
        assert call_kwargs["category_memory_context"] == memory_text


# ---------------------------------------------------------------------------
# Listing Copywriter Category Memory
# ---------------------------------------------------------------------------


class TestListingCopywriterCategoryMemory:
    """验证 listing_copywriter 在平台已知时接入类目记忆。"""

    @pytest.mark.asyncio
    async def test_uses_category_memory_per_platform(self) -> None:
        """当 target_platforms 非空时，_enhance_package 应接收类目记忆上下文。"""
        from src.agents.listing_copywriter import AICopywritingAgent
        from src.graph.listing_state import ListingState
        from src.models.listing import (
            ListingProduct,
            Platform,
        )

        product = ListingProduct(
            sku="SKU-001",
            title="Test Product",
            category="Electronics",
            brand="TestBrand",
            description="A test product description.",
        )

        state = ListingState(
            product=product,
            target_platforms=[Platform.AMAZON],
        )

        agent = AICopywritingAgent()

        # Mock _retrieve_category_memory 返回固定值
        memory_text = "【类目记忆：Electronics】\n最佳实践：突出技术参数\n"

        with patch.object(
            agent,
            "_retrieve_category_memory",
            new_callable=AsyncMock,
            return_value=memory_text,
        ), patch.object(
            agent,
            "_enhance_with_llm",
            new_callable=AsyncMock,
            return_value="Enhanced text",
        ) as mock_enhance:
            result = await agent.execute(state)

        assert "copywriting_packages" in result
        # _enhance_with_llm 调用参数应包含类目记忆
        for call_args in mock_enhance.call_args_list:
            prompt_template = call_args[0][1]
            assert "类目记忆" in prompt_template

    @pytest.mark.asyncio
    async def test_no_platform_skips_memory(self) -> None:
        """无 target_platforms 时跳过类目记忆检索。"""
        from src.agents.listing_copywriter import AICopywritingAgent
        from src.graph.listing_state import ListingState
        from src.models.listing import ListingProduct

        product = ListingProduct(
            sku="SKU-002",
            title="Test Product 2",
            category="Electronics",
        )

        state = ListingState(
            product=product,
            target_platforms=[],  # 无目标平台
        )

        agent = AICopywritingAgent()

        with patch.object(
            agent,
            "_retrieve_category_memory",
            new_callable=AsyncMock,
        ) as mock_memory, patch.object(
            agent,
            "_enhance_with_llm",
            new_callable=AsyncMock,
            return_value="Enhanced text",
        ):
            await agent.execute(state)

        # _retrieve_category_memory 返回空字符串（因为 target_platforms 为空）
        mock_memory.assert_not_called()


# ---------------------------------------------------------------------------
# Token Budget 截断
# ---------------------------------------------------------------------------


class TestTokenBudgetTruncation:
    """验证长上下文截断功能。"""

    @pytest.mark.asyncio
    async def test_truncates_long_context(
        self,
        mock_session: MagicMock,
        mock_retriever: MagicMock,
        sample_state: AgentState,
    ) -> None:
        """超过 4000 字符的类目记忆应被截断并加 '...'。"""
        long_context = "X" * 5000
        _mock_category_memory_retriever(mock_retriever, long_context)

        agent = RAGEnhancedRequirementAnalyzer(
            session=mock_session,
            retriever=mock_retriever,
        )

        with patch.object(
            agent,
            "invoke_llm",
            new_callable=AsyncMock,
            return_value='{"product_summary": "test"}',
        ) as mock_invoke:
            result = await agent.execute(sample_state)

        assert result.success is True
        call_kwargs = mock_invoke.call_args[0][1]
        ctx = call_kwargs["category_memory_context"]
        assert len(ctx) <= 4003  # 4000 + "..."
        assert ctx.endswith("...")

    def test_truncate_preserves_short_context(self) -> None:
        """短上下文不应被截断。"""
        agent = RAGEnhancedRequirementAnalyzer()
        short = "Hello World"
        result = agent._truncate_context(short, max_chars=4000)
        assert result == short

    def test_truncate_empty_context(self) -> None:
        """空字符串不应被截断。"""
        agent = RAGEnhancedRequirementAnalyzer()
        result = agent._truncate_context("", max_chars=4000)
        assert result == ""


# ---------------------------------------------------------------------------
# RAG Sources 类型区分
# ---------------------------------------------------------------------------


class TestRagSourcesTyping:
    """验证 AgentResult.data 中 rag_sources 的 source_type 区分。"""

    @pytest.mark.asyncio
    async def test_rag_sources_in_result_data(
        self,
        mock_session: MagicMock,
        mock_retriever: MagicMock,
        sample_state: AgentState,
    ) -> None:
        """AgentResult.data 应包含 rag_sources 列表。"""
        _mock_category_memory_retriever(mock_retriever, "memory text")

        agent = RAGEnhancedRequirementAnalyzer(
            session=mock_session,
            retriever=mock_retriever,
        )

        with patch.object(
            agent,
            "invoke_llm",
            new_callable=AsyncMock,
            return_value='{"product_summary": "test"}',
        ):
            result = await agent.execute(sample_state)

        assert result.success is True
        assert "rag_sources" in result.data
        assert isinstance(result.data["rag_sources"], list)
