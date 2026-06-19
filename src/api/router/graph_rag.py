"""
Graph RAG / CategoryMemory CRUD 路由。

Description:
    提供 CategoryMemory、GraphRAGEntity、GraphRAGEdge 的 CRUD 接口。
    支持租户隔离和 scope 权限控制。

    前缀: /api/v1/graph-rag
@author ganjianfei
@version 1.0.0
2026-06-19
"""

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.api.deps import AuthDep
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
from src.auth.context import AuthContext
from src.db.models import CategoryMemory, GraphRAGEdge, GraphRAGEntity
from src.db.postgres import get_db

router = APIRouter()


def _require_scope(auth: AuthContext, *scopes: str) -> None:
    """检查 auth 是否拥有指定 scope 之一，否则 raise 403。

    遍历 scopes，只要任一 scope 满足 auth.has_scope(scope) 即通过。
    若全部不满足，抛出 HTTPException(status_code=403, detail="Forbidden")。

    Args:
        auth: 认证上下文。
        *scopes: 一个或多个 scope 名称。

    Raises:
        HTTPException: 403 当 scope 不足时。
    """
    for scope in scopes:
        if auth.has_scope(scope):
            return
    raise HTTPException(status_code=403, detail="Forbidden")


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
) -> ApiResponse[CategoryMemoryResponse]:
    """创建类目记忆。

    写入时 tenant_id 强制覆盖为 auth.tenant_id，防止伪造。
    若 (tenant_id, category) 重复则返回 409。

    Args:
        request: 类目记忆创建请求。
        auth: 认证上下文。

    Returns:
        创建成功的类目记忆。

    Raises:
        HTTPException: 403 scope 不足、409 重复创建。
    """
    _require_scope(auth, "memory:write")

    async with get_db() as session:
        memory = CategoryMemory(
            tenant_id=auth.tenant_id,
            **request.model_dump(),
        )

        session.add(memory)
        try:
            await session.commit()
            await session.refresh(memory)
        except IntegrityError:
            await session.rollback()
            raise HTTPException(
                status_code=409,
                detail=f"类目记忆已存在: tenant_id={auth.tenant_id}, category={request.category}",
            )

    return ApiResponse(
        code=200,
        message="创建成功",
        data=CategoryMemoryResponse.model_validate(memory),
    )


@router.get(
    "/memories",
    response_model=ApiResponse[list[CategoryMemoryResponse]],
    summary="获取类目记忆列表",
)
async def list_memories(
    auth: AuthDep,
    category: str | None = Query(default=None, description="按类目过滤"),
    include_shared: bool = Query(default=False, description="是否包含共享记忆"),
    limit: int = 50,
) -> ApiResponse[list[CategoryMemoryResponse]]:
    """获取类目记忆列表。

    按租户过滤；include_shared=true 时同时返回 tenant_id IS NULL 的共享记忆。

    Args:
        auth: 认证上下文。
        category: 按类目过滤（可选）。
        include_shared: 是否包含共享记忆。
        limit: 返回数量上限。

    Returns:
        类目记忆列表。
    """
    _require_scope(auth, "memory:read", "memory:write")

    async with get_db() as session:
        stmt = select(CategoryMemory)

        if include_shared:
            stmt = stmt.where(
                (CategoryMemory.tenant_id == auth.tenant_id) | (CategoryMemory.tenant_id.is_(None))
            )
        else:
            stmt = stmt.where(CategoryMemory.tenant_id == auth.tenant_id)

        if category:
            stmt = stmt.where(CategoryMemory.category == category)

        stmt = stmt.order_by(CategoryMemory.updated_at.desc()).limit(limit)

        result = await session.execute(stmt)
        memories = result.scalars().all()

    return ApiResponse(
        code=200,
        message="获取成功",
        data=[CategoryMemoryResponse.model_validate(m) for m in memories],
    )


