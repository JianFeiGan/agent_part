"""适配器配置管理器测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.adapter_config import AdapterConfigManager
from src.models.listing import Platform


class TestAdapterConfigManager:
    """测试适配器配置管理器。"""

    @pytest.fixture
    def manager(self) -> AdapterConfigManager:
        """创建配置管理器实例。"""
        mgr = AdapterConfigManager()
        mgr._cache.clear()
        return mgr

    def test_singleton(self) -> None:
        """测试管理器是单例。"""
        m1 = AdapterConfigManager()
        m2 = AdapterConfigManager()
        assert m1 is m2

    @pytest.mark.asyncio
    async def test_get_config_from_db(self, manager: AdapterConfigManager) -> None:
        """测试从数据库获取配置（租户感知）。"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(
            platform="amazon",
            shop_id="default",
            tenant_id="tenant-a",
            credentials={
                "client_id": "REDACTED_CLIENT",
                "client_secret": "REDACTED_SECRET",
            },
            is_active=True,
        )
        mock_session.execute.return_value = mock_result

        with patch("src.agents.adapter_config.get_db") as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            config = await manager.get_config(Platform.AMAZON, "default", tenant_id="tenant-a")
            assert config is not None
            assert config["client_id"] == "REDACTED_CLIENT"

    @pytest.mark.asyncio
    async def test_cache_hit(self, manager: AdapterConfigManager) -> None:
        """测试缓存命中（tenant-aware key）。"""
        key = ("tenant-x", Platform.AMAZON, "shop-1")
        cached = {"client_id": "cached"}
        manager._cache[key] = (cached, 9999999999.0)  # 很久才过期

        result = await manager.get_config(Platform.AMAZON, "shop-1", tenant_id="tenant-x")
        assert result == cached
        assert result is not cached  # 返回副本，不是同一对象

    @pytest.mark.asyncio
    async def test_cache_expired(self, manager: AdapterConfigManager) -> None:
        """测试缓存过期后重新查询。"""
        key = ("tenant-b", Platform.AMAZON, "shop-2")
        manager._cache[key] = ({"old": True}, 0.0)  # 已过期

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(
            platform="amazon",
            shop_id="shop-2",
            tenant_id="tenant-b",
            credentials={"client_id": "fresh"},
            is_active=True,
        )
        mock_session.execute.return_value = mock_result

        with patch("src.agents.adapter_config.get_db") as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            config = await manager.get_config(Platform.AMAZON, "shop-2", tenant_id="tenant-b")
            assert config["client_id"] == "fresh"

    @pytest.mark.asyncio
    async def test_config_not_found(self, manager: AdapterConfigManager) -> None:
        """测试配置不存在返回 None。"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("src.agents.adapter_config.get_db") as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await manager.get_config(Platform.EBAY, "nonexistent", tenant_id="tenant-c")
            assert result is None

    @pytest.mark.asyncio
    async def test_db_error_returns_none(self, manager: AdapterConfigManager) -> None:
        """测试数据库异常时返回 None。"""
        with patch("src.agents.adapter_config.get_db") as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(side_effect=ConnectionError("DB down"))
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await manager.get_config(Platform.AMAZON, "error-shop", tenant_id="tenant-d")
            assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_cache(self, manager: AdapterConfigManager) -> None:
        """测试清除缓存（tenant-aware）。"""
        key = ("tenant-e", Platform.SHOPIFY, "shop-3")
        manager._cache[key] = ({"test": True}, 9999999999.0)
        await manager.invalidate_cache(Platform.SHOPIFY, "shop-3", tenant_id="tenant-e")
        assert key not in manager._cache

    @pytest.mark.asyncio
    async def test_invalidate_all_platform_single_tenant(
        self, manager: AdapterConfigManager
    ) -> None:
        """测试清除某租户某平台所有店铺的缓存。"""
        manager._cache[("tenant-f", Platform.AMAZON, "shop-1")] = ({"a": 1}, 9999999999.0)
        manager._cache[("tenant-f", Platform.AMAZON, "shop-2")] = ({"b": 2}, 9999999999.0)
        manager._cache[("tenant-f", Platform.EBAY, "shop-1")] = ({"c": 3}, 9999999999.0)
        manager._cache[("tenant-g", Platform.AMAZON, "shop-1")] = ({"d": 4}, 9999999999.0)

        await manager.invalidate_cache(Platform.AMAZON, tenant_id="tenant-f")

        assert ("tenant-f", Platform.AMAZON, "shop-1") not in manager._cache
        assert ("tenant-f", Platform.AMAZON, "shop-2") not in manager._cache
        assert ("tenant-f", Platform.EBAY, "shop-1") in manager._cache
        assert ("tenant-g", Platform.AMAZON, "shop-1") in manager._cache

    @pytest.mark.asyncio
    async def test_invalidate_all_tenants(self, manager: AdapterConfigManager) -> None:
        """测试不指定 tenant 时清除所有租户的该平台缓存。"""
        manager._cache[("tenant-h", Platform.AMAZON, "shop-1")] = ({"a": 1}, 9999999999.0)
        manager._cache[("tenant-i", Platform.AMAZON, "shop-2")] = ({"b": 2}, 9999999999.0)
        manager._cache[("tenant-h", Platform.EBAY, "shop-1")] = ({"c": 3}, 9999999999.0)

        await manager.invalidate_cache(Platform.AMAZON)

        assert ("tenant-h", Platform.AMAZON, "shop-1") not in manager._cache
        assert ("tenant-i", Platform.AMAZON, "shop-2") not in manager._cache
        assert ("tenant-h", Platform.EBAY, "shop-1") in manager._cache

    @pytest.mark.asyncio
    async def test_different_tenants_separate_cache(
        self, manager: AdapterConfigManager
    ) -> None:
        """测试不同租户的配置相互隔离。"""
        mock_session = AsyncMock()
        mock_result_a = MagicMock()
        mock_result_a.scalar_one_or_none.return_value = MagicMock(
            platform="amazon",
            shop_id="default",
            tenant_id="tenant-a",
            credentials={"client_id": "from_a"},
            is_active=True,
        )
        mock_result_b = MagicMock()
        mock_result_b.scalar_one_or_none.return_value = MagicMock(
            platform="amazon",
            shop_id="default",
            tenant_id="tenant-b",
            credentials={"client_id": "from_b"},
            is_active=True,
        )
        # First call returns a, second returns b
        mock_session.execute = AsyncMock(
            side_effect=[mock_result_a, mock_result_b]
        )

        with patch("src.agents.adapter_config.get_db") as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            config_a = await manager.get_config(
                Platform.AMAZON, "default", tenant_id="tenant-a"
            )
            config_b = await manager.get_config(
                Platform.AMAZON, "default", tenant_id="tenant-b"
            )

            assert config_a["client_id"] == "from_a"
            assert config_b["client_id"] == "from_b"
