-- ============================================================
-- OUTPACE — Unified Monitoring Source Health
-- ============================================================

CREATE TABLE IF NOT EXISTS monitoring_source_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    competitor_id UUID
        REFERENCES competitors(id)
        ON DELETE CASCADE
        NOT NULL,

    signal_type TEXT NOT NULL
        CHECK (
            signal_type IN (
                'general',
                'pricing',
                'reviews',
                'jobs',
                'news'
            )
        ),

    -- UUID from the provider table when the signal uses one.
    -- General and pricing monitoring are configured directly on
    -- competitors, so their source_id remains null.
    source_id UUID,

    provider TEXT,

    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (
            status IN (
                'pending',
                'healthy',
                'degraded',
                'blocked',
                'unsupported',
                'failed'
            )
        ),

    last_attempt_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,

    last_error_code TEXT,
    last_error_message TEXT,

    consecutive_failures INTEGER NOT NULL DEFAULT 0
        CHECK (consecutive_failures >= 0),

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (competitor_id, signal_type)
);


CREATE INDEX IF NOT EXISTS idx_monitoring_source_health_competitor
    ON monitoring_source_health(competitor_id);


CREATE INDEX IF NOT EXISTS idx_monitoring_source_health_status
    ON monitoring_source_health(status);


ALTER TABLE monitoring_source_health
    ENABLE ROW LEVEL SECURITY;


DROP POLICY IF EXISTS
    "Users can view their monitoring source health"
    ON monitoring_source_health;


CREATE POLICY "Users can view their monitoring source health"
    ON monitoring_source_health
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1
            FROM competitors
            WHERE competitors.id = (
                monitoring_source_health.competitor_id
            )
              AND competitors.user_id = auth.uid()
        )
    );


-- Existing successful snapshots are trustworthy evidence of a
-- healthy source. Future attempts are maintained by the worker.
INSERT INTO monitoring_source_health (
    competitor_id,
    signal_type,
    status,
    last_attempt_at,
    last_success_at,
    consecutive_failures,
    metadata
)
SELECT DISTINCT ON (
    snapshots.competitor_id,
    snapshots.signal_type
)
    snapshots.competitor_id,
    snapshots.signal_type,
    'healthy',
    snapshots.scraped_at,
    snapshots.scraped_at,
    0,
    jsonb_build_object(
        'latest_snapshot_id', snapshots.id
    )
FROM snapshots
WHERE snapshots.signal_type IN (
    'general',
    'pricing',
    'reviews',
    'jobs',
    'news'
)
ORDER BY
    snapshots.competitor_id,
    snapshots.signal_type,
    snapshots.scraped_at DESC
ON CONFLICT (competitor_id, signal_type)
DO NOTHING;
