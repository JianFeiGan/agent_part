"""
存储后端工厂函数。
"""

from functools import lru_cache

from src.config.settings import get_settings
from src.storage.local import LocalStorageBackend


@lru_cache
def get_storage_backend() -> LocalStorageBackend:
    """获取存储后端实例（单例）。

    根据配置中的 storage_type 返回对应的后端实现。
    当前仅支持 local。

    Returns:
        存储后端实例。

    Raises:
        ValueError: 不支持的 storage_type。
    """
    settings = get_settings()
    if settings.storage_type == "local":
        return LocalStorageBackend()
    raise ValueError(f"Unsupported storage type: {settings.storage_type}")
