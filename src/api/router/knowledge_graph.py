"""知识库管理 API 路由。"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import AuthDep
from src.api.schema.common import ApiResponse
from src.api.schema.knowledge_graph import (
    KnowledgeGraphCreate,
    KnowledgeGraphResponse,
    KnowledgeGraphListResponse,
    AddDocumentRequest,
    HybridSearchRequest,
    SearchResponse,
    SearchResult,
    AgentQueryRequest,
    AgentQueryResponse,
)
from src.db import get_db
from src.knowledge import (
    KnowledgeGraph,
    DocumentIngestionService,
    KnowledgeAgentWorkflow,
)

router = APIRouter()

_graphs: dict[str, dict[str, Any]] = {}


@router.post("/graphs", response_model=ApiResponse[KnowledgeGraphResponse], status_code=status.HTTP_201_CREATED)
async def create_graph(
    request: KnowledgeGraphCreate,
    auth: AuthDep = None,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[KnowledgeGraphResponse]:
    """创建知识图谱。"""
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


@router.get("/graphs", response_model=ApiResponse[KnowledgeGraphListResponse])
async def list_graphs(
    page: int = 1,
    page_size: int = 20,
    auth: AuthDep = None,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[KnowledgeGraphListResponse]:
    """获取知识图谱列表。"""
    tenant_id = auth.tenant_id if auth else "dev"

    items = [
        KnowledgeGraphResponse(**g)
        for g in _graphs.values()
        if g.get("tenant_id") == tenant_id
    ]

    return ApiResponse.success(
        KnowledgeGraphListResponse(
            items=items,
            total=len(items),
            page=page,
            page_size=page_size,
        )
    )


@router.post("/graphs/{graph_id}/documents", response_model=ApiResponse[dict[str, Any]])
async def add_document(
    graph_id: str,
    request: AddDocumentRequest,
    auth: AuthDep = None,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    """添加文档到图谱。"""
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


@router.post("/search/hybrid", response_model=ApiResponse[SearchResponse])
async def hybrid_search(
    request: HybridSearchRequest,
    auth: AuthDep = None,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SearchResponse]:
    """混合检索。"""
    workflow = KnowledgeAgentWorkflow()
    state = await workflow.run(request.query)

    results = [
        SearchResult(
            id=r.get("id", f"result_{i}"),
            content=r.get("content", ""),
            score=r.get("score", 0),
            source=r.get("source"),
        )
        for i, r in enumerate(state.fused_results[:request.top_k])
    ]

    return ApiResponse.success(
        SearchResponse(
            query=request.query,
            results=results,
            answer=state.final_answer,
            sources=state.sources,
        )
    )


@router.post("/agent/query", response_model=ApiResponse[AgentQueryResponse])
async def agent_query(
    request: AgentQueryRequest,
    auth: AuthDep = None,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[AgentQueryResponse]:
    """Agent 查询入口。"""
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