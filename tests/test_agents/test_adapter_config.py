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
        return AdapterConfigManager()

    def test_singleton(self) -> None:
        """测试管理器是单例。"""
        m1 = AdapterConfigManager()
        m2 = AdapterConfigManager()
        assert m1 is m2

    @pytest.mark.asyncio
    async def test_get_config_from_db(self, manager: AdapterConfigManager) -> None:
        """测试从数据库获取配置。"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(
            platform="amazon",
            shop_id="default",
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

            config = await manager.get_config(Platform.AMAZON, "default")
            assert config is not None
            assert config["client_id"] == "REDACTED_CLIENT"

    @pytest.mark.asyncio
    async def test_cache_hit(self, manager: AdapterConfigManager) -> None:
        """测试缓存命中。"""
        key = (Platform.AMAZON, "shop-1")
        cached = {"client_id": "cached"}
        manager._cache[key] = (cached, 9999999999.0)  # 很久才过期

        result = await manager.get_config(Platform.AMAZON, "shop-1")
        assert result == cached

    @pytest.mark.asyncio
    async def test_cache_expired(self, manager: AdapterConfigManager) -> None:
        """测试缓存过期后重新查询。"""
        key = (Platform.AMAZON, "shop-2")
        manager._cache[key] = ({"old": True}, 0.0)  # 已过期

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(
            platform="amazon", shop_id="shop-2",
            credentials={"client_id": "fresh"}, is_active=True,
        )
        mock_session.execute.return_value = mock_result

        with patch("src.agents.adapter_config.get_db") as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            config = await manager.get_config(Platform.AMAZON, "shop-2")
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

            result = await manager.get_config(Platform.EBAY, "nonexistent")
            assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_cache(self, manager: AdapterConfigManager) -> None:
        """测试清除缓存。"""
        key = (Platform.SHOPIFY, "shop-3")
        manager._cache[key] = ({"test": True}, 9999999999.0)
        await manager.invalidate_cache(Platform.SHOPIFY, "shop-3")
        assert key not in manager._cache

    @pytest.mark.asyncio
    async def test_invalidate_all_platform(self, manager: AdapterConfigManager) -> None:
        """测试清除某平台所有店铺的缓存。"""
        manager._cache[(Platform.AMAZON, "shop-1")] = ({"a": 1}, 9999999999.0)
        manager._cache[(Platform.AMAZON, "shop-2")] = ({"b": 2}, 9999999999.0)
        manager._cache[(Platform.EBAY, "shop-1")] = ({"c": 3}, 9999999999.0)

        await manager.invalidate_cache(Platform.AMAZON)

        assert (Platform.AMAZON, "shop-1") not in manager._cache
        assert (Platform.AMAZON, "shop-2") not in manager._cache
        assert (Platform.EBAY, "shop-1") in manager._cache
