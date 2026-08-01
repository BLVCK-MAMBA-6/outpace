-- Store one weekly digest preference per authenticated user.
--
-- Delivery addresses are written through the authenticated API,
-- which copies the verified Supabase Auth email. Browser clients
-- may view only their own preference row; service-role processes
-- perform protected writes and scheduled delivery.

CREATE TABLE digest_preferences (
    user_id UUID PRIMARY KEY
        REFERENCES auth.users(id)
        ON DELETE CASCADE,

    enabled BOOLEAN NOT NULL DEFAULT FALSE,

    delivery_email TEXT NOT NULL
        CHECK (
            char_length(delivery_email)
            BETWEEN 3 AND 320
        ),

    frequency TEXT NOT NULL DEFAULT 'weekly'
        CHECK (frequency = 'weekly'),

    last_sent_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW()
);


CREATE INDEX idx_digest_preferences_enabled
    ON digest_preferences(enabled)
    WHERE enabled = TRUE;


ALTER TABLE digest_preferences
    ENABLE ROW LEVEL SECURITY;


CREATE POLICY "Users can view their own digest preference"
    ON digest_preferences
    FOR SELECT
    USING (
        auth.uid() = user_id
    );
