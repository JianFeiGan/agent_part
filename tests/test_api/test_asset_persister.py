"""AssetPersister 视觉产物落库服务测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.service.asset_persister import AssetPersister
from src.models.assets import AssetStatus, GeneratedImage, ImageFormat


@pytest.fixture
def mock_repo() -> MagicMock:
    """模拟 AssetRepository。"""
    repo = MagicMock()
    repo.create_asset = AsyncMock()
    return repo


@pytest.fixture
def generated_image() -> GeneratedImage:
    """创建测试用生成图片。"""
    return GeneratedImage(
        image_id="img_001",
        image_type="main",
        prompt="Product photography",
        url="https://example.com/img_001.png",
        format=ImageFormat.PNG,
        width=1024,
        height=1024,
        status=AssetStatus.COMPLETED,
        model="wanx-v1",
    )


@pytest.mark.asyncio
async def test_persist_images_creates_asset(
    mock_repo: MagicMock, generated_image: GeneratedImage
) -> None:
    """测试图片落库创建资产记录。"""
    persister = AssetPersister(repo=mock_repo)

    await persister.persist_images(
        tenant_id="tenant-1",
        product_id="prod_001",
        task_id="task_abc",
        images=[generated_image],
    )

    mock_repo.create_asset.assert_called_once()
    call_kwargs = mock_repo.create_asset.call_args.kwargs
    assert call_kwargs["tenant_id"] == "tenant-1"
    assert call_kwargs["product_id"] == "prod_001"
    assert call_kwargs["task_id"] == "task_abc"
    assert call_kwargs["asset_type"] == "image"
    assert call_kwargs["url"] == "https://example.com/img_001.png"
    assert call_kwargs["mime_type"] == "image/png"
    assert call_kwargs["width"] == 1024
    assert call_kwargs["is_mock"] is False


@pytest.mark.asyncio
async def test_persist_images_skips_not_ready(
    mock_repo: MagicMock, generated_image: GeneratedImage
) -> None:
    """测试跳过未就绪（无 url）的图片。"""
    generated_image.url = None
    generated_image.local_path = None
    persister = AssetPersister(repo=mock_repo)

    count = await persister.persist_images(
        tenant_id="tenant-1",
        product_id="prod_001",
        task_id="task_abc",
        images=[generated_image],
    )

    assert count == 0
    mock_repo.create_asset.assert_not_called()


@pytest.mark.asyncio
async def test_persist_images_marks_mock(
    mock_repo: MagicMock, generated_image: GeneratedImage
) -> None:
    """测试 mock 模式标记 is_mock。"""
    generated_image.model = "mock"
    persister = AssetPersister(repo=mock_repo)

    await persister.persist_images(
        tenant_id="tenant-1",
        product_id="prod_001",
        task_id="task_abc",
        images=[generated_image],
    )

    call_kwargs = mock_repo.create_asset.call_args.kwargs
    assert call_kwargs["is_mock"] is True
    assert call_kwargs["provider"] == "mock"


@pytest.mark.asyncio
async def test_persist_images_extra_data(
    mock_repo: MagicMock, generated_image: GeneratedImage
) -> None:
    """测试 extra_data 包含 image_type 和 image_id。"""
    persister = AssetPersister(repo=mock_repo)

    await persister.persist_images(
        tenant_id="tenant-1",
        product_id="prod_001",
        task_id="task_abc",
        images=[generated_image],
    )

    call_kwargs = mock_repo.create_asset.call_args.kwargs
    extra = call_kwargs["extra_data"]
    assert extra["image_type"] == "main"
    assert extra["image_id"] == "img_001"
