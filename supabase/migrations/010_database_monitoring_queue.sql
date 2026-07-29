-- ============================================================
-- OUTPACE — Database-backed monitoring queue
-- ============================================================
-- Celery remains available for local and paid deployments.
-- The free founder deployment stores manual requests here so a
-- scheduled GitHub Actions runner can execute them without Redis.

ALTER TABLE monitoring_tasks
    ADD COLUMN IF NOT EXISTS execution_backend TEXT
        NOT NULL
        DEFAULT 'celery'
        CHECK (
            execution_backend IN (
                'celery',
                'database'
            )
        ),

    ADD COLUMN IF NOT EXISTS state TEXT
        NOT NULL
        DEFAULT 'PENDING'
        CHECK (
            state IN (
                'PENDING',
                'STARTED',
                'SUCCESS',
                'FAILURE'
            )
        ),

    ADD COLUMN IF NOT EXISTS result JSONB,
    ADD COLUMN IF NOT EXISTS error TEXT,
    ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT now();


CREATE INDEX IF NOT EXISTS idx_monitoring_tasks_database_queue
    ON monitoring_tasks (
        execution_backend,
        state,
        created_at ASC
    );


CREATE UNIQUE INDEX IF NOT EXISTS
    idx_monitoring_tasks_one_active_database_target
    ON monitoring_tasks (
        user_id,
        signal_type,
        target_type,
        target_id
    )
    WHERE (
        execution_backend = 'database'
        AND state IN ('PENDING', 'STARTED')
    );
