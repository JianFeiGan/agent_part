"""OpenAI 兼容协议 LLM Provider。

Description:
    基于 langchain_openai.ChatOpenAI 的 LLM Provider 实现。
    通义千问和商汤都支持 OpenAI 兼容接口，
    只需配置不同的 base_url + api_key + model 即可切换。
    不依赖任何厂商 SDK。
@author ganjianfei
@version 1.0.0
2026-07-22
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

from src.clients.protocols import LLMProviderProtocol
from src.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class OpenAICompatibleLLMProvider:
    """基于 OpenAI 兼容协议的 LLM Provider。

    适用于所有支持 OpenAI Chat Completions API 的厂商，
    包括商汤 SenseNova、阿里云通义千问等。

    Example:
        >>> provider = OpenAICompatibleLLMProvider(
        ...     base_url="https://token.sensenova.cn/v1",
        ...     api_key="sk-xxx",
        ...     model="sensenova-6.7-flash-lite",
        ... )
        >>> llm = provider.create_chat_model()
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> None:
        """初始化 OpenAI 兼容 LLM Provider。

        Args:
            base_url: API 基址。
            api_key: API Key。
            model: 模型名称。
            temperature: 采样温度。
            max_tokens: 最大生成 token 数。
            **kwargs: 其他参数。
        """
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._extra = kwargs

    def is_available(self) -> bool:
        """是否已配置 API Key。"""
        return bool(self._api_key)

    def create_chat_model(self) -> BaseChatModel:
        """创建 LangChain ChatOpenAI 实例。

        Returns:
            ChatOpenAI 实例，可用于 LangChain chain。

        Raises:
            ImportError: langchain-openai 未安装时抛出。
        """
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            raise ImportError(
                "langchain-openai 未安装。请运行: pip install langchain-openai"
            ) from e

        return ChatOpenAI(
            model=self._model,
            api_key=self._api_key,
            base_url=self._base_url,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )


class SettingsFallbackLLMProvider:
    """从 Settings 环境变量读取配置的兜底 LLM Provider。

    当数据库中无厂商配置时，从 .env 环境变量读取默认 Provider。
    保持向后兼容。
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """初始化兜底 LLM Provider。

        Args:
            settings: 应用配置，默认从 get_settings() 读取。
        """
        self._settings = settings or get_settings()

    def is_available(self) -> bool:
        """是否已配置任何 LLM API Key。"""
        return bool(
            self._settings.dashscope_api_key
            or getattr(self._settings, "sensenova_api_key", "")
        )

    def create_chat_model(self) -> BaseChatModel:
        """创建 LLM 实例（从 Settings 配置）。

        Returns:
            ChatOpenAI 实例。

        Raises:
            ValueError: 未配置任何 API Key 时抛出。
        """
        # 优先使用 sensenova_api_key（如果配置了）
        sensenova_key = getattr(self._settings, "sensenova_api_key", "")
        if sensenova_key:
            sensenova_url = getattr(
                self._settings, "sensenova_base_url", "https://token.sensenova.cn/v1"
            )
            return OpenAICompatibleLLMProvider(
                base_url=sensenova_url,
                api_key=sensenova_key,
                model=self._settings.llm_model,
            ).create_chat_model()

        # 兜底使用 dashscope_api_key（通义千问 OpenAI 兼容接口）
        if self._settings.dashscope_api_key:
            return OpenAICompatibleLLMProvider(
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key=self._settings.dashscope_api_key,
                model=self._settings.llm_model,
            ).create_chat_model()

        raise ValueError(
            "未配置任何 LLM Provider API Key。"
            "请在模型厂商管理页面配置，或设置 DASHSCOPE_API_KEY / SENSENOVA_API_KEY 环境变量。"
        )
