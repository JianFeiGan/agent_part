"""
仪表盘 API 测试。

Description:
    测试仪表盘统计 API 端点。
@author ganjianfei
@version 1.0.0
2026-06-12
"""

import asyncio
from types import MethodType

import pytest

from src.auth.context import AuthContext


class FakeRedis:
    """模拟 Redis 客户端，用于测试。"""

    def __init__(self) -> None:
        self._tasks: list[dict] = [
            {
                "task_id": "task_001",
                "product_id": "prod_001",
                "status": "completed",
                "progress": 100.0,
                "current_step": "completed",
                "created_at": "2026-06-12T10:00:00",
                "updated_at": "2026-06-12T10:30:00",
                "request": {"task_type": "image_only"},
            },
            {
                "task_id": "task_002",
                "product_id": "prod_002",
                "status": "running",
                "progress": 45.0,
                "current_step": "creative_planning",
                "created_at": "2026-06-12T11:00:00",
                "updated_at": "2026-06-12T11:15:00",
                "request": {"task_type": "image_and_video"},
            },
            {
                "task_id": "task_003",
                "product_id": "prod_003",
                "status": "failed",
                "progress": 10.0,
                "current_step": "image_generation",
                "created_at": "2026-06-12T09:00:00",
                "updated_at": "2026-06-12T09:05:00",
                "request": {"task_type": "video_only"},
            },
        ]

    async def list_products(
        self, *, tenant_id: str, page: int = 1, page_size: int = 1, category: str | None = None  # noqa: ARG002
    ) -> tuple[list, int]:
        return [], 3

    async def list_tasks(
        self, *, tenant_id: str, page: int = 1, page_size: int = 10, status: str | None = None  # noqa: ARG002
    ) -> tuple[list[dict], int]:
        filtered = [t for t in self._tasks if status is None or t["status"] == status]
        start = (page - 1) * page_size
        end = start + page_size
        return filtered[start:end], len(filtered)


@pytest.fixture
def fake_redis() -> FakeRedis:
    """创建模拟 Redis 客户端。"""
    return FakeRedis()


@pytest.fixture
def auth_ctx() -> AuthContext:
    """创建测试用 AuthContext。"""
    return AuthContext(tenant_id="test_tenant", user_id="test_user", scopes=["*"])


