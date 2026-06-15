"""
租户 API 隔离测试。

Description:
    验证 products、tasks、dashboard 路由的端点都接受 auth 参数并透传 tenant_id，
    以及 scope 授权检查逻辑。
@author ganjianfei
@version 1.0.0
2026-06-15
"""

import inspect

import pytest
from fastapi import HTTPException

from src.auth.context import AuthContext

# ---------------------------------------------------------------------------
# _require_scope helper 单元测试
# ---------------------------------------------------------------------------

class TestRequireScopeHelper:
    """测试 _require_scope 辅助函数的 scope 检查逻辑。"""

    @pytest.fixture
    def read_only_auth(self) -> AuthContext:
        """只读 auth：仅有 products:read 和 tasks:read。"""
        return AuthContext(
            tenant_id="t", user_id="u", scopes=["products:read", "tasks:read"]
        )

    @pytest.fixture
    def write_only_auth(self) -> AuthContext:
        """只写 auth：仅有 products:write 和 tasks:write。"""
        return AuthContext(
            tenant_id="t", user_id="u", scopes=["products:write", "tasks:write"]
        )

    @pytest.fixture
    def wildcard_auth(self) -> AuthContext:
        """通配符 auth：scopes=["*"]。"""
        return AuthContext(tenant_id="t", user_id="u", scopes=["*"])

    @pytest.fixture
    def empty_auth(self) -> AuthContext:
        """无 scope 的 auth。"""
        return AuthContext(tenant_id="t", user_id="u", scopes=[])

    # -- products _require_scope --

    def test_products_write_allows_write_scope(self, write_only_auth: AuthContext) -> None:
        """write scope 应通过 products:write 检查。"""
        from src.api.router.products import _require_scope

        # 不应抛出异常
        _require_scope(write_only_auth, "products:write")

    def test_products_write_rejects_read_only(self, read_only_auth: AuthContext) -> None:
        """read-only scope 不能通过 products:write 检查，应返回 403。"""
        from src.api.router.products import _require_scope

        with pytest.raises(HTTPException) as exc_info:
            _require_scope(read_only_auth, "products:write")
        assert exc_info.value.status_code == 403

    def test_products_read_allows_read_scope(self, read_only_auth: AuthContext) -> None:
        """read scope 应通过 products:read 检查。"""
        from src.api.router.products import _require_scope

        _require_scope(read_only_auth, "products:read", "products:write")

    def test_products_read_allows_write_scope(self, write_only_auth: AuthContext) -> None:
        """write scope 应通过 products:read 检查（write 是 read 的超集）。"""
        from src.api.router.products import _require_scope

        _require_scope(write_only_auth, "products:read", "products:write")

    def test_wildcard_passes_all(self, wildcard_auth: AuthContext) -> None:
        """通配符 scope * 应通过所有检查。"""
        from src.api.router.products import _require_scope

        _require_scope(wildcard_auth, "products:write")
        _require_scope(wildcard_auth, "products:read", "products:write")
        _require_scope(wildcard_auth, "tasks:write")
        _require_scope(wildcard_auth, "tasks:read", "tasks:write")

    def test_empty_scopes_rejected(self, empty_auth: AuthContext) -> None:
        """空 scope 应被拒绝。"""
        from src.api.router.products import _require_scope

        with pytest.raises(HTTPException) as exc_info:
            _require_scope(empty_auth, "products:write")
        assert exc_info.value.status_code == 403

    # -- tasks _require_scope --

    def test_tasks_write_allows_write_scope(self, write_only_auth: AuthContext) -> None:
        """write scope 应通过 tasks:write 检查。"""
        from src.api.router.tasks import _require_scope

        _require_scope(write_only_auth, "tasks:write")

    def test_tasks_write_rejects_read_only(self, read_only_auth: AuthContext) -> None:
        """read-only scope 不能通过 tasks:write 检查。"""
        from src.api.router.tasks import _require_scope

        with pytest.raises(HTTPException) as exc_info:
            _require_scope(read_only_auth, "tasks:write")
        assert exc_info.value.status_code == 403

    def test_tasks_read_allows_read_scope(self, read_only_auth: AuthContext) -> None:
        """read scope 应通过 tasks:read 检查。"""
        from src.api.router.tasks import _require_scope

        _require_scope(read_only_auth, "tasks:read", "tasks:write")

    def test_tasks_read_allows_write_scope(self, write_only_auth: AuthContext) -> None:
        """write scope 应通过 tasks:read 检查。"""
        from src.api.router.tasks import _require_scope

        _require_scope(write_only_auth, "tasks:read", "tasks:write")


