-- ============================================================
-- OUTPACE — Job Sources
-- ============================================================
-- Stores the public career source used to monitor each competitor.
-- Actual job listings are stored as structured `jobs` snapshots.
-- ============================================================

CREATE TABLE job_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    competitor_id UUID
        REFERENCES competitors(id)
        ON DELETE CASCADE
        NOT NULL,

    source TEXT NOT NULL
        CHECK (
            source IN (
                'github',
                'greenhouse',
                'lever',
                'manual'
            )
        ),

    -- Provider-specific identifier such as:
    -- rows/hiring, a Greenhouse board token, or a Lever company slug.
    external_source_id TEXT,

    source_url TEXT NOT NULL,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    -- Safe provider configuration only. Never store API tokens here.
    -- Example:
    -- {
    --   "owner": "rows",
    --   "repo": "hiring",
    --   "branch": "master",
    --   "readme_path": "README.md"
    -- }
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    last_polled_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (competitor_id, source)
);


CREATE INDEX idx_job_sources_competitor_id
    ON job_sources(competitor_id);


ALTER TABLE job_sources ENABLE ROW LEVEL SECURITY;


CREATE POLICY "Users can view their own job sources"
    ON job_sources
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1
            FROM competitors
            WHERE competitors.id = job_sources.competitor_id
              AND competitors.user_id = auth.uid()
        )
    );


CREATE POLICY "Users can insert their own job sources"
    ON job_sources
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM competitors
            WHERE competitors.id = job_sources.competitor_id
              AND competitors.user_id = auth.uid()
        )
    );


CREATE POLICY "Users can update their own job sources"
    ON job_sources
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1
            FROM competitors
            WHERE competitors.id = job_sources.competitor_id
              AND competitors.user_id = auth.uid()
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM competitors
            WHERE competitors.id = job_sources.competitor_id
              AND competitors.user_id = auth.uid()
        )
    );