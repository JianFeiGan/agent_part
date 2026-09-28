"""商品与任务路由 CRUD 行为测试。

直接调用 handler + Redis 替身，覆盖创建/列表/详情/更新/删除、
404 分支与 scope 校验。不接真实 Redis。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.api.router.products import (
    create_product,
    delete_product,
    get_product,
    list_products,
    update_product,
)
from src.api.router.tasks import (
    cancel_task as cancel_task_handler,
)
from src.api.router.tasks import (
    create_task as create_task_handler,
)
from src.api.router.tasks import (
    delete_task as delete_task_handler,
)
from src.api.router.tasks import (
    get_task_detail as get_task_detail_handler,
)
from src.api.router.tasks import (
    get_task_status as get_task_status_handler,
)
from src.api.router.tasks import (
    list_tasks as list_tasks_handler,
)
from src.api.schema.product import (
    ProductCreateRequest,
    ProductListQuery,
    ProductUpdateRequest,
)
from src.api.schema.task import TaskCreateRequest, TaskListQuery
from src.auth.context import AuthContext
from src.models.product import Product, ProductCategory

# --------------------------------------------------------------------------- #
# 夹具
# --------------------------------------------------------------------------- #


@pytest.fixture
def auth() -> AuthContext:
    """带读写 scope 的租户 A 上下文。"""
    return AuthContext(
        tenant_id="tenant-a",
        user_id="user-a",
        scopes=["products:read", "products:write", "tasks:read", "tasks:write"],
    )


def _product(**kwargs: Any) -> Product:
    """构造商品。"""
    defaults: dict[str, Any] = {
        "product_id": "prod_001",
        "name": "测试商品名称",
        "category": ProductCategory.DIGITAL,
        "description": "这是一个用于测试的商品描述信息",
    }
    defaults.update(kwargs)
    return Product(**defaults)


def _redis(**kwargs: Any) -> AsyncMock:
    """构造 Redis 替身。"""
    redis = AsyncMock()
    redis.save_product = AsyncMock()
    redis.get_product = AsyncMock(return_value=kwargs.get("product", _product()))
    redis.list_products = AsyncMock(return_value=kwargs.get("list_result", ([], 0)))
    redis.update_product = AsyncMock(return_value=True)
    redis.delete_product = AsyncMock(return_value=kwargs.get("delete_ok", True))
    redis.get_task_metadata = AsyncMock(return_value=kwargs.get("task_meta"))
    redis.delete_task = AsyncMock(return_value=kwargs.get("delete_task_ok", True))
    return redis


class _TaskManager:
    """任务管理器替身。"""

    def __init__(self) -> None:
        self.create_task = AsyncMock(return_value="task_x")
        self.list_tasks = AsyncMock(return_value=([], 0))
        self.get_task_detail = AsyncMock(return_value={})
        self.get_task_status = AsyncMock(return_value={})
        self.cancel_task = AsyncMock(return_value=True)


class TestProductCreate:
    """创建商品。"""

    async def test_create_persists_to_tenant_scope(self, auth: AuthContext) -> None:
        """创建的商品写入当前租户。"""
        redis = _redis()
        request = ProductCreateRequest(
            name="商品A",
            category=ProductCategory.DIGITAL,
            description="足够长的商品描述文本用于通过校验",
        )

        resp = await create_product(request, redis, auth)

        assert resp.code == 200
        assert resp.data.product_id.startswith("prod_")
        redis.save_product.assert_awaited_once()
        assert redis.save_product.call_args.kwargs["tenant_id"] == "tenant-a"


class TestProductList:
    """商品列表。"""

    async def test_list_passes_pagination_and_category(self, auth: AuthContext) -> None:
        """分页与类目过滤透传到 Redis。"""
        redis = _redis(list_result=([_product()], 1))
        query = ProductListQuery(page=2, page_size=5, category=ProductCategory.DIGITAL)

        resp = await list_products(redis, auth, query)

        assert resp.data.total == 1
        assert resp.data.page == 2
        redis.list_products.assert_awaited_once_with(
            tenant_id="tenant-a", page=2, page_size=5, category="digital"
        )

    async def test_list_empty(self, auth: AuthContext) -> None:
        """空列表返回 total=0。"""
        redis = _redis()
        resp = await list_products(redis, auth, ProductListQuery())

        assert resp.data.items == []
        assert resp.data.total == 0


class TestProductDetailAndUpdate:
    """详情与更新。"""

    async def test_get_missing_returns_404(self, auth: AuthContext) -> None:
        """跨租户/不存在统一 404。"""
        redis = _redis(product=None)

        with pytest.raises(HTTPException) as exc:
            await get_product("prod_x", redis, auth)

        assert exc.value.status_code == 404

    async def test_get_hit(self, auth: AuthContext) -> None:
        """命中返回商品详情。"""
        redis = _redis(product=_product())
        resp = await get_product("prod_001", redis, auth)

        assert resp.data.name == "测试商品名称"

    async def test_update_missing_returns_404(self, auth: AuthContext) -> None:
        """更新不存在的商品返回 404。"""
        redis = _redis(product=None)

        with pytest.raises(HTTPException) as exc:
            await update_product("prod_x", ProductUpdateRequest(name="xy"), redis, auth)

        assert exc.value.status_code == 404

    async def test_update_applies_only_set_fields(self, auth: AuthContext) -> None:
        """只覆盖显式传入的字段。"""
        product = _product()
        redis = _redis(product=product)

        resp = await update_product("prod_001", ProductUpdateRequest(name="新名字"), redis, auth)

        assert resp.data.name == "新名字"
        assert resp.data.description == "这是一个用于测试的商品描述信息"
        redis.update_product.assert_awaited_once()


class TestProductDelete:
    """删除商品。"""

    async def test_delete_missing_returns_404(self, auth: AuthContext) -> None:
        """删除不存在的商品返回 404。"""
        redis = _redis(delete_ok=False)

        with pytest.raises(HTTPException) as exc:
            await delete_product("prod_x", redis, auth)

        assert exc.value.status_code == 404

    async def test_delete_success(self, auth: AuthContext) -> None:
        """删除成功返回 200。"""
        redis = _redis(delete_ok=True)
        resp = await delete_product("prod_001", redis, auth)

        assert resp.code == 200


class TestTaskRoutes:
    """任务路由。"""

    async def test_create_task_product_missing(self, auth: AuthContext) -> None:
        """商品不存在时 404。"""
        redis = _redis(product=None)
        manager = _TaskManager()

        with pytest.raises(HTTPException) as exc:
            await create_task_handler(TaskCreateRequest(product_id="prod_x"), redis, auth, manager)

        assert exc.value.status_code == 404
        manager.create_task.assert_not_awaited()

    async def test_create_task_success(self, auth: AuthContext) -> None:
        """创建成功返回任务 ID。"""
        redis = _redis()
        manager = _TaskManager()

        resp = await create_task_handler(
            TaskCreateRequest(product_id="prod_001"), redis, auth, manager
        )

        assert resp.data["task_id"] == "task_x"
        manager.create_task.assert_awaited_once()
        assert manager.create_task.call_args.kwargs["tenant_id"] == "tenant-a"

    async def test_list_tasks(self, auth: AuthContext) -> None:
        """列表返回分页结构。"""
        manager = _TaskManager()
        manager.list_tasks = AsyncMock(return_value=([{"task_id": "t1"}], 1))

        resp = await list_tasks_handler(_redis(), auth, manager, TaskListQuery())

        assert resp.data.total == 1

    async def test_get_task_detail_missing_returns_404(self, auth: AuthContext) -> None:
        """详情不存在返回 404。"""
        manager = _TaskManager()
        manager.get_task_detail = AsyncMock(side_effect=ValueError("missing"))

        with pytest.raises(HTTPException) as exc:
            await get_task_detail_handler("t1", _redis(), auth, manager)

        assert exc.value.status_code == 404

    async def test_get_task_status_missing_returns_404(self, auth: AuthContext) -> None:
        """状态不存在返回 404。"""
        manager = _TaskManager()
        manager.get_task_status = AsyncMock(side_effect=ValueError("missing"))

        with pytest.raises(HTTPException) as exc:
            await get_task_status_handler("t1", _redis(), auth, manager)

        assert exc.value.status_code == 404

    async def test_cancel_task_missing_returns_404(self, auth: AuthContext) -> None:
        """取消不存在任务返回 404。"""
        manager = _TaskManager()
        manager.cancel_task = AsyncMock(return_value=False)

        with pytest.raises(HTTPException) as exc:
            await cancel_task_handler("t1", _redis(), auth, manager)

        assert exc.value.status_code == 404

    async def test_cancel_task_success(self, auth: AuthContext) -> None:
        """取消成功返回已取消标记。"""
        manager = _TaskManager()
        manager.cancel_task = AsyncMock(return_value=True)

        resp = await cancel_task_handler("t1", _redis(), auth, manager)

        assert resp.data["cancelled"] is True

    async def test_delete_task_missing_returns_404(self, auth: AuthContext) -> None:
        """删除不存在任务返回 404。"""
        redis = _redis(delete_task_ok=False)

        with pytest.raises(HTTPException) as exc:
            await delete_task_handler("t1", redis, auth)

        assert exc.value.status_code == 404

    async def test_delete_task_success(self, auth: AuthContext) -> None:
        """删除成功返回已删除标记。"""
        resp = await delete_task_handler("t1", _redis(delete_task_ok=True), auth)

        assert resp.data["deleted"] is True


class TestTaskScope:
    """任务路由 scope 校验。"""

    async def test_create_task_requires_write_scope(self) -> None:
        """无 tasks:write 时拒绝创建。"""
        auth = AuthContext(tenant_id="t", user_id="u", scopes=["tasks:read"])

        with pytest.raises(HTTPException) as exc:
            await create_task_handler(
                TaskCreateRequest(product_id="p"), _redis(), auth, _TaskManager()
            )

        assert exc.value.status_code == 403

    async def test_list_tasks_accepts_read_scope(self) -> None:
        """tasks:read 允许列表查询。"""
        auth = AuthContext(tenant_id="t", user_id="u", scopes=["tasks:read"])
        manager = _TaskManager()
        manager.list_tasks = AsyncMock(return_value=([], 0))

        resp = await list_tasks_handler(_redis(), auth, manager, TaskListQuery())

        assert resp.code == 200


class TestProductScope:
    """商品路由 scope 校验。"""

    async def test_create_requires_write_scope(self) -> None:
        """无 products:write 时拒绝创建。"""
        auth = AuthContext(tenant_id="t", user_id="u", scopes=["products:read"])
        request = ProductCreateRequest(
            name="商品A",
            category=ProductCategory.DIGITAL,
            description="足够长的商品描述文本用于通过校验",
        )

        with pytest.raises(HTTPException) as exc:
            await create_product(request, _redis(), auth)

        assert exc.value.status_code == 403

    async def test_get_accepts_read_scope(self) -> None:
        """products:read 允许读取详情。"""
        auth = AuthContext(tenant_id="t", user_id="u", scopes=["products:read"])

        resp = await get_product("prod_001", _redis(), auth)

        assert resp.code == 200
