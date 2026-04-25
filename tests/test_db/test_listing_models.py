"""刊登数据库模型测试。"""

import pytest

from src.db.listing_models import (
    AdapterConfigPO,
    AssetPackagePO,
    ComplianceReportPO,
    CopywritingPackagePO,
    ListingProductPO,
    ListingTaskPO,
    TaskResultPO,
)


class TestListingModels:
    """测试所有 ORM 模型的定义。"""

    def test_listing_product_po_fields(self) -> None:
        """测试商品模型字段。"""
        po = ListingProductPO(
            sku="TEST-001",
            title="Test Product",
            description="A test product",
            category="Electronics",
            brand="TestBrand",
        )
        assert po.sku == "TEST-001"
        assert po.title == "Test Product"
        assert po.category == "Electronics"

    def test_listing_task_po_fields(self) -> None:
        """测试任务模型字段。"""
        po = ListingTaskPO(
            product_sku="TEST-001",
            target_platforms=["amazon", "ebay"],
            status="pending",
            workflow_state="imported",
        )
        assert po.product_sku == "TEST-001"
        assert "amazon" in po.target_platforms
        assert po.workflow_state == "imported"

    def test_asset_package_po_fields(self) -> None:
        """测试素材包模型。"""
        po = AssetPackagePO(
            task_id=1,
            platform="amazon",
            main_image="https://example.com/main.jpg",
            variant_images=["https://example.com/v1.jpg"],
        )
        assert po.task_id == 1
        assert po.platform == "amazon"
        assert len(po.variant_images) == 1

    def test_copywriting_package_po_fields(self) -> None:
        """测试文案包模型。"""
        po = CopywritingPackagePO(
            task_id=1,
            platform="ebay",
            title="Test Title",
            bullet_points=["Feature 1", "Feature 2"],
            description="Test description",
            search_terms=["test", "product"],
        )
        assert po.title == "Test Title"
        assert len(po.bullet_points) == 2

    def test_compliance_report_po_json(self) -> None:
        """测试合规报告 JSON 存储。"""
        po = ComplianceReportPO(
            task_id=1,
            platform="amazon",
            report_data={
                "overall": "pass",
                "image_issues": [],
                "text_issues": [],
                "forbidden_words": [],
            },
        )
        assert po.report_data["overall"] == "pass"

    def test_task_result_po_json(self) -> None:
        """测试结果 JSON 存储。"""
        po = TaskResultPO(
            task_id=1,
            platform="shopify",
            result_data={
                "success": True,
                "listing_id": "gid://shopify/Product/123",
                "url": "https://my-store.myshopify.com/products/test",
            },
        )
        assert po.result_data["success"] is True

    def test_adapter_config_po_fields(self) -> None:
        """测试适配器配置模型。"""
        po = AdapterConfigPO(
            platform="amazon",
            shop_id="shop-001",
            credentials={
                "client_id": "REDACTED_CLIENT_ID",
                "client_secret": "REDACTED_SECRET",
                "refresh_token": "REDACTED_TOKEN",
                "marketplace_id": "TEST_MARKETPLACE",
            },
            is_active=True,
        )
        assert po.platform == "amazon"
        assert po.shop_id == "shop-001"
        assert po.credentials["marketplace_id"] == "TEST_MARKETPLACE"
