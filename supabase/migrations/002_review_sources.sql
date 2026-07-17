-- ============================================================
-- OUTPACE — Review Sources
-- ============================================================

CREATE TABLE review_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    competitor_id UUID
        REFERENCES competitors(id)
        ON DELETE CASCADE
        NOT NULL,

    source TEXT NOT NULL
        CHECK (source IN ('g2', 'capterra', 'manual')),

    -- G2 product UUID, Capterra product identifier, etc.
    external_product_id TEXT,

    source_url TEXT,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    -- Provider-specific configuration that is safe to store.
    -- Never store API tokens here.
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    last_polled_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (competitor_id, source)
);


CREATE INDEX idx_review_sources_competitor_id
    ON review_sources(competitor_id);


ALTER TABLE review_sources ENABLE ROW LEVEL SECURITY;


CREATE POLICY "Users can view their own review sources"
    ON review_sources
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1
            FROM competitors
            WHERE competitors.id = review_sources.competitor_id
              AND competitors.user_id = auth.uid()
        )
    );


CREATE POLICY "Users can insert their own review sources"
    ON review_sources
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM competitors
            WHERE competitors.id = review_sources.competitor_id
              AND competitors.user_id = auth.uid()
        )
    );


CREATE POLICY "Users can update their own review sources"
    ON review_sources
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1
            FROM competitors
            WHERE competitors.id = review_sources.competitor_id
              AND competitors.user_id = auth.uid()
        )
    );