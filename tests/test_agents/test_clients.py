"""
Provider 客户端单元测试（离线）。

使用注入式假 httpx.AsyncClient + monkeypatch，不依赖外部网络或 pytest-httpx，
在离线环境下验证真实调用逻辑（DashScope 图片 / Kling 视频），包括：
- 可用性与工厂函数（无 key 降级为 None）
- 真实路径：HTTP 交互、JWT 鉴权、提交/轮询/下载、字节落库
- 失败路径：下载失败 / 空结果 / API 错误 / 提交失败 / 任务失败 / 轮询超时
  均抛出 ProviderUnavailableError，由 Agent 捕获后降级为 Mock。
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import jwt
import pytest

from src.clients import get_image_client, get_video_client
from src.clients.dashscope_image_client import DashScopeImageClient
from src.clients.kling_video_client import KlingVideoClient
from src.clients.provider_result import (
    ImageGenerationResult,
    ProviderUnavailableError,
    VideoGenerationResult,
)


# --------------------------------------------------------------------------- #
# 测试夹具：构造最小 settings 与假 httpx 客户端
# --------------------------------------------------------------------------- #
def _img_settings(api_key: str = "sk-test") -> SimpleNamespace:
    return SimpleNamespace(dashscope_api_key=api_key, image_model="wanx-v1")


def _vid_settings(access: str = "ak", secret: str = "sk") -> SimpleNamespace:
    return SimpleNamespace(
        kling_access_key=access, kling_secret_key=secret, video_model="kling-v1"
    )


class _FakeResponse:
    """极简 httpx 响应替身，支持 .json() / .content / .raise_for_status()。"""

    def __init__(
        self, *, json_data: dict | None = None, content: bytes = b"", status_code: int = 200
    ) -> None:
        self._json = json_data
        self.content = content
        self.status_code = status_code

    def json(self) -> dict:
        if self._json is None:
            raise ValueError("response has no json body")
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("status", request=MagicMock(), response=MagicMock())


class FakeAsyncClient:
    """可编排的假 httpx.AsyncClient：posts / gets 队列，支持异常与回调。"""

    def __init__(self, *, posts: list | None = None, gets: list | None = None) -> None:
        self._posts = list(posts or [])
        self._gets = list(gets or [])
        self.post_calls: list[tuple] = []
        self.get_calls: list[tuple] = []

    async def post(self, url: str, *, headers=None, json=None, timeout=None):  # noqa: ANN001, ARG002
        self.post_calls.append((url, headers, json))
        return self._unwrap(self._posts.pop(0))

    async def get(self, url: str, *, headers=None, timeout=None):  # noqa: ANN001, ARG002
        self.get_calls.append((url, headers))
        return self._unwrap(self._gets.pop(0))

    @staticmethod
    def _unwrap(spec):  # noqa: ANN001
        if isinstance(spec, Exception):
            raise spec
        if callable(spec):
            return spec()
        return spec

    async def aclose(self) -> None:
        pass


def _fake_wanx_response(status_code: int = 200, results: list | None = None) -> SimpleNamespace:
    """构造 dashscope.ImageSynthesis.call 的返回值替身。"""
    return SimpleNamespace(
        status_code=status_code,
        code="",
        message="",
        output={"results": results or []},
    )


# --------------------------------------------------------------------------- #
# DashScope 图片客户端
# --------------------------------------------------------------------------- #
class TestDashScopeImageClient:
    def test_is_available(self) -> None:
        assert DashScopeImageClient(settings=_img_settings("sk")).is_available() is True
        assert DashScopeImageClient(settings=_img_settings("")).is_available() is False

    @pytest.mark.asyncio
    async def test_generate_happy_path(self) -> None:
        fake = FakeAsyncClient(gets=[_FakeResponse(content=b"IMAGEBYTES")])
        client = DashScopeImageClient(settings=_img_settings(), httpx_client=fake)
        with patch(
            "dashscope.ImageSynthesis.call",
            return_value=_fake_wanx_response(results=[{"url": "https://dash/x.png", "seed": 42}]),
        ):
            result = await client.generate(prompt="a cat", width=1024, height=1024, n=1)

        assert isinstance(result, ImageGenerationResult)
        assert len(result.images) == 1
        assert result.images[0].data == b"IMAGEBYTES"
        assert result.images[0].url == "https://dash/x.png"
        assert result.images[0].seed == 42

    @pytest.mark.asyncio
    async def test_generate_download_failure_raises(self) -> None:
        fake = FakeAsyncClient(gets=[httpx.ConnectError("boom")])
        client = DashScopeImageClient(settings=_img_settings(), httpx_client=fake)
        with patch(
            "dashscope.ImageSynthesis.call",
            return_value=_fake_wanx_response(results=[{"url": "u"}]),
        ), pytest.raises(ProviderUnavailableError):
            await client.generate(prompt="x")

    @pytest.mark.asyncio
    async def test_generate_empty_results_raises(self) -> None:
        fake = FakeAsyncClient()
        client = DashScopeImageClient(settings=_img_settings(), httpx_client=fake)
        with patch(
            "dashscope.ImageSynthesis.call",
            return_value=_fake_wanx_response(results=[]),
        ), pytest.raises(ProviderUnavailableError):
            await client.generate(prompt="x")

    @pytest.mark.asyncio
    async def test_generate_api_error_raises(self) -> None:
        fake = FakeAsyncClient()
        client = DashScopeImageClient(settings=_img_settings(), httpx_client=fake)
        with patch(
            "dashscope.ImageSynthesis.call",
            return_value=_fake_wanx_response(status_code=400, results=[]),
        ), pytest.raises(ProviderUnavailableError):
            await client.generate(prompt="x")


# --------------------------------------------------------------------------- #
# Kling 视频客户端
# --------------------------------------------------------------------------- #
class TestKlingVideoClient:
    def test_is_available(self) -> None:
        assert KlingVideoClient(settings=_vid_settings()).is_available() is True
        assert KlingVideoClient(settings=_vid_settings(secret="")).is_available() is False

    def test_create_token_is_valid_hs256(self) -> None:
        client = KlingVideoClient(settings=_vid_settings())
        token = client._create_token()
        decoded = jwt.decode(token, "sk", algorithms=["HS256"])
        assert decoded["iss"] == "ak"
        assert "exp" in decoded and "nbf" in decoded
        assert decoded["exp"] > decoded["nbf"]

    def test_token_cached(self) -> None:
        client = KlingVideoClient(settings=_vid_settings())
        assert client._create_token() == client._create_token()

    @pytest.mark.asyncio
    async def test_generate_happy_path(self) -> None:
        fake = FakeAsyncClient(
            posts=[_FakeResponse(json_data={"code": 0, "message": "ok", "data": {"task_id": "t1"}})],
            gets=[
                _FakeResponse(json_data={"code": 0, "data": {"task_status": "processing"}}),
                _FakeResponse(
                    json_data={
                        "code": 0,
                        "data": {"task_status": "succeed", "works": [{"resource_url": "https://kling/v.mp4"}]},
                    }
                ),
                _FakeResponse(content=b"VIDEOBYTES"),
            ],
        )
        client = KlingVideoClient(
            settings=_vid_settings(), httpx_client=fake, poll_interval=0.01, poll_timeout=30.0
        )
        result = await client.generate(prompt="a product video", duration=5.0)

        assert isinstance(result, VideoGenerationResult)
        assert result.data == b"VIDEOBYTES"
        assert result.url == "https://kling/v.mp4"
        assert result.task_id == "t1"
        # 提交端点与鉴权头正确
        assert fake.post_calls[0][0].endswith("/v1/videos/generations")
        assert fake.post_calls[0][1].get("Authorization", "").startswith("Bearer ")

    @pytest.mark.asyncio
    async def test_generate_submit_failure_raises(self) -> None:
        fake = FakeAsyncClient(posts=[_FakeResponse(json_data={"code": 500, "message": "bad"})])
        client = KlingVideoClient(settings=_vid_settings(), httpx_client=fake)
        with pytest.raises(ProviderUnavailableError):
            await client.generate(prompt="x")

    @pytest.mark.asyncio
    async def test_generate_task_failed_raises(self) -> None:
        fake = FakeAsyncClient(
            posts=[_FakeResponse(json_data={"code": 0, "data": {"task_id": "t1"}})],
            gets=[_FakeResponse(json_data={"code": 0, "data": {"task_status": "failed"}})],
        )
        client = KlingVideoClient(settings=_vid_settings(), httpx_client=fake)
        with pytest.raises(ProviderUnavailableError):
            await client.generate(prompt="x")

    @pytest.mark.asyncio
    async def test_generate_timeout_raises(self) -> None:
        fake = FakeAsyncClient(
            posts=[_FakeResponse(json_data={"code": 0, "data": {"task_id": "t1"}})],
            gets=[
                _FakeResponse(json_data={"code": 0, "data": {"task_status": "processing"}})
            ]
            * 20,
        )
        client = KlingVideoClient(
            settings=_vid_settings(), httpx_client=fake, poll_interval=0.01, poll_timeout=0.05
        )
        with pytest.raises(ProviderUnavailableError):
            await client.generate(prompt="x")


# --------------------------------------------------------------------------- #
# 工厂函数
# --------------------------------------------------------------------------- #
class TestFactoryFunctions:
    def test_get_image_client_none_when_unconfigured(self) -> None:
        assert get_image_client(settings=_img_settings("")) is None

    def test_get_image_client_returns_client_when_configured(self) -> None:
        client = get_image_client(settings=_img_settings("sk"))
        assert isinstance(client, DashScopeImageClient)

    def test_get_video_client_none_when_unconfigured(self) -> None:
        assert get_video_client(settings=_vid_settings(secret="")) is None

    def test_get_video_client_returns_client_when_configured(self) -> None:
        client = get_video_client(settings=_vid_settings())
        assert isinstance(client, KlingVideoClient)
