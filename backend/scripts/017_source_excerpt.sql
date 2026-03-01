-- =============================================
-- Source Excerpt + Review Hardening Migration
-- Adds source_excerpt column to run_audits for source transparency.
-- Safe to re-run (IF NOT EXISTS).
-- =============================================

BEGIN;

-- Add source_excerpt column to run_audits
ALTER TABLE IF EXISTS run_audits
  ADD COLUMN IF NOT EXISTS source_excerpt text;

-- Ensure review workflow columns exist (idempotent, may already exist from enterprise_upgrade)
ALTER TABLE IF EXISTS run_audits
  ADD COLUMN IF NOT EXISTS reviewer_id text;

ALTER TABLE IF EXISTS run_audits
  ADD COLUMN IF NOT EXISTS review_status text DEFAULT 'pending';

ALTER TABLE IF EXISTS run_audits
  ADD COLUMN IF NOT EXISTS review_notes text;

ALTER TABLE IF EXISTS run_audits
  ADD COLUMN IF NOT EXISTS reviewed_at timestamptz;

ALTER TABLE IF EXISTS run_audits
  ADD COLUMN IF NOT EXISTS editor_id text;

ALTER TABLE IF EXISTS run_audits
  ADD COLUMN IF NOT EXISTS edited_at timestamptz;

-- Index for filtering by review status (if not exists)
CREATE INDEX IF NOT EXISTS idx_run_audits_review_status ON run_audits(review_status);

-- Ensure projects table has description column
ALTER TABLE IF EXISTS projects
  ADD COLUMN IF NOT EXISTS description text;

COMMIT;
