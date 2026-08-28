"""
RAG 评估 API 测试。

Description:
    测试 RAG 效果评估相关 API 端点（mock 数据库层与 RAG 日志，不依赖真实 PG）。
@author ganjianfei
@version 1.0.0
2026-04-05
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from src.db import get_db

# 统一的 RAG 日志统计 mock 数据
_RAG_STATS = {
    "total_retrievals": 10,
    "total_queries": 10,
    "avg_similarity": 0.6,
    "avg_quality_score": 0.8,
    "total_quality_scores": 10,
}
_CHUNK_STATS = {
    "total_retrievals": 10,
    "unique_chunks_hit": 5,
    "unique_docs_hit": 2,
    "top_chunks": [],
}


@pytest.fixture
def client() -> TestClient:
    """创建测试客户端。"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def _inject_mock_db():
    """注入 mock 数据库会话与 RAG 日志，避免测试发起真实 DB 连接。"""
    mock_session = AsyncMock()

    async def _execute(*_args, **_kwargs):
        result = MagicMock()
        result.scalar.return_value = 0
        result.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
        result.all.return_value = []
        return result

    mock_session.execute = AsyncMock(side_effect=_execute)

    mock_logger = MagicMock()
    mock_logger.get_usage_stats = AsyncMock(return_value=_RAG_STATS)
    mock_logger.get_chunk_hit_rate = AsyncMock(return_value=_CHUNK_STATS)

    app.dependency_overrides[get_db] = lambda: mock_session
    with patch("src.rag.logger.get_rag_logger", return_value=mock_logger):
        yield mock_session
    app.dependency_overrides.clear()


class TestHitRateAPI:
    """命中率 API 测试。"""

    def test_get_hit_rate(self, client: TestClient) -> None:
        """测试获取命中率统计。"""
        response = client.get("/api/v1/evaluation/hit-rate?days=7")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data


class TestComparisonAPI:
    """对比评估 API 测试。"""

    def test_compare_rag_vs_non_rag(self, client: TestClient) -> None:
        """测试 RAG 与非 RAG 对比。"""
        response = client.post(
            "/api/v1/evaluation/compare",
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "rag_stats" in data["data"]
        assert "non_rag_stats" in data["data"]


class TestReportAPI:
    """评估报告 API 测试。"""

    def test_get_report(self, client: TestClient) -> None:
        """测试获取评估报告。"""
        response = client.get("/api/v1/evaluation/report?days=30")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "summary" in data["data"]
        assert "recommendations" in data["data"]


class TestOptimizeSuggestionsAPI:
    """优化建议 API 测试。"""

    def test_get_optimize_suggestions(self, client: TestClient) -> None:
        """测试获取优化建议。"""
        response = client.get("/api/v1/evaluation/optimize-suggestions")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert isinstance(data["data"], list)
