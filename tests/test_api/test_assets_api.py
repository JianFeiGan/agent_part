"""
资产查询与删除 API 测试。

Description:
    测试资产列表、单个查询和删除接口。
    使用 mock.patch 模拟 AssetRepository 和 get_storage_backend 来验证路由逻辑。
@author ganjianfei
@version 1.0.0
2026-06-19
"""

import asyncio
import inspect
from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import UTC, datetime
from typing import Any
from unittest import mock

import pytest
from fastapi import HTTPException

from src.auth.context import AuthContext

# ---------------------------------------------------------------------------
# Fake assets for testing
# ---------------------------------------------------------------------------


@dataclass
class FakeAsset:
    """模拟资产记录。"""

    id: int
    tenant_id: str
    product_id: str | None = None
    task_id: str | None = None
    asset_type: str = "image"
    provider: str = "wanx"
    url: str = "/static/images/test.png"
    storage_key: str = "images/test.png"
    storage_backend: str = "local"
    mime_type: str | None = "image/png"
    file_size: int | None = 204800
    width: int | None = 1024
    height: int | None = 1024
    duration: float | None = None
    is_mock: bool = False
    status: str = "completed"
    created_at: datetime = dc_field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Fake StorageBackend
# ---------------------------------------------------------------------------


class FakeStorage:
    """模拟存储后端，追踪 delete 调用。"""

    def __init__(self) -> None:
        self.deleted_keys: list[str] = []

    async def save(
        self, data: bytes, key: str, content_type: str = "application/octet-stream"  # noqa: ARG002
    ) -> str:
        return f"/static/{key}"

    async def delete(self, key: str) -> bool:
        self.deleted_keys.append(key)
        return True

    async def exists(self, key: str) -> bool:
        return key in self.deleted_keys

    def get_url(self, key: str) -> str:
        return f"/static/{key}"


# ---------------------------------------------------------------------------
# Fake AssetRepository (mimics real AssetRepository API with in-memory data)
# ---------------------------------------------------------------------------


class FakeAssetRepository:
    """模拟 AssetRepository，提供租户隔离的查询和删除。"""

    def __init__(self, assets: list[FakeAsset]) -> None:
        self._assets: dict[int, FakeAsset] = {a.id: a for a in assets}
        self._deleted_ids: set[int] = set()

    async def get_for_tenant(self, id: int, tenant_id: str) -> FakeAsset | None:
        a = self._assets.get(id)
        if a is None or a.tenant_id != tenant_id or a.id in self._deleted_ids:
            return None
        return a

    async def list_by_product(
        self, tenant_id: str, product_id: str, limit: int = 50
    ) -> list[FakeAsset]:
        return [
            a
            for a in self._assets.values()
            if a.tenant_id == tenant_id
            and a.product_id == product_id
            and a.id not in self._deleted_ids
        ][:limit]

    async def list_by_task(
        self, tenant_id: str, task_id: str
    ) -> list[FakeAsset]:
        return [
            a
            for a in self._assets.values()
            if a.tenant_id == tenant_id
            and a.task_id == task_id
            and a.id not in self._deleted_ids
        ]

    async def list_for_tenant(
        self, tenant_id: str, **filters: Any
    ) -> list[FakeAsset]:
        result = [
            a
            for a in self._assets.values()
            if a.tenant_id == tenant_id and a.id not in self._deleted_ids
        ]
        for filter_field, filter_value in filters.items():
            result = [a for a in result if getattr(a, filter_field, None) == filter_value]
        return result

    def delete_sync(self, asset: FakeAsset) -> None:
        self._deleted_ids.add(asset.id)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tenant_a_assets() -> list[FakeAsset]:
    """租户 A 的资产列表。"""
    return [
        FakeAsset(id=1, tenant_id="tenant-a", product_id="prod_001", asset_type="image"),
        FakeAsset(id=2, tenant_id="tenant-a", product_id="prod_001", asset_type="video", duration=30.0),
        FakeAsset(id=3, tenant_id="tenant-a", task_id="task_001", asset_type="image"),
    ]


@pytest.fixture
def tenant_b_assets() -> list[FakeAsset]:
    """租户 B 的资产列表。"""
    return [
        FakeAsset(id=10, tenant_id="tenant-b", product_id="prod_002", asset_type="image"),
    ]


@pytest.fixture
def all_assets(tenant_a_assets: list[FakeAsset], tenant_b_assets: list[FakeAsset]) -> list[FakeAsset]:
    """所有租户的资产。"""
    return tenant_a_assets + tenant_b_assets


