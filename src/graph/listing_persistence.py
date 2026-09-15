"""刊登工作流持久化辅助。

Description:
    将刊登工作流各阶段产物（素材包、文案包、合规报告、推送结果）与任务状态
    持久化到 PostgreSQL。save_*/update_* 为 best-effort（失败仅记日志，
    不阻断工作流主流程）；load_* 供 resume/复查场景使用，失败抛异常。
    所有函数按 tenant_id 隔离。
@author ganjianfei
@version 1.0.0
2026-09-15
"""

import logging

from sqlalchemy import select

from src.agents.listing_platform_adapter import PushResult
from src.db.listing_models import (
    AssetPackagePO,
    ComplianceReportPO,
    CopywritingPackagePO,
    ListingTaskPO,
    TaskResultPO,
)
from src.db.postgres import get_db_session
from src.models.listing import (
    AssetPackage,
    ComplianceReport,
    CopywritingPackage,
    Platform,
)

logger = logging.getLogger(__name__)


async def update_task_status(
    task_id: int,
    tenant_id: str,
    status: str,
    workflow_state: str | None = None,
) -> None:
    """更新任务状态（带租户校验，best-effort）。"""
    try:
        async with get_db_session() as session:
            task = await session.get(ListingTaskPO, task_id)
            if not task or task.tenant_id != tenant_id:
                logger.warning(f"更新任务状态跳过: task_id={task_id} 不存在或租户不匹配")
                return
            task.status = status
            if workflow_state is not None:
                task.workflow_state = workflow_state
    except Exception as e:
        logger.error(f"更新任务 {task_id} 状态为 {status} 失败: {e}")


async def save_asset_packages(
    task_id: int,
    tenant_id: str,
    packages: dict[Platform, AssetPackage],
) -> None:
    """按 (task_id, platform) upsert 素材包（best-effort）。"""
    if not packages:
        return
    try:
        async with get_db_session() as session:
            for platform, pkg in packages.items():
                result = await session.execute(
                    select(AssetPackagePO).where(
                        AssetPackagePO.task_id == task_id,
                        AssetPackagePO.platform == platform.value,
                        AssetPackagePO.tenant_id == tenant_id,
                    )
                )
                po = result.scalar_one_or_none()
                if po is None:
                    po = AssetPackagePO(
                        tenant_id=tenant_id, task_id=task_id, platform=platform.value
                    )
                    session.add(po)
                po.main_image = pkg.main_image
                po.variant_images = pkg.variant_images
                po.video_url = pkg.video_url
                po.a_plus_images = pkg.a_plus_images
    except Exception as e:
        logger.error(f"持久化素材包失败 task_id={task_id}: {e}")


async def save_copywriting_packages(
    task_id: int,
    tenant_id: str,
    packages: dict[Platform, CopywritingPackage],
) -> None:
    """按 (task_id, platform) upsert 文案包（best-effort）。"""
    if not packages:
        return
    try:
        async with get_db_session() as session:
            for platform, pkg in packages.items():
                result = await session.execute(
                    select(CopywritingPackagePO).where(
                        CopywritingPackagePO.task_id == task_id,
                        CopywritingPackagePO.platform == platform.value,
                        CopywritingPackagePO.tenant_id == tenant_id,
                    )
                )
                po = result.scalar_one_or_none()
                if po is None:
                    po = CopywritingPackagePO(
                        tenant_id=tenant_id, task_id=task_id, platform=platform.value
                    )
                    session.add(po)
                po.language = pkg.language
                po.title = pkg.title
                po.bullet_points = pkg.bullet_points
                po.description = pkg.description
                po.search_terms = pkg.search_terms
    except Exception as e:
        logger.error(f"持久化文案包失败 task_id={task_id}: {e}")


