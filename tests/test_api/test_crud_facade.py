"""
TenantCRUD 门面单元测试。

Description:
    在 facade 的 interface 上测试行为：scope 校验、租户谓词注入、
    404/403/409 错误语义、防伪造、分页。session 用 FakeDBSession 直传
    （local-substitutable 依赖类别），不做字符串 patch。
@author ganjianfei
@version 1.0.0
2026-09-08
"""

from typing import Any

import pytest
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.api.crud import (
    PageParams,
    ResourceSpec,
    Scopes,
    TenantCRUD,
    TenantMatch,
    mask_secret,
    mask_values,
    require_scope,
    resolve_tenant,
)
from src.api.crud._internals import assert_tenant_scoped
from src.api.schema.common import PageResponse
from src.auth.context import AuthContext
from src.db.models import CategoryMemory

# ============================================================================
# 测试替身
# ============================================================================


class FakeResult:
    """模拟 execute() 返回值：支持 scalars().first() / .all() / scalar_one()。"""

    def __init__(
        self,
        *,
        rows: list[Any] | None = None,
        first: Any = None,
        scalar_one: Any = None,
    ) -> None:
        self._rows = rows or []
        self._first = first
        self._scalar_one = scalar_one

    def scalars(self) -> "FakeResult":
        return self

    def first(self) -> Any:
        return self._first

    def all(self) -> list[Any]:
        return self._rows

    def scalar_one(self) -> Any:
        return self._scalar_one


class FakeDBSession:
    """模拟 AsyncSession：execute 按序弹出预设结果，支持 add/flush/refresh/delete/rollback。"""

    def __init__(
        self,
        *,
        results: list[FakeResult] | None = None,
        flush_side_effect: Exception | None = None,
    ) -> None:
        self._results = list(results or [])
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.executed_stmts: list[Any] = []
        self.flush_count = 0
        self.rolled_back = False
        self._flush_side_effect = flush_side_effect

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, stmt: Any) -> FakeResult:
        self.executed_stmts.append(stmt)
        if self._results:
            return self._results.pop(0)
        return FakeResult()

    async def flush(self) -> None:
        self.flush_count += 1
        if isinstance(self._flush_side_effect, Exception):
            raise self._flush_side_effect

    async def refresh(self, obj: Any) -> None:
        pass

    async def rollback(self) -> None:
        self.rolled_back = True

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)


def last_stmt_sql(session: FakeDBSession) -> str:
    """取最近一次 execute 的语句 SQL 文本。"""
    return str(session.executed_stmts[-1])


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def memory_spec() -> ResourceSpec[CategoryMemory]:
    """类目记忆规格：单条读放行共享行，列表默认不放行（与 graph_rag 现状一致）。"""
    return ResourceSpec(
        model=CategoryMemory,
        label="类目记忆",
        scopes=Scopes.rw("memory:read", "memory:write"),
        read_match=TenantMatch.SHARED_READ,
        not_found_detail="类目记忆不存在",
    )


@pytest.fixture
def auth() -> AuthContext:
    """租户 A 的读写上下文。"""
    return AuthContext(tenant_id="tenant-a", user_id="u1", scopes=["memory:read", "memory:write"])


@pytest.fixture
def auth_no_scope() -> AuthContext:
    """无 memory scope 的上下文。"""
    return AuthContext(tenant_id="tenant-a", user_id="u1", scopes=[])


# ============================================================================
# access.py
# ============================================================================


async def test_require_scope_any_of_passes() -> None:
    """任一 scope 命中即通过。"""
    auth = AuthContext(tenant_id="t", user_id="u", scopes=["a:read"])
    require_scope(auth, "a:read", "a:write")


async def test_require_scope_all_fail_raises_403() -> None:
    """全部不满足抛 403 Forbidden。"""
    auth = AuthContext(tenant_id="t", user_id="u", scopes=["other:read"])
    with pytest.raises(HTTPException) as ei:
        require_scope(auth, "a:read", "a:write")
    assert ei.value.status_code == 403
    assert ei.value.detail == "Forbidden"


