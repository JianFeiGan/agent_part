"""
刊登工作流状态定义。

Description:
    定义刊登工作流的共享状态模型，支持素材和文案的并行生成。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

from typing import Any

from pydantic import BaseModel, Field

from src.models.listing import (
    AssetPackage,
    CopywritingPackage,
    ListingProduct,
    Platform,
)


class ListingState(BaseModel):
    """刊登工作流共享状态。

    状态流转:
        PENDING → 商品导入 → 素材+文案并行生成 → 结果收集

    Attributes:
        product: 待刊登的标准化商品。
        asset_packages: 各平台的素材包 (platform -> package)。
        copywriting_packages: 各平台的文案包 (platform -> package)。
        target_platforms: 目标平台列表。
        error: 错误信息（如有）。
        current_step: 当前执行步骤。
        step_results: 各步骤执行结果。
    """

    product: ListingProduct | None = None
    asset_packages: dict[Platform, AssetPackage] = Field(default_factory=dict)
    copywriting_packages: dict[Platform, CopywritingPackage] = Field(default_factory=dict)
    target_platforms: list[Platform] = Field(default_factory=list)
    error: str | None = None
    current_step: str = ""
    step_results: dict[str, Any] = Field(default_factory=dict)