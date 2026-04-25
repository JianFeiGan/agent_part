"""
适配器配置 API Schema。

Description:
    定义适配器配置的请求/响应 DTO。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

from pydantic import BaseModel, Field

from src.models.listing import Platform


class AdapterConfigCreate(BaseModel):
    """创建适配器配置请求。"""

    platform: Platform
    shop_id: str = Field(default="default", max_length=100, description="店铺ID")
    credentials: dict = Field(..., min_length=1, description="凭证（含 API Key、Token 等）")
    is_active: bool = Field(default=True, description="是否启用")


class AdapterConfigUpdate(BaseModel):
    """更新适配器配置请求。"""

    credentials: dict | None = Field(default=None, description="凭证（部分更新）")
    is_active: bool | None = Field(default=None, description="是否启用")


class AdapterConfigResponse(BaseModel):
    """适配器配置响应（脱敏）。"""

    id: int
    platform: str
    shop_id: str
    credentials_masked: dict[str, str]  # 值全部为 "***"
    is_active: bool
    created_at: str | None
    updated_at: str | None
