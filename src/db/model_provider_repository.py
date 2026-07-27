"""ModelProvider Repository。

Description:
    模型厂商配置专用 Repository，继承 TenantRepository，
    提供厂商配置的 CRUD、默认厂商查询、seed 预置等能力。
@author ganjianfei
@version 1.0.0
2026-07-22
"""

from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ModelProviderPO
from src.db.repository import TenantRepository


class ModelProviderRepository(TenantRepository[ModelProviderPO]):
    """ModelProvider 厂商配置 Repository。

    继承 TenantRepository，提供租户隔离的厂商配置 CRUD 操作，
    以及默认厂商查询、按类型列表查询等专用方法。

    Example:
        >>> repo = ModelProviderRepository(session)
        >>> default_llm = await repo.get_default("tenant-1", "llm")
        >>> providers = await repo.list_by_type("tenant-1", "image")
    """

    def __init__(self, session: AsyncSession) -> None:
        """初始化 ModelProviderRepository。

        Args:
            session: 异步数据库会话。
        """
        super().__init__(ModelProviderPO, session)

    async def get_default(
        self, tenant_id: str, provider_type: str
    ) -> ModelProviderPO | None:
        """获取指定类型的默认厂商配置。

        Args:
            tenant_id: 租户 ID。
            provider_type: 厂商类型（llm/image/video）。

        Returns:
            默认厂商配置，未找到时返回 None。
        """
        self._tenant_filter()
        stmt = (
            select(self.model)
            .where(self.model.tenant_id == tenant_id)
            .where(self.model.provider_type == provider_type)
            .where(self.model.is_default.is_(True))
            .where(self.model.is_active.is_(True))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_type(
        self, tenant_id: str, provider_type: str | None = None
    ) -> Sequence[ModelProviderPO]:
        """按类型查询厂商配置列表。

        Args:
            tenant_id: 租户 ID。
            provider_type: 可选的厂商类型过滤。

        Returns:
            厂商配置列表。
        """
        self._tenant_filter()
        stmt = (
            select(self.model)
            .where(self.model.tenant_id == tenant_id)
            .where(self.model.is_active.is_(True))
        )
        if provider_type:
            stmt = stmt.where(self.model.provider_type == provider_type)
        stmt = stmt.order_by(self.model.provider_type, self.model.name)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def set_default(
        self, tenant_id: str, provider_id: int, provider_type: str
    ) -> ModelProviderPO | None:
        """将指定厂商设为默认，同类型其他厂商取消默认。

        Args:
            tenant_id: 租户 ID。
            provider_id: 要设为默认的厂商 ID。
            provider_type: 厂商类型。

        Returns:
            更新后的厂商配置，不存在时返回 None。
        """
        # 先取消同类型的所有默认
        stmt = (
            update(self.model)
            .where(self.model.tenant_id == tenant_id)
            .where(self.model.provider_type == provider_type)
            .where(self.model.is_default.is_(True))
            .values(is_default=False)
        )
        await self.session.execute(stmt)

        # 设置指定厂商为默认
        po = await self.get_for_tenant(provider_id, tenant_id)
        if po is None or po.provider_type != provider_type:
            return None
        po.is_default = True
        await self.session.flush()
        await self.session.refresh(po)
        return po
