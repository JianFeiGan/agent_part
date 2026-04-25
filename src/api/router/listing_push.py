"""
刊登推送 API 路由。

Description:
    提供刊登推送至各平台的 REST 接口。
    Phase 3-5 使用模拟适配器（返回成功），后续接入真实平台 API。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging

from fastapi import APIRouter, status

from src.api.schema.common import ApiResponse
from src.api.schema.listing import (
    PushListingRequest,
    PushResponse,
    PushResultResponse,
)
from src.models.listing import Platform

logger = logging.getLogger(__name__)

router = APIRouter()

# 内存存储推送结果
_push_results: dict[int, list[dict]] = {}

# 自动注册所有平台适配器
from src.agents.listing_amazon_adapter import AmazonAdapter
from src.agents.listing_ebay_adapter import EbayAdapter
from src.agents.listing_shopify_adapter import ShopifyAdapter
from src.agents.listing_platform_adapter import AdapterRegistry

registry = AdapterRegistry()
registry.register(Platform.AMAZON, AmazonAdapter)
registry.register(Platform.EBAY, EbayAdapter)
registry.register(Platform.SHOPIFY, ShopifyAdapter)


@router.post(
    "/tasks/{task_id}/push",
    response_model=ApiResponse[PushResponse],
    status_code=status.HTTP_200_OK,
    summary="推送刊登",
)
async def push_listing(
    task_id: int, request: PushListingRequest | None = None
) -> ApiResponse[PushResponse]:
    """将刊登推送至指定平台。

    Args:
        task_id: 任务ID。
        request: 推送请求（可选，不指定则推送全部平台）。

    Returns:
        各平台推送结果。
    """
    from src.api.router.listing import _products, _tasks
    from src.models.listing import AssetPackage, CopywritingPackage, ListingTask

    task = next((t for t in _tasks if t["task_id"] == task_id), None)
    if not task:
        return ApiResponse(code=404, message=f"任务 {task_id} 不存在", data=None)

    task_obj = ListingTask(
        id=task_id,
        product_id=0,
        target_platforms=[Platform(p) for p in task["target_platforms"]],
    )

    target_platforms = (
        request.platforms if request and request.platforms else task_obj.target_platforms
    )

    product = _products.get(task["product_sku"])
    if not product:
        return ApiResponse(code=404, message=f"商品 {task['product_sku']} 不存在", data=None)

    results: list[PushResultResponse] = []

    for platform in target_platforms:
        try:
            adapter = registry.get(platform)

            asset_package = AssetPackage(
                listing_task_id=task_id,
                platform=platform,
                main_image=None,
                variant_images=[],
            )
            copywriting = CopywritingPackage(
                listing_task_id=task_id,
                platform=platform,
                language="en",
                title=product.title,
                bullet_points=[],
                description=product.description or "",
            )

            push_result = adapter.push_listing(
                product, asset_package, copywriting, task_obj
            )

            results.append(
                PushResultResponse(
                    platform=platform.value,
                    success=push_result.success,
                    listing_id=push_result.listing_id,
                    url=push_result.url,
                    error=push_result.error,
                )
            )

        except Exception as e:
            logger.error(f"Failed to push to {platform.value}: {e}")
            results.append(
                PushResultResponse(
                    platform=platform.value,
                    success=False,
                    error=str(e),
                )
            )

    _push_results[task_id] = [r.model_dump() for r in results]

    all_success = all(r.success for r in results)
    task["status"] = "published" if all_success else "partial"

    return ApiResponse(
        code=200,
        message="推送完成",
        data=PushResponse(
            task_id=task_id,
            results=results,
            status=task["status"],
        ),
    )


@router.get(
    "/tasks/{task_id}/push-results",
    response_model=ApiResponse[list[PushResultResponse]],
    summary="查询推送结果",
)
async def get_push_results(task_id: int) -> ApiResponse[list[PushResultResponse]]:
    """获取指定任务的推送结果。

    Args:
        task_id: 任务ID。

    Returns:
        各平台推送结果。
    """
    results = _push_results.get(task_id)
    if not results:
        return ApiResponse(
            code=404, message=f"任务 {task_id} 无推送结果", data=None
        )

    return ApiResponse(
        code=200,
        message="成功",
        data=[PushResultResponse(**r) for r in results],
    )
