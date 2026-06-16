-- P1-A Tenant & Auth 迁移脚本
-- Description: 为已有表增加 tenant_id 字段，创建复合索引，数据迁移
-- 幂等性：所有语句使用 IF NOT EXISTS / 检查后执行
-- @author ganjianfei
-- @version 1.0.0
-- 2026-06-16

-- ============================================================================
-- 1. adapter_configs 表：tenant_id 字段 + 复合唯一约束
-- ============================================================================

-- 1a. 如果不存在则添加 tenant_id 列
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'adapter_configs' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE adapter_configs
            ADD COLUMN tenant_id VARCHAR(100) NOT NULL DEFAULT 'legacy';
    END IF;
END $$;

-- 1b. 为 tenant_id 创建索引
CREATE INDEX IF NOT EXISTS ix_adapter_configs_tenant_id
    ON adapter_configs (tenant_id);

-- 1c. 检查旧的 (platform, shop_id) 唯一约束/索引并移除
DO $$
DECLARE
    idx_name text;
BEGIN
    FOR idx_name IN
        SELECT indexname FROM pg_indexes
        WHERE tablename = 'adapter_configs'
          AND indexdef ILIKE '%platform%'
          AND indexdef ILIKE '%shop_id%'
          AND indexdef NOT ILIKE '%tenant_id%'
    LOOP
        EXECUTE format('DROP INDEX IF EXISTS %I', idx_name);
    END LOOP;
END $$;

-- 1d. 创建 (tenant_id, platform, shop_id) 复合唯一索引
CREATE UNIQUE INDEX IF NOT EXISTS uq_adapter_config_tenant_platform_shop
    ON adapter_configs (tenant_id, platform, shop_id);

-- ============================================================================
-- 2. listing_products 表：tenant_id + 复合唯一约束
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'listing_products' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE listing_products
            ADD COLUMN tenant_id VARCHAR(100) NOT NULL DEFAULT 'legacy';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_listing_products_tenant_id
    ON listing_products (tenant_id);

-- 移除旧的 sku 唯一约束（如果有的话）
DO $$
DECLARE
    idx_name text;
BEGIN
    FOR idx_name IN
        SELECT indexname FROM pg_indexes
        WHERE tablename = 'listing_products'
          AND indexname LIKE '%sku%'
          AND indexdef NOT ILIKE '%tenant_id%'
    LOOP
        EXECUTE format('DROP INDEX IF EXISTS %I', idx_name);
    END LOOP;
END $$;

-- 创建 (tenant_id, sku) 复合唯一索引
CREATE UNIQUE INDEX IF NOT EXISTS uq_listing_products_tenant_sku
    ON listing_products (tenant_id, sku);

-- ============================================================================
-- 3. listing_tasks 表：tenant_id 字段
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'listing_tasks' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE listing_tasks
            ADD COLUMN tenant_id VARCHAR(100) NOT NULL DEFAULT 'legacy';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_listing_tasks_tenant_id
    ON listing_tasks (tenant_id);

-- ============================================================================
-- 4. asset_packages 表：tenant_id 字段
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'asset_packages' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE asset_packages
            ADD COLUMN tenant_id VARCHAR(100) NOT NULL DEFAULT 'legacy';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_asset_packages_tenant_id
    ON asset_packages (tenant_id);

-- ============================================================================
-- 5. copywriting_packages 表：tenant_id 字段
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'copywriting_packages' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE copywriting_packages
            ADD COLUMN tenant_id VARCHAR(100) NOT NULL DEFAULT 'legacy';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_copywriting_packages_tenant_id
    ON copywriting_packages (tenant_id);

-- ============================================================================
-- 6. compliance_reports 表：tenant_id 字段
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'compliance_reports' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE compliance_reports
            ADD COLUMN tenant_id VARCHAR(100) NOT NULL DEFAULT 'legacy';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_compliance_reports_tenant_id
    ON compliance_reports (tenant_id);

-- ============================================================================
-- 7. task_results 表：tenant_id 字段
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'task_results' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE task_results
            ADD COLUMN tenant_id VARCHAR(100) NOT NULL DEFAULT 'legacy';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_task_results_tenant_id
    ON task_results (tenant_id);

-- ============================================================================
-- 8. knowledge_docs 表：tenant_id 字段
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'knowledge_docs' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE knowledge_docs
            ADD COLUMN tenant_id VARCHAR(100) NOT NULL DEFAULT 'legacy';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_knowledge_docs_tenant_id
    ON knowledge_docs (tenant_id);

-- ============================================================================
-- 9. knowledge_chunks 表：tenant_id 字段
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'knowledge_chunks' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE knowledge_chunks
            ADD COLUMN tenant_id VARCHAR(100) NOT NULL DEFAULT 'legacy';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_tenant_id
    ON knowledge_chunks (tenant_id);

-- ============================================================================
-- 10. rag_usage_logs 表：tenant_id 字段
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'rag_usage_logs' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE rag_usage_logs
            ADD COLUMN tenant_id VARCHAR(100) NOT NULL DEFAULT 'legacy';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_rag_usage_logs_tenant_id
    ON rag_usage_logs (tenant_id);

-- ============================================================================
-- 11. products 表：tenant_id 字段
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'products' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE products
            ADD COLUMN tenant_id VARCHAR(100) NOT NULL DEFAULT 'legacy';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_products_tenant_id
    ON products (tenant_id);

-- ============================================================================
-- 12. generation_tasks 表：tenant_id 字段
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'generation_tasks' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE generation_tasks
            ADD COLUMN tenant_id VARCHAR(100) NOT NULL DEFAULT 'legacy';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_generation_tasks_tenant_id
    ON generation_tasks (tenant_id);

-- ============================================================================
-- 13. graph_rag_entities 表：tenant_id 字段 (nullable)
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'graph_rag_entities' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE graph_rag_entities
            ADD COLUMN tenant_id VARCHAR(100) NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_graph_rag_entities_tenant_id
    ON graph_rag_entities (tenant_id);

-- ============================================================================
-- 14. graph_rag_edges 表：tenant_id 字段 (nullable)
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'graph_rag_edges' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE graph_rag_edges
            ADD COLUMN tenant_id VARCHAR(100) NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_graph_rag_edges_tenant_id
    ON graph_rag_edges (tenant_id);

-- ============================================================================
-- 15. category_memories 表：tenant_id 字段 (nullable)
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'category_memories' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE category_memories
            ADD COLUMN tenant_id VARCHAR(100) NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_category_memories_tenant_id
    ON category_memories (tenant_id);
