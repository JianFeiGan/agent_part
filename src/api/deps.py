"""
API 依赖注入模块。

Description:
    提供 FastAPI 路由的公共依赖项，包括 Redis 客户端、配置等。
@author ganjianfei
@version 1.0.0
2026-03-25
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends

from src.api.service.redis_client import RedisClient, get_redis
from src.config.settings import Settings, get_settings


async def get_settings_dep() -> AsyncGenerator[Settings, None]:
    """获取应用配置依赖。

    Yields:
        配置实例。
    """
    yield get_settings()


async def get_redis_dep() -> AsyncGenerator[RedisClient, None]:
    """获取 Redis 客户端依赖。

    Yields:
        Redis 客户端实例。
    """
    client = await get_redis()
    yield client


# 类型别名，简化依赖注入
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
RedisDep = Annotated[RedisClient, Depends(get_redis_dep)]
