"""
Graph RAG / CategoryMemory CRUD API 测试。

Description:
    测试 CategoryMemory、GraphRAGEntity、GraphRAGEdge 的 CRUD 接口。
    handler 直接调用 + FakeDBSession 注入（session 现为显式参数，
    无需字符串 patch get_db）。scope/租户/404/409 语义由 TenantCRUD
    门面承载，其自身行为在 test_crud_facade.py 覆盖。
@author ganjianfei
@version 1.1.0
2026-09-08
"""

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest import mock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from src.auth.context import AuthContext

# ============================================================================
# Helpers: Auth fixtures
# ============================================================================


@pytest.fixture
def auth_a() -> AuthContext:
    """租户 A，拥有 memory:* scope。"""
    return AuthContext(
        tenant_id="tenant-a",
        user_id="user-a",
        scopes=["memory:read", "memory:write"],
    )


@pytest.fixture
def auth_readonly() -> AuthContext:
    """只读 scope。"""
    return AuthContext(
        tenant_id="tenant-a",
        user_id="user-ro",
        scopes=["memory:read"],
    )


@pytest.fixture
def auth_no_scope() -> AuthContext:
    """无 memory scope。"""
    return AuthContext(
        tenant_id="tenant-a",
        user_id="user-none",
        scopes=[],
    )


# ============================================================================
# Helpers: Mock DB Session
# ============================================================================


class FakeDBSession:
    """模拟 AsyncSession，支持 add/flush/refresh/rollback/execute/delete。

    用列表存储已添加的对象，execute 返回预设的 mock result。
    """

    def __init__(
        self,
        *,
        scalars_return: list[Any] | None = None,
        scalars_first_return: Any = None,
        add_side_effect: Any = None,
        flush_side_effect: Any = None,
    ) -> None:
        """初始化 FakeDBSession。

        Args:
            scalars_return: execute().scalars().all() 返回值。
            scalars_first_return: execute().scalars().first() 返回值。
            add_side_effect: session.add() 的 side_effect（如 raise IntegrityError）。
            flush_side_effect: session.flush() 的 side_effect（409 语义测试用）。
        """
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self._scalars_return = scalars_return or []
        self._scalars_first = scalars_first_return
        self._add_side_effect = add_side_effect
        self._flush_side_effect = flush_side_effect
        self.flushed = 0
        self.rolled_back = False
        self.refreshed: list[Any] = []

    def add(self, obj: Any) -> None:
        if self._add_side_effect is not None:
            if isinstance(self._add_side_effect, Exception):
                raise self._add_side_effect
            self._add_side_effect(obj)
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushed += 1
        if self._flush_side_effect is not None:
            if isinstance(self._flush_side_effect, Exception):
                raise self._flush_side_effect
            self._flush_side_effect()

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(self, obj: Any) -> None:
        """模拟 refresh：设置 id 等字段。"""
        self.refreshed.append(obj)
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = 1
        if not hasattr(obj, "created_at") or obj.created_at is None:
            obj.created_at = datetime.now(UTC)
        if not hasattr(obj, "updated_at") or obj.updated_at is None:
            obj.updated_at = datetime.now(UTC)

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    async def execute(self, _stmt: Any) -> Any:
        return _FakeResult(
            scalars_all=self._scalars_return,
            scalars_first=self._scalars_first,
        )


class _FakeResult:
    """模拟 SQLAlchemy Result。"""

    def __init__(
        self,
        scalars_all: list[Any] | None = None,
        scalars_first: Any = None,
    ) -> None:
        self._scalars_all = scalars_all or []
        self._scalars_first = scalars_first

    def scalars(self) -> "_FakeScalars":
        return _FakeScalars(self._scalars_all, self._scalars_first)


class _FakeScalars:
    """模拟 SQLAlchemy Scalars。"""

    def __init__(self, all_items: list[Any], first_item: Any = None) -> None:
        self._all = all_items
        self._first = first_item

    def all(self) -> list[Any]:
        return self._all

    def first(self) -> Any:
        return self._first


# ============================================================================
# Helpers: Create fake model instances matching the DB model shape
# ============================================================================


