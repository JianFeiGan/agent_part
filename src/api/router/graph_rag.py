"""
Graph RAG / CategoryMemory CRUD 路由。

Description:
    提供 CategoryMemory、GraphRAGEntity、GraphRAGEdge 的 CRUD 接口。
    租户隔离、scope 校验、404 防枚举、409 冲突翻译均由 src/api/crud
    的 TenantCRUD 门面承载（读路径放行共享行，写路径恒严格本租户）。

    前缀: /api/v1/graph-rag
@author ganjianfei
@version 1.1.0
2026-09-08
"""

from fastapi import APIRouter, Query, status

from src.api.crud import ResourceSpec, Scopes, TenantCRUD, TenantMatch
from src.api.deps import AuthDep, SessionDep
from src.api.schema.common import ApiResponse
from src.api.schema.graph_rag import (
    CategoryMemoryCreate,
    CategoryMemoryResponse,
    CategoryMemoryUpdate,
    GraphRAGEdgeCreate,
    GraphRAGEdgeResponse,
    GraphRAGEntityCreate,
    GraphRAGEntityResponse,
    GraphRAGEntityUpdate,
)
from src.db.models import CategoryMemory, GraphRAGEdge, GraphRAGEntity

router = APIRouter()

_memory_crud: TenantCRUD[CategoryMemory] = TenantCRUD(
    ResourceSpec(
        model=CategoryMemory,
        label="类目记忆",
        scopes=Scopes.rw("memory:read", "memory:write"),
        read_match=TenantMatch.SHARED_READ,
        default_order=(CategoryMemory.updated_at.desc(),),
        not_found_detail="类目记忆不存在",
    )
)

_entity_crud: TenantCRUD[GraphRAGEntity] = TenantCRUD(
    ResourceSpec(
        model=GraphRAGEntity,
        label="实体",
        scopes=Scopes.rw("memory:read", "memory:write"),
        read_match=TenantMatch.SHARED_READ,
        list_shared=True,
        default_order=(GraphRAGEntity.updated_at.desc(),),
        not_found_detail="实体不存在",
    )
)

_edge_crud: TenantCRUD[GraphRAGEdge] = TenantCRUD(
    ResourceSpec(
        model=GraphRAGEdge,
        label="边",
        scopes=Scopes.rw("memory:read", "memory:write"),
        read_match=TenantMatch.SHARED_READ,
        list_shared=True,
        default_order=(GraphRAGEdge.created_at.desc(),),
        not_found_detail="边不存在",
    )
)

# ============================================================================
# CategoryMemory CRUD
# ============================================================================