# ---------------------------------------------------------------------------
# Endpoint scope 调用结构验证（通过 inspect.getsource 断言）
# ---------------------------------------------------------------------------

class TestEndpointScopeCalls:
    """验证每个 endpoint 的源码中包含正确的 _require_scope 调用。"""

    # -- products endpoints --

    def test_create_product_calls_require_scope_write(self) -> None:
        """create_product 应调用 _require_scope(auth, "products:write")。"""
        from src.api.router.products import create_product

        source = inspect.getsource(create_product)
        assert '_require_scope(auth, "products:write")' in source or \
            "_require_scope(auth, 'products:write')" in source, (
            f"create_product 未调用 _require_scope(auth, 'products:write')\nsource:\n{source}"
        )

    def test_list_products_calls_require_scope_read(self) -> None:
        """list_products 应调用 _require_scope(auth, "products:read", "products:write")。"""
        from src.api.router.products import list_products

        source = inspect.getsource(list_products)
        assert "products:read" in source, (
            f"list_products 源码中未找到 products:read\nsource:\n{source}"
        )
        assert "products:write" in source, (
            f"list_products 源码中未找到 products:write\nsource:\n{source}"
        )
        assert "_require_scope" in source, (
            f"list_products 未调用 _require_scope\nsource:\n{source}"
        )

    def test_get_product_calls_require_scope_read(self) -> None:
        """get_product 应调用 _require_scope(auth, "products:read", "products:write")。"""
        from src.api.router.products import get_product

        source = inspect.getsource(get_product)
        assert "products:read" in source
        assert "products:write" in source
        assert "_require_scope" in source

    def test_update_product_calls_require_scope_write(self) -> None:
        """update_product 应调用 _require_scope(auth, "products:write")。"""
        from src.api.router.products import update_product

        source = inspect.getsource(update_product)
        assert '_require_scope(auth, "products:write")' in source or \
            "_require_scope(auth, 'products:write')" in source

    def test_delete_product_calls_require_scope_write(self) -> None:
        """delete_product 应调用 _require_scope(auth, "products:write")。"""
        from src.api.router.products import delete_product

        source = inspect.getsource(delete_product)
        assert '_require_scope(auth, "products:write")' in source or \
            "_require_scope(auth, 'products:write')" in source

    def test_upload_product_image_calls_require_scope_write(self) -> None:
        """upload_product_image 应调用 _require_scope(auth, "products:write")。"""
        from src.api.router.products import upload_product_image

        source = inspect.getsource(upload_product_image)
        assert '_require_scope(auth, "products:write")' in source or \
            "_require_scope(auth, 'products:write')" in source

    # -- tasks endpoints --

    def test_create_task_calls_require_scope_write(self) -> None:
        """create_task 应调用 _require_scope(auth, "tasks:write")。"""
        from src.api.router.tasks import create_task

        source = inspect.getsource(create_task)
        assert '_require_scope(auth, "tasks:write")' in source or \
            "_require_scope(auth, 'tasks:write')" in source, (
            f"create_task 未调用 _require_scope(auth, 'tasks:write')\nsource:\n{source}"
        )

    def test_list_tasks_calls_require_scope_read(self) -> None:
        """list_tasks 应调用 _require_scope(auth, "tasks:read", "tasks:write")。"""
        from src.api.router.tasks import list_tasks

        source = inspect.getsource(list_tasks)
        assert "tasks:read" in source
        assert "tasks:write" in source
        assert "_require_scope" in source

    def test_get_task_detail_calls_require_scope_read(self) -> None:
        """get_task_detail 应调用 _require_scope(auth, "tasks:read", "tasks:write")。"""
        from src.api.router.tasks import get_task_detail

        source = inspect.getsource(get_task_detail)
        assert "tasks:read" in source
        assert "tasks:write" in source
        assert "_require_scope" in source

    def test_get_task_status_calls_require_scope_read(self) -> None:
        """get_task_status 应调用 _require_scope(auth, "tasks:read", "tasks:write")。"""
        from src.api.router.tasks import get_task_status

        source = inspect.getsource(get_task_status)
        assert "tasks:read" in source
        assert "tasks:write" in source
        assert "_require_scope" in source

    def test_cancel_task_calls_require_scope_write(self) -> None:
        """cancel_task 应调用 _require_scope(auth, "tasks:write")。"""
        from src.api.router.tasks import cancel_task

        source = inspect.getsource(cancel_task)
        assert '_require_scope(auth, "tasks:write")' in source or \
            "_require_scope(auth, 'tasks:write')" in source

    def test_delete_task_calls_require_scope_write(self) -> None:
        """delete_task 应调用 _require_scope(auth, "tasks:write")。"""
        from src.api.router.tasks import delete_task

        source = inspect.getsource(delete_task)
        assert '_require_scope(auth, "tasks:write")' in source or \
            "_require_scope(auth, 'tasks:write')" in source

    def test_task_websocket_calls_require_scope_read(self) -> None:
        """task_websocket 应调用 _require_scope(auth, "tasks:read", "tasks:write")。"""
        from src.api.router.tasks import task_websocket

        source = inspect.getsource(task_websocket)
        assert "tasks:read" in source, (
            f"task_websocket 源码中未找到 tasks:read\nsource:\n{source}"
        )
        assert "tasks:write" in source
        assert "_require_scope" in source


