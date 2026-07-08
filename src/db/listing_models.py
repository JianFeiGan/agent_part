"""
刊登模块数据库模型。

Description:
    定义刊登工具 7 张表的 ORM 模型，使用 SQLAlchemy 2.0 风格。
    图片统一存 OSS URL，合规报告和推送结果存 JSONB。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.encrypted_json import EncryptedJSONB
from src.db.postgres import Base


class ListingProductPO(Base):
    """刊登商品表。"""

    __tablename__ = "listing_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="租户 ID"
    )
    sku: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(200))
    brand: Mapped[str | None] = mapped_column(String(200))
    price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    weight: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    dimensions: Mapped[dict | None] = mapped_column(JSONB)
    source_images: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    tasks: Mapped[list["ListingTaskPO"]] = relationship(
        "ListingTaskPO",
        back_populates="product",
        primaryjoin=(
            "and_(ListingProductPO.sku == ListingTaskPO.product_sku, "
            "ListingProductPO.tenant_id == ListingTaskPO.tenant_id)"
        ),
        foreign_keys="ListingTaskPO.product_sku",
    )

    __table_args__ = (Index("uq_listing_products_tenant_sku", "tenant_id", "sku", unique=True),)

    def __repr__(self) -> str:
        return f"<ListingProductPO(id={self.id}, sku='{self.sku}')>"


class ListingTaskPO(Base):
    """刊登任务表。"""

    __tablename__ = "listing_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="租户 ID"
    )
    product_sku: Mapped[str] = mapped_column(
        String(100), ForeignKey("listing_products.sku"), nullable=False, index=True,
        comment="关联商品SKU",
    )
    target_platforms: Mapped[list[str]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    workflow_state: Mapped[str | None] = mapped_column(String(50))
    auto_execute: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    product: Mapped["ListingProductPO"] = relationship(
        "ListingProductPO",
        back_populates="tasks",
        primaryjoin="and_(ListingTaskPO.product_sku == ListingProductPO.sku, "
        "ListingTaskPO.tenant_id == ListingProductPO.tenant_id)",
        foreign_keys=[product_sku],
    )
    asset_packages: Mapped[list["AssetPackagePO"]] = relationship(
        "AssetPackagePO", back_populates="task"
    )
    copywriting_packages: Mapped[list["CopywritingPackagePO"]] = relationship(
        "CopywritingPackagePO", back_populates="task"
    )
    compliance_reports: Mapped[list["ComplianceReportPO"]] = relationship(
        "ComplianceReportPO", back_populates="task"
    )
    push_results: Mapped[list["TaskResultPO"]] = relationship("TaskResultPO", back_populates="task")

    def __repr__(self) -> str:
        return f"<ListingTaskPO(id={self.id}, product_sku='{self.product_sku}', status='{self.status}')>"


class AssetPackagePO(Base):
    """素材包表。"""

    __tablename__ = "asset_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="租户 ID"
    )
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("listing_tasks.id"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    main_image: Mapped[str | None] = mapped_column(String(1000))
    variant_images: Mapped[list[str]] = mapped_column(JSONB, default=list)
    video_url: Mapped[str | None] = mapped_column(String(1000))
    a_plus_images: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )

    task: Mapped["ListingTaskPO"] = relationship("ListingTaskPO", back_populates="asset_packages")

    def __repr__(self) -> str:
        return f"<AssetPackagePO(id={self.id}, task_id={self.task_id}, platform='{self.platform}')>"


class CopywritingPackagePO(Base):
    """文案包表。"""

    __tablename__ = "copywriting_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="租户 ID"
    )
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("listing_tasks.id"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en")
    title: Mapped[str] = mapped_column(String(500), default="")
    bullet_points: Mapped[list[str]] = mapped_column(JSONB, default=list)
    description: Mapped[str] = mapped_column(Text, default="")
    search_terms: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )

    task: Mapped["ListingTaskPO"] = relationship(
        "ListingTaskPO", back_populates="copywriting_packages"
    )

    def __repr__(self) -> str:
        return f"<CopywritingPackagePO(id={self.id}, task_id={self.task_id}, platform='{self.platform}')>"


class ComplianceReportPO(Base):
    """合规报告表。"""

    __tablename__ = "compliance_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="租户 ID"
    )
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("listing_tasks.id"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    report_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )

    task: Mapped["ListingTaskPO"] = relationship(
        "ListingTaskPO", back_populates="compliance_reports"
    )

    def __repr__(self) -> str:
        return f"<ComplianceReportPO(id={self.id}, task_id={self.task_id}, platform='{self.platform}')>"


class TaskResultPO(Base):
    """推送结果表。"""

    __tablename__ = "task_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="租户 ID"
    )
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("listing_tasks.id"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    result_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )

    task: Mapped["ListingTaskPO"] = relationship("ListingTaskPO", back_populates="push_results")

    def __repr__(self) -> str:
        return f"<TaskResultPO(id={self.id}, task_id={self.task_id}, platform='{self.platform}')>"


class AdapterConfigPO(Base):
    """适配器配置表。"""

    __tablename__ = "adapter_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="租户 ID"
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    credentials: Mapped[dict] = mapped_column(EncryptedJSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("uq_adapter_config_tenant_platform_shop", "tenant_id", "platform", "shop_id", unique=True),
    )

    def __repr__(self) -> str:
        return (
            f"<AdapterConfigPO(id={self.id}, platform='{self.platform}', shop_id='{self.shop_id}')>"
        )


class GeneratedAssetPO(Base):
    """生成资产表。

    存储所有生成/上传的资产文件（图片、视频、文档等），
    支持多租户、多供应商、去重和状态追踪。

    Attributes:
        id: 主键。
        tenant_id: 租户 ID（非空，索引）。
        product_id: 关联商品 ID（可空，索引）。
        task_id: 生成任务 ID（可空，索引）。
        asset_type: 资产类型 image/video/document（非空，索引）。
        provider: 供应商 mock/wanx/kling/user_upload 等（非空）。
        url: 前端可访问 URL（非空）。
        storage_key: StorageBackend key（非空，索引）。
        storage_backend: 存储后端 local/oss/s3（默认 local）。
        mime_type: MIME 类型（可空）。
        file_size: 文件大小（字节，可空）。
        width: 宽度（像素，可空）。
        height: 高度（像素，可空）。
        duration: 视频时长（秒，可空）。
        sha256: 文件 SHA256 哈希（可空，索引，用于去重）。
        status: 状态 pending/processing/completed/failed（默认 completed）。
        is_mock: 是否 mock 生成（默认 False）。
        extra_data: 额外数据（JSONB，映射 metadata 列，默认空 dict）。
        created_at: 创建时间。
        updated_at: 更新时间。
    """

    __tablename__ = "generated_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="租户 ID"
    )
    product_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True, comment="关联商品 ID"
    )
    task_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True, comment="生成任务 ID"
    )
    asset_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True, comment="资产类型: image/video/document"
    )
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="供应商: mock/wanx/kling/user_upload 等"
    )
    url: Mapped[str] = mapped_column(
        String(2000), nullable=False, comment="前端可访问 URL"
    )
    storage_key: Mapped[str] = mapped_column(
        String(500), nullable=False, index=True, comment="StorageBackend key"
    )
    storage_backend: Mapped[str] = mapped_column(
        String(50), nullable=False, default="local", comment="存储后端: local/oss/s3"
    )
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="文件大小（字节）")
    width: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="宽度（像素）")
    height: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="高度（像素）")
    duration: Mapped[float | None] = mapped_column(
        nullable=True, comment="视频时长（秒）"
    )
    sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="SHA256 哈希，用于去重"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="completed",
        comment="状态: pending/processing/completed/failed"
    )
    is_mock: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否 mock 生成"
    )
    extra_data: Mapped[dict] = mapped_column(
        "metadata", JSONB, default=dict, comment="额外数据"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_generated_assets_tenant_product", "tenant_id", "product_id"),
        Index("ix_generated_assets_tenant_task", "tenant_id", "task_id"),
        Index("ix_generated_assets_tenant_type", "tenant_id", "asset_type"),
        Index("ix_generated_assets_tenant_sha256", "tenant_id", "sha256"),
    )

    def __repr__(self) -> str:
        return (
            f"<GeneratedAssetPO(id={self.id}, asset_type='{self.asset_type}', "
            f"provider='{self.provider}')>"
        )