def _make_memory(
    id: int = 1,
    tenant_id: str = "tenant-a",
    category: str = "digital",
    **kwargs: Any,
) -> Any:
    """创建一个类似 CategoryMemory 的假对象。"""
    obj = mock.MagicMock()
    obj.id = id
    obj.tenant_id = tenant_id
    obj.category = category
    obj.summary = kwargs.get("summary", "测试摘要")
    obj.best_practices = kwargs.get("best_practices", [])
    obj.negative_patterns = kwargs.get("negative_patterns", [])
    obj.style_guidelines = kwargs.get("style_guidelines", {})
    obj.performance_hints = kwargs.get("performance_hints", {})
    obj.extra_data = kwargs.get("extra_data", {})
    obj.created_at = kwargs.get("created_at", datetime.now(UTC))
    obj.updated_at = kwargs.get("updated_at", datetime.now(UTC))
    return obj


def _make_entity(
    id: int = 1,
    tenant_id: str = "tenant-a",
    name: str = "test-entity",
    entity_type: str = "concept",
    category: str = "digital",
    **kwargs: Any,
) -> Any:
    """创建一个类似 GraphRAGEntity 的假对象。"""
    obj = mock.MagicMock()
    obj.id = id
    obj.tenant_id = tenant_id
    obj.name = name
    obj.entity_type = entity_type
    obj.category = category
    obj.description = kwargs.get("description", "描述")
    obj.aliases = kwargs.get("aliases", [])
    obj.extra_data = kwargs.get("extra_data", {})
    obj.created_at = kwargs.get("created_at", datetime.now(UTC))
    obj.updated_at = kwargs.get("updated_at", datetime.now(UTC))
    return obj


def _make_edge(
    id: int = 1,
    tenant_id: str = "tenant-a",
    source_entity_id: int = 1,
    target_entity_id: int = 2,
    relationship_type: str = "related_to",
    category: str = "digital",
    **kwargs: Any,
) -> Any:
    """创建一个类似 GraphRAGEdge 的假对象。"""
    obj = mock.MagicMock()
    obj.id = id
    obj.tenant_id = tenant_id
    obj.source_entity_id = source_entity_id
    obj.target_entity_id = target_entity_id
    obj.relationship_type = relationship_type
    obj.category = category
    obj.weight = kwargs.get("weight", 1.0)
    obj.evidence = kwargs.get("evidence")
    obj.extra_data = kwargs.get("extra_data", {})
    obj.created_at = kwargs.get("created_at", datetime.now(UTC))
    return obj


# ============================================================================
# CategoryMemory Tests
# ============================================================================


class TestCreateMemory:
    """测试创建类目记忆。"""

    def test_create_memory_writes_with_current_tenant(self, auth_a: AuthContext) -> None:
        """创建记忆时应强制使用当前租户 ID。"""
        from src.api.router.graph_rag import create_memory
        from src.api.schema.graph_rag import CategoryMemoryCreate

        session = FakeDBSession()

        async def _run() -> None:
            result = await create_memory(
                request=CategoryMemoryCreate(category="digital", summary="测试"),
                auth=auth_a,
                session=session,
            )
            assert result.code == 200
            assert result.message == "创建成功"
            assert result.data is not None
            assert len(session.added) == 1
            assert session.added[0].tenant_id == "tenant-a"
            assert session.added[0].category == "digital"

        asyncio.run(_run())

    def test_create_memory_requires_write_scope(self, auth_readonly: AuthContext) -> None:
        """只有 memory:write scope 才能创建。"""
        from src.api.router.graph_rag import create_memory
        from src.api.schema.graph_rag import CategoryMemoryCreate

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await create_memory(
                    request=CategoryMemoryCreate(category="digital"),
                    auth=auth_readonly,
                    session=FakeDBSession(),
                )
            assert exc_info.value.status_code == 403

        asyncio.run(_run())

    def test_create_memory_duplicate_returns_409(self, auth_a: AuthContext) -> None:
        """重复创建 (tenant_id, category) 返回 409。"""
        from src.api.router.graph_rag import create_memory
        from src.api.schema.graph_rag import CategoryMemoryCreate

        # 门面在 flush 时翻译 IntegrityError → 409
        session = FakeDBSession(flush_side_effect=IntegrityError("mock", {}, Exception()))

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await create_memory(
                    request=CategoryMemoryCreate(category="digital"),
                    auth=auth_a,
                    session=session,
                )
            assert exc_info.value.status_code == 409
            assert "已存在" in exc_info.value.detail
            assert session.rolled_back

        asyncio.run(_run())


