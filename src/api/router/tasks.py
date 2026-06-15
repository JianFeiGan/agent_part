"""
任务管理路由。

Description:
    提供任务的创建、查询、取消接口，以及 WebSocket 实时状态推送。
@author ganjianfei
@version 1.0.0
2026-03-25
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from src.api.deps import AuthDep, RedisDep
from src.api.schema.common import ApiResponse, PageResponse
from src.api.schema.task import (
    TaskCreateRequest,
    TaskDetailResponse,
    TaskListQuery,
    TaskStatusResponse,
)
from src.api.service.redis_client import RedisClient
from src.api.service.task_manager import TaskManager, get_task_manager
from src.auth import authenticate_websocket
from src.auth.context import AuthContext

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


def get_task_manager_dep() -> TaskManager:
    """获取任务管理器依赖。

    Returns:
        任务管理器实例。
    """
    return get_task_manager()


TaskManagerDep = Depends(get_task_manager_dep)


@router.post(
    "",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_201_CREATED,
    summary="创建生成任务",
)
async def create_task(
    request: TaskCreateRequest,
    redis: RedisDep,
    auth: AuthDep,
    task_manager: TaskManager = TaskManagerDep,
) -> ApiResponse[dict]:
    """创建生成任务（异步）。

    Args:
        request: 任务创建请求。
        redis: Redis 客户端依赖。
        auth: 认证上下文依赖。
        task_manager: 任务管理器依赖。

    Returns:
        任务 ID。

    Raises:
        HTTPException: 商品不存在时抛出 404 错误。
    """
    _require_scope(auth, "tasks:write")

    # 检查商品是否存在
    product = await redis.get_product(request.product_id, tenant_id=auth.tenant_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    # 创建任务
    task_id = await task_manager.create_task(
        product_id=request.product_id,
        request_data=request.model_dump(),
        redis=redis,
        tenant_id=auth.tenant_id,
    )

    return ApiResponse(
        code=200,
        message="任务创建成功",
        data={"task_id": task_id},
    )


@router.get(
    "",
    response_model=ApiResponse[PageResponse[dict]],
    summary="获取任务列表",
)
async def list_tasks(
    redis: RedisDep,
    auth: AuthDep,
    task_manager: TaskManager = TaskManagerDep,
    query: TaskListQuery = Depends(),
) -> ApiResponse[PageResponse[dict]]:
    """获取任务列表（分页）。

    Args:
        redis: Redis 客户端依赖。
        auth: 认证上下文依赖。
        task_manager: 任务管理器依赖。
        query: 查询参数。

    Returns:
        任务分页列表。
    """
    _require_scope(auth, "tasks:read", "tasks:write")

    tasks, total = await task_manager.list_tasks(
        redis=redis,
        tenant_id=auth.tenant_id,
        page=query.page,
        page_size=query.page_size,
        status=query.status.value if query.status else None,
    )

    return ApiResponse(
        code=200,
        message="获取成功",
        data=PageResponse(
            items=tasks,
            total=total,
            page=query.page,
            page_size=query.page_size,
            pages=(total + query.page_size - 1) // query.page_size,
        ),
    )


@router.get(
    "/{task_id}",
    response_model=ApiResponse[TaskDetailResponse],
    summary="获取任务详情",
)
async def get_task_detail(
    task_id: str,
    redis: RedisDep,
    auth: AuthDep,
    task_manager: TaskManager = TaskManagerDep,
) -> ApiResponse[TaskDetailResponse]:
    """获取任务详情。

    Args:
        task_id: 任务 ID。
        redis: Redis 客户端依赖。
        auth: 认证上下文依赖。
        task_manager: 任务管理器依赖。

    Returns:
        任务详细信息。

    Raises:
        HTTPException: 任务不存在时抛出 404 错误。
    """
    _require_scope(auth, "tasks:read", "tasks:write")

    try:
        detail = await task_manager.get_task_detail(task_id, redis, tenant_id=auth.tenant_id)
        return ApiResponse(
            code=200,
            message="获取成功",
            data=TaskDetailResponse(**detail),
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="任务不存在")


@router.get(
    "/{task_id}/status",
    response_model=ApiResponse[TaskStatusResponse],
    summary="获取任务状态",
)
async def get_task_status(
    task_id: str,
    redis: RedisDep,
    auth: AuthDep,
    task_manager: TaskManager = TaskManagerDep,
) -> ApiResponse[TaskStatusResponse]:
    """获取任务状态/进度。

    Args:
        task_id: 任务 ID。
        redis: Redis 客户端依赖。
        auth: 认证上下文依赖。
        task_manager: 任务管理器依赖。

    Returns:
        任务状态信息。

    Raises:
        HTTPException: 任务不存在时抛出 404 错误。
    """
    _require_scope(auth, "tasks:read", "tasks:write")

    try:
        status_data = await task_manager.get_task_status(task_id, redis, tenant_id=auth.tenant_id)
        return ApiResponse(
            code=200,
            message="获取成功",
            data=TaskStatusResponse(**status_data),
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="任务不存在")


@router.post(
    "/{task_id}/cancel",
    response_model=ApiResponse[dict],
    summary="取消任务",
)
async def cancel_task(
    task_id: str,
    redis: RedisDep,
    auth: AuthDep,
    task_manager: TaskManager = TaskManagerDep,
) -> ApiResponse[dict]:
    """取消任务。

    Args:
        task_id: 任务 ID。
        redis: Redis 客户端依赖。
        auth: 认证上下文依赖。
        task_manager: 任务管理器依赖。

    Returns:
        取消结果。

    Raises:
        HTTPException: 任务不存在时抛出 404 错误。
    """
    _require_scope(auth, "tasks:write")

    success = await task_manager.cancel_task(task_id, redis, tenant_id=auth.tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在")

    return ApiResponse(
        code=200,
        message="任务已取消",
        data={"task_id": task_id, "cancelled": True},
    )


@router.delete(
    "/{task_id}",
    response_model=ApiResponse[dict],
    summary="删除任务",
)
async def delete_task(
    task_id: str,
    redis: RedisDep,
    auth: AuthDep,
) -> ApiResponse[dict]:
    """删除任务。

    Args:
        task_id: 任务 ID。
        redis: Redis 客户端依赖。
        auth: 认证上下文依赖。

    Returns:
        删除结果。

    Raises:
        HTTPException: 任务不存在时抛出 404 错误。
    """
    _require_scope(auth, "tasks:write")

    success = await redis.delete_task(task_id, tenant_id=auth.tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在")

    return ApiResponse(
        code=200,
        message="任务已删除",
        data={"task_id": task_id, "deleted": True},
    )


@router.websocket("/{task_id}/ws")
async def task_websocket(
    websocket: WebSocket,
    task_id: str,
) -> None:
    """任务状态实时推送 WebSocket。

    WebSocket 鉴权在 accept 之前执行，鉴权失败关闭连接并返回。
    Scope 不足时以 WS_1008_POLICY_VIOLATION 关闭连接。

    Args:
        websocket: WebSocket 连接。
        task_id: 任务 ID。
    """
    # WebSocket 鉴权 — 必须在 accept() 之前
    try:
        auth = authenticate_websocket(websocket)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="鉴权失败")
        return

    # Scope 检查 — 需要 tasks:read 或 tasks:write
    try:
        _require_scope(auth, "tasks:read", "tasks:write")
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Forbidden")
        return

    await websocket.accept()

    redis = await get_redis_client()
    task_manager = get_task_manager()

    try:
        while True:
            # 获取任务状态
            try:
                status_data = await task_manager.get_task_status(
                    task_id, redis, tenant_id=auth.tenant_id
                )
                await websocket.send_json(status_data)

                # 如果任务已完成或失败，关闭连接
                if status_data.get("status") in ["completed", "failed"]:
                    break

            except ValueError:
                await websocket.send_json({"error": "任务不存在"})
                break

            # 等待一段时间后再次查询
            import asyncio

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()


async def get_redis_client() -> RedisClient:
    """获取 Redis 客户端实例。

    Returns:
        Redis 客户端实例。
    """
    from src.api.service.redis_client import get_redis

    return await get_redis()
