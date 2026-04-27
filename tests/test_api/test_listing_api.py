"""刊登 API 测试（mock 数据库层）。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from main import app

from src.db.listing_models import ComplianceReportPO, ListingProductPO, ListingTaskPO
from src.models.listing import ListingProduct, Platform


def _make_product_po(**kwargs) -> MagicMock:
    """构造模拟 ListingProductPO。"""
    defaults = {
        "id": 1,
        "sku": "TEST-001",
        "title": "Test Product",
        "description": "A test product",
        "category": "Electronics",
        "brand": "TestBrand",
        "price": None,
        "weight": None,
        "dimensions": None,
        "source_images": [],
        "attributes": {},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    po = MagicMock(spec=ListingProductPO)
    for k, v in defaults.items():
        setattr(po, k, v)
    return po


def _make_task_po(**kwargs) -> MagicMock:
    """构造模拟 ListingTaskPO。"""
    defaults = {
        "id": 1,
        "product_sku": "TEST-001",
        "target_platforms": ["amazon"],
        "status": "pending",
        "workflow_state": None,
        "auto_execute": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    po = MagicMock(spec=ListingTaskPO)
    for k, v in defaults.items():
        setattr(po, k, v)
    return po


def _make_compliance_po(**kwargs) -> MagicMock:
    """构造模拟 ComplianceReportPO。"""
    defaults = {
        "id": 1,
        "task_id": 1,
        "platform": "amazon",
        "report_data": {
            "overall": "pass",
            "image_issues": [],
            "text_issues": [],
            "forbidden_words": [],
        },
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    po = MagicMock(spec=ComplianceReportPO)
    for k, v in defaults.items():
        setattr(po, k, v)
    return po


def _mock_get_db():
    """创建 get_db mock 上下文管理器。"""
    mock_session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm, mock_session


@pytest.fixture
def client() -> TestClient:
    """创建测试客户端。"""
    return TestClient(app)


class TestProductImportAPI:
    """测试商品导入 API。"""

    def test_import_product_success(self, client: TestClient) -> None:
        """测试成功导入商品。"""
        mock_po = _make_product_po(sku="API-TEST-001", title="Test Product via API")
        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock(return_value=mock_po)

        cm, _ = _mock_get_db()

        with (
            patch("src.api.router.listing.get_db", return_value=cm),
            patch("src.api.router.listing.BaseRepository", return_value=mock_repo),
            patch("src.agents.listing_importer.ImportProductAgent") as MockAgent,
        ):
            mock_agent = MagicMock()
            mock_agent.execute_manual.return_value = {
                "success": True,
                "product": ListingProduct(sku="API-TEST-001", title="Test Product via API"),
            }
            MockAgent.return_value = mock_agent

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
        assert response.status_code == 422

    def test_list_products(self, client: TestClient) -> None:
        """测试商品列表。"""
        mock_po = _make_product_po(sku="LIST-001")
        mock_repo = AsyncMock()
        mock_repo.list = AsyncMock(return_value=[mock_po])

        cm, _ = _mock_get_db()

        with (
            patch("src.api.router.listing.get_db", return_value=cm),
            patch("src.api.router.listing.BaseRepository", return_value=mock_repo),
        ):
            response = client.get("/api/v1/listing/products")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert len(data["data"]) == 1


class TestListingTaskAPI:
    """测试刊登任务 API。"""

    def test_create_task_product_not_found(self, client: TestClient) -> None:
        """测试创建任务时商品不存在返回业务码404。"""
        mock_product_repo = AsyncMock()
        mock_product_repo.get_by_field = AsyncMock(return_value=None)

        cm, _ = _mock_get_db()

        def repo_factory(model, session):
            if model is ListingProductPO:
                return mock_product_repo
            return AsyncMock()

        with (
            patch("src.api.router.listing.get_db", return_value=cm),
            patch("src.api.router.listing.BaseRepository", side_effect=repo_factory),
        ):
            response = client.post(
                "/api/v1/listing/tasks",
                json={
                    "product_sku": "NONEXISTENT-SKU",
                    "target_platforms": ["amazon", "ebay"],
                },
            )
            assert response.status_code == 201
            data = response.json()
            assert data["code"] == 404

    def test_list_tasks_empty(self, client: TestClient) -> None:
        """测试空任务列表。"""
        mock_repo = AsyncMock()
        mock_repo.list = AsyncMock(return_value=[])

        cm, _ = _mock_get_db()

        with (
            patch("src.api.router.listing.get_db", return_value=cm),
            patch("src.api.router.listing.BaseRepository", return_value=mock_repo),
        ):
            response = client.get("/api/v1/listing/tasks")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert data["data"] == []

    def test_create_and_list_task(self, client: TestClient) -> None:
        """测试完整流程：创建任务 → 查询任务。"""
        mock_product_po = _make_product_po(sku="FLOW-TEST-001", title="Flow Test Product")
        mock_task_po = _make_task_po(id=1, product_sku="FLOW-TEST-001", target_platforms=["amazon"])
        mock_product_repo = AsyncMock()
        mock_product_repo.get_by_field = AsyncMock(return_value=mock_product_po)
        mock_task_repo = AsyncMock()
        mock_task_repo.create = AsyncMock(return_value=mock_task_po)
        mock_task_repo.list = AsyncMock(return_value=[mock_task_po])

        cm, _ = _mock_get_db()

        call_count = [0]

        def repo_factory(model, session):
            if model is ListingProductPO:
                return mock_product_repo
            if model is ListingTaskPO:
                return mock_task_repo
            return AsyncMock()

        with (
            patch("src.api.router.listing.get_db", return_value=cm),
            patch("src.api.router.listing.BaseRepository", side_effect=repo_factory),
        ):
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


class TestComplianceAPI:
    """测试合规报告 API。"""

    def test_run_compliance_check(self, client: TestClient) -> None:
        """测试执行合规检查。"""
        mock_task_po = _make_task_po(id=1, product_sku="COMPL-001", target_platforms=["amazon"])
        mock_product_po = _make_product_po(sku="COMPL-001", title="Clean Product")

        mock_task_repo = AsyncMock()
        mock_task_repo.get = AsyncMock(return_value=mock_task_po)
        mock_product_repo = AsyncMock()
        mock_product_repo.get_by_field = AsyncMock(return_value=mock_product_po)

        cm, mock_session = _mock_get_db()

        def repo_factory(model, session):
            if model is ListingTaskPO:
                return mock_task_repo
            if model is ListingProductPO:
                return mock_product_repo
            return AsyncMock()

        from src.models.listing import ComplianceReport, ComplianceStatus

        mock_report = ComplianceReport(
            id=1,
            listing_task_id=1,
            platform=Platform.AMAZON,
            overall=ComplianceStatus.PASS,
        )

        with (
            patch("src.api.router.listing.get_db", return_value=cm),
            patch("src.api.router.listing.BaseRepository", side_effect=repo_factory),
            patch("src.agents.listing_compliance_checker.ComplianceCheckerAgent") as MockAgent,
        ):
            mock_checker = MagicMock()
            mock_checker.execute_sync.return_value = {
                "compliance_reports": {Platform.AMAZON: mock_report},
            }
            MockAgent.return_value = mock_checker

            check_resp = client.post("/api/v1/listing/tasks/1/compliance")
            assert check_resp.status_code == 201
            data = check_resp.json()
            assert data["code"] == 200
            assert "amazon" in data["data"]

    def test_get_compliance_report(self, client: TestClient) -> None:
        """测试查询合规报告。"""
        mock_report_po = _make_compliance_po(
            task_id=2,
            platform="ebay",
            report_data={
                "overall": "pass",
                "image_issues": [],
                "text_issues": [],
                "forbidden_words": [],
            },
        )
        mock_repo = AsyncMock()
        mock_repo.list = AsyncMock(return_value=[mock_report_po])

        cm, _ = _mock_get_db()

        with (
            patch("src.api.router.listing.get_db", return_value=cm),
            patch("src.api.router.listing.BaseRepository", return_value=mock_repo),
        ):
            report_resp = client.get("/api/v1/listing/compliance/2")
            assert report_resp.status_code == 200
            data = report_resp.json()
            assert data["code"] == 200
            assert "ebay" in data["data"]

    def test_get_compliance_report_not_found(self, client: TestClient) -> None:
        """测试查询不存在的合规报告。"""
        mock_repo = AsyncMock()
        mock_repo.list = AsyncMock(return_value=[])

        cm, _ = _mock_get_db()

        with (
            patch("src.api.router.listing.get_db", return_value=cm),
            patch("src.api.router.listing.BaseRepository", return_value=mock_repo),
        ):
            response = client.get("/api/v1/listing/compliance/9999")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 404
