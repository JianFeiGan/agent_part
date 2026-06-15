"""
SQLAlchemy 数据库模型定义。

Description:
    定义知识库文档、分块、RAG 日志、商品、生成任务的数据库模型。
@author ganjianfei
@version 1.0.0
2026-04-05
"""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    TIMESTAMP,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.postgres import Base


class KnowledgeDoc(Base):
    """知识库文档模型。

    存储上传的知识文档及其元数据。

    Attributes:
        id: 主键。
        tenant_id: 租户 ID。
        title: 文档标题。
        doc_type: 文档类型 (brand_guide, category_knowledge, case_study, compliance_rule)。
        category: 商品类目 (可选)。
        source: 来源文件名。
        content: 原始内容。
        extra_data: 额外元数据。
        version: 版本号。
        created_at: 创建时间。
        updated_at: 更新时间。
        chunks: 关联的分块列表。
    """

    __tablename__ = "knowledge_docs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="租户 ID"
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    doc_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="文档类型"
    )
    category: Mapped[str | None] = mapped_column(String(100), index=True, comment="商品类目")
    source: Mapped[str | None] = mapped_column(String(255), comment="来源文件名")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    extra_data: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # 关系
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        "KnowledgeChunk", back_populates="doc", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<KnowledgeDoc(id={self.id}, title='{self.title}', type='{self.doc_type}')>"


class KnowledgeChunk(Base):
    """知识库分块模型。

    存储文档分块及其向量嵌入。

    Attributes:
        id: 主键。
        tenant_id: 租户 ID。
        doc_id: 关联文档 ID。
        chunk_index: 分块索引。
        content: 分块内容。
        embedding: 向量嵌入 (BGE-large-zh 1024维)。
        extra_data: 分块元数据。
        created_at: 创建时间。
        doc: 关联的文档。
    """

    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="租户 ID"
    )
    doc_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_docs.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), comment="BGE-large-zh 向量")
    extra_data: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)

    # 关系
    doc: Mapped["KnowledgeDoc"] = relationship("KnowledgeDoc", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<KnowledgeChunk(id={self.id}, doc_id={self.doc_id}, index={self.chunk_index})>"


class RAGUsageLog(Base):
    """RAG 使用日志模型。

    记录 RAG 检索操作的详细信息。

    Attributes:
        id: 主键。
        tenant_id: 租户 ID。
        task_id: 任务 ID。
        agent_name: Agent 名称。
        query: 检索查询。
        retrieved_chunk_ids: 检索到的分块 ID 列表。
        similarity_scores: 相似度分数列表。
        generated_output: 生成输出。
        created_at: 创建时间。
    """

    __tablename__ = "rag_usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="租户 ID"
    )
    task_id: Mapped[str | None] = mapped_column(String(100), index=True)
    agent_name: Mapped[str | None] = mapped_column(String(50), index=True)
    query: Mapped[str | None] = mapped_column(Text)
    retrieved_chunk_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    similarity_scores: Mapped[list[float] | None] = mapped_column(ARRAY(Float))
    generated_output: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<RAGUsageLog(id={self.id}, agent='{self.agent_name}')>"


class Product(Base):
    """商品信息模型。

    存储商品基本信息。

    Attributes:
        id: 主键。
        tenant_id: 租户 ID。
        product_id: 商品 ID (业务标识)。
        name: 商品名称。
        brand: 品牌。
        category: 商品类目。
        description: 商品描述。
        selling_points: 卖点列表 (JSON)。
        specifications: 规格列表 (JSON)。
        extra_data: 额外元数据。
        created_at: 创建时间。
        updated_at: 更新时间。
    """

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="租户 ID"
    )
    product_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(50), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    selling_points: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    specifications: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    extra_data: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # 关系
    tasks: Mapped[list["GenerationTask"]] = relationship("GenerationTask", back_populates="product")

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name='{self.name}')>"


class GenerationTask(Base):
    """生成任务模型。

    记录视觉生成任务的状态和结果。

    Attributes:
        id: 主键。
        tenant_id: 租户 ID。
        task_id: 任务 ID (业务标识)。
        product_id: 关联商品 ID。
        task_type: 任务类型 (image_only, video_only, image_and_video)。
        status: 任务状态 (pending, running, completed, failed)。
        request_config: 请求配置 (JSON)。
        result: 生成结果 (JSON)。
        quality_score: 质量评分。
        rag_enabled: 是否启用 RAG。
        created_at: 创建时间。
        completed_at: 完成时间。
        product: 关联的商品。
    """

    __tablename__ = "generation_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="租户 ID"
    )
    task_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    product_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("products.id"))
    task_type: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    request_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    quality_score: Mapped[float | None] = mapped_column(Float)
    rag_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)

    # 关系
    product: Mapped["Product | None"] = relationship("Product", back_populates="tasks")

    def __repr__(self) -> str:
        return f"<GenerationTask(id={self.id}, task_id='{self.task_id}', status='{self.status}')>"


