"""
资源声明规格。

Description:
    定义 TenantCRUD 所需的资源级声明：模型、资源名、scope 矩阵、
    租户匹配策略、默认排序。所有字段是"资源级不变的业务事实"，
    调用级偶变的参数（include_shared、conflict_detail 等）在 facade
    方法上以阀门参数形式提供，不进 spec。
@author ganjianfei
@version 1.0.0
2026-09-08
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, TypeVar

from sqlalchemy import ColumnElement
from sqlalchemy.orm import InstrumentedAttribute

from src.db.postgres import Base

ModelT = TypeVar("ModelT", bound=Base)


class TenantMatch(StrEnum):
    """读路径的租户匹配策略。

    Attributes:
        STRICT: 仅匹配本租户行（``tenant_id == :t``）。
        SHARED_READ: 额外放行共享行（``tenant_id == :t OR tenant_id IS NULL``）。
    """

    STRICT = "strict"
    SHARED_READ = "shared_read"


@dataclass(frozen=True, slots=True)
class Scopes:
    """按操作分组的 scope 需求矩阵。

    每个 facade 方法在执行前检查对应分组的 scope（any-of 语义）。
    """

    read: frozenset[str]
    create: frozenset[str]
    update: frozenset[str]
    delete: frozenset[str]

    @classmethod
    def rw(cls, read: str, write: str) -> "Scopes":
        """读写两分组的便捷构造：read 用于读方法，write 用于全部写方法。

        Args:
            read: 读操作 scope。
            write: 写操作 scope。

        Returns:
            Scopes 实例。
        """
        return cls(
            read=frozenset({read, write}),
            create=frozenset({write}),
            update=frozenset({write}),
            delete=frozenset({write}),
        )

    @classmethod
    def uniform(cls, *scopes: str) -> "Scopes":
        """全分组同一组 scope。

        Args:
            *scopes: 一个或多个 scope 名称。

        Returns:
            Scopes 实例。
        """
        return cls(
            read=frozenset(scopes),
            create=frozenset(scopes),
            update=frozenset(scopes),
            delete=frozenset(scopes),
        )


@dataclass(frozen=True, slots=True)
class ResourceSpec(Generic[ModelT]):
    """资源的声明式规格，TenantCRUD 的唯一构造参数。

    Attributes:
        model: SQLAlchemy 模型类。
        label: 资源中文名，用于 404 文案与日志（如 "类目记忆"）。
        scopes: scope 需求矩阵。
        tenant_attr: 租户列名；None 表示非租户表（查询不加租户条件）。
        read_match: 单条读取（get/get_by/find_by）的租户匹配策略。
            写路径恒为 STRICT，不受此字段影响（不变量）。
        list_shared: list/page 是否默认包含共享行；可被每调用的
            include_shared 阀门覆盖。
        default_order: 默认排序表达式，如 ``(CategoryMemory.updated_at.desc(),)``。
        orderable: 允许客户端 order_by 引用的列白名单。
        not_found_detail: 404 detail 文案；None 则用 ``f"{label}不存在"``。
    """

    model: type[ModelT]
    label: str
    scopes: Scopes
    tenant_attr: str | None = "tenant_id"
    read_match: TenantMatch = TenantMatch.STRICT
    list_shared: bool = False
    default_order: tuple[ColumnElement[Any] | InstrumentedAttribute[Any], ...] = field(default=())
    orderable: tuple[InstrumentedAttribute[Any], ...] = field(default=())
    not_found_detail: str | None = None

    def __post_init__(self) -> None:
        """构造期 fail-loud 校验。

        Raises:
            TypeError: 声明了 tenant_attr 但模型没有该列。
        """
        if self.tenant_attr is not None and self.tenant_attr not in self.model.__table__.columns:
            raise TypeError(
                f"Model '{self.model.__name__}' does not have a "
                f"'{self.tenant_attr}' column required by ResourceSpec."
            )
