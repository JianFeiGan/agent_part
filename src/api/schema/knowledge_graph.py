"""知识库管理 API Schema。"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class KnowledgeGraphCreate(BaseModel):
    """创建知识图谱请求。"""

    name: str = Field(..., description="图谱名称", min_length=1, max_length=100)
    description: str | None = Field(default=None, description="图谱描述")


class KnowledgeGraphResponse(BaseModel):
    """知识图谱响应。"""

    id: str
    name: str
    tenant_id: str
    status: str
    document_count: int = 0
    entity_count: int = 0
    relation_count: int = 0
    created_at: datetime
    updated_at: datetime


class KnowledgeGraphListResponse(BaseModel):
    """知识图谱列表响应。"""

    items: list[KnowledgeGraphResponse]
    total: int
    page: int
    page_size: int


class AddDocumentRequest(BaseModel):
    """添加文档请求。"""

    title: str = Field(..., description="文档标题")
    content: str = Field(..., description="文档内容")
    format: str = Field(default="markdown", description="文档格式")


class HybridSearchRequest(BaseModel):
    """混合检索请求。"""

    query: str = Field(..., description="查询文本")
    top_k: int = Field(default=10, ge=1, le=100, description="返回结果数量")
    strategy: str = Field(default="hybrid", description="检索策略")


class SearchResult(BaseModel):
    """检索结果。"""

    id: str
    content: str
    score: float
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """检索响应。"""

    query: str
    results: list[SearchResult]
    answer: str | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)


class AgentQueryRequest(BaseModel):
    """Agent 查询请求。"""

    query: str = Field(..., description="用户查询")
    session_id: str | None = Field(default=None, description="会话 ID")


class AgentQueryResponse(BaseModel):
    """Agent 查询响应。"""

    session_id: str
    answer: str
    sources: list[dict[str, Any]]
    agent_logs: list[dict[str, Any]] = Field(default_factory=list)