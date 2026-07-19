-- ============================================================
-- OUTPACE — News and Press Sources
-- ============================================================

-- Add the fifth signal type to snapshots.

ALTER TABLE snapshots
    DROP CONSTRAINT IF EXISTS snapshots_signal_type_check;


ALTER TABLE snapshots
    ADD CONSTRAINT snapshots_signal_type_check
    CHECK (
        signal_type IN (
            'general',
            'pricing',
            'reviews',
            'jobs',
            'news'
        )
    );


-- Add the fifth signal type to briefs.

ALTER TABLE briefs
    DROP CONSTRAINT IF EXISTS briefs_signal_type_check;


ALTER TABLE briefs
    ADD CONSTRAINT briefs_signal_type_check
    CHECK (
        signal_type IN (
            'general',
            'pricing',
            'reviews',
            'jobs',
            'news'
        )
    );


-- Store official news, blog, press, and feed sources.

CREATE TABLE news_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    competitor_id UUID
        REFERENCES competitors(id)
        ON DELETE CASCADE
        NOT NULL,

    source TEXT NOT NULL
        CHECK (
            source IN (
                'html',
                'rss',
                'atom',
                'sitemap',
                'manual'
            )
        ),

    external_source_id TEXT,

    source_url TEXT NOT NULL,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    -- Keywords are stored as a JSON array of strings.
    -- Example: ["pricing", "acquisition", "AI", "partnership"]
    keywords JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (
            jsonb_typeof(keywords) = 'array'
        ),

    -- Safe provider-specific configuration only.
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    last_polled_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (
        competitor_id,
        source,
        source_url
    )
);


CREATE INDEX idx_news_sources_competitor_id
    ON news_sources(competitor_id);


ALTER TABLE news_sources ENABLE ROW LEVEL SECURITY;


CREATE POLICY "Users can view their own news sources"
    ON news_sources
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1
            FROM competitors
            WHERE competitors.id = news_sources.competitor_id
              AND competitors.user_id = auth.uid()
        )
    );


CREATE POLICY "Users can insert their own news sources"
    ON news_sources
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM competitors
            WHERE competitors.id = news_sources.competitor_id
              AND competitors.user_id = auth.uid()
        )
    );


CREATE POLICY "Users can update their own news sources"
    ON news_sources
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1
            FROM competitors
            WHERE competitors.id = news_sources.competitor_id
              AND competitors.user_id = auth.uid()
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM competitors
            WHERE competitors.id = news_sources.competitor_id
              AND competitors.user_id = auth.uid()
        )
    );