class TestListMemories:
    """测试列出类目记忆。"""

    def test_list_memories_filters_by_tenant(self, auth_a: AuthContext) -> None:
        """列表应只返回当前租户的数据。"""
        from src.api.router.graph_rag import list_memories

        mem_a = _make_memory(id=1, tenant_id="tenant-a", category="digital")
        session = FakeDBSession(scalars_return=[mem_a])

        async def _run() -> None:
            result = await list_memories(auth=auth_a, session=session)
            assert result.code == 200
            assert len(result.data) == 1
            assert result.data[0].id == 1
            assert result.data[0].tenant_id == "tenant-a"

        asyncio.run(_run())

    def test_list_memories_with_include_shared_returns_shared(self, auth_a: AuthContext) -> None:
        """include_shared=true 时应返回共享记忆。"""
        from src.api.router.graph_rag import list_memories

        mem_shared = _make_memory(id=1, tenant_id=None, category="shared-cat")
        session = FakeDBSession(scalars_return=[mem_shared])

        async def _run() -> None:
            result = await list_memories(auth=auth_a, session=session, include_shared=True)
            assert result.code == 200
            assert len(result.data) == 1
            assert result.data[0].tenant_id is None

        asyncio.run(_run())

    def test_list_memories_with_category_filter(self, auth_a: AuthContext) -> None:
        """按 category 过滤列表。"""
        from src.api.router.graph_rag import list_memories

        mem = _make_memory(id=1, tenant_id="tenant-a", category="digital")
        session = FakeDBSession(scalars_return=[mem])

        async def _run() -> None:
            result = await list_memories(auth=auth_a, session=session, category="digital")
            assert result.code == 200
            assert len(result.data) == 1

        asyncio.run(_run())

    def test_list_requires_read_or_write_scope(self, auth_no_scope: AuthContext) -> None:
        """无 scope 应返回 403。"""
        from src.api.router.graph_rag import list_memories

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await list_memories(auth=auth_no_scope, session=FakeDBSession())
            assert exc_info.value.status_code == 403

        asyncio.run(_run())


class TestGetMemory:
    """测试获取类目记忆详情。"""

    def test_get_memory_returns_404_for_other_tenant(self, auth_a: AuthContext) -> None:
        """跨租户获取应返回 404。

        租户条件在 SQL 层过滤：跨租户行不会从 DB 返回，fake 模拟
        DB 视角返回 None（与"不存在"不可区分，防枚举）。
        """
        from src.api.router.graph_rag import get_memory

        session = FakeDBSession(scalars_first_return=None)

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await get_memory(memory_id=10, auth=auth_a, session=session)
            assert exc_info.value.status_code == 404

        asyncio.run(_run())

    def test_get_memory_returns_404_for_missing(self, auth_a: AuthContext) -> None:
        """不存在的记忆返回 404。"""
        from src.api.router.graph_rag import get_memory

        session = FakeDBSession(scalars_first_return=None)

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await get_memory(memory_id=999, auth=auth_a, session=session)
            assert exc_info.value.status_code == 404

        asyncio.run(_run())

    def test_get_memory_requires_scope(self, auth_no_scope: AuthContext) -> None:
        """无 scope 应返回 403。"""
        from src.api.router.graph_rag import get_memory

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await get_memory(memory_id=1, auth=auth_no_scope, session=FakeDBSession())
            assert exc_info.value.status_code == 403

        asyncio.run(_run())


class TestUpdateMemory:
    """测试更新类目记忆。"""

    def test_update_memory_validates_tenant(self, auth_a: AuthContext) -> None:
        """只能更新本租户的记忆（跨租户行在 SQL 层被过滤 → 404）。"""
        from src.api.router.graph_rag import update_memory
        from src.api.schema.graph_rag import CategoryMemoryUpdate

        session = FakeDBSession(scalars_first_return=None)

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await update_memory(
                    memory_id=10,
                    request=CategoryMemoryUpdate(summary="new"),
                    auth=auth_a,
                    session=session,
                )
            assert exc_info.value.status_code == 404

        asyncio.run(_run())

    def test_update_memory_requires_write_scope(self, auth_readonly: AuthContext) -> None:
        """更新需要 memory:write scope。"""
        from src.api.router.graph_rag import update_memory
        from src.api.schema.graph_rag import CategoryMemoryUpdate

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await update_memory(
                    memory_id=1,
                    request=CategoryMemoryUpdate(summary="new"),
                    auth=auth_readonly,
                    session=FakeDBSession(),
                )
            assert exc_info.value.status_code == 403

        asyncio.run(_run())


