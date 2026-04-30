"""
数据库模块。

Description:
    提供 PostgreSQL 数据库连接和模型定义，支持 PGVector 向量存储。
@author ganjianfei
@version 1.0.0
2026-04-05
"""

from src.db.listing_models import (
    AdapterConfigPO,
    AssetPackagePO,
    ComplianceReportPO,
    CopywritingPackagePO,
    ListingProductPO,
    ListingTaskPO,
    TaskResultPO,
)
from src.db.models import (
    GenerationTask,
    KnowledgeChunk,
    KnowledgeDoc,
    Product,
    RAGUsageLog,
)
from src.db.postgres import get_db, init_db
from src.db.repository import BaseRepository
from src.db.vector_store import VectorStore

__all__ = [
    "get_db",
    "init_db",
    "VectorStore",
    "KnowledgeDoc",
    "KnowledgeChunk",
    "RAGUsageLog",
    "Product",
    "GenerationTask",
    # Listing models
    "ListingProductPO",
    "ListingTaskPO",
    "AssetPackagePO",
    "CopywritingPackagePO",
    "ComplianceReportPO",
    "TaskResultPO",
    "AdapterConfigPO",
    "BaseRepository",
]
