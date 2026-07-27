# Install the Outpace source-discovery milestone

From the Outpace repository root:

```bash
tar -xzf outpace-source-discovery-v2.tar.gz

python -m py_compile \
  workers/source_discovery.py \
  workers/scrapers/jobs.py \
  api/models/schemas.py \
  api/routers/competitors.py

python -m unittest -v \
  tests.test_job_source_discovery \
  tests.test_job_provider_parsers

cd frontend
npm run lint
npm run build
```

Restart the API and Celery worker after installation. Celery Beat does not require a schedule change.

No new Supabase migration is required when migrations `007` and `008` are already installed.

## Manual verification

1. Open **Add competitor**.
2. Complete company details.
3. Enable **Careers source**.
4. Paste the official careers page or hosted job-board URL.
5. Select **Detect source**.
6. Confirm the suggested provider and published-role count.
7. Continue to store the source and establish its first baseline.

The first valid snapshot establishes a baseline and should not create a competitive-change brief by itself.

An indirectly discovered hosted provider with zero published roles is rejected.
For a company-owned careers page such as Deel, discovery should fall back to
the live HTML listing instead of saving an unrelated empty provider board.
