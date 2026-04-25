"""刊登工作流测试。"""

from src.graph.listing_state import ListingState
from src.models.listing import (
    AssetPackage,
    CopywritingPackage,
    ListingProduct,
    Platform,
)


class TestListingState:
    """测试 ListingState 状态模型。"""

    def test_initial_state(self) -> None:
        """测试初始状态。"""
        state = ListingState()
        assert state.product is None
        assert state.asset_packages == {}
        assert state.copywriting_packages == {}
        assert state.target_platforms == []
        assert state.error is None
        assert state.current_step == ""

    def test_with_product(self) -> None:
        """测试设置商品。"""
        product = ListingProduct(sku="T-001", title="Test Product")
        state = ListingState(product=product, target_platforms=[Platform.AMAZON])
        assert state.product is not None
        assert state.product.sku == "T-001"
        assert state.target_platforms == [Platform.AMAZON]

    def test_asset_package_accumulation(self) -> None:
        """测试素材包累积。"""
        state = ListingState(target_platforms=[Platform.AMAZON, Platform.EBAY])
        state.asset_packages[Platform.AMAZON] = AssetPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            main_image="https://example.com/amazon.jpg",
        )
        state.asset_packages[Platform.EBAY] = AssetPackage(
            listing_task_id=1,
            platform=Platform.EBAY,
            main_image="https://example.com/ebay.jpg",
        )
        assert len(state.asset_packages) == 2
        assert Platform.AMAZON in state.asset_packages

    def test_copywriting_package_accumulation(self) -> None:
        """测试文案包累积。"""
        state = ListingState(target_platforms=[Platform.AMAZON])
        state.copywriting_packages[Platform.AMAZON] = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            language="en",
            title="Test Title",
        )
        assert len(state.copywriting_packages) == 1