"""
分页参数与分页结果。

Description:
    统一此前 3 种并存的分页风格：PageParams 作为 FastAPI 依赖（query 绑定）
    或纯值对象（body 传入）均可；PageResult 承载 facade.page() 的结果。
@author ganjianfei
@version 1.0.0
2026-09-08
"""

from dataclasses import dataclass
from math import ceil
from typing import Annotated, Generic, TypeVar

from fastapi import Depends, Query

from src.db.postgres import Base

ModelT = TypeVar("ModelT", bound=Base)


@dataclass(frozen=True, slots=True)
class PageParams:
    """分页请求参数（页码制）。

    Attributes:
        page: 页码，从 1 开始。
        page_size: 每页条数。
    """

    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        """SQL offset 值。"""
        return (self.page - 1) * self.page_size


def page_params_dep(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
) -> PageParams:
    """FastAPI 依赖：从 query 参数构造 PageParams。

    Args:
        page: 页码。
        page_size: 每页条数。

    Returns:
        PageParams 实例。
    """
    return PageParams(page=page, page_size=page_size)


PageParamsDep = Annotated[PageParams, Depends(page_params_dep)]


@dataclass(frozen=True, slots=True)
class PageResult(Generic[ModelT]):
    """分页查询结果（ORM 实例 + 分页元数据）。

    Attributes:
        items: 当前页的模型实例列表。
        total: 满足条件的总记录数。
        page: 当前页码。
        page_size: 每页条数。
    """

    items: list[ModelT]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        """总页数（向上取整）。"""
        if self.page_size <= 0:
            return 0
        return ceil(self.total / self.page_size)
