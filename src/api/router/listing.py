"""
刊登工具 API 路由。

Description:
    提供商品导入、刊登任务创建等 REST 接口。
    Phase 1 实现：导入商品、创建任务（素材+文案生成）。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
from typing import Any

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
from src.models.listing import ComplianceReport, ListingProduct

logger = logging.getLogger(__name__)

router = APIRouter()

# 内存存储（Phase 1），后续替换为数据库
_products: dict[str, ListingProduct] = {}
_tasks: list[dict] = []
_compliance_reports: dict[int, dict[str, ComplianceReport]] = {}  # task_id -> {platform: report}


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
    _products[product.sku] = product

    return ApiResponse(
        code=200,
        message="商品导入成功",
        data=ProductResponse(
            sku=product.sku,
            title=product.title,
            description=product.description,
            category=product.category,
            brand=product.brand,
            source_images=[img.model_dump() for img in product.source_images],
        ),
    )


@router.get(
    "/products",
    response_model=ApiResponse[list[ProductResponse]],
    summary="商品列表",
)
async def list_products() -> ApiResponse[list[ProductResponse]]:
    """获取已导入的商品列表。"""
    return ApiResponse(
        code=200,
        message="成功",
        data=[
            ProductResponse(
                sku=p.sku,
                title=p.title,
                description=p.description,
                category=p.category,
                brand=p.brand,
                source_images=[img.model_dump() for img in p.source_images],
            )
            for p in _products.values()
        ],
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
    if request.product_sku not in _products:
        return ApiResponse(code=404, message=f"商品 {request.product_sku} 不存在", data=None)

    task_id = len(_tasks) + 1

    task_data = {
        "task_id": task_id,
        "product_sku": request.product_sku,
        "target_platforms": [p.value for p in request.target_platforms],
        "status": "pending",
    }
    _tasks.append(task_data)

    return ApiResponse(
        code=200,
        message="任务已创建",
        data=ListingTaskResponse(
            task_id=task_id,
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
    return ApiResponse(
        code=200,
        message="成功",
        data=[
            ListingTaskResponse(
                task_id=t["task_id"],
                product_sku=t["product_sku"],
                target_platforms=t["target_platforms"],
                status=t["status"],
            )
            for t in _tasks
        ],
    )


def _report_to_response(report: ComplianceReport) -> ComplianceReportResponse:
    """将内部合规报告转换为 API 响应。

    Args:
        report: 内部合规报告。

    Returns:
        API 响应格式。
    """

    def _issue_to_dict(issue: Any) -> ComplianceIssueResponse:
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
    task = next((t for t in _tasks if t["task_id"] == task_id), None)
    if not task:
        return ApiResponse(code=404, message=f"任务 {task_id} 不存在", data=None)

    product = _products.get(task["product_sku"])
    if not product:
        return ApiResponse(code=404, message=f"商品 {task['product_sku']} 不存在", data=None)

    from src.agents.listing_compliance_checker import ComplianceCheckerAgent
    from src.graph.listing_state import ListingState
    from src.models.listing import Platform

    platforms = [Platform(p) for p in task["target_platforms"]]
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

    _compliance_reports[task_id] = result["compliance_reports"]

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
    reports = _compliance_reports.get(task_id)
    if not reports:
        return ApiResponse(code=404, message=f"任务 {task_id} 无合规报告", data=None)

    return ApiResponse(
        code=200,
        message="成功",
        data={platform.value: _report_to_response(report) for platform, report in reports.items()},
    )
