-- ============================================================
-- OUTPACE — Authenticated Monitoring Task Ownership
-- ============================================================

CREATE TABLE monitoring_tasks (
    task_id UUID PRIMARY KEY,

    user_id UUID
        REFERENCES auth.users(id)
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

    target_type TEXT NOT NULL
        CHECK (
            target_type IN (
                'competitor',
                'source'
            )
        ),

    -- Polymorphic UUID: competitor ID or source ID depending
    -- on target_type.
    target_id UUID NOT NULL,

    created_at TIMESTAMPTZ
        NOT NULL
        DEFAULT now()
);


CREATE INDEX idx_monitoring_tasks_user_created
    ON monitoring_tasks (
        user_id,
        created_at DESC
    );


ALTER TABLE monitoring_tasks
    ENABLE ROW LEVEL SECURITY;


CREATE POLICY "Users can view their own monitoring tasks"
    ON monitoring_tasks
    FOR SELECT
    USING (
        auth.uid() = user_id
    );


CREATE POLICY "Users can insert their own monitoring tasks"
    ON monitoring_tasks
    FOR INSERT
    WITH CHECK (
        auth.uid() = user_id
    );
