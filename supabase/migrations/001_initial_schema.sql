-- ============================================================
-- OUTPACE — Initial Database Schema
-- ============================================================
-- This file defines the core tables Outpace needs to function.
-- Run this in the Supabase SQL Editor (Dashboard > SQL Editor)
-- to create your database structure.
-- ============================================================


-- ------------------------------------------------------------
-- TABLE: users
-- ------------------------------------------------------------
-- Note: Supabase Auth already creates and manages a built-in
-- `auth.users` table for us automatically when someone signs up.
-- We don't need to create our own users table — we just
-- reference auth.users.id (a UUID) from our other tables below.
-- ------------------------------------------------------------


-- ------------------------------------------------------------
-- TABLE: competitors
-- ------------------------------------------------------------
-- Each row = one competitor that a user wants Outpace to track.
-- Example: a user tracking "Klue" and "Crayon" will have 2 rows.
-- ------------------------------------------------------------
CREATE TABLE competitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Which user owns this competitor entry
    user_id UUID REFERENCES auth.users(id) NOT NULL,

    -- Basic info about the competitor
    name TEXT NOT NULL,                  -- e.g. "Klue"
    website_url TEXT NOT NULL,           -- e.g. "https://klue.com"
    pricing_url TEXT,                    -- e.g. "https://klue.com/pricing" (nullable — not all users add this immediately)

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);


-- ------------------------------------------------------------
-- TABLE: snapshots
-- ------------------------------------------------------------
-- Each row = one scrape of a competitor's page at a point in time.
-- This is our "raw data" table — we store the actual scraped
-- content here so we can compare snapshot N vs snapshot N-1 later
-- (that comparison is what we call "diffing").
-- ------------------------------------------------------------
CREATE TABLE snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Which competitor this snapshot belongs to
    competitor_id UUID REFERENCES competitors(id) NOT NULL,

    -- What type of page this snapshot is from.
    -- 'general' = homepage/product pages
    -- 'pricing' = dedicated pricing page (monitored more frequently)
    signal_type TEXT NOT NULL CHECK (signal_type IN ('general', 'pricing', 'reviews', 'jobs')),

    -- The raw scraped content.
    -- For 'general': raw HTML or extracted text
    -- For 'pricing': structured JSON (plan names, prices, features)
    raw_content JSONB NOT NULL,

    -- When this snapshot was taken
    scraped_at TIMESTAMPTZ DEFAULT now()
);


-- ------------------------------------------------------------
-- TABLE: briefs
-- ------------------------------------------------------------
-- Each row = one AI-synthesized insight about a detected change.
-- This is what actually gets shown to the user in their dashboard
-- or emailed to them. It's the "so what does this mean" output.
-- ------------------------------------------------------------
CREATE TABLE briefs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Which competitor and user this brief is about
    competitor_id UUID REFERENCES competitors(id) NOT NULL,
    user_id UUID REFERENCES auth.users(id) NOT NULL,

    -- What kind of signal triggered this brief
    signal_type TEXT NOT NULL CHECK (signal_type IN ('general', 'pricing', 'reviews', 'jobs')),

    -- The two snapshots that were compared to generate this brief
    old_snapshot_id UUID REFERENCES snapshots(id),
    new_snapshot_id UUID REFERENCES snapshots(id) NOT NULL,

    -- The raw diff (what literally changed, before AI interpretation)
    raw_diff JSONB,

    -- The AI-generated synthesis (what it means, why it matters)
    -- Example: { "summary": "...", "significance": "high", "recommended_action": "..." }
    synthesis JSONB NOT NULL,

    -- How urgent/important this brief is.
    -- Used to decide: does this go in the weekly digest, or trigger
    -- an immediate email alert?
    priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),

    -- Has this brief already been sent to the user via email?
    delivered BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ DEFAULT now()
);


-- ------------------------------------------------------------
-- INDEXES
-- ------------------------------------------------------------
-- These speed up the queries we'll run most often:
-- "give me all snapshots for competitor X" and
-- "give me all undelivered briefs for user Y"
-- ------------------------------------------------------------
CREATE INDEX idx_snapshots_competitor_id ON snapshots(competitor_id);
CREATE INDEX idx_briefs_user_id ON briefs(user_id);
CREATE INDEX idx_briefs_delivered ON briefs(delivered);


-- ------------------------------------------------------------
-- ROW LEVEL SECURITY (RLS)
-- ------------------------------------------------------------
-- This ensures users can only see their OWN competitors and briefs,
-- not other users' data. Critical for a multi-tenant SaaS product.
-- ------------------------------------------------------------
ALTER TABLE competitors ENABLE ROW LEVEL SECURITY;
ALTER TABLE briefs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own competitors"
    ON competitors FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own competitors"
    ON competitors FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can view their own briefs"
    ON briefs FOR SELECT
    USING (auth.uid() = user_id);