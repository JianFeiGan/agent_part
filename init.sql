-- Agent Part Database Initialization
-- This script runs automatically when the PostgreSQL container starts for the first time

CREATE EXTENSION IF NOT EXISTS vector;

-- Note: Table creation is handled by SQLAlchemy ORM models
-- See src/db/models.py for table definitions
