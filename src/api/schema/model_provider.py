"""模型厂商 DTO 模型。

Description:
    定义模型厂商管理 API 的请求和响应模型。
@author ganjianfei
@version 1.0.0
2026-07-22
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ModelProviderCreateRequest(BaseModel):
    """创建模型厂商请求模型。

    Attributes:
        name: 厂商标识名（如 sensenova/dashscope/kling）。
        display_name: 显示名称（如 商汤科技/阿里云通义）。
        provider_type: 厂商类型（llm/image/video）。
        base_url: API 基址。
        api_key: API Key（明文传入，服务端加密存储）。
        extra_credentials: 额外凭证（如 secret_key）。
        default_model: 默认模型 ID。
        supported_models: 支持的模型列表。
        model_config_extra: 模型额外配置（如 temperature、max_tokens）。
        protocol: 协议类型（openai_compatible/custom_rest）。
        is_active: 是否启用。
        is_default: 是否为该类型的默认厂商。
    """

    name: str = Field(..., min_length=1, max_length=50, description="厂商标识名")
    display_name: str = Field(..., min_length=1, max_length=100, description="显示名称")
    provider_type: str = Field(..., pattern=r"^(llm|image|video)$", description="厂商类型")
    base_url: str = Field(..., min_length=1, max_length=500, description="API 基址")
    api_key: str = Field(default="", description="API Key")
    extra_credentials: dict = Field(default_factory=dict, description="额外凭证")
    default_model: str = Field(..., min_length=1, max_length=100, description="默认模型 ID")
    supported_models: list[str] = Field(default_factory=list, description="支持的模型列表")
    model_config_extra: dict = Field(default_factory=dict, description="模型额外配置")
    protocol: str = Field(
        default="openai_compatible",
        pattern=r"^(openai_compatible|custom_rest)$",
        description="协议类型",
    )
    is_active: bool = Field(default=True, description="是否启用")
    is_default: bool = Field(default=False, description="是否为默认厂商")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "sensenova",
                    "display_name": "商汤科技",
                    "provider_type": "llm",
                    "base_url": "https://token.sensenova.cn/v1",
                    "api_key": "sk-xxx",
                    "default_model": "sensenova-6.7-flash-lite",
                    "supported_models": ["sensenova-6.7-flash-lite"],
                    "protocol": "openai_compatible",
                    "is_default": False,
                }
            ]
        }
    }


class ModelProviderUpdateRequest(BaseModel):
    """更新模型厂商请求模型。

    所有字段可选，仅更新传入的字段。

    Attributes:
        display_name: 显示名称。
        base_url: API 基址。
        api_key: API Key（空字符串表示不更新）。
        extra_credentials: 额外凭证。
        default_model: 默认模型 ID。
        supported_models: 支持的模型列表。
        model_config_extra: 模型额外配置。
        protocol: 协议类型。
        is_active: 是否启用。
    """

    display_name: str | None = Field(default=None, description="显示名称")
    base_url: str | None = Field(default=None, description="API 基址")
    api_key: str | None = Field(default=None, description="API Key（空字符串表示不更新）")
    extra_credentials: dict | None = Field(default=None, description="额外凭证")
    default_model: str | None = Field(default=None, description="默认模型 ID")
    supported_models: list[str] | None = Field(default=None, description="支持的模型列表")
    model_config_extra: dict | None = Field(default=None, description="模型额外配置")
    protocol: str | None = Field(default=None, description="协议类型")
    is_active: bool | None = Field(default=None, description="是否启用")


class ModelProviderResponse(BaseModel):
    """模型厂商响应模型。

    API Key 脱敏显示，仅保留前 4 位和后 4 位。

    Attributes:
        id: 厂商 ID。
        name: 厂商标识名。
        display_name: 显示名称。
        provider_type: 厂商类型。
        base_url: API 基址。
        api_key_masked: 脱敏后的 API Key。
        default_model: 默认模型 ID。
        supported_models: 支持的模型列表。
        protocol: 协议类型。
        is_active: 是否启用。
        is_default: 是否为默认厂商。
        created_at: 创建时间。
        updated_at: 更新时间。
    """

    id: int = Field(..., description="厂商 ID")
    name: str = Field(..., description="厂商标识名")
    display_name: str = Field(..., description="显示名称")
    provider_type: str = Field(..., description="厂商类型")
    base_url: str = Field(..., description="API 基址")
    api_key_masked: str = Field(default="", description="脱敏后的 API Key")
    default_model: str = Field(..., description="默认模型 ID")
    supported_models: list[str] = Field(default_factory=list, description="支持的模型列表")
    protocol: str = Field(..., description="协议类型")
    is_active: bool = Field(..., description="是否启用")
    is_default: bool = Field(..., description="是否为默认厂商")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "name": "sensenova",
                    "display_name": "商汤科技",
                    "provider_type": "llm",
                    "base_url": "https://token.sensenova.cn/v1",
                    "api_key_masked": "sk-x****xxx",
                    "default_model": "sensenova-6.7-flash-lite",
                    "supported_models": ["sensenova-6.7-flash-lite"],
                    "protocol": "openai_compatible",
                    "is_active": True,
                    "is_default": False,
                }
            ]
        }
    }


class ModelProviderTestRequest(BaseModel):
    """测试模型厂商连接请求模型。

    Attributes:
        model: 可选的测试模型（空则用默认模型）。
    """

    model: str | None = Field(default=None, description="测试模型（空则用默认模型）")


class ModelProviderTestResponse(BaseModel):
    """测试模型厂商连接响应模型。

    Attributes:
        success: 是否连接成功。
        message: 测试结果消息。
        latency_ms: 响应延迟（毫秒）。
    """

    success: bool = Field(..., description="是否连接成功")
    message: str = Field(default="", description="测试结果消息")
    latency_ms: float | None = Field(default=None, description="响应延迟（毫秒）")
