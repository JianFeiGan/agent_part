"""文档入库服务（占位实现）。"""

from __future__ import annotations

from typing import Any

from src.knowledge.graph import KnowledgeGraph


class DocumentIngestionService:
    """文档入库服务。

    将文档内容解析、分块、向量化后存入知识图谱。
    当前为占位实现，返回基本结果。
    """

    async def process_document(
        self,
        document: dict[str, Any],
        graph: KnowledgeGraph,
    ) -> dict[str, Any]:
        """处理文档入库。

        Args:
            document: 文档数据（id, title, content, format）。
            graph: 目标知识图谱。

        Returns:
            处理结果。
        """
        return {
            "document_id": document.get("id"),
            "status": "pending",
            "message": "文档入库功能开发中",
        }
