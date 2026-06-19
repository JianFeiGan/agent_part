"""GeneratedAsset 数据模型测试。

TDD: 先写测试，再写实现。
"""

from src.db.listing_models import GeneratedAssetPO
from src.db.postgres import Base


class TestGeneratedAssetPO:
    """测试 GeneratedAssetPO ORM 模型定义。"""

    def test_table_name(self) -> None:
        """验证表名。"""
        assert GeneratedAssetPO.__tablename__ == "generated_assets"

    def test_table_registered_in_metadata(self) -> None:
        """验证表已注册到 SQLAlchemy metadata。"""
        assert "generated_assets" in Base.metadata.tables

    def test_primary_key_is_id(self) -> None:
        """验证主键是 id 字段。"""
        table = Base.metadata.tables["generated_assets"]
        pk_cols = [c.name for c in table.primary_key.columns]
        assert "id" in pk_cols

    # ---- tenant_id ----

    def test_tenant_id_column(self) -> None:
        """验证 tenant_id 非空 String(100) 且有 index。"""
        col = GeneratedAssetPO.__table__.c.tenant_id
        assert not col.nullable
        assert col.type.length == 100
        assert col.index

    def test_tenant_id_required(self) -> None:
        """验证 tenant_id 列非空（DB 级别约束）。"""
        col = GeneratedAssetPO.__table__.c.tenant_id
        assert not col.nullable
        assert col.type.length == 100

    # ---- product_id ----

    def test_product_id_nullable(self) -> None:
        """验证 product_id 可为空且有 index。"""
        col = GeneratedAssetPO.__table__.c.product_id
        assert col.nullable
        assert col.index

    def test_product_id_can_be_none(self) -> None:
        """验证 product_id 可以为 None。"""
        po = GeneratedAssetPO(
            tenant_id="t-1",
            asset_type="image",
            provider="mock",
            url="http://example.com/a.png",
            storage_key="images/a.png",
        )
        assert po.product_id is None

    # ---- task_id ----

    def test_task_id_nullable(self) -> None:
        """验证 task_id 可为空且有 index。"""
        col = GeneratedAssetPO.__table__.c.task_id
        assert col.nullable
        assert col.index

    def test_task_id_can_be_none(self) -> None:
        """验证 task_id 可以为 None。"""
        po = GeneratedAssetPO(
            tenant_id="t-1",
            asset_type="image",
            provider="mock",
            url="http://example.com/a.png",
            storage_key="images/a.png",
        )
        assert po.task_id is None

    # ---- asset_type ----

    def test_asset_type_non_null(self) -> None:
        """验证 asset_type 非空且有 index。"""
        col = GeneratedAssetPO.__table__.c.asset_type
        assert not col.nullable
        assert col.index

    # ---- provider ----

    def test_provider_non_null(self) -> None:
        """验证 provider 非空。"""
        col = GeneratedAssetPO.__table__.c.provider
        assert not col.nullable

    # ---- url ----

    def test_url_non_null(self) -> None:
        """验证 url 非空。"""
        col = GeneratedAssetPO.__table__.c.url
        assert not col.nullable

    # ---- storage_key ----

    def test_storage_key_non_null_and_indexed(self) -> None:
        """验证 storage_key 非空且有 index。"""
        col = GeneratedAssetPO.__table__.c.storage_key
        assert not col.nullable
        assert col.index

    # ---- storage_backend ----

    def test_storage_backend_default_local(self) -> None:
        """验证 storage_backend 默认值为 'local'。"""
        col = GeneratedAssetPO.__table__.c.storage_backend
        assert col.default is not None
        # default is a scalar default; resolve it
        default_val = col.default.arg if col.default else None
        assert default_val == "local"

    # ---- mime_type ----

    def test_mime_type_nullable(self) -> None:
        """验证 mime_type 可为空。"""
        col = GeneratedAssetPO.__table__.c.mime_type
        assert col.nullable

    # ---- file_size ----

    def test_file_size_nullable(self) -> None:
        """验证 file_size 可为空。"""
        col = GeneratedAssetPO.__table__.c.file_size
        assert col.nullable

    # ---- width / height ----

    def test_width_nullable(self) -> None:
        """验证 width 可为空。"""
        col = GeneratedAssetPO.__table__.c.width
        assert col.nullable

    def test_height_nullable(self) -> None:
        """验证 height 可为空。"""
        col = GeneratedAssetPO.__table__.c.height
        assert col.nullable

    # ---- duration ----

    def test_duration_nullable(self) -> None:
        """验证 duration 可为空。"""
        col = GeneratedAssetPO.__table__.c.duration
        assert col.nullable

    # ---- sha256 ----

    def test_sha256_nullable_and_indexed(self) -> None:
        """验证 sha256 可为空且有 index。"""
        col = GeneratedAssetPO.__table__.c.sha256
        assert col.nullable
        assert col.index

    # ---- status ----

    def test_status_default_completed(self) -> None:
        """验证 status 默认值为 'completed'。"""
        col = GeneratedAssetPO.__table__.c.status
        assert col.default is not None
        default_val = col.default.arg if col.default else None
        assert default_val == "completed"

    # ---- is_mock ----

    def test_is_mock_default_false(self) -> None:
        """验证 is_mock 默认值为 False。"""
        col = GeneratedAssetPO.__table__.c.is_mock
        assert col.default is not None
        default_val = col.default.arg if col.default else None
        assert default_val is False

    def test_is_mock_field_type(self) -> None:
        """验证 is_mock 是 Boolean 类型。"""
        col = GeneratedAssetPO.__table__.c.is_mock
        assert str(col.type).upper() in ("BOOLEAN", "BOOL")

    # ---- extra_data (metadata JSONB) ----

    def test_extra_data_maps_to_metadata_column(self) -> None:
        """验证 extra_data 映射到 metadata 列（JSONB）。"""
        col = GeneratedAssetPO.__table__.c.metadata
        assert col is not None
        assert "metadata" in GeneratedAssetPO.__table__.columns
        # Verify the column type is JSONB
        assert str(col.type).upper() in ("JSONB", "JSON")

    def test_extra_data_default_dict(self) -> None:
        """验证 extra_data 列默认值为空 JSON 对象。"""
        col = GeneratedAssetPO.__table__.c.metadata
        assert col.default is not None
        # The default.arg is the callable dict (SQLAlchemy resolves it at insert time)

    # ---- created_at / updated_at ----

    def test_created_at_not_nullable(self) -> None:
        """验证 created_at 非空。"""
        col = GeneratedAssetPO.__table__.c.created_at
        assert not col.nullable

    def test_updated_at_not_nullable(self) -> None:
        """验证 updated_at 非空。"""
        col = GeneratedAssetPO.__table__.c.updated_at
        assert not col.nullable

    # ---- composite indexes ----

    def test_composite_indexes(self) -> None:
        """验证复合索引存在。"""
        table = Base.metadata.tables["generated_assets"]
        index_names = {idx.name for idx in table.indexes}
        expected = {
            "ix_generated_assets_tenant_product",
            "ix_generated_assets_tenant_task",
            "ix_generated_assets_tenant_type",
            "ix_generated_assets_tenant_sha256",
        }
        for name in expected:
            assert name in index_names, f"Missing composite index: {name}"

    # ---- full instance creation ----

    def test_full_instance_creation(self) -> None:
        """测试创建完整实例（所有字段有值）。"""
        po = GeneratedAssetPO(
            tenant_id="tenant-a",
            product_id="prod-001",
            task_id="task-001",
            asset_type="image",
            provider="wanx",
            url="https://cdn.example.com/images/abc.png",
            storage_key="images/abc.png",
            storage_backend="oss",
            mime_type="image/png",
            file_size=102400,
            width=1920,
            height=1080,
            duration=None,
            sha256="abc123def456",
            status="completed",
            is_mock=False,
            extra_data={"generation_params": {"prompt": "test"}},
        )
        assert po.tenant_id == "tenant-a"
        assert po.product_id == "prod-001"
        assert po.task_id == "task-001"
        assert po.asset_type == "image"
        assert po.provider == "wanx"
        assert po.url == "https://cdn.example.com/images/abc.png"
        assert po.storage_key == "images/abc.png"
        assert po.storage_backend == "oss"
        assert po.mime_type == "image/png"
        assert po.file_size == 102400
        assert po.width == 1920
        assert po.height == 1080
        assert po.duration is None
        assert po.sha256 == "abc123def456"
        assert po.status == "completed"
        assert po.is_mock is False
        assert po.extra_data == {"generation_params": {"prompt": "test"}}

    def test_minimal_instance_creation(self) -> None:
        """测试创建最小实例（仅必填字段）。"""
        po = GeneratedAssetPO(
            tenant_id="tenant-a",
            asset_type="video",
            provider="user_upload",
            url="/static/videos/demo.mp4",
            storage_key="videos/demo.mp4",
        )
        assert po.tenant_id == "tenant-a"
        assert po.asset_type == "video"
        assert po.provider == "user_upload"
        assert po.url == "/static/videos/demo.mp4"
        assert po.storage_key == "videos/demo.mp4"
        # DB-level defaults (not populated on Python instance until flush)
        assert po.product_id is None
        assert po.task_id is None
        # Verify columns have DB defaults
        assert GeneratedAssetPO.__table__.c.storage_backend.default is not None
        assert GeneratedAssetPO.__table__.c.status.default is not None
        assert GeneratedAssetPO.__table__.c.is_mock.default is not None

    def test_repr(self) -> None:
        """测试 __repr__ 输出。"""
        po = GeneratedAssetPO(
            id=42,
            tenant_id="t-1",
            asset_type="image",
            provider="mock",
            url="http://x.com/a.png",
            storage_key="k",
        )
        r = repr(po)
        assert "GeneratedAssetPO" in r
        assert "42" in r
