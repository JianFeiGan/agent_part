"""
DashScope 通义万象图片生成客户端。

封装 ``dashscope.ImageSynthesis.call``（同步阻塞 API，使用 ``asyncio.to_thread``
包裹以防止阻塞事件循环）以及结果字节的下载，将结果收敛为
``ImageGenerationResult``。

设计要点：
- ``dashscope`` 在方法内部懒加载导入，避免模块顶层副作用。
- ``ImageSynthesis.call`` 返回类型为 ``Any``，使用本地 TypedDict + ``cast``
  收敛，满足 mypy ``warn_return_any``。
- ``httpx.AsyncClient`` 默认懒创建，构造时可注入以便测试替换。
"""

from __future__ import annotations

import asyncio
import logging
from http import HTTPStatus
from typing import Any, Protocol, TypedDict, cast, runtime_checkable

import httpx

from src.clients.provider_result import (
    ImageGenerationResult,
    ProviderUnavailableError,
    SingleImageResult,
    is_image_provider_configured,
)
from src.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class _WanxOutputResult(TypedDict, total=False):
    """单条图片结果（output.results 元素）。"""

    url: str
    seed: int


class _WanxOutput(TypedDict):
    """图片生成输出体。"""

    results: list[_WanxOutputResult]


@runtime_checkable
class _WanxResponse(Protocol):
    """收敛后的 DashScope 响应结构（等价于 SDK 返回对象的可访问属性）。"""

    status_code: int
    code: str
    message: str
    output: _WanxOutput


class DashScopeImageClient:
    """DashScope 通义万象（wanx-v1）图片生成客户端。"""

    def __init__(
        self,
        settings: Settings | None = None,
        httpx_client: httpx.AsyncClient | None = None,
    ) -> None:
        """初始化图片客户端。

        Args:
            settings: 应用配置，默认从 ``get_settings()`` 读取。
            httpx_client: 可注入的 httpx 异步客户端；为 None 时懒创建。
        """
        self._settings = settings or get_settings()
        self._httpx = httpx_client

    def is_available(self) -> bool:
        """是否已配置 DashScope API Key。"""
        return is_image_provider_configured(self._settings)

    async def generate(
        self,
        prompt: str,
        negative_prompt: str | None = None,
        width: int = 1024,
        height: int = 1024,
        n: int = 1,
        seed: int | None = None,
    ) -> ImageGenerationResult:
        """生成图片并返回 ``ImageGenerationResult``。

        Args:
            prompt: 正向提示词。
            negative_prompt: 负向提示词，可空。
            width: 图片宽度（像素）。
            height: 图片高度（像素）。
            n: 生成数量（默认 1）。
            seed: 随机种子，可空。

        Returns:
            包含图片字节、远端 URL 与种子的结果集合。

        Raises:
            ProviderUnavailableError: 调用或下载失败时抛出。
        """
        client = self._httpx or httpx.AsyncClient()
        try:
            response = await self._call_api(
                prompt, negative_prompt, width, height, n, seed
            )
            results = response.output.get("results", [])
            if not results:
                raise ProviderUnavailableError("DashScope 返回的图片列表为空")
            images: list[SingleImageResult] = []
            for item in results:
                url = item["url"]
                data = await self._download(client, url)
                images.append(
                    SingleImageResult(data=data, url=url, seed=item.get("seed"))
                )
            return ImageGenerationResult(images=images)
        finally:
            if self._httpx is None:
                await client.aclose()

    async def _call_api(
        self,
        prompt: str,
        negative_prompt: str | None,
        width: int,
        height: int,
        n: int,
        seed: int | None,
    ) -> _WanxResponse:
        """同步调用 DashScope wanx-v1，返回收敛后的响应结构。

        Args:
            prompt: 正向提示词。
            negative_prompt: 负向提示词。
            width: 宽度。
            height: 高度。
            n: 数量。
            seed: 种子。

        Returns:
            收敛为 ``_WanxResponse`` 的响应对象。

        Raises:
            ProviderUnavailableError: 调用失败或返回非 200 时抛出。
        """
        from dashscope import ImageSynthesis

        kwargs: dict[str, Any] = {
            "api_key": self._settings.dashscope_api_key,
            "model": self._settings.image_model,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "n": n,
            "size": f"{width}*{height}",
        }
        if seed is not None:
            kwargs["seed"] = seed

        raw = await asyncio.to_thread(ImageSynthesis.call, **kwargs)
        response = cast("_WanxResponse", raw)
        if response.status_code != HTTPStatus.OK.value:
            raise ProviderUnavailableError(
                f"DashScope 图片生成失败: code={response.code}, message={response.message}"
            )
        return response

    async def _download(self, client: httpx.AsyncClient, url: str) -> bytes:
        """下载结果字节。

        Args:
            client: httpx 异步客户端。
            url: 远端图片 URL。

        Returns:
            图片字节。

        Raises:
            ProviderUnavailableError: 下载失败时抛出。
        """
        try:
            resp = await client.get(url, timeout=60.0)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"下载图片失败: {exc}") from exc
        return resp.content
