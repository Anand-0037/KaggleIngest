-- migrations/001_initial_schema.sql

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "pgcrypto"; -- For gen_random_uuid() if uuid-ossp fails or alternative

-- ============================================
-- USERS TABLE (Authentication & Billing)
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    api_key VARCHAR(255) UNIQUE NOT NULL, -- Increased length just in case
    password_hash VARCHAR(255), -- Added for internal signup flow if needed

    -- Kaggle credentials (optional - BYOK model)
    kaggle_username VARCHAR(255),
    kaggle_key_encrypted TEXT,

    -- Subscription tier
    tier VARCHAR(20) DEFAULT 'free' CHECK (tier IN ('free', 'pro', 'enterprise')),
    credits INT DEFAULT 10,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_request_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT valid_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_tier ON users(tier);

-- ============================================
-- COMPETITION CACHE (UNLOGGED for performance)
-- ============================================
CREATE UNLOGGED TABLE IF NOT EXISTS competition_cache (
    slug VARCHAR(255) PRIMARY KEY,

    -- Basic metadata
    title TEXT,
    description TEXT,
    deadline TIMESTAMP WITH TIME ZONE,
    reward VARCHAR(255),
    category VARCHAR(100),

    -- Full Kaggle API response
    metadata JSONB,

    -- TOON serialized content
    toon_content TEXT,  -- Can be large (1-10MB)
    notebook_count INT DEFAULT 0,

    -- Cache status
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT,

    -- Timestamps
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Full-text search vector (auto-generated)
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(description, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(slug, '')), 'C')
    ) STORED
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_competition_status ON competition_cache(status, updated_at);
CREATE INDEX IF NOT EXISTS idx_competition_updated ON competition_cache(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_competition_search ON competition_cache USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_competition_title_trgm ON competition_cache USING GIN(title gin_trgm_ops);

-- ============================================
-- NOTEBOOK CACHE (Ideally needed for deep context, kept from previous iteration if useful)
-- ============================================
CREATE UNLOGGED TABLE IF NOT EXISTS notebook_cache (
    identifier VARCHAR PRIMARY KEY, -- "user/slug"
    title VARCHAR,
    url VARCHAR,
    content JSONB,
    status VARCHAR DEFAULT 'pending',
    cached_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_nb_status ON notebook_cache(status);

-- ============================================
-- REQUEST LOGS (Analytics)
-- ============================================
CREATE TABLE IF NOT EXISTS request_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Request details
    endpoint VARCHAR(255),
    competition_slug VARCHAR(255),

    -- Performance metrics
    response_time_ms INT,
    cache_hit BOOLEAN DEFAULT false,

    -- Timestamp
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for analytics queries
CREATE INDEX IF NOT EXISTS idx_request_logs_user ON request_logs(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_request_logs_timestamp ON request_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_request_logs_slug ON request_logs(competition_slug);

-- ============================================
-- KAGGLE QUOTA TRACKER (Global rate limiting)
-- ============================================
CREATE TABLE IF NOT EXISTS kaggle_quota (
    date DATE PRIMARY KEY,
    used INT DEFAULT 0,
    limit_exceeded_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kaggle_quota_date ON kaggle_quota(date DESC);

-- ============================================
-- FUNCTIONS & TRIGGERS
-- ============================================

-- Auto-update timestamp on competition_cache updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_competition_timestamp ON competition_cache;
CREATE TRIGGER trigger_update_competition_timestamp
BEFORE UPDATE ON competition_cache
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
