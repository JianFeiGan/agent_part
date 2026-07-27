"""Provider 工厂：从数据库配置动态创建 Provider 实例。

Description:
    根据 model_providers 表中的配置，动态创建 LLM、图片、视频 Provider 实例。
    支持任务级指定厂商（通过 provider_id）和全局默认厂商。
    当数据库无配置时，fallback 到 Settings 环境变量。
@author ganjianfei
@version 1.0.0
2026-07-22
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.protocols import ImageProviderProtocol, LLMProviderProtocol, VideoProviderProtocol
from src.clients.provider_result import get_api_key_value
from src.config.settings import Settings, get_settings

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)


class ProviderFactory:
    """DB 驱动的 Provider 工厂。

    从 model_providers 表读取配置，动态创建对应的 Provider 实例。
    支持按任务指定厂商或使用全局默认厂商。

    Example:
        >>> factory = ProviderFactory()
        >>> llm_provider = await factory.get_llm_provider(session, "tenant-1")
        >>> image_provider = await factory.get_image_provider(session, "tenant-1", provider_id=5)
    """

    @staticmethod
    async def get_llm_provider(
        session: AsyncSession | None = None,
        tenant_id: str = "system",
        provider_id: int | None = None,
    ) -> LLMProviderProtocol | None:
        """获取 LLM Provider。

        优先使用 provider_id（任务级指定），否则使用该类型的默认厂商。
        当数据库无配置时，fallback 到 Settings 环境变量。

        Args:
            session: 异步数据库会话（为 None 时走 Settings 兜底）。
            tenant_id: 租户 ID。
            provider_id: 任务级指定的厂商 ID。

        Returns:
            LLM Provider 实例，未配置时返回 None。
        """
        config = await _resolve_provider_config(
            session, tenant_id, "llm", provider_id
        )
        if config is not None:
            return _create_llm_from_config(config)

        # Fallback：从 Settings 环境变量
        return _create_llm_from_settings()

    @staticmethod
    async def get_image_provider(
        session: AsyncSession | None = None,
        tenant_id: str = "system",
        provider_id: int | None = None,
        **kwargs: Any,
    ) -> ImageProviderProtocol | None:
        """获取图片生成 Provider。

        Args:
            session: 异步数据库会话。
            tenant_id: 租户 ID。
            provider_id: 任务级指定的厂商 ID。
            **kwargs: 额外参数（如 httpx_client）。

        Returns:
            图片 Provider 实例，未配置时返回 None。
        """
        config = await _resolve_provider_config(
            session, tenant_id, "image", provider_id
        )
        if config is not None:
            return _create_image_from_config(config, **kwargs)

        # Fallback：从 Settings 环境变量
        return _create_image_from_settings(**kwargs)

    @staticmethod
    async def get_video_provider(
        session: AsyncSession | None = None,
        tenant_id: str = "system",
        provider_id: int | None = None,
        **kwargs: Any,
    ) -> VideoProviderProtocol | None:
        """获取视频生成 Provider。

        Args:
            session: 异步数据库会话。
            tenant_id: 租户 ID。
            provider_id: 任务级指定的厂商 ID。
            **kwargs: 额外参数。

        Returns:
            视频 Provider 实例，未配置时返回 None。
        """
        config = await _resolve_provider_config(
            session, tenant_id, "video", provider_id
        )
        if config is not None:
            return _create_video_from_config(config, **kwargs)

        # Fallback：从 Settings 环境变量
        return _create_video_from_settings(**kwargs)


async def _resolve_provider_config(
    session: AsyncSession | None,
    tenant_id: str,
    provider_type: str,
    provider_id: int | None,
) -> Any | None:
    """从数据库查询厂商配置。

    Args:
        session: 数据库会话。
        tenant_id: 租户 ID。
        provider_type: 厂商类型。
        provider_id: 指定的厂商 ID。

    Returns:
        ModelProviderPO 实例，无结果时返回 None。
    """
    if session is None:
        return None

    try:
        from src.db.model_provider_repository import ModelProviderRepository

        repo = ModelProviderRepository(session)
        if provider_id:
            return await repo.get_for_tenant(provider_id, tenant_id)
        return await repo.get_default(tenant_id, provider_type)
    except Exception as exc:
        logger.warning("从数据库获取厂商配置失败，将使用 Settings 兜底: %s", exc)
        return None


def _create_llm_from_config(config: Any) -> LLMProviderProtocol:
    """根据 DB 配置创建 LLM Provider 实例。

    Args:
        config: ModelProviderPO 实例。

    Returns:
        LLM Provider 实例。

    Raises:
        ValueError: 不支持的协议类型。
    """
    from src.clients.openai_compatible_llm import OpenAICompatibleLLMProvider

    api_key = get_api_key_value(config.api_key)

    if config.protocol == "openai_compatible":
        extra = config.model_config_extra or {}
        return OpenAICompatibleLLMProvider(
            base_url=config.base_url,
            api_key=api_key,
            model=config.default_model,
            temperature=extra.get("temperature", 0.7),
            max_tokens=extra.get("max_tokens", 4096),
        )

    raise ValueError(f"不支持的 LLM 协议: {config.protocol}")


def _create_image_from_config(
    config: Any, **kwargs: Any
) -> ImageProviderProtocol:
    """根据 DB 配置创建图片 Provider 实例。

    Args:
        config: ModelProviderPO 实例。
        **kwargs: 额外参数。

    Returns:
        图片 Provider 实例。

    Raises:
        ValueError: 不支持的厂商或协议。
    """
    from src.clients.dashscope_image_client import DashScopeImageClient
    from src.clients.openai_compatible_image import OpenAICompatibleImageProvider

    api_key = get_api_key_value(config.api_key)

    if config.protocol == "openai_compatible":
        return OpenAICompatibleImageProvider(
            base_url=config.base_url,
            api_key=api_key,
            model=config.default_model,
            **kwargs,
        )

    if config.name == "dashscope":
        return DashScopeImageClient(
            api_key=api_key,
            model=config.default_model,
            **kwargs,
        )

    raise ValueError(f"不支持的图片厂商: {config.name} (protocol={config.protocol})")


def _create_video_from_config(
    config: Any, **kwargs: Any
) -> VideoProviderProtocol:
    """根据 DB 配置创建视频 Provider 实例。

    Args:
        config: ModelProviderPO 实例。
        **kwargs: 额外参数。

    Returns:
        视频 Provider 实例。

    Raises:
        ValueError: 不支持的视频厂商。
    """
    from src.clients.kling_video_client import KlingVideoClient, KLING_API_BASE

    extra_creds = config.extra_credentials or {}

    if config.name == "kling":
        # Kling 使用 access_key + secret_key 鉴权
        access_key = str(extra_creds.get("access_key", ""))
        secret_key = str(extra_creds.get("secret_key", ""))
        return KlingVideoClient(
            settings=None,
            base_url=kwargs.pop("base_url", config.base_url or KLING_API_BASE),
            httpx_client=kwargs.pop("httpx_client", None),
            access_key=access_key or None,
            secret_key=secret_key or None,
        )

    raise ValueError(f"不支持的视频厂商: {config.name}")


# ==================== Settings 兜底工厂 ====================


def _create_llm_from_settings() -> LLMProviderProtocol | None:
    """从 Settings 环境变量创建 LLM Provider（兜底）。

    Returns:
        LLM Provider 实例，未配置任何 Key 时返回 None。
    """
    from src.clients.openai_compatible_llm import SettingsFallbackLLMProvider

    provider = SettingsFallbackLLMProvider()
    if provider.is_available():
        return provider
    return None


def _create_image_from_settings(**kwargs: Any) -> ImageProviderProtocol | None:
    """从 Settings 环境变量创建图片 Provider（兜底）。

    优先使用 SenseNova 图片 Provider（如果配置了 sensenova_api_key），
    否则使用 DashScope 图片 Provider。

    Returns:
        图片 Provider 实例，未配置时返回 None。
    """
    from src.clients.dashscope_image_client import DashScopeImageClient
    from src.clients.openai_compatible_image import OpenAICompatibleImageProvider

    settings = get_settings()
    # 优先使用 SenseNova 图片 Provider
    sensenova_key = getattr(settings, "sensenova_api_key", "")
    if sensenova_key:
        sensenova_url = getattr(
            settings, "sensenova_base_url", "https://token.sensenova.cn/v1"
        )
        return OpenAICompatibleImageProvider(
            base_url=sensenova_url,
            api_key=sensenova_key,
            model=settings.image_model,
            **kwargs,
        )
    # 兜底使用 DashScope 图片 Provider
    if settings.dashscope_api_key:
        return DashScopeImageClient(
            api_key=settings.dashscope_api_key,
            model=settings.image_model,
            **kwargs,
        )
    return None


def _create_video_from_settings(**kwargs: Any) -> VideoProviderProtocol | None:
    """从 Settings 环境变量创建视频 Provider（兜底）。

    Returns:
        视频 Provider 实例，未配置时返回 None。
    """
    from src.clients.kling_video_client import KlingVideoClient, KLING_API_BASE

    settings = get_settings()
    if settings.kling_access_key and settings.kling_secret_key:
        # KlingVideoClient 需要 settings 对象
        return KlingVideoClient(
            settings=settings,
            base_url=kwargs.pop("base_url", KLING_API_BASE),
            httpx_client=kwargs.pop("httpx_client", None),
        )
    return None
