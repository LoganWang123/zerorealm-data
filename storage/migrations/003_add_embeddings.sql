-- ============================================================
-- M5: Vector Search (aligned with Execution Architecture §2.6)
-- Run in Supabase SQL Editor after 002_add_knowledge_objects.sql
-- Requires: pgvector extension
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS embeddings (
    id              VARCHAR(32) PRIMARY KEY,
    tenant_id       VARCHAR(32) NOT NULL DEFAULT 'default',
    object_id       VARCHAR(32) NOT NULL,
    object_type     VARCHAR(30) NOT NULL,          -- knowledge_object / signal / document
    chunk_index     INT DEFAULT 0,
    chunk_text      TEXT NOT NULL,
    embedding       vector(1536),
    model           VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_emb_object ON embeddings(object_id);
CREATE INDEX IF NOT EXISTS idx_emb_type ON embeddings(object_type);
CREATE INDEX IF NOT EXISTS idx_emb_vector ON embeddings
    USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100);
