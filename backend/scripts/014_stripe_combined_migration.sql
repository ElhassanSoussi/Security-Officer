-- =============================================================================
-- COMBINED Stripe Billing Migration
-- Run this ENTIRE block in Supabase SQL Editor → Click "Run"
-- Safe to re-run (all operations are idempotent)
-- =============================================================================

-- ─── 1. Add Stripe columns to ORGANIZATIONS ─────────────────────────────────
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS stripe_customer_id text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS stripe_subscription_id text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS subscription_status text DEFAULT 'trialing';
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS current_period_start timestamptz;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS current_period_end timestamptz;

CREATE INDEX IF NOT EXISTS idx_organizations_stripe_customer
    ON organizations(stripe_customer_id)
    WHERE stripe_customer_id IS NOT NULL;

-- ─── 2. Add Stripe columns to SUBSCRIPTIONS ─────────────────────────────────
-- (existing table has: org_id, status, plan_id, current_period_end, exports_used, exports_limit)
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS stripe_customer_id text;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS stripe_subscription_id text;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS stripe_status text;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS plan_name text;

-- Backfill plan_name from plan_id for existing rows
UPDATE subscriptions
SET plan_name = UPPER(COALESCE(plan_id, 'FREE'))
WHERE plan_name IS NULL;

-- Indexes for webhook lookups
CREATE INDEX IF NOT EXISTS subscriptions_stripe_customer_idx
    ON subscriptions(stripe_customer_id)
    WHERE stripe_customer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS subscriptions_stripe_sub_idx
    ON subscriptions(stripe_subscription_id)
    WHERE stripe_subscription_id IS NOT NULL;

-- ─── 3. Fix stripe_status CHECK constraint (allow 'pending') ────────────────
DO $$
BEGIN
    -- Drop any existing check constraint on stripe_status
    IF EXISTS (
        SELECT 1 FROM information_schema.constraint_column_usage
        WHERE table_name = 'subscriptions' AND column_name = 'stripe_status'
    ) THEN
        EXECUTE (
            SELECT 'ALTER TABLE subscriptions DROP CONSTRAINT ' || constraint_name
            FROM information_schema.constraint_column_usage
            WHERE table_name = 'subscriptions' AND column_name = 'stripe_status'
            LIMIT 1
        );
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'No existing stripe_status constraint to drop: %', SQLERRM;
END $$;

-- Add constraint with all valid statuses including 'pending'
DO $$
BEGIN
    ALTER TABLE subscriptions
        ADD CONSTRAINT subscriptions_stripe_status_check
        CHECK (stripe_status IS NULL OR stripe_status IN (
            'active', 'trialing', 'past_due', 'canceled', 'unpaid', 'incomplete', 'pending'
        ));
EXCEPTION WHEN duplicate_object THEN
    RAISE NOTICE 'subscriptions_stripe_status_check already exists';
END $$;

-- ─── 4. Create BILLING_EVENTS table ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS billing_events (
    id               uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    org_id           uuid        REFERENCES organizations(id) ON DELETE SET NULL,
    stripe_event_id  text        UNIQUE NOT NULL,
    type             text        NOT NULL,
    raw_payload      jsonb,
    created_at       timestamptz DEFAULT now()
);

ALTER TABLE billing_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "billing_events_select_member" ON billing_events;
CREATE POLICY "billing_events_select_member"
    ON billing_events FOR SELECT TO authenticated
    USING (
        org_id IS NULL
        OR org_id::text IN (
            SELECT org_id::text FROM memberships WHERE user_id::text = auth.uid()::text
        )
    );

CREATE INDEX IF NOT EXISTS billing_events_org_idx        ON billing_events(org_id);
CREATE INDEX IF NOT EXISTS billing_events_stripe_evt_idx ON billing_events(stripe_event_id);

-- ─── 5. Create USAGE_METRICS table (Phase 18) ───────────────────────────────
CREATE TABLE IF NOT EXISTS usage_metrics (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id       text NOT NULL,
    metric_type  text NOT NULL
                     CHECK (metric_type IN (
                         'RUN_CREATED',
                         'DOCUMENT_UPLOADED',
                         'MEMORY_STORED',
                         'EVIDENCE_GENERATED'
                     )),
    count        integer NOT NULL DEFAULT 1,
    period_start timestamptz NOT NULL DEFAULT date_trunc('month', now()),
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS usage_metrics_org_period_idx
    ON usage_metrics(org_id, period_start);

ALTER TABLE usage_metrics ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "usage_metrics_read_member" ON usage_metrics;
CREATE POLICY "usage_metrics_read_member"
    ON usage_metrics FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM memberships m
            WHERE m.org_id::text = usage_metrics.org_id
              AND m.user_id::text = auth.uid()::text
        )
    );

-- ─── 6. Update PLANS table with correct pricing ─────────────────────────────
UPDATE plans SET price_cents = 14900  WHERE id = 'starter' AND price_cents != 14900;
UPDATE plans SET price_cents = 49900  WHERE id = 'growth'  AND price_cents != 49900;
UPDATE plans SET price_cents = 149900 WHERE id = 'elite'   AND price_cents != 149900;

-- ─── 7. Verify ──────────────────────────────────────────────────────────────
SELECT 'subscriptions' AS tbl, column_name, data_type
FROM information_schema.columns
WHERE table_name = 'subscriptions'
  AND column_name IN ('stripe_customer_id','stripe_subscription_id','stripe_status','plan_name','current_period_end')
UNION ALL
SELECT 'organizations' AS tbl, column_name, data_type
FROM information_schema.columns
WHERE table_name = 'organizations'
  AND column_name IN ('stripe_customer_id','stripe_subscription_id','subscription_status')
UNION ALL
SELECT 'billing_events' AS tbl, column_name, data_type
FROM information_schema.columns
WHERE table_name = 'billing_events'
  AND column_name IN ('id','stripe_event_id','type')
ORDER BY tbl, column_name;
