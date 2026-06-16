"""
本地存储后端测试。
"""

from pathlib import Path

import pytest

from src.storage.local import LocalStorageBackend


class TestLocalStorageBackend:
    """LocalStorageBackend 单元测试。"""

    @pytest.fixture
    def tmp_storage(self, tmp_path: Path) -> LocalStorageBackend:
        """创建指向临时目录的本地存储后端。"""
        return LocalStorageBackend(base_path=str(tmp_path))

    @pytest.mark.asyncio
    async def test_save_and_get_url(self, tmp_storage: LocalStorageBackend) -> None:
        """测试保存数据并获取 URL。"""
        data = b"hello world"
        key = "images/test.png"

        url = await tmp_storage.save(data, key, content_type="image/png")

        assert url == f"/static/{key}"
        assert await tmp_storage.exists(key)

    @pytest.mark.asyncio
    async def test_save_creates_parent_dirs(self, tmp_storage: LocalStorageBackend) -> None:
        """测试自动创建父目录。"""
        data = b"test"
        key = "images/nested/deep/file.txt"

        url = await tmp_storage.save(data, key)

        assert url == f"/static/{key}"
        assert await tmp_storage.exists(key)

    @pytest.mark.asyncio
    async def test_delete_existing(self, tmp_storage: LocalStorageBackend) -> None:
        """测试删除已存在的文件。"""
        key = "images/to_delete.png"
        await tmp_storage.save(b"data", key)

        result = await tmp_storage.delete(key)

        assert result is True
        assert not await tmp_storage.exists(key)

    @pytest.mark.asyncio
    async def test_delete_non_existing(self, tmp_storage: LocalStorageBackend) -> None:
        """测试删除不存在的文件。"""
        result = await tmp_storage.delete("nonexistent/file.png")

        assert result is True  # missing_ok=True

    @pytest.mark.asyncio
    async def test_exists_true(self, tmp_storage: LocalStorageBackend) -> None:
        """测试文件存在。"""
        key = "images/exists.png"
        await tmp_storage.save(b"data", key)

        assert await tmp_storage.exists(key)

    @pytest.mark.asyncio
    async def test_exists_false(self, tmp_storage: LocalStorageBackend) -> None:
        """测试文件不存在。"""
        assert not await tmp_storage.exists("nonexistent/file.png")

    def test_get_url(self, tmp_storage: LocalStorageBackend) -> None:
        """测试获取 URL。"""
        url = tmp_storage.get_url("images/test.png")

        assert url == "/static/images/test.png"

    def test_generate_key_with_extension(self) -> None:
        """测试生成带扩展名的唯一键名。"""
        key = LocalStorageBackend.generate_key("images", "png")

        assert key.startswith("images/")
        assert key.endswith(".png")
        assert len(key) > len("images/") + 4  # 至少 32 位 hex

    def test_generate_key_without_extension(self) -> None:
        """测试生成不带扩展名的唯一键名。"""
        key = LocalStorageBackend.generate_key("videos")

        assert key.startswith("videos/")
        assert "." not in key

    def test_generate_key_is_unique(self) -> None:
        """测试生成的键名唯一。"""
        keys = {LocalStorageBackend.generate_key("images") for _ in range(10)}

        assert len(keys) == 10

    def test_compute_sha256(self) -> None:
        """测试 SHA-256 哈希计算。"""
        import hashlib

        data = b"hello world"
        expected = hashlib.sha256(data).hexdigest()

        assert LocalStorageBackend.compute_sha256(data) == expected
