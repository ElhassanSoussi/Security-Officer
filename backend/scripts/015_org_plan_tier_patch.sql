-- =============================================================================
-- Patch: Add missing columns to organizations table
-- Run in Supabase SQL Editor → Click "Run"
-- Safe to re-run (all IF NOT EXISTS)
-- =============================================================================

-- plan_tier: used by billing endpoints and webhook handlers
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS plan_tier text NOT NULL DEFAULT 'starter';

-- trade_type / company_size: used by onboarding
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS trade_type text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS company_size text;

-- Verify
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'organizations'
  AND column_name IN ('plan_tier', 'trade_type', 'company_size', 'stripe_customer_id', 'subscription_status')
ORDER BY column_name;
