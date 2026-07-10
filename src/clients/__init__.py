"""
Provider 客户端包。

提供真实图片 / 视频生成 provider 的客户端封装与工厂函数：
- ``DashScopeImageClient``：通义万象（wanx-v1）图片生成。
- ``KlingVideoClient``：可灵 AI（kling-v1）视频生成。
- ``get_image_client`` / ``get_video_client``：读配置创建客户端，未配置则返回 None 表示降级。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.clients.dashscope_image_client import DashScopeImageClient
from src.clients.kling_video_client import KLING_API_BASE, KlingVideoClient
from src.clients.provider_result import (
    ImageGenerationResult,
    ProviderUnavailableError,
    SingleImageResult,
    VideoGenerationResult,
    is_image_provider_configured,
    is_video_provider_configured,
)
from src.config.settings import Settings, get_settings

if TYPE_CHECKING:
    import httpx

__all__ = [
    "DashScopeImageClient",
    "KlingVideoClient",
    "ImageGenerationResult",
    "SingleImageResult",
    "VideoGenerationResult",
    "ProviderUnavailableError",
    "is_image_provider_configured",
    "is_video_provider_configured",
    "get_image_client",
    "get_video_client",
]


def get_image_client(
    settings: Settings | None = None,
    httpx_client: httpx.AsyncClient | None = None,
) -> DashScopeImageClient | None:
    """创建图片客户端；未配置 DashScope API Key 时返回 None（降级）。

    Args:
        settings: 应用配置，默认从 ``get_settings()`` 读取。
        httpx_client: 可注入的 httpx 异步客户端。

    Returns:
        已配置的 ``DashScopeImageClient`` 实例，未配置时返回 None。
    """
    client_settings = settings or get_settings()
    client = DashScopeImageClient(settings=client_settings, httpx_client=httpx_client)
    if client.is_available():
        return client
    return None


def get_video_client(
    settings: Settings | None = None,
    base_url: str | None = None,
    httpx_client: httpx.AsyncClient | None = None,
) -> KlingVideoClient | None:
    """创建视频客户端；未配置 Kling Key 时返回 None（降级）。

    Args:
        settings: 应用配置，默认从 ``get_settings()`` 读取。
        base_url: API 基址，默认 ``KLING_API_BASE``。
        httpx_client: 可注入的 httpx 异步客户端。

    Returns:
        已配置的 ``KlingVideoClient`` 实例，未配置时返回 None。
    """
    client_settings = settings or get_settings()
    client = KlingVideoClient(
        settings=client_settings,
        base_url=base_url or KLING_API_BASE,
        httpx_client=httpx_client,
    )
    if client.is_available():
        return client
    return None
