"""
端到端测试 - RAG 知识库工作流。

Description:
    测试完整的 RAG 知识库工作流程，包括文档上传、检索、Agent 集成。
@author ganjianfei
@version 1.0.0
2026-04-05
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.rag_requirement_analyzer import RAGEnhancedRequirementAnalyzer
from src.agents.rag_creative_planner import RAGEnhancedCreativePlanner
from src.agents.rag_quality_reviewer import RAGEnhancedQualityReviewer
from src.graph.state import AgentState
from src.graph.workflow import WorkflowBuilder
from src.models.product import Product, ProductCategory
from src.rag.retriever import KnowledgeRetriever, RetrievalResult
from src.db.vector_store import SearchResult


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
    retriever = MagicMock(spec=KnowledgeRetriever)
    retriever.retrieve = AsyncMock()
    retriever.retrieve_for_product_analysis = AsyncMock()
    retriever.retrieve_for_creative_planning = AsyncMock()
    retriever.retrieve_compliance_rules = AsyncMock()
    return retriever


@pytest.fixture
def sample_product() -> Product:
    """创建示例商品。"""
    return Product(
        product_id="test_e2e_001",
        name="智能手表 Pro Max",
        brand="TechBrand",
        category=ProductCategory.DIGITAL,
        description="高端智能手表，支持健康监测、运动追踪、移动支付等功能。",
        selling_points=[],
        specifications=[],
    )


def _create_search_result(
    chunk_id: int,
    doc_id: int,
    doc_title: str,
    doc_type: str,
    content: str,
    similarity: float,
) -> SearchResult:
    """创建 SearchResult 辅助函数。"""
    return SearchResult(
        chunk_id=chunk_id,
        doc_id=doc_id,
        doc_title=doc_title,
        doc_type=doc_type,
        content=content,
        similarity=similarity,
        metadata={},
    )


class TestRAGWorkflowE2E:
    """RAG 工作流端到端测试。"""

    @pytest.mark.asyncio
    async def test_complete_rag_workflow(
        self,
        mock_session: MagicMock,
        mock_retriever: MagicMock,
        sample_product: Product,
    ) -> None:
        """测试完整的 RAG 工作流程。

        流程:
        1. 商品信息输入
        2. RAG 检索品牌规范和类目知识
        3. 需求分析 Agent 使用检索结果
        4. 创意策划 Agent 使用检索结果
        5. 质量审核 Agent 使用合规规则
        """
        # 1. 准备模拟数据
        brand_result = RetrievalResult(
            query="TechBrand 品牌规范",
            results=[
                _create_search_result(
                    1,
                    1,
                    "TechBrand 品牌手册",
                    "brand_guide",
                    "品牌调性：科技感、简约、专业。配色：深蓝 #1A365D，白色 #FFFFFF。",
                    0.92,
                )
            ],
            context="品牌调性：科技感、简约、专业。",
            sources=[{"chunk_id": 1, "doc_id": 1}],
        )

        mock_retriever.retrieve_for_product_analysis.return_value = brand_result
        mock_retriever.retrieve_for_creative_planning.return_value = brand_result
        mock_retriever.retrieve_compliance_rules.return_value = RetrievalResult(
            query="禁止词",
            results=[
                _create_search_result(
                    3,
                    3,
                    "电商合规规则",
                    "compliance_rule",
                    "禁止词：第一、最好、独家、国家级。",
                    0.95,
                )
            ],
            context="禁止词：第一、最好、独家。",
            sources=[{"chunk_id": 3, "doc_id": 3}],
        )

        # 2. 创建 Workflow Builder
        builder = WorkflowBuilder(
            retriever=mock_retriever,
            session=mock_session,
            rag_enabled=True,
        )

        # 验证 RAG 配置正确
        assert builder._rag_enabled is True
        assert builder._retriever == mock_retriever

        # 3. 创建 RAG 增强的 Agent
        analyzer = builder._create_requirement_analyzer()
        assert isinstance(analyzer, RAGEnhancedRequirementAnalyzer)

        planner = builder._create_creative_planner()
        assert isinstance(planner, RAGEnhancedCreativePlanner)

        reviewer = builder._create_quality_reviewer()
        assert isinstance(reviewer, RAGEnhancedQualityReviewer)

    @pytest.mark.asyncio
    async def test_rag_enhanced_requirement_analysis(
        self,
        mock_session: MagicMock,
        mock_retriever: MagicMock,
        sample_product: Product,
    ) -> None:
        """测试 RAG 增强的需求分析。"""
        # 配置检索器返回
        retrieval_result = RetrievalResult(
            query="智能手表 产品分析",
            results=[
                _create_search_result(
                    1,
                    1,
                    "数码类目知识",
                    "category_knowledge",
                    "智能手表核心卖点：健康监测、运动追踪。",
                    0.90,
                )
            ],
            context="智能手表核心卖点：健康监测、运动追踪。",
            sources=[{"chunk_id": 1, "doc_id": 1}],
        )
        mock_retriever.retrieve_for_product_analysis.return_value = retrieval_result

        # 创建 Agent
        agent = RAGEnhancedRequirementAnalyzer(
            session=mock_session,
            retriever=mock_retriever,
        )

        # 准备状态
        state = AgentState(product_info=sample_product)

        # Mock LLM 响应
        with patch.object(
            agent,
            "invoke_llm",
            new_callable=AsyncMock,
            return_value='{"product_summary": "智能手表", "key_features": ["健康监测"], "selling_points": [], "target_audience": ["科技爱好者"], "style_recommendations": ["科技风"], "keywords": ["智能手表"]}',
        ):
            result = await agent.execute(state)

        # 验证结果
        assert result.success is True
        assert "requirement_report" in result.data

        # 验证检索器被调用
        mock_retriever.retrieve_for_product_analysis.assert_called_once()

    @pytest.mark.asyncio
    async def test_rag_enhanced_creative_planning(
        self,
        mock_session: MagicMock,
        mock_retriever: MagicMock,
        sample_product: Product,
    ) -> None:
        """测试 RAG 增强的创意策划。"""
        # 配置检索器返回
        retrieval_result = RetrievalResult(
            query="创意策划",
            results=[
                _create_search_result(
                    1,
                    1,
                    "TechBrand 视觉规范",
                    "brand_guide",
                    "配色：深蓝 #1A365D，科技感风格。",
                    0.88,
                )
            ],
            context="配色：深蓝 #1A365D，科技感风格。",
            sources=[{"chunk_id": 1, "doc_id": 1}],
        )
        mock_retriever.retrieve_for_creative_planning.return_value = retrieval_result

        # 创建 Agent
        agent = RAGEnhancedCreativePlanner(
            session=mock_session,
            retriever=mock_retriever,
        )

        # 准备状态（需要先有需求分析结果）
        state = AgentState(product_info=sample_product)

        # Mock LLM 响应
        with patch.object(
            agent,
            "invoke_llm",
            new_callable=AsyncMock,
            return_value='{"theme": "科技未来", "style": "现代简约", "color_scheme": {"primary": "#1A365D"}, "visual_elements": []}',
        ):
            result = await agent.execute(state)

        # 验证结果
        assert result.success is True

    @pytest.mark.asyncio
    async def test_rag_enhanced_quality_review(
        self,
        mock_session: MagicMock,
        mock_retriever: MagicMock,
        sample_product: Product,
    ) -> None:
        """测试 RAG 增强的质量审核。"""
        # 配置检索器返回
        compliance_result = RetrievalResult(
            query="合规规则",
            results=[
                _create_search_result(
                    1,
                    1,
                    "电商合规规则",
                    "compliance_rule",
                    "禁止词列表：第一、最好、独家。",
                    0.95,
                )
            ],
            context="禁止词列表：第一、最好、独家。",
            sources=[{"chunk_id": 1, "doc_id": 1}],
        )
        mock_retriever.retrieve_compliance_rules.return_value = compliance_result

        # 创建 Agent
        agent = RAGEnhancedQualityReviewer(
            session=mock_session,
            retriever=mock_retriever,
        )

        # 准备状态
        state = AgentState(product_info=sample_product)

        # Mock LLM 响应
        with patch.object(
            agent,
            "invoke_llm",
            new_callable=AsyncMock,
            return_value='{"score": 85, "issues": [], "suggestions": []}',
        ):
            result = await agent.execute(state)

        # 验证结果
        assert result.success is True

        # 验证合规检索被调用
        mock_retriever.retrieve_compliance_rules.assert_called_once()


class TestRAGFallback:
    """RAG 降级测试。"""

    @pytest.mark.asyncio
    async def test_workflow_without_rag(self, sample_product: Product) -> None:
        """测试无 RAG 时工作流正常工作。"""
        builder = WorkflowBuilder(rag_enabled=False)

        # 验证 RAG 未启用
        assert builder._rag_enabled is False

        # 创建 Agent 应该返回普通版本
        from src.agents.requirement_analyzer import RequirementAnalyzerAgent

        analyzer = builder._create_requirement_analyzer()
        assert isinstance(analyzer, RequirementAnalyzerAgent)
        assert not hasattr(analyzer, "_retriever") or analyzer._retriever is None

    @pytest.mark.asyncio
    async def test_retriever_failure_fallback(
        self,
        mock_session: MagicMock,
        mock_retriever: MagicMock,
        sample_product: Product,
    ) -> None:
        """测试检索器失败时的降级处理。"""
        # 配置检索器抛出异常
        mock_retriever.retrieve_for_product_analysis.side_effect = Exception("检索服务不可用")

        # 创建 Agent
        agent = RAGEnhancedRequirementAnalyzer(
            session=mock_session,
            retriever=mock_retriever,
        )

        # 准备状态
        state = AgentState(product_info=sample_product)

        # Mock LLM 响应
        with patch.object(
            agent,
            "invoke_llm",
            new_callable=AsyncMock,
            return_value='{"product_summary": "智能手表", "key_features": [], "selling_points": [], "target_audience": [], "style_recommendations": [], "keywords": []}',
        ):
            # 应该优雅处理检索失败
            result = await agent.execute(state)

        # 即使检索失败，Agent 也应该能完成任务
        assert result.success is True
