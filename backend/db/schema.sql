-- Job Queue
CREATE TABLE IF NOT EXISTS job_queue (
    id SERIAL PRIMARY KEY,
    job_id TEXT UNIQUE NOT NULL,
    job_type TEXT NOT NULL,
    params JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    result JSONB,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    locked_until TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    attempts INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_job_queue_status_locked ON job_queue (status, locked_until) WHERE status = 'pending';

-- Cache Entries (Generic)
CREATE TABLE IF NOT EXISTS cache_entries (
    cache_key TEXT PRIMARY KEY,
    cache_value JSONB NOT NULL,
    cache_type TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_entries (expires_at);

-- Competitions Registry (Source of Truth)
CREATE TABLE IF NOT EXISTS competitions_registry (
    slug TEXT PRIMARY KEY,
    title TEXT,
    description TEXT,
    dataset_count INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 2, -- 1=High, 2=Medium, 3=Low
    is_active BOOLEAN DEFAULT TRUE,
    deadline TIMESTAMP WITH TIME ZONE,
    last_metadata_refresh TIMESTAMP WITH TIME ZONE,
    last_notebooks_refresh TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Warm Cache Competitions
CREATE TABLE IF NOT EXISTS warm_cache_competitions (
    identifier TEXT PRIMARY KEY,
    metadata JSONB,
    schema JSONB,
    notebook_count INTEGER,
    is_popular BOOLEAN DEFAULT FALSE,

    -- New CDN Columns
    tier TEXT DEFAULT 'warm', -- 'static', 'warm', 'on-demand'
    request_count INTEGER DEFAULT 0,
    refresh_frequency INTERVAL DEFAULT '3 days',

    last_refreshed TIMESTAMPTZ,
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '3 days')
);

CREATE INDEX IF NOT EXISTS idx_registry_priority ON competitions_registry(priority, last_notebooks_refresh);
CREATE INDEX IF NOT EXISTS idx_warm_cache_tier ON warm_cache_competitions(tier, last_refreshed);

-- Warm Cache Notebooks
CREATE TABLE IF NOT EXISTS warm_cache_notebooks (
    id SERIAL PRIMARY KEY,
    competition_id TEXT REFERENCES warm_cache_competitions(identifier) ON DELETE CASCADE,
    notebook_ref TEXT NOT NULL,
    rank INTEGER,
    metadata JSONB,
    parsed_content JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notebook_content ON warm_cache_notebooks USING GIN (to_tsvector('english', parsed_content::text));
CREATE INDEX IF NOT EXISTS idx_notebook_comp_rank ON warm_cache_notebooks (competition_id, rank);

-- Additional Performance Indices
CREATE INDEX IF NOT EXISTS idx_cache_type ON cache_entries(cache_type);
CREATE INDEX IF NOT EXISTS idx_cache_type_expires ON cache_entries(cache_type, expires_at);
CREATE INDEX IF NOT EXISTS idx_registry_active_priority ON competitions_registry(is_active, priority, last_notebooks_refresh);
CREATE INDEX IF NOT EXISTS idx_notebook_comp_id ON warm_cache_notebooks(competition_id);
