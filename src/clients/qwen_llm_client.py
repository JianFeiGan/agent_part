"""
千问 LLM 客户端。

通过阿里云百炼平台的 OpenAI 兼容接口调用千问系列 LLM 模型。
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from src.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def get_qwen_llm(
    settings: Settings | None = None,
    model: str | None = None,
    temperature: float = 0.7,
    **kwargs: Any,
) -> BaseChatModel:
    """获取千问 LLM 客户端。

    Args:
        settings: 应用配置。
        model: 模型名称，默认使用配置中的 qwen_llm_model。
        temperature: 温度参数。
        **kwargs: 其他传递给 ChatOpenAI 的参数。

    Returns:
        LangChain ChatOpenAI 实例。

    Raises:
        ValueError: 如果未配置 QWEN_API_KEY。
    """
    settings = settings or get_settings()

    api_key = settings.qwen_api_key
    if not api_key:
        raise ValueError("QWEN_API_KEY 未配置，请检查 .env 文件")

    base_url = settings.qwen_api_base
    model_name = model or settings.qwen_llm_model

    logger.info(f"初始化千问 LLM: model={model_name}, base_url={base_url}")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        **kwargs,
    )


def is_qwen_llm_configured(settings: Settings | None = None) -> bool:
    """检查千问 LLM 是否已配置。

    Args:
        settings: 应用配置。

    Returns:
        是否已配置 API Key。
    """
    settings = settings or get_settings()
    return bool(settings.qwen_api_key)