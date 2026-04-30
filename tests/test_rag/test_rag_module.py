"""
RAG 模块测试。

Description:
    测试 RAG 核心组件：Embedding、Chunker、Retriever。
@author ganjianfei
@version 1.0.0
2026-04-05
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.rag.chunker import SemanticChunker, Chunk
from src.rag.retriever import KnowledgeRetriever, RetrievalResult
from src.db.vector_store import SearchResult


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


class TestEmbeddingService:
    """Embedding 服务测试。"""

    def test_service_initialization(self) -> None:
        """测试服务初始化。"""
        with patch("src.rag.embeddings.get_settings") as mock_settings:
            mock_settings.return_value.embedding_model = "BAAI/bge-large-zh"
            mock_settings.return_value.embedding_device = "cpu"

            from src.rag.embeddings import EmbeddingService

            service = EmbeddingService()

            assert service.settings is not None
            assert service._initialized is False


class TestSemanticChunker:
    """语义分块器测试。"""

    @pytest.fixture
    def chunker(self) -> SemanticChunker:
        """创建分块器实例。"""
        with patch("src.rag.chunker.get_settings") as mock_settings:
            mock_settings.return_value.chunk_size = 500
            mock_settings.return_value.chunk_overlap = 50
            return SemanticChunker()

    def test_split_empty_text(self, chunker: SemanticChunker) -> None:
        """测试空文本分块。"""
        chunks = chunker.split("")
        assert chunks == []

    def test_split_short_text(self, chunker: SemanticChunker) -> None:
        """测试短文本分块。"""
        text = "这是一段短文本。"
        chunks = chunker.split(text)

        # 短文本应该返回单个分块
        assert len(chunks) == 1
        assert chunks[0].content == text

    def test_split_long_text(self, chunker: SemanticChunker) -> None:
        """测试长文本分块。"""
        # 生成足够长的文本
        text = "这是测试句子。" * 200
        chunks = chunker.split(text)

        assert len(chunks) >= 1

    def test_split_with_metadata(self, chunker: SemanticChunker) -> None:
        """测试带元数据的分块。"""
        text = "这是测试文本。" * 50
        metadata = {"doc_type": "brand_guide", "source": "test"}
        chunks = chunker.split(text, metadata=metadata)

        for chunk in chunks:
            assert chunk.metadata.get("doc_type") == "brand_guide"
            assert chunk.metadata.get("source") == "test"


class TestKnowledgeRetriever:
    """知识检索器测试。"""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """创建模拟数据库会话。"""
        session = MagicMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def retriever(self) -> KnowledgeRetriever:
        """创建检索器实例。"""
        with patch("src.rag.retriever.get_embedding_service") as mock_emb:
            with patch("src.rag.retriever.VectorStore") as mock_vs:
                mock_emb.return_value = MagicMock()
                return KnowledgeRetriever()

    def test_build_context(self, retriever: KnowledgeRetriever) -> None:
        """测试上下文构建。"""
        results = [
            _create_search_result(1, 1, "品牌规范", "brand_guide", "品牌调性说明", 0.85),
            _create_search_result(2, 2, "类目知识", "category_knowledge", "商品特点", 0.75),
        ]

        context = retriever._build_context(results)

        assert "品牌规范" in context
        assert "类目知识" in context
        assert "品牌调性说明" in context
        assert "商品特点" in context

    def test_build_context_empty(self, retriever: KnowledgeRetriever) -> None:
        """测试空结果上下文构建。"""
        context = retriever._build_context([])
        assert context == ""

    def test_extract_sources(self, retriever: KnowledgeRetriever) -> None:
        """测试来源提取。"""
        results = [
            _create_search_result(1, 1, "测试文档", "brand_guide", "内容", 0.85),
        ]

        sources = retriever._extract_sources(results)

        assert len(sources) == 1
        assert sources[0]["chunk_id"] == 1
        assert sources[0]["doc_id"] == 1
        assert sources[0]["doc_title"] == "测试文档"

    def test_deduplicate_results(self, retriever: KnowledgeRetriever) -> None:
        """测试结果去重。"""
        results = [
            _create_search_result(1, 1, "文档1", "brand_guide", "内容1", 0.85),
            _create_search_result(1, 1, "文档1", "brand_guide", "内容1", 0.85),  # 重复
            _create_search_result(2, 2, "文档2", "brand_guide", "内容2", 0.75),
        ]

        unique = retriever._deduplicate_results(results)

        assert len(unique) == 2
        assert unique[0].chunk_id == 1
        assert unique[1].chunk_id == 2


class TestRetrievalResult:
    """检索结果测试。"""

    def test_result_creation(self) -> None:
        """测试结果创建。"""
        result = RetrievalResult(
            query="测试查询",
            results=[],
            context="",
            sources=[],
        )

        assert result.query == "测试查询"
        assert len(result.results) == 0
        assert result.context == ""

    def test_result_with_data(self) -> None:
        """测试带数据的结果。"""
        search_result = _create_search_result(1, 1, "测试文档", "brand_guide", "测试内容", 0.85)

        result = RetrievalResult(
            query="测试查询",
            results=[search_result],
            context="上下文内容",
            sources=[{"chunk_id": 1, "doc_id": 1}],
        )

        assert len(result.results) == 1
        assert result.results[0].chunk_id == 1
        assert len(result.sources) == 1


class TestChunk:
    """分块模型测试。"""

    def test_chunk_creation(self) -> None:
        """测试分块创建。"""
        chunk = Chunk(
            content="测试内容",
            index=0,
            metadata={"doc_type": "brand_guide"},
        )

        assert chunk.content == "测试内容"
        assert chunk.index == 0
        assert chunk.metadata["doc_type"] == "brand_guide"

    def test_chunk_with_extra_metadata(self) -> None:
        """测试带额外元数据的分块。"""
        chunk = Chunk(
            content="测试内容",
            index=1,
            metadata={
                "doc_type": "category_knowledge",
                "category": "digital",
                "chunk_index": 1,
            },
        )

        assert chunk.metadata["doc_type"] == "category_knowledge"
        assert chunk.metadata["category"] == "digital"
        assert chunk.metadata["chunk_index"] == 1
