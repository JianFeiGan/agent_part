"""
刊登模块数据库模型。

Description:
    定义刊登工具 7 张表的 ORM 模型，使用 SQLAlchemy 2.0 风格。
    图片统一存 OSS URL，合规报告和推送结果存 JSONB。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

from datetime import datetime, timezone

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

from src.db.postgres import Base


class ListingProductPO(Base):
    """刊登商品表。"""

    __tablename__ = "listing_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
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
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    tasks: Mapped[list["ListingTaskPO"]] = relationship("ListingTaskPO", back_populates="product")

    def __repr__(self) -> str:
        return f"<ListingProductPO(id={self.id}, sku='{self.sku}')>"


class ListingTaskPO(Base):
    """刊登任务表。"""

    __tablename__ = "listing_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_sku: Mapped[str] = mapped_column(
        String(100), ForeignKey("listing_products.sku"), nullable=False, index=True
    )
    target_platforms: Mapped[list[str]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    workflow_state: Mapped[str | None] = mapped_column(String(50))
    auto_execute: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    product: Mapped["ListingProductPO"] = relationship("ListingProductPO", back_populates="tasks")
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
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("listing_tasks.id"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    main_image: Mapped[str | None] = mapped_column(String(1000))
    variant_images: Mapped[list[str]] = mapped_column(JSONB, default=list)
    video_url: Mapped[str | None] = mapped_column(String(1000))
    a_plus_images: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    task: Mapped["ListingTaskPO"] = relationship("ListingTaskPO", back_populates="asset_packages")

    def __repr__(self) -> str:
        return f"<AssetPackagePO(id={self.id}, task_id={self.task_id}, platform='{self.platform}')>"


class CopywritingPackagePO(Base):
    """文案包表。"""

    __tablename__ = "copywriting_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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
        DateTime, default=lambda: datetime.now(timezone.utc)
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
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("listing_tasks.id"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    report_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
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
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("listing_tasks.id"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    result_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    task: Mapped["ListingTaskPO"] = relationship("ListingTaskPO", back_populates="push_results")

    def __repr__(self) -> str:
        return f"<TaskResultPO(id={self.id}, task_id={self.task_id}, platform='{self.platform}')>"


class AdapterConfigPO(Base):
    """适配器配置表。"""

    __tablename__ = "adapter_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    credentials: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (Index("ix_adapter_config_platform_shop", "platform", "shop_id", unique=True),)

    def __repr__(self) -> str:
        return (
            f"<AdapterConfigPO(id={self.id}, platform='{self.platform}', shop_id='{self.shop_id}')>"
        )
