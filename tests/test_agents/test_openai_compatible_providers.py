"""OpenAI 兼容 Provider（LLM / 图片）行为测试（离线）。

覆盖尺寸映射、url/b64 两种图片提取路径、失败映射到 ProviderUnavailableError，
以及 SettingsFallbackLLMProvider 的厂商优先级与未配置失败。
"""

from __future__ import annotations

import base64
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from src.clients.openai_compatible_image import OpenAICompatibleImageProvider
from src.clients.openai_compatible_llm import (
    OpenAICompatibleLLMProvider,
    SettingsFallbackLLMProvider,
)
from src.clients.provider_result import ProviderUnavailableError

# --------------------------------------------------------------------------- #
# 夹具
# --------------------------------------------------------------------------- #


class _FakeResponse:
    """极简 httpx 响应替身。"""

    def __init__(
        self,
        *,
        json_data: dict[str, Any] | None = None,
        content: bytes = b"",
        status_code: int = 200,
    ) -> None:
        self._json = json_data
        self.content = content
        self.status_code = status_code
        self.text = str(json_data)

    def json(self) -> dict[str, Any]:
        if self._json is None:
            raise ValueError("no json body")
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("status", request=AsyncMock(), response=AsyncMock())


def _provider(http: AsyncMock) -> OpenAICompatibleImageProvider:
    """构造注入假 httpx 的图片 Provider。"""
    return OpenAICompatibleImageProvider(
        base_url="https://api.example.com/v1/",
        api_key="sk-test",
        model="u1-fast",
        httpx_client=http,
    )


class TestOpenAICompatibleLLM:
    """OpenAICompatibleLLMProvider 行为。"""

    def test_is_available_depends_on_key(self) -> None:
        """API Key 决定可用性。"""
        assert OpenAICompatibleLLMProvider(
            base_url="https://x", api_key="sk", model="m"
        ).is_available()
        assert not OpenAICompatibleLLMProvider(
            base_url="https://x", api_key="", model="m"
        ).is_available()

    def test_create_chat_model_passes_config(self) -> None:
        """模型参数透传给 ChatOpenAI。"""
        llm = OpenAICompatibleLLMProvider(
            base_url="https://x/v1",
            api_key="sk",
            model="m1",
            temperature=0.2,
            max_tokens=64,
        ).create_chat_model()

        assert llm.model_name == "m1"
        assert llm.openai_api_base == "https://x/v1"
        assert llm.temperature == 0.2
        assert llm.max_tokens == 64


class TestSettingsFallbackLLM:
    """SettingsFallbackLLMProvider 的厂商优先级。"""

    def test_unavailable_without_any_key(self) -> None:
        """无任何 Key 时不可用。"""
        settings = SimpleNamespace(dashscope_api_key="", sensenova_api_key="")
        assert not SettingsFallbackLLMProvider(settings).is_available()

    def test_available_with_dashscope(self) -> None:
        """dashscope Key 即可用。"""
        settings = SimpleNamespace(dashscope_api_key="sk", sensenova_api_key="")
        assert SettingsFallbackLLMProvider(settings).is_available()

    def test_create_raises_without_key(self) -> None:
        """未配置任何 Key 时 create_chat_model 抛 ValueError。"""
        settings = SimpleNamespace(dashscope_api_key="", sensenova_api_key="")
        with pytest.raises(ValueError, match="未配置任何 LLM Provider"):
            SettingsFallbackLLMProvider(settings).create_chat_model()

    def test_sensenova_preferred(self) -> None:
        """同时配置时优先 sensenova。"""
        settings = SimpleNamespace(
            dashscope_api_key="sk-dash",
            sensenova_api_key="sk-sense",
            sensenova_base_url="https://sense/v1",
            llm_model="deepseek-v4-flash",
        )
        llm = SettingsFallbackLLMProvider(settings).create_chat_model()
        assert llm.openai_api_base == "https://sense/v1"

    def test_sensenova_default_base_url(self) -> None:
        """sensenova 未配 base_url 时使用默认端点。"""
        settings = SimpleNamespace(
            dashscope_api_key="",
            sensenova_api_key="sk-sense",
            llm_model="m",
        )
        llm = SettingsFallbackLLMProvider(settings).create_chat_model()
        assert llm.openai_api_base == "https://token.sensenova.cn/v1"

    def test_dashscope_fallback(self) -> None:
        """仅 dashscope Key 时走通义兼容端点。"""
        settings = SimpleNamespace(
            dashscope_api_key="sk-dash",
            sensenova_api_key="",
            llm_model="qwen-plus",
        )
        llm = SettingsFallbackLLMProvider(settings).create_chat_model()
        assert "dashscope" in llm.openai_api_base


