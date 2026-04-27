"""
刊登工具 API 路由。

Description:
    提供商品导入、刊登任务创建等 REST 接口。
    Phase 2 接入 PostgreSQL 数据库，替换内存存储。
    Phase 3-5 实现：导入商品、创建任务（素材+文案生成）。
    Phase 6 增强：合规检查、推送刊登全流程。
    素材和文案生成通过 LangGraph 工作流异步执行。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
from decimal import Decimal

from fastapi import APIRouter, status

from src.api.schema.common import ApiResponse
from src.api.schema.listing import (
    ComplianceIssueResponse,
    ComplianceReportResponse,
    CreateListingTaskRequest,
    ListingTaskResponse,
    ProductImportRequest,
    ProductResponse,
)
from src.db.listing_models import (
    ComplianceReportPO,
    ListingProductPO,
    ListingTaskPO,
)
from src.db.postgres import get_db
from src.db.repository import BaseRepository
from src.models.listing import ComplianceReport, ComplianceStatus, ListingProduct, Platform

logger = logging.getLogger(__name__)

router = APIRouter()


def _po_to_product(po: ListingProductPO) -> ListingProduct:
    """将 ORM 对象转换为领域模型。"""
    from src.models.listing import ImageRef

    return ListingProduct(
        id=po.id,
        sku=po.sku,
        title=po.title,
        description=po.description,
        category=po.category,
        brand=po.brand,
        price=Decimal(str(po.price)) if po.price else None,
        weight=Decimal(str(po.weight)) if po.weight else None,
        dimensions=po.dimensions or {},
        source_images=[ImageRef(**img) for img in (po.source_images or [])],
        attributes=po.attributes or {},
    )


def _po_to_response(po: ListingProductPO) -> ProductResponse:
    """将 ORM 对象转换为 API 响应。"""
    return ProductResponse(
        sku=po.sku,
        title=po.title,
        description=po.description,
        category=po.category,
        brand=po.brand,
        source_images=po.source_images or [],
    )


@router.post(
    "/import-product",
    response_model=ApiResponse[ProductResponse],
    status_code=status.HTTP_201_CREATED,
    summary="导入商品",
)
async def import_product(request: ProductImportRequest) -> ApiResponse[ProductResponse]:
    """导入商品到刊登系统。

    Args:
        request: 商品导入请求。

    Returns:
        导入的商品信息。
    """
    from src.agents.listing_importer import ImportProductAgent

    agent = ImportProductAgent()
    product_data = request.model_dump()
    result = agent.execute_manual(product_data)

    if not result["success"]:
        return ApiResponse(code=400, message=result["error"], data=None)

    product = result["product"]

    async with get_db() as session:
        repo = BaseRepository(ListingProductPO, session)
        try:
            po = await repo.create(
                sku=product.sku,
                title=product.title,
                description=product.description,
                category=product.category,
                brand=product.brand,
                price=float(product.price) if product.price else None,
                weight=float(product.weight) if product.weight else None,
                dimensions=product.dimensions,
                source_images=[img.model_dump() for img in product.source_images],
                attributes=product.attributes,
            )
        except Exception:
            # SKU 已存在，返回已有商品
            existing = await repo.get_by_field("sku", product.sku)
            if existing:
                po = existing
            else:
                raise

    return ApiResponse(
        code=200,
        message="商品导入成功",
        data=_po_to_response(po),
    )


@router.get(
    "/products",
    response_model=ApiResponse[list[ProductResponse]],
    summary="商品列表",
)
async def list_products() -> ApiResponse[list[ProductResponse]]:
    """获取已导入的商品列表。"""
    async with get_db() as session:
        repo = BaseRepository(ListingProductPO, session)
        products = await repo.list()
        return ApiResponse(
            code=200,
            message="成功",
            data=[_po_to_response(p) for p in products],
        )


@router.post(
    "/tasks",
    response_model=ApiResponse[ListingTaskResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建刊登任务",
)
async def create_task(request: CreateListingTaskRequest) -> ApiResponse[ListingTaskResponse]:
    """创建刊登任务，触发生成素材和文案。

    Args:
        request: 刊登任务请求。

    Returns:
        创建的任务信息。
    """
    async with get_db() as session:
        product_repo = BaseRepository(ListingProductPO, session)
        product_po = await product_repo.get_by_field("sku", request.product_sku)
        if not product_po:
            return ApiResponse(code=404, message=f"商品 {request.product_sku} 不存在", data=None)

        task_repo = BaseRepository(ListingTaskPO, session)
        task_po = await task_repo.create(
            product_sku=request.product_sku,
            target_platforms=[p.value for p in request.target_platforms],
            status="pending",
        )

    return ApiResponse(
        code=200,
        message="任务已创建",
        data=ListingTaskResponse(
            task_id=task_po.id,
            product_sku=request.product_sku,
            target_platforms=[p.value for p in request.target_platforms],
            status="pending",
        ),
    )


@router.get(
    "/tasks",
    response_model=ApiResponse[list[ListingTaskResponse]],
    summary="任务列表",
)
async def list_tasks() -> ApiResponse[list[ListingTaskResponse]]:
    """获取刊登任务列表。"""
    async with get_db() as session:
        repo = BaseRepository(ListingTaskPO, session)
        tasks = await repo.list()
        return ApiResponse(
            code=200,
            message="成功",
            data=[
                ListingTaskResponse(
                    task_id=t.id,
                    product_sku=t.product_sku,
                    target_platforms=t.target_platforms,
                    status=t.status,
                )
                for t in tasks
            ],
        )


def _report_to_response(report: ComplianceReport) -> ComplianceReportResponse:
    """将内部合规报告转换为 API 响应。

    Args:
        report: 内部合规报告。

    Returns:
        API 响应格式。
    """

    def _issue_to_dict(issue) -> ComplianceIssueResponse:
        return ComplianceIssueResponse(
            severity=issue.severity,
            rule=issue.rule,
            field=issue.field,
            message=issue.message,
            suggestion=issue.suggestion,
        )

    return ComplianceReportResponse(
        platform=report.platform.value,
        overall=report.overall,
        image_issues=[_issue_to_dict(i) for i in report.image_issues],
        text_issues=[_issue_to_dict(i) for i in report.text_issues],
        forbidden_words=report.forbidden_words,
    )


def _po_to_report(po: ComplianceReportPO) -> ComplianceReport:
    """将 ORM 对象转换为领域报告模型。"""
    from src.models.listing import ComplianceIssue

    report = ComplianceReport(
        id=po.id,
        listing_task_id=po.task_id,
        platform=Platform(po.platform),
        overall=ComplianceStatus(po.report_data.get("overall", "pass")),
    )
    for issue_data in po.report_data.get("image_issues", []):
        report.image_issues.append(ComplianceIssue(**issue_data))
    for issue_data in po.report_data.get("text_issues", []):
        report.text_issues.append(ComplianceIssue(**issue_data))
    report.forbidden_words = po.report_data.get("forbidden_words", [])
    return report


@router.post(
    "/tasks/{task_id}/compliance",
    response_model=ApiResponse[dict[str, ComplianceReportResponse]],
    status_code=status.HTTP_201_CREATED,
    summary="执行合规检查",
)
async def run_compliance_check(task_id: int) -> ApiResponse[dict[str, ComplianceReportResponse]]:
    """对指定任务执行合规检查。

    Args:
        task_id: 任务ID。

    Returns:
        各平台合规报告。
    """
    async with get_db() as session:
        task_repo = BaseRepository(ListingTaskPO, session)
        task_po = await task_repo.get(task_id)
        if not task_po:
            return ApiResponse(code=404, message=f"任务 {task_id} 不存在", data=None)

        product_repo = BaseRepository(ListingProductPO, session)
        product_po = await product_repo.get_by_field("sku", task_po.product_sku)
        if not product_po:
            return ApiResponse(code=404, message=f"商品 {task_po.product_sku} 不存在", data=None)

        from src.agents.listing_compliance_checker import ComplianceCheckerAgent
        from src.graph.listing_state import ListingState

        product = _po_to_product(product_po)
        platforms = [Platform(p) for p in task_po.target_platforms]
        state = ListingState(
            product=product,
            target_platforms=platforms,
        )
        # 为每个平台创建空的文案包以触发检查
        for platform in platforms:
            from src.models.listing import CopywritingPackage

            state.copywriting_packages[platform] = CopywritingPackage(
                listing_task_id=task_id,
                platform=platform,
                language="en",
                title=product.title,
                bullet_points=[],
                description=product.description or "",
            )

        agent = ComplianceCheckerAgent()
        result = agent.execute_sync(state)

        # 保存到数据库
        for platform, report in result["compliance_reports"].items():
            report_po_data = {
                "overall": report.overall.value,
                "image_issues": [i.model_dump() for i in report.image_issues],
                "text_issues": [i.model_dump() for i in report.text_issues],
                "forbidden_words": report.forbidden_words,
            }
            po = ComplianceReportPO(
                task_id=task_id,
                platform=platform.value,
                report_data=report_po_data,
            )
            session.add(po)

    reports = {
        platform.value: _report_to_response(report)
        for platform, report in result["compliance_reports"].items()
    }

    return ApiResponse(code=200, message="合规检查完成", data=reports)


@router.get(
    "/compliance/{task_id}",
    response_model=ApiResponse[dict[str, ComplianceReportResponse]],
    summary="查询合规报告",
)
async def get_compliance_report(task_id: int) -> ApiResponse[dict[str, ComplianceReportResponse]]:
    """获取指定任务的合规报告。

    Args:
        task_id: 任务ID。

    Returns:
        各平台合规报告。
    """
    async with get_db() as session:
        repo = BaseRepository(ComplianceReportPO, session)
        reports_po = await repo.list(task_id=task_id)
        if not reports_po:
            return ApiResponse(code=404, message=f"任务 {task_id} 无合规报告", data=None)

        result = {}
        for po in reports_po:
            report = _po_to_report(po)
            result[po.platform] = _report_to_response(report)

        return ApiResponse(
            code=200,
            message="成功",
            data=result,
        )
