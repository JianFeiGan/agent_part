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
from src.api.service.redis_client import RedisClient

router = APIRouter()

_redis_client: RedisClient | None = None


async def _get_redis_client() -> RedisClient | None:
    """获取或创建 Redis 客户端。"""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
        try:
            await _redis_client.connect()
        except Exception:
            return None
    return _redis_client


@router.get("/health", response_model=HealthResponse, summary="健康检查")
async def health_check() -> HealthResponse:
    """健康检查接口。

    Returns:
        服务健康状态信息，包括版本、Redis 连接状态等。
    """
    settings = get_settings()
    
    redis_status = "connected"
    try:
        redis_client = await _get_redis_client()
        if redis_client and redis_client._client:
            await redis_client._client.ping()
        else:
            redis_status = "not_configured"
    except Exception:
        redis_status = "disconnected"
    
    overall_status = "ok" if redis_status == "connected" else "degraded"
    
    return HealthResponse(
        status=overall_status,
        version="0.1.0",
        redis=redis_status,
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