# ---------------------------------------------------------------------------
# Auth 参数签名验证（保留原有测试）
# ---------------------------------------------------------------------------

class TestTenantApiIsolation:
    """验证关键 API 端点签名包含 auth 参数。"""

    def test_create_product_has_auth_param(self) -> None:
        """测试 products.create_product 签名包含 auth 参数。"""
        from src.api.router.products import create_product

        sig = inspect.signature(create_product)
        params = list(sig.parameters.keys())
        assert "auth" in params, f"create_product 缺少 auth 参数，当前参数: {params}"

    def test_list_products_has_auth_param(self) -> None:
        """测试 products.list_products 签名包含 auth 参数。"""
        from src.api.router.products import list_products

        sig = inspect.signature(list_products)
        params = list(sig.parameters.keys())
        assert "auth" in params, f"list_products 缺少 auth 参数，当前参数: {params}"

    def test_get_product_has_auth_param(self) -> None:
        """测试 products.get_product 签名包含 auth 参数。"""
        from src.api.router.products import get_product

        sig = inspect.signature(get_product)
        params = list(sig.parameters.keys())
        assert "auth" in params, f"get_product 缺少 auth 参数，当前参数: {params}"

    def test_update_product_has_auth_param(self) -> None:
        """测试 products.update_product 签名包含 auth 参数。"""
        from src.api.router.products import update_product

        sig = inspect.signature(update_product)
        params = list(sig.parameters.keys())
        assert "auth" in params, f"update_product 缺少 auth 参数，当前参数: {params}"

    def test_delete_product_has_auth_param(self) -> None:
        """测试 products.delete_product 签名包含 auth 参数。"""
        from src.api.router.products import delete_product

        sig = inspect.signature(delete_product)
        params = list(sig.parameters.keys())
        assert "auth" in params, f"delete_product 缺少 auth 参数，当前参数: {params}"

    def test_upload_product_image_has_auth_param(self) -> None:
        """测试 products.upload_product_image 签名包含 auth 参数。"""
        from src.api.router.products import upload_product_image

        sig = inspect.signature(upload_product_image)
        params = list(sig.parameters.keys())
        assert "auth" in params, f"upload_product_image 缺少 auth 参数，当前参数: {params}"

    def test_create_task_has_auth_param(self) -> None:
        """测试 tasks.create_task 签名包含 auth 参数。"""
        from src.api.router.tasks import create_task

        sig = inspect.signature(create_task)
        params = list(sig.parameters.keys())
        assert "auth" in params, f"create_task 缺少 auth 参数，当前参数: {params}"

    def test_list_tasks_has_auth_param(self) -> None:
        """测试 tasks.list_tasks 签名包含 auth 参数。"""
        from src.api.router.tasks import list_tasks

        sig = inspect.signature(list_tasks)
        params = list(sig.parameters.keys())
        assert "auth" in params, f"list_tasks 缺少 auth 参数，当前参数: {params}"

    def test_get_task_detail_has_auth_param(self) -> None:
        """测试 tasks.get_task_detail 签名包含 auth 参数。"""
        from src.api.router.tasks import get_task_detail

        sig = inspect.signature(get_task_detail)
        params = list(sig.parameters.keys())
        assert "auth" in params, f"get_task_detail 缺少 auth 参数，当前参数: {params}"

    def test_get_task_status_has_auth_param(self) -> None:
        """测试 tasks.get_task_status 签名包含 auth 参数。"""
        from src.api.router.tasks import get_task_status

        sig = inspect.signature(get_task_status)
        params = list(sig.parameters.keys())
        assert "auth" in params, f"get_task_status 缺少 auth 参数，当前参数: {params}"

    def test_cancel_task_has_auth_param(self) -> None:
        """测试 tasks.cancel_task 签名包含 auth 参数。"""
        from src.api.router.tasks import cancel_task

        sig = inspect.signature(cancel_task)
        params = list(sig.parameters.keys())
        assert "auth" in params, f"cancel_task 缺少 auth 参数，当前参数: {params}"

    def test_delete_task_has_auth_param(self) -> None:
        """测试 tasks.delete_task 签名包含 auth 参数。"""
        from src.api.router.tasks import delete_task

        sig = inspect.signature(delete_task)
        params = list(sig.parameters.keys())
        assert "auth" in params, f"delete_task 缺少 auth 参数，当前参数: {params}"

    def test_get_dashboard_stats_has_auth_param(self) -> None:
        """测试 dashboard.get_dashboard_stats 签名包含 auth 参数。"""
        from src.api.router.dashboard import get_dashboard_stats

        sig = inspect.signature(get_dashboard_stats)
        params = list(sig.parameters.keys())
        assert "auth" in params, f"get_dashboard_stats 缺少 auth 参数，当前参数: {params}"


