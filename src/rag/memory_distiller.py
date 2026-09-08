"""
记忆提炼服务。

Description:
    MemoryDistiller 从任务完成、合规失败、推送结果中提炼候选记忆。
    不直接写 CategoryMemoryPO，只创建 CategoryMemoryProposalPO with status="pending"。
@author ganjianfei
@version 1.0.0
2026-06-19
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CategoryMemoryProposalPO

logger = logging.getLogger(__name__)


class MemoryDistiller:
    """记忆提炼器。

    从不同来源提炼类目记忆候选，生成 pending 状态的 Proposal。
    不直接写入 CategoryMemory，需要人工审核通过后才正式写入。

    Example:
        >>> distiller = MemoryDistiller()
        >>> proposal = await distiller.distill_from_task(
        ...     session, "tenant-a", "task-001",
        ...     generation_result={"selling_points": ["白色背景", "细节清晰"]},
        ...     category="digital"
        ... )
    """

    # ------------------------------------------------------------------
    # distill_from_task
    # ------------------------------------------------------------------

    async def distill_from_task(
        self,
        session: AsyncSession,
        tenant_id: str,
        task_id: str,
        generation_result: dict[str, Any],
        category: str,
    ) -> CategoryMemoryProposalPO | None:
        """从任务完成结果中提炼候选记忆。

        简单规则：
        - 如果 generation_result 包含 selling_points，提炼到 best_practices。
        - 如果 quality_review 有 issues，提炼到 negative_patterns。
        - confidence 取决于完成度（1.0 完整，0.5 部分）。

        Args:
            session: 数据库会话。
            tenant_id: 租户 ID。
            task_id: 任务 ID。
            generation_result: 生成结果数据。
            category: 商品类目。

        Returns:
            创建的提案对象，或 None（无可提炼内容时）。
        """
        best_practices: list[str] = []
        negative_patterns: list[str] = []
        style_guidelines: dict[str, Any] = {}
        performance_hints: dict[str, Any] = {}
        summary_parts: list[str] = []

        # 提炼 selling_points -> best_practices
        selling_points = generation_result.get("selling_points", [])
        if isinstance(selling_points, list) and len(selling_points) > 0:
            for sp in selling_points:
                if isinstance(sp, str):
                    best_practices.append(sp)
                elif isinstance(sp, dict):
                    text = sp.get("text") or sp.get("content") or sp.get("description")
                    if text:
                        best_practices.append(str(text))
            if best_practices:
                summary_parts.append(f"从任务 {task_id} 提炼了 {len(best_practices)} 条最佳实践")

        # 提炼 quality_review issues -> negative_patterns
        quality_review = generation_result.get("quality_review", {})
        if isinstance(quality_review, dict):
            issues = quality_review.get("issues", [])
            if isinstance(issues, list):
                for issue in issues:
                    if isinstance(issue, str):
                        negative_patterns.append(issue)
                    elif isinstance(issue, dict):
                        desc = issue.get("description") or issue.get("issue") or str(issue)
                        negative_patterns.append(str(desc))
            if negative_patterns:
                summary_parts.append(f"从任务 {task_id} 提炼了 {len(negative_patterns)} 条负面模式")

        # 提炼 style_guidelines / performance_hints
        if isinstance(generation_result.get("style_guidelines"), dict):
            style_guidelines = generation_result["style_guidelines"]
            summary_parts.append(f"从任务 {task_id} 提炼了风格指南")
        if isinstance(generation_result.get("performance_hints"), dict):
            performance_hints = generation_result["performance_hints"]
            summary_parts.append(f"从任务 {task_id} 提炼了性能提示")

        if not best_practices and not negative_patterns and not style_guidelines and not performance_hints:
            return None

        # 计算置信度：selling_points 和 quality_review 都有时完整，否则部分
        has_selling = bool(best_practices)
        has_quality = bool(negative_patterns)
        confidence = 1.0 if (has_selling and has_quality) else 0.5

        summary = "；".join(summary_parts) if summary_parts else None

        proposal = CategoryMemoryProposalPO(
            tenant_id=tenant_id,
            category=category,
            summary=summary,
            best_practices=best_practices,
            negative_patterns=negative_patterns,
            style_guidelines=style_guidelines,
            performance_hints=performance_hints,
            source_type="task_completion",
            source_ref=task_id,
            status="pending",
            confidence=confidence,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        session.add(proposal)
        await session.flush()
        logger.info(
            "Created memory proposal from task: tenant=%s task=%s category=%s confidence=%.1f",
            tenant_id, task_id, category, confidence,
        )
        return proposal

    # ------------------------------------------------------------------
    # distill_from_compliance
    # ------------------------------------------------------------------

    async def distill_from_compliance(
        self,
        session: AsyncSession,
        tenant_id: str,
        compliance_report: dict[str, Any],
    ) -> CategoryMemoryProposalPO | None:
        """从合规失败报告中提炼候选记忆。

        把禁词、违规规则提炼到 negative_patterns。

        Args:
            session: 数据库会话。
            tenant_id: 租户 ID。
            compliance_report: 合规报告数据。

        Returns:
            创建的提案对象，或 None。
        """
        negative_patterns: list[str] = []
        category = compliance_report.get("category", "unknown")
        report_id = compliance_report.get("report_id") or compliance_report.get("id")

        # 提炼违规项
        violations = compliance_report.get("violations", [])
        if isinstance(violations, list):
            for v in violations:
                if isinstance(v, str):
                    negative_patterns.append(v)
                elif isinstance(v, dict):
                    rule = v.get("rule") or v.get("description") or v.get("message") or str(v)
                    negative_patterns.append(str(rule))

        # 提炼禁词列表
        banned_words = compliance_report.get("banned_words", [])
        if isinstance(banned_words, list):
            for w in banned_words:
                if isinstance(w, str):
                    negative_patterns.append(f"禁用词: {w}")

        if not negative_patterns:
            return None

        summary = f"从合规报告提炼了 {len(negative_patterns)} 条负面模式/违规规则"

        proposal = CategoryMemoryProposalPO(
            tenant_id=tenant_id,
            category=category,
            summary=summary,
            negative_patterns=negative_patterns,
            source_type="compliance_failure",
            source_ref=str(report_id) if report_id else None,
            status="pending",
            confidence=0.8,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        session.add(proposal)
        await session.flush()
        logger.info(
            "Created memory proposal from compliance: tenant=%s report=%s category=%s",
            tenant_id, report_id, category,
        )
        return proposal

    # ------------------------------------------------------------------
    # distill_from_push_result
    # ------------------------------------------------------------------

    async def distill_from_push_result(
        self,
        session: AsyncSession,
        tenant_id: str,
        push_result: dict[str, Any],
    ) -> CategoryMemoryProposalPO | None:
        """从平台推送结果中提炼候选记忆。

        根据推送表现提炼 best_practices 和 performance_hints。

        Args:
            session: 数据库会话。
            tenant_id: 租户 ID。
            push_result: 推送结果数据。

        Returns:
            创建的提案对象，或 None。
        """
        category = push_result.get("category", "unknown")
        listing_id = push_result.get("listing_id") or push_result.get("id")
        best_practices: list[str] = []
        performance_hints: dict[str, Any] = {}
        summary_parts: list[str] = []

        # 高表现指标 -> best_practices
        high_performance = push_result.get("high_performance", {})
        if isinstance(high_performance, dict):
            for key, value in high_performance.items():
                best_practices.append(f"{key}: {value}")
            if best_practices:
                summary_parts.append(f"从推送结果提炼了 {len(best_practices)} 条最佳实践")

        # 转化/曝光数据 -> performance_hints
        metrics = push_result.get("metrics", {})
        if isinstance(metrics, dict) and metrics:
            performance_hints = dict(metrics)
            summary_parts.append("从推送结果提炼了性能指标")

        if not best_practices and not performance_hints:
            return None

        summary = "；".join(summary_parts) if summary_parts else None

        proposal = CategoryMemoryProposalPO(
            tenant_id=tenant_id,
            category=category,
            summary=summary,
            best_practices=best_practices,
            performance_hints=performance_hints,
            source_type="platform_push",
            source_ref=str(listing_id) if listing_id else None,
            status="pending",
            confidence=0.6,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        session.add(proposal)
        await session.flush()
        logger.info(
            "Created memory proposal from push result: tenant=%s listing=%s category=%s",
            tenant_id, listing_id, category,
        )
        return proposal
