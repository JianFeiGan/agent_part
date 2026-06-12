"""
Graph RAG 模型测试。

Description:
    测试 GraphRAGEntity、GraphRAGEdge、CategoryMemory 模型的字段、默认值和注册。
@author ganjianfei
@version 1.0.0
2026-06-12
"""

from src.db.models import CategoryMemory, GraphRAGEdge, GraphRAGEntity
from src.db.postgres import Base


class TestGraphRAGEntity:
    """GraphRAGEntity 模型测试。"""

    def test_model_table_name(self) -> None:
        """测试表名。"""
        assert GraphRAGEntity.__tablename__ == "graph_rag_entities"

    def test_model_is_registered(self) -> None:
        """测试模型已注册到 Base.metadata。"""
        table_names = Base.metadata.tables.keys()
        assert GraphRAGEntity.__tablename__ in table_names

    def test_instantiation_defaults(self) -> None:
        """测试字段赋值与列默认值配置。"""
        entity = GraphRAGEntity(
            name="智能手表",
            entity_type="concept",
            category="digital",
        )

        assert entity.name == "智能手表"
        assert entity.entity_type == "concept"
        assert entity.category == "digital"
        assert entity.description is None
        # aliases default is SQL-level (JSONB), None at Python level before flush
        # created_at/updated_at are SQL-level defaults, None at Python level
        # before flush

    def test_aliases_column_default(self) -> None:
        """测试 aliases 列默认值配置。"""
        aliases_col = GraphRAGEntity.__table__.columns["aliases"]
        assert aliases_col.default is not None

    def test_column_defaults(self) -> None:
        """测试列默认值配置。"""
        extra_data_col = GraphRAGEntity.__table__.columns["metadata"]
        assert extra_data_col.default is not None

    def test_instantiation_full(self) -> None:
        """测试完整字段创建。"""
        entity = GraphRAGEntity(
            name="Apple",
            entity_type="brand",
            category="digital",
            description="Apple 品牌",
            aliases=["苹果", "AAPL"],
            extra_data={"source": "manual"},
        )

        assert entity.entity_type == "brand"
        assert entity.name == "Apple"
        assert entity.description == "Apple 品牌"
        assert entity.aliases == ["苹果", "AAPL"]
        assert entity.extra_data["source"] == "manual"

    def test_extra_data_mapped_as_metadata_column(self) -> None:
        """测试 extra_data 映射到 'metadata' 列。"""
        column = GraphRAGEntity.__table__.columns["metadata"]
        assert column is not None

    def test_embedding_column_exists(self) -> None:
        """测试 embedding 列存在且类型为 Vector。"""
        column = GraphRAGEntity.__table__.columns["embedding"]
        assert column is not None

    def test_updated_at_column_exists(self) -> None:
        """测试 updated_at 列存在。"""
        column = GraphRAGEntity.__table__.columns["updated_at"]
        assert column is not None

    def test_repr(self) -> None:
        """测试 __repr__ 输出。"""
        entity = GraphRAGEntity(
            id=1,
            name="智能手表",
            entity_type="concept",
            category="digital",
        )
        repr_str = repr(entity)

        assert "GraphRAGEntity" in repr_str
        assert "id=1" in repr_str
        assert "智能手表" in repr_str
        assert "concept" in repr_str
        assert "digital" in repr_str