async def test_require_scope_wildcard() -> None:
    """通配符 "*" 全部放行。"""
    auth = AuthContext(tenant_id="t", user_id="u", scopes=["*"])
    require_scope(auth, "anything:at:all")


async def test_require_scope_none_auth_passes() -> None:
    """auth=None 放行（仅直调路径可达）。"""
    require_scope(None, "a:read")


async def test_resolve_tenant_default() -> None:
    """auth=None 回退默认租户。"""
    assert resolve_tenant(None) == "default"
    assert resolve_tenant(None, default="dev") == "dev"
    assert resolve_tenant(AuthContext(tenant_id="t9", user_id="u")) == "t9"


# ============================================================================
# TenantCRUD.get
# ============================================================================


async def test_get_returns_instance(
    memory_spec: ResourceSpec[CategoryMemory], auth: AuthContext
) -> None:
    """命中返回实例，且查询带租户条件。"""
    row = CategoryMemory(tenant_id="tenant-a", category="c1")
    session = FakeDBSession(results=[FakeResult(first=row)])
    crud: TenantCRUD[CategoryMemory] = TenantCRUD(memory_spec)

    got = await crud.get(session, auth, 7)

    assert got is row
    assert_tenant_scoped(session.executed_stmts[0], "tenant_id", "tenant-a")


async def test_get_not_found_404_detail(
    memory_spec: ResourceSpec[CategoryMemory], auth: AuthContext
) -> None:
    """不存在返回 404，detail 用 spec 文案。"""
    session = FakeDBSession(results=[FakeResult(first=None)])
    crud: TenantCRUD[CategoryMemory] = TenantCRUD(memory_spec)

    with pytest.raises(HTTPException) as ei:
        await crud.get(session, auth, 7)
    assert ei.value.status_code == 404
    assert ei.value.detail == "类目记忆不存在"


async def test_get_shared_row_allowed_with_shared_read(
    auth: AuthContext,
) -> None:
    """read_match=SHARED_READ 时查询放行共享行（SQL 含 OR tenant_id IS NULL）。"""
    spec = ResourceSpec(
        model=CategoryMemory,
        label="类目记忆",
        scopes=Scopes.rw("memory:read", "memory:write"),
        read_match=TenantMatch.SHARED_READ,
    )
    row = CategoryMemory(tenant_id=None, category="shared")
    session = FakeDBSession(results=[FakeResult(first=row)])
    crud: TenantCRUD[CategoryMemory] = TenantCRUD(spec)

    got = await crud.get(session, auth, 7)

    assert got is row
    assert "IS NULL" in last_stmt_sql(session).upper()


async def test_get_strict_shared_row_blocked(auth: AuthContext) -> None:
    """read_match=STRICT（默认）时共享行被谓词排除（SQL 无 IS NULL 放行）。"""
    spec = ResourceSpec(
        model=CategoryMemory,
        label="类目记忆",
        scopes=Scopes.rw("memory:read", "memory:write"),
    )
    session = FakeDBSession(results=[FakeResult(first=None)])
    crud: TenantCRUD[CategoryMemory] = TenantCRUD(spec)

    with pytest.raises(HTTPException) as ei:
        await crud.get(session, auth, 7)
    assert ei.value.status_code == 404
    assert "IS NULL" not in last_stmt_sql(session).upper()


async def test_get_scope_denied_403(
    memory_spec: ResourceSpec[CategoryMemory], auth_no_scope: AuthContext
) -> None:
    """scope 不足 403，且不发起任何 DB 访问。"""
    session = FakeDBSession()
    crud: TenantCRUD[CategoryMemory] = TenantCRUD(memory_spec)

    with pytest.raises(HTTPException) as ei:
        await crud.get(session, auth_no_scope, 7)
    assert ei.value.status_code == 403
    assert session.executed_stmts == []


# ============================================================================
# TenantCRUD.list / page
# ============================================================================


