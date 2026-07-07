"""
Provider 结果数据类与共享辅助函数。

定义图片 / 视频真实 provider 的统一结果结构、降级判定函数，
以及自定义异常 ProviderUnavailableError。

本模块不依赖任何外部 SDK，便于离线单测与 Agent 侧复用。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config.settings import Settings


@dataclass
class SingleImageResult:
    """单张图片生成结果。

    Attributes:
        data: 下载后的图片字节（落 StorageBackend 用）。
        url: 远端临时 URL（可记入 metadata）。
        seed: 随机种子，未提供时为 None。
    """

    data: bytes
    url: str
    seed: int | None


@dataclass
class ImageGenerationResult:
    """图片生成结果集合。

    Attributes:
        images: 生成的图片结果列表。
    """

    images: list[SingleImageResult]


@dataclass
class VideoGenerationResult:
    """视频生成结果。

    Attributes:
        data: 下载后的视频字节。
        url: 远端结果 URL。
        duration: 实际时长（秒）。
        task_id: Provider 任务 ID（可记入 metadata）。
    """

    data: bytes
    url: str
    duration: float
    task_id: str


class ProviderUnavailableError(Exception):
    """Provider 不可用异常。

    当真实 provider 调用失败（鉴权失败、网络错误、任务失败、下载失败等）
    时由 client 抛出，Agent 捕获后降级为 Mock，不向上抛错。
    """


def is_image_provider_configured(settings: Settings) -> bool:
    """判断图片 provider（DashScope）是否已配置 API Key。

    Args:
        settings: 应用配置实例。

    Returns:
        已配置返回 True，否则 False。
    """
    return bool(getattr(settings, "dashscope_api_key", ""))


def is_video_provider_configured(settings: Settings) -> bool:
    """判断视频 provider（Kling）是否已配置 Access / Secret Key。

    Args:
        settings: 应用配置实例。

    Returns:
        Access Key 与 Secret Key 均非空时返回 True，否则 False。
    """
    access_key = getattr(settings, "kling_access_key", "")
    secret_key = getattr(settings, "kling_secret_key", "")
    return bool(access_key) and bool(secret_key)
