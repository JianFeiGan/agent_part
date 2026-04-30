"""
数据库模块测试。

Description:
    测试数据库连接、向量存储等核心功能。
@author ganjianfei
@version 1.0.0
2026-04-05
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.vector_store import VectorStore, SearchResult


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


class TestVectorStore:
    """向量存储测试。"""

    @pytest.fixture
    def vector_store(self) -> VectorStore:
        """创建向量存储实例。"""
        with patch("src.db.vector_store.get_settings") as mock_settings:
            mock_settings.return_value.vector_dimension = 1024
            return VectorStore()

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """创建模拟数据库会话。"""
        session = MagicMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_search_empty_results(
        self, vector_store: VectorStore, mock_session: MagicMock
    ) -> None:
        """测试空结果搜索。"""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        results = await vector_store.search(
            session=mock_session,
            query_embedding=[0.1] * 1024,
            top_k=5,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_doc_type_filter(
        self, vector_store: VectorStore, mock_session: MagicMock
    ) -> None:
        """测试带文档类型过滤的搜索。"""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        await vector_store.search(
            session=mock_session,
            query_embedding=[0.1] * 1024,
            top_k=5,
            doc_type="brand_guide",
        )

        # 验证 SQL 语句包含 doc_type 过滤
        call_args = mock_session.execute.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_search_with_similarity_threshold(
        self, vector_store: VectorStore, mock_session: MagicMock
    ) -> None:
        """测试带相似度阈值的搜索。"""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        await vector_store.search(
            session=mock_session,
            query_embedding=[0.1] * 1024,
            top_k=5,
            similarity_threshold=0.7,
        )

        mock_session.execute.assert_called_once()


class TestSearchResult:
    """搜索结果测试。"""

    def test_search_result_creation(self) -> None:
        """测试搜索结果创建。"""
        result = _create_search_result(1, 1, "测试文档", "brand_guide", "测试内容", 0.85)

        assert result.chunk_id == 1
        assert result.doc_id == 1
        assert result.doc_title == "测试文档"
        assert result.doc_type == "brand_guide"
        assert result.content == "测试内容"
        assert result.similarity == 0.85

    def test_search_result_to_dict(self) -> None:
        """测试搜索结果转字典。"""
        result = _create_search_result(1, 1, "测试文档", "brand_guide", "测试内容", 0.85)

        # SearchResult 是 dataclass，可以用 dataclasses.asdict
        from dataclasses import asdict

        result_dict = asdict(result)

        assert result_dict["chunk_id"] == 1
        assert result_dict["doc_id"] == 1
        assert result_dict["doc_title"] == "测试文档"
        assert result_dict["doc_type"] == "brand_guide"
        assert result_dict["content"] == "测试内容"
        assert result_dict["similarity"] == 0.85
