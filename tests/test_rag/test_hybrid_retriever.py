"""
BGE-M3 混合检索服务测试。

Description:
    测试 HybridRetriever 的检索逻辑和 RRF 融合。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.vector_store import SearchResult
from src.rag.hybrid_retriever import HybridRetriever, HybridSearchResult


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


class TestHybridRetriever:
    """HybridRetriever 测试类。"""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """创建模拟配置。"""
        settings = MagicMock()
        settings.hybrid_retrieval_enabled = False
        settings.hybrid_model = "BAAI/bge-m3"
        settings.hybrid_dense_weight = 0.4
        settings.hybrid_sparse_weight = 0.3
        settings.hybrid_colbert_weight = 0.3
        settings.hybrid_rrf_k = 60
        settings.retrieval_top_k = 5
        settings.embedding_device = "cpu"
        return settings

    @pytest.fixture
    def retriever(self, mock_settings: MagicMock) -> HybridRetriever:
        """创建混合检索器实例。"""
        with (
            patch("src.rag.hybrid_retriever.get_settings", return_value=mock_settings),
            patch("src.rag.hybrid_retriever.get_embedding_service"),
            patch("src.rag.hybrid_retriever.VectorStore"),
        ):
            return HybridRetriever()

    @pytest.mark.asyncio
    async def test_search_disabled(self, retriever: HybridRetriever) -> None:
        """测试混合检索禁用时回退到 Dense 检索。"""
        # Mock embedding service 和 vector store
        mock_embedding = MagicMock()
        mock_embedding.aembed_single = AsyncMock(return_value=[0.1, 0.2, 0.3])
        retriever.embedding_service = mock_embedding

        mock_vs = MagicMock()
        mock_results = [
            _create_search_result(1, 1, "文档1", "brand_guide", "内容1", 0.85),
        ]
        mock_vs.search = AsyncMock(return_value=mock_results)
        retriever.vector_store = mock_vs

        result = await retriever.search(MagicMock(), "查询", tenant_id="t1")

        assert result.method == "dense"
        assert len(result.results) == 1
        assert result.dense_count == 1

    def test_rrf_fuse(self, retriever: HybridRetriever) -> None:
        """测试 RRF 融合逻辑。"""
        dense_results = [
            _create_search_result(1, 1, "文档1", "brand_guide", "内容1", 0.9),
            _create_search_result(2, 2, "文档2", "brand_guide", "内容2", 0.8),
            _create_search_result(3, 3, "文档3", "brand_guide", "内容3", 0.7),
        ]

        sparse_results = [
            _create_search_result(2, 2, "文档2", "brand_guide", "内容2", 0.5),
            _create_search_result(4, 4, "文档4", "brand_guide", "内容4", 0.4),
        ]

        colbert_results = [
            _create_search_result(1, 1, "文档1", "brand_guide", "内容1", 0.95),
            _create_search_result(3, 3, "文档3", "brand_guide", "内容3", 0.85),
        ]

        fused = retriever._rrf_fuse(
            dense_results=dense_results,
            sparse_results=sparse_results,
            colbert_results=colbert_results,
            top_k=5,
        )

        # 应包含所有 4 个文档
        chunk_ids = [r.chunk_id for r in fused]
        assert set(chunk_ids) == {1, 2, 3, 4}

        # 在多路中都出现的文档应该排名更高
        # 文档1: Dense rank=1 + ColBERT rank=1 -> 高分
        # 文档2: Dense rank=2 + Sparse rank=1 -> 较高分
        assert fused[0].chunk_id in {1, 2}

        # 检查 RRF 分数存在
        for result in fused:
            assert "rrf_score" in result.metadata
            assert result.similarity == result.metadata["rrf_score"]

    def test_rrf_fuse_top_k(self, retriever: HybridRetriever) -> None:
        """测试 RRF 融合 top_k 截断。"""
        dense_results = [
            _create_search_result(i, i, f"文档{i}", "brand_guide", f"内容{i}", 0.9 - i * 0.1)
            for i in range(1, 6)
        ]

        fused = retriever._rrf_fuse(
            dense_results=dense_results,
            sparse_results=[],
            colbert_results=[],
            top_k=3,
        )

        assert len(fused) == 3


class TestHybridSearchResult:
    """HybridSearchResult 测试类。"""

    def test_default_values(self) -> None:
        """测试默认值。"""
        result = HybridSearchResult()

        assert result.results == []
        assert result.dense_count == 0
        assert result.sparse_count == 0
        assert result.colbert_count == 0
        assert result.method == "hybrid"
