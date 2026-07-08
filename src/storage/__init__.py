"""
存储抽象层。

提供统一的 StorageBackend 协议和本地/OSS 实现。
"""

from src.storage.base import StorageBackend
from src.storage.factory import get_storage_backend
from src.storage.local import LocalStorageBackend

__all__ = [
    "LocalStorageBackend",
    "StorageBackend",
    "get_storage_backend",
]
