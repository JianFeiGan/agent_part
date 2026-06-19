"""
资产查询与删除路由。

Description:
    提供资产列表查询、单个资产获取和资产删除接口。
    所有操作均进行租户隔离和 scope 鉴权。
@author ganjianfei
@version 1.0.0
2026-06-19
"""

from fastapi import APIRouter, HTTPException, Query, status

from src.api.deps import AuthDep
from src.api.schema.assets import AssetResponse
from src.api.schema.common import ApiResponse
from src.auth.context import AuthContext
from src.db.asset_repository import AssetRepository
from src.db.listing_models import GeneratedAssetPO
from src.db.postgres import get_db
from src.storage.factory import get_storage_backend

router = APIRouter()


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


def _asset_to_response(asset: GeneratedAssetPO) -> AssetResponse:
    """将 ORM 模型转换为 AssetResponse。

    Args:
        asset: 数据库资产实例。

    Returns:
        AssetResponse 对象。
    """
    return AssetResponse(
        asset_id=asset.id,
        product_id=asset.product_id,
        task_id=asset.task_id,
        asset_type=asset.asset_type,
        provider=asset.provider,
        url=asset.url,
        mime_type=asset.mime_type,
        file_size=asset.file_size,
        width=asset.width,
        height=asset.height,
        duration=asset.duration,
        is_mock=asset.is_mock,
        status=asset.status,
        created_at=asset.created_at.isoformat(),
    )


@router.get(
    "",
    response_model=ApiResponse[list[AssetResponse]],
    summary="列出当前租户的资产",
)
async def list_assets(
    auth: AuthDep,
    product_id: str | None = Query(default=None, description="按商品 ID 过滤"),
    task_id: str | None = Query(default=None, description="按任务 ID 过滤"),
    asset_type: str | None = Query(default=None, description="资产类型: image/video"),
    limit: int = Query(default=20, ge=1, le=100, description="最大返回数量"),
) -> ApiResponse[list[AssetResponse]]:
    """列出当前租户的资产。

    支持按 product_id、task_id、asset_type 过滤。
    至少需要一个 assets:read 或 assets:write scope。

    Args:
        auth: 认证上下文依赖。
        product_id: 按商品 ID 过滤（可选）。
        task_id: 按任务 ID 过滤（可选）。
        asset_type: 按资产类型过滤（可选）。
        limit: 最大返回数量。

    Returns:
        资产列表。
    """
    _require_scope(auth, "assets:read", "assets:write")

    async with get_db() as session:
        repo = AssetRepository(session)

        if product_id is not None:
            results = await repo.list_by_product(auth.tenant_id, product_id, limit=limit)
        elif task_id is not None:
            results = await repo.list_by_task(auth.tenant_id, task_id)
        elif asset_type is not None:
            results = await repo.list_for_tenant(
                auth.tenant_id, asset_type=asset_type
            )
        else:
            results = await repo.list_for_tenant(auth.tenant_id)

        # 对无 product_id/task_id 过滤的情况做 limit
        if product_id is None:
            results = results[:limit]

        items = [_asset_to_response(a) for a in results]

    return ApiResponse(
        code=200,
        message="获取成功",
        data=items,
    )


@router.get(
    "/{asset_id}",
    response_model=ApiResponse[AssetResponse],
    summary="获取单个资产",
)
async def get_asset(
    asset_id: int,
    auth: AuthDep,
) -> ApiResponse[AssetResponse]:
    """获取单个资产详情。

    跨租户访问返回 404。

    Args:
        asset_id: 资产 ID。
        auth: 认证上下文依赖。

    Returns:
        资产详情。

    Raises:
        HTTPException: 404 当资产不存在或不属于当前租户。
    """
    _require_scope(auth, "assets:read", "assets:write")

    async with get_db() as session:
        repo = AssetRepository(session)
        asset = await repo.get_for_tenant(asset_id, auth.tenant_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="资产不存在")

    return ApiResponse(
        code=200,
        message="获取成功",
        data=_asset_to_response(asset),
    )


@router.delete(
    "/{asset_id}",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="删除资产",
)
async def delete_asset(
    asset_id: int,
    auth: AuthDep,
) -> ApiResponse[None]:
    """删除资产。

    同时清理 StorageBackend 文件和数据库记录，操作在同一事务中。
    跨租户访问返回 404。

    Args:
        asset_id: 资产 ID。
        auth: 认证上下文依赖。

    Returns:
        删除结果。

    Raises:
        HTTPException: 404 当资产不存在或不属于当前租户。
    """
    _require_scope(auth, "assets:write")

    async with get_db() as session:
        repo = AssetRepository(session)
        asset = await repo.get_for_tenant(asset_id, auth.tenant_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="资产不存在")

        storage_key = asset.storage_key

        # 先删除 DB 记录，再清理文件存储
        # 同一 session 事务内操作
        await session.delete(asset)
        await session.flush()

        # 清理存储文件（best-effort，失败不影响 DB 操作）
        backend = get_storage_backend()
        await backend.delete(storage_key)

    return ApiResponse(code=200, message="删除成功")