@pytest.fixture
def repo(all_assets: list[FakeAsset]) -> FakeAssetRepository:
    """创建 FakeAssetRepository。"""
    return FakeAssetRepository(all_assets)


@pytest.fixture
def storage() -> FakeStorage:
    """创建 FakeStorage。"""
    return FakeStorage()


@pytest.fixture
def auth_a() -> AuthContext:
    """租户 A 的认证上下文，拥有 assets:* scope。"""
    return AuthContext(tenant_id="tenant-a", user_id="user-a", scopes=["assets:read", "assets:write"])


@pytest.fixture
def auth_b() -> AuthContext:
    """租户 B 的认证上下文，拥有 assets:* scope。"""
    return AuthContext(tenant_id="tenant-b", user_id="user-b", scopes=["assets:read", "assets:write"])


@pytest.fixture
def auth_readonly() -> AuthContext:
    """只读 assets scope。"""
    return AuthContext(tenant_id="tenant-a", user_id="user-ro", scopes=["assets:read"])


@pytest.fixture
def auth_no_scope() -> AuthContext:
    """无 assets scope。"""
    return AuthContext(tenant_id="tenant-a", user_id="user-none", scopes=[])


# ---------------------------------------------------------------------------
# Context managers for patching
# ---------------------------------------------------------------------------


def _patches(repo: FakeAssetRepository, storage: FakeStorage | None = None):
    """返回 mock.patch 上下文管理器列表。

    同时 mock get_db（返回一个能产生 FakeDBSession 的上下文管理器）
    和 AssetRepository 构造函数。
    """
    patches = []

    # Mock AssetRepository 构造函数，让它返回我们的 FakeAssetRepository
    patches.append(
        mock.patch(
            "src.api.router.assets.AssetRepository",
            return_value=repo,
        )
    )

    # Mock get_db 使其返回一个假的 async context manager
    class _FakeDB:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def delete(self, asset):
            repo.delete_sync(asset)

        async def flush(self):
            pass

    fake_db = _FakeDB()

    def _fake_get_db():
        return fake_db

    patches.append(
        mock.patch("src.api.router.assets.get_db", side_effect=_fake_get_db)
    )

    # Mock storage backend if provided
    if storage is not None:
        patches.append(
            mock.patch(
                "src.api.router.assets.get_storage_backend",
                return_value=storage,
            )
        )

    return patches


# ---------------------------------------------------------------------------
# Tests: list_assets
# ---------------------------------------------------------------------------


class TestListAssets:
    """测试资产列表接口。"""

    def test_list_assets_returns_only_current_tenant(
        self, repo: FakeAssetRepository, auth_a: AuthContext
    ) -> None:
        """列出资产应只返回当前租户的数据。"""
        from src.api.router.assets import list_assets

        async def _run() -> None:
            with _patches(repo)[0], _patches(repo)[1]:
                result = await list_assets(
                    auth=auth_a,
                    product_id=None,
                    task_id=None,
                    asset_type=None,
                    limit=20,
                )
            assert result.code == 200
            assert result.data is not None
            assert len(result.data) == 3
            ids = {item.asset_id for item in result.data}
            assert ids == {1, 2, 3}

        asyncio.run(_run())

    def test_list_assets_filters_by_product_id(
        self, repo: FakeAssetRepository, auth_a: AuthContext
    ) -> None:
        """按 product_id 过滤资产列表。"""
        from src.api.router.assets import list_assets

        async def _run() -> None:
            with _patches(repo)[0], _patches(repo)[1]:
                result = await list_assets(
                    auth=auth_a,
                    product_id="prod_001",
                    task_id=None,
                    asset_type=None,
                    limit=20,
                )
            assert result.code == 200
            assert result.data is not None
            assert len(result.data) == 2
            for item in result.data:
                assert item.product_id == "prod_001"

        asyncio.run(_run())

    def test_list_assets_filters_by_task_id(
        self, repo: FakeAssetRepository, auth_a: AuthContext
    ) -> None:
        """按 task_id 过滤资产列表。"""
        from src.api.router.assets import list_assets

        async def _run() -> None:
            with _patches(repo)[0], _patches(repo)[1]:
                result = await list_assets(
                    auth=auth_a,
                    product_id=None,
                    task_id="task_001",
                    asset_type=None,
                    limit=20,
                )
            assert result.code == 200
            assert result.data is not None
            assert len(result.data) == 1
            assert result.data[0].asset_id == 3
            assert result.data[0].task_id == "task_001"

        asyncio.run(_run())

    def test_list_assets_filters_by_asset_type(
        self, repo: FakeAssetRepository, auth_a: AuthContext
    ) -> None:
        """按 asset_type 过滤资产列表。"""
        from src.api.router.assets import list_assets

        async def _run() -> None:
            with _patches(repo)[0], _patches(repo)[1]:
                result = await list_assets(
                    auth=auth_a,
                    product_id=None,
                    task_id=None,
                    asset_type="video",
                    limit=20,
                )
            assert result.code == 200
            assert result.data is not None
            assert len(result.data) == 1
            assert result.data[0].asset_type == "video"
            assert result.data[0].duration == 30.0

        asyncio.run(_run())

    def test_list_requires_assets_read_or_write_scope(
        self, auth_no_scope: AuthContext
    ) -> None:
        """list_assets 应拒绝无 scope 的请求。"""
        from src.api.router.assets import list_assets

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await list_assets(
                    auth=auth_no_scope,
                    product_id=None,
                    task_id=None,
                    asset_type=None,
                    limit=20,
                )
            assert exc_info.value.status_code == 403

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Tests: get_asset
# ---------------------------------------------------------------------------


