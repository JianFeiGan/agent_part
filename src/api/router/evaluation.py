"""
RAG 效果评估 API 路由。

Description:
    提供 RAG 检索效果评估和对比分析接口。
@author ganjianfei
@version 1.0.0
2026-04-05
"""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schema.common import ApiResponse
from src.db import get_db
from src.db.models import RAGUsageLog
from src.rag.logger import get_rag_logger

router = APIRouter()


# ==================== 请求/响应模型 ====================


class HitRateResponse(BaseModel):
    """命中率响应。"""

    period: str
    total_retrievals: int
    unique_chunks_hit: int
    unique_docs_hit: int
    avg_results_per_query: float
    top_hit_chunks: list[dict[str, Any]]


class ComparisonRequest(BaseModel):
    """对比评估请求。"""

    task_id: str | None = Field(default=None, description="任务ID（可选）")
    start_date: str | None = Field(default=None, description="开始日期")
    end_date: str | None = Field(default=None, description="结束日期")


class ComparisonResponse(BaseModel):
    """对比评估响应。"""

    period: str
    rag_stats: dict[str, Any]
    non_rag_stats: dict[str, Any]
    improvement: dict[str, float]


class EvaluationReportResponse(BaseModel):
    """评估报告响应。"""

    generated_at: str
    period: str
    summary: dict[str, Any]
    retrieval_metrics: dict[str, Any]
    quality_metrics: dict[str, Any]
    recommendations: list[str]


# ==================== API 端点 ====================


