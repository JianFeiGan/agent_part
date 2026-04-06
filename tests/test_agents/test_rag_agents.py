"""
RAG 增强 Agent 集成测试。

Description:
    测试 RAG 增强版 Agent 的基本功能。
@author ganjianfei
@version 1.0.0
2026-04-05
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.base import AgentRole
from src.agents.rag_creative_planner import RAGEnhancedCreativePlanner
from src.agents.rag_quality_reviewer import RAGEnhancedQualityReviewer
from src.agents.rag_requirement_analyzer import RAGEnhancedRequirementAnalyzer
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

    # 模拟检索结果
    mock_result = MagicMock()
    mock_result.results = []

    retriever.retrieve = AsyncMock(return_value=mock_result)
    return retriever


@pytest.fixture
def sample_product() -> Product:
    """创建示例商品。"""
    return Product(
        product_id="test_001",
        name="智能手表 Pro",
        brand="TechBrand",
        category=ProductCategory.DIGITAL,
        description="一款高端智能手表，支持健康监测、运动追踪等功能。",
        selling_points=[],
        specifications=[],
    )


@pytest.fixture
def sample_state(sample_product: Product) -> AgentState:
    """创建示例状态。"""
    return AgentState(
        product_info=sample_product,
        generation_request=None,
    )


class TestRAGEnhancedRequirementAnalyzer:
    """RAG 增强需求分析 Agent 测试。"""

    def test_init(self, mock_session: MagicMock, mock_retriever: MagicMock) -> None:
        """测试初始化。"""
        agent = RAGEnhancedRequirementAnalyzer(
            session=mock_session,
            retriever=mock_retriever,
        )

        assert agent.role == AgentRole.REQUIREMENT_ANALYZER
        assert agent._session == mock_session
        assert agent._retriever == mock_retriever

    def test_has_rag(self, mock_session: MagicMock, mock_retriever: MagicMock) -> None:
        """测试 RAG 能力检查。"""
        agent = RAGEnhancedRequirementAnalyzer(
            session=mock_session,
            retriever=mock_retriever,
        )

        assert agent.has_rag() is True

        # 无 retriever
        agent_no_rag = RAGEnhancedRequirementAnalyzer(session=mock_session)
        assert agent_no_rag.has_rag() is False

    @pytest.mark.asyncio
    async def test_execute_without_product(
        self, mock_session: MagicMock, mock_retriever: MagicMock
    ) -> None:
        """测试无商品信息时执行。"""
        agent = RAGEnhancedRequirementAnalyzer(
            session=mock_session,
            retriever=mock_retriever,
        )

        state = AgentState()
        result = await agent.execute(state)

        assert result.success is False
        assert "缺少商品信息" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_product(
        self,
        mock_session: MagicMock,
        mock_retriever: MagicMock,
        sample_state: AgentState,
    ) -> None:
        """测试有商品信息时执行。"""
        agent = RAGEnhancedRequirementAnalyzer(
            session=mock_session,
            retriever=mock_retriever,
        )

        # Mock LLM 响应
        with patch.object(
            agent,
            "invoke_llm",
            new_callable=AsyncMock,
            return_value='{"product_summary": "智能手表", "key_features": ["健康监测"], "selling_points": [], "target_audience": ["科技爱好者"], "style_recommendations": ["科技风"], "keywords": ["智能手表"]}',
        ):
            result = await agent.execute(sample_state)

        assert result.success is True
        assert "requirement_report" in result.data
        assert result.next_agent == AgentRole.CREATIVE_PLANNER


class TestRAGEnhancedCreativePlanner:
    """RAG 增强创意策划 Agent 测试。"""

    def test_init(self, mock_session: MagicMock, mock_retriever: MagicMock) -> None:
        """测试初始化。"""
        agent = RAGEnhancedCreativePlanner(
            session=mock_session,
            retriever=mock_retriever,
        )

        assert agent.role == AgentRole.CREATIVE_PLANNER

    @pytest.mark.asyncio
    async def test_execute_without_product(
        self, mock_session: MagicMock, mock_retriever: MagicMock
    ) -> None:
        """测试无商品信息时执行。"""
        agent = RAGEnhancedCreativePlanner(
            session=mock_session,
            retriever=mock_retriever,
        )

        state = AgentState()
        result = await agent.execute(state)

        assert result.success is False
        assert "缺少商品信息" in result.error


class TestRAGEnhancedQualityReviewer:
    """RAG 增强质量审核 Agent 测试。"""

    def test_init(self, mock_session: MagicMock, mock_retriever: MagicMock) -> None:
        """测试初始化。"""
        agent = RAGEnhancedQualityReviewer(
            session=mock_session,
            retriever=mock_retriever,
        )

        assert agent.role == AgentRole.QUALITY_REVIEWER

    @pytest.mark.asyncio
    async def test_execute_without_product(
        self, mock_session: MagicMock, mock_retriever: MagicMock
    ) -> None:
        """测试无商品信息时执行。"""
        agent = RAGEnhancedQualityReviewer(
            session=mock_session,
            retriever=mock_retriever,
        )

        state = AgentState()
        result = await agent.execute(state)

        assert result.success is False
        assert "缺少商品信息" in result.error

    def test_extract_prohibited_words(
        self, mock_session: MagicMock, mock_retriever: MagicMock
    ) -> None:
        """测试禁止词提取。"""
        agent = RAGEnhancedQualityReviewer(
            session=mock_session,
            retriever=mock_retriever,
        )

        rule_content = '禁止词列表：["第一", "最好", "独家"]'
        words = agent._extract_prohibited_words(rule_content)

        assert "第一" in words
        assert "最好" in words
        assert "独家" in words


class TestWorkflowBuilderRAG:
    """WorkflowBuilder RAG 支持测试。"""

    def test_create_with_rag(self, mock_session: MagicMock, mock_retriever: MagicMock) -> None:
        """测试使用 RAG 配置创建。"""
        from src.graph.workflow import WorkflowBuilder

        builder = WorkflowBuilder(
            retriever=mock_retriever,
            session=mock_session,
            rag_enabled=True,
        )

        assert builder._retriever == mock_retriever
        assert builder._session == mock_session
        assert builder._rag_enabled is True

    def test_create_rag_analyzer(self, mock_session: MagicMock, mock_retriever: MagicMock) -> None:
        """测试创建 RAG 增强版分析器。"""
        from src.graph.workflow import WorkflowBuilder

        builder = WorkflowBuilder(
            retriever=mock_retriever,
            session=mock_session,
            rag_enabled=True,
        )

        analyzer = builder._create_requirement_analyzer()
        assert isinstance(analyzer, RAGEnhancedRequirementAnalyzer)

    def test_create_normal_analyzer_without_rag(self, mock_session: MagicMock) -> None:
        """测试不使用 RAG 时创建普通分析器。"""
        from src.agents.requirement_analyzer import RequirementAnalyzerAgent
        from src.graph.workflow import WorkflowBuilder

        builder = WorkflowBuilder(rag_enabled=False)
        analyzer = builder._create_requirement_analyzer()

        assert isinstance(analyzer, RequirementAnalyzerAgent)
