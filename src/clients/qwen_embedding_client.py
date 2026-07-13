"""
千问 Embedding 客户端。

通过阿里云百炼平台的 OpenAI 兼容接口调用千问 Embedding 模型。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from src.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class QwenEmbeddingClient:
    """千问 Embedding 客户端。

    通过 OpenAI 兼容接口调用 text-embedding-v3 模型。
    """

    def __init__(
        self,
        settings: Settings | None = None,
        httpx_client: httpx.AsyncClient | None = None,
    ) -> None:
        """初始化客户端。

        Args:
            settings: 应用配置。
            httpx_client: 可注入的 httpx 异步客户端。
        """
        self._settings = settings or get_settings()
        self._httpx = httpx_client

    def is_available(self) -> bool:
        """检查是否已配置 API Key。"""
        return bool(self._settings.effective_qwen_api_key)

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 httpx 客户端。"""
        if self._httpx is None:
            self._httpx = httpx.AsyncClient(timeout=60.0)
        return self._httpx

    async def embed(self, text: str) -> list[float]:
        """生成文本向量。

        Args:
            text: 输入文本。

        Returns:
            向量列表。

        Raises:
            ValueError: 如果未配置 API Key。
            RuntimeError: 如果 API 调用失败。
        """
        result = await self.embed_batch([text])
        return result[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量生成文本向量。

        Args:
            texts: 输入文本列表。

        Returns:
            向量列表（始终返回 list[list[float]]）。

        Raises:
            ValueError: 如果未配置 API Key。
            RuntimeError: 如果 API 调用失败。
        """
        if not self.is_available():
            raise ValueError("QWEN_API_KEY 或 DASHSCOPE_API_KEY 未配置")

        api_key = self._settings.effective_qwen_api_key
        base_url = self._settings.qwen_api_base
        model = self._settings.qwen_embedding_model
        dimensions = self._settings.qwen_embedding_dimensions

        client = await self._get_client()

        url = f"{base_url.rstrip('/')}/embeddings"

        payload = {
            "model": model,
            "input": texts,
            "dimensions": dimensions,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        logger.debug(f"调用千问 Embedding API: model={model}, texts_count={len(texts)}")

        response = await client.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            error_detail = response.text
            raise RuntimeError(
                f"千问 Embedding API 调用失败: status={response.status_code}, error={error_detail}"
            )

        result = response.json()

        if "data" not in result or len(result["data"]) == 0:
            raise RuntimeError(f"千问 Embedding API 返回数据为空: {result}")

        embeddings = [item["embedding"] for item in result["data"]]
        return embeddings

    async def close(self) -> None:
        """关闭客户端。"""
        if self._httpx:
            await self._httpx.aclose()
            self._httpx = None


async def get_qwen_embedding(
    text: str,
    settings: Settings | None = None,
) -> list[float]:
    """获取文本向量。

    Args:
        text: 输入文本。
        settings: 应用配置。

    Returns:
        向量列表。
    """
    client = QwenEmbeddingClient(settings)
    return await client.embed(text)


def is_qwen_embedding_configured(settings: Settings | None = None) -> bool:
    """检查千问 Embedding 是否已配置。

    Args:
        settings: 应用配置。

    Returns:
        是否已配置 API Key。
    """
    settings = settings or get_settings()
    return bool(settings.effective_qwen_api_key)