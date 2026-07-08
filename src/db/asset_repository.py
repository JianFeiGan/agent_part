"""GeneratedAsset Repository。

Description:
    资产专用 Repository，继承 TenantRepository，提供资产查询、创建和去重能力。
@author ganjianfei
@version 1.0.0
2026-06-19
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.listing_models import GeneratedAssetPO
from src.db.repository import TenantRepository


class AssetRepository(TenantRepository[GeneratedAssetPO]):
    """GeneratedAsset 资产 Repository。

    继承 TenantRepository，提供租户隔离的资产 CRUD 操作，
    以及去重查询、按商品/任务列表查询等专用方法。

    Example:
        >>> repo = AssetRepository(session)
        >>> asset = await repo.find_by_sha256("tenant-1", "abc123")
        >>> assets = await repo.list_by_product("tenant-1", "prod-001")
    """

    def __init__(self, session: AsyncSession) -> None:
        """初始化 AssetRepository。

        Args:
            session: 异步数据库会话。
        """
        super().__init__(GeneratedAssetPO, session)

    async def find_by_sha256(
        self, tenant_id: str, sha256: str
    ) -> GeneratedAssetPO | None:
        """按 sha256 哈希查找资产（去重查询）。

        Args:
            tenant_id: 租户 ID。
            sha256: 文件 SHA256 哈希值。

        Returns:
            匹配的资产实例，未找到时返回 None。
        """
        self._tenant_filter()
        stmt = (
            select(self.model)
            .where(self.model.tenant_id == tenant_id)
            .where(self.model.sha256 == sha256)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_product(
        self, tenant_id: str, product_id: str, limit: int = 50
    ) -> Sequence[GeneratedAssetPO]:
        """按商品 ID 查询资产列表。

        Args:
            tenant_id: 租户 ID。
            product_id: 商品 ID。
            limit: 最大返回数量（默认 50）。

        Returns:
            资产实例列表。
        """
        self._tenant_filter()
        stmt = (
            select(self.model)
            .where(self.model.tenant_id == tenant_id)
            .where(self.model.product_id == product_id)
            .order_by(self.model.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_task(
        self, tenant_id: str, task_id: str
    ) -> Sequence[GeneratedAssetPO]:
        """按任务 ID 查询资产列表。

        Args:
            tenant_id: 租户 ID。
            task_id: 任务 ID。

        Returns:
            资产实例列表。
        """
        self._tenant_filter()
        stmt = (
            select(self.model)
            .where(self.model.tenant_id == tenant_id)
            .where(self.model.task_id == task_id)
            .order_by(self.model.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_asset(self, tenant_id: str, **kwargs: object) -> GeneratedAssetPO:
        """创建资产记录。

        Args:
            tenant_id: 租户 ID。
            **kwargs: 资产字段键值对。

        Returns:
            创建的资产实例（已刷新）。
        """
        return await self.create_for_tenant(tenant_id, **kwargs)
