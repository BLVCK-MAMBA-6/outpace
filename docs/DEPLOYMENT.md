# Outpace production deployment

Outpace deploys as five Render resources while Supabase remains the
database and authentication provider:

| Resource | Purpose | Recommended plan |
| --- | --- | --- |
| `outpace-web` | Vite/React static frontend | Static site |
| `outpace-api` | FastAPI and authenticated API | Starter |
| `outpace-worker` | Celery scraping, diffing, synthesis, email | Standard |
| `outpace-beat` | Celery recurring schedule | Starter |
| `outpace-queue` | Persistent Celery broker/result backend | Starter Key Value |

The worker receives the larger plan because Chromium/Playwright and large
competitor pages use materially more memory than FastAPI or Celery Beat.
Begin with one worker at concurrency `1`; increase only after observing
memory, task duration, and queue depth.

The Blueprint uses Frankfurt for the API, worker, scheduler, and queue.
Change every `region` value in `render.yaml` before the first deployment if
the production Supabase project is hosted closer to a different Render
region. Render does not allow an existing service's region to be changed.

## 1. Pre-deployment checks

From the repository root:

```bash
python scripts/check_production_config.py
python -m compileall -q api workers
python -m unittest discover -v

cd frontend
npm ci
npm run lint
npm run build
cd ..
```

Run every unapplied SQL migration in `supabase/migrations/` against the
production Supabase project before inviting beta users.

## 2. Create the Render Blueprint

1. Push `Dockerfile`, `.dockerignore`, `render.yaml`, and this document.
2. In Render, choose **New → Blueprint**.
3. Connect the Outpace repository and select `render.yaml`.
4. Confirm the paid plans. Background workers cannot use Render's free plan,
   and a persistent queue should not use an ephemeral free Key Value instance.
5. Enter every secret marked `sync: false`.

Do not put a Supabase service-role key in any `VITE_*` variable. Vite embeds
those variables into public browser assets.

### Frontend variables

| Variable | Value |
| --- | --- |
| `VITE_SUPABASE_URL` | Production Supabase project URL |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Supabase publishable/anon key |
| `VITE_API_URL` | `https://<outpace-api-host>` |

### API variables

| Variable | Value |
| --- | --- |
| `SUPABASE_URL` | Production Supabase project URL |
| `SUPABASE_PUBLISHABLE_KEY` | Supabase publishable/anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend-only service-role key |
| `SUPABASE_AUTH_REDIRECT_URL` | `https://<outpace-web-host>/auth/callback` |
| `FRONTEND_URL` | `https://<outpace-web-host>` |
| `GEMINI_API_KEY` | Production Gemini key |

### Worker variables

The worker needs the Supabase and Gemini values above plus:

| Variable | Value |
| --- | --- |
| `RESEND_API_KEY` | Production Resend key |
| `RESEND_FROM_EMAIL` | Verified sender, such as `Outpace <briefs@example.com>` |
| `DIGEST_TO_EMAIL` | Current MVP digest recipient |
| `DIGEST_USER_ID` | Supabase user UUID for that recipient |
| `MONITORING_EXCLUDED_COMPETITOR_IDS` | Optional comma-separated UUIDs |

`REDIS_URL` and `CELERY_RESULT_BACKEND` are injected automatically from
`outpace-queue` over Render's private network.

## 3. Resolve the public URLs

Render service URLs are assigned during Blueprint creation. After they are
known, verify these three settings and redeploy the affected services:

```text
VITE_API_URL=https://<api-host>
FRONTEND_URL=https://<frontend-host>
SUPABASE_AUTH_REDIRECT_URL=https://<frontend-host>/auth/callback
```

In **Supabase Dashboard → Authentication → URL Configuration**:

- Set **Site URL** to `https://<frontend-host>`.
- Add the exact redirect URL
  `https://<frontend-host>/auth/callback`.
- Keep localhost callback URLs only if local development still needs them.

The frontend Blueprint includes a catch-all rewrite to `/index.html`, so
React Router routes such as `/login`, `/auth/callback`, `/dashboard`, and
`/competitors/:id` work on direct loads.

## 4. Production smoke test

Replace the two hosts below:

```bash
API_URL="https://<api-host>"
WEB_URL="https://<frontend-host>"

curl --fail --show-error "$API_URL/health"
curl --fail --show-error --head "$WEB_URL/"
curl --fail --show-error \
  -X OPTIONS "$API_URL/competitors/" \
  -H "Origin: $WEB_URL" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization,content-type" \
  -D -
```

Expected:

- API health returns `{"status":"healthy"}`.
- Frontend returns `200`.
- CORS response contains `access-control-allow-origin: <WEB_URL>`.

Then test the complete user path:

1. Request a magic link from `/login`.
2. Open the emailed link and confirm `/auth/callback` reaches the dashboard.
3. Add one permitted live competitor.
4. Establish at least one baseline.
5. Run that signal again and confirm a stable source reports no change.
6. Open a real brief from the dashboard or competitor page.
7. Check worker and Beat logs for errors.

## 5. Operational checks

After deployment:

- API: `/health` remains green.
- Worker: all `outpace.*` tasks are registered and the process stays ready.
- Beat: only one Beat instance is running.
- Queue: `noeviction` and `journal-snapshot` remain enabled.
- Source failures: verify `monitoring_source_health` updates after failures
  and recovery.
- Resend: verify the sending domain before sending to beta users.
- Supabase: confirm RLS and Auth redirect settings against the production
  project.

Never scale Celery Beat above one instance. Multiple schedulers would enqueue
duplicate recurring runs.

## 6. Current beta limitation

Weekly digest delivery still uses one environment-mapped
`DIGEST_USER_ID`/`DIGEST_TO_EMAIL`. This is acceptable for the founder's
private production test, but it is a blocker for inviting multiple beta users.
Before a multi-user beta, store per-user digest preferences and make the
weekly task fan out by authenticated user.

## Rollback

Render keeps previous deploys. If a release fails:

1. Roll the affected service back to its last healthy deploy.
2. Do not roll back Supabase destructively.
3. Pause Beat if a scheduler change is producing bad fan-out.
4. Preserve snapshots and source-health records for diagnosis.
