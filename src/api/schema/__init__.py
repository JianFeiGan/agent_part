"""
API Schema 模块。

Description:
    定义 FastAPI 的请求和响应模型（DTO）。
@author ganjianfei
@version 1.0.0
2026-03-25
"""

from src.api.schema.common import (
    ApiResponse,
    ErrorResponse,
    HealthResponse,
    PageResponse,
)
from src.api.schema.product import (
    ProductCreateRequest,
    ProductListQuery,
    ProductResponse,
    ProductUpdateRequest,
)
from src.api.schema.task import (
    TaskCreateRequest,
    TaskDetailResponse,
    TaskListQuery,
    TaskStatusResponse,
)
from src.api.schema.asset import (
    ImageResponse,
    QualityReportResponse,
    VideoResponse,
)

__all__ = [
    # Common
    "ApiResponse",
    "PageResponse",
    "ErrorResponse",
    "HealthResponse",
    # Product
    "ProductCreateRequest",
    "ProductUpdateRequest",
    "ProductResponse",
    "ProductListQuery",
    # Task
    "TaskCreateRequest",
    "TaskStatusResponse",
    "TaskDetailResponse",
    "TaskListQuery",
    # Asset
    "ImageResponse",
    "VideoResponse",
    "QualityReportResponse",
]