class TestDashboardAPI:
    """仪表盘 API 测试。"""

    def test_get_dashboard_stats_success(
        self, fake_redis: FakeRedis, auth_ctx: AuthContext
    ) -> None:
        """测试获取仪表盘统计数据成功。"""
        from src.api.router.dashboard import get_dashboard_stats

        async def _run() -> None:
            result = await get_dashboard_stats(
                redis=fake_redis,  # type: ignore[arg-type]
                auth=auth_ctx,
            )
            assert result.code == 200
            assert result.message == "获取成功"
            assert result.data is not None
            assert result.data.total_products == 3
            assert result.data.total_tasks == 3
            # running_tasks 来自 status="running" 的 list_tasks 调用，而非 TaskManager
            assert result.data.running_tasks == 1
            assert result.data.failed_tasks == 1
            assert len(result.data.recent_tasks) == 3
            assert result.data.recent_tasks[0].task_id == "task_001"
            assert result.data.recent_tasks[0].status == "completed"
            assert result.data.recent_tasks[0].task_type == "image_only"

        asyncio.run(_run())

    def test_get_dashboard_stats_empty(self, auth_ctx: AuthContext) -> None:
        """测试空数据时仪表盘统计。"""
        empty_redis = FakeRedis()
        empty_redis._tasks = []  # type: ignore[attr-defined]

        from src.api.router.dashboard import get_dashboard_stats

        async def _run() -> None:
            result = await get_dashboard_stats(
                redis=empty_redis,  # type: ignore[arg-type]
                auth=auth_ctx,
            )
            assert result.code == 200
            assert result.data is not None
            assert result.data.total_products == 3
            assert result.data.total_tasks == 0
            assert len(result.data.recent_tasks) == 0

        asyncio.run(_run())

    def test_get_dashboard_stats_all_running(self, auth_ctx: AuthContext) -> None:
        """测试所有任务都在运行时的统计。"""
        running_redis = FakeRedis()
        running_redis._tasks = [  # type: ignore[attr-defined]
            {
                "task_id": "t1",
                "product_id": "p1",
                "status": "running",
                "progress": 50.0,
                "current_step": "image_generation",
                "created_at": "2026-06-12T10:00:00",
                "updated_at": "2026-06-12T10:15:00",
                "request": {"task_type": "image_only"},
            },
            {
                "task_id": "t2",
                "product_id": "p2",
                "status": "running",
                "progress": 20.0,
                "current_step": "requirement_analysis",
                "created_at": "2026-06-12T11:00:00",
                "updated_at": "2026-06-12T11:05:00",
                "request": {"task_type": "image_and_video"},
            },
        ]

        from src.api.router.dashboard import get_dashboard_stats

        async def _run() -> None:
            result = await get_dashboard_stats(
                redis=running_redis,  # type: ignore[arg-type]
                auth=auth_ctx,
            )
            assert result.data is not None
            assert result.data.total_tasks == 2
            # running_tasks 来自 status="running" 的 list_tasks 聚合
            assert result.data.running_tasks == 2
            assert result.data.failed_tasks == 0
            assert len(result.data.recent_tasks) == 2

        asyncio.run(_run())

    def test_get_dashboard_stats_no_running_tasks(self, auth_ctx: AuthContext) -> None:
        """测试没有运行中任务时的统计。"""
        no_running_redis = FakeRedis()
        no_running_redis._tasks = [  # type: ignore[attr-defined]
            {
                "task_id": "t1",
                "product_id": "p1",
                "status": "completed",
                "progress": 100.0,
                "current_step": "completed",
                "created_at": "2026-06-12T10:00:00",
                "updated_at": "2026-06-12T10:30:00",
                "request": {"task_type": "image_only"},
            },
        ]

        from src.api.router.dashboard import get_dashboard_stats

        async def _run() -> None:
            result = await get_dashboard_stats(
                redis=no_running_redis,  # type: ignore[arg-type]
                auth=auth_ctx,
            )
            assert result.data is not None
            assert result.data.total_tasks == 1
            # running_tasks 来自 status="running" 的 list_tasks 聚合
            assert result.data.running_tasks == 0
            assert result.data.failed_tasks == 0

        asyncio.run(_run())

    def test_task_type_extraction(self) -> None:
        """测试 task_type 从 request 字典中正确提取。"""
        from src.api.router.dashboard import _extract_task_type

        # 正常情况
        assert _extract_task_type({"request": {"task_type": "image_only"}}) == "image_only"
        assert _extract_task_type({"request": {"task_type": "image_and_video"}}) == "image_and_video"
        assert _extract_task_type({"request": {"task_type": "video_only"}}) == "video_only"

        # 缺失 request 字段
        assert _extract_task_type({}) is None

        # request 为 None
        assert _extract_task_type({"request": None}) is None

        # request 中无 task_type
        assert _extract_task_type({"request": {"foo": "bar"}}) is None

    def test_product_id_none_for_empty_string(self, auth_ctx: AuthContext) -> None:
        """测试 product_id 为空字符串时转换为 None。"""
        empty_prod_redis = FakeRedis()
        empty_prod_redis._tasks = [  # type: ignore[attr-defined]
            {
                "task_id": "t1",
                "product_id": "",
                "status": "completed",
                "progress": 100.0,
                "current_step": "completed",
                "created_at": "2026-06-12T10:00:00",
                "updated_at": "2026-06-12T10:30:00",
                "request": {"task_type": "image_only"},
            },
        ]

        from src.api.router.dashboard import get_dashboard_stats

        async def _run() -> None:
            result = await get_dashboard_stats(
                redis=empty_prod_redis,  # type: ignore[arg-type]
                auth=auth_ctx,
            )
            assert result.data is not None
            assert result.data.recent_tasks[0].product_id is None

        asyncio.run(_run())


class FakeRedisListClient:
    """模拟 Redis sorted set 客户端。"""

    async def zrevrange(self, key: str, start: int, end: int) -> list[str]:  # noqa: ARG002
        return ["task_004", "task_003", "task_002", "task_001"]


class TestRedisClientTaskListing:
    """RedisClient 任务列表过滤语义测试。"""

    def test_list_tasks_filters_before_pagination(self) -> None:
        """测试状态过滤先于分页，并返回过滤后的总数。"""
        from src.api.service.redis_client import RedisClient

        redis_client = RedisClient()
        metadata_by_id = {
            "task_004": {"task_id": "task_004", "status": "completed"},
            "task_003": {"task_id": "task_003", "status": "running"},
            "task_002": {"task_id": "task_002", "status": "failed"},
            "task_001": {"task_id": "task_001", "status": "running"},
        }

        async def _ensure_connected(self) -> FakeRedisListClient:  # noqa: ANN001
            return FakeRedisListClient()

        async def _get_task_metadata(self, task_id: str, *, tenant_id: str) -> dict:  # noqa: ARG002
            return metadata_by_id[task_id]

        async def _get_task_state(self, task_id: str, *, tenant_id: str):  # noqa: ANN001, ARG002
            return None

        redis_client._ensure_connected = MethodType(_ensure_connected, redis_client)  # type: ignore[method-assign]
        redis_client.get_task_metadata = MethodType(_get_task_metadata, redis_client)  # type: ignore[method-assign]
        redis_client.get_task_state = MethodType(_get_task_state, redis_client)  # type: ignore[method-assign]

        async def _run() -> None:
            tasks, total = await redis_client.list_tasks(
                tenant_id="test_tenant", page=1, page_size=1, status="running"
            )

            assert total == 2
            assert len(tasks) == 1
            assert tasks[0]["task_id"] == "task_003"

        asyncio.run(_run())
