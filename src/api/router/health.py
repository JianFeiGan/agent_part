"""
健康检查路由。

Description:
    /health 仅进程存活（liveness）。
    /ready 探测 PostgreSQL 与 Redis（readiness），供 compose/负载均衡使用。
@author ganjianfei
@version 1.1.0
2026-09-12
"""

from collections.abc import Awaitable
from typing import Any, cast

from fastapi import APIRouter, Response
from sqlalchemy import text

from src.api.schema.common import HealthResponse
from src.api.service.redis_client import RedisClient
from src.db.postgres import get_db_session

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


async def _check_redis() -> str:
    """探测 Redis：connected / disconnected / not_configured。"""
    try:
        redis_client = await _get_redis_client()
        if redis_client and redis_client._client:
            ping = cast(Awaitable[Any], redis_client._client.ping())
            await ping
            return "connected"
        return "not_configured"
    except Exception:
        return "disconnected"


async def _check_postgres() -> str:
    """探测 PostgreSQL：connected / disconnected。"""
    try:
        async with get_db_session() as session:
            await session.execute(text("SELECT 1"))
        return "connected"
    except Exception:
        return "disconnected"


@router.get("/health", response_model=HealthResponse, summary="存活探针（liveness）")
async def health_check() -> HealthResponse:
    """liveness：进程可响应即 200，不强制依赖 DB。

    Returns:
        服务健康状态信息。
    """
    redis_status = await _check_redis()
    overall_status = "ok" if redis_status != "disconnected" else "degraded"
    return HealthResponse(
        status=overall_status,
        version="0.1.0",
        redis=redis_status,
    )


@router.get("/ready", summary="就绪探针（readiness：DB + Redis）")
async def ready_check(response: Response) -> dict[str, Any]:
    """readiness：PostgreSQL 与 Redis 均可用才返回 200。

    Returns:
        依赖探测明细；任一失败时 HTTP 503。
    """
    postgres = await _check_postgres()
    redis = await _check_redis()
    ready = postgres == "connected" and redis == "connected"
    if not ready:
        response.status_code = 503
    return {
        "status": "ready" if ready else "not_ready",
        "postgres": postgres,
        "redis": redis,
    }


@router.get("/", summary="API 根路径")
async def api_root() -> dict[str, Any]:
    """API 根路径。

    Returns:
        API 基本信息。
    """
    return {
        "name": "Product Visual Generator API",
        "version": "0.1.0",
        "docs": "/docs",
    }
