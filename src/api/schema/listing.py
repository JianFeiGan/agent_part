"""
刊登工具 API Schema。

Description:
    定义刊登工具的请求/响应 DTO。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

from typing import Any

from pydantic import BaseModel, Field

from src.models.listing import ComplianceStatus, Platform


class ComplianceIssueResponse(BaseModel):
    """合规问题响应。"""

    severity: ComplianceStatus
    rule: str
    field: str
    message: str
    suggestion: str | None


class ComplianceReportResponse(BaseModel):
    """合规报告响应。"""

    platform: str
    overall: ComplianceStatus
    image_issues: list[ComplianceIssueResponse]
    text_issues: list[ComplianceIssueResponse]
    forbidden_words: list[str]


class ProductImportRequest(BaseModel):
    """商品导入请求。"""

    sku: str = Field(..., min_length=1, max_length=100, description="商品SKU")
    title: str = Field(..., min_length=1, max_length=500, description="商品标题")
    description: str | None = Field(default=None, description="商品描述")
    category: str | None = Field(default=None, description="商品类目")
    brand: str | None = Field(default=None, description="品牌")
    price: float | None = Field(default=None, ge=0, description="价格")
    weight: float | None = Field(default=None, ge=0, description="重量(kg)")
    dimensions: dict[str, Any] | None = Field(default=None, description="尺寸")
    source_images: list[dict[str, Any]] = Field(default_factory=list, description="图片列表")
    attributes: dict[str, Any] = Field(default_factory=dict, description="属性")


class ProductResponse(BaseModel):
    """商品响应。"""

    sku: str
    title: str
    description: str | None
    category: str | None
    brand: str | None
    source_images: list[dict[str, Any]]


class CreateListingTaskRequest(BaseModel):
    """创建刊登任务请求。"""

    product_sku: str = Field(..., description="商品SKU")
    target_platforms: list[Platform] = Field(..., min_length=1, description="目标平台")


class ListingTaskResponse(BaseModel):
    """刊登任务响应。"""

    task_id: int
    product_sku: str
    target_platforms: list[str]
    status: str


class PushListingRequest(BaseModel):
    """刊登推送请求。"""

    platforms: list[Platform] = Field(
        default_factory=list, description="指定推送平台，空则全部推送"
    )


class PushResultResponse(BaseModel):
    """单个平台推送结果。"""

    platform: str
    success: bool
    listing_id: str | None = None
    url: str | None = None
    error: str | None = None


class PushResponse(BaseModel):
    """刊登推送响应。"""

    task_id: int
    results: list[PushResultResponse]
    status: str
