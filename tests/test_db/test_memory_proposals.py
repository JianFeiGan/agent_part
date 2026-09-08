"""
CategoryMemoryProposalPO 模型测试。

Description:
    测试模型字段、默认值、表注册和复合索引。
@author ganjianfei
@version 1.0.0
2026-06-19
"""

from src.db.models import CategoryMemoryProposalPO
from src.db.postgres import Base


class TestCategoryMemoryProposalPO:
    """CategoryMemoryProposalPO 模型测试。"""

    def test_model_table_name(self) -> None:
        """测试表名。"""
        assert CategoryMemoryProposalPO.__tablename__ == "category_memory_proposals"

    def test_model_is_registered(self) -> None:
        """测试模型已注册到 Base.metadata。"""
        table_names = Base.metadata.tables.keys()
        assert CategoryMemoryProposalPO.__tablename__ in table_names

    def test_instantiation_defaults(self) -> None:
        """测试字段赋值与列默认值配置。"""
        proposal = CategoryMemoryProposalPO(
            tenant_id="tenant-a",
            category="digital",
            source_type="task_completion",
        )

        assert proposal.tenant_id == "tenant-a"
        assert proposal.category == "digital"
        assert proposal.source_type == "task_completion"
        assert proposal.summary is None
        assert proposal.reviewed_by is None
        assert proposal.review_reason is None
        assert proposal.reviewed_at is None
        # status and confidence are SQL-level defaults; None at Python level before flush
        # source_ref is nullable, defaults to None at Python level

    def test_instantiation_full(self) -> None:
        """测试完整字段创建。"""
        proposal = CategoryMemoryProposalPO(
            tenant_id="tenant-a",
            category="digital",
            summary="测试摘要",
            best_practices=["使用白色背景", "突出产品细节"],
            negative_patterns=["避免过曝", "避免暗角"],
            style_guidelines={"风格": "科技感"},
            performance_hints={"表盘": "优先渲染"},
            source_type="task_completion",
            source_ref="task-001",
            status="pending",
            confidence=0.8,
            reviewed_by=None,
            review_reason=None,
        )

        assert proposal.category == "digital"
        assert proposal.summary == "测试摘要"
        assert isinstance(proposal.best_practices, list)
        assert len(proposal.best_practices) == 2
        assert "使用白色背景" in proposal.best_practices
        assert isinstance(proposal.negative_patterns, list)
        assert len(proposal.negative_patterns) == 2
        assert "避免过曝" in proposal.negative_patterns
        assert isinstance(proposal.style_guidelines, dict)
        assert proposal.style_guidelines["风格"] == "科技感"
        assert isinstance(proposal.performance_hints, dict)
        assert proposal.performance_hints["表盘"] == "优先渲染"
        assert proposal.source_type == "task_completion"
        assert proposal.source_ref == "task-001"
        assert proposal.status == "pending"
        assert proposal.confidence == 0.8

    def test_status_default_is_pending(self) -> None:
        """测试 status 默认值为 pending。"""
        col = CategoryMemoryProposalPO.__table__.columns["status"]
        assert col.default is not None
        assert col.default.arg == "pending"

    def test_confidence_default(self) -> None:
        """测试 confidence 默认值为 0.5。"""
        col = CategoryMemoryProposalPO.__table__.columns["confidence"]
        assert col.default is not None
        assert col.default.arg == 0.5

    def test_tenant_id_not_nullable(self) -> None:
        """测试 tenant_id 不允许 NULL。"""
        col = CategoryMemoryProposalPO.__table__.columns["tenant_id"]
        assert col.nullable is False

    def test_category_not_nullable(self) -> None:
        """测试 category 不允许 NULL。"""
        col = CategoryMemoryProposalPO.__table__.columns["category"]
        assert col.nullable is False

    def test_source_type_not_nullable(self) -> None:
        """测试 source_type 不允许 NULL。"""
        col = CategoryMemoryProposalPO.__table__.columns["source_type"]
        assert col.nullable is False

    def test_composite_index_tenant_status(self) -> None:
        """测试 (tenant_id, status) 复合索引存在。"""
        from sqlalchemy import Index

        indexes = [
            idx for idx in CategoryMemoryProposalPO.__table__.indexes
            if isinstance(idx, Index)
        ]
        found = any(
            {"tenant_id", "status"}.issubset({col.name for col in idx.columns})
            for idx in indexes
        )
        assert found is True

    def test_composite_index_tenant_category_status(self) -> None:
        """测试 (tenant_id, category, status) 复合索引存在。"""
        from sqlalchemy import Index

        indexes = [
            idx for idx in CategoryMemoryProposalPO.__table__.indexes
            if isinstance(idx, Index)
        ]
        found = any(
            {"tenant_id", "category", "status"}.issubset({col.name for col in idx.columns})
            for idx in indexes
        )
        assert found is True

    def test_source_ref_nullable(self) -> None:
        """测试 source_ref 允许 NULL。"""
        col = CategoryMemoryProposalPO.__table__.columns["source_ref"]
        assert col.nullable is True

    def test_reviewed_by_nullable(self) -> None:
        """测试 reviewed_by 允许 NULL。"""
        col = CategoryMemoryProposalPO.__table__.columns["reviewed_by"]
        assert col.nullable is True

    def test_reviewed_at_nullable(self) -> None:
        """测试 reviewed_at 允许 NULL。"""
        col = CategoryMemoryProposalPO.__table__.columns["reviewed_at"]
        assert col.nullable is True

    def test_repr(self) -> None:
        """测试 __repr__ 输出。"""
        proposal = CategoryMemoryProposalPO(
            id=1,
            tenant_id="tenant-a",
            category="digital",
            source_type="task_completion",
        )
        proposal.status = "pending"
        repr_str = repr(proposal)

        assert "CategoryMemoryProposalPO" in repr_str
        assert "id=1" in repr_str
        assert "digital" in repr_str
        assert "pending" in repr_str
