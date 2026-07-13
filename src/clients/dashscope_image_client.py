"""
DashScope 通义万象图片生成客户端。

封装 ``dashscope.ImageSynthesis`` 的异步调用模式（async_call + wait），
支持 wanx-v1、wan2.7-image-pro 等模型，使用 ``asyncio.to_thread``
包裹以防止阻塞事件循环。

设计要点：
- ``dashscope`` 在方法内部懒加载导入，避免模块顶层副作用。
- 使用 async_call + wait 模式，兼容所有万相系列模型。
- ``httpx.AsyncClient`` 默认懒创建，构造时可注入以便测试替换。
- API Key 使用 effective_dashscope_api_key，兼容百炼平台统一 Key。
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


# 支持同步 call 的模型列表（无需异步轮询）
_SYNC_MODELS = {"wanx-v1", "wanx-v1-edit"}

# wanx 系列支持的尺寸枚举（非标准尺寸会被拒绝）
_SUPPORTED_SIZES = {
    "1024*1024", "720*1280", "1280*720",
    "960*1280", "1280*960",
    "768*1024", "1024*768",
    "720*480", "480*720",
}


class DashScopeImageClient:
    """DashScope 通义万象图片生成客户端。

    支持万相系列模型（wanx-v1, wan2.7-image-pro 等）。
    自动选择同步/异步调用模式。
    """

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

    def _normalize_size(self, width: int, height: int) -> str:
        """将宽高转换为 DashScope 支持的 size 格式。

        如果精确尺寸不在支持列表中，回退到最接近的标准尺寸。

        Args:
            width: 宽度。
            height: 高度。

        Returns:
            DashScope size 字符串，如 "1024*1024"。
        """
        size_str = f"{width}*{height}"
        if size_str in _SUPPORTED_SIZES:
            return size_str

        # 回退到最接近的标准尺寸
        if width >= height:
            if width > 1280:
                return "1280*720"
            return "1024*1024"
        else:
            if height > 1280:
                return "720*1280"
            return "1024*1024"

    async def _call_api(
        self,
        prompt: str,
        negative_prompt: str | None,
        width: int,
        height: int,
        n: int,
        seed: int | None,
    ) -> _WanxResponse:
        """调用 DashScope 图片生成 API。

        根据模型类型自动选择同步/异步调用模式：
        - wanx-v1 等旧模型使用同步 call
        - wan2.7-image-pro 等新模型使用 async_call + wait

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

        api_key = getattr(
            self._settings,
            "effective_dashscope_api_key",
            None,
        ) or getattr(self._settings, "dashscope_api_key", "") or getattr(self._settings, "qwen_api_key", "")
        model = self._settings.image_model
        size = self._normalize_size(width, height)

        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "model": model,
            "prompt": prompt,
            "n": n,
            "size": size,
        }
        if negative_prompt:
            kwargs["negative_prompt"] = negative_prompt
        if seed is not None:
            kwargs["seed"] = seed

        logger.info(f"调用 DashScope 图片生成: model={model}, size={size}")

        # 根据模型选择调用模式
        if model in _SYNC_MODELS:
            raw = await asyncio.to_thread(ImageSynthesis.call, **kwargs)
        else:
            # 新模型使用异步调用 + 轮询等待
            task = await asyncio.to_thread(ImageSynthesis.async_call, **kwargs)
            raw = await asyncio.to_thread(ImageSynthesis.wait, task)

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
