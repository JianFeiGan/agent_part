"""
知识库管理 API 路由。

Description:
    提供知识库文档的上传、查询、删除和检索测试接口。
@author ganjianfei
@version 1.0.0
2026-04-05
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schema.common import Result
from src.db import get_db
from src.db.models import KnowledgeDoc
from src.db.vector_store import VectorStore
from src.rag.document_processor import DocumentProcessor
from src.rag.embeddings import get_embedding_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 请求/响应模型 ====================

from pydantic import BaseModel, Field


class KnowledgeDocumentCreate(BaseModel):
    """创建知识文档请求。"""

    title: str = Field(..., description="文档标题", min_length=1, max_length=255)
    doc_type: str = Field(
        ...,
        description="文档类型: brand_guide, category_knowledge, case_study, compliance_rule",
    )
    category: str | None = Field(default=None, description="商品类目")
    content: str = Field(..., description="文档内容", min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class KnowledgeDocumentResponse(BaseModel):
    """知识文档响应。"""

    id: int
    title: str
    doc_type: str
    category: str | None
    source: str | None
    version: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class KnowledgeDocumentListResponse(BaseModel):
    """知识文档列表响应。"""

    total: int
    documents: list[KnowledgeDocumentResponse]


class SearchRequest(BaseModel):
    """检索测试请求。"""

    query: str = Field(..., description="检索查询", min_length=1)
    doc_type: str | None = Field(default=None, description="文档类型过滤")
    category: str | None = Field(default=None, description="类目过滤")
    top_k: int = Field(default=5, description="返回结果数量", ge=1, le=20)


class SearchResultItem(BaseModel):
    """单个检索结果。"""

    chunk_id: int
    doc_id: int
    content: str
    similarity: float
    doc_title: str
    doc_type: str


class SearchResponse(BaseModel):
    """检索测试响应。"""

    query: str
    results: list[SearchResultItem]
    total: int


class KnowledgeStatsResponse(BaseModel):
    """知识库统计响应。"""

    total_documents: int
    total_chunks: int
    documents_by_type: dict[str, int]


# ==================== API 端点 ====================


@router.post("/documents", response_model=Result[KnowledgeDocumentResponse])
async def create_document(
    request: KnowledgeDocumentCreate,
    session: AsyncSession = Depends(get_db),
) -> Result[KnowledgeDocumentResponse]:
    """创建知识文档。

    Args:
        request: 创建请求。
        session: 数据库会话。

    Returns:
        创建的文档信息。
    """
    # 创建文档记录
    doc = KnowledgeDoc(
        title=request.title,
        doc_type=request.doc_type,
        category=request.category,
        content=request.content,
        metadata=request.metadata,
        source="api_create",
    )
    session.add(doc)
    await session.flush()

    # 处理文档分块和向量化
    processor = DocumentProcessor()
    embedding_service = get_embedding_service()
    vector_store = VectorStore()

    # 分块
    chunks = processor.process(
        processor.parse_content(
            content=request.content,
            title=request.title,
            doc_type=request.doc_type,
            category=request.category,
        )
    )

    # 生成向量
    contents = [chunk["content"] for chunk in chunks]
    embeddings = embedding_service.embed_batch(contents)

    # 存储向量
    await vector_store.add_vectors(session, doc.id, chunks, embeddings)

    await session.commit()
    await session.refresh(doc)

    logger.info(f"Created knowledge document: id={doc.id}, title='{doc.title}'")

    return Result.success(
        KnowledgeDocumentResponse(
            id=doc.id,
            title=doc.title,
            doc_type=doc.doc_type,
            category=doc.category,
            source=doc.source,
            version=doc.version,
            created_at=doc.created_at.isoformat(),
            updated_at=doc.updated_at.isoformat(),
        )
    )


@router.post("/documents/upload", response_model=Result[KnowledgeDocumentResponse])
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Query(..., description="文档类型"),
    category: str | None = Query(default=None, description="商品类目"),
    session: AsyncSession = Depends(get_db),
) -> Result[KnowledgeDocumentResponse]:
    """上传文档文件。

    支持格式: .md, .txt, .json, .pdf, .docx

    Args:
        file: 上传的文件。
        doc_type: 文档类型。
        category: 商品类目。
        session: 数据库会话。

    Returns:
        创建的文档信息。
    """
    # 检查文件格式
    allowed_extensions = {".md", ".txt", ".json", ".pdf", ".docx"}
    file_ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Allowed: {allowed_extensions}",
        )

    # 保存临时文件
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 解析文档
        processor = DocumentProcessor()
        parsed_doc = processor.parse(
            tmp_path,
            doc_type=doc_type,
            category=category,
        )

        # 创建数据库记录
        doc = KnowledgeDoc(
            title=parsed_doc.title,
            doc_type=parsed_doc.doc_type,
            category=parsed_doc.category,
            content=parsed_doc.content,
            metadata=parsed_doc.metadata,
            source=parsed_doc.source,
        )
        session.add(doc)
        await session.flush()

        # 分块和向量化
        chunks = processor.process(parsed_doc)
        if chunks:
            embedding_service = get_embedding_service()
            vector_store = VectorStore()

            contents = [chunk["content"] for chunk in chunks]
            embeddings = embedding_service.embed_batch(contents)
            await vector_store.add_vectors(session, doc.id, chunks, embeddings)

        await session.commit()
        await session.refresh(doc)

        logger.info(f"Uploaded knowledge document: id={doc.id}, file='{file.filename}'")

        return Result.success(
            KnowledgeDocumentResponse(
                id=doc.id,
                title=doc.title,
                doc_type=doc.doc_type,
                category=doc.category,
                source=doc.source,
                version=doc.version,
                created_at=doc.created_at.isoformat(),
                updated_at=doc.updated_at.isoformat(),
            )
        )

    finally:
        # 清理临时文件
        import os

        os.unlink(tmp_path)


@router.get("/documents", response_model=Result[KnowledgeDocumentListResponse])
async def list_documents(
    doc_type: str | None = Query(default=None, description="文档类型过滤"),
    category: str | None = Query(default=None, description="类目过滤"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    session: AsyncSession = Depends(get_db),
) -> Result[KnowledgeDocumentListResponse]:
    """获取知识文档列表。

    Args:
        doc_type: 文档类型过滤。
        category: 类目过滤。
        page: 页码。
        page_size: 每页数量。
        session: 数据库会话。

    Returns:
        文档列表。
    """
    from sqlalchemy import func, select

    # 构建查询
    query = select(KnowledgeDoc)

    if doc_type:
        query = query.where(KnowledgeDoc.doc_type == doc_type)
    if category:
        query = query.where(KnowledgeDoc.category == category)

    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    query = query.order_by(KnowledgeDoc.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await session.execute(query)
    docs = result.scalars().all()

    return Result.success(
        KnowledgeDocumentListResponse(
            total=total,
            documents=[
                KnowledgeDocumentResponse(
                    id=doc.id,
                    title=doc.title,
                    doc_type=doc.doc_type,
                    category=doc.category,
                    source=doc.source,
                    version=doc.version,
                    created_at=doc.created_at.isoformat(),
                    updated_at=doc.updated_at.isoformat(),
                )
                for doc in docs
            ],
        )
    )


@router.delete("/documents/{doc_id}", response_model=Result[dict])
async def delete_document(
    doc_id: int,
    session: AsyncSession = Depends(get_db),
) -> Result[dict]:
    """删除知识文档。

    同时删除关联的分块和向量。

    Args:
        doc_id: 文档 ID。
        session: 数据库会话。

    Returns:
        删除结果。
    """
    from sqlalchemy import select

    result = await session.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # 删除文档（级联删除分块）
    await session.delete(doc)
    await session.commit()

    logger.info(f"Deleted knowledge document: id={doc_id}")

    return Result.success({"deleted_id": doc_id})


@router.post("/search", response_model=Result[SearchResponse])
async def search_knowledge(
    request: SearchRequest,
    session: AsyncSession = Depends(get_db),
) -> Result[SearchResponse]:
    """检索测试接口。

    测试知识库检索效果。

    Args:
        request: 检索请求。
        session: 数据库会话。

    Returns:
        检索结果。
    """
    from src.rag.retriever import KnowledgeRetriever

    retriever = KnowledgeRetriever()
    result = await retriever.retrieve(
        session,
        query=request.query,
        doc_type=request.doc_type,
        category=request.category,
        top_k=request.top_k,
    )

    return Result.success(
        SearchResponse(
            query=request.query,
            results=[
                SearchResultItem(
                    chunk_id=r.chunk_id,
                    doc_id=r.doc_id,
                    content=r.content[:500] + "..." if len(r.content) > 500 else r.content,
                    similarity=r.similarity,
                    doc_title=r.doc_title,
                    doc_type=r.doc_type,
                )
                for r in result.results
            ],
            total=len(result.results),
        )
    )


@router.get("/stats", response_model=Result[KnowledgeStatsResponse])
async def get_knowledge_stats(
    session: AsyncSession = Depends(get_db),
) -> Result[KnowledgeStatsResponse]:
    """获取知识库统计信息。

    Args:
        session: 数据库会话。

    Returns:
        统计信息。
    """
    vector_store = VectorStore()
    stats = await vector_store.get_stats(session)

    return Result.success(
        KnowledgeStatsResponse(
            total_documents=stats["total_documents"],
            total_chunks=stats["total_chunks"],
            documents_by_type=stats["documents_by_type"],
        )
    )
