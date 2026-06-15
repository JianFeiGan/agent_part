"""
Tenant 模型字段测试。

Description:
    测试 models.py 和 listing_models.py 中所有模型的 tenant_id 字段，
    以及 tenant 复合唯一约束。
@author ganjianfei
@version 1.0.0
2026-06-15
"""

import pytest

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
    CategoryMemory,
    GenerationTask,
    GraphRAGEdge,
    GraphRAGEntity,
    KnowledgeChunk,
    KnowledgeDoc,
    Product,
    RAGUsageLog,
)
from src.db.postgres import Base

# ---------------------------------------------------------------------------
# Helper: check tenant_id column properties
# ---------------------------------------------------------------------------

def _has_tenant_id(model: type) -> bool:
    return "tenant_id" in model.__table__.columns


def _tenant_id_nullable(model: type) -> bool | None:
    col = model.__table__.columns.get("tenant_id")
    return col.nullable if col is not None else None


def _tenant_id_indexed(model: type) -> bool:
    col = model.__table__.columns.get("tenant_id")
    if col is None:
        return False
    return col.index is True or any(
        col in idx.columns for idx in model.__table__.indexes
    )


# ---------------------------------------------------------------------------
# Core models – non-null tenant_id
# ---------------------------------------------------------------------------

CORE_NON_NULL_MODELS = [
    KnowledgeDoc,
    KnowledgeChunk,
    RAGUsageLog,
    Product,
    GenerationTask,
]


class TestCoreModelTenantId:
    """核心模型 tenant_id 字段测试（non-null）。"""

    @pytest.mark.parametrize("model", CORE_NON_NULL_MODELS)
    def test_has_tenant_id_column(self, model: type) -> None:
        """测试核心模型有 tenant_id 列。"""
        assert _has_tenant_id(model), f"{model.__name__} 缺少 tenant_id 列"

    @pytest.mark.parametrize("model", CORE_NON_NULL_MODELS)
    def test_tenant_id_not_nullable(self, model: type) -> None:
        """测试核心模型 tenant_id 不可为空。"""
        assert _tenant_id_nullable(model) is False, (
            f"{model.__name__}.tenant_id 应为 non-nullable"
        )

    @pytest.mark.parametrize("model", CORE_NON_NULL_MODELS)
    def test_tenant_id_indexed(self, model: type) -> None:
        """测试核心模型 tenant_id 有索引。"""
        assert _tenant_id_indexed(model), f"{model.__name__}.tenant_id 缺少索引"


# ---------------------------------------------------------------------------
# GraphRAG models – nullable tenant_id
# ---------------------------------------------------------------------------

GRAPH_RAG_MODELS = [GraphRAGEntity, GraphRAGEdge, CategoryMemory]


class TestGraphRAGTenantId:
    """GraphRAG 模型 tenant_id 字段测试（nullable）。"""

    @pytest.mark.parametrize("model", GRAPH_RAG_MODELS)
    def test_has_tenant_id_column(self, model: type) -> None:
        """测试 GraphRAG 模型有 tenant_id 列。"""
        assert _has_tenant_id(model), f"{model.__name__} 缺少 tenant_id 列"

    @pytest.mark.parametrize("model", GRAPH_RAG_MODELS)
    def test_tenant_id_nullable(self, model: type) -> None:
        """测试 GraphRAG 模型 tenant_id 可为空。"""
        assert _tenant_id_nullable(model) is True, (
            f"{model.__name__}.tenant_id 应为 nullable"
        )

    @pytest.mark.parametrize("model", GRAPH_RAG_MODELS)
    def test_tenant_id_indexed(self, model: type) -> None:
        """测试 GraphRAG 模型 tenant_id 有索引。"""
        assert _tenant_id_indexed(model), f"{model.__name__}.tenant_id 缺少索引"


# ---------------------------------------------------------------------------
# Listing models – non-null tenant_id
# ---------------------------------------------------------------------------

