"""DashScope 通义万象图片生成客户端（纯 HTTP 实现）。

Description:
    封装阿里云 DashScope wanx-v1 图片生成的异步流程，
    使用 httpx 直接调用 REST API，不依赖 dashscope SDK。
    支持同步生成和异步任务两种模式，自动适配。
@author ganjianfei
@version 1.0.0
2026-07-22
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from src.clients.provider_result import (
    ImageGenerationResult,
    ProviderUnavailableError,
    SingleImageResult,
)
from src.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# DashScope 图片生成 API 端点
_DASHSCOPE_IMAGE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
# DashScope 异步任务查询端点
_DASHSCOPE_TASK_URL = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
# 轮询退避上限（秒）
_MAX_POLL_INTERVAL = 10.0
# 轮询总超时（秒）
_POLL_TIMEOUT = 300.0


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
    """DashScope 通义万象（wanx-v1）图片生成客户端。

    使用纯 HTTP REST 调用替代 dashscope SDK，
    支持 DashScope 的同步和异步两种图片生成模式。

    Example:
        >>> client = DashScopeImageClient(api_key="sk-xxx", model="wanx-v1")
        >>> result = await client.generate(prompt="一只可爱的猫咪")
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "wanx-v1",
        base_url: str = "",
        httpx_client: httpx.AsyncClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        """初始化图片客户端。

        Args:
            api_key: DashScope API Key。
            model: 图片生成模型名称。
            base_url: API 基址（兼容旧接口，实际使用硬编码端点）。
            httpx_client: 可注入的 httpx 异步客户端；为 None 时懒创建。
            settings: 应用配置（向后兼容）。
        """
        if settings and not api_key:
            api_key = settings.dashscope_api_key
        if settings and model == "wanx-v1" and settings.image_model:
            model = settings.image_model
        self._api_key = api_key
        self._model = model
        self._httpx = httpx_client

    def is_available(self) -> bool:
        """是否已配置 DashScope API Key。"""
        return bool(self._api_key)

    async def generate(
        self,
        prompt: str,
        negative_prompt: str | None = None,
        width: int = 1024,
        height: int = 1024,
        n: int = 1,
        seed: int | None = None,
    ) -> ImageGenerationResult:
        """生成图片并返回 ImageGenerationResult。

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
            result = await self._call_api(
                client, prompt, negative_prompt, width, height, n, seed
            )
            return result
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
        client: httpx.AsyncClient,
        prompt: str,
        negative_prompt: str | None,
        width: int,
        height: int,
        n: int,
        seed: int | None,
    ) -> ImageGenerationResult:
        """调用 DashScope REST API 生成图片。

        DashScope 图片生成支持同步和异步两种模式：
        - 同步模式：设置 X-DashScope-Async=disable，直接返回结果
        - 异步模式：返回 task_id，需轮询获取结果

        Args:
            client: httpx 异步客户端。
            prompt: 正向提示词。
            negative_prompt: 负向提示词。
            width: 宽度。
            height: 高度。
            n: 数量。
            seed: 种子。

        Returns:
            ImageGenerationResult。

        Raises:
            ProviderUnavailableError: 调用失败时抛出。
        """
        body: dict[str, Any] = {
            "model": self._model,
            "input": {
                "prompt": prompt,
            },
            "parameters": {
                "size": f"{width}*{height}",
                "n": n,
            },
        }
        if negative_prompt:
            body["input"]["negative_prompt"] = negative_prompt
        if seed is not None:
            body["parameters"]["seed"] = seed

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",  # 使用异步模式
        }

        try:
            resp = await client.post(
                _DASHSCOPE_IMAGE_URL,
                headers=headers,
                json=body,
                timeout=60.0,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                f"DashScope 图片生成提交失败: {exc}"
            ) from exc

        data = resp.json()

        # 检查是否直接返回了结果（同步模式）
        output = data.get("output", {})
        if output.get("results"):
            return self._parse_results(client, output["results"])

        # 异步模式：获取 task_id 并轮询
        task_id = output.get("task_id")
        if not task_id:
            # 也可能在 data.task_status 中
            task_id = data.get("task_id") or data.get("output", {}).get("task_id")

        if task_id:
            return await self._poll_task(client, task_id)

        raise ProviderUnavailableError(
            f"DashScope 图片生成未返回结果或 task_id: {data}"
        )

    async def _poll_task(
        self, client: httpx.AsyncClient, task_id: str
    ) -> ImageGenerationResult:
        """轮询异步任务状态直到成功或失败。

        Args:
            client: httpx 异步客户端。
            task_id: 异步任务 ID。

        Returns:
            ImageGenerationResult。

        Raises:
            ProviderUnavailableError: 任务失败或超时时抛出。
        """
        url = _DASHSCOPE_TASK_URL.format(task_id=task_id)
        headers = {"Authorization": f"Bearer {self._api_key}"}
        start = time.time()
        interval = 2.0

        while True:
            try:
                resp = await client.get(url, headers=headers, timeout=30.0)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise ProviderUnavailableError(
                    f"DashScope 任务查询失败: {exc}"
                ) from exc

            data = resp.json()
            output = data.get("output", {})
            status = output.get("task_status", "")

            if status == "SUCCEEDED":
                results = output.get("results", [])
                if not results:
                    raise ProviderUnavailableError("DashScope 任务成功但返回空图片列表")
                return await self._parse_results(client, results)

            if status == "FAILED":
                msg = output.get("message", "未知错误")
                code = output.get("code", "")
                raise ProviderUnavailableError(
                    f"DashScope 图片生成任务失败: code={code}, message={msg}"
                )

            if time.time() - start > _POLL_TIMEOUT:
                raise ProviderUnavailableError(
                    f"DashScope 任务 {task_id} 轮询超时（{_POLL_TIMEOUT}s）"
                )

            remaining = max(0.0, _POLL_TIMEOUT - (time.time() - start))
            await asyncio.sleep(min(interval, remaining))
            interval = min(interval * 1.5, _MAX_POLL_INTERVAL)

    async def _parse_results(
        self, client: httpx.AsyncClient, results: list[dict[str, Any]]
    ) -> ImageGenerationResult:
        """解析图片生成结果并下载图片字节。

        Args:
            client: httpx 异步客户端。
            results: DashScope 返回的图片结果列表。

        Returns:
            ImageGenerationResult。

        Raises:
            ProviderUnavailableError: 下载失败时抛出。
        """
        images: list[SingleImageResult] = []
        for item in results:
            url = item.get("url", "")
            if not url:
                continue
            try:
                img_resp = await client.get(url, timeout=60.0)
                img_resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise ProviderUnavailableError(
                    f"下载 DashScope 图片失败: {exc}"
                ) from exc
            images.append(
                SingleImageResult(data=img_resp.content, url=url, seed=item.get("seed"))
            )

        if not images:
            raise ProviderUnavailableError("DashScope 返回的图片列表为空或下载全部失败")

        return ImageGenerationResult(images=images)
