"""千问客户端（LLM / Embedding）行为测试（离线）。

通过注入假 httpx.AsyncClient 与 SimpleNamespace Settings 验证真实调用路径，
不发起网络请求。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from src.clients.qwen_embedding_client import (
    QwenEmbeddingClient,
    get_qwen_embedding,
    is_qwen_embedding_configured,
)
from src.clients.qwen_llm_client import get_qwen_llm, is_qwen_llm_configured

# --------------------------------------------------------------------------- #
# 夹具
# --------------------------------------------------------------------------- #


def _settings(**kwargs: Any) -> SimpleNamespace:
    """构造千问相关 Settings 子集。"""
    defaults: dict[str, Any] = {
        "effective_qwen_api_key": "",
        "qwen_api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "qwen_llm_model": "qwen-plus",
        "qwen_embedding_model": "text-embedding-v3",
        "qwen_embedding_dimensions": 8,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class _FakeResponse:
    """极简 httpx 响应替身。"""

    def __init__(self, *, json_data: dict[str, Any] | None = None, status_code: int = 200) -> None:
        self._json = json_data
        self.status_code = status_code
        self.text = str(json_data)

    def json(self) -> dict[str, Any]:
        if self._json is None:
            raise ValueError("no json body")
        return self._json


class TestQwenLLM:
    """get_qwen_llm 工厂行为。"""

    def test_raises_without_api_key(self) -> None:
        """未配置任何 Key 时抛 ValueError。"""
        with pytest.raises(ValueError, match="未配置"):
            get_qwen_llm(settings=_settings())

    def test_uses_configured_model_and_base(self) -> None:
        """默认模型与 base_url 取自 Settings。"""
        llm = get_qwen_llm(settings=_settings(effective_qwen_api_key="sk-test"))
        assert llm.model_name == "qwen-plus"
        assert "dashscope" in llm.openai_api_base

    def test_model_override(self) -> None:
        """显式 model 参数覆盖 Settings 默认。"""
        llm = get_qwen_llm(settings=_settings(effective_qwen_api_key="sk-test"), model="qwen-max")
        assert llm.model_name == "qwen-max"

    def test_is_configured(self) -> None:
        """is_qwen_llm_configured 依据 effective key 判定。"""
        assert is_qwen_llm_configured(_settings(effective_qwen_api_key="sk")) is True
        assert is_qwen_llm_configured(_settings()) is False


class TestQwenEmbedding:
    """QwenEmbeddingClient 行为。"""

    def test_is_available(self) -> None:
        """is_available 依据 effective key 判定。"""
        assert QwenEmbeddingClient(_settings(effective_qwen_api_key="sk")).is_available()
        assert not QwenEmbeddingClient(_settings()).is_available()

    async def test_embed_batch_requires_key(self) -> None:
        """无 Key 时抛 ValueError，不发请求。"""
        client = QwenEmbeddingClient(_settings())
        with pytest.raises(ValueError, match="未配置"):
            await client.embed_batch(["hello"])

    async def test_embed_batch_happy_path(self) -> None:
        """批量向量化返回 data 中的 embedding 列表。"""
        http = AsyncMock()
        http.post = AsyncMock(
            return_value=_FakeResponse(
                json_data={"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]}
            )
        )
        client = QwenEmbeddingClient(_settings(effective_qwen_api_key="sk"), httpx_client=http)

        result = await client.embed_batch(["a", "b"])

        assert result == [[0.1, 0.2], [0.3, 0.4]]
        _, kwargs = http.post.call_args
        assert kwargs["json"]["input"] == ["a", "b"]
        assert kwargs["json"]["model"] == "text-embedding-v3"
        assert kwargs["json"]["dimensions"] == 8
        assert kwargs["headers"]["Authorization"] == "Bearer sk"

    async def test_embed_single_returns_first(self) -> None:
        """embed() 返回单条向量。"""
        http = AsyncMock()
        http.post = AsyncMock(
            return_value=_FakeResponse(json_data={"data": [{"embedding": [1.0, 2.0]}]})
        )
        client = QwenEmbeddingClient(_settings(effective_qwen_api_key="sk"), httpx_client=http)

        assert await client.embed("hello") == [1.0, 2.0]

    async def test_http_error_raises_runtime_error(self) -> None:
        """非 200 响应抛 RuntimeError 并带状态码。"""
        http = AsyncMock()
        http.post = AsyncMock(return_value=_FakeResponse(status_code=429))
        client = QwenEmbeddingClient(_settings(effective_qwen_api_key="sk"), httpx_client=http)

        with pytest.raises(RuntimeError, match="status=429"):
            await client.embed_batch(["a"])

    async def test_empty_data_raises_runtime_error(self) -> None:
        """data 缺失或为空抛 RuntimeError。"""
        http = AsyncMock()
        http.post = AsyncMock(return_value=_FakeResponse(json_data={"data": []}))
        client = QwenEmbeddingClient(_settings(effective_qwen_api_key="sk"), httpx_client=http)

        with pytest.raises(RuntimeError, match="返回数据为空"):
            await client.embed_batch(["a"])

    async def test_close_releases_owned_client(self) -> None:
        """close() 关闭自建 httpx 客户端并置空。"""
        fake = AsyncMock()
        fake.aclose = AsyncMock()
        client = QwenEmbeddingClient(_settings(effective_qwen_api_key="sk"))
        client._httpx = fake  # noqa: SLF001 —— 注入替身

        await client.close()

        fake.aclose.assert_awaited_once()
        assert client._httpx is None  # noqa: SLF001

    async def test_close_without_client_is_noop(self) -> None:
        """无自建客户端时 close() 不报错。"""
        await QwenEmbeddingClient(_settings()).close()

    async def test_get_qwen_embedding_facade(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """模块级 get_qwen_embedding 委托到客户端 embed。"""
        captured: dict[str, Any] = {}

        class _Stub:
            def __init__(self, settings: Any) -> None:
                captured["settings"] = settings

            async def embed(self, text: str) -> list[float]:
                captured["text"] = text
                return [9.0]

        monkeypatch.setattr("src.clients.qwen_embedding_client.QwenEmbeddingClient", _Stub)

        assert await get_qwen_embedding("hello", settings=_settings()) == [9.0]
        assert captured["text"] == "hello"

    def test_is_qwen_embedding_configured(self) -> None:
        """模块级配置判定。"""
        assert is_qwen_embedding_configured(_settings(effective_qwen_api_key="sk"))
        assert not is_qwen_embedding_configured(_settings())

    async def test_injected_httpx_reused(self) -> None:
        """注入的 httpx 客户端被复用，不自建新实例。"""
        http = AsyncMock()
        http.post = AsyncMock(
            return_value=_FakeResponse(json_data={"data": [{"embedding": [0.0]}]})
        )
        client = QwenEmbeddingClient(_settings(effective_qwen_api_key="sk"), httpx_client=http)

        await client.embed_batch(["a"])

        assert client._httpx is http  # noqa: SLF001


class TestHttpxErrorWrapping:
    """HTTP 异常映射到 RuntimeError 的边界。"""

    async def test_httpx_transport_error_propagates_as_httpx(self) -> None:
        """传输层异常按 httpx 约定向上抛（调用方决定降级）。"""
        http = AsyncMock()
        http.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        client = QwenEmbeddingClient(_settings(effective_qwen_api_key="sk"), httpx_client=http)

        with pytest.raises(httpx.ConnectError):
            await client.embed_batch(["a"])

    def test_forged_response_without_json(self) -> None:
        """_FakeResponse 无 json 体时抛 ValueError（仅校验替身自身契约）。"""
        resp = _FakeResponse()
        with pytest.raises(ValueError):
            resp.json()
