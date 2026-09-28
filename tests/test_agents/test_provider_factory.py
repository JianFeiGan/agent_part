"""ProviderFactory 行为测试（离线）。

覆盖数据库配置优先、Settings 兜底、协议/厂商不匹配时的显式失败三条主路径，
以及配置解析失败时降级到 Settings 的容错路径。不发起真实外部调用。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.clients.provider_factory import ProviderFactory
from src.clients.provider_result import (
    get_api_key_value,
    is_image_provider_configured,
    is_video_provider_configured,
)

# conftest 会把图片/视频工厂替换成返回 None 的 mock，这里捕获真实实现供用例还原。
_REAL_GET_IMAGE_PROVIDER = ProviderFactory.get_image_provider
_REAL_GET_VIDEO_PROVIDER = ProviderFactory.get_video_provider

# --------------------------------------------------------------------------- #
# 夹具
# --------------------------------------------------------------------------- #


def _config(**kwargs: Any) -> SimpleNamespace:
    """构造 ModelProviderPO 风格的厂商配置。"""
    defaults: dict[str, Any] = {
        "name": "sensenova",
        "protocol": "openai_compatible",
        "base_url": "https://token.sensenova.cn/v1",
        "api_key": {"key": "sk-test"},
        "extra_credentials": {},
        "default_model": "sensenova-6.7-flash-lite",
        "model_config_extra": {},
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _patch_repo(monkeypatch: pytest.MonkeyPatch, config: Any) -> MagicMock:
    """替换 ModelProviderRepository，返回替身类以便断言调用路径。"""
    repo_cls = MagicMock()
    instance = MagicMock()
    instance.get_for_tenant = AsyncMock(return_value=config)
    instance.get_default = AsyncMock(return_value=config)
    repo_cls.return_value = instance
    monkeypatch.setattr("src.db.model_provider_repository.ModelProviderRepository", repo_cls)
    return instance


def _restore_real_media_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    """还原 conftest 屏蔽的图片/视频工厂，验证真实构造路径。"""
    monkeypatch.setattr(
        ProviderFactory,
        "get_image_provider",
        _REAL_GET_IMAGE_PROVIDER,
    )
    monkeypatch.setattr(
        ProviderFactory,
        "get_video_provider",
        _REAL_GET_VIDEO_PROVIDER,
    )


class TestResolveFromDatabase:
    """数据库配置优先路径。"""

    async def test_llm_from_openai_compatible_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """openai_compatible 协议的 LLM 配置产出 OpenAICompatibleLLMProvider。"""
        _patch_repo(monkeypatch, _config())
        provider = await ProviderFactory.get_llm_provider(AsyncMock(), "tenant-1")

        assert provider is not None
        assert provider.is_available() is True
        model = provider.create_chat_model()
        assert model.model_name == "sensenova-6.7-flash-lite"
        assert model.openai_api_base == "https://token.sensenova.cn/v1"

    async def test_llm_config_extra_overrides_temperature(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """model_config_extra 中的 temperature/max_tokens 透传到模型。"""
        _patch_repo(
            monkeypatch, _config(model_config_extra={"temperature": 0.1, "max_tokens": 128})
        )
        provider = await ProviderFactory.get_llm_provider(AsyncMock(), "tenant-1")

        assert provider is not None
        model = provider.create_chat_model()
        assert model.temperature == 0.1
        assert model.max_tokens == 128

    async def test_llm_unsupported_protocol_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """未知 LLM 协议必须显式失败，不得静默兜底。"""
        _patch_repo(monkeypatch, _config(protocol="grpc"))
        with pytest.raises(ValueError, match="不支持的 LLM 协议"):
            await ProviderFactory.get_llm_provider(AsyncMock(), "tenant-1")

    async def test_image_openai_compatible_protocol(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """openai_compatible 图片配置产出 OpenAICompatibleImageProvider。"""
        _restore_real_media_factory(monkeypatch)
        _patch_repo(monkeypatch, _config(name="sensenova", protocol="openai_compatible"))
        provider = await ProviderFactory.get_image_provider(AsyncMock(), "tenant-1")

        assert provider is not None
        assert provider.is_available() is True

    async def test_image_dashscope_custom_rest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """name=dashscope 走 DashScopeImageClient。"""
        _restore_real_media_factory(monkeypatch)
        _patch_repo(
            monkeypatch,
            _config(name="dashscope", protocol="custom_rest", default_model="wanx-v1"),
        )
        provider = await ProviderFactory.get_image_provider(AsyncMock(), "tenant-1")

        assert provider is not None
        assert type(provider).__name__ == "DashScopeImageClient"

    async def test_image_unsupported_vendor_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """未知图片厂商显式失败。"""
        _restore_real_media_factory(monkeypatch)
        _patch_repo(monkeypatch, _config(name="unknown-vendor", protocol="custom_rest"))
        with pytest.raises(ValueError, match="不支持的图片厂商"):
            await ProviderFactory.get_image_provider(AsyncMock(), "tenant-1")

    async def test_video_kling_uses_extra_credentials(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Kling 视频配置从 extra_credentials 取 access/secret key。"""
        _restore_real_media_factory(monkeypatch)
        _patch_repo(
            monkeypatch,
            _config(
                name="kling",
                protocol="custom_rest",
                extra_credentials={"access_key": "ak-1", "secret_key": "sk-1"},
            ),
        )
        provider = await ProviderFactory.get_video_provider(AsyncMock(), "tenant-1")

        assert provider is not None
        assert provider.is_available() is True

    async def test_video_unsupported_vendor_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """未知视频厂商显式失败。"""
        _restore_real_media_factory(monkeypatch)
        _patch_repo(monkeypatch, _config(name="runway", protocol="custom_rest"))
        with pytest.raises(ValueError, match="不支持的视频厂商"):
            await ProviderFactory.get_video_provider(AsyncMock(), "tenant-1")

    async def test_provider_id_lookup_uses_get_for_tenant(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """任务级 provider_id 走 get_for_tenant 而非默认厂商查询。"""
        instance = _patch_repo(monkeypatch, _config())
        provider = await ProviderFactory.get_llm_provider(AsyncMock(), "tenant-1", provider_id=7)

        assert provider is not None
        instance.get_for_tenant.assert_awaited_once_with(7, "tenant-1")
        instance.get_default.assert_not_called()

    async def test_db_error_falls_back_to_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """数据库查询异常时降级到 Settings，不向上抛。"""
        instance = MagicMock()
        instance.get_default = AsyncMock(side_effect=RuntimeError("db down"))
        repo_cls = MagicMock(return_value=instance)
        monkeypatch.setattr("src.db.model_provider_repository.ModelProviderRepository", repo_cls)
        monkeypatch.setattr("src.clients.provider_factory.get_settings", lambda: SimpleNamespace())
        monkeypatch.setattr(
            "src.clients.openai_compatible_llm.get_settings",
            lambda: SimpleNamespace(dashscope_api_key="", sensenova_api_key="", llm_model="m"),
        )

        provider = await ProviderFactory.get_llm_provider(AsyncMock(), "tenant-1")

        assert provider is None


class TestSettingsFallback:
    """无数据库配置时的 Settings 兜底路径。"""

    @pytest.fixture
    def factory_settings(self, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
        """注入可控 Settings 到 provider_factory 与 LLM 兜底实现。"""
        settings = SimpleNamespace(
            sensenova_api_key="",
            sensenova_base_url="https://token.sensenova.cn/v1",
            dashscope_api_key="",
            kling_access_key="",
            kling_secret_key="",
            image_model="sensenova-u1-fast",
            llm_model="deepseek-v4-flash",
            video_model="kling-v1",
        )
        monkeypatch.setattr("src.clients.provider_factory.get_settings", lambda: settings)
        monkeypatch.setattr("src.clients.openai_compatible_llm.get_settings", lambda: settings)
        return settings

    async def test_llm_none_without_any_key(self, factory_settings: SimpleNamespace) -> None:
        """无任何 LLM Key 时返回 None。"""
        assert await ProviderFactory.get_llm_provider(None) is None

    async def test_llm_sensenova_preferred(self, factory_settings: SimpleNamespace) -> None:
        """同时配置 sensenova 与 dashscope 时优先 sensenova。"""
        factory_settings.sensenova_api_key = "sk-sense"
        factory_settings.dashscope_api_key = "sk-dash"

        provider = await ProviderFactory.get_llm_provider(None)
        assert provider is not None
        model = provider.create_chat_model()
        assert model.openai_api_base == "https://token.sensenova.cn/v1"

    async def test_llm_dashscope_fallback(self, factory_settings: SimpleNamespace) -> None:
        """仅 dashscope Key 时走通义千问兼容端点。"""
        factory_settings.dashscope_api_key = "sk-dash"

        provider = await ProviderFactory.get_llm_provider(None)
        assert provider is not None
        model = provider.create_chat_model()
        assert "dashscope" in model.openai_api_base

    async def test_image_none_without_key(
        self, factory_settings: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """无图片 Key 时返回 None（fail-closed）。"""
        _restore_real_media_factory(monkeypatch)
        assert await ProviderFactory.get_image_provider(None) is None

    async def test_image_sensenova_wins(
        self, factory_settings: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """sensenova Key 优先于 dashscope。"""
        _restore_real_media_factory(monkeypatch)
        factory_settings.sensenova_api_key = "sk-sense"
        factory_settings.dashscope_api_key = "sk-dash"

        provider = await ProviderFactory.get_image_provider(None)
        assert provider is not None
        assert type(provider).__name__ == "OpenAICompatibleImageProvider"

    async def test_image_dashscope_only(
        self, factory_settings: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """仅 dashscope Key 时产出 DashScopeImageClient。"""
        _restore_real_media_factory(monkeypatch)
        factory_settings.dashscope_api_key = "sk-dash"

        provider = await ProviderFactory.get_image_provider(None)
        assert provider is not None
        assert type(provider).__name__ == "DashScopeImageClient"

    async def test_video_none_without_keys(
        self, factory_settings: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """缺任一 Kling Key 都返回 None。"""
        _restore_real_media_factory(monkeypatch)
        factory_settings.kling_access_key = "ak-only"
        assert await ProviderFactory.get_video_provider(None) is None

    async def test_video_kling_when_both_keys(
        self, factory_settings: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """access + secret 齐备时产出 KlingVideoClient。"""
        _restore_real_media_factory(monkeypatch)
        factory_settings.kling_access_key = "ak"
        factory_settings.kling_secret_key = "sk"

        provider = await ProviderFactory.get_video_provider(None)
        assert provider is not None
        assert type(provider).__name__ == "KlingVideoClient"
        assert provider.is_available() is True


class TestApiKeyExtraction:
    """get_api_key_value 与配置判定辅助函数。"""

    def test_dict_with_key(self) -> None:
        """EncryptedJSONB 解密后的 dict 提取 key 字段。"""
        assert get_api_key_value({"key": "sk-abc"}) == "sk-abc"

    def test_dict_without_key(self) -> None:
        """dict 缺 key 字段时返回空串。"""
        assert get_api_key_value({"other": 1}) == ""

    def test_plain_string(self) -> None:
        """原始字符串原样返回。"""
        assert get_api_key_value("sk-plain") == "sk-plain"

    def test_empty_returns_empty(self) -> None:
        """None / 空值返回空串。"""
        assert get_api_key_value(None) == ""
        assert get_api_key_value("") == ""
        assert get_api_key_value({}) == ""

    def test_image_configured_via_effective_key(self) -> None:
        """有 effective_dashscope_api_key 属性时以其为准。"""
        settings = SimpleNamespace(effective_dashscope_api_key="sk-eff")
        assert is_image_provider_configured(settings) is True

    def test_image_configured_via_fallback_attrs(self) -> None:
        """无 effective 属性时回退检查 dashscope_api_key/qwen_api_key。"""
        assert is_image_provider_configured(SimpleNamespace(dashscope_api_key="sk"))
        assert is_image_provider_configured(SimpleNamespace(qwen_api_key="sk"))
        assert not is_image_provider_configured(SimpleNamespace())

    def test_video_configured_requires_both_keys(self) -> None:
        """视频配置判定要求 access/secret 同时非空。"""
        assert is_video_provider_configured(
            SimpleNamespace(kling_access_key="ak", kling_secret_key="sk")
        )
        assert not is_video_provider_configured(
            SimpleNamespace(kling_access_key="ak", kling_secret_key="")
        )
        assert not is_video_provider_configured(SimpleNamespace())
