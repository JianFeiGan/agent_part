"""GraphRAG 数据模型测试。"""

import pytest
from datetime import datetime
from src.knowledge.models import (
    KnowledgeGraph,
    GraphEntity,
    GraphRelation,
    Community,
    GraphSummary,
    GraphRAGState,
)


class TestKnowledgeGraph:
    """知识图谱模型测试。"""

    def test_create_knowledge_graph(self):
        """测试创建知识图谱。"""
        graph = KnowledgeGraph(
            id="kg_001",
            name="产品知识库",
            tenant_id="tenant_001",
            status="active",
            document_count=10,
            entity_count=50,
            relation_count=30,
        )
        assert graph.id == "kg_001"
        assert graph.name == "产品知识库"
        assert graph.status == "active"

    def test_knowledge_graph_defaults(self):
        """测试知识图谱默认值。"""
        graph = KnowledgeGraph(
            id="kg_002",
            name="测试图谱",
            tenant_id="tenant_001",
        )
        assert graph.status == "draft"
        assert graph.document_count == 0
        assert graph.entity_count == 0


class TestGraphEntity:
    """图谱实体模型测试。"""

    def test_create_graph_entity(self):
        """测试创建图谱实体。"""
        entity = GraphEntity(
            id="ent_001",
            graph_id="kg_001",
            type="产品",
            name="智能手表",
            properties={"brand": "品牌A", "price": "999"},
            embedding=[0.1] * 1024,
        )
        assert entity.id == "ent_001"
        assert entity.type == "产品"
        assert entity.properties["brand"] == "品牌A"


class TestGraphRelation:
    """图谱关系模型测试。"""

    def test_create_graph_relation(self):
        """测试创建图谱关系。"""
        relation = GraphRelation(
            id="rel_001",
            graph_id="kg_001",
            source_id="ent_001",
            target_id="ent_002",
            type="属于",
            properties={"confidence": 0.95},
        )
        assert relation.id == "rel_001"
        assert relation.type == "属于"
        assert relation.source_id == "ent_001"


class TestCommunity:
    """社区模型测试。"""

    def test_create_community(self):
        """测试创建社区。"""
        community = Community(
            id="comm_001",
            graph_id="kg_001",
            entity_ids=["ent_001", "ent_002", "ent_003"],
            summary="智能穿戴设备相关实体",
            level=0,
        )
        assert community.id == "comm_001"
        assert len(community.entity_ids) == 3


class TestGraphSummary:
    """图摘要模型测试。"""

    def test_create_graph_summary(self):
        """测试创建图摘要。"""
        summary = GraphSummary(
            id="gs_001",
            graph_id="kg_001",
            community_id="comm_001",
            content="该社区包含智能手表相关的产品实体...",
        )
        assert summary.id == "gs_001"
        assert summary.community_id == "comm_001"


class TestGraphRAGState:
    """GraphRAG 状态模型测试。"""

    def test_create_graph_rag_state(self):
        """测试创建 GraphRAG 状态。"""
        state = GraphRAGState(
            query="智能手表有哪些功能？",
            query_intent="fact",
            entities=["智能手表", "功能"],
            retrieval_strategy="hybrid",
        )
        assert state.query == "智能手表有哪些功能？"
        assert state.query_intent == "fact"
        assert state.retrieval_strategy == "hybrid"

    def test_graph_rag_state_defaults(self):
        """测试 GraphRAG 状态默认值。"""
        state = GraphRAGState(query="测试查询")
        assert state.vector_results == []
        assert state.graph_results == []
        assert state.fused_results == []