# Outpace — Build Progress

Tracking the full journey from MVP to Phase 3. Check items off as they're done.
Last updated: _18/07/2026_

---

## Phase 1 — MVP (Weeks 1–8)
**Goal: one competitor, one working end-to-end pipeline, delivering a useful weekly brief.**

### Foundation
- [x] Repo scaffolded (folder structure, README, .gitignore)
- [x] Supabase project created
- [x] Database schema deployed (001_initial_schema.sql run in Supabase)
- [x] `.env` filled with real Supabase + Gemini keys
- [x] FastAPI app runs locally (`main.py` boots without errors)
- [ ] Supabase Auth wired up (magic link)

## Known Shortcuts (fix before real users)
- [ ] competitors.py uses a hardcoded PLACEHOLDER_USER_ID — needs real Supabase Auth wired in before multi-user support works

### Signal Type 1 — General Website Monitoring
- [x] Playwright scraper fetches a competitor homepage
- [x] Raw HTML snapshot stored in `snapshots` table
- [x] Diffing logic compares snapshot N vs N-1
- [x] Claude/Gemini synthesis turns diff into structured brief
- [x] Brief stored in `briefs` table
- [x] Manually tested end-to-end on 1 real competitor (Rows, controlled test change)

### Signal Type 2 — Pricing Page Monitoring
- [x] Pricing page scraper built
- [x] Structured extraction (plan name, price, features → JSON)
- [x] Schema diff logic (catches changes even through redesigns)
- [ ] Pricing-specific synthesis prompt
- [ ] Tested on 1 real competitor's pricing page

### Signal Type 3 — Reviews (G2 / Capterra)
- [ ] Live review provider integration (G2 token works, but account currently returns no entitled products)
- [x] Review ingestion adapter tested with clearly labeled synthetic fixture data
- [x] New review / rating shift detection
- [x] Review-specific Gemini synthesis wired up
- [x] Review brief stored in `briefs` table
- [x] Duplicate brief prevention tested
- [x] Controlled end-to-end test completed on Rows fixture data

### Signal Type 4 — Job Postings
- [x] `job_sources` configuration table created
- [x] Public GitHub careers provider built
- [x] Public HTML careers provider built
- [x] Structured job snapshots stored in `snapshots` table
- [x] Zero-opening live baseline tested on Rows
- [x] Active live-job ingestion tested on Hex (26 real openings)
- [x] Stable live job identifiers verified across repeated collections
- [x] Department, location, and remote signals extracted
- [x] New, removed, and updated job detection implemented
- [x] Job-specific Gemini synthesis wired up
- [x] Controlled job brief stored in `briefs` table
- [x] Duplicate brief prevention tested
- [ ] Natural real-world job addition/removal observed

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

This log records architectural decisions, temporary shortcuts, blockers, and the reason behind each choice.

### 12/07/2026 — Temporary hardcoded user identity

**Decision:** Use `PLACEHOLDER_USER_ID` during the initial single-user MVP pipeline.

**Reason:** Authentication was not required to prove that competitor creation, monitoring, synthesis, and brief storage worked end-to-end.

**Follow-up:** Replace the placeholder with the authenticated Supabase user before onboarding real or multiple users.

---

### 15/07/2026 — Gemini selected for synthesis

**Decision:** Use the Gemini API instead of Claude for structured competitive-intelligence synthesis.

**Reason:** Gemini was selected for initial cost control and was available through the existing Google API setup.

**Implementation:** Structured responses are validated with Pydantic before being stored.

---

### 15/07/2026 — Julius AI monitoring deferred

**Decision:** Do not bypass Julius AI's Cloudflare or CAPTCHA protection.

**Reason:** Playwright received a Cloudflare challenge instead of the real homepage. Saving the challenge page would create invalid snapshots and false change alerts.

**Follow-up:**

- Detect blocked pages using indicators such as `Just a moment`, `Verify you are human`, `cf-chl`, and Cloudflare challenge elements.
- Reject challenge pages before snapshot insertion.
- Record the failure reason for monitoring and debugging.
- Revisit Julius AI through a permitted API, RSS feed, sitemap, accessible public page, or explicit scraping permission.

---

### 15/07/2026 — Rows selected as the first test competitor

**Decision:** Use Rows to validate the initial monitoring pipeline.

**Reason:** Its homepage was accessible through Playwright and supplied meaningful content for development.

**Verified result:**

