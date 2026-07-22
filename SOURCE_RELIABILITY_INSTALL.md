# Source reliability installation

1. Extract this archive at the Outpace repository root.
2. Run `supabase/migrations/008_monitoring_source_health.sql` in the
   Supabase SQL Editor.
3. Restart the FastAPI process and Celery worker so both load the new
   health schema and task wrappers.
4. Run one live source check and confirm its row in
   `monitoring_source_health` becomes `healthy`.

The last successful snapshot remains available when a later collection
is blocked, degraded, unsupported, or fails.
