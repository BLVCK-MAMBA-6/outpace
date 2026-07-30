# Install the free monitoring reliability fix

This update hardens Outpace's zero-cost production monitoring path without
weakening snapshot safety.

## What changes

- Deel job detail pages that return HTTP 200 without `JobPosting` JSON-LD are
  retried.
- Deel detail collection uses two concurrent requests, pauses between batches,
  and retries only the failed subset sequentially.
- The complete Deel snapshot is still rejected if any detail remains
  unresolved, preventing false job-removal alerts.
- Manual GitHub Actions runs default to `pending`, which drains the
  database-backed queue created by the web app.
- GitHub Actions reports failed sources as readable annotations while retaining
  a failed workflow status for genuine monitoring gaps.
- A task that exceeds the browser's short polling window is shown as queued.
  The existing button becomes **Check status** instead of enqueueing a
  duplicate run.

## Install

From `/workspaces/outpace`, after downloading
`outpace-ci-monitoring-fix.tar.gz`:

```bash
cd /workspaces/outpace || exit 1

tar -xzf outpace-ci-monitoring-fix.tar.gz
rm outpace-ci-monitoring-fix.tar.gz
```

## Verify

```bash
python -m py_compile \
  workers/scrapers/jobs.py \
  scripts/run_scheduled_monitoring.py

python -m unittest -v \
  tests.test_job_provider_parsers \
  tests.test_job_source_discovery

cd frontend || exit 1
npm run lint
npm run build
cd ..

git diff --check
git status --short
```

## Commit and deploy

If every check passes:

```bash
git add \
  .github/workflows/scheduled-monitoring.yml \
  workers/scrapers/jobs.py \
  tests/test_job_provider_parsers.py \
  scripts/run_scheduled_monitoring.py \
  frontend/src/pages/CompetitorDetailPage.tsx \
  CI_MONITORING_FIX_INSTALL.md

git commit -m "Harden free monitoring execution"
git push origin main
```

Render will redeploy the API and frontend from `main`.

In GitHub, open **Actions → Outpace Scheduled Monitoring → Run workflow**.
Leave the scope at its new default, `pending`, to process tasks queued from the
website. A real unresolved provider failure will still make the workflow red;
open the run summary to see the source-specific annotation.
