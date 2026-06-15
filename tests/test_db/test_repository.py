"""通用异步 Repository 测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import Column, Integer, String

from src.db.listing_models import ListingProductPO
from src.db.postgres import Base as _Base
from src.db.repository import BaseRepository, TenantRepository


class TestBaseRepository:
    """测试通用异步 Repository。"""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """创建模拟异步会话。"""
        return AsyncMock()

    @pytest.fixture
    def repo(self, mock_session: AsyncMock) -> BaseRepository[ListingProductPO]:
        """创建 Repository 实例。"""
        return BaseRepository(ListingProductPO, mock_session)

    @pytest.mark.asyncio
    async def test_get_existing(self, repo: BaseRepository, mock_session: AsyncMock) -> None:
        """测试获取已存在的记录。"""
        expected = ListingProductPO(sku="TEST-001", title="Test")
        mock_session.get.return_value = expected

        result = await repo.get(1)

        assert result == expected
        mock_session.get.assert_called_once_with(ListingProductPO, 1)

    @pytest.mark.asyncio
    async def test_get_not_found(self, repo: BaseRepository, mock_session: AsyncMock) -> None:
        """测试获取不存在的记录。"""
        mock_session.get.return_value = None

        result = await repo.get(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_create(self, repo: BaseRepository, mock_session: AsyncMock) -> None:
        """测试创建记录。"""
        instance = ListingProductPO(sku="NEW-001", title="New Product")
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        # create() 会构造新实例，我们需要验证返回
        result = await repo.create(sku="NEW-001", title="New Product")

        assert result.sku == "NEW-001"
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_existing(self, repo: BaseRepository, mock_session: AsyncMock) -> None:
        """测试更新已存在的记录。"""
        existing = ListingProductPO(sku="TEST-001", title="Old Title")
        mock_session.get.return_value = existing
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await repo.update(1, title="New Title")

        assert result is not None
        assert result.title == "New Title"

    @pytest.mark.asyncio
    async def test_update_not_found(self, repo: BaseRepository, mock_session: AsyncMock) -> None:
        """测试更新不存在的记录。"""
        mock_session.get.return_value = None

        result = await repo.update(999, title="Does Not Matter")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_existing(self, repo: BaseRepository, mock_session: AsyncMock) -> None:
        """测试删除已存在的记录。"""
        existing = ListingProductPO(sku="TEST-001", title="Test")
        mock_session.get.return_value = existing
        mock_session.delete = AsyncMock()
        mock_session.flush = AsyncMock()

        result = await repo.delete(1)

        assert result is True
        mock_session.delete.assert_called_once_with(existing)

    @pytest.mark.asyncio
    async def test_delete_not_found(self, repo: BaseRepository, mock_session: AsyncMock) -> None:
        """测试删除不存在的记录。"""
        mock_session.get.return_value = None

        result = await repo.delete(999)

        assert result is False

    @pytest.mark.asyncio
    async def test_list_no_filters(self, repo: BaseRepository, mock_session: AsyncMock) -> None:
        """测试无条件查询列表。"""
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [
            ListingProductPO(sku="A", title="A"),
            ListingProductPO(sku="B", title="B"),
        ]
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = exec_result

        result = await repo.list()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_with_filters(self, repo: BaseRepository, mock_session: AsyncMock) -> None:
        """测试带过滤条件查询列表。"""
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [ListingProductPO(sku="A", title="A")]
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = exec_result

        result = await repo.list(sku="A")

        assert len(result) == 1
        assert result[0].sku == "A"


# ---------------------------------------------------------------------------
# TenantRepository tests
# ---------------------------------------------------------------------------


class _ModelWithoutTenantId(_Base):
    """用于测试的模型——没有 tenant_id 列。"""

    __tablename__ = "_test_no_tenant"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))


class TestTenantRepository:
    """测试 TenantRepository 租户隔离功能。"""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """创建模拟异步会话。"""
        return AsyncMock()

    @pytest.fixture
    def tenant_repo(self, mock_session: AsyncMock) -> TenantRepository[ListingProductPO]:
        """创建 TenantRepository 实例（使用有 tenant_id 的模型）。"""
        return TenantRepository(ListingProductPO, mock_session)

    # ---- Negative test: model without tenant_id ----

    def test_model_without_tenant_id_raises_typeerror(self, mock_session: AsyncMock) -> None:
        """测试没有 tenant_id 的模型抛 TypeError。"""
        repo = TenantRepository(_ModelWithoutTenantId, mock_session)

        with pytest.raises(TypeError, match="tenant_id"):
            repo._tenant_filter()

    # ---- get_for_tenant ----

    @pytest.mark.asyncio
    async def test_get_for_tenant_found(
        self, tenant_repo: TenantRepository, mock_session: AsyncMock
    ) -> None:
        """测试按租户获取已存在的记录。"""
        expected = ListingProductPO(sku="SKU-1", title="Product 1")
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = expected
        mock_session.execute.return_value = exec_result

        result = await tenant_repo.get_for_tenant(1, "t-123")

        assert result == expected
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_for_tenant_not_found(
        self, tenant_repo: TenantRepository, mock_session: AsyncMock
    ) -> None:
        """测试按租户获取不存在的记录。"""
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = exec_result

        result = await tenant_repo.get_for_tenant(999, "t-123")

        assert result is None

    # ---- list_for_tenant ----

    @pytest.mark.asyncio
    async def test_list_for_tenant_no_extra_filters(
        self, tenant_repo: TenantRepository, mock_session: AsyncMock
    ) -> None:
        """测试按租户查询列表（无额外过滤）。"""
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [
            ListingProductPO(sku="A", title="A"),
            ListingProductPO(sku="B", title="B"),
        ]
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = exec_result

        result = await tenant_repo.list_for_tenant("t-123")

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_for_tenant_with_filters(
        self, tenant_repo: TenantRepository, mock_session: AsyncMock
    ) -> None:
        """测试按租户查询列表（带额外过滤）。"""
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [ListingProductPO(sku="A", title="A")]
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = exec_result

        result = await tenant_repo.list_for_tenant("t-123", sku="A")

        assert len(result) == 1
        assert result[0].sku == "A"

    # ---- create_for_tenant ----

    @pytest.mark.asyncio
    async def test_create_for_tenant(
        self, tenant_repo: TenantRepository, mock_session: AsyncMock
    ) -> None:
        """测试创建带租户的记录。"""
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await tenant_repo.create_for_tenant("t-123", sku="NEW", title="New")

        assert result.sku == "NEW"
        assert result.tenant_id == "t-123"
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once()