async def test_list_applies_tenant_and_order(auth: AuthContext) -> None:
    """list 注入租户条件与默认排序。"""
    spec = ResourceSpec(
        model=CategoryMemory,
        label="类目记忆",
        scopes=Scopes.rw("memory:read", "memory:write"),
        read_match=TenantMatch.SHARED_READ,
        default_order=(CategoryMemory.updated_at.desc(),),
    )
    rows = [CategoryMemory(tenant_id="tenant-a", category="c1")]
    session = FakeDBSession(results=[FakeResult(rows=rows)])
    crud: TenantCRUD[CategoryMemory] = TenantCRUD(spec)

    got = await crud.list(session, auth)

    assert got == rows
    assert_tenant_scoped(session.executed_stmts[0], "tenant_id", "tenant-a")
    assert "ORDER BY" in last_stmt_sql(session).upper()


async def test_list_include_shared_overrides_default(auth: AuthContext) -> None:
    """include_shared=True 阀门覆盖 spec.list_shared=False。"""
    spec = ResourceSpec(
        model=CategoryMemory,
        label="类目记忆",
        scopes=Scopes.rw("memory:read", "memory:write"),
        read_match=TenantMatch.SHARED_READ,
        list_shared=False,
    )
    session = FakeDBSession(results=[FakeResult(rows=[])])
    crud: TenantCRUD[CategoryMemory] = TenantCRUD(spec)

    await crud.list(session, auth, include_shared=True)

    assert "IS NULL" in last_stmt_sql(session).upper()


async def test_list_none_filter_skipped(
    memory_spec: ResourceSpec[CategoryMemory], auth: AuthContext
) -> None:
    """filters 值为 None 的键不产生 WHERE 条件。"""
    session = FakeDBSession(results=[FakeResult(rows=[])])
    crud: TenantCRUD[CategoryMemory] = TenantCRUD(memory_spec)

    await crud.list(session, auth, category=None)

    # 编译后绑定参数只应有租户条件，不应有 category 过滤参数
    params = session.executed_stmts[-1].compile().params
    assert not any("category" in str(key) for key in params)


async def test_list_order_by_whitelist_400(auth: AuthContext) -> None:
    """order_by 不在白名单抛 400。"""
    spec = ResourceSpec(
        model=CategoryMemory,
        label="类目记忆",
        scopes=Scopes.rw("memory:read", "memory:write"),
        orderable=(CategoryMemory.category,),
    )
    session = FakeDBSession()
    crud: TenantCRUD[CategoryMemory] = TenantCRUD(spec)

    with pytest.raises(HTTPException) as ei:
        await crud.list(session, auth, order_by="hacked_column")
    assert ei.value.status_code == 400


async def test_page_returns_count_and_items(
    memory_spec: ResourceSpec[CategoryMemory], auth: AuthContext
) -> None:
    """page 执行 count + items 两条查询，pages 向上取整。"""
    rows = [CategoryMemory(tenant_id="tenant-a", category="c1")]
    session = FakeDBSession(results=[FakeResult(scalar_one=5), FakeResult(rows=rows)])
    crud: TenantCRUD[CategoryMemory] = TenantCRUD(memory_spec)

    result = await crud.page(session, auth, pagination=PageParams(page=2, page_size=2))

    assert result.total == 5
    assert result.items == rows
    assert result.page == 2
    assert result.page_size == 2
    assert result.pages == 3
    assert "LIMIT" in last_stmt_sql(session).upper()
    assert "OFFSET" in last_stmt_sql(session).upper()


# ============================================================================
# TenantCRUD.create / update / delete
# ============================================================================


def last_stmt_where(session: FakeDBSession) -> str:
    """取最近一次 execute 语句的 WHERE 子句文本。"""
    whereclause = session.executed_stmts[-1].whereclause
    return "" if whereclause is None else str(whereclause)


class MemoryPayload(BaseModel):
    """测试用请求模型（与真实 Pydantic schema 同构）。"""

    model_config = {"extra": "allow"}

    tenant_id: str | None = None
    category: str | None = None
    summary: str | None = None


