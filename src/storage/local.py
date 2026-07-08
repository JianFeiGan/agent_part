"""
本地文件系统存储后端。
"""

import hashlib
import uuid
from pathlib import Path

from src.config.settings import get_settings


class LocalStorageBackend:
    """本地文件系统存储后端。

    将文件保存到配置的本地目录，通过 FastAPI StaticFiles 提供访问。

    Example:
        >>> backend = LocalStorageBackend()
        >>> url = await backend.save(data, key="images/abc.png",
        ...     content_type="image/png")
        >>> print(url)
        /static/images/abc.png
    """

    def __init__(self, base_path: str | None = None) -> None:
        """初始化本地存储后端。

        Args:
            base_path: 存储根目录，默认从配置读取。
        """
        settings = get_settings()
        self._base_path = Path(base_path or settings.storage_path).resolve()

    async def save(
        self,
        data: bytes,
        key: str,
        content_type: str = "application/octet-stream",  # noqa: ARG002
    ) -> str:
        """保存数据到本地文件系统。

        Args:
            data: 文件二进制数据。
            key: 相对于 base_path 的存储键名。
            content_type: MIME 类型（未使用，保留接口兼容）。

        Returns:
            可访问 URL（/static/{key}）。
        """
        full_path = self._base_path / key
        full_path.parent.mkdir(parents=True, exist_ok=True)

        full_path.write_bytes(data)

        return f"/static/{key}"

    async def delete(self, key: str) -> bool:
        """删除指定键的文件。

        Args:
            key: 存储键名。

        Returns:
            是否删除成功。
        """
        full_path = self._base_path / key
        try:
            full_path.unlink(missing_ok=True)
            return True
        except OSError:
            return False

    async def exists(self, key: str) -> bool:
        """检查键是否存在。

        Args:
            key: 存储键名。

        Returns:
            是否存在。
        """
        full_path = self._base_path / key
        return full_path.is_file()

    def get_url(self, key: str) -> str:
        """获取指定键的可访问 URL。

        Args:
            key: 存储键名。

        Returns:
            可访问 URL（/static/{key}）。
        """
        return f"/static/{key}"

    @staticmethod
    def generate_key(prefix: str, extension: str = "") -> str:
        """生成唯一存储键名。

        Args:
            prefix: 键前缀（如 "images", "videos"）。
            extension: 文件扩展名（不含点）。

        Returns:
            存储键名。
        """
        unique_id = uuid.uuid4().hex
        if extension:
            return f"{prefix}/{unique_id}.{extension}"
        return f"{prefix}/{unique_id}"

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        """计算数据的 SHA-256 哈希。

        Args:
            data: 二进制数据。

        Returns:
            SHA-256 十六进制字符串。
        """
        return hashlib.sha256(data).hexdigest()
