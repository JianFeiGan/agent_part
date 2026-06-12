"""
仪表盘 Schema 模型。

Description:
    定义仪表盘统计相关的 API 响应模型。
@author ganjianfei
@version 1.0.0
2026-06-12
"""

from pydantic import BaseModel, Field


class RecentTaskItem(BaseModel):
    """最近任务条目。

    Attributes:
        task_id: 任务 ID。
        product_id: 关联商品 ID（可能为空）。
        task_type: 任务类型（可能为空）。
        status: 任务状态。
        progress: 进度 (0-100)。
        current_step: 当前步骤。
        created_at: 创建时间。
        updated_at: 更新时间。
    """

    task_id: str = Field(..., description="任务 ID")
    product_id: str | None = Field(default=None, description="商品 ID")
    task_type: str | None = Field(default=None, description="任务类型")
    status: str = Field(..., description="任务状态")
    progress: float = Field(default=0.0, description="进度")
    current_step: str = Field(default="init", description="当前步骤")
    created_at: str | None = Field(default=None, description="创建时间")
    updated_at: str | None = Field(default=None, description="更新时间")


class DashboardStatsResponse(BaseModel):
    """仪表盘统计响应模型。

    Attributes:
        total_products: 商品总数。
        total_tasks: 任务总数。
        running_tasks: 运行中任务数。
        failed_tasks: 失败任务数。
        recent_tasks: 最近任务列表。
    """

    total_products: int = Field(default=0, description="商品总数")
    total_tasks: int = Field(default=0, description="任务总数")
    running_tasks: int = Field(default=0, description="运行中任务数")
    failed_tasks: int = Field(default=0, description="失败任务数")
    recent_tasks: list[RecentTaskItem] = Field(default_factory=list, description="最近任务列表")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "total_products": 128,
                    "total_tasks": 256,
                    "running_tasks": 12,
                    "failed_tasks": 3,
                    "recent_tasks": [
                        {
                            "task_id": "task_abc123",
                            "product_id": "prod_001",
                            "task_type": "image_only",
                            "status": "completed",
                            "progress": 100.0,
                            "current_step": "completed",
                            "created_at": "2026-06-12T10:00:00",
                            "updated_at": "2026-06-12T10:30:00",
                        }
                    ],
                }
            ]
        }
    }