class TestTaskManagerTenant:
    """验证 TaskManager 方法签名包含 tenant_id 参数。"""

    def test_create_task_has_tenant_id_param(self) -> None:
        """测试 TaskManager.create_task 签名包含 tenant_id 参数。"""
        from src.api.service.task_manager import TaskManager

        sig = inspect.signature(TaskManager.create_task)
        params = list(sig.parameters.keys())
        assert "tenant_id" in params, f"TaskManager.create_task 缺少 tenant_id 参数，当前参数: {params}"

    def test_get_task_status_has_tenant_id_param(self) -> None:
        """测试 TaskManager.get_task_status 签名包含 tenant_id 参数。"""
        from src.api.service.task_manager import TaskManager

        sig = inspect.signature(TaskManager.get_task_status)
        params = list(sig.parameters.keys())
        assert "tenant_id" in params, (
            f"TaskManager.get_task_status 缺少 tenant_id 参数，当前参数: {params}"
        )

    def test_get_task_detail_has_tenant_id_param(self) -> None:
        """测试 TaskManager.get_task_detail 签名包含 tenant_id 参数。"""
        from src.api.service.task_manager import TaskManager

        sig = inspect.signature(TaskManager.get_task_detail)
        params = list(sig.parameters.keys())
        assert "tenant_id" in params, (
            f"TaskManager.get_task_detail 缺少 tenant_id 参数，当前参数: {params}"
        )

    def test_cancel_task_has_tenant_id_param(self) -> None:
        """测试 TaskManager.cancel_task 签名包含 tenant_id 参数。"""
        from src.api.service.task_manager import TaskManager

        sig = inspect.signature(TaskManager.cancel_task)
        params = list(sig.parameters.keys())
        assert "tenant_id" in params, (
            f"TaskManager.cancel_task 缺少 tenant_id 参数，当前参数: {params}"
        )

    def test_list_tasks_has_tenant_id_param(self) -> None:
        """测试 TaskManager.list_tasks 签名包含 tenant_id 参数。"""
        from src.api.service.task_manager import TaskManager

        sig = inspect.signature(TaskManager.list_tasks)
        params = list(sig.parameters.keys())
        assert "tenant_id" in params, (
            f"TaskManager.list_tasks 缺少 tenant_id 参数，当前参数: {params}"
        )
