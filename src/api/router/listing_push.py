"""
刊登推送 API 路由。

Description:
    提供刊登推送至各平台的 REST 接口。
    Phase 6 接入数据库，推送结果持久化至 task_results 表。
    平台适配器自动注册，按需从数据库加载凭证。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy import select

from src.agents.adapter_config import AdapterConfigManager
from src.agents.listing_amazon_adapter import AmazonAdapter
from src.agents.listing_ebay_adapter import EbayAdapter
from src.agents.listing_platform_adapter import AdapterRegistry
from src.agents.listing_shopify_adapter import ShopifyAdapter
from src.api.schema.common import ApiResponse
from src.api.schema.listing import (
    PushListingRequest,
    PushResponse,
    PushResultResponse,
)
from src.auth.api_key import require_auth
from src.auth.context import AuthContext
from src.db.listing_models import ListingProductPO, ListingTaskPO, TaskResultPO
from src.db.postgres import get_db, get_db_session
from src.db.repository import BaseRepository
from src.models.listing import Platform

logger = logging.getLogger(__name__)

router = APIRouter()

# 自动注册所有平台适配器
registry = AdapterRegistry()
registry.register(Platform.AMAZON, AmazonAdapter)
registry.register(Platform.EBAY, EbayAdapter)
registry.register(Platform.SHOPIFY, ShopifyAdapter)

_config_manager = AdapterConfigManager()


async def _load_domain_objects(task_id: int, *, tenant_id: str):
    """从数据库加载任务、商品、文案包（tenant 过滤）。

    Args:
        task_id: 任务 ID。
        tenant_id: 租户 ID。

    Returns:
        (task_po, product, task_obj) 或 None（未找到）。
    """
    from src.models.listing import ImageRef, ListingProduct, ListingTask

    async with get_db_session() as session:
        task_repo = BaseRepository(ListingTaskPO, session)
        task_po = await task_repo.get(task_id)
        if not task_po or getattr(task_po, "tenant_id", None) != tenant_id:
            return None

        product_repo = BaseRepository(ListingProductPO, session)
        product_po = await product_repo.get_by_field("sku", task_po.product_sku)
        if not product_po or getattr(product_po, "tenant_id", None) != tenant_id:
            return None

        product = ListingProduct(
            id=product_po.id,
            sku=product_po.sku,
            title=product_po.title,
            description=product_po.description,
            category=product_po.category,
            brand=product_po.brand,
            source_images=[ImageRef(**img) for img in (product_po.source_images or [])],
            attributes=product_po.attributes or {},
        )

        task_obj = ListingTask(
            id=task_po.id,
            product_id=product_po.id,
            target_platforms=[Platform(p) for p in task_po.target_platforms],
        )

    return task_po, product, task_obj


@router.post(
    "/tasks/{task_id}/push",
    response_model=ApiResponse[PushResponse],
    status_code=status.HTTP_200_OK,
    summary="推送刊登",
)
async def push_listing(
    task_id: int,
    auth: AuthContext = Depends(require_auth),
    request: PushListingRequest | None = None,
) -> ApiResponse[PushResponse]:
    """将刊登推送至指定平台。

    Args:
        task_id: 任务ID。
        auth: 认证上下文。
        request: 推送请求（可选，不指定则推送全部平台）。

    Returns:
        各平台推送结果。
    """
    from src.models.listing import AssetPackage, CopywritingPackage

    loaded = await _load_domain_objects(task_id, tenant_id=auth.tenant_id)
    if not loaded:
        return ApiResponse(code=404, message=f"任务 {task_id} 或关联商品不存在", data=None)

    task_po, product, task_obj = loaded
    target_platforms = (
        request.platforms if request and request.platforms else task_obj.target_platforms
    )

    results: list[PushResultResponse] = []

    async with get_db_session() as session:
        from src.db.asset_repository import AssetRepository
        from src.db.listing_models import CopywritingPackagePO
        
        asset_repo = AssetRepository(session)
        
        for platform in target_platforms:
            try:
                # 从数据库加载适配器凭证（租户感知）
                config = await _config_manager.get_config(
                    platform, tenant_id=auth.tenant_id
                )
                adapter = registry.get(platform, config=config)

                # 从数据库加载已生成的素材
                db_assets = await asset_repo.list_by_task(auth.tenant_id, str(task_id))
                
                # 构建 AssetPackage
                main_image = None
                variant_images = []
                video_url = None
                for asset in db_assets:
                    if asset.asset_type == "image":
                        if main_image is None:
                            main_image = asset.url
                        else:
                            variant_images.append(asset.url)
                    elif asset.asset_type == "video":
                        video_url = asset.url
                
                asset_package = AssetPackage(
                    listing_task_id=task_id,
                    platform=platform,
                    main_image=main_image,
                    variant_images=variant_images,
                    video_url=video_url,
                )
                
                # 尝试加载已生成的文案
                copywriting_result = await session.execute(
                    select(CopywritingPackagePO).where(
                        CopywritingPackagePO.task_id == task_id,
                        CopywritingPackagePO.platform == platform.value,
                    )
                )
                copywriting_po = copywriting_result.scalar_one_or_none()
                
                if copywriting_po:
                    copywriting = CopywritingPackage(
                        listing_task_id=task_id,
                        platform=platform,
                        language=copywriting_po.language,
                        title=copywriting_po.title,
                        bullet_points=copywriting_po.bullet_points,
                        description=copywriting_po.description,
                    )
                else:
                    copywriting = CopywritingPackage(
                        listing_task_id=task_id,
                        platform=platform,
                        language="en",
                        title=product.title,
                        bullet_points=[],
                        description=product.description or "",
                    )

                push_result = adapter.push_listing(product, asset_package, copywriting, task_obj)

                results.append(
                    PushResultResponse(
                        platform=platform.value,
                        success=push_result.success,
                        listing_id=push_result.listing_id,
                        url=push_result.url,
                        error=push_result.error,
                    )
                )

                # 持久化推送结果
                result_po = TaskResultPO(
                    tenant_id=auth.tenant_id,
                    task_id=task_id,
                    platform=platform.value,
                    success=push_result.success,
                    result_data={
                        "listing_id": push_result.listing_id,
                        "url": push_result.url,
                        "error": push_result.error,
                    },
                )
                session.add(result_po)

            except Exception as e:
                logger.error(f"Failed to push to {platform.value}: {e}")
                results.append(
                    PushResultResponse(
                        platform=platform.value,
                        success=False,
                        error=str(e),
                    )
                )
                # 也记录失败结果
                result_po = TaskResultPO(
                    tenant_id=auth.tenant_id,
                    task_id=task_id,
                    platform=platform.value,
                    success=False,
                    result_data={"error": str(e)},
                )
                session.add(result_po)

        # 更新任务状态
        all_success = all(r.success for r in results)
        task_po.status = "published" if all_success else "partial"

    return ApiResponse(
        code=200,
        message="推送完成",
        data=PushResponse(
            task_id=task_id,
            results=results,
            status=task_po.status,
        ),
    )


@router.get(
    "/tasks/{task_id}/push-results",
    response_model=ApiResponse[list[PushResultResponse]],
    summary="查询推送结果",
)
async def get_push_results(
    task_id: int,
    auth: AuthContext = Depends(require_auth),
) -> ApiResponse[list[PushResultResponse]]:
    """获取指定任务的推送结果。

    Args:
        task_id: 任务ID。
        auth: 认证上下文。

    Returns:
        各平台推送结果（仅当前租户）。
    """
    async with get_db_session() as session:
        repo = BaseRepository(TaskResultPO, session)
        results_po = await repo.list(task_id=task_id, tenant_id=auth.tenant_id)
        if not results_po:
            return ApiResponse(code=404, message=f"任务 {task_id} 无推送结果", data=None)

        results = [
            PushResultResponse(
                platform=r.platform,
                success=r.success,
                listing_id=r.result_data.get("listing_id"),
                url=r.result_data.get("url"),
                error=r.result_data.get("error"),
            )
            for r in results_po
        ]

        return ApiResponse(
            code=200,
            message="成功",
            data=results,
        )
