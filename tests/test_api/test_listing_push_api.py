"""刊登推送 API 测试。"""

import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestListingPushAPI:
    """测试刊登推送 API。"""

    def test_push_listing(self, client: TestClient) -> None:
        """测试推送刊登。"""
        client.post(
            "/api/v1/listing/import-product",
            json={
                "sku": "PUSH-TEST-001",
                "title": "Push Test Product",
                "description": "Testing push",
            },
        )
        task_resp = client.post(
            "/api/v1/listing/tasks",
            json={
                "product_sku": "PUSH-TEST-001",
                "target_platforms": ["amazon"],
            },
        )
        task_id = task_resp.json()["data"]["task_id"]

        push_resp = client.post(f"/api/v1/listing/tasks/{task_id}/push")
        assert push_resp.status_code == 200
        data = push_resp.json()
        assert data["code"] == 200
        assert data["data"]["task_id"] == task_id

    def test_push_task_not_found(self, client: TestClient) -> None:
        """测试推送不存在的任务。"""
        response = client.post("/api/v1/listing/tasks/9999/push")
        data = response.json()
        assert data["code"] == 404

    def test_get_push_results(self, client: TestClient) -> None:
        """测试查询推送结果。"""
        client.post(
            "/api/v1/listing/import-product",
            json={
                "sku": "PUSH-TEST-002",
                "title": "Push Test 2",
            },
        )
        task_resp = client.post(
            "/api/v1/listing/tasks",
            json={
                "product_sku": "PUSH-TEST-002",
                "target_platforms": ["amazon"],
            },
        )
        task_id = task_resp.json()["data"]["task_id"]

        client.post(f"/api/v1/listing/tasks/{task_id}/push")

        result_resp = client.get(
            f"/api/v1/listing/tasks/{task_id}/push-results"
        )
        assert result_resp.status_code == 200
        data = result_resp.json()
        assert data["code"] == 200

    def test_get_push_results_not_found(self, client: TestClient) -> None:
        """测试查询不存在的推送结果。"""
        response = client.get("/api/v1/listing/tasks/9999/push-results")
        data = response.json()
        assert data["code"] == 404
