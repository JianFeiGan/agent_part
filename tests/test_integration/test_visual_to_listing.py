"""视觉生成到刊登端到端集成测试。

验证完整链路:
    Product -> product_to_listing -> ListingProduct（带 source_product_id）
    -> ListingAssetLoader 从 generated_assets 拉图 -> source_images 填充
    -> AssetOptimizerAgent 消费 AI 生成图
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.listing_asset_optimizer import AssetOptimizerAgent
from src.agents.listing_asset_loader import ListingAssetLoader
from src.graph.listing_state import ListingState
from src.models.listing import Platform
from src.models.listing_converter import product_to_listing
from src.models.product import Product, ProductCategory


@pytest.mark.asyncio
async def test_full_pipeline_visual_to_listing_assets() -> None:
    """测试完整链路：视觉商品转换 + 资产加载 + 素材优化。"""
    # 1. 视觉生成商品
    visual_product = Product(
        product_id="prod_001",
        name="智能运动手表",
        brand="TechFit",
        category=ProductCategory.DIGITAL,
        description="一款集健康监测、运动追踪、智能提醒于一体的高性价比智能手表。",
    )

    # 2. 转换为刊登商品
    listing_product = product_to_listing(visual_product)
    assert listing_product.attributes["source_product_id"] == "prod_001"
    assert listing_product.source_images == []

    # 3. 模拟资产加载
    mock_repo = MagicMock()
    mock_main = MagicMock()
    mock_main.asset_type = "image"
    mock_main.url = "https://example.com/main.png"
    mock_main.width = 1024
    mock_main.height = 1024
    mock_main.file_size = 500000
    mock_main.extra_data = {"image_type": "main"}
    mock_repo.list_by_product = AsyncMock(return_value=[mock_main])

    loader = ListingAssetLoader(repo=mock_repo)
    image_refs = await loader.load_images(tenant_id="tenant-1", product_id="prod_001")
    listing_product.source_images = image_refs

    assert len(listing_product.source_images) == 1
    assert listing_product.source_images[0].is_main is True
    assert listing_product.main_image.url == "https://example.com/main.png"

    # 4. 素材优化消费 AI 生成图
    state = ListingState(
        product=listing_product,
        target_platforms=[Platform.AMAZON],
    )
    optimizer = AssetOptimizerAgent()
    result = optimizer.execute_sync(state)

    asset_packages = result["asset_packages"]
    assert Platform.AMAZON in asset_packages
    assert asset_packages[Platform.AMAZON].main_image == "https://example.com/main.png"