async def test_create_forces_tenant_id(
    memory_spec: ResourceSpec[CategoryMemory], auth: AuthContext
) -> None:
    """请求体伪造的 tenant_id 被丢弃，强制覆盖为调用方租户。"""
    session = FakeDBSession()
    crud: TenantCRUD[CategoryMemory] = TenantCRUD(memory_spec)

    await crud.create(session, auth, MemoryPayload(tenant_id="evil", category="c1"))

    added = session.added[0]
    assert added.tenant_id == "tenant-a"
    assert added.category == "c1"


async def test_create_conflict_translated_409(
    memory_spec: ResourceSpec[CategoryMemory], auth: AuthContext
) -> None:
    """IntegrityError → rollback → 409。"""
    session = FakeDBSession(flush_side_effect=IntegrityError("s", {}, Exception()))
    crud: TenantCRUD[CategoryMemory] = TenantCRUD(memory_spec)

    with pytest.raises(HTTPException) as ei:
        await crud.create(
            session,
            auth,
            MemoryPayload(category="dup"),
            conflict_detail="类目记忆已存在: tenant_id=tenant-a, category=dup",
        )
    assert ei.value.status_code == 409
    assert ei.value.detail == "类目记忆已存在: tenant_id=tenant-a, category=dup"
    assert session.rolled_back


async def test_create_conflict_callable_detail(
    memory_spec: ResourceSpec[CategoryMemory], auth: AuthContext
) -> None:
    """conflict_detail 为 callable 时收到 flush 后的实例。"""
    session = FakeDBSession(flush_side_effect=IntegrityError("s", {}, Exception()))
    crud: TenantCRUD[CategoryMemory] = TenantCRUD(memory_spec)

    with pytest.raises(HTTPException) as ei:
        await crud.create(
            session,
            auth,
            MemoryPayload(category="dup"),
            conflict_detail=lambda m: f"冲突: {m.category}",
        )
    assert ei.value.detail == "冲突: dup"


async def test_create_integrity_without_detail_reraises(
    memory_spec: ResourceSpec[CategoryMemory], auth: AuthContext
) -> None:
    """未给 conflict_detail 时 IntegrityError 原样抛出。"""
    err = IntegrityError("s", {}, Exception())
    session = FakeDBSession(flush_side_effect=err)
    crud: TenantCRUD[CategoryMemory] = TenantCRUD(memory_spec)

    with pytest.raises(IntegrityError):
        await crud.create(session, auth, MemoryPayload(category="dup"))


async def test_update_applies_exclude_unset(
    memory_spec: ResourceSpec[CategoryMemory], auth: AuthContext
) -> None:
    """PATCH 语义：exclude_unset 字段 setattr，未设置字段不动。"""
    row = CategoryMemory(tenant_id="tenant-a", category="c1", summary="old")
    session = FakeDBSession(results=[FakeResult(first=row)])
    crud: TenantCRUD[CategoryMemory] = TenantCRUD(memory_spec)

    # 只设置 summary；category 未传（exclude_unset 下不应出现在更新集里）
    got = await crud.update(session, auth, 7, MemoryPayload(summary="new"))

    assert got is row
    assert row.summary == "new"
    assert row.category == "c1"


async def test_update_strict_blocks_shared_row(auth: AuthContext) -> None:
    """写路径恒 STRICT：共享行即使 read_match=SHARED_READ 也不可更新（404）。"""
    spec = ResourceSpec(
        model=CategoryMemory,
        label="类目记忆",
        scopes=Scopes.rw("memory:read", "memory:write"),
        read_match=TenantMatch.SHARED_READ,
    )
    session = FakeDBSession(results=[FakeResult(first=None)])
    crud: TenantCRUD[CategoryMemory] = TenantCRUD(spec)

    with pytest.raises(HTTPException) as ei:
        await crud.update(session, auth, 7, MemoryPayload(summary="x"))
    assert ei.value.status_code == 404
    assert "IS NULL" not in last_stmt_sql(session).upper()


