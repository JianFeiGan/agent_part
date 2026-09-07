"""知识图谱数据结构测试。

覆盖 src.knowledge.graph.KnowledgeGraph 数据类的真实契约
（src.knowledge 包当前为占位实现）。
"""

from src.knowledge.graph import KnowledgeGraph


class TestKnowledgeGraph:
    """知识图谱数据类测试。"""

    def test_create_knowledge_graph(self):
        """测试创建知识图谱。"""
        graph = KnowledgeGraph(
            id="kg_001",
            name="产品知识库",
            tenant_id="tenant_001",
        )
        assert graph.id == "kg_001"
        assert graph.name == "产品知识库"
        assert graph.tenant_id == "tenant_001"

    def test_knowledge_graph_defaults(self):
        """测试集合字段默认值为空列表。"""
        graph = KnowledgeGraph(
            id="kg_002",
            name="测试图谱",
            tenant_id="tenant_001",
        )
        assert graph.entities == []
        assert graph.relations == []
        # 默认列表是独立实例，互不影响
        graph.entities.append({"id": "ent_001"})
        assert len(graph.entities) == 1
        assert graph.relations == []
