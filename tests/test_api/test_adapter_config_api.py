"""适配器配置 API 测试。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from main import app

from src.config.settings import get_settings
from src.db.listing_models import AdapterConfigPO


def _make_mock_po(**kwargs) -> MagicMock:
    """快速构造模拟 AdapterConfigPO。"""
    defaults = {
        "id": 1,
        "platform": "amazon",
        "shop_id": "default",
        "tenant_id": "tenant-a",
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


@pytest.fixture(autouse=True)
def _disable_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """禁用认证用于测试。"""
    monkeypatch.setattr(get_settings(), "auth_enabled", False)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestAdapterConfigAPI:
    """测试适配器配置 CRUD API（含租户隔离）。"""

    def test_create_adapter_config(self, client: TestClient) -> None:
        """测试创建配置（带 tenant_id）。"""
        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.add = MagicMock()

        with patch("src.api.router.adapter_config.get_db") as mock_gdb:
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=mock_session)
            cm.__aexit__ = AsyncMock(return_value=None)
            mock_gdb.return_value = cm

            # Simulate refresh populating id
            def _refresh_side_effect(po: MagicMock) -> None:
                po.id = 1
                po.platform = "amazon"
                po.shop_id = "shop-001"
                po.tenant_id = "tenant-a"
                po.credentials = {"client_id": "abc", "client_secret": "xyz"}
                po.is_active = True
                po.created_at = datetime.now(timezone.utc)
                po.updated_at = datetime.now(timezone.utc)

            mock_session.refresh = AsyncMock(side_effect=_refresh_side_effect)

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
        """测试配置列表（仅当前租户）。"""
        mock_po = _make_mock_po(id=1, platform="amazon", shop_id="default", tenant_id="dev")
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
        """测试获取单个配置（仅当前租户）。"""
        mock_po = _make_mock_po(id=1, platform="ebay", shop_id="shop-2", tenant_id="dev")
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

    def test_get_adapter_config_wrong_tenant(self, client: TestClient) -> None:
        """测试获取其他租户的配置返回 404。"""
        mock_po = _make_mock_po(id=1, platform="amazon", shop_id="default", tenant_id="other-tenant")
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
            assert data["code"] == 404

    def test_delete_adapter_config(self, client: TestClient) -> None:
        """测试删除配置。"""
        mock_po = _make_mock_po(id=1, platform="amazon", shop_id="default", tenant_id="dev")
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

    def test_delete_adapter_config_wrong_tenant(self, client: TestClient) -> None:
        """测试删除其他租户的配置返回 404。"""
        mock_po = _make_mock_po(id=1, platform="amazon", shop_id="default", tenant_id="other-tenant")
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_po

        with patch("src.api.router.adapter_config.get_db") as mock_gdb:
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=mock_session)
            cm.__aexit__ = AsyncMock(return_value=None)
            mock_gdb.return_value = cm

            resp = client.delete("/api/v1/listing/adapter-configs/1")
            assert resp.status_code == 200
            data = resp.json()
            assert data["code"] == 404
