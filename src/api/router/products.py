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

from src.api.deps import AuthDep, RedisDep, SettingsDep
from src.api.schema.common import ApiResponse, PageResponse
from src.api.schema.product import (
    ProductCreateRequest,
    ProductListQuery,
    ProductResponse,
    ProductUpdateRequest,
)
from src.auth.context import AuthContext
from src.db.asset_repository import AssetRepository
from src.db.postgres import get_db, get_db_session
from src.models.product import Product
from src.storage.factory import get_storage_backend
from src.storage.local import LocalStorageBackend

router = APIRouter()

# 允许的图片 MIME 类型
_ALLOWED_IMAGE_MIME_TYPES: frozenset[str] = frozenset({
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
})

# MIME 类型到文件扩展名的映射
_MIME_TO_EXTENSION: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}


def _require_scope(auth: AuthContext, *scopes: str) -> None:
    """检查 auth 是否拥有指定 scope 之一，否则 raise 403。

    遍历 scopes，只要任一 scope 满足 auth.has_scope(scope) 即通过。
    若全部不满足，抛出 HTTPException(status_code=403, detail="Forbidden")。

    Args:
        auth: 认证上下文。
        *scopes: 一个或多个 scope 名称。

    Raises:
        HTTPException: 403 当 scope 不足时。
    """
    for scope in scopes:
        if auth.has_scope(scope):
            return
    raise HTTPException(status_code=403, detail="Forbidden")


@router.post(
    "",
    response_model=ApiResponse[ProductResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建商品",
)
async def create_product(
    request: ProductCreateRequest,
    redis: RedisDep,
    auth: AuthDep,
) -> ApiResponse[ProductResponse]:
    """创建商品。

    Args:
        request: 商品创建请求。
        redis: Redis 客户端依赖。
        auth: 认证上下文依赖。

    Returns:
        创建成功的商品信息。
    """
    _require_scope(auth, "products:write")

    # 生成商品 ID
    product_id = f"prod_{uuid4().hex[:12]}"

    # 创建商品模型
    product = Product(product_id=product_id, **request.model_dump())

    # 保存到 Redis
    await redis.save_product(product, tenant_id=auth.tenant_id)

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
    auth: AuthDep,
    query: ProductListQuery = Depends(),
) -> ApiResponse[PageResponse[ProductResponse]]:
    """获取商品列表（分页）。

    Args:
        redis: Redis 客户端依赖。
        auth: 认证上下文依赖。
        query: 查询参数。

    Returns:
        商品分页列表。
    """
    _require_scope(auth, "products:read", "products:write")

    products, total = await redis.list_products(
        tenant_id=auth.tenant_id,
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
    auth: AuthDep,
) -> ApiResponse[ProductResponse]:
    """获取商品详情。

    Args:
        product_id: 商品 ID。
        redis: Redis 客户端依赖。
        auth: 认证上下文依赖。

    Returns:
        商品详细信息。

    Raises:
        HTTPException: 商品不存在时抛出 404 错误。
    """
    _require_scope(auth, "products:read", "products:write")

    product = await redis.get_product(product_id, tenant_id=auth.tenant_id)
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
    auth: AuthDep,
) -> ApiResponse[ProductResponse]:
    """更新商品。

    Args:
        product_id: 商品 ID。
        request: 商品更新请求。
        redis: Redis 客户端依赖。
        auth: 认证上下文依赖。

    Returns:
        更新后的商品信息。

    Raises:
        HTTPException: 商品不存在时抛出 404 错误。
    """
    _require_scope(auth, "products:write")

    # 获取现有商品
    product = await redis.get_product(product_id, tenant_id=auth.tenant_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    # 更新字段（只更新非 None 的字段）
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)

    # 保存更新
    await redis.update_product(product, tenant_id=auth.tenant_id)

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
    auth: AuthDep,
) -> ApiResponse[None]:
    """删除商品。

    Args:
        product_id: 商品 ID。
        redis: Redis 客户端依赖。
        auth: 认证上下文依赖。

    Returns:
        删除结果。

    Raises:
        HTTPException: 商品不存在时抛出 404 错误。
    """
    _require_scope(auth, "products:write")

    success = await redis.delete_product(product_id, tenant_id=auth.tenant_id)
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
    auth: AuthDep,
    settings: SettingsDep,
    file: UploadFile = File(...),
) -> ApiResponse[dict]:
    """上传商品图片。

    接受 multipart 图片文件，校验 MIME 类型和文件大小，
    计算 SHA256 去重，落盘到本地存储并写入 GeneratedAssetPO。

    Args:
        product_id: 商品 ID。
        redis: Redis 客户端依赖。
        auth: 认证上下文依赖。
        settings: 应用配置依赖。
        file: 上传的图片文件。

    Returns:
        上传结果，包含 url、asset_id、size、content_type。

    Raises:
        HTTPException: 403 scope 不足、400 MIME 不支持、413 文件过大、
                       404 商品不存在。
    """
    _require_scope(auth, "products:write")

    # 检查商品是否存在
    product = await redis.get_product(product_id, tenant_id=auth.tenant_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    # --- 校验 MIME 类型 ---
    content_type = file.content_type or "application/octet-stream"
    if content_type not in _ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的图片格式: {content_type}，仅支持: "
            f"{', '.join(sorted(_ALLOWED_IMAGE_MIME_TYPES))}",
        )

    # --- 读取文件内容并校验大小 ---
    data = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"文件大小超过限制 ({settings.max_upload_size_mb}MB)",
        )

    # --- 计算 SHA256 ---
    file_sha256 = LocalStorageBackend.compute_sha256(data)

    # --- 获取存储后端 ---
    backend = get_storage_backend()

    # --- 去重检查 ---
    async with get_db_session() as session:
        asset_repo = AssetRepository(session)
        existing = await asset_repo.find_by_sha256(auth.tenant_id, file_sha256)
        if existing is not None:
            return ApiResponse(
                code=200,
                message="上传成功（复用已有资产）",
                data={
                    "url": existing.url,
                    "asset_id": existing.id,
                    "size": existing.file_size,
                    "content_type": existing.mime_type,
                },
            )

        # --- 生成 storage_key 并落盘 ---
        extension = _MIME_TO_EXTENSION.get(content_type, "bin")
        storage_key = LocalStorageBackend.generate_key(
            prefix=f"products/{auth.tenant_id}/{product_id}", extension=extension
        )

        try:
            url = await backend.save(data, key=storage_key, content_type=content_type)
        except Exception:
            raise HTTPException(status_code=500, detail="文件存储失败")

        # --- 写入 GeneratedAssetPO ---
        try:
            asset = await asset_repo.create_asset(
                tenant_id=auth.tenant_id,
                product_id=product_id,
                asset_type="image",
                provider="user_upload",
                url=url,
                storage_key=storage_key,
                storage_backend="local",
                mime_type=content_type,
                file_size=len(data),
                sha256=file_sha256,
                status="completed",
                is_mock=False,
            )
        except Exception:
            # DB 写入失败，尝试清理已落盘的文件
            await backend.delete(storage_key)
            raise HTTPException(status_code=500, detail="资产记录写入失败")

    return ApiResponse(
        code=200,
        message="上传成功",
        data={
            "url": url,
            "asset_id": asset.id,
            "size": len(data),
            "content_type": content_type,
        },
    )
