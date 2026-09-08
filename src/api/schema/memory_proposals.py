"""
记忆提案请求/响应 DTO。

Description:
    定义 CategoryMemoryProposalPO 的创建请求、审核请求和响应模型。
@author ganjianfei
@version 1.0.0
2026-06-19
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DistillRequest(BaseModel):
    """记忆提炼请求。

    支持手动触发提炼，传入 source_type 和来源数据。

    Attributes:
        source_type: 来源类型。
        source_ref: 来源引用（task_id / compliance_report_id 等）。
        generation_result: 生成结果数据（task_completion 场景）。
        compliance_data: 合规报告数据（compliance_failure 场景）。
        push_result: 推送结果数据（platform_push 场景）。
        category: 商品类目（可选，从数据中推断）。
    """

    source_type: str = Field(
        ...,
        description="来源类型: task_completion, compliance_failure, platform_push, manual",
    )
    source_ref: str | None = Field(default=None, description="来源引用")
    generation_result: dict[str, Any] | None = Field(
        default=None, description="生成结果（task_completion）"
    )
    compliance_data: dict[str, Any] | None = Field(
        default=None, description="合规报告（compliance_failure）"
    )
    push_result: dict[str, Any] | None = Field(
        default=None, description="推送结果（platform_push）"
    )
    category: str | None = Field(default=None, max_length=100, description="商品类目")


class MemoryProposalResponse(BaseModel):
    """记忆提案响应模型。"""

    id: int
    tenant_id: str
    category: str
    summary: str | None
    best_practices: list[str]
    negative_patterns: list[str]
    style_guidelines: dict[str, Any]
    performance_hints: dict[str, Any]
    source_type: str
    source_ref: str | None
    status: str
    confidence: float
    reviewed_by: str | None
    review_reason: str | None
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class ApproveRequest(BaseModel):
    """审批通过请求。

    可选覆盖 proposal 中的字段后再写入 CategoryMemory。
    """

    summary: str | None = Field(default=None, description="覆盖摘要")
    best_practices: list[str] | None = Field(default=None, description="追加最佳实践")
    negative_patterns: list[str] | None = Field(default=None, description="追加负面模式")
    style_guidelines: dict[str, Any] | None = Field(default=None, description="覆盖风格指南")
    performance_hints: dict[str, Any] | None = Field(default=None, description="覆盖性能提示")


class RejectRequest(BaseModel):
    """审批拒绝请求。"""

    reason: str = Field(..., min_length=1, max_length=500, description="拒绝理由")
