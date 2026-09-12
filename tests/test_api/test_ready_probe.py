"""/ready 就绪探针：依赖失败时 503。"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_ready_not_ready_when_db_fails() -> None:
    from fastapi import Response

    from src.api.router import health as health_mod

    with (
        patch.object(health_mod, "_check_postgres", AsyncMock(return_value="disconnected")),
        patch.object(health_mod, "_check_redis", AsyncMock(return_value="connected")),
    ):
        response = Response()
        body = await health_mod.ready_check(response)
        assert response.status_code == 503
        assert body["status"] == "not_ready"
        assert body["postgres"] == "disconnected"


@pytest.mark.asyncio
async def test_ready_ok_when_deps_up() -> None:
    from fastapi import Response

    from src.api.router import health as health_mod

    with (
        patch.object(health_mod, "_check_postgres", AsyncMock(return_value="connected")),
        patch.object(health_mod, "_check_redis", AsyncMock(return_value="connected")),
    ):
        response = Response()
        body = await health_mod.ready_check(response)
        assert response.status_code == 200
        assert body["status"] == "ready"