class TestDeleteMemory:
    """测试删除类目记忆。"""

    def test_delete_memory_validates_tenant(self, auth_a: AuthContext) -> None:
        """只能删除本租户的记忆（跨租户行在 SQL 层被过滤 → 404）。"""
        from src.api.router.graph_rag import delete_memory

        session = FakeDBSession(scalars_first_return=None)

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await delete_memory(memory_id=10, auth=auth_a, session=session)
            assert exc_info.value.status_code == 404

        asyncio.run(_run())

    def test_delete_memory_requires_write_scope(self, auth_readonly: AuthContext) -> None:
        """删除需要 memory:write scope。"""
        from src.api.router.graph_rag import delete_memory

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await delete_memory(memory_id=1, auth=auth_readonly, session=FakeDBSession())
            assert exc_info.value.status_code == 403

        asyncio.run(_run())


# ============================================================================
# GraphRAGEntity Tests
# ============================================================================


class TestCreateEntity:
    """测试创建实体。"""

    def test_create_entity(self, auth_a: AuthContext) -> None:
        """创建实体成功。"""
        from src.api.router.graph_rag import create_entity
        from src.api.schema.graph_rag import GraphRAGEntityCreate

        session = FakeDBSession()

        async def _run() -> None:
            result = await create_entity(
                request=GraphRAGEntityCreate(
                    name="test-entity",
                    entity_type="concept",
                    category="digital",
                ),
                auth=auth_a,
                session=session,
            )
            assert result.code == 200
            assert len(session.added) == 1
            assert session.added[0].tenant_id == "tenant-a"

        asyncio.run(_run())

    def test_create_entity_requires_write_scope(self, auth_readonly: AuthContext) -> None:
        """创建实体需要 memory:write scope。"""
        from src.api.router.graph_rag import create_entity
        from src.api.schema.graph_rag import GraphRAGEntityCreate

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await create_entity(
                    request=GraphRAGEntityCreate(
                        name="test", entity_type="concept", category="digital"
                    ),
                    auth=auth_readonly,
                    session=FakeDBSession(),
                )
            assert exc_info.value.status_code == 403

        asyncio.run(_run())


class TestListEntities:
    """测试列出实体。"""

    def test_list_entities(self, auth_a: AuthContext) -> None:
        """列出实体返回结果。"""
        from src.api.router.graph_rag import list_entities

        entity = _make_entity(id=1)
        session = FakeDBSession(scalars_return=[entity])

        async def _run() -> None:
            result = await list_entities(auth=auth_a, session=session)
            assert result.code == 200
            assert len(result.data) == 1
            assert result.data[0].id == 1

        asyncio.run(_run())

    def test_list_entities_with_filters(self, auth_a: AuthContext) -> None:
        """按 category 和 entity_type 过滤实体。"""
        from src.api.router.graph_rag import list_entities

        entity = _make_entity(id=1, category="digital", entity_type="concept")
        session = FakeDBSession(scalars_return=[entity])

        async def _run() -> None:
            result = await list_entities(
                auth=auth_a,
                session=session,
                category="digital",
                entity_type="concept",
            )
            assert result.code == 200
            assert len(result.data) == 1

        asyncio.run(_run())


class TestGetEntity:
    """测试获取实体详情。"""

    def test_get_entity(self, auth_a: AuthContext) -> None:
        """获取实体详情成功。"""
        from src.api.router.graph_rag import get_entity

        entity = _make_entity(id=1)
        session = FakeDBSession(scalars_first_return=entity)

        async def _run() -> None:
            result = await get_entity(entity_id=1, auth=auth_a, session=session)
            assert result.code == 200
            assert result.data.id == 1

        asyncio.run(_run())

    def test_get_entity_returns_404_for_other_tenant(self, auth_a: AuthContext) -> None:
        """跨租户获取实体返回 404（SQL 层过滤，DB 视角无行）。"""
        from src.api.router.graph_rag import get_entity

        session = FakeDBSession(scalars_first_return=None)

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await get_entity(entity_id=10, auth=auth_a, session=session)
            assert exc_info.value.status_code == 404

        asyncio.run(_run())