class TestGetAsset:
    """测试单个资产获取接口。"""

    def test_get_asset_returns_404_for_other_tenant(
        self, repo: FakeAssetRepository, auth_a: AuthContext
    ) -> None:
        """跨租户获取资产应返回 404。"""
        from src.api.router.assets import get_asset

        async def _run() -> None:
            p0, p1 = _patches(repo)[0], _patches(repo)[1]
            with p0, p1, pytest.raises(HTTPException) as exc_info:
                await get_asset(asset_id=10, auth=auth_a)
            assert exc_info.value.status_code == 404

        asyncio.run(_run())

    def test_get_asset_returns_404_for_missing(
        self, repo: FakeAssetRepository, auth_a: AuthContext
    ) -> None:
        """获取不存在的资产应返回 404。"""
        from src.api.router.assets import get_asset

        async def _run() -> None:
            p0, p1 = _patches(repo)[0], _patches(repo)[1]
            with p0, p1, pytest.raises(HTTPException) as exc_info:
                await get_asset(asset_id=999, auth=auth_a)
            assert exc_info.value.status_code == 404

        asyncio.run(_run())

    def test_get_asset_requires_scope(
        self, repo: FakeAssetRepository, auth_no_scope: AuthContext
    ) -> None:
        """获取资产应拒绝无 scope 的请求。"""
        from src.api.router.assets import get_asset

        async def _run() -> None:
            p0, p1 = _patches(repo)[0], _patches(repo)[1]
            with p0, p1, pytest.raises(HTTPException) as exc_info:
                await get_asset(asset_id=1, auth=auth_no_scope)
            assert exc_info.value.status_code == 403

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Tests: delete_asset
# ---------------------------------------------------------------------------


class TestDeleteAsset:
    """测试资产删除接口。"""

    def test_delete_asset_removes_storage_and_db(
        self,
        repo: FakeAssetRepository,
        storage: FakeStorage,
        auth_a: AuthContext,
    ) -> None:
        """删除资产应同时清理存储和数据库记录。"""
        from src.api.router.assets import delete_asset

        async def _run() -> None:
            patches = _patches(repo, storage=storage)
            with patches[0], patches[1], patches[2]:
                result = await delete_asset(asset_id=1, auth=auth_a)
            assert result.code == 200
            assert result.message == "删除成功"
            # 验证 DB 删除
            assert 1 in repo._deleted_ids
            # 验证存储删除
            assert "images/test.png" in storage.deleted_keys

        asyncio.run(_run())

    def test_delete_asset_returns_404_for_other_tenant(
        self,
        repo: FakeAssetRepository,
        storage: FakeStorage,
        auth_a: AuthContext,
    ) -> None:
        """跨租户删除资产应返回 404。"""
        from src.api.router.assets import delete_asset

        async def _run() -> None:
            patches = _patches(repo, storage=storage)
            with patches[0], patches[1], patches[2], pytest.raises(HTTPException) as exc_info:
                await delete_asset(asset_id=10, auth=auth_a)
            assert exc_info.value.status_code == 404
            # 确保没有误删除
            assert 10 not in repo._deleted_ids
            assert len(storage.deleted_keys) == 0

        asyncio.run(_run())

    def test_delete_asset_returns_404_for_missing(
        self,
        repo: FakeAssetRepository,
        storage: FakeStorage,
        auth_a: AuthContext,
    ) -> None:
        """删除不存在的资产应返回 404。"""
        from src.api.router.assets import delete_asset

        async def _run() -> None:
            patches = _patches(repo, storage=storage)
            with patches[0], patches[1], patches[2], pytest.raises(HTTPException) as exc_info:
                await delete_asset(asset_id=999, auth=auth_a)
            assert exc_info.value.status_code == 404

        asyncio.run(_run())

    def test_delete_requires_assets_write_scope(
        self,
        repo: FakeAssetRepository,
        storage: FakeStorage,
        auth_readonly: AuthContext,
    ) -> None:
        """删除资产应拒绝只有 read scope 的请求。"""
        from src.api.router.assets import delete_asset

        async def _run() -> None:
            patches = _patches(repo, storage=storage)
            with patches[0], patches[1], patches[2], pytest.raises(HTTPException) as exc_info:
                await delete_asset(asset_id=1, auth=auth_readonly)
            assert exc_info.value.status_code == 403

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Tests: scope enforcement (inspect)
# ---------------------------------------------------------------------------


