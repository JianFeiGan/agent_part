"""
通用响应模型。

Description:
    定义统一的 API 响应格式，包括成功响应、分页响应、错误响应等。
@author ganjianfei
@version 1.0.0
2026-03-25
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应格式。

    所有 API 接口的响应都应使用此模型包装，确保响应格式一致。

    Attributes:
        code: 状态码，200 表示成功。
        message: 响应消息。
        data: 响应数据。

    Example:
        >>> response = ApiResponse(data={"id": "123"})
        >>> response.model_dump()
        {'code': 200, 'message': 'success', 'data': {'id': '123'}}
    """

    code: int = Field(default=200, description="状态码")
    message: str = Field(default="success", description="消息")
    data: T | None = Field(default=None, description="数据")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "code": 200,
                    "message": "success",
                    "data": {"id": "prod_001", "name": "智能手表"},
                }
            ]
        }
    }


class PageResponse(BaseModel, Generic[T]):
    """分页响应模型。

    用于列表查询接口的分页数据返回。

    Attributes:
        items: 数据列表。
        total: 总记录数。
        page: 当前页码。
        page_size: 每页大小。
        pages: 总页数。

    Example:
        >>> response = PageResponse(
        ...     items=[{"id": "1"}, {"id": "2"}],
        ...     total=100,
        ...     page=1,
        ...     page_size=10,
        ...     pages=10
        ... )
    """

    items: list[T] = Field(default_factory=list, description="数据列表")
    total: int = Field(default=0, description="总数")
    page: int = Field(default=1, ge=1, description="当前页")
    page_size: int = Field(default=10, ge=1, le=100, description="每页大小")
    pages: int = Field(default=0, ge=0, description="总页数")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "items": [
                        {"id": "task_001", "status": "completed"},
                        {"id": "task_002", "status": "running"},
                    ],
                    "total": 100,
                    "page": 1,
                    "page_size": 10,
                    "pages": 10,
                }
            ]
        }
    }


class ErrorResponse(BaseModel):
    """错误响应模型。

    用于 API 错误情况的响应。

    Attributes:
        code: 错误码。
        message: 错误消息。
        detail: 详细错误信息。

    Example:
        >>> error = ErrorResponse(code=404, message="资源不存在", detail="商品ID: 123 不存在")
    """

    code: int = Field(description="错误码")
    message: str = Field(description="错误消息")
    detail: str | None = Field(default=None, description="详细信息")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"code": 404, "message": "资源不存在", "detail": "商品ID: 123 不存在"},
                {"code": 400, "message": "参数错误", "detail": "商品名称不能为空"},
            ]
        }
    }


class HealthResponse(BaseModel):
    """健康检查响应模型。

    用于服务健康检查接口。

    Attributes:
        status: 服务状态。
        version: 服务版本。
        redis: Redis 连接状态。
    """

    status: str = Field(default="ok", description="服务状态")
    version: str = Field(default="0.1.0", description="版本")
    redis: str = Field(default="connected", description="Redis 状态")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"status": "ok", "version": "0.1.0", "redis": "connected"}
            ]
        }
    }