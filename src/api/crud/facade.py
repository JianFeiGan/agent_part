"""
租户范围 CRUD 门面。

Description:
    把此前散落在各 router 的 scope 校验、实体加载、404 防枚举、租户过滤、
    防伪造、唯一冲突翻译收敛到一个深模块。调用者只学 ResourceSpec 声明
    与本类的方法签名；session 永远是显式第一参数（HTTP 路径经
    deps.SessionDep 注入，测试直传 FakeDBSession，无需字符串 patch）。

    事务边界归 session 生命周期：本类只 flush 不 commit；HTTP 路径上
    SessionDep（get_db）在请求成功退出时自动 commit、异常自动 rollback。

    不变量：
    I1 403 永远先于任何 DB 访问。
    I2 读路径（get/get_by/find_by/list/page/scoped_select）的租户谓词由
       本模块注入，经 facade 得到的行必然属于 resolve_tenant(auth)
       （或共享行，仅当对应策略允许）。
    I3 写路径（create/update/update_fields/delete）恒用 STRICT 租户匹配：
       共享行（tenant_id IS NULL）只读，接口上不可能误改误删。
    I4 create 的租户列由本模块用 resolve_tenant(auth) 强制覆盖，请求体
       同名字段被丢弃（防伪造）。
    I5 除 IntegrityError→409 翻译（仅当 conflict_detail 给定）外，异常
       原样传播；返回 ORM 实例，HTTP 响应包装不在本类职责内。
@author ganjianfei
@version 1.0.0
2026-09-08
"""

from collections.abc import Callable, Collection, Mapping, Sequence
from typing import Any, Generic, TypeVar

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.crud._internals import apply_order, build_list_stmt, tenant_predicate
from src.api.crud.access import require_scope, resolve_tenant
from src.api.crud.paging import PageParams, PageResult
from src.api.crud.spec import ResourceSpec, TenantMatch
from src.auth.context import AuthContext
from src.db.postgres import Base

ModelT = TypeVar("ModelT", bound=Base)

ConflictDetail = str | Callable[[Any], str] | None

_DATA_DUMP_EXCLUDE = ("tenant_id",)