class TestImageGenerate:
    """OpenAICompatibleImageProvider.generate 行为。"""

    def test_is_available(self) -> None:
        """API Key 决定可用性。"""
        assert _provider(AsyncMock()).is_available()
        assert not OpenAICompatibleImageProvider(
            base_url="https://x", api_key="", model="m"
        ).is_available()

    async def test_generate_url_path(self) -> None:
        """响应带 url 时下载字节并返回。"""
        http = AsyncMock()
        http.post = AsyncMock(
            return_value=_FakeResponse(json_data={"data": [{"url": "https://img/1.png"}]})
        )
        http.get = AsyncMock(return_value=_FakeResponse(content=b"PNGDATA"))

        result = await _provider(http).generate(prompt="cat", n=1)

        assert len(result.images) == 1
        assert result.images[0].data == b"PNGDATA"
        assert result.images[0].url == "https://img/1.png"
        # 请求体：尺寸映射默认 2048x2048
        body = http.post.call_args.kwargs["json"]
        assert body["size"] == "2048x2048"
        assert body["n"] == 1

    async def test_generate_b64_path(self) -> None:
        """响应带 b64_json 时解码字节，url 为空。"""
        encoded = base64.b64encode(b"B64DATA").decode()
        http = AsyncMock()
        http.post = AsyncMock(
            return_value=_FakeResponse(json_data={"data": [{"b64_json": encoded}]})
        )

        result = await _provider(http).generate(prompt="cat")

        assert result.images[0].data == b"B64DATA"
        assert result.images[0].url == ""

    async def test_generate_seed_forwarded(self) -> None:
        """seed 非 None 时写入请求体并回填到结果。"""
        http = AsyncMock()
        http.post = AsyncMock(return_value=_FakeResponse(json_data={"data": [{"b64_json": ""}]}))
        # 空 b64 会走 raise，这里改用 url 路径验证 seed
        http.post = AsyncMock(
            return_value=_FakeResponse(json_data={"data": [{"url": "https://img/1.png"}]})
        )
        http.get = AsyncMock(return_value=_FakeResponse(content=b"X"))

        result = await _provider(http).generate(prompt="cat", seed=42)

        assert http.post.call_args.kwargs["json"]["seed"] == 42
        assert result.images[0].seed == 42

    async def test_size_mapping_known_ratio(self) -> None:
        """已知宽高比映射到厂商尺寸。"""
        http = AsyncMock()
        http.post = AsyncMock(
            return_value=_FakeResponse(json_data={"data": [{"url": "https://img/1.png"}]})
        )
        http.get = AsyncMock(return_value=_FakeResponse(content=b"X"))

        await _provider(http).generate(prompt="cat", width=1920, height=1080)

        assert http.post.call_args.kwargs["json"]["size"] == "2752x1536"

    async def test_size_mapping_unknown_ratio_falls_back(self) -> None:
        """未知宽高比回退到 2048x2048。"""
        http = AsyncMock()
        http.post = AsyncMock(
            return_value=_FakeResponse(json_data={"data": [{"url": "https://img/1.png"}]})
        )
        http.get = AsyncMock(return_value=_FakeResponse(content=b"X"))

        await _provider(http).generate(prompt="cat", width=123, height=45)

        assert http.post.call_args.kwargs["json"]["size"] == "2048x2048"

    async def test_empty_images_raises(self) -> None:
        """data 为空列表抛 ProviderUnavailableError。"""
        http = AsyncMock()
        http.post = AsyncMock(return_value=_FakeResponse(json_data={"data": []}))

        with pytest.raises(ProviderUnavailableError, match="图片列表为空"):
            await _provider(http).generate(prompt="cat")

    async def test_http_error_wrapped(self) -> None:
        """HTTP 层异常包装为 ProviderUnavailableError。"""
        http = AsyncMock()
        http.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with pytest.raises(ProviderUnavailableError, match="调用失败"):
            await _provider(http).generate(prompt="cat")

    async def test_download_failure_wrapped(self) -> None:
        """图片下载失败包装为 ProviderUnavailableError。"""
        http = AsyncMock()
        http.post = AsyncMock(
            return_value=_FakeResponse(json_data={"data": [{"url": "https://img/1.png"}]})
        )
        http.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with pytest.raises(ProviderUnavailableError, match="下载图片失败"):
            await _provider(http).generate(prompt="cat")

    async def test_item_without_url_and_b64_raises(self) -> None:
        """响应项缺 url 与 b64_json 时显式失败。"""
        http = AsyncMock()
        http.post = AsyncMock(return_value=_FakeResponse(json_data={"data": [{}]}))

        with pytest.raises(ProviderUnavailableError, match="缺少 url 和 b64_json"):
            await _provider(http).generate(prompt="cat")

    async def test_injected_client_not_closed(self) -> None:
        """注入的 httpx 客户端不会被 generate 关闭。"""
        http = AsyncMock()
        http.post = AsyncMock(
            return_value=_FakeResponse(json_data={"data": [{"url": "https://img/1.png"}]})
        )
        http.get = AsyncMock(return_value=_FakeResponse(content=b"X"))
        http.aclose = AsyncMock()

        await _provider(http).generate(prompt="cat")

        http.aclose.assert_not_called()
