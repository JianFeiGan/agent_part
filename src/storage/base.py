"""
存储后端协议。
"""

from typing import Protocol


class StorageBackend(Protocol):
    """存储后端抽象协议。

    定义统一的存储操作接口，支持本地文件系统和对象存储。
    """

    async def save(self, data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
        """保存数据并返回可访问 URL。

        Args:
            data: 文件二进制数据。
            key: 存储键名。
            content_type: MIME 类型。

        Returns:
            可访问 URL。
        """
        ...

    async def delete(self, key: str) -> bool:
        """删除指定键的文件。

        Args:
            key: 存储键名。

        Returns:
            是否删除成功。
        """
        ...

    async def exists(self, key: str) -> bool:
        """检查键是否存在。

        Args:
            key: 存储键名。

        Returns:
            是否存在。
        """
        ...

    def get_url(self, key: str) -> str:
        """获取指定键的可访问 URL。

        Args:
            key: 存储键名。

        Returns:
            可访问 URL。
        """
        ...
