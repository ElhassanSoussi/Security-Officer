-- Stripe Billing Integration Migration
-- Run in Supabase SQL Editor after 012_billing_usage.sql
-- Safe to re-run (uses IF NOT EXISTS / DO $$ blocks)
-- =============================================================================

-- 1. Add Stripe tracking columns to the subscriptions table
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS stripe_customer_id     text;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS stripe_subscription_id text;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS stripe_status           text
    CHECK (stripe_status IN ('active', 'trialing', 'past_due', 'canceled', 'unpaid', 'incomplete', 'pending'));
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS current_period_end      timestamptz;

-- 2. Index: fast lookup by stripe_customer_id (used by webhook handlers)
CREATE INDEX IF NOT EXISTS subscriptions_stripe_customer_idx
    ON subscriptions(stripe_customer_id)
    WHERE stripe_customer_id IS NOT NULL;

-- 3. Index: fast lookup by stripe_subscription_id
CREATE INDEX IF NOT EXISTS subscriptions_stripe_sub_idx
    ON subscriptions(stripe_subscription_id)
    WHERE stripe_subscription_id IS NOT NULL;

-- 4. billing_events table (idempotent — may already exist from stripe_billing_migration.sql)
CREATE TABLE IF NOT EXISTS billing_events (
    id               uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    org_id           uuid        REFERENCES organizations(id) ON DELETE SET NULL,
    stripe_event_id  text        UNIQUE NOT NULL,
    type             text        NOT NULL,
    raw_payload      jsonb,
    created_at       timestamptz DEFAULT now()
);

-- 5. RLS on billing_events (idempotent)
ALTER TABLE billing_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "billing_events_select_member" ON billing_events;
CREATE POLICY "billing_events_select_member"
    ON billing_events FOR SELECT TO authenticated
    USING (
        org_id::text IN (
            SELECT org_id::text FROM memberships WHERE user_id::text = auth.uid()::text
        )
    );

-- 6. Indexes on billing_events (idempotent)
CREATE INDEX IF NOT EXISTS billing_events_org_idx        ON billing_events(org_id);
CREATE INDEX IF NOT EXISTS billing_events_stripe_evt_idx ON billing_events(stripe_event_id);

-- 7. Verify subscriptions columns
SELECT column_name, data_type
FROM   information_schema.columns
WHERE  table_name = 'subscriptions'
  AND  column_name IN (
    'stripe_customer_id', 'stripe_subscription_id',
    'stripe_status', 'current_period_end'
  )
ORDER BY column_name;