async def test_delete_returns_instance(
    memory_spec: ResourceSpec[CategoryMemory], auth: AuthContext
) -> None:
    """删除返回被删实例并 flush。"""
    row = CategoryMemory(tenant_id="tenant-a", category="c1")
    session = FakeDBSession(results=[FakeResult(first=row)])
    crud: TenantCRUD[CategoryMemory] = TenantCRUD(memory_spec)

    got = await crud.delete(session, auth, 7)

    assert got is row
    assert session.deleted == [row]
    assert session.flush_count == 1


# ============================================================================
# 逃生舱与内部构件
# ============================================================================


async def test_scoped_select_injects_tenant(
    memory_spec: ResourceSpec[CategoryMemory], auth: AuthContext
) -> None:
    """scoped_select 注入租户条件，续写后仍可断言。"""
    crud: TenantCRUD[CategoryMemory] = TenantCRUD(memory_spec)

    stmt = crud.scoped_select(auth).where(CategoryMemory.category == "c1")

    assert_tenant_scoped(stmt, "tenant_id", "tenant-a")


async def test_assert_tenant_scoped_negative() -> None:
    """缺租户条件时断言失败。"""
    stmt = select(CategoryMemory).where(CategoryMemory.category == "c1")
    with pytest.raises(AssertionError):
        assert_tenant_scoped(stmt, "tenant_id", "tenant-a")


async def test_non_tenant_table_no_predicate() -> None:
    """tenant_attr=None 的非租户表：查询不带租户条件。"""

    class _LocalBase(DeclarativeBase):
        pass

    class TagRow(_LocalBase):
        __tablename__ = "crud_test_tag_rows"

        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column()

    spec = ResourceSpec(
        model=TagRow,  # type: ignore[arg-type]
        label="标签",
        scopes=Scopes.uniform("tag:read"),
        tenant_attr=None,
    )
    session = FakeDBSession(results=[FakeResult(first=None)])
    crud: TenantCRUD[TagRow] = TenantCRUD(spec)  # type: ignore[arg-type]

    with pytest.raises(HTTPException) as ei:
        await crud.get(session, None, 1)
    assert ei.value.status_code == 404
    assert "tenant_id" not in last_stmt_sql(session)


def test_spec_fail_loud_without_tenant_column() -> None:
    """声明的租户列不存在时构造即抛 TypeError。"""

    class _LocalBase(DeclarativeBase):
        pass

    class BareRow(_LocalBase):
        __tablename__ = "crud_test_bare_rows"

        id: Mapped[int] = mapped_column(primary_key=True)

    with pytest.raises(TypeError):
        ResourceSpec(
            model=BareRow,  # type: ignore[arg-type]
            label="无租户列",
            scopes=Scopes.uniform("x:read"),
        )


# ============================================================================
# mask 与 PageResponse.build
# ============================================================================


def test_mask_secret_keeps_prefix_and_suffix() -> None:
    """前4后4保留，中间打码。"""
    assert mask_secret("sk-abcdef12345678") == "sk-a****5678"


def test_mask_secret_short_value_fully_masked() -> None:
    """长度不超过 2*keep 时整体打码，None/空串返回空串。"""
    assert mask_secret("short") == "****"
    assert mask_secret(None) == ""
    assert mask_secret("") == ""


def test_mask_values_masks_all_values() -> None:
    """键保留、值整体打码，不修改原映射。"""
    source = {"k1": "v1", "k2": "v2"}
    masked = mask_values(source)
    assert masked == {"k1": "***", "k2": "***"}
    assert source == {"k1": "v1", "k2": "v2"}
    assert mask_values(None) == {}


def test_page_response_build_ceils_pages() -> None:
    """pages 向上取整。"""
    r = PageResponse.build(["a", "b"], total=5, page=2, page_size=2)
    assert r.total == 5
    assert r.pages == 3
    assert r.page == 2
    assert r.page_size == 2
