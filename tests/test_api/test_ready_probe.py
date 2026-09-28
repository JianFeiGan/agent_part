"""
就绪/存活探针 HTTP 层验收。

Description:
    用应用级测试客户端驱动完整应用的 /api/v1/health 与 /api/v1/ready，
    钉住存活（liveness）与就绪（readiness）在缓存三态下的语义差异：
    - 存活：缓存 not_configured 判健康；disconnected 判降级但 HTTP 仍 2xx
    - 就绪：存储与缓存均 connected 才 200；存储不可用 / 缓存不可用 /
      缓存未配置 三种情况均 503，依赖明细分别指出是哪一层
    故障注入在 RedisClient（redis.from_url）与 get_db_session 服务边界，
    不替换 router 内部探测函数、不读内部状态。
@author ganjianfei
@version 2.0.0
2026-09-28
"""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from main import app


@dataclass
class DepState:
    """外部依赖注入状态，测试用例直接改写字段以驱动探针结果。

    Attributes:
        postgres: PostgreSQL 探测结果，connected / disconnected。
        redis: 缓存探测结果，connected / disconnected / not_configured。
    """

    postgres: str = "connected"
    redis: str = "connected"


@pytest.fixture
def deps() -> Iterator[DepState]:
    """在服务边界注入可控的 PostgreSQL / Redis 依赖。

    注入点是 RedisClient 所用的 redis.from_url 与 health 模块的
    get_db_session（公共依赖），不替换 _check_postgres / _check_redis。
    同时清零 health 模块级 Redis 连接缓存，保证用例隔离。
    """
    from src.api.router import health as health_mod

    state = DepState()

    def _fake_from_url(*_args: Any, **_kwargs: Any) -> MagicMock | None:
        """返回可控的 Redis 连接对象，模拟缓存三态。"""
        if state.redis == "not_configured":
            return None
        conn = MagicMock()
        if state.redis == "connected":
            conn.ping = AsyncMock(return_value=True)
        else:
            conn.ping = AsyncMock(side_effect=ConnectionError("redis down"))
        return conn

    @asynccontextmanager
    async def _fake_get_db_session() -> AsyncIterator[MagicMock]:
        """返回可控的数据库会话，模拟存储可用 / 不可用。"""
        if state.postgres == "connected":
            session = MagicMock()
            session.execute = AsyncMock(return_value=None)
            yield session
        else:
            raise ConnectionError("postgres down")

    # 模块级连接缓存跨用例保留，测试卫生重置（非断言内部状态）
    health_mod._redis_client = None
    with (
        patch("src.api.service.redis_client.redis.from_url", _fake_from_url),
        patch("src.api.router.health.get_db_session", _fake_get_db_session),
    ):
        yield state
    health_mod._redis_client = None


@pytest.fixture
def client(deps: DepState) -> TestClient:
    """创建应用级测试客户端（依赖注入须先就位）。"""
    return TestClient(app)


class TestLivenessProbe:
    """存活探针 /health：进程可响应即成功，不强制依赖。"""

    def test_200_ok_when_cache_connected(self, client: TestClient, deps: DepState) -> None:
        """缓存可用时判定健康。"""
        deps.redis = "connected"

        response = client.get("/api/v1/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["redis"] == "connected"

    def test_200_ok_when_cache_not_configured(self, client: TestClient, deps: DepState) -> None:
        """缓存未配置时仍判定为健康（与就绪语义相反，刻意设计）。"""
        deps.redis = "not_configured"

        response = client.get("/api/v1/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["redis"] == "not_configured"

    def test_200_degraded_when_cache_disconnected(self, client: TestClient, deps: DepState) -> None:
        """缓存断连时判定降级，但 HTTP 仍成功（不触发编排器误重启）。"""
        deps.redis = "disconnected"

        response = client.get("/api/v1/health")

        # 关键：降级不改 HTTP 状态，编排器不会误重启
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["redis"] == "disconnected"


class TestReadinessProbe:
    """就绪探针 /ready：存储与缓存同时可用才放行。"""

    def test_200_ready_when_storage_and_cache_connected(
        self, client: TestClient, deps: DepState
    ) -> None:
        """存储与缓存均可用时返回 200 且判定就绪。"""
        deps.postgres = "connected"
        deps.redis = "connected"

        response = client.get("/api/v1/ready")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["postgres"] == "connected"
        assert body["redis"] == "connected"

    def test_503_when_storage_unavailable(self, client: TestClient, deps: DepState) -> None:
        """存储不可用时拒绝就绪，依赖明细指向存储层。"""
        deps.postgres = "disconnected"

        response = client.get("/api/v1/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "not_ready"
        assert body["postgres"] == "disconnected"
        assert body["redis"] == "connected"

    def test_503_when_cache_unavailable(self, client: TestClient, deps: DepState) -> None:
        """缓存断连时拒绝就绪，依赖明细指向缓存层。"""
        deps.redis = "disconnected"

        response = client.get("/api/v1/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "not_ready"
        assert body["postgres"] == "connected"
        assert body["redis"] == "disconnected"

    def test_503_when_cache_not_configured(self, client: TestClient, deps: DepState) -> None:
        """缓存未配置时同样拒绝就绪（与存活语义相反）。"""
        deps.redis = "not_configured"

        response = client.get("/api/v1/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "not_ready"
        assert body["postgres"] == "connected"
        assert body["redis"] == "not_configured"

    def test_503_body_pinpoints_both_layers_when_both_down(
        self, client: TestClient, deps: DepState
    ) -> None:
        """双层同时不可用时，依赖明细同时指出两层。"""
        deps.postgres = "disconnected"
        deps.redis = "disconnected"

        response = client.get("/api/v1/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "not_ready"
        assert body["postgres"] == "disconnected"
        assert body["redis"] == "disconnected"


class TestLivenessReadinessDivergence:
    """存活与就绪在缓存未配置时语义相反——刻意设计，显式钉住。"""

    def test_cache_not_configured(self, client: TestClient, deps: DepState) -> None:
        """同一依赖状态下：存活判健康，就绪判未就绪。"""
        deps.postgres = "connected"
        deps.redis = "not_configured"

        liveness = client.get("/api/v1/health")
        readiness = client.get("/api/v1/ready")

        # 存活：未配置 = 健康，HTTP 成功
        assert liveness.status_code == 200
        assert liveness.json()["status"] == "ok"
        assert liveness.json()["redis"] == "not_configured"

        # 就绪：未配置 = 不可用，HTTP 503
        assert readiness.status_code == 503
        assert readiness.json()["status"] == "not_ready"
        assert readiness.json()["redis"] == "not_configured"
