"""
知识库 API 测试。

Description:
    测试知识库管理相关 API 端点（mock 数据库层，不依赖真实 PG/Redis）。
@author ganjianfei
@version 1.0.0
2026-04-05
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from src.db import get_db


@pytest.fixture
def client() -> TestClient:
    """创建测试客户端。"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def _inject_mock_db():
    """注入 mock 数据库会话，避免测试发起真实 DB 连接。"""
    mock_session = AsyncMock()

    async def _execute(*_args, **_kwargs):
        result = MagicMock()
        result.scalar.return_value = 0
        # scalars().all() 为同步调用（list_documents 内直接迭代）
        result.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
        result.all.return_value = []
        return result

    mock_session.execute = AsyncMock(side_effect=_execute)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    app.dependency_overrides[get_db] = lambda: mock_session
    # 端点内部构造真实 KnowledgeRetriever / VectorStore，统一替换为 mock
    mock_retriever = AsyncMock()
    mock_retriever.retrieve.return_value = MagicMock(results=[], total=0)
    with (
        patch("src.rag.retriever.KnowledgeRetriever") as MockRetriever,
        patch("src.db.vector_store.VectorStore") as MockVectorStore,
    ):
        MockRetriever.return_value = mock_retriever
        MockVectorStore.return_value.get_stats = AsyncMock(
            return_value={
                "total_documents": 0,
                "total_chunks": 0,
                "documents_by_type": {},
            }
        )
        yield mock_session
    app.dependency_overrides.clear()


class TestKnowledgeDocumentAPI:
    """知识库文档 API 测试。"""

    def test_list_documents(self, client: TestClient) -> None:
        """测试获取文档列表。"""
        response = client.get("/api/v1/knowledge/documents")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_get_stats(self, client: TestClient) -> None:
        """测试获取统计信息。"""
        response = client.get("/api/v1/knowledge/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200


class TestKnowledgeSearchAPI:
    """知识库检索 API 测试。"""

    def test_search_knowledge(self, client: TestClient) -> None:
        """测试知识检索。"""
        response = client.post(
            "/api/v1/knowledge/search",
            json={
                "query": "品牌规范",
                "top_k": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
