"""
RAGEnhancedCreativePlanner P0 修复测试。

验证 execute() 方法参数名修改为 state 后，函数体能正确访问传入状态，
并且 product_info=None 时返回 success=False、error="缺少商品信息"。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.base import AgentRole
from src.agents.rag_creative_planner import RAGEnhancedCreativePlanner
from src.graph.state import AgentState
from src.models.product import Product, ProductCategory


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
    """创建模拟知识检索器。"""
    retriever = MagicMock()

    mock_result = MagicMock()
    mock_result.results = []

    retriever.retrieve = AsyncMock(return_value=mock_result)
    return retriever


@pytest.fixture
def sample_product() -> Product:
    """创建示例商品。"""
    return Product(
        product_id="test_p0_001",
        name="智能手表 Pro",
        brand="TechBrand",
        category=ProductCategory.DIGITAL,
        description="高端智能手表，支持健康监测、运动追踪等功能。",
        selling_points=[],
        specifications=[],
    )


@pytest.fixture
def sample_state(sample_product: Product) -> AgentState:
    """创建包含商品信息的示例状态。"""
    return AgentState(product_info=sample_product)


class TestRAGCreativePlannerExecuteSignature:
    """验证 execute() 方法签名和参数访问。"""

    def test_execute_method_exists(self, mock_session: MagicMock, mock_retriever: MagicMock) -> None:
        """验证 execute 方法存在且参数名为 state。"""
        agent = RAGEnhancedCreativePlanner(
            session=mock_session,
            retriever=mock_retriever,
        )

        import inspect

        sig = inspect.signature(agent.execute)
        params = list(sig.parameters.keys())
        assert "state" in params, (
            f"execute() 参数名应为 'state'，实际为: {params}"
        )

    def test_execute_accepts_state_arg(
        self, mock_session: MagicMock, mock_retriever: MagicMock
    ) -> None:
        """验证 execute 能接收 state 参数（不报 TypeError）。"""
        agent = RAGEnhancedCreativePlanner(
            session=mock_session,
            retriever=mock_retriever,
        )

        import inspect

        sig = inspect.signature(agent.execute)
        # 应该只有一个参数 'state'（不算 self）
        params = list(sig.parameters.keys())
        assert len(params) == 1, f"execute() 应只有 1 个参数，实际: {params}"
        assert params[0] == "state"


class TestRAGCreativePlannerP0:
    """P0 修复核心测试。"""

    @pytest.mark.asyncio
    async def test_execute_without_product_returns_failure(
        self, mock_session: MagicMock, mock_retriever: MagicMock
    ) -> None:
        """product_info=None 时返回 success=False 且 error == "缺少商品信息"。"""
        agent = RAGEnhancedCreativePlanner(
            session=mock_session,
            retriever=mock_retriever,
        )

        # 状态没有 product_info
        state = AgentState()

        result = await agent.execute(state)

        assert result.success is False, (
            f"product_info=None 时应返回 success=False，实际为 {result.success}"
        )
        assert result.error == "缺少商品信息", (
            f"错误信息应为 '缺少商品信息'，实际为: {result.error}"
        )

    @pytest.mark.asyncio
    async def test_execute_with_product_succeeds(
        self,
        mock_session: MagicMock,
        mock_retriever: MagicMock,
        sample_state: AgentState,
    ) -> None:
        """有商品信息时正常执行成功。"""
        agent = RAGEnhancedCreativePlanner(
            session=mock_session,
            retriever=mock_retriever,
        )

        # Mock LLM 响应避免真实 API 调用
        with patch.object(
            agent,
            "invoke_llm",
            new_callable=AsyncMock,
            return_value='{"theme_name": "科技未来", "theme_description": "描述", "visual_style": "modern", "style_keywords": ["科技"], "key_elements": ["产品"], "target_emotion": "信赖", "color_suggestion": "tech"}',
        ):
            result = await agent.execute(sample_state)

        assert result.success is True, (
            f"有商品信息时应返回 success=True，实际为 {result.success}"
        )
        assert "creative_plan" in result.data
        assert result.next_agent == AgentRole.VISUAL_DESIGNER
