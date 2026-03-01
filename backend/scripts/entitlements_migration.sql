-- Plan Entitlements Migration
-- Run this on your Supabase SQL Editor before restarting the backend.

-- 1. Add plan columns to organizations (idempotent)
ALTER TABLE organizations
  ADD COLUMN IF NOT EXISTS plan_tier text NOT NULL DEFAULT 'starter';

ALTER TABLE organizations
  ADD COLUMN IF NOT EXISTS period_start timestamptz NOT NULL DEFAULT date_trunc('month', now());

ALTER TABLE organizations
  ADD COLUMN IF NOT EXISTS period_end timestamptz NOT NULL DEFAULT (date_trunc('month', now()) + interval '1 month');

-- 2. Usage counters table
CREATE TABLE IF NOT EXISTS org_usage (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  period_start timestamptz NOT NULL,
  questionnaires_used int NOT NULL DEFAULT 0,
  exports_used int NOT NULL DEFAULT 0,
  storage_used_bytes bigint NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, period_start)
);

-- 3. RLS on org_usage
ALTER TABLE org_usage ENABLE ROW LEVEL SECURITY;

-- Allow users to read their own org's usage
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE policyname = 'org_usage_select' AND tablename = 'org_usage'
  ) THEN
    CREATE POLICY org_usage_select ON org_usage FOR SELECT
      USING (org_id IN (
        SELECT org_id FROM org_members WHERE user_id = auth.uid()
      ));
  END IF;
END $$;

-- Allow service role full access (for atomic increments)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE policyname = 'org_usage_service_all' AND tablename = 'org_usage'
  ) THEN
    CREATE POLICY org_usage_service_all ON org_usage FOR ALL
      USING (auth.role() = 'service_role');
  END IF;
END $$;

-- 4. Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_org_usage_org_period
  ON org_usage (org_id, period_start);
