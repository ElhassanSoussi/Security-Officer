-- =============================================
-- Stripe Billing Migration
-- Run in Supabase SQL Editor
-- Safe to re-run (uses IF NOT EXISTS / IF EXISTS)
-- =============================================

-- 1. Add Stripe columns to organizations
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS stripe_customer_id text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS stripe_subscription_id text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS subscription_status text DEFAULT 'trialing';
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS current_period_start timestamptz;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS current_period_end timestamptz;

-- 2. Create billing_events audit trail
CREATE TABLE IF NOT EXISTS billing_events (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  org_id uuid REFERENCES organizations(id),
  stripe_event_id text UNIQUE NOT NULL,
  type text NOT NULL,
  raw_payload jsonb,
  created_at timestamptz DEFAULT now()
);

-- 3. Enable RLS on billing_events
ALTER TABLE billing_events ENABLE ROW LEVEL SECURITY;

-- 4. RLS policy: members can read their org's billing events
DROP POLICY IF EXISTS "billing_events_select_member" ON billing_events;
CREATE POLICY "billing_events_select_member"
  ON billing_events FOR SELECT TO authenticated
  USING (org_id::text IN (
    SELECT org_id::text FROM memberships WHERE user_id::text = auth.uid()::text
  ));

-- 5. Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_billing_events_org_id ON billing_events(org_id);
CREATE INDEX IF NOT EXISTS idx_billing_events_stripe_event ON billing_events(stripe_event_id);
CREATE INDEX IF NOT EXISTS idx_organizations_stripe_customer ON organizations(stripe_customer_id);

-- 6. Verify
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'organizations'
  AND column_name IN ('stripe_customer_id', 'stripe_subscription_id', 'subscription_status', 'current_period_start', 'current_period_end')
ORDER BY column_name;
