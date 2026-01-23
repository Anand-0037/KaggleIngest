-- Migration: Add notebooks JSONB column to competition_cache
-- Added on: 2026-01-23

ALTER TABLE competition_cache ADD COLUMN IF NOT EXISTS notebooks JSONB;

-- Optional: Add a comment for documentation
COMMENT ON COLUMN competition_cache.notebooks IS 'Raw processed notebook data as an array of JSON objects';