@router.get(
    "/memories/{memory_id}",
    response_model=ApiResponse[CategoryMemoryResponse],
    summary="获取类目记忆详情",
)
async def get_memory(
    memory_id: int,
    auth: AuthDep,
) -> ApiResponse[CategoryMemoryResponse]:
    """获取类目记忆详情。

    跨租户访问返回 404。

    Args:
        memory_id: 记忆 ID。
        auth: 认证上下文。

    Returns:
        类目记忆详情。

    Raises:
        HTTPException: 403 scope 不足、404 不存在或跨租户。
    """
    _require_scope(auth, "memory:read", "memory:write")

    async with get_db() as session:
        stmt = select(CategoryMemory).where(CategoryMemory.id == memory_id)
        result = await session.execute(stmt)
        memory = result.scalars().first()

        if memory is None:
            raise HTTPException(status_code=404, detail="类目记忆不存在")

        # 跨租户访问返回 404（只有 tenant_id 匹配或全局共享的才可访问）
        if memory.tenant_id is not None and memory.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="类目记忆不存在")

    return ApiResponse(
        code=200,
        message="获取成功",
        data=CategoryMemoryResponse.model_validate(memory),
    )


@router.patch(
    "/memories/{memory_id}",
    response_model=ApiResponse[CategoryMemoryResponse],
    summary="更新类目记忆",
)
async def update_memory(
    memory_id: int,
    request: CategoryMemoryUpdate,
    auth: AuthDep,
) -> ApiResponse[CategoryMemoryResponse]:
    """更新类目记忆。

    仅本租户的记忆可更新；共享记忆（tenant_id IS NULL）不可通过此接口修改。

    Args:
        memory_id: 记忆 ID。
        request: 更新请求。
        auth: 认证上下文。

    Returns:
        更新后的类目记忆。

    Raises:
        HTTPException: 403 scope 不足、404 不存在或跨租户。
    """
    _require_scope(auth, "memory:write")

    async with get_db() as session:
        stmt = select(CategoryMemory).where(CategoryMemory.id == memory_id)
        result = await session.execute(stmt)
        memory = result.scalars().first()

        if memory is None:
            raise HTTPException(status_code=404, detail="类目记忆不存在")

        if memory.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="类目记忆不存在")

        update_data = request.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(memory, key, value)

        try:
            await session.commit()
            await session.refresh(memory)
        except IntegrityError:
            await session.rollback()
            raise HTTPException(
                status_code=409,
                detail=f"类目记忆已存在: tenant_id={auth.tenant_id}, category={memory.category}",
            )

    return ApiResponse(
        code=200,
        message="更新成功",
        data=CategoryMemoryResponse.model_validate(memory),
    )


@router.delete(
    "/memories/{memory_id}",
    response_model=ApiResponse[None],
    summary="删除类目记忆",
)
async def delete_memory(
    memory_id: int,
    auth: AuthDep,
) -> ApiResponse[None]:
    """删除类目记忆。

    仅本租户的记忆可删除。

    Args:
        memory_id: 记忆 ID。
        auth: 认证上下文。

    Returns:
        删除结果。

    Raises:
        HTTPException: 403 scope 不足、404 不存在或跨租户。
    """
    _require_scope(auth, "memory:write")

    async with get_db() as session:
        stmt = select(CategoryMemory).where(CategoryMemory.id == memory_id)
        result = await session.execute(stmt)
        memory = result.scalars().first()

        if memory is None:
            raise HTTPException(status_code=404, detail="类目记忆不存在")

        if memory.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="类目记忆不存在")

        await session.delete(memory)
        await session.commit()

    return ApiResponse(code=200, message="删除成功")


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
) -> ApiResponse[GraphRAGEntityResponse]:
    """创建 Graph RAG 实体。

    tenant_id 强制覆盖为 auth.tenant_id。

    Args:
        request: 实体创建请求。
        auth: 认证上下文。

    Returns:
        创建成功的实体。
    """
    _require_scope(auth, "memory:write")

    async with get_db() as session:
        entity = GraphRAGEntity(
            tenant_id=auth.tenant_id,
            **request.model_dump(),
        )

        session.add(entity)
        await session.commit()
        await session.refresh(entity)

    return ApiResponse(
        code=200,
        message="创建成功",
        data=GraphRAGEntityResponse.model_validate(entity),
    )


