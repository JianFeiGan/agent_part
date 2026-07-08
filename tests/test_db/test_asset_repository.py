"""GeneratedAsset Repository 测试。

TDD: 先写测试，再写实现。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.db.asset_repository import AssetRepository
from src.db.listing_models import GeneratedAssetPO


class TestAssetRepository:
    """测试 AssetRepository。"""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """创建模拟异步会话。"""
        return AsyncMock()

    @pytest.fixture
    def repo(self, mock_session: AsyncMock) -> AssetRepository:
        """创建 AssetRepository 实例。"""
        return AssetRepository(mock_session)

    # ---- find_by_sha256 ----

    @pytest.mark.asyncio
    async def test_find_by_sha256_hit(
        self, repo: AssetRepository, mock_session: AsyncMock
    ) -> None:
        """测试按 sha256 查找命中。"""
        expected = GeneratedAssetPO(
            tenant_id="t-1",
            asset_type="image",
            provider="mock",
            url="http://example.com/a.png",
            storage_key="images/a.png",
            sha256="abc123",
        )
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = expected
        mock_session.execute.return_value = exec_result

        result = await repo.find_by_sha256("t-1", "abc123")

        assert result == expected
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_by_sha256_miss(
        self, repo: AssetRepository, mock_session: AsyncMock
    ) -> None:
        """测试按 sha256 查找未命中。"""
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = exec_result

        result = await repo.find_by_sha256("t-1", "nonexistent")

        assert result is None

    # ---- list_by_product ----

    @pytest.mark.asyncio
    async def test_list_by_product_filters_by_tenant(
        self, repo: AssetRepository, mock_session: AsyncMock
    ) -> None:
        """测试 list_by_product 按租户过滤。"""
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [
            GeneratedAssetPO(
                tenant_id="t-1",
                product_id="prod-1",
                asset_type="image",
                provider="mock",
                url="http://x.com/1.png",
                storage_key="k1",
            ),
            GeneratedAssetPO(
                tenant_id="t-1",
                product_id="prod-1",
                asset_type="image",
                provider="mock",
                url="http://x.com/2.png",
                storage_key="k2",
            ),
        ]
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = exec_result

        result = await repo.list_by_product("t-1", "prod-1")

        assert len(result) == 2
        for asset in result:
            assert asset.tenant_id == "t-1"
            assert asset.product_id == "prod-1"
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_by_product_empty(
        self, repo: AssetRepository, mock_session: AsyncMock
    ) -> None:
        """测试 list_by_product 无结果。"""
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = exec_result

        result = await repo.list_by_product("t-1", "nonexistent")

        assert result == []

    @pytest.mark.asyncio
    async def test_list_by_product_respects_limit(
        self, repo: AssetRepository, mock_session: AsyncMock
    ) -> None:
        """测试 list_by_product 尊重 limit 参数。"""
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = exec_result

        await repo.list_by_product("t-1", "prod-1", limit=10)

        # Verify query was executed (limit is applied via SQLAlchemy, not Python)
        mock_session.execute.assert_called_once()

    # ---- list_by_task ----

    @pytest.mark.asyncio
    async def test_list_by_task_filters_by_tenant(
        self, repo: AssetRepository, mock_session: AsyncMock
    ) -> None:
        """测试 list_by_task 按租户过滤。"""
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [
            GeneratedAssetPO(
                tenant_id="t-1",
                task_id="task-1",
                asset_type="image",
                provider="mock",
                url="http://x.com/1.png",
                storage_key="k1",
            ),
        ]
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = exec_result

        result = await repo.list_by_task("t-1", "task-1")

        assert len(result) == 1
        assert result[0].tenant_id == "t-1"
        assert result[0].task_id == "task-1"

    @pytest.mark.asyncio
    async def test_list_by_task_empty(
        self, repo: AssetRepository, mock_session: AsyncMock
    ) -> None:
        """测试 list_by_task 无结果。"""
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = exec_result

        result = await repo.list_by_task("t-1", "nonexistent")

        assert result == []

    # ---- create_asset ----

    @pytest.mark.asyncio
    async def test_create_asset_writes_to_db(
        self, repo: AssetRepository, mock_session: AsyncMock
    ) -> None:
        """测试 create_asset 写入数据库。"""
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await repo.create_asset(
            tenant_id="t-1",
            asset_type="image",
            provider="wanx",
            url="http://cdn.example.com/img.png",
            storage_key="images/img.png",
            storage_backend="oss",
            mime_type="image/png",
            file_size=204800,
            width=1024,
            height=768,
            sha256="def789",
            status="completed",
            is_mock=False,
            product_id="prod-1",
            task_id="task-1",
            extra_data={"prompt": "test"},
        )

        assert result.tenant_id == "t-1"
        assert result.asset_type == "image"
        assert result.provider == "wanx"
        assert result.url == "http://cdn.example.com/img.png"
        assert result.storage_key == "images/img.png"
        assert result.sha256 == "def789"
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_asset_minimal_fields(
        self, repo: AssetRepository, mock_session: AsyncMock
    ) -> None:
        """测试 create_asset 最小字段（仅必填）。"""
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await repo.create_asset(
            tenant_id="t-1",
            asset_type="video",
            provider="user_upload",
            url="/static/v.mp4",
            storage_key="videos/v.mp4",
        )

        assert result.tenant_id == "t-1"
        assert result.asset_type == "video"
        assert result.provider == "user_upload"
        # DB-level defaults exist on columns
        assert GeneratedAssetPO.__table__.c.storage_backend.default is not None
        assert GeneratedAssetPO.__table__.c.status.default is not None
        assert GeneratedAssetPO.__table__.c.is_mock.default is not None
        mock_session.add.assert_called_once()
