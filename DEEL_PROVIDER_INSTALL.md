# Install the Deel careers provider

From the Outpace repository root:

```bash
tar -xzf outpace-deel-provider.tar.gz
rm outpace-deel-provider.tar.gz

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
cd ..
```

Run `supabase/migrations/009_add_deel_job_source.sql` in the Supabase SQL
editor before changing an existing source to `deel`.

Repair the existing Deel source:

```bash
python - <<'PY'
from api.utils.supabase_client import get_supabase_client

source_id = "9cc10d27-cf0d-463b-b666-f84778d2a774"
db = get_supabase_client()
result = (
    db.table("job_sources")
    .update(
        {
            "source": "deel",
            "source_url": "https://jobs.deel.com/deel",
            "external_source_id": "deel",
            "metadata": {
                "company_name": "Deel",
                "tenant": "deel",
            },
        }
    )
    .eq("id", source_id)
    .execute()
)

if not result.data:
    raise RuntimeError("Deel source was not updated")

print("Deel source repaired:", result.data[0]["id"])
PY
```

Restart the API and Celery worker, then establish two live snapshots:

```bash
python -m workers.scrapers.jobs \
  --source-id 9cc10d27-cf0d-463b-b666-f84778d2a774

python -m workers.scrapers.jobs \
  --source-id 9cc10d27-cf0d-463b-b666-f84778d2a774

python -m workers.diffing \
  --competitor-id 4f15b7c4-f3a5-44af-bdf2-76ea08a3cb31 \
  --signal-type jobs
```

Expected result: both collections report the same positive job count,
`test_fixture: False`, and diffing reports `has_changes: false`.
