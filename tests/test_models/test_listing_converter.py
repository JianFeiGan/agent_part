"""Product -> ListingProduct 转换器测试。"""

import pytest

from src.models.listing_converter import product_to_listing
from src.models.product import Product, ProductCategory


@pytest.fixture
def visual_product() -> Product:
    """创建视觉生成用的商品。"""
    return Product(
        product_id="prod_001",
        name="智能运动手表",
        brand="TechFit",
        category=ProductCategory.DIGITAL,
        description="一款集健康监测、运动追踪、智能提醒于一体的高性价比智能手表。",
    )


def test_product_to_listing_basic_fields(visual_product: Product) -> None:
    """测试基本字段映射。"""
    listing = product_to_listing(visual_product)

    assert listing.sku == "prod_001"
    assert listing.title == "智能运动手表"
    assert listing.description == "一款集健康监测、运动追踪、智能提醒于一体的高性价比智能手表。"
    assert listing.category == "digital"
    assert listing.brand == "TechFit"


def test_product_to_listing_records_source_product_id(visual_product: Product) -> None:
    """测试 source_product_id 记录到 attributes。"""
    listing = product_to_listing(visual_product)

    assert listing.attributes["source_product_id"] == "prod_001"


def test_product_to_listing_empty_source_images(visual_product: Product) -> None:
    """测试转换后 source_images 为空（由 AssetLoader 后续填充）。"""
    listing = product_to_listing(visual_product)

    assert listing.source_images == []


def test_product_to_listing_without_product_id() -> None:
    """测试无 product_id 时用 name 生成 sku。"""
    product = Product(
        name="无线耳机",
        category=ProductCategory.DIGITAL,
        description="高品质无线蓝牙耳机。",
    )
    listing = product_to_listing(product)

    assert listing.sku.startswith("VIS-")
    assert listing.title == "无线耳机"
    assert "source_product_id" not in listing.attributes