@router.post(
    "/memories",
    response_model=ApiResponse[CategoryMemoryResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建类目记忆",
)
async def create_memory(
    request: CategoryMemoryCreate,
    auth: AuthDep,
    session: SessionDep,
) -> ApiResponse[CategoryMemoryResponse]:
    """创建类目记忆。

    写入时 tenant_id 强制覆盖为 auth.tenant_id，防止伪造。
    若 (tenant_id, category) 重复则返回 409。

    Args:
        request: 类目记忆创建请求。
        auth: 认证上下文。
        session: 数据库会话。

    Returns:
        创建成功的类目记忆。
    """
    memory = await _memory_crud.create(
        session,
        auth,
        request,
        conflict_detail=lambda m: (
            f"类目记忆已存在: tenant_id={auth.tenant_id}, category={m.category}"
        ),
    )
    return ApiResponse.success(CategoryMemoryResponse.model_validate(memory), message="创建成功")


@router.get(
    "/memories",
    response_model=ApiResponse[list[CategoryMemoryResponse]],
    summary="获取类目记忆列表",
)
async def list_memories(
    auth: AuthDep,
    session: SessionDep,
    category: str | None = Query(default=None, description="按类目过滤"),
    include_shared: bool = Query(default=False, description="是否包含共享记忆"),
    limit: int = 50,
) -> ApiResponse[list[CategoryMemoryResponse]]:
    """获取类目记忆列表。

    按租户过滤；include_shared=true 时同时返回 tenant_id IS NULL 的共享记忆。

    Args:
        auth: 认证上下文。
        session: 数据库会话。
        category: 按类目过滤（可选）。
        include_shared: 是否包含共享记忆。
        limit: 返回数量上限。

    Returns:
        类目记忆列表。
    """
    memories = await _memory_crud.list(
        session, auth, limit=limit, include_shared=include_shared, category=category or None
    )
    return ApiResponse.success(
        [CategoryMemoryResponse.model_validate(m) for m in memories], message="获取成功"
    )


@router.get(
    "/memories/{memory_id}",
    response_model=ApiResponse[CategoryMemoryResponse],
    summary="获取类目记忆详情",
)
async def get_memory(
    memory_id: int,
    auth: AuthDep,
    session: SessionDep,
) -> ApiResponse[CategoryMemoryResponse]:
    """获取类目记忆详情。

    跨租户访问返回 404；共享记忆（tenant_id IS NULL）可读。

    Args:
        memory_id: 记忆 ID。
        auth: 认证上下文。
        session: 数据库会话。

    Returns:
        类目记忆详情。
    """
    memory = await _memory_crud.get(session, auth, memory_id)
    return ApiResponse.success(CategoryMemoryResponse.model_validate(memory), message="获取成功")


@router.patch(
    "/memories/{memory_id}",
    response_model=ApiResponse[CategoryMemoryResponse],
    summary="更新类目记忆",
)
async def update_memory(
    memory_id: int,
    request: CategoryMemoryUpdate,
    auth: AuthDep,
    session: SessionDep,
) -> ApiResponse[CategoryMemoryResponse]:
    """更新类目记忆。

    仅本租户的记忆可更新；共享记忆（tenant_id IS NULL）不可通过此接口修改。

    Args:
        memory_id: 记忆 ID。
        request: 更新请求。
        auth: 认证上下文。
        session: 数据库会话。

    Returns:
        更新后的类目记忆。
    """
    memory = await _memory_crud.update(
        session,
        auth,
        memory_id,
        request,
        conflict_detail=lambda m: (
            f"类目记忆已存在: tenant_id={auth.tenant_id}, category={m.category}"
        ),
    )
    return ApiResponse.success(CategoryMemoryResponse.model_validate(memory), message="更新成功")


@router.delete(
    "/memories/{memory_id}",
    response_model=ApiResponse[None],
    summary="删除类目记忆",
)
async def delete_memory(
    memory_id: int,
    auth: AuthDep,
    session: SessionDep,
) -> ApiResponse[None]:
    """删除类目记忆。

    仅本租户的记忆可删除。

    Args:
        memory_id: 记忆 ID。
        auth: 认证上下文。
        session: 数据库会话。

    Returns:
        删除结果。
    """
    await _memory_crud.delete(session, auth, memory_id)
    return ApiResponse.success(message="删除成功")


# ============================================================================
# GraphRAGEntity CRUD
# ============================================================================


@router.post(
    "/entities",
    response_model=ApiResponse[GraphRAGEntityResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建实体",
)
async def create_entity(
    request: GraphRAGEntityCreate,
    auth: AuthDep,
    session: SessionDep,
) -> ApiResponse[GraphRAGEntityResponse]:
    """创建 Graph RAG 实体。

    tenant_id 强制覆盖为 auth.tenant_id。

    Args:
        request: 实体创建请求。
        auth: 认证上下文。
        session: 数据库会话。

    Returns:
        创建成功的实体。
    """
    entity = await _entity_crud.create(session, auth, request)
    return ApiResponse.success(GraphRAGEntityResponse.model_validate(entity), message="创建成功")


@router.get(
    "/entities",
    response_model=ApiResponse[list[GraphRAGEntityResponse]],
    summary="获取实体列表",
)
async def list_entities(
    auth: AuthDep,
    session: SessionDep,
    category: str | None = Query(default=None, description="按类目过滤"),
    entity_type: str | None = Query(default=None, description="按实体类型过滤"),
    limit: int = 50,
) -> ApiResponse[list[GraphRAGEntityResponse]]:
    """获取实体列表。

    按租户过滤并包含共享实体；支持按 category 和 entity_type 过滤。

    Args:
        auth: 认证上下文。
        session: 数据库会话。
        category: 按类目过滤。
        entity_type: 按实体类型过滤。
        limit: 返回数量上限。

    Returns:
        实体列表。
    """
    entities = await _entity_crud.list(
        session, auth, limit=limit, category=category or None, entity_type=entity_type or None
    )
    return ApiResponse.success(
        [GraphRAGEntityResponse.model_validate(e) for e in entities], message="获取成功"
    )


@router.get(
    "/entities/{entity_id}",
    response_model=ApiResponse[GraphRAGEntityResponse],
    summary="获取实体详情",
)
async def get_entity(
    entity_id: int,
    auth: AuthDep,
    session: SessionDep,
) -> ApiResponse[GraphRAGEntityResponse]:
    """获取实体详情。

    跨租户访问返回 404；共享实体（tenant_id IS NULL）可读。

    Args:
        entity_id: 实体 ID。
        auth: 认证上下文。
        session: 数据库会话。

    Returns:
        实体详情。
    """
    entity = await _entity_crud.get(session, auth, entity_id)
    return ApiResponse.success(GraphRAGEntityResponse.model_validate(entity), message="获取成功")


@router.patch(
    "/entities/{entity_id}",
    response_model=ApiResponse[GraphRAGEntityResponse],
    summary="更新实体",
)
async def update_entity(
    entity_id: int,
    request: GraphRAGEntityUpdate,
    auth: AuthDep,
    session: SessionDep,
) -> ApiResponse[GraphRAGEntityResponse]:
    """更新实体。

    仅本租户的实体可更新。

    Args:
        entity_id: 实体 ID。
        request: 更新请求。
        auth: 认证上下文。
        session: 数据库会话。

    Returns:
        更新后的实体。
    """
    entity = await _entity_crud.update(session, auth, entity_id, request)
    return ApiResponse.success(GraphRAGEntityResponse.model_validate(entity), message="更新成功")


@router.delete(
    "/entities/{entity_id}",
    response_model=ApiResponse[None],
    summary="删除实体",
)
async def delete_entity(
    entity_id: int,
    auth: AuthDep,
    session: SessionDep,
) -> ApiResponse[None]:
    """删除实体。

    仅本租户的实体可删除。

    Args:
        entity_id: 实体 ID。
        auth: 认证上下文。
        session: 数据库会话。

    Returns:
        删除结果。
    """
    await _entity_crud.delete(session, auth, entity_id)
    return ApiResponse.success(message="删除成功")


# ============================================================================
# GraphRAGEdge CRUD
# ============================================================================


@router.post(
    "/edges",
    response_model=ApiResponse[GraphRAGEdgeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建边",
)
async def create_edge(
    request: GraphRAGEdgeCreate,
    auth: AuthDep,
    session: SessionDep,
) -> ApiResponse[GraphRAGEdgeResponse]:
    """创建 Graph RAG 边。

    tenant_id 强制覆盖为 auth.tenant_id。

    Args:
        request: 边创建请求。
        auth: 认证上下文。
        session: 数据库会话。

    Returns:
        创建成功的边。
    """
    edge = await _edge_crud.create(session, auth, request)
    return ApiResponse.success(GraphRAGEdgeResponse.model_validate(edge), message="创建成功")


@router.get(
    "/edges",
    response_model=ApiResponse[list[GraphRAGEdgeResponse]],
    summary="获取边列表",
)
async def list_edges(
    auth: AuthDep,
    session: SessionDep,
    category: str | None = Query(default=None, description="按类目过滤"),
    source_entity_id: int | None = Query(default=None, description="按源实体 ID 过滤"),
    limit: int = 50,
) -> ApiResponse[list[GraphRAGEdgeResponse]]:
    """获取边列表。

    按租户过滤并包含共享边；支持按 category 和 source_entity_id 过滤。

    Args:
        auth: 认证上下文。
        session: 数据库会话。
        category: 按类目过滤。
        source_entity_id: 按源实体 ID 过滤。
        limit: 返回数量上限。

    Returns:
        边列表。
    """
    edges = await _edge_crud.list(
        session,
        auth,
        limit=limit,
        category=category or None,
        source_entity_id=source_entity_id,
    )
    return ApiResponse.success(
        [GraphRAGEdgeResponse.model_validate(e) for e in edges], message="获取成功"
    )


@router.get(
    "/edges/{edge_id}",
    response_model=ApiResponse[GraphRAGEdgeResponse],
    summary="获取边详情",
)
async def get_edge(
    edge_id: int,
    auth: AuthDep,
    session: SessionDep,
) -> ApiResponse[GraphRAGEdgeResponse]:
    """获取边详情。

    跨租户访问返回 404；共享边（tenant_id IS NULL）可读。

    Args:
        edge_id: 边 ID。
        auth: 认证上下文。
        session: 数据库会话。

    Returns:
        边详情。
    """
    edge = await _edge_crud.get(session, auth, edge_id)
    return ApiResponse.success(GraphRAGEdgeResponse.model_validate(edge), message="获取成功")


@router.delete(
    "/edges/{edge_id}",
    response_model=ApiResponse[None],
    summary="删除边",
)
async def delete_edge(
    edge_id: int,
    auth: AuthDep,
    session: SessionDep,
) -> ApiResponse[None]:
    """删除边。

    仅本租户的边可删除。

    Args:
        edge_id: 边 ID。
        auth: 认证上下文。
        session: 数据库会话。

    Returns:
        删除结果。
    """
    await _edge_crud.delete(session, auth, edge_id)
    return ApiResponse.success(message="删除成功")
