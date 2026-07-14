"""
Cross-Encoder 重排序服务测试。

Description:
    测试 CrossEncoderReranker 的重排序逻辑和回退行为。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

from unittest.mock import MagicMock, patch

import pytest

from src.db.vector_store import SearchResult
from src.rag.reranker import CrossEncoderReranker, RerankResult


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


class TestCrossEncoderReranker:
    """CrossEncoderReranker 测试类。"""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """创建模拟配置。"""
        settings = MagicMock()
        settings.reranker_enabled = False
        settings.reranker_model = "BAAI/bge-reranker-v2-m3"
        settings.reranker_top_k = 5
        settings.reranker_device = "cpu"
        return settings

    @pytest.fixture
    def reranker(self, mock_settings: MagicMock) -> CrossEncoderReranker:
        """创建重排序器实例。"""
        with patch("src.rag.reranker.get_settings", return_value=mock_settings):
            return CrossEncoderReranker()

    @pytest.mark.asyncio
    async def test_rerank_disabled(self, reranker: CrossEncoderReranker) -> None:
        """测试重排序禁用时返回原始结果。"""
        results = [
            _create_search_result(1, 1, "文档1", "brand_guide", "内容1", 0.8),
            _create_search_result(2, 2, "文档2", "brand_guide", "内容2", 0.7),
        ]

        result = await reranker.rerank("查询", results)

        assert result.original_count == 2
        assert result.reranked_count == 2
        assert result.results == results

    @pytest.mark.asyncio
    async def test_rerank_empty_results(self, mock_settings: MagicMock) -> None:
        """测试空结果列表。"""
        mock_settings.reranker_enabled = True

        with patch("src.rag.reranker.get_settings", return_value=mock_settings):
            reranker = CrossEncoderReranker()

        result = await reranker.rerank("查询", [])

        assert result.original_count == 0
        assert result.reranked_count == 0
        assert result.results == []

    @pytest.mark.asyncio
    async def test_rerank_with_model(self, mock_settings: MagicMock) -> None:
        """测试使用模型进行重排序。"""
        mock_settings.reranker_enabled = True
        mock_settings.reranker_top_k = 2

        with patch("src.rag.reranker.get_settings", return_value=mock_settings):
            reranker = CrossEncoderReranker()

        results = [
            _create_search_result(1, 1, "文档1", "brand_guide", "智能手表功能", 0.8),
            _create_search_result(2, 2, "文档2", "brand_guide", "运动鞋特点", 0.7),
            _create_search_result(3, 3, "文档3", "brand_guide", "智能穿戴设备", 0.6),
        ]

        # Mock _compute_scores 返回重排序分数
        # 让文档3的分数最高，文档1其次，文档2最低
        with patch.object(reranker, "_compute_scores", return_value=[0.5, 0.2, 0.9]):
            result = await reranker.rerank("智能手表", results, top_k=2)

        assert result.original_count == 3
        assert result.reranked_count == 2
        # 文档3 分数最高排第一，文档1 其次排第二
        assert result.results[0].chunk_id == 3
        assert result.results[1].chunk_id == 1
        # 原始相似度保存到 metadata
        assert result.results[0].metadata["original_similarity"] == 0.6
        assert result.results[1].metadata["original_similarity"] == 0.8


class TestRerankResult:
    """RerankResult 测试类。"""

    def test_default_values(self) -> None:
        """测试默认值。"""
        result = RerankResult()

        assert result.results == []
        assert result.original_count == 0
        assert result.reranked_count == 0
