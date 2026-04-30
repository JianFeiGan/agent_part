"""
商品管理路由。

Description:
    提供商品的 CRUD 接口，包括创建、查询、更新、删除和图片上传。
@author ganjianfei
@version 1.0.0
2026-03-25
"""

from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from src.api.deps import RedisDep
from src.api.schema.common import ApiResponse, PageResponse
from src.api.schema.product import (
    ProductCreateRequest,
    ProductListQuery,
    ProductResponse,
    ProductUpdateRequest,
)
from src.models.product import Product

router = APIRouter()


@router.post(
    "",
    response_model=ApiResponse[ProductResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建商品",
)
async def create_product(
    request: ProductCreateRequest,
    redis: RedisDep,
) -> ApiResponse[ProductResponse]:
    """创建商品。

    Args:
        request: 商品创建请求。
        redis: Redis 客户端依赖。

    Returns:
        创建成功的商品信息。
    """
    # 生成商品 ID
    product_id = f"prod_{uuid4().hex[:12]}"

    # 创建商品模型
    product = Product(product_id=product_id, **request.model_dump())

    # 保存到 Redis
    await redis.save_product(product)

    # 返回响应
    return ApiResponse(
        code=200,
        message="商品创建成功",
        data=ProductResponse(**product.model_dump()),
    )


@router.get(
    "",
    response_model=ApiResponse[PageResponse[ProductResponse]],
    summary="获取商品列表",
)
async def list_products(
    redis: RedisDep,
    query: ProductListQuery = Depends(),
) -> ApiResponse[PageResponse[ProductResponse]]:
    """获取商品列表（分页）。

    Args:
        redis: Redis 客户端依赖。
        query: 查询参数。

    Returns:
        商品分页列表。
    """
    products, total = await redis.list_products(
        page=query.page,
        page_size=query.page_size,
        category=query.category.value if query.category else None,
    )

    # 转换为响应模型
    items = [ProductResponse(**p.model_dump()) for p in products]

    return ApiResponse(
        code=200,
        message="获取成功",
        data=PageResponse(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
            pages=(total + query.page_size - 1) // query.page_size,
        ),
    )


@router.get(
    "/{product_id}",
    response_model=ApiResponse[ProductResponse],
    summary="获取商品详情",
)
async def get_product(
    product_id: str,
    redis: RedisDep,
) -> ApiResponse[ProductResponse]:
    """获取商品详情。

    Args:
        product_id: 商品 ID。
        redis: Redis 客户端依赖。

    Returns:
        商品详细信息。

    Raises:
        HTTPException: 商品不存在时抛出 404 错误。
    """
    product = await redis.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    return ApiResponse(
        code=200,
        message="获取成功",
        data=ProductResponse(**product.model_dump()),
    )


@router.put(
    "/{product_id}",
    response_model=ApiResponse[ProductResponse],
    summary="更新商品",
)
async def update_product(
    product_id: str,
    request: ProductUpdateRequest,
    redis: RedisDep,
) -> ApiResponse[ProductResponse]:
    """更新商品。

    Args:
        product_id: 商品 ID。
        request: 商品更新请求。
        redis: Redis 客户端依赖。

    Returns:
        更新后的商品信息。

    Raises:
        HTTPException: 商品不存在时抛出 404 错误。
    """
    # 获取现有商品
    product = await redis.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    # 更新字段（只更新非 None 的字段）
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)

    # 保存更新
    await redis.update_product(product)

    return ApiResponse(
        code=200,
        message="更新成功",
        data=ProductResponse(**product.model_dump()),
    )


@router.delete(
    "/{product_id}",
    response_model=ApiResponse[None],
    summary="删除商品",
)
async def delete_product(
    product_id: str,
    redis: RedisDep,
) -> ApiResponse[None]:
    """删除商品。

    Args:
        product_id: 商品 ID。
        redis: Redis 客户端依赖。

    Returns:
        删除结果。

    Raises:
        HTTPException: 商品不存在时抛出 404 错误。
    """
    success = await redis.delete_product(product_id)
    if not success:
        raise HTTPException(status_code=404, detail="商品不存在")

    return ApiResponse(code=200, message="删除成功")


@router.post(
    "/{product_id}/images",
    response_model=ApiResponse[dict],
    summary="上传商品图片",
)
async def upload_product_image(
    product_id: str,
    redis: RedisDep,
    file: UploadFile = File(...),
) -> ApiResponse[dict]:
    """上传商品图片。

    Args:
        product_id: 商品 ID。
        redis: Redis 客户端依赖。
        file: 上传的图片文件。

    Returns:
        上传结果，包含文件 URL。

    Raises:
        HTTPException: 商品不存在时抛出 404 错误。
    """
    # 检查商品是否存在
    product = await redis.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    # TODO: 实现文件上传逻辑（保存到本地或 OSS）
    # 这里暂时返回模拟数据
    file_url = f"/uploads/{product_id}/{file.filename}"

    return ApiResponse(
        code=200,
        message="上传成功",
        data={"url": file_url, "filename": file.filename},
    )
