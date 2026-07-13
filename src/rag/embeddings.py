"""
Embedding 服务封装。

Description:
    封装 BGE-large-zh 和千问 Embedding 模型，提供文本向量化功能。
@author ganjianfei
@version 1.0.0
2026-04-05
"""

import logging
from typing import Any

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Embedding 服务封装。

    支持本地 BGE 模型和千问 Embedding API。

    Example:
        >>> embedding_service = EmbeddingService()
        >>> vector = await embedding_service.embed_single("商品卖点分析")
        >>> vectors = await embedding_service.embed_batch(["文本1", "文本2"])
    """

    def __init__(self) -> None:
        """初始化 Embedding 服务。"""
        self.settings = get_settings()
        self._model: Any = None
        self._initialized = False
        self._qwen_client = None

    def _is_qwen_provider(self) -> bool:
        """检查是否使用千问 Embedding。"""
        return self.settings.embedding_provider == "qwen"

    def _ensure_model_loaded(self) -> None:
        """确保模型已加载（本地模型）。"""
        if self._initialized:
            return

        if self._is_qwen_provider():
            return

        try:
            from sentence_transformers import SentenceTransformer

            model_name = self.settings.embedding_model
            device = self.settings.embedding_device

            logger.info(f"Loading embedding model: {model_name} on {device}")
            self._model = SentenceTransformer(model_name, device=device)
            self._initialized = True
            logger.info(
                f"Embedding model loaded successfully (dimension: {self._model.get_sentence_embedding_dimension()})"
            )

        except ImportError as e:
            raise ImportError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers FlagEmbedding"
            ) from e

    async def _get_qwen_client(self):
        """获取千问 Embedding 客户端。"""
        if self._qwen_client is None:
            from src.clients.qwen_embedding_client import QwenEmbeddingClient
            self._qwen_client = QwenEmbeddingClient(self.settings)
        return self._qwen_client

    @property
    def dimension(self) -> int:
        """获取向量维度。

        Returns:
            向量维度。
        """
        if self._is_qwen_provider():
            return self.settings.qwen_embedding_dimensions
        self._ensure_model_loaded()
        return self._model.get_sentence_embedding_dimension()

    def embed_single(self, text: str) -> list[float]:
        """将单个文本转换为向量。

        Args:
            text: 输入文本。

        Returns:
            向量列表。
        """
        if self._is_qwen_provider():
            raise RuntimeError("千问 Embedding 仅支持异步调用，请使用 aembed_single")

        self._ensure_model_loaded()

        embedding = self._model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """批量将文本转换为向量。

        Args:
            texts: 输入文本列表。
            batch_size: 批处理大小。

        Returns:
            向量列表的列表。
        """
        if self._is_qwen_provider():
            raise RuntimeError("千问 Embedding 仅支持异步调用，请使用 aembed_batch")

        self._ensure_model_loaded()

        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 100,
        )
        return [emb.tolist() for emb in embeddings]

    async def aembed_single(self, text: str) -> list[float]:
        """异步将单个文本转换为向量。

        Args:
            text: 输入文本。

        Returns:
            向量列表。
        """
        if self._is_qwen_provider():
            client = await self._get_qwen_client()
            return await client.embed(text)

        import asyncio
        return await asyncio.to_thread(self.embed_single, text)

    async def aembed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """异步批量将文本转换为向量。

        Args:
            texts: 输入文本列表。
            batch_size: 批处理大小。

        Returns:
            向量列表的列表。
        """
        if self._is_qwen_provider():
            client = await self._get_qwen_client()
            return await client.embed_batch(texts)

        import asyncio
        return await asyncio.to_thread(self.embed_batch, texts, batch_size)


_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """获取 Embedding 服务单例。

    Returns:
        Embedding 服务实例。
    """
    global _embedding_service

    if _embedding_service is None:
        _embedding_service = EmbeddingService()

    return _embedding_service