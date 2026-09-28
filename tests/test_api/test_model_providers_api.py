"""模型厂商管理 API 行为测试。

直接调用 handler + FakeSession 注入，验证 CRUD、默认厂商切换、
脱敏返回与连接测试的成败分支。所有厂商探测均 patch，不发起真实外部调用。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest import mock

import pytest

from src.api.router.model_providers import (
    create_model_provider,
    delete_model_provider,
    get_model_provider,
    list_model_providers,
    set_default_model_provider,
    update_model_provider,
)
from src.api.router.model_providers import (
    test_model_provider as check_provider_connection,
)
from src.api.schema.model_provider import (
    ModelProviderCreateRequest,
    ModelProviderTestRequest,
    ModelProviderUpdateRequest,
)
from src.auth.context import AuthContext

# --------------------------------------------------------------------------- #
# 夹具
# --------------------------------------------------------------------------- #


@pytest.fixture
def auth() -> AuthContext:
    """租户 A 的认证上下文。"""
    return AuthContext(tenant_id="tenant-a", user_id="user-a", scopes=[])


def _po(**kwargs: Any) -> Any:
    """构造 ModelProviderPO 风格对象。"""
    obj = mock.MagicMock()
    defaults: dict[str, Any] = {
        "id": 1,
        "tenant_id": "tenant-a",
        "name": "sensenova",
        "display_name": "商汤科技",
        "provider_type": "llm",
        "base_url": "https://token.sensenova.cn/v1",
        "api_key": {"key": "sk-abcdefghijkl"},
        "extra_credentials": {},
        "default_model": "deepseek-v4-flash",
        "supported_models": ["deepseek-v4-flash"],
        "model_config_extra": {},
        "protocol": "openai_compatible",
        "is_active": True,
        "is_default": False,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


class FakeSession:
    """模拟 AsyncSession（仅覆盖路由用到的方法）。"""

    def __init__(self, *, get_return: Any = None) -> None:
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.flushed = 0
        self.refreshed: list[Any] = []
        self._get_return = get_return

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    async def flush(self) -> None:
        self.flushed += 1

    async def refresh(self, obj: Any) -> None:
        self.refreshed.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = 1
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(UTC)
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = datetime.now(UTC)


def _patch_repo(monkeypatch: pytest.MonkeyPatch, **methods: Any) -> mock.MagicMock:
    """替换 ModelProviderRepository，返回替身实例。"""
    instance = mock.MagicMock()
    instance.list_by_type = mock.AsyncMock(return_value=methods.get("list_by_type", []))
    instance.get_for_tenant = mock.AsyncMock(return_value=methods.get("get_for_tenant"))
    instance.set_default = mock.AsyncMock(return_value=methods.get("set_default"))
    repo_cls = mock.MagicMock(return_value=instance)
    monkeypatch.setattr("src.api.router.model_providers.ModelProviderRepository", repo_cls)
    return instance


class TestListAndGet:
    """列表与详情。"""

    async def test_list_returns_masked_keys(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """列表返回脱敏 API Key，不泄漏明文。"""
        _patch_repo(monkeypatch, list_by_type=[_po(), _po(id=2, api_key="plain-key")])

        resp = await list_model_providers(auth, FakeSession(), provider_type=None)

        assert resp.code == 200
        assert len(resp.data) == 2
        for item in resp.data:
            assert "abcdefghijkl" not in item.api_key_masked
            assert "plain-key" not in item.api_key_masked

    async def test_list_passes_provider_type_filter(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """provider_type 透传到仓储层。"""
        instance = _patch_repo(monkeypatch, list_by_type=[])
        await list_model_providers(auth, FakeSession(), provider_type="image")

        instance.list_by_type.assert_awaited_once_with("tenant-a", "image")

    async def test_get_missing_returns_404_payload(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """跨租户/不存在统一 404，防枚举。"""
        _patch_repo(monkeypatch, get_for_tenant=None)

        resp = await get_model_provider(99, auth, FakeSession())

        assert resp.code == 404
        assert resp.data is None

    async def test_get_own_tenant(self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext) -> None:
        """本租户命中返回脱敏详情。"""
        _patch_repo(monkeypatch, get_for_tenant=_po())

        resp = await get_model_provider(1, auth, FakeSession())

        assert resp.code == 200
        assert resp.data is not None
        assert resp.data.name == "sensenova"


class TestCreateUpdateDelete:
    """创建 / 更新 / 删除。"""

    async def test_create_stores_key_and_masks_response(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """创建时明文 Key 包装为 {"key": ...} 存储，响应脱敏。"""
        session = FakeSession()
        request = ModelProviderCreateRequest(
            name="dashscope",
            display_name="阿里云通义",
            provider_type="llm",
            base_url="https://dashscope.example/v1",
            api_key="sk-secret-value",
            default_model="qwen-plus",
        )

        resp = await create_model_provider(request, auth, session)

        assert resp.code == 200
        assert len(session.added) == 1
        stored = session.added[0]
        assert stored.api_key == {"key": "sk-secret-value"}
        assert stored.tenant_id == "tenant-a"
        assert "sk-secret-value" not in resp.data.api_key_masked

    async def test_create_without_key_uses_empty_dict(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """未传 Key 时存空 dict，供用户后续配置。"""
        session = FakeSession()
        request = ModelProviderCreateRequest(
            name="kling",
            display_name="可灵AI",
            provider_type="video",
            base_url="https://api.klingai.com",
            default_model="kling-v1",
        )

        await create_model_provider(request, auth, session)

        assert session.added[0].api_key == {"key": ""}

    async def test_create_as_default_clears_previous(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """设为默认时先清除同类型旧默认。"""
        instance = _patch_repo(monkeypatch)
        session = FakeSession()
        request = ModelProviderCreateRequest(
            name="sensenova",
            display_name="商汤科技",
            provider_type="llm",
            base_url="https://x/v1",
            default_model="m",
            is_default=True,
        )

        await create_model_provider(request, auth, session)

        instance.set_default.assert_awaited_once_with("tenant-a", 0, "llm")

    async def test_update_missing_returns_404(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """更新不存在的厂商返回 404。"""
        _patch_repo(monkeypatch, get_for_tenant=None)

        resp = await update_model_provider(
            99, ModelProviderUpdateRequest(display_name="x"), auth, FakeSession()
        )

        assert resp.code == 404

    async def test_update_applies_only_provided_fields(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """仅更新传入字段，其余保持不变。"""
        po = _po(display_name="旧名字", base_url="https://old/v1")
        _patch_repo(monkeypatch, get_for_tenant=po)
        session = FakeSession()
        request = ModelProviderUpdateRequest(
            display_name="新名字",
            api_key="sk-new",
            is_active=False,
        )

        resp = await update_model_provider(1, request, auth, session)

        assert resp.code == 200
        assert po.display_name == "新名字"
        assert po.api_key == {"key": "sk-new"}
        assert po.is_active is False
        assert po.base_url == "https://old/v1"

    async def test_delete_missing_returns_404(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """删除不存在的厂商返回 404。"""
        _patch_repo(monkeypatch, get_for_tenant=None)

        resp = await delete_model_provider(99, auth, FakeSession())

        assert resp.code == 404

    async def test_delete_removes_row(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """删除命中时调用 session.delete。"""
        po = _po()
        _patch_repo(monkeypatch, get_for_tenant=po)
        session = FakeSession()

        resp = await delete_model_provider(1, auth, session)

        assert resp.code == 200
        assert session.deleted == [po]


class TestSetDefault:
    """设为默认厂商。"""

    async def test_missing_returns_404(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """厂商不存在返回 404。"""
        _patch_repo(monkeypatch, get_for_tenant=None)

        resp = await set_default_model_provider(99, auth, FakeSession())

        assert resp.code == 404

    async def test_repo_reject_returns_400(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """类型不匹配等仓储拒绝返回 400。"""
        _patch_repo(monkeypatch, get_for_tenant=_po(), set_default=None)

        resp = await set_default_model_provider(1, auth, FakeSession())

        assert resp.code == 400

    async def test_success(self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext) -> None:
        """设置成功返回更新后的脱敏配置。"""
        updated = _po(is_default=True)
        instance = _patch_repo(monkeypatch, get_for_tenant=_po(), set_default=updated)

        resp = await set_default_model_provider(1, auth, FakeSession())

        assert resp.code == 200
        assert resp.data.is_default is True
        instance.set_default.assert_awaited_once_with("tenant-a", 1, "llm")


class TestTestConnection:
    """连接测试。"""

    async def test_missing_returns_404(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """厂商不存在返回 404。"""
        _patch_repo(monkeypatch, get_for_tenant=None)

        resp = await check_provider_connection(99, ModelProviderTestRequest(), auth, FakeSession())

        assert resp.code == 404

    async def test_missing_api_key_reports_failure(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """未配置 Key 时返回 success=False 而非异常。"""
        _patch_repo(monkeypatch, get_for_tenant=_po(api_key={}))

        resp = await check_provider_connection(1, None, auth, FakeSession())

        assert resp.data.success is False
        assert "API Key 未配置" in resp.data.message

    async def test_llm_success(self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext) -> None:
        """LLM 测试成功时返回延迟。"""

        class _FakeLLM:
            async def ainvoke(self, _prompt: str) -> str:
                return "ok"

        class _FakeProvider:
            def __init__(self, **_kw: Any) -> None:
                pass

            def create_chat_model(self) -> _FakeLLM:
                return _FakeLLM()

        monkeypatch.setattr(
            "src.clients.openai_compatible_llm.OpenAICompatibleLLMProvider",
            _FakeProvider,
        )
        _patch_repo(monkeypatch, get_for_tenant=_po(provider_type="llm"))

        resp = await check_provider_connection(
            1, ModelProviderTestRequest(model="qwen-plus"), auth, FakeSession()
        )

        assert resp.data.success is True
        assert resp.data.latency_ms is not None

    async def test_llm_failure_reports_error(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """LLM 调用异常被映射为 success=False。"""

        class _BoomProvider:
            def __init__(self, **_kw: Any) -> None:
                pass

            def create_chat_model(self) -> Any:
                raise RuntimeError("connect refused")

        monkeypatch.setattr(
            "src.clients.openai_compatible_llm.OpenAICompatibleLLMProvider",
            _BoomProvider,
        )
        _patch_repo(monkeypatch, get_for_tenant=_po(provider_type="llm"))

        resp = await check_provider_connection(1, None, auth, FakeSession())

        assert resp.data.success is False
        assert "连接测试失败" in resp.data.message

    async def test_image_unavailable_reports_failure(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """图片 Provider 不可用时返回 success=False。"""

        class _Unavailable:
            def __init__(self, **_kw: Any) -> None:
                pass

            def is_available(self) -> bool:
                return False

        monkeypatch.setattr(
            "src.clients.provider_factory._create_image_from_config",
            lambda _cfg, **_kw: _Unavailable(),
        )
        _patch_repo(monkeypatch, get_for_tenant=_po(provider_type="image"))

        resp = await check_provider_connection(1, None, auth, FakeSession())

        assert resp.data.success is False

    async def test_video_available_reports_success(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """视频 Provider 可用时返回 success=True。"""

        class _Available:
            def __init__(self, **_kw: Any) -> None:
                pass

            def is_available(self) -> bool:
                return True

        monkeypatch.setattr(
            "src.clients.provider_factory._create_video_from_config",
            lambda _cfg, **_kw: _Available(),
        )
        _patch_repo(monkeypatch, get_for_tenant=_po(provider_type="video"))

        resp = await check_provider_connection(1, None, auth, FakeSession())

        assert resp.data.success is True

    async def test_unknown_provider_type_reports_failure(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """未知厂商类型返回 success=False。"""
        _patch_repo(monkeypatch, get_for_tenant=_po(provider_type="audio"))

        resp = await check_provider_connection(1, None, auth, FakeSession())

        assert resp.data.success is False
