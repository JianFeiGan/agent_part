"""
Graph RAG / CategoryMemory 请求/响应 DTO。

Description:
    定义 CategoryMemory、GraphRAGEntity、GraphRAGEdge 的创建请求和响应模型。
@author ganjianfei
@version 1.0.0
2026-06-19
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ============================================================================
# CategoryMemory DTO
# ============================================================================


class CategoryMemoryCreate(BaseModel):
    """类目记忆创建请求。

    Attributes:
        category: 商品类目。
        summary: 类目摘要概述。
        best_practices: 最佳实践列表。
        negative_patterns: 避坑/负面模式列表。
        style_guidelines: 风格指南字典。
        performance_hints: 性能/效果提示字典。
        extra_data: 额外元数据。
    """

    category: str = Field(..., min_length=1, max_length=100, description="商品类目")
    summary: str | None = Field(default=None, description="类目摘要")
    best_practices: list[str] = Field(default_factory=list, description="最佳实践")
    negative_patterns: list[str] = Field(default_factory=list, description="避坑/负面模式")
    style_guidelines: dict[str, Any] = Field(default_factory=dict, description="风格指南")
    performance_hints: dict[str, Any] = Field(default_factory=dict, description="性能提示")
    extra_data: dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class CategoryMemoryUpdate(BaseModel):
    """类目记忆更新请求。

    所有字段均为可选，仅更新传入的非 None 字段。
    """

    category: str | None = Field(default=None, min_length=1, max_length=100, description="商品类目")
    summary: str | None = Field(default=None, description="类目摘要")
    best_practices: list[str] | None = Field(default=None, description="最佳实践")
    negative_patterns: list[str] | None = Field(default=None, description="避坑/负面模式")
    style_guidelines: dict[str, Any] | None = Field(default=None, description="风格指南")
    performance_hints: dict[str, Any] | None = Field(default=None, description="性能提示")
    extra_data: dict[str, Any] | None = Field(default=None, description="额外元数据")


class CategoryMemoryResponse(BaseModel):
    """类目记忆响应模型。"""

    id: int
    tenant_id: str | None
    category: str
    summary: str | None
    best_practices: list[str]
    negative_patterns: list[str]
    style_guidelines: dict[str, Any]
    performance_hints: dict[str, Any]
    extra_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# GraphRAGEntity DTO
# ============================================================================


class GraphRAGEntityCreate(BaseModel):
    """Graph RAG 实体创建请求。"""

    name: str = Field(..., min_length=1, max_length=255, description="实体名称")
    entity_type: str = Field(..., min_length=1, max_length=50, description="实体类型")
    category: str = Field(..., min_length=1, max_length=100, description="商品类目")
    description: str | None = Field(default=None, description="实体描述")
    aliases: list[str] = Field(default_factory=list, description="实体别名")
    extra_data: dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class GraphRAGEntityUpdate(BaseModel):
    """Graph RAG 实体更新请求。

    所有字段均为可选。
    """

    name: str | None = Field(default=None, min_length=1, max_length=255, description="实体名称")
    entity_type: str | None = Field(
        default=None, min_length=1, max_length=50, description="实体类型"
    )
    category: str | None = Field(default=None, min_length=1, max_length=100, description="商品类目")
    description: str | None = Field(default=None, description="实体描述")
    aliases: list[str] | None = Field(default=None, description="实体别名")
    extra_data: dict[str, Any] | None = Field(default=None, description="额外元数据")


class GraphRAGEntityResponse(BaseModel):
    """Graph RAG 实体响应模型。"""

    id: int
    tenant_id: str | None
    name: str
    entity_type: str
    category: str
    description: str | None
    aliases: list[str]
    extra_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# GraphRAGEdge DTO
# ============================================================================


class GraphRAGEdgeCreate(BaseModel):
    """Graph RAG 边创建请求。"""

    source_entity_id: int = Field(..., gt=0, description="源实体 ID")
    target_entity_id: int = Field(..., gt=0, description="目标实体 ID")
    relationship_type: str = Field(..., min_length=1, max_length=50, description="关系类型")
    category: str = Field(..., min_length=1, max_length=100, description="商品类目")
    weight: float = Field(default=1.0, ge=0.0, description="关系权重")
    evidence: str | None = Field(default=None, description="关系依据")
    extra_data: dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class GraphRAGEdgeResponse(BaseModel):
    """Graph RAG 边响应模型。"""

    id: int
    tenant_id: str | None
    source_entity_id: int
    target_entity_id: int
    relationship_type: str
    category: str
    weight: float
    evidence: str | None
    extra_data: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