class TestDeleteEntity:
    """测试删除实体。"""

    def test_delete_entity(self, auth_a: AuthContext) -> None:
        """删除实体成功。"""
        from src.api.router.graph_rag import delete_entity

        entity = _make_entity(id=1)
        session = FakeDBSession(scalars_first_return=entity)

        async def _run() -> None:
            result = await delete_entity(entity_id=1, auth=auth_a, session=session)
            assert result.code == 200
            assert result.message == "删除成功"
            assert len(session.deleted) == 1

        asyncio.run(_run())

    def test_delete_entity_returns_404_for_other_tenant(self, auth_a: AuthContext) -> None:
        """跨租户删除实体返回 404（SQL 层过滤，DB 视角无行）。"""
        from src.api.router.graph_rag import delete_entity

        session = FakeDBSession(scalars_first_return=None)

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await delete_entity(entity_id=10, auth=auth_a, session=session)
            assert exc_info.value.status_code == 404
            assert len(session.deleted) == 0

        asyncio.run(_run())


# ============================================================================
# GraphRAGEdge Tests
# ============================================================================


class TestCreateEdge:
    """测试创建边。"""

    def test_create_edge(self, auth_a: AuthContext) -> None:
        """创建边成功。"""
        from src.api.router.graph_rag import create_edge
        from src.api.schema.graph_rag import GraphRAGEdgeCreate

        session = FakeDBSession()

        async def _run() -> None:
            result = await create_edge(
                request=GraphRAGEdgeCreate(
                    source_entity_id=1,
                    target_entity_id=2,
                    relationship_type="related_to",
                    category="digital",
                ),
                auth=auth_a,
                session=session,
            )
            assert result.code == 200
            assert len(session.added) == 1
            assert session.added[0].tenant_id == "tenant-a"

        asyncio.run(_run())

    def test_create_edge_requires_write_scope(self, auth_readonly: AuthContext) -> None:
        """创建边需要 memory:write scope。"""
        from src.api.router.graph_rag import create_edge
        from src.api.schema.graph_rag import GraphRAGEdgeCreate

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await create_edge(
                    request=GraphRAGEdgeCreate(
                        source_entity_id=1,
                        target_entity_id=2,
                        relationship_type="related_to",
                        category="digital",
                    ),
                    auth=auth_readonly,
                    session=FakeDBSession(),
                )
            assert exc_info.value.status_code == 403

        asyncio.run(_run())


class TestListEdges:
    """测试列出边。"""

    def test_list_edges(self, auth_a: AuthContext) -> None:
        """列出边返回结果。"""
        from src.api.router.graph_rag import list_edges

        edge = _make_edge(id=1)
        session = FakeDBSession(scalars_return=[edge])

        async def _run() -> None:
            result = await list_edges(auth=auth_a, session=session)
            assert result.code == 200
            assert len(result.data) == 1
            assert result.data[0].id == 1

        asyncio.run(_run())

    def test_list_edges_with_filters(self, auth_a: AuthContext) -> None:
        """按 category 和 source_entity_id 过滤边。"""
        from src.api.router.graph_rag import list_edges

        edge = _make_edge(id=1, category="digital", source_entity_id=1)
        session = FakeDBSession(scalars_return=[edge])

        async def _run() -> None:
            result = await list_edges(
                auth=auth_a,
                session=session,
                category="digital",
                source_entity_id=1,
            )
            assert result.code == 200
            assert len(result.data) == 1

        asyncio.run(_run())


class TestGetEdge:
    """测试获取边详情。"""

    def test_get_edge(self, auth_a: AuthContext) -> None:
        """获取边详情成功。"""
        from src.api.router.graph_rag import get_edge

        edge = _make_edge(id=1)
        session = FakeDBSession(scalars_first_return=edge)

        async def _run() -> None:
            result = await get_edge(edge_id=1, auth=auth_a, session=session)
            assert result.code == 200
            assert result.data.id == 1

        asyncio.run(_run())

    def test_get_edge_returns_404_for_other_tenant(self, auth_a: AuthContext) -> None:
        """跨租户获取边返回 404（SQL 层过滤，DB 视角无行）。"""
        from src.api.router.graph_rag import get_edge

        session = FakeDBSession(scalars_first_return=None)

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await get_edge(edge_id=10, auth=auth_a, session=session)
            assert exc_info.value.status_code == 404

        asyncio.run(_run())
