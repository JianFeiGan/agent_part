"""ModelProviderRepository 与 seed_model_providers 行为测试。

覆盖默认厂商查询、按类型列表、set_default 的互斥切换与类型校验，
以及 seed 的空表写入 / 非空跳过两条路径。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.db.model_provider_repository import ModelProviderRepository
from src.db.model_provider_seeder import seed_model_providers

# --------------------------------------------------------------------------- #
# 夹具
# --------------------------------------------------------------------------- #


def _result(*, one_or_none: Any = None, all_items: list[Any] | None = None) -> MagicMock:
    """构造 SQLAlchemy Result 替身。"""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=one_or_none)
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=all_items or [])
    result.scalars = MagicMock(return_value=scalars)
    return result


@pytest.fixture
def session() -> AsyncMock:
    """异步会话替身。"""
    return AsyncMock()


@pytest.fixture
def repo(session: AsyncMock) -> ModelProviderRepository:
    """ModelProviderRepository 实例。"""
    return ModelProviderRepository(session)


class TestGetDefault:
    """get_default 查询。"""

    async def test_returns_default_active_provider(
        self, repo: ModelProviderRepository, session: AsyncMock
    ) -> None:
        """命中默认启用厂商时返回该行。"""
        expected = MagicMock()
        session.execute = AsyncMock(return_value=_result(one_or_none=expected))

        assert await repo.get_default("tenant-1", "llm") is expected

    async def test_returns_none_when_absent(
        self, repo: ModelProviderRepository, session: AsyncMock
    ) -> None:
        """无默认厂商返回 None。"""
        session.execute = AsyncMock(return_value=_result(one_or_none=None))

        assert await repo.get_default("tenant-1", "llm") is None


class TestListByType:
    """list_by_type 查询。"""

    async def test_lists_active_only(
        self, repo: ModelProviderRepository, session: AsyncMock
    ) -> None:
        """仅返回启用中的厂商。"""
        rows = [MagicMock(), MagicMock()]
        session.execute = AsyncMock(return_value=_result(all_items=rows))

        result = await repo.list_by_type("tenant-1", "image")

        assert list(result) == rows

    async def test_type_filter_optional(
        self, repo: ModelProviderRepository, session: AsyncMock
    ) -> None:
        """provider_type 为 None 时不按类型过滤。"""
        session.execute = AsyncMock(return_value=_result(all_items=[]))

        assert list(await repo.list_by_type("tenant-1", None)) == []
        session.execute.assert_awaited_once()


class TestSetDefault:
    """set_default 的互斥切换。"""

    async def test_switches_default(
        self, repo: ModelProviderRepository, session: AsyncMock
    ) -> None:
        """清掉同类型旧默认后把目标置为默认。"""
        po = MagicMock()
        po.provider_type = "llm"
        po.is_default = False
        session.execute = AsyncMock(return_value=_result(one_or_none=po))
        session.flush = AsyncMock()
        session.refresh = AsyncMock()

        updated = await repo.set_default("tenant-1", 5, "llm")

        assert updated is po
        assert po.is_default is True
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once_with(po)

    async def test_missing_target_returns_none(
        self, repo: ModelProviderRepository, session: AsyncMock
    ) -> None:
        """目标厂商不存在时返回 None。"""
        session.execute = AsyncMock(return_value=_result(one_or_none=None))

        assert await repo.set_default("tenant-1", 99, "llm") is None
        session.flush.assert_not_called()

    async def test_type_mismatch_returns_none(
        self, repo: ModelProviderRepository, session: AsyncMock
    ) -> None:
        """厂商类型与请求不符时拒绝切换。"""
        po = MagicMock()
        po.provider_type = "image"
        session.execute = AsyncMock(return_value=_result(one_or_none=po))

        assert await repo.set_default("tenant-1", 5, "llm") is None
        session.flush.assert_not_called()


class TestSeedModelProviders:
    """seed_model_providers。"""

    async def test_seeds_when_empty(self, session: AsyncMock) -> None:
        """租户无配置时写入预置厂商。"""
        session.execute = AsyncMock(return_value=_result(one_or_none=None))
        session.add = MagicMock()
        session.flush = AsyncMock()

        await seed_model_providers(session, "tenant-new")

        assert session.add.call_count > 0
        session.flush.assert_awaited_once()
        tenants = {call.args[0].tenant_id for call in session.add.call_args_list}
        assert tenants == {"tenant-new"}

    async def test_skips_when_already_seeded(self, session: AsyncMock) -> None:
        """已有配置时不重复写入。"""
        session.execute = AsyncMock(return_value=_result(one_or_none=MagicMock()))
        session.add = MagicMock()
        session.flush = AsyncMock()

        await seed_model_providers(session, "tenant-a")

        session.add.assert_not_called()
        session.flush.assert_not_called()

    async def test_preset_covers_all_provider_types(self, session: AsyncMock) -> None:
        """预置数据覆盖 llm/image/video 三类。"""
        session.execute = AsyncMock(return_value=_result(one_or_none=None))
        session.add = MagicMock()
        session.flush = AsyncMock()

        await seed_model_providers(session, "tenant-new")

        types = {call.args[0].provider_type for call in session.add.call_args_list}
        assert types == {"llm", "image", "video"}
