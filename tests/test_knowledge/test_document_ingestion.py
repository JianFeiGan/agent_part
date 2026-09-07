"""文档摄入服务测试。

覆盖 src.knowledge.ingestion.DocumentIngestionService 的真实契约：
当前为占位实现，process_document 返回 pending 状态结果。
"""

import pytest

from src.knowledge.graph import KnowledgeGraph
from src.knowledge.ingestion import DocumentIngestionService


class TestDocumentIngestionService:
    """文档摄入服务测试。"""

    @pytest.fixture
    def service(self):
        """创建服务实例。"""
        return DocumentIngestionService()

    def test_service_initialization(self, service):
        """测试服务初始化。"""
        assert service is not None

    @pytest.mark.asyncio
    async def test_process_document_returns_pending(self, service):
        """测试占位实现返回 pending 状态。"""
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

        result = await service.process_document(document, graph)

        assert result is not None
        assert result["document_id"] == "doc_001"
        assert result["status"] == "pending"
        assert "message" in result
