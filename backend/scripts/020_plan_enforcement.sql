-- =============================================================================
-- 020 — Deterministic Plan Enforcement Columns
-- Adds constrained `plan` column, `stripe_price_id`, and ensures
-- `subscription_status` exists on the organizations table.
-- Safe to re-run (all IF NOT EXISTS / DO-guard).
-- =============================================================================

-- 1) plan column with CHECK constraint
ALTER TABLE organizations
  ADD COLUMN IF NOT EXISTS plan text NOT NULL DEFAULT 'starter';

-- Add CHECK constraint (guard: only if not already present)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'organizations_plan_check'
      AND conrelid = 'organizations'::regclass
  ) THEN
    ALTER TABLE organizations
      ADD CONSTRAINT organizations_plan_check
      CHECK (plan IN ('starter', 'growth', 'elite'));
  END IF;
END $$;

-- 2) stripe_price_id — the Stripe Price ID that determined the current plan
ALTER TABLE organizations
  ADD COLUMN IF NOT EXISTS stripe_price_id text;

-- 3) subscription_status — mirrors Stripe subscription.status
--    (may already exist from earlier migrations; safe to re-run)
ALTER TABLE organizations
  ADD COLUMN IF NOT EXISTS subscription_status text DEFAULT 'trialing';

-- 4) Back-fill: sync plan from existing plan_tier for any rows that
--    already have a plan_tier value but plan is still 'starter'.
UPDATE organizations
SET plan = plan_tier
WHERE plan_tier IN ('starter', 'growth', 'elite')
  AND plan = 'starter'
  AND plan_tier != 'starter';

-- 5) Index for fast plan-based queries
CREATE INDEX IF NOT EXISTS idx_organizations_plan ON organizations (plan);

-- 6) Verify
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'organizations'
  AND column_name IN ('plan', 'stripe_price_id', 'subscription_status', 'plan_tier')
ORDER BY column_name;