class GraphRAGEntity(Base):
    """Graph RAG 实体模型。

    知识图谱中的节点，表示类目下的概念、属性、品牌等实体。

    Attributes:
        id: 主键。
        tenant_id: 租户 ID (可选)。
        name: 实体名称。
        entity_type: 实体类型 (concept, attribute, brand, style, etc.)。
        category: 商品类目。
        description: 实体描述。
        aliases: 实体别名列表 (JSON)。
        extra_data: 额外元数据。
        embedding: 向量嵌入 (BGE-large-zh 1024维)。
        created_at: 创建时间。
        updated_at: 更新时间。
    """

    __tablename__ = "graph_rag_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True, comment="租户 ID"
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="实体名称")
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="实体类型"
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="商品类目")
    description: Mapped[str | None] = mapped_column(Text, comment="实体描述")
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list)
    extra_data: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), comment="BGE-large-zh 向量")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<GraphRAGEntity(id={self.id}, name='{self.name}', "
            f"type='{self.entity_type}', category='{self.category}')>"
        )


class GraphRAGEdge(Base):
    """Graph RAG 边模型。

    知识图谱中的边，表示实体之间的语义关系。

    Attributes:
        id: 主键。
        tenant_id: 租户 ID (可选)。
        source_entity_id: 源实体 ID。
        target_entity_id: 目标实体 ID。
        relationship_type: 关系类型 (related_to, has_attribute, belongs_to, etc.)。
        category: 商品类目。
        weight: 关系权重。
        evidence: 关系依据 (来源文本或推理依据)。
        extra_data: 额外元数据。
        created_at: 创建时间。
        updated_at: 更新时间。
        source_entity: 源实体关系。
        target_entity: 目标实体关系。
    """

    __tablename__ = "graph_rag_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True, comment="租户 ID"
    )
    source_entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("graph_rag_entities.id"), nullable=False, index=True
    )
    target_entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("graph_rag_entities.id"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="关系类型"
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="商品类目")
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    evidence: Mapped[str | None] = mapped_column(Text, comment="关系依据")
    extra_data: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # 关系
    source_entity: Mapped["GraphRAGEntity"] = relationship(
        "GraphRAGEntity", foreign_keys=[source_entity_id]
    )
    target_entity: Mapped["GraphRAGEntity"] = relationship(
        "GraphRAGEntity", foreign_keys=[target_entity_id]
    )

    def __repr__(self) -> str:
        return (
            f"<GraphRAGEdge(id={self.id}, {self.source_entity_id} "
            f"-[{self.relationship_type}]-> {self.target_entity_id})>"
        )


class CategoryMemory(Base):
    """类目记忆模型。

    存储特定类目下的累积知识和经验，使用扁平化字段设计。

    Attributes:
        id: 主键。
        tenant_id: 租户 ID (可选)。
        category: 商品类目 (unique+index)。
        summary: 类目摘要概述。
        best_practices: 最佳实践列表 (JSONB)。
        negative_patterns: 避坑/负面模式列表 (JSONB)。
        style_guidelines: 风格指南字典 (JSONB)。
        performance_hints: 性能/效果提示字典 (JSONB)。
        extra_data: 额外元数据。
        embedding: 向量嵌入 (BGE-large-zh 1024维)。
        created_at: 创建时间。
        updated_at: 更新时间。
    """

    __tablename__ = "category_memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True, comment="租户 ID"
    )
    category: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True, comment="商品类目"
    )
    summary: Mapped[str | None] = mapped_column(Text, comment="类目摘要")
    best_practices: Mapped[list[str]] = mapped_column(JSONB, default=list, comment="最佳实践")
    negative_patterns: Mapped[list[str]] = mapped_column(JSONB, default=list, comment="避坑/负面模式")
    style_guidelines: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, comment="风格指南")
    performance_hints: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, comment="性能提示")
    extra_data: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), comment="BGE-large-zh 向量")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<CategoryMemory(id={self.id}, category='{self.category}')>"
        )
