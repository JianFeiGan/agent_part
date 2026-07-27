"""
Cross-Encoder 重排序服务。

Description:
    使用 FlagEmbedding FlagReranker 对检索结果进行重排序，提升检索精度。
    懒加载模型，支持 auto/cuda/cpu 设备选择。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from src.config.settings import get_settings
from src.db.vector_store import SearchResult

logger = logging.getLogger(__name__)


@dataclass
class RerankResult:
    """重排序结果。

    Attributes:
        results: 重排序后的搜索结果列表。
        original_count: 重排序前的结果数量。
        reranked_count: 重排序后保留的结果数量。
    """

    results: list[SearchResult] = field(default_factory=list)
    original_count: int = 0
    reranked_count: int = 0


class CrossEncoderReranker:
    """Cross-Encoder 重排序服务。

    使用 FlagReranker 对检索结果进行精排，提升检索精度。

    Example:
        >>> reranker = CrossEncoderReranker()
        >>> result = await reranker.rerank("智能手表", search_results)
        >>> print(result.reranked_count)
    """

    def __init__(self) -> None:
        """初始化重排序服务。"""
        self.settings = get_settings()
        self._model: Any = None
        self._initialized = False

    def _ensure_model_loaded(self) -> None:
        """确保模型已加载。"""
        if self._initialized:
            return

        try:
            from FlagEmbedding import FlagReranker

            model_name = self.settings.reranker_model
            device = self._resolve_device(self.settings.reranker_device)

            logger.info(f"加载重排序模型: {model_name} on {device}")
            self._model = FlagReranker(
                model_name,
                use_fp16=True,
                device=device,
            )
            self._initialized = True
            logger.info("重排序模型加载完成")

        except ImportError as e:
            raise ImportError("FlagEmbedding 未安装。请运行: pip install FlagEmbedding") from e

    def _resolve_device(self, device: str) -> str:
        """解析设备配置。

        Args:
            device: 设备配置: auto/cuda/cpu。

        Returns:
            实际设备名称。
        """
        if device != "auto":
            return device

        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass

        return "cpu"

    def _compute_scores(self, query: str, documents: list[str]) -> list[float]:
        """计算重排序分数（同步方法）。

        Args:
            query: 查询文本。
            documents: 文档内容列表。

        Returns:
            重排序分数列表。
        """
        self._ensure_model_loaded()

        pairs = [[query, doc] for doc in documents]
        scores = self._model.compute_score(pairs)

        # compute_score 返回单个分数或列表
        if isinstance(scores, (int, float)):
            return [float(scores)]
        return [float(s) for s in scores]

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int | None = None,
    ) -> RerankResult:
        """对检索结果进行重排序。

        Args:
            query: 查询文本。
            results: 原始检索结果列表。
            top_k: 重排序后保留的结果数量，默认使用配置值。

        Returns:
            重排序结果。
        """
        if not self.settings.reranker_enabled:
            return RerankResult(
                results=results,
                original_count=len(results),
                reranked_count=len(results),
            )

        if not results:
            return RerankResult(
                results=[],
                original_count=0,
                reranked_count=0,
            )

        top_k = top_k or self.settings.reranker_top_k

        try:
            # 提取文档内容
            documents = [r.content for r in results]

            # 在线程中执行同步模型调用
            scores = await asyncio.to_thread(self._compute_scores, query, documents)

            # 将分数与结果配对，原始分数存入 metadata
            scored_results = []
            for result, score in zip(results, scores, strict=True):
                # 保存原始相似度到 metadata
                updated_metadata = dict(result.metadata)
                updated_metadata["original_similarity"] = result.similarity

                # 用重排序分数替换 similarity
                scored_results.append(
                    SearchResult(
                        chunk_id=result.chunk_id,
                        doc_id=result.doc_id,
                        content=result.content,
                        similarity=score,
                        metadata=updated_metadata,
                        doc_title=result.doc_title,
                        doc_type=result.doc_type,
                    )
                )

            # 按重排序分数降序排列
            scored_results.sort(key=lambda r: r.similarity, reverse=True)

            # 截取 top_k
            reranked = scored_results[:top_k]

            logger.info(f"重排序完成: 原始 {len(results)} 条 -> 保留 {len(reranked)} 条")

            return RerankResult(
                results=reranked,
                original_count=len(results),
                reranked_count=len(reranked),
            )

        except Exception as e:
            logger.warning(f"重排序失败，返回原始结果: {e}")
            return RerankResult(
                results=results[:top_k],
                original_count=len(results),
                reranked_count=min(len(results), top_k),
            )


# 全局 CrossEncoderReranker 实例
_reranker: CrossEncoderReranker | None = None


def get_reranker() -> CrossEncoderReranker:
    """获取重排序服务单例。

    Returns:
        CrossEncoderReranker 实例。
    """
    global _reranker

    if _reranker is None:
        _reranker = CrossEncoderReranker()

    return _reranker
