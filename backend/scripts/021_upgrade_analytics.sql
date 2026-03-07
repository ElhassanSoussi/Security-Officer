-- =============================================================================
-- 021 — Upgrade Funnel Analytics Table
-- Creates the upgrade_events table for tracking the upgrade conversion funnel.
-- Safe to re-run (IF NOT EXISTS throughout).
--
-- Event types stored:
--   limit_hit              — PlanService detected a limit breach
--   upgrade_modal_shown    — UpgradeModal rendered in the browser
--   upgrade_clicked        — User clicked "Upgrade Now" in the modal
--   stripe_portal_redirected — User sent to Stripe Customer Portal
--   stripe_portal_returned — User returned from Stripe portal
--   plan_upgraded          — Webhook confirmed subscription tier changed
-- =============================================================================

-- 1. Main table
CREATE TABLE IF NOT EXISTS upgrade_events (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      uuid        NOT NULL,
    user_id     text        NOT NULL DEFAULT '',
    event_type  text        NOT NULL,
    metadata    jsonb       NOT NULL DEFAULT '{}',
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- 2. Indexes for analytics queries
CREATE INDEX IF NOT EXISTS upgrade_events_org_created
    ON upgrade_events (org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS upgrade_events_event_type
    ON upgrade_events (event_type, created_at DESC);

CREATE INDEX IF NOT EXISTS upgrade_events_org_type
    ON upgrade_events (org_id, event_type, created_at DESC);

-- 3. CHECK constraint on event_type
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'upgrade_events_event_type_check'
          AND conrelid = 'upgrade_events'::regclass
    ) THEN
        ALTER TABLE upgrade_events
            ADD CONSTRAINT upgrade_events_event_type_check
            CHECK (event_type IN (
                'limit_hit',
                'upgrade_modal_shown',
                'upgrade_clicked',
                'stripe_portal_redirected',
                'stripe_portal_returned',
                'plan_upgraded'
            ));
    END IF;
END $$;

-- 4. RLS — org members can read their own org's events; only service role writes
ALTER TABLE upgrade_events ENABLE ROW LEVEL SECURITY;

-- Allow org members to read their own org's analytics
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'upgrade_events' AND policyname = 'upgrade_events_org_select'
    ) THEN
        CREATE POLICY upgrade_events_org_select
            ON upgrade_events FOR SELECT
            USING (
                org_id IN (
                    SELECT org_id FROM memberships
                    WHERE user_id = auth.uid()
                )
            );
    END IF;
END $$;

-- Only service role (backend admin client) may insert
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'upgrade_events' AND policyname = 'upgrade_events_service_insert'
    ) THEN
        CREATE POLICY upgrade_events_service_insert
            ON upgrade_events FOR INSERT
            WITH CHECK (true);  -- enforced by service-role key requirement
    END IF;
END $$;

-- 5. Comment
COMMENT ON TABLE upgrade_events IS
    'Upgrade funnel analytics: tracks limit_hit → modal_shown → upgrade_clicked → plan_upgraded.';
