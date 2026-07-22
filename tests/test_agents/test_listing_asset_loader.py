"""ListingAssetLoader 资产加载器测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.listing_asset_loader import ListingAssetLoader


@pytest.fixture
def mock_repo() -> MagicMock:
    """模拟 AssetRepository。"""
    return MagicMock()


@pytest.fixture
def mock_image_assets() -> list:
    """模拟图片资产 PO 列表。"""
    main = MagicMock()
    main.asset_type = "image"
    main.url = "https://example.com/main.png"
    main.width = 1024
    main.height = 1024
    main.file_size = 500000
    main.extra_data = {"image_type": "main"}

    variant = MagicMock()
    variant.asset_type = "image"
    variant.url = "https://example.com/variant.png"
    variant.width = 800
    variant.height = 800
    variant.file_size = 300000
    variant.extra_data = {"image_type": "scene"}

    video = MagicMock()
    video.asset_type = "video"
    video.url = "https://example.com/video.mp4"
    return [main, variant, video]


@pytest.mark.asyncio
async def test_load_images_returns_only_image_assets(
    mock_repo: MagicMock, mock_image_assets: list
) -> None:
    """测试只返回 image 类型资产，过滤 video。"""
    mock_repo.list_by_product = AsyncMock(return_value=mock_image_assets)
    loader = ListingAssetLoader(repo=mock_repo)

    refs = await loader.load_images(tenant_id="tenant-1", product_id="prod_001")

    assert len(refs) == 2
    assert all(r.url.startswith("https://example.com/") for r in refs)


@pytest.mark.asyncio
async def test_load_images_first_is_main(
    mock_repo: MagicMock, mock_image_assets: list
) -> None:
    """测试第一张图标记为主图。"""
    mock_repo.list_by_product = AsyncMock(return_value=mock_image_assets)
    loader = ListingAssetLoader(repo=mock_repo)

    refs = await loader.load_images(tenant_id="tenant-1", product_id="prod_001")

    assert refs[0].is_main is True
    assert refs[0].url == "https://example.com/main.png"
    assert refs[1].is_main is False


@pytest.mark.asyncio
async def test_load_images_main_type_preferred(
    mock_repo: MagicMock, mock_image_assets: list
) -> None:
    """测试 image_type=main 的资产优先作为主图。"""
    mock_repo.list_by_product = AsyncMock(return_value=mock_image_assets)
    loader = ListingAssetLoader(repo=mock_repo)

    refs = await loader.load_images(tenant_id="tenant-1", product_id="prod_001")

    assert refs[0].is_main is True
    assert refs[0].url == "https://example.com/main.png"


@pytest.mark.asyncio
async def test_load_images_empty(mock_repo: MagicMock) -> None:
    """测试无资产时返回空列表。"""
    mock_repo.list_by_product = AsyncMock(return_value=[])
    loader = ListingAssetLoader(repo=mock_repo)

    refs = await loader.load_images(tenant_id="tenant-1", product_id="prod_001")

    assert refs == []
