"""
向量存储接口。

Description:
    封装 PGVector 向量存储和检索操作。
@author ganjianfei
@version 1.0.0
2026-04-05
"""

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.db.models import KnowledgeChunk

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """检索结果。

    Attributes:
        chunk_id: 分块 ID。
        doc_id: 文档 ID。
        content: 分块内容。
        similarity: 相似度分数。
        metadata: 元数据。
        doc_title: 文档标题。
        doc_type: 文档类型。
    """

    chunk_id: int
    doc_id: int
    content: str
    similarity: float
    metadata: dict[str, Any]
    doc_title: str
    doc_type: str


class VectorStore:
    """向量存储接口。

    提供向量存储和相似度检索功能。

    Example:
        >>> vector_store = VectorStore()
        >>> # 存储向量
        >>> await vector_store.add_vectors(session, doc_id, chunks, embeddings)
        >>> # 检索相似内容
        >>> results = await vector_store.search(session, query_embedding, top_k=5)
    """

    def __init__(self) -> None:
        """初始化向量存储。"""
        self.settings = get_settings()

    async def add_vectors(
        self,
        session: AsyncSession,
        doc_id: int,
        chunks: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> list[KnowledgeChunk]:
        """添加向量到存储。

        Args:
            session: 数据库会话。
            doc_id: 文档 ID。
            chunks: 分块内容列表，每个包含 content, metadata。
            embeddings: 向量嵌入列表。

        Returns:
            创建的分块记录列表。
        """
        created_chunks = []

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            db_chunk = KnowledgeChunk(
                doc_id=doc_id,
                chunk_index=i,
                content=chunk["content"],
                embedding=embedding,
                metadata=chunk.get("metadata", {}),
            )
            session.add(db_chunk)
            created_chunks.append(db_chunk)

        await session.flush()
        logger.info(f"Added {len(created_chunks)} vectors for doc_id={doc_id}")
        return created_chunks

    async def search(
        self,
        session: AsyncSession,
        query_embedding: list[float],
        top_k: int | None = None,
        doc_type: str | None = None,
        category: str | None = None,
        similarity_threshold: float | None = None,
    ) -> list[SearchResult]:
        """向量相似度检索。

        Args:
            session: 数据库会话。
            query_embedding: 查询向量。
            top_k: 返回结果数量，默认使用配置值。
            doc_type: 文档类型过滤。
            category: 商品类目过滤。
            similarity_threshold: 相似度阈值，默认使用配置值。

        Returns:
            检索结果列表，按相似度降序排列。
        """
        top_k = top_k or self.settings.retrieval_top_k
        similarity_threshold = similarity_threshold or self.settings.similarity_threshold

        # 构建向量检索 SQL
        # 使用 pgvector 的余弦相似度
        query = text("""
            SELECT
                kc.id as chunk_id,
                kc.doc_id,
                kc.content,
                kc.metadata,
                kd.title as doc_title,
                kd.doc_type,
                1 - (kc.embedding <=> :embedding::vector) as similarity
            FROM knowledge_chunks kc
            JOIN knowledge_docs kd ON kc.doc_id = kd.id
            WHERE 1 - (kc.embedding <=> :embedding::vector) >= :threshold
                AND (:doc_type IS NULL OR kd.doc_type = :doc_type)
                AND (:category IS NULL OR kd.category = :category)
            ORDER BY kc.embedding <=> :embedding::vector
            LIMIT :top_k
        """)

        result = await session.execute(
            query,
            {
                "embedding": str(query_embedding),
                "threshold": similarity_threshold,
                "doc_type": doc_type,
                "category": category,
                "top_k": top_k,
            }
        )

        rows = result.fetchall()
        results = [
            SearchResult(
                chunk_id=row.chunk_id,
                doc_id=row.doc_id,
                content=row.content,
                similarity=float(row.similarity),
                metadata=row.metadata or {},
                doc_title=row.doc_title,
                doc_type=row.doc_type,
            )
            for row in rows
        ]

        logger.info(
            f"Vector search returned {len(results)} results "
            f"(doc_type={doc_type}, category={category})"
        )
        return results

    async def delete_by_doc_id(self, session: AsyncSession, doc_id: int) -> int:
        """删除指定文档的所有向量。

        Args:
            session: 数据库会话。
            doc_id: 文档 ID。

        Returns:
            删除的分块数量。
        """
        result = await session.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc_id)
        )
        chunks = result.scalars().all()
        count = len(chunks)

        for chunk in chunks:
            await session.delete(chunk)

        await session.flush()
        logger.info(f"Deleted {count} vectors for doc_id={doc_id}")
        return count

    async def get_stats(self, session: AsyncSession) -> dict[str, Any]:
        """获取向量存储统计信息。

        Args:
            session: 数据库会话。

        Returns:
            统计信息字典。
        """
        # 文档统计
        docs_result = await session.execute(
            text("""
                SELECT doc_type, COUNT(*) as count
                FROM knowledge_docs
                GROUP BY doc_type
            """)
        )
        docs_by_type = {row.doc_type: row.count for row in docs_result.fetchall()}

        # 分块统计
        chunks_result = await session.execute(
            text("SELECT COUNT(*) as total FROM knowledge_chunks")
        )
        total_chunks = chunks_result.scalar() or 0

        # 文档总数
        total_docs_result = await session.execute(
            text("SELECT COUNT(*) as total FROM knowledge_docs")
        )
        total_docs = total_docs_result.scalar() or 0

        return {
            "total_documents": total_docs,
            "total_chunks": total_chunks,
            "documents_by_type": docs_by_type,
        }
