"""
测试 Redis 租户命名空间隔离。

Tests for RedisClient tenant namespace (_tenant_key) and all product/task
methods with keyword-only tenant_id parameter.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.service.redis_client import RedisClient
from src.graph.state import GenerationRequest
from src.models.product import Product, ProductCategory

# ---------------------------------------------------------------------------
# Fake pipeline for testing async with usage
# ---------------------------------------------------------------------------


class _FakePipeline:
    """Fake Redis pipeline for testing async with usage.

    Mirrors the production pattern::

        async with client.pipeline() as pipe:
            pipe.hset(...)   # sync, chainable
            pipe.zadd(...)   # sync, chainable
            pipe.delete(...) # sync, chainable
            pipe.zrem(...)   # sync, chainable
            pipe.set(...)    # sync, chainable
            await pipe.execute()  # async

    Sync methods use MagicMock (no RuntimeWarning).
    ``execute`` uses AsyncMock (it is awaited in production).
    """

    def __init__(self) -> None:
        self.hset = MagicMock()
        self.zadd = MagicMock()
        self.delete = MagicMock()
        self.zrem = MagicMock()
        self.set = MagicMock()
        self.execute: AsyncMock = AsyncMock()

    async def __aenter__(self) -> "_FakePipeline":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_product(product_id: str, name: str = "测试商品") -> Product:
    """Create a minimal Product for tests."""
    return Product(
        product_id=product_id,
        name=name,
        category=ProductCategory.DIGITAL,
        description="这是一个测试商品，包含足够的描述文字",
    )


def make_request(task_id: str = "task-1") -> GenerationRequest:
    """Create a minimal GenerationRequest for tests."""
    return GenerationRequest(task_id=task_id)


# ---------------------------------------------------------------------------
# _tenant_key helper
# ---------------------------------------------------------------------------


class TestTenantKey:
    """测试 _tenant_key 方法。"""

    def test_basic_tenant_key(self) -> None:
        """测试基本的租户 key 生成。"""
        client = RedisClient()
        key = client._tenant_key("tenant_001", "product", "prod_001")
        prefix = client._prefix
        assert key == f"{prefix}tenant:tenant_001:product:prod_001"

    def test_tenant_key_with_multiple_parts(self) -> None:
        """测试多段 key 拼接。"""
        client = RedisClient()
        key = client._tenant_key("tenant_001", "task", "task-abc", "state")
        prefix = client._prefix
        assert key == f"{prefix}tenant:tenant_001:task:task-abc:state"

    def test_tenant_key_empty_string_raises(self) -> None:
        """测试空 tenant_id 抛出 ValueError。"""
        client = RedisClient()
        with pytest.raises(ValueError, match="tenant_id is required"):
            client._tenant_key("", "product", "prod_001")

    def test_tenant_key_none_raises(self) -> None:
        """测试 None tenant_id 抛出 ValueError。"""
        client = RedisClient()
        with pytest.raises(ValueError, match="tenant_id is required"):
            client._tenant_key(None, "product", "prod_001")  # type: ignore[arg-type]

    def test_tenant_key_preserves_single_tenant(self) -> None:
        """测试不同 tenant 产生不同的 key 前缀。"""
        client = RedisClient()
        k1 = client._tenant_key("t1", "product", "p1")
        k2 = client._tenant_key("t2", "product", "p1")
        assert k1 != k2
        assert "tenant:t1" in k1
        assert "tenant:t2" in k2


# ---------------------------------------------------------------------------
# Product CRUD with tenant namespace
# ---------------------------------------------------------------------------


class TestProductWithTenant:
    """测试商品操作的租户命名空间隔离。"""

    @pytest.fixture
    def client(self) -> RedisClient:
        """创建 RedisClient 并 mock 内部 _client。"""
        c = RedisClient()
        c._client = MagicMock()
        # _FakePipeline supports async with via real __aenter__/__aexit__
        c._client.pipeline.return_value = _FakePipeline()
        return c

    @pytest.mark.asyncio
    async def test_save_product_uses_tenant_namespace(self, client: RedisClient) -> None:
        """测试 save_product 使用租户命名空间 key。"""
        product = make_product("prod_001", name="智能手表")
        mock_pipe = client._client.pipeline.return_value
        mock_pipe.execute.return_value = None

        result = await client.save_product(product, tenant_id="tenant_001")

        assert result == "prod_001"
        assert mock_pipe.hset.called
        hset_key = mock_pipe.hset.call_args[0][0]
        assert "tenant:tenant_001:product:prod_001" in str(hset_key)

    @pytest.mark.asyncio
    async def test_get_product_uses_tenant_namespace(self, client: RedisClient) -> None:
        """测试 get_product 使用租户命名空间 key。"""
        product = make_product("prod_001", name="智能手表")
        client._client.hget = AsyncMock(
            return_value=json.dumps(product.model_dump(mode="json"))
        )

        result = await client.get_product("prod_001", tenant_id="tenant_001")

        assert result is not None
        assert result.name == "智能手表"
        # Verify hget was called with tenant-namespaced key
        call_args = client._client.hget.call_args
        assert "tenant:tenant_001" in str(call_args[0][0])

    @pytest.mark.asyncio
    async def test_list_products_uses_tenant_namespace(self, client: RedisClient) -> None:
        """测试 list_products 使用租户命名空间 list key。"""
        client._client.zcard = AsyncMock(return_value=2)
        client._client.zrevrange = AsyncMock(return_value=["prod_001", "prod_002"])
        product = make_product("prod_001", name="商品1")

        async def fake_hget(key: str, field: str) -> str:
            return json.dumps(product.model_dump(mode="json"))

        client._client.hget = AsyncMock(side_effect=fake_hget)

        products, total = await client.list_products(tenant_id="tenant_001", page=1, page_size=10)

        assert total == 2
        assert len(products) == 2
        # Verify zcard/zrevrange key contains tenant namespace
        assert "tenant:tenant_001" in str(client._client.zcard.call_args[0][0])
        assert "tenant:tenant_001" in str(client._client.zrevrange.call_args[0][0])

    @pytest.mark.asyncio
    async def test_update_product_uses_tenant_namespace(self, client: RedisClient) -> None:
        """测试 update_product 使用租户命名空间 key。"""
        product = make_product("prod_001", name="智能手表")
        client._client.exists = AsyncMock(return_value=1)
        client._client.hset = AsyncMock()

        result = await client.update_product(product, tenant_id="tenant_001")

        assert result is True
        # Verify exists was called with tenant-namespaced key
        assert "tenant:tenant_001" in str(client._client.exists.call_args[0][0])

    @pytest.mark.asyncio
    async def test_delete_product_uses_tenant_namespace(self, client: RedisClient) -> None:
        """测试 delete_product 使用租户命名空间 key 且只删除该租户的数据。"""
        mock_pipe = client._client.pipeline.return_value
        mock_pipe.execute.return_value = [1, 1]  # delete returns 1, zrem returns 1

        result = await client.delete_product("prod_001", tenant_id="tenant_001")

        assert result is True
        # Verify delete was called with tenant-namespaced key
        assert mock_pipe.delete.called
        delete_key = mock_pipe.delete.call_args[0][0]
        assert "tenant:tenant_001" in str(delete_key)


# ---------------------------------------------------------------------------
# Task operations with tenant namespace
# ---------------------------------------------------------------------------


class TestTaskWithTenant:
    """测试任务操作的租户命名空间隔离。"""

    @pytest.fixture
    def client(self) -> RedisClient:
        """创建 RedisClient 并 mock 内部 _client。"""
        c = RedisClient()
        c._client = MagicMock()
        # _FakePipeline supports async with via real __aenter__/__aexit__
        c._client.pipeline.return_value = _FakePipeline()
        return c

    @pytest.mark.asyncio
    async def test_create_task_metadata_contains_tenant_id(self, client: RedisClient) -> None:
        """测试 create_task metadata 包含 tenant_id。"""
        request = make_request("task-1")
        mock_pipe = client._client.pipeline.return_value
        mock_pipe.execute.return_value = None

        await client.create_task("task-1", "prod_001", request, tenant_id="tenant_001")

        # Verify hset was called
        assert mock_pipe.hset.called, "hset should have been called"

        # Extract the metadata from the hset call
        hset_key = mock_pipe.hset.call_args[0][0]
        hset_kwargs = mock_pipe.hset.call_args[1]
        mapping = hset_kwargs.get("mapping", {})
        assert "tenant:tenant_001" in str(hset_key)
        metadata_json = mapping.get("metadata", "{}")
        metadata = json.loads(metadata_json)
        assert metadata["tenant_id"] == "tenant_001"
        assert metadata["task_id"] == "task-1"
        assert metadata["product_id"] == "prod_001"

    @pytest.mark.asyncio
    async def test_create_task_uses_tenant_key_for_task_and_list(
        self, client: RedisClient
    ) -> None:
        """测试 create_task 的 task key 和 list key 都使用租户命名空间。"""
        request = make_request("task-1")
        mock_pipe = client._client.pipeline.return_value
        mock_pipe.execute.return_value = None

        await client.create_task("task-1", "prod_001", request, tenant_id="tenant_001")

        # Check hset key uses tenant namespace
        assert mock_pipe.hset.called, "hset should have been called"
        hset_key = str(mock_pipe.hset.call_args[0][0])
        assert "tenant:tenant_001" in hset_key, f"hset key {hset_key} missing tenant namespace"

        # Check zadd key uses tenant namespace
        assert mock_pipe.zadd.called, "zadd should have been called"
        zadd_key = str(mock_pipe.zadd.call_args[0][0])
        assert "tenant:tenant_001" in zadd_key, f"zadd key {zadd_key} missing tenant namespace"

    @pytest.mark.asyncio
    async def test_get_task_metadata_uses_tenant_namespace(self, client: RedisClient) -> None:
        """测试 get_task_metadata 使用租户命名空间。"""
        metadata = {
            "task_id": "task-1",
            "product_id": "prod_001",
            "tenant_id": "tenant_001",
            "status": "pending",
        }
        client._client.hget = AsyncMock(
            return_value=json.dumps(metadata)
        )

        result = await client.get_task_metadata("task-1", tenant_id="tenant_001")

        assert result is not None
        assert result["tenant_id"] == "tenant_001"
        assert "tenant:tenant_001" in str(client._client.hget.call_args[0][0])

    @pytest.mark.asyncio
    async def test_save_task_state_uses_tenant_namespace(self, client: RedisClient) -> None:
        """测试 save_task_state 使用租户命名空间。"""
        from src.graph.state import AgentState

        state = AgentState(current_step="test")
        client._client.hget = AsyncMock(return_value=None)  # get_task_metadata will return None
        mock_pipe = client._client.pipeline.return_value
        mock_pipe.execute.return_value = None

        await client.save_task_state("task-1", state, tenant_id="tenant_001")

        # Verify the set call used tenant namespace
        assert mock_pipe.set.called, "set should have been called"
        key = mock_pipe.set.call_args[0][0]
        assert "tenant:tenant_001" in str(key)
        assert ":state" in str(key)

    @pytest.mark.asyncio
    async def test_get_task_state_uses_tenant_namespace(self, client: RedisClient) -> None:
        """测试 get_task_state 使用租户命名空间。"""
        from src.graph.state import AgentState

        state = AgentState(current_step="test")
        client._client.get = AsyncMock(
            return_value=json.dumps(state.model_dump(mode="json"))
        )

        result = await client.get_task_state("task-1", tenant_id="tenant_001")

        assert result is not None
        assert result.current_step == "test"
        assert "tenant:tenant_001" in str(client._client.get.call_args[0][0])

    @pytest.mark.asyncio
    async def test_update_task_progress_uses_tenant_namespace(
        self, client: RedisClient
    ) -> None:
        """测试 update_task_progress 使用租户命名空间。"""
        metadata = {
            "task_id": "task-1",
            "product_id": "prod_001",
            "tenant_id": "tenant_001",
            "status": "pending",
            "progress": 0.0,
        }
        client._client.hget = AsyncMock(return_value=json.dumps(metadata))
        client._client.hset = AsyncMock()

        await client.update_task_progress(
            "task-1", "running", 50.0, "generate", tenant_id="tenant_001"
        )

        # Verify hset was called with tenant-namespaced key
        hset_key = str(client._client.hset.call_args[0][0])
        assert "tenant:tenant_001" in hset_key

    @pytest.mark.asyncio
    async def test_list_tasks_filter_then_paginate_in_tenant_namespace(
        self, client: RedisClient
    ) -> None:
        """测试 list_tasks 在租户命名空间里先过滤状态再分页，total 是过滤后总数。"""
        # Simulate 3 tasks in tenant sorted set
        client._client.zrevrange = AsyncMock(
            return_value=["task-1", "task-2", "task-3"]
        )

        def fake_hget(key: str, field: str) -> str | None:
            if "task-1" in str(key):
                return json.dumps(
                    {"task_id": "task-1", "status": "pending", "tenant_id": "tenant_001"}
                )
            elif "task-2" in str(key):
                return json.dumps(
                    {"task_id": "task-2", "status": "completed", "tenant_id": "tenant_001"}
                )
            elif "task-3" in str(key):
                return json.dumps(
                    {"task_id": "task-3", "status": "completed", "tenant_id": "tenant_001"}
                )
            return None

        client._client.hget = AsyncMock(side_effect=fake_hget)
        client._client.get = AsyncMock(return_value=None)  # get_task_state returns None

        # Filter by status=completed, page=1, page_size=1
        tasks, total = await client.list_tasks(
            tenant_id="tenant_001", page=1, page_size=1, status="completed"
        )

        # total should be filtered count (2 completed), page 1 should return 1 item
        assert total == 2, f"Expected 2 filtered tasks, got {total}"
        assert len(tasks) == 1
        assert tasks[0]["task_id"] == "task-2"

        # Verify zrevrange key is tenant-namespaced
        zrevrange_key = str(client._client.zrevrange.call_args[0][0])
        assert "tenant:tenant_001" in zrevrange_key
        assert ":list" in zrevrange_key

    @pytest.mark.asyncio
    async def test_list_tasks_tenant_isolation_no_cross_tenant(
        self, client: RedisClient
    ) -> None:
        """测试不同租户的 list_tasks 使用不同的 key。"""
        client._client.zrevrange = AsyncMock(return_value=[])
        client._client.get = AsyncMock(return_value=None)

        await client.list_tasks(tenant_id="tenant_A", page=1, page_size=10)
        key_a = str(client._client.zrevrange.call_args[0][0])

        await client.list_tasks(tenant_id="tenant_B", page=1, page_size=10)
        key_b = str(client._client.zrevrange.call_args[0][0])

        assert "tenant:tenant_A" in key_a
        assert "tenant:tenant_B" in key_b
        assert key_a != key_b

    @pytest.mark.asyncio
    async def test_delete_task_only_deletes_tenant_namespace(
        self, client: RedisClient
    ) -> None:
        """测试 delete_task 只删除租户命名空间内的 key。"""
        mock_pipe = client._client.pipeline.return_value
        mock_pipe.execute.return_value = [2, 1]  # delete returns 2 keys, zrem returns 1

        result = await client.delete_task("task-1", tenant_id="tenant_001")

        assert result is True

        # Verify delete was called with tenant-namespaced keys
        assert mock_pipe.delete.called
        delete_args = mock_pipe.delete.call_args[0]
        for key in delete_args:
            assert "tenant:tenant_001" in str(key), (
                f"Key {key} missing tenant namespace"
            )

    @pytest.mark.asyncio
    async def test_save_task_state_calls_get_task_metadata_with_tenant(
        self, client: RedisClient
    ) -> None:
        """测试 save_task_state 调用 get_task_metadata 时传递 tenant_id。"""
        from src.graph.state import AgentState

        state = AgentState(current_step="test")

        metadata = {
            "task_id": "task-1",
            "product_id": "prod_001",
            "tenant_id": "tenant_001",
            "status": "pending",
            "updated_at": "2026-01-01T00:00:00",
        }
        client._client.hget = AsyncMock(return_value=json.dumps(metadata))
        mock_pipe = client._client.pipeline.return_value
        mock_pipe.execute.return_value = None

        await client.save_task_state("task-1", state, tenant_id="tenant_001")

        # hget should have been called with tenant-namespaced key
        assert "tenant:tenant_001" in str(client._client.hget.call_args[0][0])