class TestAssetScopeCalls:
    """验证每个 asset endpoint 源码中包含正确的 _require_scope 调用。"""

    def test_list_assets_calls_require_scope_read(self) -> None:
        """list_assets 应调用 _require_scope(auth, 'assets:read', 'assets:write')。"""
        from src.api.router.assets import list_assets

        source = inspect.getsource(list_assets)
        assert "assets:read" in source, (
            f"list_assets 源码中未找到 assets:read\nsource:\n{source}"
        )
        assert "assets:write" in source, (
            f"list_assets 源码中未找到 assets:write\nsource:\n{source}"
        )
        assert "_require_scope" in source, (
            f"list_assets 未调用 _require_scope\nsource:\n{source}"
        )

    def test_get_asset_calls_require_scope_read(self) -> None:
        """get_asset 应调用 _require_scope(auth, 'assets:read', 'assets:write')。"""
        from src.api.router.assets import get_asset

        source = inspect.getsource(get_asset)
        assert "assets:read" in source
        assert "assets:write" in source
        assert "_require_scope" in source

    def test_delete_asset_calls_require_scope_write(self) -> None:
        """delete_asset 应调用 _require_scope(auth, 'assets:write')。"""
        from src.api.router.assets import delete_asset

        source = inspect.getsource(delete_asset)
        assert '_require_scope(auth, "assets:write")' in source or \
            "_require_scope(auth, 'assets:write')" in source, (
            f"delete_asset 未调用 _require_scope(auth, 'assets:write')\nsource:\n{source}"
        )


# ---------------------------------------------------------------------------
# Tests: _require_scope helper (unit tests)
# ---------------------------------------------------------------------------


class TestRequireScopeHelper:
    """测试 assets.py 中的 _require_scope 辅助函数。"""

    @pytest.fixture
    def read_only_auth(self) -> AuthContext:
        return AuthContext(tenant_id="t", user_id="u", scopes=["assets:read"])

    @pytest.fixture
    def write_only_auth(self) -> AuthContext:
        return AuthContext(tenant_id="t", user_id="u", scopes=["assets:write"])

    @pytest.fixture
    def wildcard_auth(self) -> AuthContext:
        return AuthContext(tenant_id="t", user_id="u", scopes=["*"])

    @pytest.fixture
    def empty_auth(self) -> AuthContext:
        return AuthContext(tenant_id="t", user_id="u", scopes=[])

    def test_assets_write_allows_write_scope(self, write_only_auth: AuthContext) -> None:
        from src.api.router.assets import _require_scope

        _require_scope(write_only_auth, "assets:write")

    def test_assets_write_rejects_read_only(self, read_only_auth: AuthContext) -> None:
        from src.api.router.assets import _require_scope

        with pytest.raises(HTTPException) as exc_info:
            _require_scope(read_only_auth, "assets:write")
        assert exc_info.value.status_code == 403

    def test_assets_read_allows_read_scope(self, read_only_auth: AuthContext) -> None:
        from src.api.router.assets import _require_scope

        _require_scope(read_only_auth, "assets:read", "assets:write")

    def test_assets_read_allows_write_scope(self, write_only_auth: AuthContext) -> None:
        from src.api.router.assets import _require_scope

        _require_scope(write_only_auth, "assets:read", "assets:write")

    def test_wildcard_passes_all(self, wildcard_auth: AuthContext) -> None:
        from src.api.router.assets import _require_scope

        _require_scope(wildcard_auth, "assets:write")
        _require_scope(wildcard_auth, "assets:read", "assets:write")

    def test_empty_scopes_rejected(self, empty_auth: AuthContext) -> None:
        from src.api.router.assets import _require_scope

        with pytest.raises(HTTPException) as exc_info:
            _require_scope(empty_auth, "assets:write")
        assert exc_info.value.status_code == 403
