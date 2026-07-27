"""
KnowledgeRetriever 高级管道集成测试。

Description:
    测试 KnowledgeRetriever 在高级 RAG 管道模式下的集成行为。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.vector_store import SearchResult
from src.rag.retriever import KnowledgeRetriever, RetrievalResult


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


class TestKnowledgeRetrieverAdvanced:
    """KnowledgeRetriever 高级管道测试类。"""

    @pytest.fixture
    def mock_settings_disabled(self) -> MagicMock:
        """创建模拟配置（高级功能禁用）。"""
        settings = MagicMock()
        settings.query_rewriting_enabled = False
        settings.reranker_enabled = False
        settings.hybrid_retrieval_enabled = False
        settings.retrieval_top_k = 5
        settings.similarity_threshold = 0.7
        return settings

    @pytest.fixture
    def mock_settings_enabled(self) -> MagicMock:
        """创建模拟配置（高级功能启用）。"""
        settings = MagicMock()
        settings.query_rewriting_enabled = True
        settings.query_rewriting_mode = "single"
        settings.query_rewriting_max_variants = 3
        settings.reranker_enabled = True
        settings.reranker_top_k = 5
        settings.hybrid_retrieval_enabled = False
        settings.retrieval_top_k = 5
        settings.similarity_threshold = 0.7
        return settings

    @pytest.mark.asyncio
    async def test_fallback_to_basic_when_disabled(self, mock_settings_disabled: MagicMock) -> None:
        """测试高级功能禁用时回退到基础检索。"""
        with (
            patch("src.rag.retriever.get_settings", return_value=mock_settings_disabled),
            patch("src.rag.retriever.get_embedding_service"),
            patch("src.rag.retriever.VectorStore"),
        ):
            retriever = KnowledgeRetriever()

        # Mock embedding 和 vector store
        mock_embedding = MagicMock()
        mock_embedding.aembed_single = AsyncMock(return_value=[0.1, 0.2, 0.3])
        retriever.embedding_service = mock_embedding

        mock_results = [
            _create_search_result(1, 1, "文档1", "brand_guide", "内容1", 0.85),
        ]
        mock_vs = MagicMock()
        mock_vs.search = AsyncMock(return_value=mock_results)
        retriever.vector_store = mock_vs

        mock_session = MagicMock()

        result = await retriever.retrieve(mock_session, "智能手表", tenant_id="t1")

        assert isinstance(result, RetrievalResult)
        assert result.query == "智能手表"
        assert len(result.results) == 1

    @pytest.mark.asyncio
    async def test_advanced_pipeline_with_rewriting_and_reranking(
        self, mock_settings_enabled: MagicMock
    ) -> None:
        """测试 Query 改写 + 重排序的高级管道。"""
        with (
            patch("src.rag.retriever.get_settings", return_value=mock_settings_enabled),
            patch("src.rag.retriever.get_embedding_service"),
            patch("src.rag.retriever.VectorStore"),
        ):
            retriever = KnowledgeRetriever()

        # Mock Query Rewriter
        from src.rag.query_rewriter import RewriteResult, RewrittenQuery

        mock_rewriter = MagicMock()
        mock_rewriter.rewrite = AsyncMock(
            return_value=RewriteResult(
                original_query="智能手表",
                rewritten_queries=[
                    RewrittenQuery(query="智能手表功能特性", mode="single"),
                ],
                mode="single",
            )
        )
        retriever._query_rewriter = mock_rewriter

        # Mock Reranker
        from src.rag.reranker import RerankResult

        search_results = [
            _create_search_result(1, 1, "文档1", "brand_guide", "智能手表功能", 0.8),
            _create_search_result(2, 2, "文档2", "brand_guide", "运动鞋特点", 0.6),
        ]

        reranked_results = [
            _create_search_result(1, 1, "文档1", "brand_guide", "智能手表功能", 0.95),
        ]
        mock_reranker = MagicMock()
        mock_reranker.rerank = AsyncMock(
            return_value=RerankResult(
                results=reranked_results,
                original_count=2,
                reranked_count=1,
            )
        )
        retriever._reranker = mock_reranker

        # Mock embedding 和 vector store
        mock_embedding = MagicMock()
        mock_embedding.aembed_single = AsyncMock(return_value=[0.1, 0.2, 0.3])
        retriever.embedding_service = mock_embedding

        mock_vs = MagicMock()
        mock_vs.search = AsyncMock(return_value=search_results)
        retriever.vector_store = mock_vs

        mock_session = MagicMock()

        result = await retriever.retrieve(mock_session, "智能手表", tenant_id="t1")

        # 验证 Query 改写被调用
        mock_rewriter.rewrite.assert_called_once_with("智能手表")

        # 验证重排序被调用
        mock_reranker.rerank.assert_called_once()

        # 验证最终结果来自重排序
        assert isinstance(result, RetrievalResult)
        assert len(result.results) == 1
        assert result.results[0].chunk_id == 1

    @pytest.mark.asyncio
    async def test_is_advanced_rag_enabled(self) -> None:
        """测试高级 RAG 启用判断。"""
        # 全部禁用
        settings = MagicMock()
        settings.query_rewriting_enabled = False
        settings.reranker_enabled = False
        settings.hybrid_retrieval_enabled = False

        with (
            patch("src.rag.retriever.get_settings", return_value=settings),
            patch("src.rag.retriever.get_embedding_service"),
            patch("src.rag.retriever.VectorStore"),
        ):
            retriever = KnowledgeRetriever()
        assert retriever._is_advanced_rag_enabled() is False

        # 启用其中一个
        settings.query_rewriting_enabled = True
        with (
            patch("src.rag.retriever.get_settings", return_value=settings),
            patch("src.rag.retriever.get_embedding_service"),
            patch("src.rag.retriever.VectorStore"),
        ):
            retriever = KnowledgeRetriever()
        assert retriever._is_advanced_rag_enabled() is True
