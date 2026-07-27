-- ============================================================
-- OUTPACE — Add Deel-Hosted Careers Provider
-- ============================================================

ALTER TABLE job_sources
    DROP CONSTRAINT IF EXISTS job_sources_source_check;


ALTER TABLE job_sources
    ADD CONSTRAINT job_sources_source_check
    CHECK (
        source IN (
            'github',
            'greenhouse',
            'lever',
            'html',
            'ashby',
            'deel',
            'manual'
        )
    );
