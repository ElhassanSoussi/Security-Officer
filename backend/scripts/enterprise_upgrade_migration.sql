-- =============================================
-- Enterprise Upgrade Migration
-- Run in Supabase SQL Editor
-- Safe to re-run (IF NOT EXISTS / IF EXISTS)
-- =============================================

-- 1. Add review workflow columns to run_audits
ALTER TABLE run_audits ADD COLUMN IF NOT EXISTS reviewer_id text;
ALTER TABLE run_audits ADD COLUMN IF NOT EXISTS review_status text DEFAULT 'pending';
ALTER TABLE run_audits ADD COLUMN IF NOT EXISTS review_notes text;
ALTER TABLE run_audits ADD COLUMN IF NOT EXISTS reviewed_at timestamptz;

-- 2. Index for filtering by review status
CREATE INDEX IF NOT EXISTS idx_run_audits_review_status ON run_audits(review_status);

-- 3. Defensive RLS audit: drop any overly-permissive USING(true) policies
-- (Verified: none currently present — these are purely defensive)
DO $$ 
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT tablename, policyname
        FROM pg_policies
        WHERE tablename IN ('organizations','memberships','projects','documents','runs','exports','chunks','run_audits')
          AND qual = 'true'
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON %I', r.policyname, r.tablename);
        RAISE NOTICE 'Dropped USING(true) policy: % on %', r.policyname, r.tablename;
    END LOOP;
END $$;

-- 4. Ensure RLS is enabled on run_audits
ALTER TABLE run_audits ENABLE ROW LEVEL SECURITY;

-- 5. RLS policy for run_audits (membership-scoped via runs → org_id)
DROP POLICY IF EXISTS "run_audits_select_member" ON run_audits;
CREATE POLICY "run_audits_select_member"
  ON run_audits FOR SELECT TO authenticated
  USING (
    run_id::text IN (
      SELECT id::text FROM runs
      WHERE org_id::text IN (SELECT org_id::text FROM memberships WHERE user_id::text = auth.uid()::text)
    )
  );

DROP POLICY IF EXISTS "run_audits_update_member" ON run_audits;
CREATE POLICY "run_audits_update_member"
  ON run_audits FOR UPDATE TO authenticated
  USING (
    run_id::text IN (
      SELECT id::text FROM runs
      WHERE org_id::text IN (SELECT org_id::text FROM memberships WHERE user_id::text = auth.uid()::text)
    )
  );

-- 6. Verify
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'run_audits'
  AND column_name IN ('reviewer_id', 'review_status', 'review_notes', 'reviewed_at')
ORDER BY column_name;
