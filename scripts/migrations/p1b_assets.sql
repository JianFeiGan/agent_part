-- P1-B Generated Assets 迁移脚本
-- Description: 创建 generated_assets 表，用于存储所有生成/上传的资产文件
-- 幂等性：使用 IF NOT EXISTS
-- @author ganjianfei
-- @version 1.0.0
-- 2026-06-19

-- ============================================================================
-- 1. generated_assets 表
-- ============================================================================

CREATE TABLE IF NOT EXISTS generated_assets (
    id              SERIAL              PRIMARY KEY,
    tenant_id       VARCHAR(100)        NOT NULL,
    product_id      VARCHAR(100),
    task_id         VARCHAR(100),
    asset_type      VARCHAR(20)         NOT NULL,
    provider        VARCHAR(50)         NOT NULL,
    url             VARCHAR(2000)       NOT NULL,
    storage_key     VARCHAR(500)        NOT NULL,
    storage_backend VARCHAR(50)         NOT NULL DEFAULT 'local',
    mime_type       VARCHAR(100),
    file_size       INTEGER,
    width           INTEGER,
    height          INTEGER,
    duration        DOUBLE PRECISION,
    sha256          VARCHAR(64),
    status          VARCHAR(20)         NOT NULL DEFAULT 'completed',
    is_mock         BOOLEAN             NOT NULL DEFAULT FALSE,
    metadata        JSONB               NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMP           NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP           NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 2. 单列索引
-- ============================================================================

CREATE INDEX IF NOT EXISTS ix_generated_assets_tenant_id
    ON generated_assets (tenant_id);

CREATE INDEX IF NOT EXISTS ix_generated_assets_product_id
    ON generated_assets (product_id);

CREATE INDEX IF NOT EXISTS ix_generated_assets_task_id
    ON generated_assets (task_id);

CREATE INDEX IF NOT EXISTS ix_generated_assets_asset_type
    ON generated_assets (asset_type);

CREATE INDEX IF NOT EXISTS ix_generated_assets_storage_key
    ON generated_assets (storage_key);

CREATE INDEX IF NOT EXISTS ix_generated_assets_sha256
    ON generated_assets (sha256);

-- ============================================================================
-- 3. 复合索引
-- ============================================================================

-- (tenant_id, product_id) 复合索引 — 按商品查询资产
CREATE INDEX IF NOT EXISTS ix_generated_assets_tenant_product
    ON generated_assets (tenant_id, product_id);

-- (tenant_id, task_id) 复合索引 — 按任务查询资产
CREATE INDEX IF NOT EXISTS ix_generated_assets_tenant_task
    ON generated_assets (tenant_id, task_id);

-- (tenant_id, asset_type) 复合索引 — 按类型查询资产
CREATE INDEX IF NOT EXISTS ix_generated_assets_tenant_type
    ON generated_assets (tenant_id, asset_type);

-- (tenant_id, sha256) 复合索引 — 去重查询
CREATE INDEX IF NOT EXISTS ix_generated_assets_tenant_sha256
    ON generated_assets (tenant_id, sha256);
