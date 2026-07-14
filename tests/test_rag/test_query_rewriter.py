"""
Query 改写服务测试。

Description:
    测试 QueryRewriter 的三种改写模式和回退逻辑。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.rag.query_rewriter import QueryRewriter, RewriteResult, RewrittenQuery


class TestQueryRewriter:
    """QueryRewriter 测试类。"""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """创建模拟配置。"""
        settings = MagicMock()
        settings.query_rewriting_enabled = False
        settings.query_rewriting_mode = "single"
        settings.query_rewriting_max_variants = 3
        settings.hyde_enabled = False
        settings.llm_provider = "qwen"
        settings.effective_qwen_api_key = "test_key"
        settings.qwen_api_base = "https://test.api.com"
        settings.qwen_llm_model = "qwen-plus"
        settings.llm_model = "qwen-plus"
        settings.effective_dashscope_api_key = "test_key"
        return settings

    @pytest.fixture
    def rewriter(self, mock_settings: MagicMock) -> QueryRewriter:
        """创建改写器实例。"""
        with patch("src.rag.query_rewriter.get_settings", return_value=mock_settings):
            return QueryRewriter()

    @pytest.mark.asyncio
    async def test_rewrite_disabled(self, rewriter: QueryRewriter) -> None:
        """测试改写功能禁用时返回原始查询。"""
        result = await rewriter.rewrite("智能手表特点")

        assert result.original_query == "智能手表特点"
        assert len(result.rewritten_queries) == 1
        assert result.rewritten_queries[0].query == "智能手表特点"
        assert result.rewritten_queries[0].is_original is True
        assert result.mode == "none"

    @pytest.mark.asyncio
    async def test_single_rewrite(self, mock_settings: MagicMock) -> None:
        """测试单次改写模式。"""
        mock_settings.query_rewriting_enabled = True
        mock_settings.query_rewriting_mode = "single"

        with patch("src.rag.query_rewriter.get_settings", return_value=mock_settings):
            rewriter = QueryRewriter()

        # Mock LLM
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "智能手表产品功能特性分析"

        # 构建 chain: prompt | llm → ainvoke 返回 response
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_response)

        # mock prompt 对象，其 __or__ 返回 mock_chain
        mock_prompt = MagicMock()
        mock_prompt.__or__ = MagicMock(return_value=mock_chain)

        rewriter._llm = mock_llm

        with patch("langchain_core.prompts.ChatPromptTemplate") as mock_prompt_cls:
            mock_prompt_cls.from_messages.return_value = mock_prompt

            result = await rewriter._single_rewrite("智能手表特点")

        assert result.original_query == "智能手表特点"
        assert len(result.rewritten_queries) == 1
        assert result.mode == "single"
        assert result.rewritten_queries[0].query == "智能手表产品功能特性分析"

    @pytest.mark.asyncio
    async def test_multi_query_rewrite(self, mock_settings: MagicMock) -> None:
        """测试多视角变体改写模式。"""
        mock_settings.query_rewriting_enabled = True
        mock_settings.query_rewriting_mode = "multi_query"
        mock_settings.query_rewriting_max_variants = 3

        with patch("src.rag.query_rewriter.get_settings", return_value=mock_settings):
            rewriter = QueryRewriter()

        # Mock LLM
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "智能手表功能评测\n智能穿戴设备特点\n手表科技趋势"

        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_response)

        mock_prompt = MagicMock()
        mock_prompt.__or__ = MagicMock(return_value=mock_chain)

        rewriter._llm = mock_llm

        with patch("langchain_core.prompts.ChatPromptTemplate") as mock_prompt_cls:
            mock_prompt_cls.from_messages.return_value = mock_prompt

            result = await rewriter._multi_query_rewrite("智能手表特点")

        assert result.original_query == "智能手表特点"
        assert result.mode == "multi_query"
        # 原始查询 + 3 个变体
        assert len(result.rewritten_queries) == 4
        assert result.rewritten_queries[0].is_original is True
        assert result.rewritten_queries[0].query == "智能手表特点"

    @pytest.mark.asyncio
    async def test_hyde_rewrite(self, mock_settings: MagicMock) -> None:
        """测试 HyDE 假设文档嵌入模式。"""
        mock_settings.query_rewriting_enabled = True
        mock_settings.query_rewriting_mode = "hyde"

        with patch("src.rag.query_rewriter.get_settings", return_value=mock_settings):
            rewriter = QueryRewriter()

        # Mock LLM
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = (
            "智能手表是一种集成了健康监测、消息通知、运动追踪等功能的可穿戴设备..."
        )

        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_response)

        mock_prompt = MagicMock()
        mock_prompt.__or__ = MagicMock(return_value=mock_chain)

        rewriter._llm = mock_llm

        with patch("langchain_core.prompts.ChatPromptTemplate") as mock_prompt_cls:
            mock_prompt_cls.from_messages.return_value = mock_prompt

            result = await rewriter._hyde_rewrite("智能手表特点")

        assert result.original_query == "智能手表特点"
        assert len(result.rewritten_queries) == 1
        assert result.mode == "hyde"
        assert "智能手表" in result.rewritten_queries[0].query

    @pytest.mark.asyncio
    async def test_rewrite_fallback_on_error(self, mock_settings: MagicMock) -> None:
        """测试改写失败时回退到原始查询。"""
        mock_settings.query_rewriting_enabled = True
        mock_settings.query_rewriting_mode = "single"

        with patch("src.rag.query_rewriter.get_settings", return_value=mock_settings):
            rewriter = QueryRewriter()

        # Mock LLM 抛出异常
        mock_llm = MagicMock()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(side_effect=Exception("LLM 调用失败"))

        mock_prompt = MagicMock()
        mock_prompt.__or__ = MagicMock(return_value=mock_chain)

        rewriter._llm = mock_llm

        with patch("langchain_core.prompts.ChatPromptTemplate") as mock_prompt_cls:
            mock_prompt_cls.from_messages.return_value = mock_prompt

            result = await rewriter.rewrite("智能手表特点")

        # 回退到原始查询
        assert result.original_query == "智能手表特点"
        assert len(result.rewritten_queries) == 1
        assert result.rewritten_queries[0].query == "智能手表特点"
        assert result.rewritten_queries[0].is_original is True


class TestRewriteResult:
    """RewriteResult 测试类。"""

    def test_queries_property(self) -> None:
        """测试 queries 属性提取查询文本。"""
        result = RewriteResult(
            original_query="测试",
            rewritten_queries=[
                RewrittenQuery(query="查询1", mode="single"),
                RewrittenQuery(query="查询2", mode="multi_query"),
            ],
            mode="multi_query",
        )

        assert result.queries == ["查询1", "查询2"]

    def test_empty_queries(self) -> None:
        """测试空查询列表。"""
        result = RewriteResult(original_query="测试")
        assert result.queries == []
