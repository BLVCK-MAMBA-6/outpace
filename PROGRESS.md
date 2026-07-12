# Outpace — Build Progress

Tracking the full journey from MVP to Phase 3. Check items off as they're done.
Last updated: _update this date each time you edit_

---

## Phase 1 — MVP (Weeks 1–8)
**Goal: one competitor, one working end-to-end pipeline, delivering a useful weekly brief.**

### Foundation
- [x] Repo scaffolded (folder structure, README, .gitignore)
- [ ] Supabase project created
- [ ] Database schema deployed (001_initial_schema.sql run in Supabase)
- [ ] `.env` filled with real Supabase + Gemini keys
- [ ] FastAPI app runs locally (`main.py` boots without errors)
- [ ] Supabase Auth wired up (magic link)

### Signal Type 1 — General Website Monitoring
- [ ] Playwright scraper fetches a competitor homepage
- [ ] Raw HTML snapshot stored in `snapshots` table
- [ ] Diffing logic compares snapshot N vs N-1
- [ ] Claude/Gemini synthesis turns diff into structured brief
- [ ] Brief stored in `briefs` table
- [ ] Manually tested end-to-end on 1 real competitor

### Signal Type 2 — Pricing Page Monitoring
- [ ] Pricing page scraper built
- [ ] Structured extraction (plan name, price, features → JSON)
- [ ] Schema diff logic (catches changes even through redesigns)
- [ ] Pricing-specific synthesis prompt
- [ ] Tested on 1 real competitor's pricing page

### Signal Type 3 — Reviews (G2 / Capterra)
- [ ] Review scraper built
- [ ] New review / rating shift detection
- [ ] Synthesis wired up

### Signal Type 4 — Job Postings
- [ ] Job board scraper built (or API if available)
- [ ] New posting detection
- [ ] Synthesis wired up

### Signal Type 5 — News & Press
- [ ] RSS feed monitoring set up
- [ ] Keyword search wired up
- [ ] Synthesis wired up

### Infrastructure
- [ ] Celery + Redis set up locally
- [ ] Weekly scheduled job (general crawl)
- [ ] 48-hour scheduled job (pricing crawl)
- [ ] Resend email integration
- [ ] Weekly digest email template built
- [ ] Digest successfully sent to yourself (test)

### Frontend / Dashboard
- [ ] Onboarding flow (add competitor, add pricing URL, add keywords)
- [ ] Dashboard showing last 4 weeks of briefs
- [ ] Deployed to Vercel (or still local — note which)

### Billing (can be stubbed/skipped until real users)
- [ ] Stripe test mode integrated
- [ ] Starter/Growth/Scale plans configured

### Beta Prep
- [ ] Error handling + Sentry wired up
- [ ] Tested with 2–3 real competitors, not just 1
- [ ] Onboarded yourself as first user
- [ ] Onboarded 2–3 friendly beta testers
- [ ] Collected first round of feedback

---

## Phase 2 (Weeks 9–20)
**Goal: real-time alerts, sales enablement tools, team accounts.**

- [ ] Slack integration — real-time high-priority alerts
- [ ] LinkedIn monitoring (company posts, exec moves)
- [ ] Battlecard generator (auto-generated per competitor)
- [ ] Pricing comparison tables in battlecards
- [ ] Trend view — historical timeline of competitor activity
- [ ] Multi-user workspace with role-based access
- [ ] Public API access for power users

---

## Phase 3 (Months 6–12)
**Goal: distribution, integrations, scale.**

- [ ] Chrome extension (inline intel while browsing competitor sites)
- [ ] HubSpot CRM integration
- [ ] Salesforce CRM integration
- [ ] Custom signal alerts (keyword/price threshold triggers)
- [ ] Competitor ad monitoring (Google/Facebook ad copy tracking)
- [ ] SEO position tracking per competitor

---

## Milestones (from PRD Section 10)
- [ ] MVP built (Weeks 1–8)
- [ ] Beta launched (Week 9) — 10 beta users
- [ ] Phase 2 complete (Week 20)
- [ ] $25K MRR / 200 customers — raise pre-seed
- [ ] Phase 3 complete (Month 12)

---

## Notes / Decisions Log
_Use this space to jot down decisions as you make them — future you will thank present you._

- Using Gemini API instead of Claude API for synthesis (cost reasons) — [date]
-