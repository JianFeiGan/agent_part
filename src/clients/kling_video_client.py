"""
Kling AI 视频生成客户端。

封装 Kling ``kling-v1`` 视频生成的完整异步流程：
1. HS256 JWT 鉴权（实例内缓存至 exp-60s 复用）；
2. 提交异步生成任务（POST /v1/videos/generations）；
3. 轮询任务状态（GET /v1/videos/generations/{task_id}）；
4. 取结果 URL 并下载字节。

设计要点：
- 端点基址 ``KLING_API_BASE`` 为模块常量，构造参数 ``base_url`` 可覆盖，无需新增配置项。
- JWT 缓存使用实例属性 ``_token_cache``，不引入全局缓存。
- ``httpx.AsyncClient`` 默认懒创建，构造时可注入以便测试替换。
- HTTP 响应用 ``cast`` 收敛到本地 TypedDict，满足 mypy ``warn_return_any``。
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from typing import Any, TypedDict, cast

import httpx
import jwt

from src.clients.provider_result import (
    ProviderUnavailableError,
    VideoGenerationResult,
    is_video_provider_configured,
)
from src.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# Kling 公开 API 基址（国内为 https://platform.klingai.com）
KLING_API_BASE = "https://api.klingai.com"

# JWT 过期时间（秒）与提前复用阈值（秒）
_KLING_TOKEN_EXP = 1800
_KLING_TOKEN_REUSE_BUFFER = 60
# 轮询退避上限（秒）
_KLING_MAX_POLL_INTERVAL = 30.0


class _KlingSubmitData(TypedDict):
    """提交响应 data 体。"""

    task_id: str


class _KlingSubmitResponse(TypedDict):
    """提交响应。"""

    code: int
    message: str
    data: _KlingSubmitData


class _KlingWork(TypedDict, total=False):
    """生成结果作品。"""

    resource_url: str


class _KlingQueryData(TypedDict, total=False):
    """查询响应 data 体。"""

    task_status: str
    works: list[_KlingWork]


class _KlingQueryResponse(TypedDict, total=False):
    """查询响应。"""

    code: int
    message: str
    data: _KlingQueryData


class KlingVideoClient:
    """Kling AI 视频生成客户端。"""

    def __init__(
        self,
        settings: Settings | None = None,
        base_url: str = KLING_API_BASE,
        httpx_client: httpx.AsyncClient | None = None,
        poll_interval: float = 5.0,
        poll_timeout: float = 300.0,
        access_key: str | None = None,
        secret_key: str | None = None,
    ) -> None:
        """初始化视频客户端。

        Args:
            settings: 应用配置，默认从 ``get_settings()`` 读取。
            base_url: API 基址，默认 ``KLING_API_BASE``，可覆盖。
            httpx_client: 可注入的 httpx 异步客户端；为 None 时懒创建。
            poll_interval: 初始轮询间隔（秒）。
            poll_timeout: 轮询总超时（秒）。
            access_key: 可灵 Access Key（优先于 settings 读取）。
            secret_key: 可灵 Secret Key（优先于 settings 读取）。
        """
        self._settings = settings or get_settings()
        self._base_url = base_url.rstrip("/")
        self._httpx = httpx_client
        self._poll_interval = poll_interval
        self._poll_timeout = poll_timeout
        # 优先使用直接传入的凭据，否则从 settings 读取
        self._access_key = access_key or self._settings.kling_access_key
        self._secret_key = secret_key or self._settings.kling_secret_key
        self._token_cache: tuple[str, float] | None = None

    def is_available(self) -> bool:
        """是否已配置 Kling Access / Secret Key。"""
        return bool(self._access_key) and bool(self._secret_key)

    async def generate(
        self,
        prompt: str,
        image: bytes | None = None,
        duration: float = 5.0,
        mode: str = "std",
        cfg_scale: float = 0.5,
        aspect_ratio: str = "16:9",
    ) -> VideoGenerationResult:
        """生成视频并返回 ``VideoGenerationResult``。

        Args:
            prompt: 视频提示词。
            image: 可选首帧图片字节（图生视频）。
            duration: 时长（秒）。
            mode: 生成模式（默认 std）。
            cfg_scale: 自由度参数。
            aspect_ratio: 宽高比。

        Returns:
            包含视频字节、远端 URL、时长与任务 ID 的结果。

        Raises:
            ProviderUnavailableError: 任意环节失败时抛出。
        """
        client = self._httpx or httpx.AsyncClient()
        try:
            task_id = await self._submit(
                client, prompt, image, duration, mode, cfg_scale, aspect_ratio
            )
            status, url = await self._query(client, task_id)
            if url is None:
                raise ProviderUnavailableError(
                    f"Kling 任务 {task_id} 未返回视频 URL (status={status})"
                )
            data = await self._download(client, url)
            return VideoGenerationResult(
                data=data, url=url, duration=duration, task_id=task_id
            )
        finally:
            if self._httpx is None:
                await client.aclose()

    def _create_token(self) -> str:
        """创建 HS256 JWT 鉴权令牌（实例内缓存复用）。

        Returns:
            签名后的 JWT 字符串。
        """
        now = int(time.time())
        if self._token_cache is not None:
            cached_token, exp = self._token_cache
            if now < exp - _KLING_TOKEN_REUSE_BUFFER:
                return cached_token

        exp = now + _KLING_TOKEN_EXP
        payload = {
            "iss": self._access_key,
            "exp": exp,
            "nbf": now - 5,
        }
        token: str | bytes = jwt.encode(
            payload, self._secret_key, algorithm="HS256"
        )
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        self._token_cache = (token, float(exp))
        return token

    async def _submit(
        self,
        client: httpx.AsyncClient,
        prompt: str,
        image: bytes | None,
        duration: float,
        mode: str,
        cfg_scale: float,
        aspect_ratio: str,
    ) -> str:
        """提交视频生成任务，返回 task_id。

        Args:
            client: httpx 异步客户端。
            prompt: 提示词。
            image: 首帧图片字节。
            duration: 时长。
            mode: 模式。
            cfg_scale: 自由度。
            aspect_ratio: 宽高比。

        Returns:
            Kling 任务 ID。

        Raises:
            ProviderUnavailableError: 提交或响应异常时抛出。
        """
        token = self._create_token()
        url = f"{self._base_url}/v1/videos/generations"
        body: dict[str, Any] = {
            "model": self._settings.video_model,
            "prompt": prompt,
            "mode": mode,
            "duration": duration,
            "cfg_scale": cfg_scale,
            "aspect_ratio": aspect_ratio,
        }
        if image is not None:
            encoded = base64.b64encode(image).decode("utf-8")
            body["image"] = f"data:image/png;base64,{encoded}"

        try:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=30.0,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Kling 提交失败: {exc}") from exc

        data = cast("_KlingSubmitResponse", resp.json())
        code = data.get("code")
        if code is not None and code != 0:
            raise ProviderUnavailableError(
                f"Kling 提交失败: code={code}, message={data.get('message')}"
            )
        task_id = data["data"]["task_id"]
        return task_id

    async def _query(
        self, client: httpx.AsyncClient, task_id: str
    ) -> tuple[str, str | None]:
        """轮询任务状态直到 succeed / failed 或超时。

        Args:
            client: httpx 异步客户端。
            task_id: 任务 ID。

        Returns:
            ``(status, resource_url)``，未完成或失败时 url 为 None。

        Raises:
            ProviderUnavailableError: 任务失败或轮询超时时抛出。
        """
        url = f"{self._base_url}/v1/videos/generations/{task_id}"
        token = self._create_token()
        headers = {"Authorization": f"Bearer {token}"}
        start = time.time()
        interval = self._poll_interval

        while True:
            try:
                resp = await client.get(url, headers=headers, timeout=30.0)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise ProviderUnavailableError(f"Kling 查询失败: {exc}") from exc

            data = cast("_KlingQueryResponse", resp.json())
            code = data.get("code")
            if code is not None and code != 0:
                raise ProviderUnavailableError(
                    f"Kling 查询失败: code={code}, message={data.get('message')}"
                )

            data_obj = data.get("data")
            if data_obj is None:
                raise ProviderUnavailableError("Kling 查询返回缺少 data 字段")

            status = data_obj.get("task_status", "processing")
            if status == "succeed":
                works = data_obj.get("works") or []
                if works:
                    return status, works[0].get("resource_url")
                return status, None
            if status == "failed":
                raise ProviderUnavailableError(f"Kling 任务 {task_id} 处理失败")

            if time.time() - start > self._poll_timeout:
                raise ProviderUnavailableError(
                    f"Kling 任务 {task_id} 轮询超时（{self._poll_timeout}s）"
                )

            remaining = max(0.0, self._poll_timeout - (time.time() - start))
            await asyncio.sleep(min(interval, remaining))
            interval = min(interval * 2, _KLING_MAX_POLL_INTERVAL)

    async def _download(self, client: httpx.AsyncClient, url: str) -> bytes:
        """下载视频字节。

        Args:
            client: httpx 异步客户端。
            url: 远端视频 URL。

        Returns:
            视频字节。

        Raises:
            ProviderUnavailableError: 下载失败时抛出。
        """
        try:
            resp = await client.get(url, timeout=60.0)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Kling 下载视频失败: {exc}") from exc
        return resp.content
