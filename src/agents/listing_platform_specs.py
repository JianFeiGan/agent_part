"""
各平台素材规范配置。

Description:
    定义 Amazon、eBay、Shopify 的素材尺寸、格式、数量等规范。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

from dataclasses import dataclass

from src.models.listing import Platform


@dataclass(frozen=True)
class PlatformSpec:
    """平台素材规范。

    Attributes:
        main_image_size: 主图推荐尺寸 (宽, 高)。
        white_background: 是否要求纯白背景。
        max_images: 最大图片数量。
        max_title_length: 标题最大长度（0表示无限制）。
        video_supported: 是否支持视频。
        accepted_formats: 接受的图片格式。

    Example:
        >>> spec = get_platform_spec(Platform.AMAZON)
        >>> assert spec.main_image_size == (1500, 1500)
    """

    main_image_size: tuple[int, int]
    white_background: bool
    max_images: int
    max_title_length: int
    video_supported: bool
    accepted_formats: tuple[str, ...] = ("jpg", "jpeg", "png", "webp")


AMAZON_SPEC = PlatformSpec(
    main_image_size=(1500, 1500),
    white_background=True,
    max_images=9,
    max_title_length=200,
    video_supported=True,
)

EBAY_SPEC = PlatformSpec(
    main_image_size=(1600, 1600),
    white_background=True,
    max_images=12,
    max_title_length=80,
    video_supported=True,
)

SHOPIFY_SPEC = PlatformSpec(
    main_image_size=(2048, 2048),
    white_background=False,
    max_images=999,
    max_title_length=0,
    video_supported=True,
)

_SPECS: dict[Platform, PlatformSpec] = {
    Platform.AMAZON: AMAZON_SPEC,
    Platform.EBAY: EBAY_SPEC,
    Platform.SHOPIFY: SHOPIFY_SPEC,
}


def get_platform_spec(platform: Platform) -> PlatformSpec:
    """获取平台规范。

    Args:
        platform: 目标平台。

    Returns:
        平台素材规范配置。

    Raises:
        KeyError: 平台不在预定义列表中。
    """
    return _SPECS[platform]
