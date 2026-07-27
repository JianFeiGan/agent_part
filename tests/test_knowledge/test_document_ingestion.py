"""文档摄入服务测试。"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.knowledge.document_ingestion import DocumentIngestionService
from src.knowledge.models import KnowledgeGraph


class TestDocumentIngestionService:
    """文档摄入服务测试。"""

    @pytest.fixture
    def service(self):
        """创建服务实例。"""
        return DocumentIngestionService()

    def test_service_initialization(self, service):
        """测试服务初始化。"""
        assert service is not None
        assert service.chunk_size == 512
        assert service.chunk_overlap == 64

    @pytest.mark.asyncio
    async def test_parse_markdown_document(self, service):
        """测试解析 Markdown 文档。"""
        content = """# 产品说明

这是一个智能手表产品。

## 功能特点
- 心率监测
- GPS 定位
"""
        result = await service.parse_document(content, "markdown")
        assert result is not None
        assert len(result["chunks"]) > 0

    @pytest.mark.asyncio
    async def test_chunk_document(self, service):
        """测试文档分块。"""
        content = "这是第一句话。这是第二句话。这是第三句话。"
        chunks = await service.chunk_document(content, chunk_size=20)
        assert len(chunks) >= 1

    @pytest.mark.asyncio
    async def test_process_document(self, service):
        """测试完整文档处理流程。"""
        document = {
            "id": "doc_001",
            "title": "测试文档",
            "content": "这是一个测试文档内容，用于验证文档处理流程。",
            "format": "markdown",
        }
        graph = KnowledgeGraph(
            id="kg_001",
            name="测试图谱",
            tenant_id="tenant_001",
        )

        with patch.object(
            service, "generate_embedding", new_callable=AsyncMock
        ) as mock_embed:
            mock_embed.return_value = [0.1] * 1024
            result = await service.process_document(document, graph)

        assert result is not None
        assert result["document_id"] == "doc_001"
        assert len(result["chunks"]) > 0
        assert result["chunks"][0]["embedding"] is not None