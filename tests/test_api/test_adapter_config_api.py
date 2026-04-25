"""适配器配置 API 测试。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from main import app

from src.db.listing_models import AdapterConfigPO


def _make_mock_po(**kwargs) -> MagicMock:
    """快速构造模拟 AdapterConfigPO。"""
    defaults = {
        "id": 1,
        "platform": "amazon",
        "shop_id": "default",
        "credentials": {"client_id": "test", "client_secret": "secret"},
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    po = MagicMock(spec=AdapterConfigPO)
    for k, v in defaults.items():
        setattr(po, k, v)
    return po


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """创建模拟数据库会话。"""
    session = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_get_db(mock_db_session: AsyncMock):
    """替换 get_db 上下文管理器。"""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_db_session)
    cm.__aexit__ = AsyncMock(return_value=None)
    with patch("src.api.router.adapter_config.get_db", return_value=cm):
        yield mock_db_session


class TestAdapterConfigAPI:
    """测试适配器配置 CRUD API。"""

    def test_create_adapter_config(self, client: TestClient, mock_get_db: AsyncMock) -> None:
        """测试创建配置。"""
        mock_po = _make_mock_po(id=1)
        mock_get_db.add = MagicMock()

        with patch("src.api.router.adapter_config.get_db") as mock_gdb:
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=mock_get_db)
            cm.__aexit__ = AsyncMock(return_value=None)
            mock_gdb.return_value = cm

            with patch.object(mock_get_db, "flush", AsyncMock()):
                with patch.object(mock_get_db, "refresh", AsyncMock()):
                    # 让 refresh 后 po 有 id
                    mock_get_db.add = MagicMock(side_effect=lambda po: setattr(po, "id", 1))

                    resp = client.post(
                        "/api/v1/listing/adapter-configs",
                        json={
                            "platform": "amazon",
                            "shop_id": "shop-001",
                            "credentials": {"client_id": "abc", "client_secret": "xyz"},
                            "is_active": True,
                        },
                    )
                    assert resp.status_code == 201
                    data = resp.json()
                    assert data["code"] == 200
                    assert data["data"]["platform"] == "amazon"
                    assert data["data"]["shop_id"] == "shop-001"

    def test_list_adapter_configs(self, client: TestClient) -> None:
        """测试配置列表。"""
        mock_po = _make_mock_po(id=1, platform="amazon", shop_id="default")
        mock_session = AsyncMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [mock_po]
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = exec_result

        with patch("src.api.router.adapter_config.get_db") as mock_gdb:
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=mock_session)
            cm.__aexit__ = AsyncMock(return_value=None)
            mock_gdb.return_value = cm

            resp = client.get("/api/v1/listing/adapter-configs")
            assert resp.status_code == 200
            data = resp.json()
            assert data["code"] == 200
            assert len(data["data"]) == 1

    def test_get_adapter_config(self, client: TestClient) -> None:
        """测试获取单个配置。"""
        mock_po = _make_mock_po(id=1, platform="ebay", shop_id="shop-2")
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_po

        with patch("src.api.router.adapter_config.get_db") as mock_gdb:
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=mock_session)
            cm.__aexit__ = AsyncMock(return_value=None)
            mock_gdb.return_value = cm

            resp = client.get("/api/v1/listing/adapter-configs/1")
            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["platform"] == "ebay"

    def test_get_adapter_config_not_found(self, client: TestClient) -> None:
        """测试获取不存在的配置。"""
        mock_session = AsyncMock()
        mock_session.get.return_value = None

        with patch("src.api.router.adapter_config.get_db") as mock_gdb:
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=mock_session)
            cm.__aexit__ = AsyncMock(return_value=None)
            mock_gdb.return_value = cm

            resp = client.get("/api/v1/listing/adapter-configs/999")
            assert resp.status_code == 200
            data = resp.json()
            assert data["code"] == 404

    def test_delete_adapter_config(self, client: TestClient) -> None:
        """测试删除配置。"""
        mock_po = _make_mock_po(id=1, platform="amazon", shop_id="default")
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_po
        mock_session.delete = AsyncMock()
        mock_session.flush = AsyncMock()

        with patch("src.api.router.adapter_config.get_db") as mock_gdb:
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=mock_session)
            cm.__aexit__ = AsyncMock(return_value=None)
            mock_gdb.return_value = cm

            resp = client.delete("/api/v1/listing/adapter-configs/1")
            assert resp.status_code == 200
            data = resp.json()
            assert data["code"] == 200
