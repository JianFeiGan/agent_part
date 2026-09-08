-- P2-C 记忆提案表迁移脚本
-- Description: 创建 category_memory_proposals 表，存储记忆提炼候选
-- 幂等性：使用 IF NOT EXISTS
-- @author ganjianfei
-- @version 1.0.0
-- 2026-06-19

-- ============================================================================
-- category_memory_proposals 表
-- ============================================================================

CREATE TABLE IF NOT EXISTS category_memory_proposals (
    id                  SERIAL              PRIMARY KEY,
    tenant_id           VARCHAR(100)        NOT NULL,
    category            VARCHAR(100)        NOT NULL,
    summary             TEXT,
    best_practices      JSONB               NOT NULL DEFAULT '[]'::jsonb,
    negative_patterns   JSONB               NOT NULL DEFAULT '[]'::jsonb,
    style_guidelines    JSONB               NOT NULL DEFAULT '{}'::jsonb,
    performance_hints   JSONB               NOT NULL DEFAULT '{}'::jsonb,
    source_type         VARCHAR(50)         NOT NULL,
    source_ref          VARCHAR(200),
    status              VARCHAR(20)         NOT NULL DEFAULT 'pending',
    confidence          DOUBLE PRECISION    NOT NULL DEFAULT 0.5,
    reviewed_by         VARCHAR(100),
    review_reason       TEXT,
    created_at          TIMESTAMP           NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP           NOT NULL DEFAULT NOW(),
    reviewed_at         TIMESTAMP
);

-- ============================================================================
-- 索引
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_proposals_tenant_id
    ON category_memory_proposals (tenant_id);

CREATE INDEX IF NOT EXISTS idx_proposals_category
    ON category_memory_proposals (category);

CREATE INDEX IF NOT EXISTS idx_proposals_status
    ON category_memory_proposals (status);

CREATE INDEX IF NOT EXISTS idx_proposals_tenant_status
    ON category_memory_proposals (tenant_id, status);

CREATE INDEX IF NOT EXISTS idx_proposals_tenant_category_status
    ON category_memory_proposals (tenant_id, category, status);
