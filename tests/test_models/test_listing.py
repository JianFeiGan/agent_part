"""刊登工具数据模型测试。"""

from datetime import datetime
from decimal import Decimal

import pytest

from src.models.listing import (
    ListingProduct,
    ImageRef,
    AssetPackage,
    CopywritingPackage,
    ListingTask,
    TaskStatus,
    Platform,
)


class TestListingProduct:
    """测试 ListingProduct 模型。"""

    def test_create_minimal(self) -> None:
        """测试最小创建。"""
        product = ListingProduct(sku="TEST-001", title="测试商品")
        assert product.sku == "TEST-001"
        assert product.title == "测试商品"
        assert product.brand is None

    def test_create_full(self) -> None:
        """测试完整创建。"""
        product = ListingProduct(
            sku="TEST-002",
            title="Wireless Bluetooth Headphones",
            description="High-quality wireless headphones with noise cancellation",
            category="Electronics",
            brand="SoundMax",
            price=Decimal("49.99"),
            weight=Decimal("0.35"),
            dimensions={"length": 20, "width": 18, "height": 8, "unit": "cm"},
            source_images=[
                ImageRef(url="https://example.com/img1.jpg", is_main=True),
                ImageRef(url="https://example.com/img2.jpg", is_main=False),
            ],
            attributes={"color": "Black", "connectivity": "Bluetooth 5.0"},
        )
        assert product.price == Decimal("49.99")
        assert len(product.source_images) == 2
        assert product.source_images[0].is_main is True

    def test_main_image(self) -> None:
        """测试获取主图。"""
        product = ListingProduct(
            sku="TEST-003",
            title="Test",
            source_images=[
                ImageRef(url="https://example.com/secondary.jpg", is_main=False),
                ImageRef(url="https://example.com/main.jpg", is_main=True),
            ],
        )
        main = product.main_image
        assert main is not None
        assert main.url == "https://example.com/main.jpg"

    def test_main_image_none(self) -> None:
        """测试无主图时返回 None。"""
        product = ListingProduct(sku="TEST-004", title="Test")
        assert product.main_image is None


class TestAssetPackage:
    """测试 AssetPackage 模型。"""

    def test_create(self) -> None:
        """测试创建素材包。"""
        pkg = AssetPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            main_image="https://example.com/main.jpg",
        )
        assert pkg.platform == Platform.AMAZON
        assert pkg.main_image is not None
        assert len(pkg.variant_images) == 0


class TestCopywritingPackage:
    """测试 CopywritingPackage 模型。"""

    def test_create(self) -> None:
        """测试创建文案包。"""
        pkg = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            language="en",
            title="Premium Wireless Bluetooth Headphones",
            bullet_points=[
                "Advanced noise cancellation technology",
                "40-hour battery life",
            ],
            description="Experience premium sound quality...",
            search_terms=["wireless", "bluetooth", "headphones"],
        )
        assert len(pkg.bullet_points) == 2
        assert len(pkg.search_terms) == 3


class TestListingTask:
    """测试 ListingTask 模型。"""

    def test_create(self) -> None:
        """测试创建任务。"""
        task = ListingTask(
            product_id=1,
            target_platforms=[Platform.AMAZON, Platform.EBAY],
        )
        assert task.status == TaskStatus.PENDING
        assert len(task.target_platforms) == 2

    def test_mark_generating(self) -> None:
        """测试状态转换。"""
        task = ListingTask(product_id=1, target_platforms=[Platform.AMAZON])
        task.mark_generating()
        assert task.status == TaskStatus.GENERATING