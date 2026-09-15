"""
刊登工作流状态定义。

Description:
    定义刊登工作流的共享状态模型，支持素材和文案的并行生成。
@author ganjianfei
@version 1.1.0
2026-09-15
"""

from operator import add
from typing import Annotated, Any

from pydantic import BaseModel, Field

from src.models.listing import (
    AssetPackage,
    ComplianceReport,
    CopywritingPackage,
    ListingProduct,
    Platform,
)


class ListingState(BaseModel):
    """刊登工作流共享状态。

    状态流转:
        PENDING → 商品导入 → 素材+文案并行生成 → 合规门禁 → 推送/挂起 → 终态

    Attributes:
        product: 待刊登的标准化商品。
        tenant_id: 租户 ID。
        task_id: 关联的刊登任务 ID；为 None 时不做 DB 持久化（纯内存运行）。
        asset_packages: 各平台的素材包 (platform -> package)。
        copywriting_packages: 各平台的文案包 (platform -> package)。
        compliance_reports: 各平台的合规报告 (platform -> report)。
        blocked_platforms: 合规检查 FAIL 被阻断的平台。
        push_results: 各平台推送结果。
        target_platforms: 目标平台列表。
        error: 致命错误信息（触发快速终止）。
        errors: 各节点非致命错误（累加，不阻断流程）。
        current_step: 当前执行步骤。
        step_results: 各步骤执行结果；finalize 写入 final_status。
    """

    product: ListingProduct | None = None
    tenant_id: str = Field(default="", description="租户 ID")
    task_id: int | None = Field(default=None, description="关联刊登任务 ID")
    asset_packages: dict[Platform, AssetPackage] = Field(default_factory=dict)
    copywriting_packages: dict[Platform, CopywritingPackage] = Field(default_factory=dict)
    compliance_reports: dict[Platform, ComplianceReport] = Field(default_factory=dict)
    blocked_platforms: list[Platform] = Field(
        default_factory=list, description="合规 FAIL 被阻断的平台"
    )
    push_results: dict[str, Any] = Field(default_factory=dict, description="各平台推送结果")
    target_platforms: list[Platform] = Field(default_factory=list)
    error: str | None = None
    errors: Annotated[list[dict[str, Any]], add] = Field(
        default_factory=list, description="节点错误（累加）"
    )
    current_step: str = ""
    step_results: dict[str, Any] = Field(default_factory=dict)
