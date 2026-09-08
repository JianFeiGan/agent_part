"""
记忆提炼与人工审核 API 路由。

Description:
    提供记忆提炼触发、提案列表/详情、审批通过/拒绝接口。
    前缀: /api/v1/memory-proposals

    流程:
    1. POST /distill - 手动触发提炼，生成 pending proposal
    2. GET /proposals - 列表（按租户、状态、类目过滤）
    3. GET /proposals/{id} - 详情
    4. POST /proposals/{id}/approve - 审批通过 → 写入 CategoryMemory
    5. POST /proposals/{id}/reject - 审批拒绝

    提案的租户过滤/scope/404 语义由 TenantCRUD 门面承载（STRICT，
    提案无共享行概念）；approve 的跨资源编排留在调用方。
@author ganjianfei
@version 1.1.0
2026-09-08
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from src.api.crud import ResourceSpec, Scopes, TenantCRUD, require_scope
from src.api.deps import AuthDep, SessionDep
from src.api.schema.common import ApiResponse
from src.api.schema.memory_proposals import (
    ApproveRequest,
    DistillRequest,
    MemoryProposalResponse,
    RejectRequest,
)
from src.db.models import CategoryMemory, CategoryMemoryProposalPO
from src.rag.memory_distiller import MemoryDistiller

router = APIRouter()

_proposal_crud: TenantCRUD[CategoryMemoryProposalPO] = TenantCRUD(
    ResourceSpec(
        model=CategoryMemoryProposalPO,
        label="提案",
        scopes=Scopes.rw("memory:read", "memory:write"),
        default_order=(CategoryMemoryProposalPO.created_at.desc(),),
        not_found_detail="提案不存在",
    )
)

# approve 落库目标：严格本租户的 CategoryMemory（无共享行语义）
_memory_crud: TenantCRUD[CategoryMemory] = TenantCRUD(
    ResourceSpec(
        model=CategoryMemory,
        label="类目记忆",
        scopes=Scopes.rw("memory:read", "memory:write"),
        not_found_detail="类目记忆不存在",
    )
)


def _get_distiller() -> MemoryDistiller:
    """获取 MemoryDistiller 实例（无状态，可直接构造）。"""
    return MemoryDistiller()


# ============================================================================
# Distill
# ============================================================================


@router.post(
    "/distill",
    response_model=ApiResponse[MemoryProposalResponse],
    status_code=status.HTTP_201_CREATED,
    summary="手动触发记忆提炼",
)
async def distill(
    request: DistillRequest,
    auth: AuthDep,
    session: SessionDep,
) -> ApiResponse[MemoryProposalResponse]:
    """手动触发记忆提炼，生成 pending 状态的提案。

    根据 source_type 调用对应的提炼方法。

    Args:
        request: 提炼请求。
        auth: 认证上下文。
        session: 数据库会话。

    Returns:
        创建的提案。

    Raises:
        HTTPException: 403 scope 不足、400 无可提炼内容。
    """
    require_scope(auth, "memory:write")

    distiller = _get_distiller()

    proposal: CategoryMemoryProposalPO | None = None

    if request.source_type == "task_completion":
        gen_result = request.generation_result or {}
        category = request.category or gen_result.get("category", "unknown")
        proposal = await distiller.distill_from_task(
            session=session,
            tenant_id=auth.tenant_id,
            task_id=request.source_ref or "manual",
            generation_result=gen_result,
            category=category,
        )
    elif request.source_type == "compliance_failure":
        compliance_data = request.compliance_data or {}
        proposal = await distiller.distill_from_compliance(
            session=session,
            tenant_id=auth.tenant_id,
            compliance_report=compliance_data,
        )
    elif request.source_type == "platform_push":
        push_result = request.push_result or {}
        proposal = await distiller.distill_from_push_result(
            session=session,
            tenant_id=auth.tenant_id,
            push_result=push_result,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的 source_type: {request.source_type}",
        )

    if proposal is None:
        raise HTTPException(
            status_code=400,
            detail="无可提炼内容，未生成提案",
        )

    await session.commit()
    await session.refresh(proposal)

    return ApiResponse.success(MemoryProposalResponse.model_validate(proposal), message="提炼成功")


# ============================================================================
# List / Get Proposals
# ============================================================================


@router.get(
    "/proposals",
    response_model=ApiResponse[list[MemoryProposalResponse]],
    summary="获取提案列表",
)
async def list_proposals(
    auth: AuthDep,
    session: SessionDep,
    status_filter: str | None = Query(default=None, alias="status", description="按状态过滤"),
    category: str | None = Query(default=None, description="按类目过滤"),
    limit: int = 20,
) -> ApiResponse[list[MemoryProposalResponse]]:
    """获取当前租户的提案列表。

    支持按状态和类目过滤。

    Args:
        auth: 认证上下文。
        session: 数据库会话。
        status_filter: 按状态过滤。
        category: 按类目过滤。
        limit: 返回数量上限。

    Returns:
        提案列表。
    """
    proposals = await _proposal_crud.list(
        session,
        auth,
        limit=limit,
        status=status_filter or None,
        category=category or None,
    )
    return ApiResponse.success(
        [MemoryProposalResponse.model_validate(p) for p in proposals], message="获取成功"
    )


@router.get(
    "/proposals/{proposal_id}",
    response_model=ApiResponse[MemoryProposalResponse],
    summary="获取提案详情",
)
async def get_proposal(
    proposal_id: int,
    auth: AuthDep,
    session: SessionDep,
) -> ApiResponse[MemoryProposalResponse]:
    """获取提案详情。

    跨租户访问返回 404。

    Args:
        proposal_id: 提案 ID。
        auth: 认证上下文。
        session: 数据库会话。

    Returns:
        提案详情。
    """
    proposal = await _proposal_crud.get(session, auth, proposal_id)
    return ApiResponse.success(MemoryProposalResponse.model_validate(proposal), message="获取成功")


# ============================================================================
# Approve
# ============================================================================


@router.post(
    "/proposals/{proposal_id}/approve",
    response_model=ApiResponse[MemoryProposalResponse],
    summary="审批通过并写入 CategoryMemory",
)
async def approve_proposal(
    proposal_id: int,
    request: ApproveRequest | None = None,
    auth: AuthDep = None,  # type: ignore[assignment]
    session: SessionDep = None,  # type: ignore[assignment]
) -> ApiResponse[MemoryProposalResponse]:
    """审批通过提案，合并写入 CategoryMemory。

    流程：
    1. 获取 proposal。
    2. 查询 CategoryMemory(tenant_id, category)。
    3. 如果存在：merge（集合并集去重，dict 合并，proposal 优先）。
    4. 如果不存在：创建。
    5. proposal.status = "applied", reviewed_by = auth.user_id。

    Args:
        proposal_id: 提案 ID。
        request: 可选的字段覆盖。
        auth: 认证上下文。
        session: 数据库会话。

    Returns:
        更新后的提案。

    Raises:
        HTTPException: 403 scope 不足、404 不存在或跨租户、409 状态不允许。
    """
    require_scope(auth, "memory:write")

    # 1. 获取 proposal（租户条件在 SQL 层过滤，跨租户 404 防枚举）
    proposal = await _proposal_crud.get(session, auth, proposal_id)

    if proposal.status not in ("pending",):
        raise HTTPException(
            status_code=409,
            detail=f"提案状态不允许审批: {proposal.status}",
        )

    # 2. 查询已有 CategoryMemory（严格本租户）
    existing_memory = await _memory_crud.find_by(session, auth, category=proposal.category)

    # 准备 merge 数据（approve request 可选覆盖）
    bp: list[str] = (
        request.best_practices
        if request and request.best_practices is not None
        else proposal.best_practices
    )
    np: list[str] = (
        request.negative_patterns
        if request and request.negative_patterns is not None
        else proposal.negative_patterns
    )
    sg: dict[str, Any] = (
        request.style_guidelines
        if request and request.style_guidelines is not None
        else proposal.style_guidelines
    )
    ph: dict[str, Any] = (
        request.performance_hints
        if request and request.performance_hints is not None
        else proposal.performance_hints
    )
    summary: str | None = (
        request.summary if request and request.summary is not None else proposal.summary
    )

    if existing_memory is not None:
        # 3a. Merge: 集合并集去重
        existing_memory.best_practices = list(
            dict.fromkeys(list(existing_memory.best_practices) + bp)
        )
        existing_memory.negative_patterns = list(
            dict.fromkeys(list(existing_memory.negative_patterns) + np)
        )
        # dict 合并，proposal 优先
        merged_sg: dict[str, Any] = dict(existing_memory.style_guidelines)
        merged_sg.update(sg)
        existing_memory.style_guidelines = merged_sg
        merged_ph: dict[str, Any] = dict(existing_memory.performance_hints)
        merged_ph.update(ph)
        existing_memory.performance_hints = merged_ph
        if summary:
            existing_memory.summary = summary
        existing_memory.updated_at = datetime.now(UTC)
        await _memory_crud.save(session, existing_memory)
    else:
        # 3b. 创建新 CategoryMemory
        await _memory_crud.create(
            session,
            auth,
            {
                "category": proposal.category,
                "summary": summary,
                "best_practices": bp,
                "negative_patterns": np,
                "style_guidelines": sg,
                "performance_hints": ph,
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            },
        )

    # 4. 更新 proposal 状态
    proposal.status = "applied"
    proposal.reviewed_by = auth.user_id
    proposal.reviewed_at = datetime.now(UTC)
    proposal.updated_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(proposal)

    return ApiResponse.success(
        MemoryProposalResponse.model_validate(proposal),
        message="审批通过，已写入类目记忆",
    )


# ============================================================================
# Reject
# ============================================================================


@router.post(
    "/proposals/{proposal_id}/reject",
    response_model=ApiResponse[MemoryProposalResponse],
    summary="审批拒绝",
)
async def reject_proposal(
    proposal_id: int,
    request: RejectRequest,
    auth: AuthDep,
    session: SessionDep,
) -> ApiResponse[MemoryProposalResponse]:
    """审批拒绝提案。

    必填拒绝理由。

    Args:
        proposal_id: 提案 ID。
        request: 拒绝请求（含 reason）。
        auth: 认证上下文。
        session: 数据库会话。

    Returns:
        更新后的提案。

    Raises:
        HTTPException: 403 scope 不足、404 不存在或跨租户、409 状态不允许。
    """
    require_scope(auth, "memory:write")

    proposal = await _proposal_crud.get(session, auth, proposal_id)

    if proposal.status not in ("pending",):
        raise HTTPException(
            status_code=409,
            detail=f"提案状态不允许拒绝: {proposal.status}",
        )

    proposal.status = "rejected"
    proposal.review_reason = request.reason
    proposal.reviewed_by = auth.user_id
    proposal.reviewed_at = datetime.now(UTC)
    proposal.updated_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(proposal)

    return ApiResponse.success(MemoryProposalResponse.model_validate(proposal), message="已拒绝")
