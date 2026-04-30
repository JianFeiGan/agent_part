"""
RAG 使用日志服务模块。

Description:
    记录和分析 RAG 检索操作的使用日志。
    主要功能：
    - 记录每次 RAG 检索的详细信息
    - 统计 RAG 使用情况
    - 分析检索效果
@author ganjianfei
@version 1.0.0
2026-04-05
"""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import RAGUsageLog


class RAGLogger:
    """RAG 使用日志记录器。

    记录 RAG 检索操作的详细信息，用于效果分析和审计。

    Example:
        >>> logger = RAGLogger()
        >>> await logger.log_retrieval(
        ...     session=db_session,
        ...     task_id="task_123",
        ...     agent_name="RequirementAnalyzer",
        ...     query="品牌调性 视觉规范",
        ...     chunk_ids=[1, 2, 3],
        ...     scores=[0.85, 0.82, 0.78],
        ... )
    """

    async def log_retrieval(
        self,
        session: AsyncSession,
        task_id: str | None = None,
        agent_name: str | None = None,
        query: str | None = None,
        chunk_ids: list[int] | None = None,
        scores: list[float] | None = None,
        output: str | None = None,
    ) -> RAGUsageLog:
        """记录 RAG 检索操作。

        Args:
            session: 数据库会话。
            task_id: 任务 ID。
            agent_name: Agent 名称。
            query: 检索查询。
            chunk_ids: 检索到的分块 ID 列表。
            scores: 相似度分数列表。
            output: 生成的输出（可选）。

        Returns:
            创建的日志记录。
        """
        log = RAGUsageLog(
            task_id=task_id,
            agent_name=agent_name,
            query=query,
            retrieved_chunk_ids=chunk_ids,
            similarity_scores=scores,
            generated_output=output,
            created_at=datetime.utcnow(),
        )
        session.add(log)
        await session.flush()
        return log

    async def get_logs_by_task(
        self,
        session: AsyncSession,
        task_id: str,
    ) -> list[RAGUsageLog]:
        """获取任务的所有 RAG 日志。

        Args:
            session: 数据库会话。
            task_id: 任务 ID。

        Returns:
            日志列表。
        """
        result = await session.execute(
            select(RAGUsageLog)
            .where(RAGUsageLog.task_id == task_id)
            .order_by(RAGUsageLog.created_at)
        )
        return list(result.scalars().all())

    async def get_logs_by_agent(
        self,
        session: AsyncSession,
        agent_name: str,
        limit: int = 100,
    ) -> list[RAGUsageLog]:
        """获取 Agent 的 RAG 日志。

        Args:
            session: 数据库会话。
            agent_name: Agent 名称。
            limit: 返回数量限制。

        Returns:
            日志列表。
        """
        result = await session.execute(
            select(RAGUsageLog)
            .where(RAGUsageLog.agent_name == agent_name)
            .order_by(RAGUsageLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_usage_stats(
        self,
        session: AsyncSession,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """获取 RAG 使用统计。

        Args:
            session: 数据库会话。
            start_date: 开始日期。
            end_date: 结束日期。

        Returns:
            统计数据。
        """
        # 构建基础查询
        base_query = select(RAGUsageLog)

        if start_date:
            base_query = base_query.where(RAGUsageLog.created_at >= start_date)
        if end_date:
            base_query = base_query.where(RAGUsageLog.created_at <= end_date)

        # 总检索次数
        total_result = await session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total_retrievals = total_result.scalar() or 0

        # 按 Agent 统计
        agent_stats_result = await session.execute(
            select(
                RAGUsageLog.agent_name,
                func.count().label("count"),
            )
            .group_by(RAGUsageLog.agent_name)
            .order_by(func.count().desc())
        )
        agent_stats = [{"agent": row.agent_name, "count": row.count} for row in agent_stats_result]

        # 平均相似度
        avg_score_result = await session.execute(select(func.avg(RAGUsageLog.similarity_scores[1])))
        avg_score = avg_score_result.scalar()

        return {
            "total_retrievals": total_retrievals,
            "by_agent": agent_stats,
            "avg_similarity": float(avg_score) if avg_score else 0.0,
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
        }

    async def get_chunk_hit_rate(
        self,
        session: AsyncSession,
        doc_id: int | None = None,
    ) -> dict[str, Any]:
        """获取分块命中率统计。

        Args:
            session: 数据库会话。
            doc_id: 文档 ID（可选，不指定则统计所有）。

        Returns:
            命中率统计。
        """
        # 获取所有检索日志
        result = await session.execute(select(RAGUsageLog.retrieved_chunk_ids))
        all_chunk_ids = []
        for row in result:
            if row[0]:
                all_chunk_ids.extend(row[0])

        if not all_chunk_ids:
            return {
                "total_retrievals": 0,
                "unique_chunks_hit": 0,
                "top_chunks": [],
            }

        # 统计每个 chunk 的命中次数
        chunk_hit_count: dict[int, int] = {}
        for chunk_id in all_chunk_ids:
            chunk_hit_count[chunk_id] = chunk_hit_count.get(chunk_id, 0) + 1

        # 排序获取热门 chunk
        sorted_chunks = sorted(
            chunk_hit_count.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        return {
            "total_retrievals": len(all_chunk_ids),
            "unique_chunks_hit": len(chunk_hit_count),
            "top_chunks": [
                {"chunk_id": chunk_id, "hits": count} for chunk_id, count in sorted_chunks[:10]
            ],
        }


# 全局实例
_rag_logger: RAGLogger | None = None


def get_rag_logger() -> RAGLogger:
    """获取 RAG 日志记录器实例。

    Returns:
        RAGLogger 实例。
    """
    global _rag_logger
    if _rag_logger is None:
        _rag_logger = RAGLogger()
    return _rag_logger
