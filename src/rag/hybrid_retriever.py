"""
BGE-M3 混合检索服务。

Description:
    使用 BGE-M3 的 Dense + Sparse + ColBERT 三路检索，通过 RRF 融合提升检索效果。
    Dense 检索复用 VectorStore，Sparse 使用 PostgreSQL 全文搜索，ColBERT 复用 Dense 结果。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.db.vector_store import SearchResult, VectorStore
from src.rag.embeddings import EmbeddingService, get_embedding_service

logger = logging.getLogger(__name__)


@dataclass
class HybridSearchResult:
    """混合检索结果。

    Attributes:
        results: 融合后的搜索结果列表。
        dense_count: Dense 检索结果数量。
        sparse_count: Sparse 检索结果数量。
        colbert_count: ColBERT 检索结果数量。
        method: 检索方法标识。
    """

    results: list[SearchResult] = field(default_factory=list)
    dense_count: int = 0
    sparse_count: int = 0
    colbert_count: int = 0
    method: str = "hybrid"


class HybridRetriever:
    """BGE-M3 混合检索服务。

    支持 Dense + Sparse + ColBERT 三路检索，通过 RRF 融合。

    Example:
        >>> retriever = HybridRetriever()
        >>> result = await retriever.search(session, "智能手表", tenant_id="t1")
        >>> print(result.method)
    """

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        """初始化混合检索服务。

        Args:
            embedding_service: Embedding 服务实例。
            vector_store: 向量存储实例。
        """
        self.settings = get_settings()
        self.embedding_service = embedding_service or get_embedding_service()
        self.vector_store = vector_store or VectorStore()
        self._model: Any = None
        self._initialized = False

    def _ensure_model_loaded(self) -> None:
        """确保 BGE-M3 模型已加载。"""
        if self._initialized:
            return

        try:
            from FlagEmbedding import BGEM3FlagModel

            model_name = self.settings.hybrid_model
            device = self._resolve_device(self.settings.embedding_device)

            logger.info(f"加载混合检索模型: {model_name} on {device}")
            self._model = BGEM3FlagModel(
                model_name,
                use_fp16=True,
                device=device,
            )
            self._initialized = True
            logger.info("混合检索模型加载完成")

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

    def encode(self, texts: list[str]) -> dict[str, Any]:
        """使用 BGE-M3 编码文本，返回三路表示。

        Args:
            texts: 待编码的文本列表。

        Returns:
            包含 dense_embedding、sparse_weights、colbert_vecs 的字典。
        """
        self._ensure_model_loaded()

        encoding = self._model.encode(
            texts,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=True,
        )

        return {
            "dense_embedding": encoding.get("dense_vecs"),
            "sparse_weights": encoding.get("lexical_weights"),
            "colbert_vecs": encoding.get("colbert_vecs"),
        }

    async def search(
        self,
        session: AsyncSession,
        query: str,
        *,
        tenant_id: str,
        top_k: int | None = None,
        doc_type: str | None = None,
        category: str | None = None,
        similarity_threshold: float | None = None,
    ) -> HybridSearchResult:
        """执行混合检索。

        Dense 检索 + Sparse 全文搜索 + ColBERT → RRF 融合。

        Args:
            session: 数据库会话。
            query: 查询文本。
            tenant_id: 租户 ID。
            top_k: 返回结果数量。
            doc_type: 文档类型过滤。
            category: 商品类目过滤。
            similarity_threshold: 相似度阈值。

        Returns:
            混合检索结果。
        """
        if not self.settings.hybrid_retrieval_enabled:
            # 未启用混合检索，回退到纯 Dense 检索
            query_embedding = await self.embedding_service.aembed_single(query)
            results = await self.vector_store.search(
                session,
                query_embedding,
                tenant_id=tenant_id,
                top_k=top_k,
                doc_type=doc_type,
                category=category,
                similarity_threshold=similarity_threshold,
            )
            return HybridSearchResult(
                results=results,
                dense_count=len(results),
                method="dense",
            )

        top_k = top_k or self.settings.retrieval_top_k

        try:
            # 1. Dense 检索（复用 VectorStore）
            query_embedding = await self.embedding_service.aembed_single(query)
            dense_results = await self.vector_store.search(
                session,
                query_embedding,
                tenant_id=tenant_id,
                top_k=top_k * 3,  # 多取一些用于融合
                doc_type=doc_type,
                category=category,
                similarity_threshold=similarity_threshold,
            )

            # 2. Sparse 检索（PostgreSQL 全文搜索）
            sparse_results = await self._sparse_search(
                session,
                query,
                tenant_id=tenant_id,
                top_k=top_k * 3,
                doc_type=doc_type,
                category=category,
            )

            # 3. ColBERT 复用 Dense 结果（BGE-M3 的 ColBERT 需要逐对计算，
            #    在大规模场景下开销较大，此处复用 Dense 结果作为 ColBERT 排名）
            colbert_results = dense_results

            # 4. RRF 融合
            fused = self._rrf_fuse(
                dense_results=dense_results,
                sparse_results=sparse_results,
                colbert_results=colbert_results,
                top_k=top_k,
            )

            logger.info(
                f"混合检索完成: Dense={len(dense_results)}, "
                f"Sparse={len(sparse_results)}, "
                f"融合后={len(fused)}"
            )

            return HybridSearchResult(
                results=fused,
                dense_count=len(dense_results),
                sparse_count=len(sparse_results),
                colbert_count=len(colbert_results),
                method="hybrid",
            )

        except Exception as e:
            logger.warning(f"混合检索失败，回退到 Dense 检索: {e}")
            query_embedding = await self.embedding_service.aembed_single(query)
            results = await self.vector_store.search(
                session,
                query_embedding,
                tenant_id=tenant_id,
                top_k=top_k,
                doc_type=doc_type,
                category=category,
                similarity_threshold=similarity_threshold,
            )
            return HybridSearchResult(
                results=results,
                dense_count=len(results),
                method="dense_fallback",
            )

    async def _sparse_search(
        self,
        session: AsyncSession,
        query: str,
        *,
        tenant_id: str,
        top_k: int = 15,
        doc_type: str | None = None,
        category: str | None = None,
    ) -> list[SearchResult]:
        """Sparse 稀疏检索（PostgreSQL 全文搜索）。

        使用 PostgreSQL 的 to_tsvector 和 plainto_tsquery 实现全文搜索。

        Args:
            session: 数据库会话。
            query: 查询文本。
            tenant_id: 租户 ID。
            top_k: 返回结果数量。
            doc_type: 文档类型过滤。
            category: 商品类目过滤。

        Returns:
            搜索结果列表。
        """
        sql = text("""
            SELECT
                kc.id as chunk_id,
                kc.doc_id,
                kc.content,
                kc.metadata,
                kd.title as doc_title,
                kd.doc_type,
                ts_rank(
                    to_tsvector('simple', kc.content),
                    plainto_tsquery('simple', :query)
                ) as similarity
            FROM knowledge_chunks kc
            JOIN knowledge_docs kd ON kc.doc_id = kd.id
            WHERE to_tsvector('simple', kc.content) @@ plainto_tsquery('simple', :query)
                AND kc.tenant_id = :tenant_id
                AND (CAST(:doc_type AS text) IS NULL OR kd.doc_type = CAST(:doc_type AS text))
                AND (CAST(:category AS text) IS NULL OR kd.category = CAST(:category AS text))
            ORDER BY similarity DESC
            LIMIT :top_k
        """)

        result = await session.execute(
            sql,
            {
                "query": query,
                "tenant_id": tenant_id,
                "doc_type": doc_type,
                "category": category,
                "top_k": top_k,
            },
        )

        rows = result.fetchall()
        return [
            SearchResult(
                chunk_id=row.chunk_id,
                doc_id=row.doc_id,
                content=row.content,
                similarity=float(row.similarity) if row.similarity else 0.0,
                metadata=row.metadata or {},
                doc_title=row.doc_title,
                doc_type=row.doc_type,
            )
            for row in rows
        ]

    def _rrf_fuse(
        self,
        dense_results: list[SearchResult],
        sparse_results: list[SearchResult],
        colbert_results: list[SearchResult],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Reciprocal Rank Fusion 融合三路检索结果。

        RRF 公式: score(d) = sum(w_i / (k + rank_i(d)))

        Args:
            dense_results: Dense 检索结果。
            sparse_results: Sparse 检索结果。
            colbert_results: ColBERT 检索结果。
            top_k: 融合后保留的结果数量。

        Returns:
            融合后的搜索结果列表。
        """
        k = self.settings.hybrid_rrf_k
        dense_weight = self.settings.hybrid_dense_weight
        sparse_weight = self.settings.hybrid_sparse_weight
        colbert_weight = self.settings.hybrid_colbert_weight

        # 构建 chunk_id -> (rrf_score, SearchResult) 映射
        score_map: dict[int, float] = {}
        result_map: dict[int, SearchResult] = {}

        # Dense 路贡献
        for rank, result in enumerate(dense_results, 1):
            cid = result.chunk_id
            score_map[cid] = score_map.get(cid, 0.0) + dense_weight / (k + rank)
            if cid not in result_map:
                result_map[cid] = result

        # Sparse 路贡献
        for rank, result in enumerate(sparse_results, 1):
            cid = result.chunk_id
            score_map[cid] = score_map.get(cid, 0.0) + sparse_weight / (k + rank)
            if cid not in result_map:
                result_map[cid] = result

        # ColBERT 路贡献
        for rank, result in enumerate(colbert_results, 1):
            cid = result.chunk_id
            score_map[cid] = score_map.get(cid, 0.0) + colbert_weight / (k + rank)
            if cid not in result_map:
                result_map[cid] = result

        # 按 RRF 分数降序排列
        sorted_ids = sorted(score_map, key=lambda cid: score_map[cid], reverse=True)
        sorted_ids = sorted_ids[:top_k]

        # 构建融合结果，用 RRF 分数替换 similarity
        fused_results = []
        for cid in sorted_ids:
            original = result_map[cid]
            fused_results.append(
                SearchResult(
                    chunk_id=original.chunk_id,
                    doc_id=original.doc_id,
                    content=original.content,
                    similarity=score_map[cid],
                    metadata={**original.metadata, "rrf_score": score_map[cid]},
                    doc_title=original.doc_title,
                    doc_type=original.doc_type,
                )
            )

        return fused_results


# 全局 HybridRetriever 实例
_hybrid_retriever: HybridRetriever | None = None


def get_hybrid_retriever() -> HybridRetriever:
    """获取混合检索服务单例。

    Returns:
        HybridRetriever 实例。
    """
    global _hybrid_retriever

    if _hybrid_retriever is None:
        _hybrid_retriever = HybridRetriever()

    return _hybrid_retriever
