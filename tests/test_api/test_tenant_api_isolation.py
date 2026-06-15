"""
租户 API 隔离测试。

Description:
    验证 products、tasks、dashboard 路由的端点都接受 auth 参数并透传 tenant_id。
@author ganjianfei
@version 1.0.0
2026-06-15
"""

import inspect


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
        # self + product_id + request_data + redis + tenant_id
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
