-- ============================================================
-- M3: Knowledge Platform (aligned with Execution Architecture §2.5)
-- Run in Supabase SQL Editor after 001_init_sources_signals.sql
-- ============================================================

CREATE TABLE IF NOT EXISTS knowledge_objects (
    id              VARCHAR(32) PRIMARY KEY,
    tenant_id       VARCHAR(32) NOT NULL DEFAULT 'default',
    entity_type     VARCHAR(30) NOT NULL,
    canonical_name  VARCHAR(500) NOT NULL,
    aliases         JSONB DEFAULT '[]',
    external_ids    JSONB DEFAULT '{}',
    industry_role   VARCHAR(50),
    industry_segment VARCHAR(100),
    lifecycle       VARCHAR(20) DEFAULT 'draft',
    confidence      SMALLINT DEFAULT 50,
    provenance      VARCHAR(30) DEFAULT 'derived',
    mention_count   INT DEFAULT 0,
    source_signals  JSONB DEFAULT '[]',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ko_type ON knowledge_objects(entity_type);
CREATE INDEX IF NOT EXISTS idx_ko_lifecycle ON knowledge_objects(lifecycle);
CREATE INDEX IF NOT EXISTS idx_ko_role ON knowledge_objects(industry_role);
CREATE INDEX IF NOT EXISTS idx_ko_name ON knowledge_objects(canonical_name);

CREATE TABLE IF NOT EXISTS relations (
    id              VARCHAR(32) PRIMARY KEY,
    tenant_id       VARCHAR(32) NOT NULL DEFAULT 'default',
    from_id         VARCHAR(32) NOT NULL REFERENCES knowledge_objects(id),
    to_id           VARCHAR(32) NOT NULL REFERENCES knowledge_objects(id),
    relation_type   VARCHAR(30) NOT NULL,
    confidence      SMALLINT DEFAULT 50,
    provenance      VARCHAR(30) DEFAULT 'derived',
    source_signal   VARCHAR(32),
    metadata        JSONB DEFAULT '{}',
    valid_from      TIMESTAMPTZ,
    valid_to        TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rel_from ON relations(from_id);
CREATE INDEX IF NOT EXISTS idx_rel_to ON relations(to_id);
CREATE INDEX IF NOT EXISTS idx_rel_type ON relations(relation_type);
