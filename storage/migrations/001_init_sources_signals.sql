-- ============================================================
-- M1: Data Acquisition (aligned with Execution Architecture §2.3)
-- Run in Supabase SQL Editor
-- ============================================================

CREATE TABLE IF NOT EXISTS sources (
    id              VARCHAR(32) PRIMARY KEY,
    tenant_id       VARCHAR(32) NOT NULL DEFAULT 'default',
    name            VARCHAR(200) NOT NULL,
    url             TEXT NOT NULL,
    type            VARCHAR(20) NOT NULL,
    parser          VARCHAR(20) NOT NULL DEFAULT 'rss',
    category        VARCHAR(50),
    industry_role   VARCHAR(50),
    priority        VARCHAR(5) DEFAULT 'P1',
    score           SMALLINT DEFAULT 50,
    interval        VARCHAR(20) DEFAULT 'daily',
    status          VARCHAR(20) DEFAULT 'active',
    health_score    SMALLINT,
    config          JSONB DEFAULT '{}',
    last_crawled_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS signals (
    id              VARCHAR(32) PRIMARY KEY,
    tenant_id       VARCHAR(32) NOT NULL DEFAULT 'default',
    source_id       VARCHAR(32) NOT NULL,
    signal_type     VARCHAR(30) DEFAULT 'news',
    title           TEXT NOT NULL,
    url             TEXT,
    content_html    TEXT,
    content_text    TEXT,
    summary         TEXT,
    author          VARCHAR(200),
    language        VARCHAR(10) DEFAULT 'zh-CN',
    published_at    TIMESTAMPTZ,
    crawled_at      TIMESTAMPTZ DEFAULT NOW(),
    run_id          VARCHAR(32),
    status          VARCHAR(20) DEFAULT 'raw',
    http_status     SMALLINT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signals_source ON signals(source_id);
CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);
CREATE INDEX IF NOT EXISTS idx_signals_published ON signals(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_run ON signals(run_id);
CREATE INDEX IF NOT EXISTS idx_signals_crawled ON signals(crawled_at DESC);