@router.get(
    "/entities",
    response_model=ApiResponse[list[GraphRAGEntityResponse]],
    summary="获取实体列表",
)
async def list_entities(
    auth: AuthDep,
    category: str | None = Query(default=None, description="按类目过滤"),
    entity_type: str | None = Query(default=None, description="按实体类型过滤"),
    limit: int = 50,
) -> ApiResponse[list[GraphRAGEntityResponse]]:
    """获取实体列表。

    按租户过滤；支持按 category 和 entity_type 过滤。

    Args:
        auth: 认证上下文。
        category: 按类目过滤。
        entity_type: 按实体类型过滤。
        limit: 返回数量上限。

    Returns:
        实体列表。
    """
    _require_scope(auth, "memory:read", "memory:write")

    async with get_db() as session:
        stmt = select(GraphRAGEntity).where(
            (GraphRAGEntity.tenant_id == auth.tenant_id) | (GraphRAGEntity.tenant_id.is_(None))
        )

        if category:
            stmt = stmt.where(GraphRAGEntity.category == category)

        if entity_type:
            stmt = stmt.where(GraphRAGEntity.entity_type == entity_type)

        stmt = stmt.order_by(GraphRAGEntity.updated_at.desc()).limit(limit)

        result = await session.execute(stmt)
        entities = result.scalars().all()

    return ApiResponse(
        code=200,
        message="获取成功",
        data=[GraphRAGEntityResponse.model_validate(e) for e in entities],
    )


@router.get(
    "/entities/{entity_id}",
    response_model=ApiResponse[GraphRAGEntityResponse],
    summary="获取实体详情",
)
async def get_entity(
    entity_id: int,
    auth: AuthDep,
) -> ApiResponse[GraphRAGEntityResponse]:
    """获取实体详情。

    跨租户访问返回 404。

    Args:
        entity_id: 实体 ID。
        auth: 认证上下文。

    Returns:
        实体详情。

    Raises:
        HTTPException: 403 scope 不足、404 不存在或跨租户。
    """
    _require_scope(auth, "memory:read", "memory:write")

    async with get_db() as session:
        stmt = select(GraphRAGEntity).where(GraphRAGEntity.id == entity_id)
        result = await session.execute(stmt)
        entity = result.scalars().first()

        if entity is None:
            raise HTTPException(status_code=404, detail="实体不存在")

        if entity.tenant_id is not None and entity.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="实体不存在")

    return ApiResponse(
        code=200,
        message="获取成功",
        data=GraphRAGEntityResponse.model_validate(entity),
    )


@router.patch(
    "/entities/{entity_id}",
    response_model=ApiResponse[GraphRAGEntityResponse],
    summary="更新实体",
)
async def update_entity(
    entity_id: int,
    request: GraphRAGEntityUpdate,
    auth: AuthDep,
) -> ApiResponse[GraphRAGEntityResponse]:
    """更新实体。

    仅本租户的实体可更新。

    Args:
        entity_id: 实体 ID。
        request: 更新请求。
        auth: 认证上下文。

    Returns:
        更新后的实体。

    Raises:
        HTTPException: 403 scope 不足、404 不存在或跨租户。
    """
    _require_scope(auth, "memory:write")

    async with get_db() as session:
        stmt = select(GraphRAGEntity).where(GraphRAGEntity.id == entity_id)
        result = await session.execute(stmt)
        entity = result.scalars().first()

        if entity is None:
            raise HTTPException(status_code=404, detail="实体不存在")

        if entity.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="实体不存在")

        update_data = request.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(entity, key, value)

        await session.commit()
        await session.refresh(entity)

    return ApiResponse(
        code=200,
        message="更新成功",
        data=GraphRAGEntityResponse.model_validate(entity),
    )


@router.delete(
    "/entities/{entity_id}",
    response_model=ApiResponse[None],
    summary="删除实体",
)
async def delete_entity(
    entity_id: int,
    auth: AuthDep,
) -> ApiResponse[None]:
    """删除实体。

    仅本租户的实体可删除。

    Args:
        entity_id: 实体 ID。
        auth: 认证上下文。

    Returns:
        删除结果。

    Raises:
        HTTPException: 403 scope 不足、404 不存在或跨租户。
    """
    _require_scope(auth, "memory:write")

    async with get_db() as session:
        stmt = select(GraphRAGEntity).where(GraphRAGEntity.id == entity_id)
        result = await session.execute(stmt)
        entity = result.scalars().first()

        if entity is None:
            raise HTTPException(status_code=404, detail="实体不存在")

        if entity.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="实体不存在")

        await session.delete(entity)
        await session.commit()

    return ApiResponse(code=200, message="删除成功")


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
) -> ApiResponse[GraphRAGEdgeResponse]:
    """创建 Graph RAG 边。

    tenant_id 强制覆盖为 auth.tenant_id。

    Args:
        request: 边创建请求。
        auth: 认证上下文。

    Returns:
        创建成功的边。
    """
    _require_scope(auth, "memory:write")

    async with get_db() as session:
        edge = GraphRAGEdge(
            tenant_id=auth.tenant_id,
            **request.model_dump(),
        )

        session.add(edge)
        await session.commit()
        await session.refresh(edge)

    return ApiResponse(
        code=200,
        message="创建成功",
        data=GraphRAGEdgeResponse.model_validate(edge),
    )


