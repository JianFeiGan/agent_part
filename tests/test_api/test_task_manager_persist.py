"""task_manager 集成产物落库测试。

验证 _execute_workflow 完成后调用 AssetPersister.persist_images。
使用简化的 mock 策略，patch _execute_workflow 的内部调用链，
避免 mock 整个工作流。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.assets import AssetStatus, GeneratedImage, ImageFormat


@pytest.mark.asyncio
async def test_persist_images_called_after_workflow_success() -> None:
    """测试工作流成功完成后调用 AssetPersister.persist_images。"""
    from src.api.service.task_manager import TaskManager

    manager = TaskManager()

    # 构造真实的 GeneratedImage（避免 MagicMock 的 is_ready 问题）
    fake_image = GeneratedImage(
        image_id="img_001",
        image_type="main",
        prompt="test prompt",
        url="https://example.com/img.png",
        format=ImageFormat.PNG,
        width=1024,
        height=1024,
        status=AssetStatus.COMPLETED,
        model="wanx-v1",
    )

    # 构造真实的 Product（满足 create_initial_state 验证）
    from src.models.product import Product, ProductCategory

    product = Product(
        product_id="prod_001",
        name="测试商品",
        category=ProductCategory.DIGITAL,
        description="这是一个用于测试的商品描述信息",
    )

    from src.graph.state import GenerationRequest

    request = GenerationRequest(
        task_id="task_abc",
        task_type="image_and_video",
    )

    # 模拟最终状态（包含生成图片）
    from src.graph.state import AgentState

    final_state = AgentState(
        product_info=product,
        generation_request=request,
        generated_images=[fake_image],
    )

    mock_persister_instance = MagicMock()
    mock_persister_instance.persist_images = AsyncMock(return_value=1)

    # mock redis、workflow、db session
    mock_redis = MagicMock()
    mock_redis.update_task_progress = AsyncMock()
    mock_redis.save_task_state = AsyncMock()

    mock_app = MagicMock()

    async def _empty_astream(*args, **kwargs):
        """空异步生成器。"""
        if False:
            yield

    mock_app.astream = MagicMock(side_effect=_empty_astream)
    mock_app.aget_state = AsyncMock(
        return_value=MagicMock(values=final_state.model_dump())
    )

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("src.api.service.task_manager.get_redis", new_callable=AsyncMock, return_value=mock_redis),
        patch("src.api.service.task_manager.ProductVisualWorkflow") as mock_wf_cls,
        patch("src.api.service.task_manager.AssetPersister", return_value=mock_persister_instance),
        patch("src.api.service.task_manager.get_db_session", return_value=mock_session),
    ):
        mock_wf_cls.return_value.app = mock_app

        await manager._execute_workflow(
            task_id="task_abc",
            product=product,
            request=request,
            tenant_id="tenant-1",
        )

    # 验证 persist_images 被调用
    mock_persister_instance.persist_images.assert_called_once()
    call_kwargs = mock_persister_instance.persist_images.call_args.kwargs
    assert call_kwargs["tenant_id"] == "tenant-1"
    assert call_kwargs["product_id"] == "prod_001"
    assert call_kwargs["task_id"] == "task_abc"


@pytest.mark.asyncio
async def test_persist_images_not_called_on_error() -> None:
    """测试工作流失败时不调用产物落库。"""
    from src.api.service.task_manager import TaskManager
    from src.models.product import Product, ProductCategory
    from src.graph.state import GenerationRequest, AgentState

    manager = TaskManager()

    product = Product(
        product_id="prod_002",
        name="出错商品",
        category=ProductCategory.DIGITAL,
        description="这是一个用于测试的商品描述信息",
    )
    request = GenerationRequest(task_id="task_err", task_type="image_and_video")

    # 带错误的最终状态
    final_state = AgentState(
        product_info=product,
        generation_request=request,
        error="模拟错误",
    )

    mock_persister_instance = MagicMock()
    mock_persister_instance.persist_images = AsyncMock(return_value=0)

    mock_redis = MagicMock()
    mock_redis.update_task_progress = AsyncMock()
    mock_redis.save_task_state = AsyncMock()
    mock_redis.get_task_state = AsyncMock(return_value=None)

    mock_app = MagicMock()

    async def _empty_astream(*args, **kwargs):
        if False:
            yield

    mock_app.astream = MagicMock(side_effect=_empty_astream)
    mock_app.aget_state = AsyncMock(
        return_value=MagicMock(values=final_state.model_dump())
    )

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("src.api.service.task_manager.get_redis", new_callable=AsyncMock, return_value=mock_redis),
        patch("src.api.service.task_manager.ProductVisualWorkflow") as mock_wf_cls,
        patch("src.api.service.task_manager.AssetPersister", return_value=mock_persister_instance),
        patch("src.api.service.task_manager.get_db_session", return_value=mock_session),
    ):
        mock_wf_cls.return_value.app = mock_app

        await manager._execute_workflow(
            task_id="task_err",
            product=product,
            request=request,
            tenant_id="tenant-1",
        )

    mock_persister_instance.persist_images.assert_not_called()
