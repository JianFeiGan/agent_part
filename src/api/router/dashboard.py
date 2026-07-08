"""
仪表盘路由。

Description:
    提供仪表盘统计数据的聚合查询接口。
@author ganjianfei
@version 1.0.0
2026-06-12
"""

from fastapi import APIRouter

from src.api.deps import AuthDep, RedisDep
from src.api.schema.common import ApiResponse
from src.api.schema.dashboard import DashboardStatsResponse, RecentTaskItem

router = APIRouter()


def _extract_task_type(task: dict) -> str | None:
    """从任务字典中提取 task_type。

    任务元数据中 request 字段存储了序列化的 GenerationRequest，
    task_type 位于 request.task_type 中。

    Args:
        task: 任务元数据字典。

    Returns:
        任务类型字符串，如果无法提取则返回 None。
    """
    request = task.get("request") or {}
    return request.get("task_type")


@router.get(
    "/stats",
    response_model=ApiResponse[DashboardStatsResponse],
    summary="获取仪表盘统计数据",
)
async def get_dashboard_stats(
    redis: RedisDep,
    auth: AuthDep,
) -> ApiResponse[DashboardStatsResponse]:
    """获取仪表盘聚合统计数据。

    返回商品总数、任务总数、运行中/失败任务数以及最近任务列表。

    Args:
        redis: Redis 客户端依赖。
        auth: 认证上下文依赖。

    Returns:
        仪表盘统计数据。
    """
    # 商品总数
    _, total_products = await redis.list_products(
        tenant_id=auth.tenant_id, page=1, page_size=1
    )

    # 任务总数
    _, total_tasks = await redis.list_tasks(
        tenant_id=auth.tenant_id, page=1, page_size=1
    )

    # 运行中任务数（按状态聚合）
    _, running_tasks = await redis.list_tasks(
        tenant_id=auth.tenant_id, page=1, page_size=1, status="running"
    )

    # 失败任务数
    _, failed_tasks = await redis.list_tasks(
        tenant_id=auth.tenant_id, page=1, page_size=1, status="failed"
    )

    # 最近任务（最新 5 条）
    recent, _ = await redis.list_tasks(
        tenant_id=auth.tenant_id, page=1, page_size=5
    )

    recent_items = [
        RecentTaskItem(
            task_id=t.get("task_id", ""),
            product_id=t.get("product_id") or None,
            task_type=_extract_task_type(t),
            status=t.get("status", "pending"),
            progress=t.get("progress", 0.0),
            current_step=t.get("current_step", "init"),
            created_at=t.get("created_at"),
            updated_at=t.get("updated_at"),
        )
        for t in recent
    ]

    return ApiResponse(
        code=200,
        message="获取成功",
        data=DashboardStatsResponse(
            total_products=total_products,
            total_tasks=total_tasks,
            running_tasks=running_tasks,
            failed_tasks=failed_tasks,
            recent_tasks=recent_items,
        ),
    )
