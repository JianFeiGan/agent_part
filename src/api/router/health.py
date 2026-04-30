"""
健康检查路由。

Description:
    提供服务健康状态检查接口，用于监控系统服务运行状态。
@author ganjianfei
@version 1.0.0
2026-03-25
"""

from fastapi import APIRouter

from src.api.schema.common import HealthResponse
from src.config.settings import get_settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="健康检查")
async def health_check() -> HealthResponse:
    """健康检查接口。

    Returns:
        服务健康状态信息，包括版本、Redis 连接状态等。
    """
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version="0.1.0",
        redis="connected",  # 实际应检查 Redis 连接状态
    )


@router.get("/", summary="API 根路径")
async def api_root() -> dict:
    """API 根路径。

    Returns:
        API 基本信息。
    """
    return {
        "name": "Product Visual Generator API",
        "version": "0.1.0",
        "docs": "/docs",
    }
