"""
AI 会话记录 API 路由。

提供会话记录查询、Token 统计、费用预算、会话内容搜索等功能。
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from src.api.deps import AuthDep
from src.api.schema.common import ApiResponse
from src.api.schema.conversation import (
    ConversationContentQuery,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationLogResponse,
    ConversationQueryParams,
    CostBudgetRequest,
    CostBudgetResponse,
    AgentUsageBreakdown,
    ModelUsageBreakdown,
    TokenUsageStats,
    UsageOverviewResponse,
)
from src.auth.api_key import require_auth
from src.auth.context import AuthContext
from src.db.conversation_models import AIConversationLog
from src.db.postgres import get_db, get_db_session
from src.db.repository import BaseRepository

logger = logging.getLogger(__name__)

router = APIRouter()

# USD/CNY 汇率（近似值）
USD_CNY_RATE = 7.2


def _log_to_response(log: AIConversationLog) -> ConversationLogResponse:
    """将 ORM 对象转换为列表响应。"""
    return ConversationLogResponse(
        id=log.id,
        task_id=log.task_id,
        session_id=log.session_id,
        agent_name=log.agent_name,
        model_name=log.model_name,
        provider=log.provider,
        input_tokens=log.input_tokens,
        output_tokens=log.output_tokens,
        total_tokens=log.total_tokens,
        cost_usd=round(log.cost_usd, 6),
        cost_cny=round(log.cost_cny, 4),
        latency_ms=log.latency_ms,
        status=log.status,
        created_at=log.created_at,
    )


def _log_to_detail(log: AIConversationLog) -> ConversationDetailResponse:
    """将 ORM 对象转换为详情响应。"""
    return ConversationDetailResponse(
        id=log.id,
        task_id=log.task_id,
        session_id=log.session_id,
        agent_name=log.agent_name,
        model_name=log.model_name,
        provider=log.provider,
        input_content=log.input_content,
        output_content=log.output_content,
        input_tokens=log.input_tokens,
        output_tokens=log.output_tokens,
        total_tokens=log.total_tokens,
        cost_usd=round(log.cost_usd, 6),
        cost_cny=round(log.cost_cny, 4),
        latency_ms=log.latency_ms,
        status=log.status,
        error_message=log.error_message,
        extra_data=log.extra_data,
        created_at=log.created_at,
    )


@router.get(
    "/conversations",
    response_model=ApiResponse[ConversationListResponse],
    summary="查询会话记录",
)
async def list_conversations(
    params: ConversationQueryParams = Depends(),
    auth: AuthContext = Depends(require_auth),
) -> ApiResponse[ConversationListResponse]:
    """查询 AI 会话记录列表。

    支持按 Agent、模型、任务、状态、时间范围过滤。
    """
    async with get_db_session() as session:
        # 构建查询
        stmt = select(AIConversationLog).where(
            AIConversationLog.tenant_id == auth.tenant_id
        )
        count_stmt = select(func.count(AIConversationLog.id)).where(
            AIConversationLog.tenant_id == auth.tenant_id
        )

        if params.agent_name:
            stmt = stmt.where(AIConversationLog.agent_name == params.agent_name)
            count_stmt = count_stmt.where(AIConversationLog.agent_name == params.agent_name)
        if params.model_name:
            stmt = stmt.where(AIConversationLog.model_name == params.model_name)
            count_stmt = count_stmt.where(AIConversationLog.model_name == params.model_name)
        if params.provider:
            stmt = stmt.where(AIConversationLog.provider == params.provider)
            count_stmt = count_stmt.where(AIConversationLog.provider == params.provider)
        if params.task_id:
            stmt = stmt.where(AIConversationLog.task_id == params.task_id)
            count_stmt = count_stmt.where(AIConversationLog.task_id == params.task_id)
        if params.session_id:
            stmt = stmt.where(AIConversationLog.session_id == params.session_id)
            count_stmt = count_stmt.where(AIConversationLog.session_id == params.session_id)
        if params.status:
            stmt = stmt.where(AIConversationLog.status == params.status)
            count_stmt = count_stmt.where(AIConversationLog.status == params.status)
        if params.start_date:
            stmt = stmt.where(AIConversationLog.created_at >= params.start_date)
            count_stmt = count_stmt.where(AIConversationLog.created_at >= params.start_date)
        if params.end_date:
            stmt = stmt.where(AIConversationLog.created_at <= params.end_date)
            count_stmt = count_stmt.where(AIConversationLog.created_at <= params.end_date)

        # 总数
        total_result = await session.execute(count_stmt)
        total = total_result.scalar() or 0

        # 分页
        offset = (params.page - 1) * params.page_size
        stmt = stmt.order_by(AIConversationLog.created_at.desc())
        stmt = stmt.offset(offset).limit(params.page_size)

        result = await session.execute(stmt)
        logs = result.scalars().all()

    return ApiResponse(
        code=200,
        message="成功",
        data=ConversationListResponse(
            items=[_log_to_response(log) for log in logs],
            total=total,
            page=params.page,
            page_size=params.page_size,
        ),
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ApiResponse[ConversationDetailResponse],
    summary="获取会话详情",
)
async def get_conversation(
    conversation_id: int,
    auth: AuthContext = Depends(require_auth),
) -> ApiResponse[ConversationDetailResponse]:
    """获取单条 AI 会话记录详情（含输入输出内容）。"""
    async with get_db_session() as session:
        repo = BaseRepository(AIConversationLog, session)
        log = await repo.get(conversation_id)

    if not log or log.tenant_id != auth.tenant_id:
        return ApiResponse(code=404, message="会话记录不存在", data=None)

    return ApiResponse(code=200, message="成功", data=_log_to_detail(log))


@router.get(
    "/usage/overview",
    response_model=ApiResponse[UsageOverviewResponse],
    summary="使用量概览",
)
async def get_usage_overview(
    start_date: datetime | None = Query(default=None, description="开始时间"),
    end_date: datetime | None = Query(default=None, description="结束时间"),
    auth: AuthContext = Depends(require_auth),
) -> ApiResponse[UsageOverviewResponse]:
    """获取 Token 使用量和费用概览。

    返回总体统计、按模型分解、按 Agent 分解。
    """
    async with get_db_session() as session:
        base_filter = AIConversationLog.tenant_id == auth.tenant_id
        if start_date:
            base_filter &= AIConversationLog.created_at >= start_date
        if end_date:
            base_filter &= AIConversationLog.created_at <= end_date

        # 总体统计
        stats_stmt = select(
            func.coalesce(func.sum(AIConversationLog.input_tokens), 0),
            func.coalesce(func.sum(AIConversationLog.output_tokens), 0),
            func.coalesce(func.sum(AIConversationLog.total_tokens), 0),
            func.coalesce(func.sum(AIConversationLog.cost_usd), 0.0),
            func.coalesce(func.sum(AIConversationLog.cost_cny), 0.0),
            func.coalesce(func.avg(AIConversationLog.latency_ms), 0.0),
            func.count(AIConversationLog.id),
        ).where(base_filter & (AIConversationLog.status == "success"))

        stats_row = (await session.execute(stats_stmt)).one()
        success_count = stats_row[6]

        failed_stmt = select(func.count(AIConversationLog.id)).where(
            base_filter & (AIConversationLog.status != "success")
        )
        failed_count = (await session.execute(failed_stmt)).scalar() or 0

        stats = TokenUsageStats(
            total_input_tokens=stats_row[0],
            total_output_tokens=stats_row[1],
            total_tokens=stats_row[2],
            total_cost_usd=round(stats_row[3], 6),
            total_cost_cny=round(stats_row[4], 4),
            avg_latency_ms=round(float(stats_row[5] or 0), 1),
            success_count=success_count,
            failed_count=failed_count,
            total_count=success_count + failed_count,
        )

        # 按模型分解
        model_stmt = (
            select(
                AIConversationLog.model_name,
                AIConversationLog.provider,
                func.count(AIConversationLog.id),
                func.coalesce(func.sum(AIConversationLog.total_tokens), 0),
                func.coalesce(func.sum(AIConversationLog.cost_usd), 0.0),
                func.coalesce(func.sum(AIConversationLog.cost_cny), 0.0),
            )
            .where(base_filter)
            .group_by(AIConversationLog.model_name, AIConversationLog.provider)
            .order_by(func.sum(AIConversationLog.total_tokens).desc())
        )
        model_rows = (await session.execute(model_stmt)).all()
        by_model = [
            ModelUsageBreakdown(
                model_name=row[0],
                provider=row[1],
                call_count=row[2],
                total_tokens=row[3],
                total_cost_usd=round(row[4], 6),
                total_cost_cny=round(row[5], 4),
            )
            for row in model_rows
        ]

        # 按 Agent 分解
        agent_stmt = (
            select(
                AIConversationLog.agent_name,
                func.count(AIConversationLog.id),
                func.coalesce(func.sum(AIConversationLog.total_tokens), 0),
                func.coalesce(func.sum(AIConversationLog.cost_usd), 0.0),
                func.coalesce(func.sum(AIConversationLog.cost_cny), 0.0),
            )
            .where(base_filter)
            .group_by(AIConversationLog.agent_name)
            .order_by(func.sum(AIConversationLog.total_tokens).desc())
        )
        agent_rows = (await session.execute(agent_stmt)).all()
        by_agent = [
            AgentUsageBreakdown(
                agent_name=row[0] or "unknown",
                call_count=row[1],
                total_tokens=row[2],
                total_cost_usd=round(row[3], 6),
                total_cost_cny=round(row[4], 4),
            )
            for row in agent_rows
        ]

    return ApiResponse(
        code=200,
        message="成功",
        data=UsageOverviewResponse(stats=stats, by_model=by_model, by_agent=by_agent),
    )


@router.post(
    "/usage/budget",
    response_model=ApiResponse[CostBudgetResponse],
    summary="费用预算分析",
)
async def get_cost_budget(
    request: CostBudgetRequest,
    auth: AuthContext = Depends(require_auth),
) -> ApiResponse[CostBudgetResponse]:
    """分析当前费用使用情况与预算对比。

    计算今日和本月的费用使用量，与预算对比，并预估月费用。
    """
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    async with get_db_session() as session:
        tenant_filter = AIConversationLog.tenant_id == auth.tenant_id

        # 今日统计
        today_stmt = select(
            func.coalesce(func.sum(AIConversationLog.cost_cny), 0.0),
            func.coalesce(func.sum(AIConversationLog.cost_usd), 0.0),
            func.coalesce(func.sum(AIConversationLog.total_tokens), 0),
            func.count(AIConversationLog.id),
        ).where(
            tenant_filter & (AIConversationLog.created_at >= today_start)
        )
        today_row = (await session.execute(today_stmt)).one()

        # 本月统计
        month_stmt = select(
            func.coalesce(func.sum(AIConversationLog.cost_cny), 0.0),
        ).where(
            tenant_filter & (AIConversationLog.created_at >= month_start)
        )
        month_cost_cny = (await session.execute(month_stmt)).scalar() or 0.0

    today_cost_cny = float(today_row[0])
    today_cost_usd = float(today_row[1])
    today_tokens = int(today_row[2])
    today_calls = int(today_row[3])

    daily_remaining = max(0.0, request.daily_budget_cny - today_cost_cny)
    daily_pct = min(100.0, (today_cost_cny / request.daily_budget_cny * 100)) if request.daily_budget_cny > 0 else 0.0

    monthly_remaining = max(0.0, request.monthly_budget_cny - float(month_cost_cny))
    monthly_pct = min(100.0, (float(month_cost_cny) / request.monthly_budget_cny * 100)) if request.monthly_budget_cny > 0 else 0.0

    # 预估月费用：基于今日日均 × 当月天数
    day_of_month = now.day
    days_in_month = (now.replace(month=now.month % 12 + 1, day=1) - timedelta(days=1)).day if now.month < 12 else 31
    projected_month = today_cost_cny * days_in_month / max(day_of_month, 1)

    return ApiResponse(
        code=200,
        message="成功",
        data=CostBudgetResponse(
            today_cost_cny=round(today_cost_cny, 4),
            today_cost_usd=round(today_cost_usd, 6),
            today_token_count=today_tokens,
            today_call_count=today_calls,
            daily_budget_cny=request.daily_budget_cny,
            daily_remaining_cny=round(daily_remaining, 4),
            daily_usage_percent=round(daily_pct, 1),
            month_cost_cny=round(float(month_cost_cny), 4),
            monthly_budget_cny=request.monthly_budget_cny,
            monthly_remaining_cny=round(monthly_remaining, 4),
            monthly_usage_percent=round(monthly_pct, 1),
            projected_month_cost_cny=round(projected_month, 4),
        ),
    )


@router.post(
    "/conversations/search",
    response_model=ApiResponse[ConversationListResponse],
    summary="搜索会话内容",
)
async def search_conversations(
    request: ConversationContentQuery,
    auth: AuthContext = Depends(require_auth),
) -> ApiResponse[ConversationListResponse]:
    """按关键词搜索会话的输入/输出内容。"""
    async with get_db_session() as session:
        keyword = f"%{request.keyword}%"
        base = AIConversationLog.tenant_id == auth.tenant_id

        # 根据搜索字段构建条件
        from sqlalchemy import or_

        if request.search_field == "input":
            condition = AIConversationLog.input_content.ilike(keyword)
        elif request.search_field == "output":
            condition = AIConversationLog.output_content.ilike(keyword)
        else:
            condition = or_(
                AIConversationLog.input_content.ilike(keyword),
                AIConversationLog.output_content.ilike(keyword),
            )

        # 总数
        count_stmt = select(func.count(AIConversationLog.id)).where(base & condition)
        total = (await session.execute(count_stmt)).scalar() or 0

        # 分页查询
        offset = (request.page - 1) * request.page_size
        stmt = (
            select(AIConversationLog)
            .where(base & condition)
            .order_by(AIConversationLog.created_at.desc())
            .offset(offset)
            .limit(request.page_size)
        )
        result = await session.execute(stmt)
        logs = result.scalars().all()

    return ApiResponse(
        code=200,
        message="成功",
        data=ConversationListResponse(
            items=[_log_to_response(log) for log in logs],
            total=total,
            page=request.page,
            page_size=request.page_size,
        ),
    )