- Competitor ID: `dad6bbe4-6425-4b86-ba91-611a6fe74302`
- First snapshot ID: `8c771ae8-e8a2-4d7e-a98f-24426d43d8ad`
- Page title: `Rows - Your new AI Data Analyst`
- Raw HTML characters: `5,931,165`
- Extracted text characters: `3,613`

---

### 15/07/2026 — General monitoring compares meaningful text

**Decision:** Store both raw HTML and extracted meaningful text, but use normalized text for general website diffing.

**Reason:** Raw HTML contains scripts, generated markup, and other noise that could trigger false changes. Extracted text better represents user-visible competitor messaging.

---

### 15/07/2026 — Controlled fixtures permitted for pipeline testing

**Decision:** Use clearly labeled synthetic snapshot changes when a real competitor has not changed during testing.

**Reason:** An end-to-end pipeline cannot be reliably tested by waiting for an unpredictable real-world website change.

**Rule:** Fixtures must contain labels such as `[OUTPACE INTEGRATION TEST ONLY]` or `[TEST DATA]` and must never be presented as real competitor activity.

---

### 16/07/2026 — Pricing monitoring uses structured plans

**Decision:** Extract pricing pages into structured plan objects and compare those objects instead of comparing page text or HTML.

**Reason:** Structured comparison can detect plan, price, feature, and billing changes while ignoring plan order and webpage redesigns.

**Verified result:** The controlled pricing test detected a newly added plan, generated a pricing-specific Gemini brief, stored it in Supabase, and prevented duplicate brief insertion.

---

### 17/07/2026 — G2 live review ingestion blocked by entitlement

**Decision:** Keep the G2 provider interface, but do not claim the G2 integration is production-ready.

**Reason:** The G2 API token authenticates successfully, but `/api/v2/products` returns zero products because the account currently has no entitled product data.

**Follow-up:** Obtain the required G2 data subscription or connect another permitted review provider before enabling live review monitoring.

---

### 17/07/2026 — Synthetic review provider used for validation

**Decision:** Use a clearly labeled manual fixture provider to test the review pipeline while live G2 data is unavailable.

**Reason:** This allows review snapshot storage, new-review detection, rating-shift calculation, negative-review classification, Gemini synthesis, brief storage, and idempotency to be tested independently from the external provider.

**Verified result:**

- Review count changed from `3` to `4`
- Average rating changed from `4.0` to `3.25`
- Rating delta was `-0.75`
- One new 1-star review was detected
- Gemini labeled the result as synthetic
- Priority remained `low`
- Duplicate brief insertion was prevented

---

### 17/07/2026 — Dependency versions aligned

**Decision:** Upgrade the Supabase Python SDK after installing `google-genai`.

**Reason:** `google-genai` required `httpx 0.28.1`, while the older Supabase SDK required `httpx <0.28`.

**Result:** Supabase was upgraded to `2.31.0`, and `pip check` reported no broken requirements.

**Status:** Resolved on 17/07/2026. The working Supabase, Gemini, HTTPX, and Pydantic versions are pinned in `requirements.txt`.

---

### 18/07/2026 — Public careers sources used for job monitoring

**Decision:** Monitor official public career sources through provider-specific adapters instead of scraping aggregators such as LinkedIn or Indeed.

**Reason:** Official sources provide clearer current-opening data, more stable identifiers, and fewer duplication and access problems.

**Implementation:**

- GitHub careers provider for repositories such as `rows/hiring`.
- Public HTML careers provider for server-rendered company career pages.
- Structured fields include title, department, location, workplace type, URL, and provider-stable ID.

**Live verification:**

- Rows' official GitHub careers source returned zero openings; zero was correctly stored as valid live data.
- Hex's official careers page returned 26 real openings.
- Nine Hex roles were identified as remote-compatible.
- Departments were extracted: Engineering 13, Sales 5, Product 3, Customer 2, Design 1, Marketing 1, and People 1.
- A second Hex collection returned the same 26 stable jobs with no false changes.
- All live snapshots were marked `test_fixture: false`.

**Controlled verification:**

- A synthetic new role tested addition detection, Gemini synthesis, brief storage, and duplicate prevention.
- Two fresh Rows snapshots restored its latest comparison state to live data.

**Follow-up:** Add Greenhouse and Lever adapters when a monitored competitor uses those systems. A natural live addition or removal has not yet been observed.

---

### Open assumptions to validate

- The proposed target of `10–15` actionable briefs per competitor per week is a working alert-fatigue hypothesis, not yet a validated product requirement.
- Validate alert volume with beta users before encoding it as permanent priority or suppression logic.
