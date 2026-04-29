"""
RAG 评估 API 测试。

Description:
    测试 RAG 效果评估相关 API 端点。
@author ganjianfei
@version 1.0.0
2026-04-05
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client() -> TestClient:
    """创建测试客户端。"""
    return TestClient(app)


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
