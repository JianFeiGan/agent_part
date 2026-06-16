"""
适配器配置管理器。

Description:
    从数据库读取平台适配器凭证，支持多店铺的配置。
    内存缓存 + 5 分钟过期，减少数据库查询。
    单例模式，全局共享。
    租户感知：缓存 key 和查询均包含 tenant_id。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
import time
from typing import Any

from sqlalchemy import select

from src.db.listing_models import AdapterConfigPO
from src.db.postgres import get_db
from src.models.listing import Platform

logger = logging.getLogger(__name__)

CACHE_TTL = 300  # 5 分钟


class AdapterConfigManager:
    """适配器配置管理器（单例）。

    职责:
    - 从 adapter_configs 表读取平台凭证
    - 支持多店铺（同平台多配置）
    - 内存缓存 + 5 分钟过期
    - 租户感知：缓存 key 为 (tenant_id, platform, shop_id)
    """

    _instance: "AdapterConfigManager | None" = None
    _cache: dict[tuple[str, Platform, str], tuple[dict, float]]

    def __new__(cls) -> "AdapterConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache = {}
        return cls._instance

    async def get_config(
        self, platform: Platform, shop_id: str = "default", tenant_id: str = "dev"
    ) -> dict[str, Any] | None:
        """获取平台适配器配置。

        Args:
            platform: 平台枚举。
            shop_id: 店铺 ID，默认 "default"。
            tenant_id: 租户 ID，默认 "dev"。

        Returns:
            凭证字典（含 client_id, client_secret 等），未找到返回 None。
        """
        cache_key = (tenant_id, platform, shop_id)

        # 检查缓存
        if cache_key in self._cache:
            cached, expiry = self._cache[cache_key]
            if time.time() < expiry:
                return cached.copy()
            else:
                del self._cache[cache_key]

        # 查询数据库
        try:
            async with get_db() as session:
                stmt = select(AdapterConfigPO).where(
                    AdapterConfigPO.tenant_id == tenant_id,
                    AdapterConfigPO.platform == platform.value,
                    AdapterConfigPO.shop_id == shop_id,
                    AdapterConfigPO.is_active == True,  # noqa: E712
                )
                result = await session.execute(stmt)
                config_po = result.scalar_one_or_none()

                if config_po:
                    creds = config_po.credentials.copy()
                    self._cache[cache_key] = (creds, time.time() + CACHE_TTL)
                    logger.info(
                        f"Adapter config loaded: tenant={tenant_id}, "
                        f"platform={platform.value}, shop={shop_id}"
                    )
                    return creds
                else:
                    logger.warning(
                        f"No active adapter config found: tenant={tenant_id}, "
                        f"platform={platform.value}, shop={shop_id}"
                    )
                    return None

        except Exception:
            logger.exception(
                f"Failed to load adapter config for tenant={tenant_id}, "
                f"{platform.value}/{shop_id}"
            )
            return None

    async def invalidate_cache(
        self,
        platform: Platform,
        shop_id: str | None = None,
        tenant_id: str | None = None,
    ) -> None:
        """清除缓存。

        Args:
            platform: 平台枚举。
            shop_id: 可选的店铺 ID，不指定则清除该平台所有缓存。
            tenant_id: 可选的租户 ID，不指定则清除所有租户的该平台缓存。
        """
        if tenant_id and shop_id:
            self._cache.pop((tenant_id, platform, shop_id), None)
        elif tenant_id:
            keys_to_remove = [
                k for k in self._cache if k[0] == tenant_id and k[1] == platform
            ]
            for k in keys_to_remove:
                del self._cache[k]
        else:
            keys_to_remove = [k for k in self._cache if k[1] == platform]
            for k in keys_to_remove:
                del self._cache[k]
        logger.info(
            f"Adapter config cache invalidated: "
            f"tenant={tenant_id or 'all'}, {platform.value}/{shop_id or 'all'}"
        )