LISTING_MODELS = [
    ListingProductPO,
    ListingTaskPO,
    AssetPackagePO,
    CopywritingPackagePO,
    ComplianceReportPO,
    TaskResultPO,
    AdapterConfigPO,
]


class TestListingModelTenantId:
    """刊登模型 tenant_id 字段测试（non-null）。"""

    @pytest.mark.parametrize("model", LISTING_MODELS)
    def test_has_tenant_id_column(self, model: type) -> None:
        """测试刊登模型有 tenant_id 列。"""
        assert _has_tenant_id(model), f"{model.__name__} 缺少 tenant_id 列"

    @pytest.mark.parametrize("model", LISTING_MODELS)
    def test_tenant_id_not_nullable(self, model: type) -> None:
        """测试刊登模型 tenant_id 不可为空。"""
        assert _tenant_id_nullable(model) is False, (
            f"{model.__name__}.tenant_id 应为 non-nullable"
        )

    @pytest.mark.parametrize("model", LISTING_MODELS)
    def test_tenant_id_indexed(self, model: type) -> None:
        """测试刊登模型 tenant_id 有索引。"""
        assert _tenant_id_indexed(model), f"{model.__name__}.tenant_id 缺少索引"


# ---------------------------------------------------------------------------
# ListingProductPO – sku no longer globally unique
# ---------------------------------------------------------------------------

class TestListingProductSkuConstraint:
    """ListingProductPO sku 约束测试。"""

    def test_sku_no_longer_globally_unique(self) -> None:
        """测试 sku 不再有全局 unique 约束。"""
        col = ListingProductPO.__table__.columns["sku"]
        assert col.unique is False or col.unique is None, (
            "sku 不应再有 global unique 约束"
        )

    def test_tenant_sku_composite_unique(self) -> None:
        """测试 (tenant_id, sku) 复合唯一约束。"""
        indexes = ListingProductPO.__table__.indexes
        found = False
        for idx in indexes:
            col_names = [c.name for c in idx.columns]
            if col_names == ["tenant_id", "sku"] and idx.unique:
                found = True
                break
        assert found, "缺少 (tenant_id, sku) 复合唯一索引"


# ---------------------------------------------------------------------------
# AdapterConfigPO – tenant composite unique
# ---------------------------------------------------------------------------

class TestAdapterConfigConstraint:
    """AdapterConfigPO 约束测试。"""

    def test_old_constraint_removed(self) -> None:
        """测试旧的 ix_adapter_config_platform_shop 索引已移除。"""
        indexes = AdapterConfigPO.__table__.indexes
        for idx in indexes:
            col_names = [c.name for c in idx.columns]
            # 旧索引名或旧列组合不应再是 unique
            if col_names == ["platform", "shop_id"]:
                assert not idx.unique, (
                    "旧的 (platform, shop_id) unique 索引应已移除"
                )

    def test_tenant_platform_shop_composite_unique(self) -> None:
        """测试 (tenant_id, platform, shop_id) 复合唯一约束。"""
        indexes = AdapterConfigPO.__table__.indexes
        found = False
        for idx in indexes:
            col_names = [c.name for c in idx.columns]
            if col_names == ["tenant_id", "platform", "shop_id"] and idx.unique:
                found = True
                break
        assert found, "缺少 (tenant_id, platform, shop_id) 复合唯一索引"


# ---------------------------------------------------------------------------
# All models registered
# ---------------------------------------------------------------------------

ALL_MODELS = CORE_NON_NULL_MODELS + GRAPH_RAG_MODELS + LISTING_MODELS


class TestAllModelsRegistered:
    """所有模型注册验证。"""

    @pytest.mark.parametrize("model", ALL_MODELS)
    def test_model_registered_in_metadata(self, model: type) -> None:
        """测试所有模型已注册到 Base.metadata。"""
        table_names = Base.metadata.tables.keys()
        assert model.__tablename__ in table_names, (
            f"{model.__name__} 未注册到 Base.metadata"
        )
