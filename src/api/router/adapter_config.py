"""
适配器配置 API 路由。

Description:
    提供适配器配置的 CRUD REST 接口。
    写操作自动刷新 AdapterConfigManager 缓存。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging

from fastapi import APIRouter, status
from sqlalchemy import select

from src.agents.adapter_config import AdapterConfigManager
from src.api.schema.adapter_config import (
    AdapterConfigCreate,
    AdapterConfigResponse,
    AdapterConfigUpdate,
)
from src.api.schema.common import ApiResponse
from src.db.listing_models import AdapterConfigPO
from src.db.postgres import get_db
from src.models.listing import Platform

logger = logging.getLogger(__name__)

router = APIRouter()

_config_manager = AdapterConfigManager()


def _po_to_response(po: AdapterConfigPO) -> AdapterConfigResponse:
    """将 ORM 对象转换为脱敏响应。"""
    return AdapterConfigResponse(
        id=po.id,
        platform=po.platform,
        shop_id=po.shop_id,
        credentials_masked={k: "***" for k in po.credentials},
        is_active=po.is_active,
        created_at=po.created_at.isoformat() if po.created_at else None,
        updated_at=po.updated_at.isoformat() if po.updated_at else None,
    )


@router.post(
    "/adapter-configs",
    response_model=ApiResponse[AdapterConfigResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建适配器配置",
)
async def create_adapter_config(request: AdapterConfigCreate) -> ApiResponse[AdapterConfigResponse]:
    """创建新的适配器配置。

    Args:
        request: 配置创建请求。

    Returns:
        新创建的配置（脱敏）。
    """
    async with get_db() as session:
        po = AdapterConfigPO(
            platform=request.platform.value,
            shop_id=request.shop_id,
            credentials=request.credentials,
            is_active=request.is_active,
        )
        session.add(po)
        await session.flush()
        await session.refresh(po)
        await _config_manager.invalidate_cache(request.platform, request.shop_id)
        return ApiResponse(
            code=200,
            message="创建成功",
            data=_po_to_response(po),
        )


@router.get(
    "/adapter-configs",
    response_model=ApiResponse[list[AdapterConfigResponse]],
    summary="适配器配置列表",
)
async def list_adapter_configs(
    platform: Platform | None = None,
) -> ApiResponse[list[AdapterConfigResponse]]:
    """获取适配器配置列表。

    Args:
        platform: 可选的平台过滤。

    Returns:
        配置列表（脱敏）。
    """
    async with get_db() as session:
        stmt = select(AdapterConfigPO)
        if platform:
            stmt = stmt.where(AdapterConfigPO.platform == platform.value)
        stmt = stmt.order_by(AdapterConfigPO.created_at.desc())
        result = await session.execute(stmt)
        configs = result.scalars().all()
        return ApiResponse(
            code=200,
            message="成功",
            data=[_po_to_response(c) for c in configs],
        )


@router.get(
    "/adapter-configs/{config_id}",
    response_model=ApiResponse[AdapterConfigResponse],
    summary="适配器配置详情",
)
async def get_adapter_config(config_id: int) -> ApiResponse[AdapterConfigResponse]:
    """获取单个适配器配置详情（脱敏）。

    Args:
        config_id: 配置 ID。

    Returns:
        配置详情（脱敏）。
    """
    async with get_db() as session:
        po = await session.get(AdapterConfigPO, config_id)
        if not po:
            return ApiResponse(code=404, message="配置不存在", data=None)
        return ApiResponse(
            code=200,
            message="成功",
            data=_po_to_response(po),
        )


@router.put(
    "/adapter-configs/{config_id}",
    response_model=ApiResponse[AdapterConfigResponse],
    summary="更新适配器配置",
)
async def update_adapter_config(
    config_id: int,
    request: AdapterConfigUpdate,
) -> ApiResponse[AdapterConfigResponse]:
    """更新适配器配置。

    Args:
        config_id: 配置 ID。
        request: 更新请求。

    Returns:
        更新后的配置（脱敏）。
    """
    async with get_db() as session:
        po = await session.get(AdapterConfigPO, config_id)
        if not po:
            return ApiResponse(code=404, message="配置不存在", data=None)

        if request.credentials is not None:
            po.credentials = request.credentials
        if request.is_active is not None:
            po.is_active = request.is_active

        await session.flush()
        await session.refresh(po)
        await _config_manager.invalidate_cache(Platform(po.platform))
        return ApiResponse(
            code=200,
            message="更新成功",
            data=_po_to_response(po),
        )


@router.delete(
    "/adapter-configs/{config_id}",
    response_model=ApiResponse[None],
    summary="删除适配器配置",
)
async def delete_adapter_config(config_id: int) -> ApiResponse[None]:
    """删除适配器配置。

    Args:
        config_id: 配置 ID。

    Returns:
        操作结果。
    """
    async with get_db() as session:
        po = await session.get(AdapterConfigPO, config_id)
        if not po:
            return ApiResponse(code=404, message="配置不存在", data=None)

        platform = Platform(po.platform)
        await session.delete(po)
        await session.flush()
        await _config_manager.invalidate_cache(platform)
        return ApiResponse(code=200, message="删除成功", data=None)
