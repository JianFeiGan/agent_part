"""listing 工作流 _import_node 接入资产加载测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.listing import ImageRef, ListingProduct


@pytest.mark.asyncio
async def test_import_node_loads_assets_for_source_product() -> None:
    """测试有 source_product_id 时加载 AI 生成图。"""
    from src.graph.listing_workflow import ListingWorkflow

    product = ListingProduct(
        sku="prod_001",
        title="智能手表",
        description="智能手表的描述信息",
        attributes={"source_product_id": "prod_001"},
    )

    workflow = ListingWorkflow()
    state = MagicMock()
    state.product = product
    state.tenant_id = "tenant-1"

    mock_image_ref = ImageRef(
        url="https://example.com/main.png",
        is_main=True,
        width=1024,
        height=1024,
    )

    with (
        patch("src.graph.listing_workflow.ListingAssetLoader") as mock_loader_cls,
        patch("src.graph.listing_workflow.get_db_session") as mock_get_session,
    ):
        mock_loader = MagicMock()
        mock_loader.load_images = AsyncMock(return_value=[mock_image_ref])
        mock_loader_cls.return_value = mock_loader

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_get_session.return_value = mock_session

        result = await workflow._import_node(state)

    assert result["product"].source_images == [mock_image_ref]
    mock_loader.load_images.assert_called_once_with(
        tenant_id="tenant-1", product_id="prod_001"
    )


@pytest.mark.asyncio
async def test_import_node_no_source_product_id_unchanged() -> None:
    """测试无 source_product_id 时商品不变。"""
    from src.graph.listing_workflow import ListingWorkflow

    product = ListingProduct(
        sku="SKU-001",
        title="普通商品",
        description="普通商品的描述信息",
        attributes={},
    )

    workflow = ListingWorkflow()
    state = MagicMock()
    state.product = product
    state.tenant_id = "tenant-1"

    result = await workflow._import_node(state)

    assert result["product"].source_images == []


@pytest.mark.asyncio
async def test_import_node_no_product() -> None:
    """测试无商品时返回错误。"""
    from src.graph.listing_workflow import ListingWorkflow

    workflow = ListingWorkflow()
    state = MagicMock()
    state.product = None

    result = await workflow._import_node(state)

    assert result["error"] == "No product provided"
