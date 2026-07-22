"""OpenAI 兼容协议图片生成 Provider。

Description:
    基于 OpenAI Images API（/v1/images/generations）的图片生成 Provider。
    适用于商汤 SenseNova U1 Fast 等支持该接口的厂商。
    使用 httpx 直接 HTTP 调用，不依赖任何厂商 SDK。
@author ganjianfei
@version 1.0.0
2026-07-22
"""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from src.clients.provider_result import (
    ImageGenerationResult,
    ProviderUnavailableError,
    SingleImageResult,
)

logger = logging.getLogger(__name__)

# 宽高比到 SenseNova U1 Fast 支持尺寸的映射
_SIZE_MAP: dict[tuple[int, int], str] = {
    (1024, 1024): "2048x2048",  # 1:1
    (1024, 768): "2368x1760",  # 4:3
    (768, 1024): "1760x2368",  # 3:4
    (1920, 1080): "2752x1536",  # 16:9
    (1080, 1920): "1536x2752",  # 9:16
    (1536, 1024): "2496x1664",  # 3:2
    (1024, 1536): "1664x2496",  # 2:3
}


class OpenAICompatibleImageProvider:
    """基于 OpenAI Images API 的图片生成 Provider。

    适用于商汤 SenseNova U1 Fast 等支持 /v1/images/generations 接口的厂商。
    注意：SenseNova U1 Fast 返回的图片 URL 有效期仅 1 小时，
    生成后需立即下载并持久化。

    Example:
        >>> provider = OpenAICompatibleImageProvider(
        ...     base_url="https://token.sensenova.cn/v1",
        ...     api_key="sk-xxx",
        ...     model="sensenova-u1-fast",
        ... )
        >>> result = await provider.generate(prompt="一只可爱的猫咪")
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        httpx_client: httpx.AsyncClient | None = None,
        **kwargs: Any,
    ) -> None:
        """初始化 OpenAI 兼容图片 Provider。

        Args:
            base_url: API 基址。
            api_key: API Key。
            model: 模型名称（如 sensenova-u1-fast）。
            httpx_client: 可注入的 httpx 异步客户端；为 None 时懒创建。
            **kwargs: 其他参数。
        """
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._httpx = httpx_client

    def is_available(self) -> bool:
        """是否已配置 API Key。"""
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
        """生成图片。

        Args:
            prompt: 正向提示词。
            negative_prompt: 负向提示词（SenseNova U1 Fast 不支持，忽略）。
            width: 图片宽度。
            height: 图片高度。
            n: 生成数量。
            seed: 随机种子。

        Returns:
            图片生成结果。

        Raises:
            ProviderUnavailableError: 调用或下载失败时抛出。
        """
        client = self._httpx or httpx.AsyncClient()
        try:
            size = self._map_size(width, height)
            body: dict[str, Any] = {
                "model": self._model,
                "prompt": prompt,
                "size": size,
                "n": n,
            }
            if seed is not None:
                body["seed"] = seed

            try:
                resp = await client.post(
                    f"{self._base_url}/images/generations",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                    timeout=300.0,
                )
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise ProviderUnavailableError(
                    f"OpenAI 兼容图片生成调用失败: {exc}"
                ) from exc

            data = resp.json()
            images_data = data.get("data", [])
            if not images_data:
                raise ProviderUnavailableError("图片生成返回的图片列表为空")

            images: list[SingleImageResult] = []
            for item in images_data:
                img_bytes, url = await self._extract_image(client, item)
                images.append(
                    SingleImageResult(data=img_bytes, url=url, seed=seed)
                )

            return ImageGenerationResult(images=images)
        finally:
            if self._httpx is None:
                await client.aclose()

    def _map_size(self, width: int, height: int) -> str:
        """将宽高映射为厂商支持的尺寸字符串。

        Args:
            width: 宽度。
            height: 高度。

        Returns:
            尺寸字符串（如 "2048x2048"）。
        """
        return _SIZE_MAP.get((width, height), "2048x2048")

    async def _extract_image(
        self, client: httpx.AsyncClient, item: dict[str, Any]
    ) -> tuple[bytes, str]:
        """从响应项提取图片字节。

        优先下载 url，若无 url 则尝试 b64_json。

        Args:
            client: httpx 异步客户端。
            item: 响应项。

        Returns:
            (图片字节, 远端 URL) 元组。

        Raises:
            ProviderUnavailableError: 下载失败时抛出。
        """
        url = item.get("url", "")
        if url:
            try:
                img_resp = await client.get(url, timeout=60.0)
                img_resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise ProviderUnavailableError(
                    f"下载图片失败: {exc}"
                ) from exc
            return img_resp.content, url

        b64 = item.get("b64_json", "")
        if b64:
            return base64.b64decode(b64), ""

        raise ProviderUnavailableError("图片响应项缺少 url 和 b64_json")