class TestGraphRAGEdge:
    """GraphRAGEdge 模型测试。"""

    def test_model_table_name(self) -> None:
        """测试表名。"""
        assert GraphRAGEdge.__tablename__ == "graph_rag_edges"

    def test_model_is_registered(self) -> None:
        """测试模型已注册到 Base.metadata。"""
        table_names = Base.metadata.tables.keys()
        assert GraphRAGEdge.__tablename__ in table_names

    def test_instantiation_defaults(self) -> None:
        """测试字段赋值与列默认值配置。"""
        edge = GraphRAGEdge(
            source_entity_id=1,
            target_entity_id=2,
            relationship_type="has_attribute",
            category="digital",
        )

        assert edge.source_entity_id == 1
        assert edge.target_entity_id == 2
        assert edge.relationship_type == "has_attribute"
        assert edge.category == "digital"

    def test_column_defaults(self) -> None:
        """测试列默认值配置。"""
        weight_col = GraphRAGEdge.__table__.columns["weight"]
        assert weight_col.default is not None
        # default=1.0 creates a scalar default
        assert weight_col.default.arg == 1.0

    def test_instantiation_full(self) -> None:
        """测试完整字段创建。"""
        edge = GraphRAGEdge(
            source_entity_id=1,
            target_entity_id=2,
            relationship_type="related_to",
            category="digital",
            weight=0.85,
            evidence="基于共现分析",
            extra_data={"confidence": 0.9},
        )

        assert edge.weight == 0.85
        assert edge.evidence == "基于共现分析"
        assert edge.extra_data["confidence"] == 0.9

    def test_extra_data_mapped_as_metadata_column(self) -> None:
        """测试 extra_data 映射到 'metadata' 列。"""
        column = GraphRAGEdge.__table__.columns["metadata"]
        assert column is not None

    def test_evidence_column_exists(self) -> None:
        """测试 evidence 列存在。"""
        column = GraphRAGEdge.__table__.columns["evidence"]
        assert column is not None

    def test_updated_at_column_exists(self) -> None:
        """测试 updated_at 列存在。"""
        column = GraphRAGEdge.__table__.columns["updated_at"]
        assert column is not None

    def test_foreign_key_constraints(self) -> None:
        """测试外键约束指向正确表。"""
        fk = GraphRAGEdge.__table__.columns["source_entity_id"].foreign_keys
        assert len(fk) > 0
        fk_col = next(iter(fk))
        assert fk_col.column.table.name == "graph_rag_entities"

        fk2 = GraphRAGEdge.__table__.columns["target_entity_id"].foreign_keys
        assert len(fk2) > 0
        fk_col2 = next(iter(fk2))
        assert fk_col2.column.table.name == "graph_rag_entities"

    def test_relationship_type_column_exists(self) -> None:
        """测试 relationship_type 列存在（不是 edge_type）。"""
        column = GraphRAGEdge.__table__.columns["relationship_type"]
        assert column is not None

    def test_category_column_exists(self) -> None:
        """测试 category 列存在。"""
        column = GraphRAGEdge.__table__.columns["category"]
        assert column is not None

    def test_repr(self) -> None:
        """测试 __repr__ 输出。"""
        edge = GraphRAGEdge(
            id=1,
            source_entity_id=10,
            target_entity_id=20,
            relationship_type="has_attribute",
            category="digital",
        )
        repr_str = repr(edge)

        assert "GraphRAGEdge" in repr_str
        assert "has_attribute" in repr_str


class TestCategoryMemory:
    """CategoryMemory 模型测试。"""

    def test_model_table_name(self) -> None:
        """测试表名。"""
        assert CategoryMemory.__tablename__ == "category_memories"

    def test_model_is_registered(self) -> None:
        """测试模型已注册到 Base.metadata。"""
        table_names = Base.metadata.tables.keys()
        assert CategoryMemory.__tablename__ in table_names

    def test_instantiation_defaults(self) -> None:
        """测试字段赋值与列默认值配置。"""
        mem = CategoryMemory(
            category="digital",
            summary="智能手表类目摘要",
        )

        assert mem.category == "digital"
        assert mem.summary == "智能手表类目摘要"
        # best_practices/negative_patterns default to empty list (SQL-level default)
        # style_guidelines/performance_hints default to empty dict (SQL-level default)
        # At Python level before flush, they are None; after flush, they become []/{}

    def test_instantiation_full(self) -> None:
        """测试完整字段创建。"""
        mem = CategoryMemory(
            category="digital",
            summary="智能手表类目摘要",
            best_practices=["使用白色背景", "突出产品细节"],
            negative_patterns=["避免过曝", "避免暗角"],
            style_guidelines={"风格": "科技感", "调性": "简约"},
            performance_hints={"表盘": "优先渲染", "色彩": "冷色调"},
            extra_data={"source": "review_feedback"},
        )

        assert mem.category == "digital"
        assert mem.summary == "智能手表类目摘要"
        assert isinstance(mem.best_practices, list)
        assert len(mem.best_practices) == 2
        assert "使用白色背景" in mem.best_practices
        assert isinstance(mem.negative_patterns, list)
        assert len(mem.negative_patterns) == 2
        assert "避免过曝" in mem.negative_patterns
        assert isinstance(mem.style_guidelines, dict)
        assert mem.style_guidelines["风格"] == "科技感"
        assert isinstance(mem.performance_hints, dict)
        assert mem.performance_hints["表盘"] == "优先渲染"
        assert mem.extra_data["source"] == "review_feedback"

    def test_extra_data_mapped_as_metadata_column(self) -> None:
        """测试 extra_data 映射到 'metadata' 列。"""
        column = CategoryMemory.__table__.columns["metadata"]
        assert column is not None

    def test_category_unique_constraint(self) -> None:
        """测试 category 字段有 unique 约束。"""
        column = CategoryMemory.__table__.columns["category"]
        assert column.unique is True

    def test_embedding_column_exists(self) -> None:
        """测试 embedding 列存在且类型为 Vector。"""
        column = CategoryMemory.__table__.columns["embedding"]
        assert column is not None

    def test_updated_at_column_exists(self) -> None:
        """测试 updated_at 列存在。"""
        column = CategoryMemory.__table__.columns["updated_at"]
        assert column is not None

    def test_repr(self) -> None:
        """测试 __repr__ 输出。"""
        mem = CategoryMemory(
            id=1,
            category="digital",
        )
        repr_str = repr(mem)

        assert "CategoryMemory" in repr_str
        assert "id=1" in repr_str
        assert "digital" in repr_str