class TenantCRUD(Generic[ModelT]):
    """单资源的租户范围 CRUD 门面。

    Attributes:
        spec: 资源声明（模型、label、scope 矩阵、租户策略等）。
    """

    def __init__(self, spec: ResourceSpec[ModelT]) -> None:
        """初始化门面。

        Args:
            spec: 资源声明。构造期即校验租户列存在性（fail-loud，
                早于任何请求）。
        """
        self.spec = spec

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _not_found(self) -> HTTPException:
        """构造 404 异常（不存在/跨租户/写共享行共用，防枚举）。"""
        detail = self.spec.not_found_detail or f"{self.spec.label}不存在"
        return HTTPException(status_code=404, detail=detail)

    def _scopes(self, override: Sequence[str] | None, action: str) -> Collection[str]:
        """解析本次调用的 scope 组：调用级覆盖优先，否则用 spec 分组。"""
        if override is not None:
            return override
        group: frozenset[str] = getattr(self.spec.scopes, action)
        return group

    def _tenant_id(self, auth: AuthContext | None) -> str:
        """解析租户 ID。"""
        return resolve_tenant(auth)

    def _read_stmt(
        self,
        auth: AuthContext | None,
        *,
        shared: bool,
        filters: Mapping[str, Any] | None = None,
    ) -> Select[tuple[ModelT]]:
        """构造带租户条件的基础读查询（匹配策略由调用方定）。"""
        stmt = build_list_stmt(
            self.spec.model,
            self.spec.tenant_attr,
            self._tenant_id(auth),
            shared=shared,
            filters=dict(filters or {}),
        )
        return stmt

    async def _flush_or_conflict(
        self,
        session: AsyncSession,
        instance: ModelT,
        conflict_detail: ConflictDetail,
    ) -> None:
        """flush + refresh，IntegrityError 按需翻译为 409。

        Args:
            session: 数据库会话。
            instance: 待 flush 的实例。
            conflict_detail: 给定则 IntegrityError → rollback + 409
                （str 直接用，callable 收到实例用于拼 detail）；None 则
                IntegrityError 原样抛出。

        Raises:
            HTTPException: 409 当唯一约束冲突且 conflict_detail 给定时。
        """
        try:
            await session.flush()
            await session.refresh(instance)
        except IntegrityError:
            await session.rollback()
            if conflict_detail is None:
                raise
            detail = conflict_detail(instance) if callable(conflict_detail) else conflict_detail
            raise HTTPException(status_code=409, detail=detail) from None

    async def _strict_get(
        self, session: AsyncSession, auth: AuthContext | None, obj_id: int
    ) -> ModelT:
        """按主键严格加载（STRICT 谓词；写路径专用，共享行一律 404）。"""
        stmt = select(self.spec.model).where(getattr(self.spec.model, "id") == obj_id)
        predicate = tenant_predicate(
            self.spec.model, self.spec.tenant_attr, self._tenant_id(auth), TenantMatch.STRICT
        )
        if predicate is not None:
            stmt = stmt.where(predicate)
        result = await session.execute(stmt)
        instance = result.scalars().first()
        if instance is None:
            raise self._not_found()
        return instance

    # ------------------------------------------------------------------
    # 读操作（scope 分组 read；匹配策略 spec.read_match / include_shared）
    # ------------------------------------------------------------------

    async def get(
        self,
        session: AsyncSession,
        auth: AuthContext | None,
        obj_id: int,
        *,
        scopes: Sequence[str] | None = None,
    ) -> ModelT:
        """按主键读取单条，不存在或跨租户（或 STRICT 下的共享行）返回 404。

        Args:
            session: 数据库会话。
            auth: 认证上下文（None 仅限直调路径）。
            obj_id: 主键。
            scopes: 覆盖 spec.scopes.read 的 scope 组。

        Returns:
            模型实例。

        Raises:
            HTTPException: 403 scope 不足；404 不存在或租户不匹配。
        """
        require_scope(auth, *self._scopes(scopes, "read"))
        stmt = select(self.spec.model).where(getattr(self.spec.model, "id") == obj_id)
        predicate = tenant_predicate(
            self.spec.model,
            self.spec.tenant_attr,
            self._tenant_id(auth),
            self.spec.read_match,
        )
        if predicate is not None:
            stmt = stmt.where(predicate)
        result = await session.execute(stmt)
        instance = result.scalars().first()
        if instance is None:
            raise self._not_found()
        return instance

    async def find_by(
        self,
        session: AsyncSession,
        auth: AuthContext | None,
        /,
        *,
        scopes: Sequence[str] | None = None,
        **filters: Any,
    ) -> ModelT | None:
        """按等值条件查询单条，可为 None（不抛 404）。

        Args:
            session: 数据库会话。
            auth: 认证上下文。
            scopes: 覆盖 spec.scopes.read 的 scope 组。
            **filters: 等值过滤条件；值为 None 的键跳过。

        Returns:
            模型实例或 None。
        """
        require_scope(auth, *self._scopes(scopes, "read"))
        stmt = self._read_stmt(
            auth, shared=self.spec.read_match is TenantMatch.SHARED_READ, filters=filters
        )
        stmt = stmt.limit(1)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def get_by(
        self,
        session: AsyncSession,
        auth: AuthContext | None,
        /,
        *,
        scopes: Sequence[str] | None = None,
        **filters: Any,
    ) -> ModelT:
        """find_by 的 404 版本：查不到即抛 404。

        Args:
            session: 数据库会话。
            auth: 认证上下文。
            scopes: 覆盖 spec.scopes.read 的 scope 组。
            **filters: 等值过滤条件。

        Returns:
            模型实例。

        Raises:
            HTTPException: 403 scope 不足；404 不存在或租户不匹配。
        """
        instance = await self.find_by(session, auth, scopes=scopes, **filters)
        if instance is None:
            raise self._not_found()
        return instance

    async def list(
        self,
        session: AsyncSession,
        auth: AuthContext | None,
        /,
        *,
        limit: int = 50,
        include_shared: bool | None = None,
        order_by: str | None = None,
        scopes: Sequence[str] | None = None,
        **filters: Any,
    ) -> Sequence[ModelT]:
        """按租户查询列表。

        Args:
            session: 数据库会话。
            auth: 认证上下文。
            limit: 返回数量上限。
            include_shared: 是否包含共享行；None 用 spec.list_shared。
            order_by: 客户端排序字段（需在 spec.orderable 白名单内）。
            scopes: 覆盖 spec.scopes.read 的 scope 组。
            **filters: 等值过滤条件；值为 None 的键跳过。

        Returns:
            模型实例列表。

        Raises:
            HTTPException: 403 scope 不足；400 排序字段不在白名单。
        """
        require_scope(auth, *self._scopes(scopes, "read"))
        shared = self.spec.list_shared if include_shared is None else include_shared
        stmt = self._read_stmt(auth, shared=shared, filters=filters)
        stmt = apply_order(stmt, self.spec.default_order, order_by, self.spec.orderable)
        stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def page(
        self,
        session: AsyncSession,
        auth: AuthContext | None,
        /,
        *,
        pagination: PageParams,
        include_shared: bool | None = None,
        order_by: str | None = None,
        scopes: Sequence[str] | None = None,
        **filters: Any,
    ) -> PageResult[ModelT]:
        """分页查询（count + 当前页）。

        Args:
            session: 数据库会话。
            auth: 认证上下文。
            pagination: 分页参数。
            include_shared: 是否包含共享行；None 用 spec.list_shared。
            order_by: 客户端排序字段。
            scopes: 覆盖 spec.scopes.read 的 scope 组。
            **filters: 等值过滤条件。

        Returns:
            PageResult，含 total 与当前页 items。

        Raises:
            HTTPException: 403 scope 不足；400 排序字段不在白名单。
        """
        require_scope(auth, *self._scopes(scopes, "read"))
        shared = self.spec.list_shared if include_shared is None else include_shared
        base = self._read_stmt(auth, shared=shared, filters=filters)
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = apply_order(base, self.spec.default_order, order_by, self.spec.orderable)
        stmt = stmt.offset(pagination.offset).limit(pagination.page_size)
        result = await session.execute(stmt)
        items = list(result.scalars().all())
        return PageResult(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    # ------------------------------------------------------------------
    # 写操作（恒 STRICT；scope 分组 create/update/delete）
    # ------------------------------------------------------------------

    async def create(
        self,
        session: AsyncSession,
        auth: AuthContext | None,
        data: BaseModel | Mapping[str, Any],
        *,
        extra: Mapping[str, Any] | None = None,
        conflict_detail: ConflictDetail = None,
        scopes: Sequence[str] | None = None,
    ) -> ModelT:
        """创建记录，租户列强制覆盖为调用方租户（防伪造）。

        Args:
            session: 数据库会话。
            auth: 认证上下文。
            data: Pydantic 请求模型或字段映射。
            extra: 服务端派生列（覆盖 data 同名字段）。
            conflict_detail: IntegrityError 的 409 文案；callable 收到
                flush 后的实例。None 则 IntegrityError 原样抛出。
            scopes: 覆盖 spec.scopes.create 的 scope 组。

        Returns:
            创建并刷新后的模型实例。

        Raises:
            HTTPException: 403 scope 不足；409 唯一约束冲突（当给定文案时）。
        """
        require_scope(auth, *self._scopes(scopes, "create"))
        fields: dict[str, Any] = {}
        if isinstance(data, BaseModel):
            fields.update(data.model_dump())
        else:
            fields.update(dict(data))
        if extra:
            fields.update(extra)
        for excluded in _DATA_DUMP_EXCLUDE:
            fields.pop(excluded, None)
        if self.spec.tenant_attr is not None:
            fields[self.spec.tenant_attr] = self._tenant_id(auth)
        instance = self.spec.model(**fields)
        session.add(instance)
        await self._flush_or_conflict(session, instance, conflict_detail)
        return instance

    async def update(
        self,
        session: AsyncSession,
        auth: AuthContext | None,
        obj_id: int,
        data: BaseModel | Mapping[str, Any],
        *,
        conflict_detail: ConflictDetail = None,
        scopes: Sequence[str] | None = None,
    ) -> ModelT:
        """PATCH 语义更新：Pydantic 用 exclude_unset，Mapping 全量应用。

        仅本租户的行可更新（共享行 404，不变量 I3）。

        Args:
            session: 数据库会话。
            auth: 认证上下文。
            obj_id: 主键。
            data: Pydantic 请求模型（exclude_unset）或字段映射。
            conflict_detail: IntegrityError 的 409 文案。
            scopes: 覆盖 spec.scopes.update 的 scope 组。

        Returns:
            更新并刷新后的模型实例。

        Raises:
            HTTPException: 403 scope 不足；404 不存在或租户不匹配；
                409 唯一约束冲突。
        """
        require_scope(auth, *self._scopes(scopes, "update"))
        instance = await self._strict_get(session, auth, obj_id)
        if isinstance(data, BaseModel):
            update_data = data.model_dump(exclude_unset=True)
        else:
            update_data = dict(data)
        for key, value in update_data.items():
            setattr(instance, key, value)
        await self._flush_or_conflict(session, instance, conflict_detail)
        return instance

    async def update_fields(
        self,
        session: AsyncSession,
        auth: AuthContext | None,
        obj_id: int,
        fields: Mapping[str, Any],
        *,
        conflict_detail: ConflictDetail = None,
        scopes: Sequence[str] | None = None,
    ) -> ModelT:
        """按字段映射直写更新（状态机字段等场景）。语义同 update。

        Args:
            session: 数据库会话。
            auth: 认证上下文。
            obj_id: 主键。
            fields: 要更新的字段映射。
            conflict_detail: IntegrityError 的 409 文案。
            scopes: 覆盖 spec.scopes.update 的 scope 组。

        Returns:
            更新并刷新后的模型实例。

        Raises:
            HTTPException: 403/404/409 同 update。
        """
        require_scope(auth, *self._scopes(scopes, "update"))
        instance = await self._strict_get(session, auth, obj_id)
        for key, value in fields.items():
            setattr(instance, key, value)
        await self._flush_or_conflict(session, instance, conflict_detail)
        return instance

    async def save(
        self,
        session: AsyncSession,
        instance: ModelT,
        *,
        conflict_detail: ConflictDetail = None,
    ) -> ModelT:
        """持久化已加载实例的修改（不做 scope/404 检查）。

        用于跨资源编排等已通过 facade 加载实例后的落库。

        Args:
            session: 数据库会话。
            instance: 已加载（通常经本类读方法）的实例。
            conflict_detail: IntegrityError 的 409 文案。

        Returns:
            刷新后的实例。

        Raises:
            HTTPException: 409 唯一约束冲突（当给定文案时）。
        """
        await self._flush_or_conflict(session, instance, conflict_detail)
        return instance

    async def delete(
        self,
        session: AsyncSession,
        auth: AuthContext | None,
        obj_id: int,
        *,
        scopes: Sequence[str] | None = None,
    ) -> ModelT:
        """删除记录，返回被删实例。仅本租户的行可删除（共享行 404）。

        Args:
            session: 数据库会话。
            auth: 认证上下文。
            obj_id: 主键。
            scopes: 覆盖 spec.scopes.delete 的 scope 组。

        Returns:
            被删除的实例（已 flush，尚未 commit）。

        Raises:
            HTTPException: 403 scope 不足；404 不存在或租户不匹配。
        """
        require_scope(auth, *self._scopes(scopes, "delete"))
        instance = await self._strict_get(session, auth, obj_id)
        await session.delete(instance)
        await session.flush()
        return instance

    # ------------------------------------------------------------------
    # 逃生舱（租户过滤由本模块注入；scope 由调用方显式 require_scope）
    # ------------------------------------------------------------------

    def scoped_select(self, auth: AuthContext | None) -> Select[tuple[ModelT]]:
        """构造注入了租户条件的基础查询，供非等值/聚合/向量等复杂查询续写。

        调用方必须自行 require_scope；测试应附 assert_tenant_scoped 断言。

        Args:
            auth: 认证上下文。

        Returns:
            已注入租户条件的 Select。
        """
        stmt = select(self.spec.model)
        predicate = tenant_predicate(
            self.spec.model,
            self.spec.tenant_attr,
            self._tenant_id(auth),
            self.spec.read_match,
        )
        if predicate is not None:
            stmt = stmt.where(predicate)
        return stmt

    async def fetch_all(
        self, session: AsyncSession, stmt: Select[tuple[ModelT]]
    ) -> Sequence[ModelT]:
        """执行逃生舱查询并取全部行。

        Args:
            session: 数据库会话。
            stmt: 经 scoped_select 续写的查询。

        Returns:
            模型实例列表。
        """
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def fetch_one(self, session: AsyncSession, stmt: Select[tuple[ModelT]]) -> ModelT | None:
        """执行逃生舱查询并取单行。

        Args:
            session: 数据库会话。
            stmt: 经 scoped_select 续写的查询。

        Returns:
            模型实例或 None。
        """
        result = await session.execute(stmt)
        return result.scalars().first()
