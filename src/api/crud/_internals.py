"""
TenantCRUD 内部构件（私有测试面）。

Description:
    租户谓词构造、排序解析、租户过滤断言。下划线前缀表示不属于公共
    接口：供 facade 实现与单元测试使用，调用方不应 import。
    ``assert_tenant_scoped`` 是"忘记租户过滤一眼可见"的机制化：
    逃生舱路径（scoped_select）的每个端点测试都应附一行断言。
@author ganjianfei
@version 1.0.0
2026-09-08
"""

from typing import Any

from fastapi import HTTPException
from sqlalchemy import ColumnElement, Select, and_, or_, select
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql import visitors

from src.api.crud.spec import TenantMatch


def tenant_predicate(
    model: type[Any],
    tenant_attr: str | None,
    tenant_id: str,
    match: TenantMatch,
) -> ColumnElement[bool] | None:
    """构造租户过滤谓词。

    Args:
        model: SQLAlchemy 模型类。
        tenant_attr: 租户列名；None 表示非租户表，返回 None（不加条件）。
        tenant_id: 租户 ID。
        match: 匹配策略；SHARED_READ 额外放行 tenant_id IS NULL 的共享行。

    Returns:
        SQLAlchemy 布尔谓词，或 None（非租户表）。
    """
    if tenant_attr is None:
        return None
    col: InstrumentedAttribute[Any] = getattr(model, tenant_attr)
    if match is TenantMatch.SHARED_READ:
        return or_(col == tenant_id, col.is_(None))
    return col == tenant_id


def apply_order(
    stmt: Select[tuple[Any]],
    default_order: tuple[Any, ...],
    order_by: str | None,
    orderable: tuple[InstrumentedAttribute[Any], ...],
) -> Select[tuple[Any]]:
    """解析排序参数并附加到查询。

    Args:
        stmt: 基础查询。
        default_order: spec 声明的默认排序表达式。
        order_by: 客户端排序字段名，前缀 "-" 表示降序；None 用默认排序。
        orderable: 允许客户端引用的列白名单。

    Returns:
        附加排序后的查询。

    Raises:
        HTTPException: order_by 不在白名单时抛 400。
    """
    if order_by is not None:
        desc = order_by.startswith("-")
        name = order_by.lstrip("-")
        for col in orderable:
            if col.key == name or col.name == name:
                return stmt.order_by(col.desc() if desc else col.asc())
        raise HTTPException(status_code=400, detail=f"不支持的排序字段: {order_by}")
    if default_order:
        return stmt.order_by(*default_order)
    return stmt


def _collect_column_names(clause: Any) -> set[str]:
    """遍历 SQL 子句，收集其中引用的列名。

    Args:
        clause: SQLAlchemy 子句（如 whereclause）。

    Returns:
        列名集合。
    """
    names: set[str] = set()
    for node in visitors.iterate(clause):
        key = getattr(node, "key", None)
        name = getattr(node, "name", None)
        if isinstance(key, str):
            names.add(key)
        elif isinstance(name, str):
            names.add(name)
    return names


def assert_tenant_scoped(
    stmt: Select[tuple[Any]],
    tenant_attr: str,
    tenant_id: str,
) -> None:
    """断言查询的 WHERE 中包含租户过滤条件（测试辅助）。

    解析 stmt 的 whereclause，检查租户列出现在过滤条件中。供逃生舱路径
    （scoped_select + 自定义 where）的测试使用，一行锁死安全语义。

    Args:
        stmt: 待检查的查询。
        tenant_attr: 租户列名。
        tenant_id: 预期的租户 ID。

    Raises:
        AssertionError: WHERE 缺失或不含租户列。
    """
    whereclause = stmt.whereclause
    assert whereclause is not None, "查询缺少 WHERE 子句：租户未过滤！"
    names = _collect_column_names(whereclause)
    assert tenant_attr in names, f"WHERE 子句未包含租户列 {tenant_attr}: {whereclause}"
    compiled_params = stmt.compile().params
    assert tenant_id in compiled_params.values(), (
        f"WHERE 子句未绑定租户 {tenant_id}: {compiled_params}"
    )


def build_list_stmt(
    model: type[Any],
    tenant_attr: str | None,
    tenant_id: str,
    *,
    shared: bool,
    filters: dict[str, Any],
) -> Select[tuple[Any]]:
    """构造带租户条件与等值过滤的基础查询。

    filters 中值为 None 的键跳过（可选过滤参数的惯例）。

    Args:
        model: 模型类。
        tenant_attr: 租户列名（None 表示非租户表）。
        tenant_id: 租户 ID。
        shared: 是否包含共享行。
        filters: 等值过滤条件。

    Returns:
        SQLAlchemy Select。
    """
    stmt = select(model)
    predicate = tenant_predicate(
        model,
        tenant_attr,
        tenant_id,
        TenantMatch.SHARED_READ if shared else TenantMatch.STRICT,
    )
    if predicate is not None:
        stmt = stmt.where(predicate)
    for key, value in filters.items():
        if value is None:
            continue
        stmt = stmt.where(and_(getattr(model, key) == value))
    return stmt
