"""
资产响应 DTO。

Description:
    定义资产查询 API 的响应模型。
@author ganjianfei
@version 1.0.0
2026-06-19
"""

from pydantic import BaseModel, Field


class AssetResponse(BaseModel):
    """资产响应模型。

    Attributes:
        asset_id: 资产 ID。
        product_id: 关联商品 ID（可空）。
        task_id: 关联任务 ID（可空）。
        asset_type: 资产类型 image/video/document。
        provider: 供应商。
        url: 前端可访问 URL。
        mime_type: MIME 类型（可空）。
        file_size: 文件大小（字节，可空）。
        width: 宽度（像素，可空）。
        height: 高度（像素，可空）。
        duration: 视频时长（秒，可空）。
        is_mock: 是否 mock 生成。
        status: 状态。
        created_at: 创建时间（ISO 8601 字符串）。
    """

    asset_id: int = Field(..., description="资产 ID")
    product_id: str | None = Field(default=None, description="关联商品 ID")
    task_id: str | None = Field(default=None, description="关联任务 ID")
    asset_type: str = Field(..., description="资产类型: image/video/document")
    provider: str = Field(..., description="供应商")
    url: str = Field(..., description="前端可访问 URL")
    mime_type: str | None = Field(default=None, description="MIME 类型")
    file_size: int | None = Field(default=None, description="文件大小（字节）")
    width: int | None = Field(default=None, description="宽度（像素）")
    height: int | None = Field(default=None, description="高度（像素）")
    duration: float | None = Field(default=None, description="视频时长（秒）")
    is_mock: bool = Field(default=False, description="是否 mock 生成")
    status: str = Field(default="completed", description="状态")
    created_at: str = Field(..., description="创建时间")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "asset_id": 1,
                    "product_id": "prod_001",
                    "task_id": None,
                    "asset_type": "image",
                    "provider": "wanx",
                    "url": "/static/images/abc123.png",
                    "mime_type": "image/png",
                    "file_size": 204800,
                    "width": 1024,
                    "height": 1024,
                    "duration": None,
                    "is_mock": False,
                    "status": "completed",
                    "created_at": "2026-06-19T10:00:00",
                }
            ]
        }
    }