@router.get("/hit-rate", response_model=ApiResponse[HitRateResponse])
async def get_hit_rate(
    days: int = Query(default=7, ge=1, le=90, description="统计天数"),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[HitRateResponse]:
    """获取 RAG 命中率统计。

    Args:
        days: 统计天数。
        session: 数据库会话。

    Returns:
        命中率统计数据。
    """
    logger = get_rag_logger()

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # 获取使用统计
    stats = await logger.get_usage_stats(session, start_date, end_date)

    # 获取分块命中率
    chunk_stats = await logger.get_chunk_hit_rate(session)

    # 获取唯一文档数
    result = await session.execute(
        select(func.count(func.distinct(RAGUsageLog.task_id)))
        .where(RAGUsageLog.created_at >= start_date)
    )
    unique_tasks = result.scalar() or 0

    # 计算平均每次查询结果数
    avg_results = 0.0
    if stats["total_retrievals"] > 0 and unique_tasks > 0:
        # 假设每次检索返回约 top_k 个结果
        avg_results = chunk_stats.get("total_retrievals", 0) / max(unique_tasks, 1)

    return ApiResponse.success(
        HitRateResponse(
            period=f"{start_date.date()} ~ {end_date.date()}",
            total_retrievals=stats["total_retrievals"],
            unique_chunks_hit=chunk_stats["unique_chunks_hit"],
            unique_docs_hit=len(set(c["chunk_id"] // 100 for c in chunk_stats.get("top_chunks", []))),
            avg_results_per_query=round(avg_results, 2),
            top_hit_chunks=chunk_stats.get("top_chunks", []),
        )
    )


@router.post("/compare", response_model=ApiResponse[ComparisonResponse])
async def compare_rag_vs_non_rag(
    request: ComparisonRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[ComparisonResponse]:
    """对比 RAG 与非 RAG 的生成质量。

    Args:
        request: 对比请求。
        session: 数据库会话。

    Returns:
        对比分析结果。
    """
    from src.db.models import GenerationTask

    # 解析日期
    if request.start_date:
        start_date = datetime.fromisoformat(request.start_date)
    else:
        start_date = datetime.utcnow() - timedelta(days=30)

    if request.end_date:
        end_date = datetime.fromisoformat(request.end_date)
    else:
        end_date = datetime.utcnow()

    # 统计启用 RAG 的任务
    rag_result = await session.execute(
        select(
            func.count().label("count"),
            func.avg(GenerationTask.quality_score).label("avg_score"),
        )
        .where(
            GenerationTask.created_at >= start_date,
            GenerationTask.created_at <= end_date,
            GenerationTask.rag_enabled == True,
            GenerationTask.status == "completed",
        )
    )
    rag_row = rag_result.first()

    # 统计未启用 RAG 的任务
    non_rag_result = await session.execute(
        select(
            func.count().label("count"),
            func.avg(GenerationTask.quality_score).label("avg_score"),
        )
        .where(
            GenerationTask.created_at >= start_date,
            GenerationTask.created_at <= end_date,
            GenerationTask.rag_enabled == False,
            GenerationTask.status == "completed",
        )
    )
    non_rag_row = non_rag_result.first()

    rag_stats = {
        "task_count": rag_row.count if rag_row else 0,
        "avg_quality_score": float(rag_row.avg_score) if rag_row and rag_row.avg_score else 0.0,
    }

    non_rag_stats = {
        "task_count": non_rag_row.count if non_rag_row else 0,
        "avg_quality_score": float(non_rag_row.avg_score) if non_rag_row and non_rag_row.avg_score else 0.0,
    }

    # 计算改进百分比
    improvement = {}
    if non_rag_stats["avg_quality_score"] > 0:
        improvement["quality_score"] = round(
            (rag_stats["avg_quality_score"] - non_rag_stats["avg_quality_score"])
            / non_rag_stats["avg_quality_score"]
            * 100,
            2,
        )
    else:
        improvement["quality_score"] = 0.0

    return ApiResponse.success(
        ComparisonResponse(
            period=f"{start_date.date()} ~ {end_date.date()}",
            rag_stats=rag_stats,
            non_rag_stats=non_rag_stats,
            improvement=improvement,
        )
    )


@router.get("/report", response_model=ApiResponse[EvaluationReportResponse])
async def get_evaluation_report(
    days: int = Query(default=30, ge=1, le=90, description="统计天数"),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[EvaluationReportResponse]:
    """生成 RAG 效果评估报告。

    Args:
        days: 统计天数。
        session: 数据库会话。

    Returns:
        评估报告。
    """
    logger = get_rag_logger()

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # 获取各类统计数据
    usage_stats = await logger.get_usage_stats(session, start_date, end_date)
    chunk_stats = await logger.get_chunk_hit_rate(session)

    # 获取按 Agent 分类的统计
    agent_stats = usage_stats.get("by_agent", [])

    # 生成建议
    recommendations = []

    avg_similarity = usage_stats.get("avg_similarity", 0)
    if avg_similarity < 0.5:
        recommendations.append("平均相似度较低，建议优化文档分块策略或调整检索阈值")

    if usage_stats["total_retrievals"] == 0:
        recommendations.append("暂无 RAG 使用记录，建议增加知识库内容并推广使用")

    if chunk_stats["unique_chunks_hit"] < 10:
        recommendations.append("命中分块数量较少，建议扩充知识库内容覆盖更多场景")

    if not recommendations:
        recommendations.append("RAG 系统运行良好，建议持续监控并定期更新知识库内容")

    return ApiResponse.success(
        EvaluationReportResponse(
            generated_at=datetime.utcnow().isoformat(),
            period=f"{start_date.date()} ~ {end_date.date()}",
            summary={
                "total_retrievals": usage_stats["total_retrievals"],
                "unique_chunks_hit": chunk_stats["unique_chunks_hit"],
                "avg_similarity": round(avg_similarity, 4) if avg_similarity else 0,
            },
            retrieval_metrics={
                "by_agent": agent_stats,
                "top_chunks": chunk_stats.get("top_chunks", [])[:5],
            },
            quality_metrics={
                "hit_rate": round(
                    chunk_stats["unique_chunks_hit"] / max(usage_stats["total_retrievals"], 1) * 100,
                    2,
                ),
            },
            recommendations=recommendations,
        )
    )


@router.get("/optimize-suggestions", response_model=ApiResponse[list[str]])
async def get_optimize_suggestions(
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[list[str]]:
    """获取检索参数优化建议。

    Args:
        session: 数据库会话。

    Returns:
        优化建议列表。
    """
    logger = get_rag_logger()

    # 获取最近 7 天的统计
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)

    usage_stats = await logger.get_usage_stats(session, start_date, end_date)
    chunk_stats = await logger.get_chunk_hit_rate(session)

    suggestions = []

    avg_similarity = usage_stats.get("avg_similarity", 0)

    # 相似度阈值建议
    if avg_similarity > 0.8:
        suggestions.append("当前平均相似度较高，可考虑降低相似度阈值以获取更多结果")
    elif avg_similarity < 0.5:
        suggestions.append("当前平均相似度较低，建议提高相似度阈值以过滤不相关结果")
    else:
        suggestions.append("当前相似度阈值设置合理，无需调整")

    # Top-k 建议
    total = chunk_stats.get("total_retrievals", 0)
    unique = chunk_stats.get("unique_chunks_hit", 0)
    if total > 0:
        avg_per_query = total / max(usage_stats["total_retrievals"], 1)
        if avg_per_query < 3:
            suggestions.append("平均返回结果较少，建议增加 top-k 参数值")
        elif avg_per_query > 10:
            suggestions.append("平均返回结果较多，可考虑减少 top-k 参数以聚焦核心内容")

    # 知识库覆盖建议
    if unique < 20:
        suggestions.append("知识库覆盖范围有限，建议补充更多文档内容")

    if not suggestions:
        suggestions.append("当前检索参数配置良好")

    return ApiResponse.success(suggestions)