async def save_compliance_reports(
    task_id: int,
    tenant_id: str,
    reports: dict[Platform, ComplianceReport],
) -> None:
    """按 (task_id, platform) upsert 合规报告（best-effort）。"""
    if not reports:
        return
    try:
        async with get_db_session() as session:
            for platform, report in reports.items():
                result = await session.execute(
                    select(ComplianceReportPO).where(
                        ComplianceReportPO.task_id == task_id,
                        ComplianceReportPO.platform == platform.value,
                        ComplianceReportPO.tenant_id == tenant_id,
                    )
                )
                po = result.scalar_one_or_none()
                if po is None:
                    po = ComplianceReportPO(
                        tenant_id=tenant_id, task_id=task_id, platform=platform.value
                    )
                    session.add(po)
                po.report_data = {
                    "overall": report.overall.value,
                    "image_issues": [i.model_dump() for i in report.image_issues],
                    "text_issues": [i.model_dump() for i in report.text_issues],
                    "forbidden_words": report.forbidden_words,
                }
    except Exception as e:
        logger.error(f"持久化合规报告失败 task_id={task_id}: {e}")


async def save_push_results(
    task_id: int,
    tenant_id: str,
    results: dict[str, PushResult],
) -> None:
    """按 (task_id, platform) upsert 推送结果（best-effort）。"""
    if not results:
        return
    try:
        async with get_db_session() as session:
            for platform_name, r in results.items():
                result = await session.execute(
                    select(TaskResultPO).where(
                        TaskResultPO.task_id == task_id,
                        TaskResultPO.platform == platform_name,
                        TaskResultPO.tenant_id == tenant_id,
                    )
                )
                po = result.scalar_one_or_none()
                if po is None:
                    po = TaskResultPO(
                        tenant_id=tenant_id, task_id=task_id, platform=platform_name
                    )
                    session.add(po)
                po.success = r.success
                po.result_data = {
                    "listing_id": r.listing_id,
                    "url": r.url,
                    "error": r.error,
                    "error_code": r.error_code,
                    "retry_count": r.retry_count,
                    "latency_ms": r.latency_ms,
                }
    except Exception as e:
        logger.error(f"持久化推送结果失败 task_id={task_id}: {e}")


async def load_asset_packages(
    task_id: int, tenant_id: str
) -> dict[Platform, AssetPackage]:
    """加载任务的素材包（不存在返回空 dict）。"""
    async with get_db_session() as session:
        result = await session.execute(
            select(AssetPackagePO).where(
                AssetPackagePO.task_id == task_id,
                AssetPackagePO.tenant_id == tenant_id,
            )
        )
        return {
            Platform(po.platform): AssetPackage(
                id=po.id,
                listing_task_id=po.task_id,
                platform=Platform(po.platform),
                main_image=po.main_image,
                variant_images=po.variant_images or [],
                video_url=po.video_url,
                a_plus_images=po.a_plus_images or [],
            )
            for po in result.scalars().all()
        }


async def load_copywriting_packages(
    task_id: int, tenant_id: str
) -> dict[Platform, CopywritingPackage]:
    """加载任务的文案包（不存在返回空 dict）。"""
    async with get_db_session() as session:
        result = await session.execute(
            select(CopywritingPackagePO).where(
                CopywritingPackagePO.task_id == task_id,
                CopywritingPackagePO.tenant_id == tenant_id,
            )
        )
        return {
            Platform(po.platform): CopywritingPackage(
                id=po.id,
                listing_task_id=po.task_id,
                platform=Platform(po.platform),
                language=po.language,
                title=po.title,
                bullet_points=po.bullet_points or [],
                description=po.description,
                search_terms=po.search_terms or [],
            )
            for po in result.scalars().all()
        }


async def load_blocked_platforms(task_id: int, tenant_id: str) -> set[Platform]:
    """从最新合规报告中提取 overall=fail 的平台集合。"""
    async with get_db_session() as session:
        result = await session.execute(
            select(ComplianceReportPO).where(
                ComplianceReportPO.task_id == task_id,
                ComplianceReportPO.tenant_id == tenant_id,
            )
        )
        return {
            Platform(po.platform)
            for po in result.scalars().all()
            if po.report_data.get("overall") == "fail"
        }


async def load_push_result_statuses(task_id: int, tenant_id: str) -> dict[str, bool]:
    """加载各平台最新推送结果的成功标记 {platform_name: success}。"""
    async with get_db_session() as session:
        result = await session.execute(
            select(TaskResultPO).where(
                TaskResultPO.task_id == task_id,
                TaskResultPO.tenant_id == tenant_id,
            )
        )
        return {po.platform: po.success for po in result.scalars().all()}
