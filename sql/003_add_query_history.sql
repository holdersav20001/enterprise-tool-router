-- Week 4 Commit 27: Permanent query storage with retention
--
-- This migration adds a dedicated table for storing successful SQL queries
-- with configurable retention (default: 30 days).

CREATE TABLE IF NOT EXISTS query_history (
    id SERIAL PRIMARY KEY,
    query_hash VARCHAR(64) NOT NULL UNIQUE,          -- SHA256 of natural language query
    natural_language_query TEXT NOT NULL,            -- Original user query
    generated_sql TEXT NOT NULL,                      -- LLM-generated or validated SQL
    confidence DECIMAL(3, 2) NOT NULL,               -- Planner confidence (0.00-1.00)
    tool VARCHAR(32) NOT NULL DEFAULT 'sql',         -- Tool that generated it
    result_size_bytes INTEGER,                       -- Size of results (for monitoring)
    row_count INTEGER,                                -- Number of rows returned
    execution_time_ms INTEGER,                        -- How long it took to run
    tokens_input INTEGER DEFAULT 0,                  -- LLM cost tracking
    tokens_output INTEGER DEFAULT 0,
    cost_usd DECIMAL(10, 6) DEFAULT 0.0,
    user_id VARCHAR(128),                             -- Who created it
    correlation_id VARCHAR(64),                       -- Link to audit_log
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- Update on reuse
    use_count INTEGER DEFAULT 1,                     -- How many times reused
    expires_at TIMESTAMP NOT NULL                    -- Auto-cleanup date
);

-- Index for fast lookups by query hash
CREATE INDEX IF NOT EXISTS idx_query_history_hash ON query_history(query_hash);

-- Index for retention cleanup
CREATE INDEX IF NOT EXISTS idx_query_history_expires ON query_history(expires_at);

-- Index for analytics
CREATE INDEX IF NOT EXISTS idx_query_history_created ON query_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_query_history_user ON query_history(user_id);

COMMENT ON TABLE query_history IS 'Permanent storage of successful SQL queries (Week 4 Commit 27)';
COMMENT ON COLUMN query_history.query_hash IS 'SHA256 hash of normalized natural language query';
COMMENT ON COLUMN query_history.generated_sql IS 'Final validated SQL that was executed';
COMMENT ON COLUMN query_history.expires_at IS 'Auto-delete after this timestamp (default: created_at + 30 days)';
COMMENT ON COLUMN query_history.use_count IS 'Number of times this query was reused (cache hits)';
