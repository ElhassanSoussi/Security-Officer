-- Phase 26: New Customer Onboarding Guide
-- Adds onboarding state columns to organizations.
-- Multi-tenant isolation unchanged: this only extends the organizations row.

ALTER TABLE IF EXISTS public.organizations
  ADD COLUMN IF NOT EXISTS onboarding_completed boolean NOT NULL DEFAULT false;

ALTER TABLE IF EXISTS public.organizations
  ADD COLUMN IF NOT EXISTS onboarding_step integer NOT NULL DEFAULT 1;

-- Keep values bounded (1..5). Use NOT VALID to avoid breaking existing rows;
-- validate separately if desired.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'organizations_onboarding_step_range'
  ) THEN
    ALTER TABLE public.organizations
      ADD CONSTRAINT organizations_onboarding_step_range
      CHECK (onboarding_step >= 1 AND onboarding_step <= 5) NOT VALID;
  END IF;
END $$;
