"""知识图谱 API 路由（已废弃的内存占位实现）。

Description:
    本模块的 graphs / search / agent 端点均为进程内内存占位，
    重启即丢，不落库。真实知识库管理请使用 /api/v1/knowledge
    下的 documents 端点（src/api/router/knowledge.py）及
    src/rag/* 持久化实现。保留本路由仅为兼容既有客户端，
    所有端点已在 OpenAPI 中标记 deprecated。
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import AuthDep
from src.api.schema.common import ApiResponse
from src.api.schema.knowledge_graph import (
    AddDocumentRequest,
    AgentQueryRequest,
    AgentQueryResponse,
    HybridSearchRequest,
    KnowledgeGraphCreate,
    KnowledgeGraphListResponse,
    KnowledgeGraphResponse,
    SearchResponse,
    SearchResult,
)
from src.db import get_db
from src.knowledge import (
    DocumentIngestionService,
    KnowledgeAgentWorkflow,
    KnowledgeGraph,
)

router = APIRouter()

_graphs: dict[str, dict[str, Any]] = {}


@router.post(
    "/graphs",
    response_model=ApiResponse[KnowledgeGraphResponse],
    status_code=status.HTTP_201_CREATED,
    deprecated=True,
)
async def create_graph(
    request: KnowledgeGraphCreate,
    auth: AuthDep = None,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[KnowledgeGraphResponse]:
    """创建知识图谱。

    Deprecated: 进程内内存占位，不落库。真实知识库管理请使用
    /api/v1/knowledge documents（src/api/router/knowledge.py）。
    """
    graph_id = f"kg_{uuid.uuid4().hex[:8]}"
    tenant_id = auth.tenant_id if auth else "dev"

    graph_data = {
        "id": graph_id,
        "name": request.name,
        "tenant_id": tenant_id,
        "status": "draft",
        "document_count": 0,
        "entity_count": 0,
        "relation_count": 0,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    _graphs[graph_id] = graph_data

    return ApiResponse.success(
        KnowledgeGraphResponse(**graph_data),
        message="知识图谱创建成功",
    )


@router.get(
    "/graphs",
    response_model=ApiResponse[KnowledgeGraphListResponse],
    deprecated=True,
)
async def list_graphs(
    page: int = 1,
    page_size: int = 20,
    auth: AuthDep = None,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[KnowledgeGraphListResponse]:
    """获取知识图谱列表。

    Deprecated: 进程内内存占位，不落库。真实知识库管理请使用
    /api/v1/knowledge documents（src/api/router/knowledge.py）。
    """
    tenant_id = auth.tenant_id if auth else "dev"

    items = [
        KnowledgeGraphResponse(**g) for g in _graphs.values() if g.get("tenant_id") == tenant_id
    ]

    return ApiResponse.success(
        KnowledgeGraphListResponse(
            items=items,
            total=len(items),
            page=page,
            page_size=page_size,
        )
    )


@router.post(
    "/graphs/{graph_id}/documents",
    response_model=ApiResponse[dict[str, Any]],
    deprecated=True,
)
async def add_document(
    graph_id: str,
    request: AddDocumentRequest,
    auth: AuthDep = None,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    """添加文档到图谱。

    Deprecated: 依赖内存占位图谱。真实知识库管理请使用
    /api/v1/knowledge documents（src/api/router/knowledge.py）。
    """
    if graph_id not in _graphs:
        raise HTTPException(status_code=404, detail="知识图谱不存在")

    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    graph = _graphs[graph_id]

    ingestion = DocumentIngestionService()
    kg = KnowledgeGraph(
        id=graph_id,
        name=graph["name"],
        tenant_id=graph["tenant_id"],
    )

    result = await ingestion.process_document(
        {
            "id": doc_id,
            "title": request.title,
            "content": request.content,
            "format": request.format,
        },
        kg,
    )

    graph["document_count"] += 1
    graph["updated_at"] = datetime.utcnow()

    return ApiResponse.success(result, message="文档添加成功")


@router.post("/search/hybrid", response_model=ApiResponse[SearchResponse], deprecated=True)
async def hybrid_search(
    request: HybridSearchRequest,
    auth: AuthDep = None,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SearchResponse]:
    """混合检索。

    Deprecated: 兼容保留。检索请走 /api/v1/knowledge/search 或 src/rag/*。
    """
    workflow = KnowledgeAgentWorkflow()
    state = await workflow.run(request.query)

    results = [
        SearchResult(
            id=r.get("id", f"result_{i}"),
            content=r.get("content", ""),
            score=r.get("score", 0),
            source=r.get("source"),
        )
        for i, r in enumerate(state.fused_results[: request.top_k])
    ]

    return ApiResponse.success(
        SearchResponse(
            query=request.query,
            results=results,
            answer=state.final_answer,
            sources=state.sources,
        )
    )


@router.post("/agent/query", response_model=ApiResponse[AgentQueryResponse], deprecated=True)
async def agent_query(
    request: AgentQueryRequest,
    auth: AuthDep = None,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[AgentQueryResponse]:
    """Agent 查询入口。

    Deprecated: 兼容保留。真实检索/问答请走 /api/v1/knowledge 与 src/rag/*。
    """
    session_id = request.session_id or f"session_{uuid.uuid4().hex[:8]}"

    workflow = KnowledgeAgentWorkflow()
    state = await workflow.run(request.query)

    return ApiResponse.success(
        AgentQueryResponse(
            session_id=session_id,
            answer=state.final_answer,
            sources=state.sources,
            agent_logs=state.agent_logs,
        )
    )
