"""刊登 Agent 测试。

Description:
    测试 ImportProductAgent、AssetOptimizerAgent、
    CopywriterAgent 和 PlatformSpec 的功能。
@author ganjianfei
@version 1.0.0
2026-04-25
"""


from src.agents.listing_asset_optimizer import AssetOptimizerAgent
from src.agents.listing_copywriter import CopywriterAgent
from src.agents.listing_importer import ImportProductAgent
from src.agents.listing_platform_specs import get_platform_spec
from src.graph.listing_state import ListingState
from src.models.listing import ImageRef, ListingProduct, Platform


class TestImportProductAgent:
    """测试 ImportProductAgent。"""

    def test_execute_with_manual_input(self) -> None:
        """测试手动录入商品。"""
        agent = ImportProductAgent()
        product_data = {
            "sku": "TEST-001",
            "title": "Wireless Headphones",
            "description": "Bluetooth headphones",
            "category": "Electronics",
            "brand": "SoundMax",
        }
        result = agent.execute_manual(product_data)
        assert result["success"] is True
        assert isinstance(result["product"], ListingProduct)
        assert result["product"].sku == "TEST-001"

    def test_execute_with_image_urls(self) -> None:
        """测试带图片的商品导入。"""
        agent = ImportProductAgent()
        product_data = {
            "sku": "TEST-002",
            "title": "Phone Case",
            "source_images": [
                {"url": "https://example.com/main.jpg", "is_main": True},
                {"url": "https://example.com/side.jpg", "is_main": False},
            ],
        }
        result = agent.execute_manual(product_data)
        assert len(result["product"].source_images) == 2
        assert result["product"].main_image is not None
        assert result["product"].main_image.url == "https://example.com/main.jpg"

    def test_execute_missing_sku(self) -> None:
        """测试缺少 SKU 时失败。"""
        agent = ImportProductAgent()
        result = agent.execute_manual({"title": "No SKU"})
        assert result["success"] is False
        assert "sku" in result.get("error", "")


class TestPlatformSpec:
    """测试平台规范。"""

    def test_amazon_spec(self) -> None:
        """测试 Amazon 规范。"""
        spec = get_platform_spec(Platform.AMAZON)
        assert spec.main_image_size == (1500, 1500)
        assert spec.white_background is True
        assert spec.max_images == 9
        assert spec.max_title_length == 200

    def test_ebay_spec(self) -> None:
        """测试 eBay 规范。"""
        spec = get_platform_spec(Platform.EBAY)
        assert spec.main_image_size == (1600, 1600)
        assert spec.white_background is True
        assert spec.max_images == 12
        assert spec.max_title_length == 80

    def test_shopify_spec(self) -> None:
        """测试 Shopify 规范。"""
        spec = get_platform_spec(Platform.SHOPIFY)
        assert spec.main_image_size == (2048, 2048)
        assert spec.white_background is False
        assert spec.max_images == 999


class TestAssetOptimizerAgent:
    """测试 AssetOptimizerAgent。"""

    def test_optimize_with_no_images(self) -> None:
        """测试无图片时返回空。"""
        state = ListingState(
            product=ListingProduct(sku="T-001", title="Test"),
            target_platforms=[Platform.AMAZON],
        )
        agent = AssetOptimizerAgent()
        result = agent.execute_sync(state)
        assert len(result["asset_packages"]) == 1
        pkg = result["asset_packages"][Platform.AMAZON]
        assert pkg.main_image is None

    def test_optimize_amazon_single_image(self) -> None:
        """测试 Amazon 单图优化。"""
        state = ListingState(
            product=ListingProduct(
                sku="T-002",
                title="Test",
                source_images=[ImageRef(url="https://example.com/test.jpg", is_main=True)],
            ),
            target_platforms=[Platform.AMAZON],
        )
        agent = AssetOptimizerAgent()
        result = agent.execute_sync(state)
        pkg = result["asset_packages"][Platform.AMAZON]
        assert pkg.main_image is not None
        assert len(pkg.variant_images) == 0

    def test_optimize_multiple_platforms(self) -> None:
        """测试多平台同时优化。"""
        state = ListingState(
            product=ListingProduct(
                sku="T-003",
                title="Test",
                source_images=[ImageRef(url="https://example.com/test.jpg", is_main=True)],
            ),
            target_platforms=[Platform.AMAZON, Platform.EBAY, Platform.SHOPIFY],
        )
        agent = AssetOptimizerAgent()
        result = agent.execute_sync(state)
        assert len(result["asset_packages"]) == 3


class TestCopywriterAgent:
    """测试 CopywriterAgent。"""

    def test_generate_amazon_copy(self) -> None:
        """测试 Amazon 文案生成。"""
        state = ListingState(
            product=ListingProduct(
                sku="T-010",
                title="Wireless Bluetooth Headphones",
                description="Premium noise-cancelling headphones",
                brand="SoundMax",
                category="Electronics",
            ),
            target_platforms=[Platform.AMAZON],
        )
        agent = CopywriterAgent()
        result = agent.execute_sync(state)
        assert Platform.AMAZON in result["copywriting_packages"]
        pkg = result["copywriting_packages"][Platform.AMAZON]
        assert pkg.platform == Platform.AMAZON
        assert pkg.language == "en"
        assert len(pkg.title) <= 200

    def test_generate_ebay_copy_truncates_title(self) -> None:
        """测试 eBay 文案（标题截断到80字符）。"""
        state = ListingState(
            product=ListingProduct(
                sku="T-011",
                title="A Very Long Product Title That Would Exceed Eighty Characters Limit For eBay Platform",
                description="Some description",
            ),
            target_platforms=[Platform.EBAY],
        )
        agent = CopywriterAgent()
        result = agent.execute_sync(state)
        pkg = result["copywriting_packages"][Platform.EBAY]
        assert len(pkg.title) <= 80

    def test_generate_shopify_copy(self) -> None:
        """测试 Shopify 文案（无标题长度限制）。"""
        long_title = "A" * 300
        state = ListingState(
            product=ListingProduct(
                sku="T-012",
                title=long_title,
                description="Detailed description",
            ),
            target_platforms=[Platform.SHOPIFY],
        )
        agent = CopywriterAgent()
        result = agent.execute_sync(state)
        pkg = result["copywriting_packages"][Platform.SHOPIFY]
        assert len(pkg.title) == len(long_title)

    def test_generate_multi_platform_copy(self) -> None:
        """测试多平台同时生成。"""
        state = ListingState(
            product=ListingProduct(sku="T-013", title="Multi-Platform Product"),
            target_platforms=[Platform.AMAZON, Platform.EBAY, Platform.SHOPIFY],
        )
        agent = CopywriterAgent()
        result = agent.execute_sync(state)
        assert len(result["copywriting_packages"]) == 3
