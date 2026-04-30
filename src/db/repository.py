"""
通用异步 Repository。

Description:
    基于 SQLAlchemy 2.0 的通用异步 CRUD 封装。
    所有业务 Repository 继承此类。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

from typing import Any, Generic, Sequence, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.postgres import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """通用异步 Repository 基类。"""

    def __init__(self, model: type[ModelT], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get(self, id: int) -> ModelT | None:
        """按主键获取记录。

        Args:
            id: 主键值。

        Returns:
            模型实例，不存在时返回 None。
        """
        return await self.session.get(self.model, id)

    async def get_by_field(self, field: str, value: Any) -> ModelT | None:
        """按字段值获取单条记录。

        Args:
            field: 字段名。
            value: 字段值。

        Returns:
            模型实例，不存在时返回 None。
        """
        stmt = select(self.model).where(getattr(self.model, field) == value)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(self, **filters: Any) -> Sequence[ModelT]:
        """按条件查询多条记录。

        Args:
            **filters: 过滤条件键值对。

        Returns:
            模型实例列表。
        """
        stmt = select(self.model)
        for field, value in filters.items():
            stmt = stmt.where(getattr(self.model, field) == value)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, **kwargs: Any) -> ModelT:
        """创建新记录。

        Args:
            **kwargs: 字段键值对。

        Returns:
            创建的模型实例（已刷新）。
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, id: int, **kwargs: Any) -> ModelT | None:
        """更新记录。

        Args:
            id: 主键值。
            **kwargs: 要更新的字段。

        Returns:
            更新后的模型实例，不存在时返回 None。
        """
        instance = await self.get(id)
        if instance:
            for key, value in kwargs.items():
                setattr(instance, key, value)
            await self.session.flush()
            await self.session.refresh(instance)
        return instance

    async def delete(self, id: int) -> bool:
        """删除记录。

        Args:
            id: 主键值。

        Returns:
            是否成功删除。
        """
        instance = await self.get(id)
        if instance:
            await self.session.delete(instance)
            await self.session.flush()
            return True
        return False
