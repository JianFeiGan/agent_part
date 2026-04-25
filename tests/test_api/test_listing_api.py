"""
刊登 API 测试。
"""

import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client() -> TestClient:
    """创建测试客户端。"""
    return TestClient(app)


class TestProductImportAPI:
    """测试商品导入 API。"""

    def test_import_product_success(self, client: TestClient) -> None:
        """测试成功导入商品。"""
        response = client.post(
            "/api/v1/listing/import-product",
            json={
                "sku": "API-TEST-001",
                "title": "Test Product via API",
                "description": "A test product",
                "category": "Test",
                "brand": "TestBrand",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["sku"] == "API-TEST-001"

    def test_import_product_missing_sku(self, client: TestClient) -> None:
        """测试缺少 SKU 返回验证错误。"""
        response = client.post(
            "/api/v1/listing/import-product",
            json={"title": "No SKU Product"},
        )
        assert response.status_code == 422  # Validation error

    def test_list_products(self, client: TestClient) -> None:
        """测试商品列表。"""
        response = client.get("/api/v1/listing/products")
        assert response.status_code == 200


class TestListingTaskAPI:
    """测试刊登任务 API。"""

    def test_create_task(self, client: TestClient) -> None:
        """测试创建刊登任务（商品不存在时返回404）。"""
        response = client.post(
            "/api/v1/listing/tasks",
            json={
                "product_sku": "NONEXISTENT-SKU",
                "target_platforms": ["amazon", "ebay"],
            },
        )
        assert response.status_code == 201  # HTTP 状态码始终 201
        data = response.json()
        assert data["code"] == 404  # 商品不存在，业务码 404

    def test_list_tasks_empty(self, client: TestClient) -> None:
        """测试空任务列表。"""
        response = client.get("/api/v1/listing/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_create_and_list_task(self, client: TestClient) -> None:
        """测试完整流程：导入商品 → 创建任务 → 查询任务。"""
        # 先导入商品
        import_resp = client.post(
            "/api/v1/listing/import-product",
            json={
                "sku": "FLOW-TEST-001",
                "title": "Flow Test Product",
                "description": "Testing full flow",
            },
        )
        assert import_resp.status_code == 201

        # 创建任务
        task_resp = client.post(
            "/api/v1/listing/tasks",
            json={
                "product_sku": "FLOW-TEST-001",
                "target_platforms": ["amazon"],
            },
        )
        assert task_resp.status_code == 201
        task_data = task_resp.json()
        assert task_data["data"]["product_sku"] == "FLOW-TEST-001"

        # 查询任务列表
        list_resp = client.get("/api/v1/listing/tasks")
        assert list_resp.status_code == 200
        tasks = list_resp.json()["data"]
        assert any(t["product_sku"] == "FLOW-TEST-001" for t in tasks)