@router.get(
    "/edges",
    response_model=ApiResponse[list[GraphRAGEdgeResponse]],
    summary="获取边列表",
)
async def list_edges(
    auth: AuthDep,
    category: str | None = Query(default=None, description="按类目过滤"),
    source_entity_id: int | None = Query(default=None, description="按源实体 ID 过滤"),
    limit: int = 50,
) -> ApiResponse[list[GraphRAGEdgeResponse]]:
    """获取边列表。

    按租户过滤；支持按 category 和 source_entity_id 过滤。

    Args:
        auth: 认证上下文。
        category: 按类目过滤。
        source_entity_id: 按源实体 ID 过滤。
        limit: 返回数量上限。

    Returns:
        边列表。
    """
    _require_scope(auth, "memory:read", "memory:write")

    async with get_db() as session:
        stmt = select(GraphRAGEdge).where(
            (GraphRAGEdge.tenant_id == auth.tenant_id) | (GraphRAGEdge.tenant_id.is_(None))
        )

        if category:
            stmt = stmt.where(GraphRAGEdge.category == category)

        if source_entity_id is not None:
            stmt = stmt.where(GraphRAGEdge.source_entity_id == source_entity_id)

        stmt = stmt.order_by(GraphRAGEdge.created_at.desc()).limit(limit)

        result = await session.execute(stmt)
        edges = result.scalars().all()

    return ApiResponse(
        code=200,
        message="获取成功",
        data=[GraphRAGEdgeResponse.model_validate(e) for e in edges],
    )


@router.get(
    "/edges/{edge_id}",
    response_model=ApiResponse[GraphRAGEdgeResponse],
    summary="获取边详情",
)
async def get_edge(
    edge_id: int,
    auth: AuthDep,
) -> ApiResponse[GraphRAGEdgeResponse]:
    """获取边详情。

    跨租户访问返回 404。

    Args:
        edge_id: 边 ID。
        auth: 认证上下文。

    Returns:
        边详情。

    Raises:
        HTTPException: 403 scope 不足、404 不存在或跨租户。
    """
    _require_scope(auth, "memory:read", "memory:write")

    async with get_db() as session:
        stmt = select(GraphRAGEdge).where(GraphRAGEdge.id == edge_id)
        result = await session.execute(stmt)
        edge = result.scalars().first()

        if edge is None:
            raise HTTPException(status_code=404, detail="边不存在")

        if edge.tenant_id is not None and edge.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="边不存在")

    return ApiResponse(
        code=200,
        message="获取成功",
        data=GraphRAGEdgeResponse.model_validate(edge),
    )


@router.delete(
    "/edges/{edge_id}",
    response_model=ApiResponse[None],
    summary="删除边",
)
async def delete_edge(
    edge_id: int,
    auth: AuthDep,
) -> ApiResponse[None]:
    """删除边。

    仅本租户的边可删除。

    Args:
        edge_id: 边 ID。
        auth: 认证上下文。

    Returns:
        删除结果。

    Raises:
        HTTPException: 403 scope 不足、404 不存在或跨租户。
    """
    _require_scope(auth, "memory:write")

    async with get_db() as session:
        stmt = select(GraphRAGEdge).where(GraphRAGEdge.id == edge_id)
        result = await session.execute(stmt)
        edge = result.scalars().first()

        if edge is None:
            raise HTTPException(status_code=404, detail="边不存在")

        if edge.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="边不存在")

        await session.delete(edge)
        await session.commit()

    return ApiResponse(code=200, message="删除成功")
