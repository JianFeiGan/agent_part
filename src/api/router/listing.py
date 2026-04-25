"""
刊登工具 API 路由。

Description:
    提供商品导入、刊登任务创建等 REST 接口。
    Phase 1 实现：导入商品、创建任务（素材+文案生成）。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging

from fastapi import APIRouter, status

from src.api.schema.listing import (
    CreateListingTaskRequest,
    ListingTaskResponse,
    ProductImportRequest,
    ProductResponse,
)
from src.api.schema.common import ApiResponse
from src.models.listing import ListingProduct

logger = logging.getLogger(__name__)

router = APIRouter()

# 内存存储（Phase 1），后续替换为数据库
_products: dict[str, ListingProduct] = {}
_tasks: list[dict] = []


@router.post(
    "/import-product",
    response_model=ApiResponse[ProductResponse],
    status_code=status.HTTP_201_CREATED,
    summary="导入商品",
)
async def import_product(request: ProductImportRequest) -> ApiResponse[ProductResponse]:
    """导入商品到刊登系统。

    Args:
        request: 商品导入请求。

    Returns:
        导入的商品信息。
    """
    from src.agents.listing_importer import ImportProductAgent

    agent = ImportProductAgent()
    product_data = request.model_dump()
    result = agent.execute_manual(product_data)

    if not result["success"]:
        return ApiResponse(code=400, message=result["error"], data=None)

    product = result["product"]
    _products[product.sku] = product

    return ApiResponse(
        code=200,
        message="商品导入成功",
        data=ProductResponse(
            sku=product.sku,
            title=product.title,
            description=product.description,
            category=product.category,
            brand=product.brand,
            source_images=[img.model_dump() for img in product.source_images],
        ),
    )


@router.get(
    "/products",
    response_model=ApiResponse[list[ProductResponse]],
    summary="商品列表",
)
async def list_products() -> ApiResponse[list[ProductResponse]]:
    """获取已导入的商品列表。"""
    return ApiResponse(
        code=200,
        message="成功",
        data=[
            ProductResponse(
                sku=p.sku,
                title=p.title,
                description=p.description,
                category=p.category,
                brand=p.brand,
                source_images=[img.model_dump() for img in p.source_images],
            )
            for p in _products.values()
        ],
    )


@router.post(
    "/tasks",
    response_model=ApiResponse[ListingTaskResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建刊登任务",
)
async def create_task(request: CreateListingTaskRequest) -> ApiResponse[ListingTaskResponse]:
    """创建刊登任务，触发生成素材和文案。

    Args:
        request: 刊登任务请求。

    Returns:
        创建的任务信息。
    """
    if request.product_sku not in _products:
        return ApiResponse(code=404, message=f"商品 {request.product_sku} 不存在", data=None)

    task_id = len(_tasks) + 1

    task_data = {
        "task_id": task_id,
        "product_sku": request.product_sku,
        "target_platforms": [p.value for p in request.target_platforms],
        "status": "pending",
    }
    _tasks.append(task_data)

    return ApiResponse(
        code=200,
        message="任务已创建",
        data=ListingTaskResponse(
            task_id=task_id,
            product_sku=request.product_sku,
            target_platforms=[p.value for p in request.target_platforms],
            status="pending",
        ),
    )


@router.get(
    "/tasks",
    response_model=ApiResponse[list[ListingTaskResponse]],
    summary="任务列表",
)
async def list_tasks() -> ApiResponse[list[ListingTaskResponse]]:
    """获取刊登任务列表。"""
    return ApiResponse(
        code=200,
        message="成功",
        data=[
            ListingTaskResponse(
                task_id=t["task_id"],
                product_sku=t["product_sku"],
                target_platforms=t["target_platforms"],
                status=t["status"],
            )
            for t in _tasks
        ],
    )
