"""
RAG 检索增强生成模块。

Description:
    提供知识检索、文档处理、语义分块等 RAG 核心功能。
    支持高级 RAG 管道：Query 改写、混合检索、重排序。
@author ganjianfei
@version 1.0.0
2026-04-05
"""

from src.rag.chunker import SemanticChunker
from src.rag.document_processor import DocumentProcessor
from src.rag.embeddings import EmbeddingService
from src.rag.hybrid_retriever import HybridRetriever
from src.rag.logger import RAGLogger, get_rag_logger
from src.rag.query_rewriter import QueryRewriter
from src.rag.reranker import CrossEncoderReranker
from src.rag.retriever import KnowledgeRetriever

__all__ = [
    "EmbeddingService",
    "DocumentProcessor",
    "SemanticChunker",
    "KnowledgeRetriever",
    "QueryRewriter",
    "CrossEncoderReranker",
    "HybridRetriever",
    "RAGLogger",
    "get_rag_logger",
]
