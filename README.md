# Outpace

**AI-powered competitive intelligence for teams who can't afford Crayon or Klue.**

Outpace automatically monitors competitors — pricing pages, websites, job postings,
and reviews — detects meaningful changes, and delivers synthesized weekly briefs.
Built for lean B2B teams who need signal, not a $25K/year BI platform.

## Status
🚧 Phase 1 (MVP) — in active development

## How it works
1. **Monitor** — scrapers check competitor sources on a schedule
2. **Detect** — diffing engine compares new snapshots to previous ones
3. **Synthesize** — Gemini API turns raw diffs into structured, actionable briefs
4. **Deliver** — weekly email digest + urgent alerts for high-priority signals (like pricing changes)

## Stack
- **Backend:** FastAPI (Python)
- **Scraping:** Playwright + BeautifulSoup
- **AI:** Gemini API (via LangChain)
- **Database:** Supabase (Postgres)
- **Queue:** Celery + Redis
- **Email:** Resend
- **Frontend:** Next.js

## Local Development
See `docs/ARCHITECTURE.md` for full setup instructions.

## Why this exists
Competitive intelligence tools are priced for enterprise ($15K–$60K/year) and
require a dedicated CI owner to configure and maintain. Most 50–500 person
companies have neither the budget nor the headcount. Outpace delivers 80% of
the value at a fraction of the cost, with zero setup overhead.
