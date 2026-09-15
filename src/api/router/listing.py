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

import asyncio
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, status

from src.api.deps import AuthDep
from src.api.schema.common import ApiResponse
from src.api.schema.listing import (
    ComplianceIssueResponse,
    ComplianceReportResponse,
    CreateListingTaskRequest,
    FromVisualListingTaskRequest,
    ListingTaskResponse,
    ProductImportRequest,
    ProductResponse,
)
from src.api.service.redis_client import get_redis
from src.auth.api_key import require_auth
from src.auth.context import AuthContext
from src.db.listing_models import (
    ComplianceReportPO,
    ListingProductPO,
    ListingTaskPO,
)
from src.db.postgres import get_db_session
from src.db.repository import BaseRepository
from src.graph.listing_persistence import (
    load_asset_packages,
    load_copywriting_packages,
    save_compliance_reports,
    update_task_status,
)
from src.models.listing import ComplianceReport, ComplianceStatus, ListingProduct, Platform
from src.models.listing_converter import product_to_listing

logger = logging.getLogger(__name__)

router = APIRouter()


async def _run_listing_workflow(
    *,
    task_id: int,
    tenant_id: str,
    product: ListingProduct,
    target_platforms: list[Platform],
) -> None:
    """后台执行刊登工作流。

    状态推进与产物持久化由工作流内部完成；
    此处仅兜底未捕获异常，将任务标记为 failed。
    """
    from src.graph.listing_workflow import ListingWorkflow

    try:
        workflow = ListingWorkflow()
        await workflow.run(
            product=product,
            target_platforms=target_platforms,
            thread_id=f"listing_{task_id}",
            task_id=task_id,
            tenant_id=tenant_id,
        )
        logger.info(f"刊登任务 {task_id} 工作流执行结束")
    except Exception as e:
        logger.exception(f"刊登任务 {task_id} 工作流执行失败: {e}")
        await update_task_status(
            task_id, tenant_id, "failed", workflow_state="workflow_error"
        )


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
async def import_product(
    request: ProductImportRequest,
    auth: AuthContext = Depends(require_auth),
) -> ApiResponse[ProductResponse]:
    """导入商品到刊登系统。

    Args:
        request: 商品导入请求。
        auth: 认证上下文。

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

    async with get_db_session() as session:
        repo = BaseRepository(ListingProductPO, session)
        try:
            po = await repo.create(
                tenant_id=auth.tenant_id,
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
async def list_products(auth: AuthDep) -> ApiResponse[list[ProductResponse]]:
    """获取已导入的商品列表。

    Args:
        auth: 认证上下文。

    Returns:
        商品列表（仅当前租户）。
    """
    async with get_db_session() as session:
        repo = BaseRepository(ListingProductPO, session)
        products = await repo.list(tenant_id=auth.tenant_id)
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
async def create_task(
    request: CreateListingTaskRequest,
    auth: AuthContext = Depends(require_auth),
) -> ApiResponse[ListingTaskResponse]:
    """创建刊登任务，触发生成素材和文案。

    创建 DB 记录后，异步启动 ListingWorkflow 执行
    素材优化 + 文案生成 + 合规检查流程。

    Args:
        request: 刊登任务请求。
        auth: 认证上下文。

    Returns:
        创建的任务信息。
    """
    async with get_db_session() as session:
        product_repo = BaseRepository(ListingProductPO, session)
        product_po = await product_repo.get_by_field("sku", request.product_sku)
        if not product_po:
            return ApiResponse(code=404, message=f"商品 {request.product_sku} 不存在", data=None)

        task_repo = BaseRepository(ListingTaskPO, session)
        task_po = await task_repo.create(
            tenant_id=auth.tenant_id,
            product_sku=request.product_sku,
            target_platforms=[p.value for p in request.target_platforms],
            status="pending",
        )

    # 异步启动刊登工作流
    product = _po_to_product(product_po)
    asyncio.create_task(
        _run_listing_workflow(
            task_id=task_po.id,
            tenant_id=auth.tenant_id,
            product=product,
            target_platforms=request.target_platforms,
        )
    )

    return ApiResponse(
        code=200,
        message="任务已创建，正在执行素材优化和文案生成",
        data=ListingTaskResponse(
            task_id=task_po.id,
            product_sku=request.product_sku,
            target_platforms=[p.value for p in request.target_platforms],
            status="pending",
        ),
    )


@router.post(
    "/tasks/from-visual",
    response_model=ApiResponse[ListingTaskResponse],
    status_code=status.HTTP_201_CREATED,
    summary="基于视觉生成商品创建刊登任务（一键刊登）",
)
async def create_task_from_visual(
    request: FromVisualListingTaskRequest,
    auth: AuthContext = Depends(require_auth),
) -> ApiResponse[ListingTaskResponse]:
    """基于视觉生成商品创建刊登任务。

    通过 product_id 从 Redis 获取视觉生成商品，转换为 ListingProduct
    （attributes 记录 source_product_id），创建刊登任务并异步启动
    ListingWorkflow。工作流导入节点会自动从 generated_assets 拉取
    AI 生成图填充到 source_images。

    Args:
        request: 一键刊登请求。
        auth: 认证上下文。

    Returns:
        创建的刊登任务信息。
    """
    redis = await get_redis()
    product = await redis.get_product(request.product_id, tenant_id=auth.tenant_id)
    if not product:
        return ApiResponse(code=404, message=f"视觉商品 {request.product_id} 不存在", data=None)

    listing_product = product_to_listing(product)

    async with get_db_session() as session:
        product_repo = BaseRepository(ListingProductPO, session)
        try:
            product_po = await product_repo.create(
                tenant_id=auth.tenant_id,
                sku=listing_product.sku,
                title=listing_product.title,
                description=listing_product.description,
                category=listing_product.category,
                brand=listing_product.brand,
                source_images=[img.model_dump() for img in listing_product.source_images],
                attributes=listing_product.attributes,
            )
        except Exception:
            existing = await product_repo.get_by_field("sku", listing_product.sku)
            if existing:
                product_po = existing
            else:
                raise

        listing_product.id = product_po.id

        task_repo = BaseRepository(ListingTaskPO, session)
        task_po = await task_repo.create(
            tenant_id=auth.tenant_id,
            product_sku=listing_product.sku,
            target_platforms=[p.value for p in request.target_platforms],
            status="pending",
        )

    asyncio.create_task(
        _run_listing_workflow(
            task_id=task_po.id,
            tenant_id=auth.tenant_id,
            product=listing_product,
            target_platforms=request.target_platforms,
        )
    )

    return ApiResponse(
        code=200,
        message="一键刊登任务已创建，正在加载 AI 生成图并执行刊登流程",
        data=ListingTaskResponse(
            task_id=task_po.id,
            product_sku=listing_product.sku,
            target_platforms=[p.value for p in request.target_platforms],
            status="pending",
        ),
    )


@router.get(
    "/tasks",
    response_model=ApiResponse[list[ListingTaskResponse]],
    summary="任务列表",
)
async def list_tasks(auth: AuthDep) -> ApiResponse[list[ListingTaskResponse]]:
    """获取刊登任务列表。

    Args:
        auth: 认证上下文。

    Returns:
        任务列表（仅当前租户）。
    """
    async with get_db_session() as session:
        repo = BaseRepository(ListingTaskPO, session)
        tasks = await repo.list(tenant_id=auth.tenant_id)
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
async def run_compliance_check(
    task_id: int,
    auth: AuthContext = Depends(require_auth),
) -> ApiResponse[dict[str, ComplianceReportResponse]]:
    """对指定任务执行合规检查。

    Args:
        task_id: 任务ID。
        auth: 认证上下文。

    Returns:
        各平台合规报告。
    """
    async with get_db_session() as session:
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

        # 加载工作流已持久化的真实产物，而非凭空捏造
        copywriting_packages = await load_copywriting_packages(task_id, auth.tenant_id)
        if not copywriting_packages:
            return ApiResponse(
                code=409,
                message=f"任务 {task_id} 尚无已生成文案，请先执行生成流程",
                data=None,
            )
        asset_packages = await load_asset_packages(task_id, auth.tenant_id)

        state = ListingState(
            product=product,
            target_platforms=platforms,
            task_id=task_id,
            tenant_id=auth.tenant_id,
            asset_packages=asset_packages,
            copywriting_packages=copywriting_packages,
        )

        agent = ComplianceCheckerAgent()
        result = agent.execute_sync(state)

        # upsert 保存，重复复查不产生重复行
        await save_compliance_reports(task_id, auth.tenant_id, result["compliance_reports"])

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
async def get_compliance_report(
    task_id: int,
    auth: AuthContext = Depends(require_auth),
) -> ApiResponse[dict[str, ComplianceReportResponse]]:
    """获取指定任务的合规报告。

    Args:
        task_id: 任务ID。
        auth: 认证上下文。

    Returns:
        各平台合规报告（仅当前租户）。
    """
    async with get_db_session() as session:
        repo = BaseRepository(ComplianceReportPO, session)
        reports_po = await repo.list(task_id=task_id, tenant_id=auth.tenant_id)
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
