-- Institutional Memory Governance and Activity Log Migration

-- 1. Add governance columns to institutional_answers
ALTER TABLE IF EXISTS institutional_answers
  ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS edited_by text NULL,
  ADD COLUMN IF NOT EXISTS edited_at timestamptz NULL;

-- 2. Create activity_log table
CREATE TABLE IF NOT EXISTS activity_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id text NOT NULL,
  user_id text NULL,
  action_type text NOT NULL,
  entity_type text NULL,
  entity_id text NULL,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS activity_log_org_idx ON activity_log(org_id);
CREATE INDEX IF NOT EXISTS activity_log_created_idx ON activity_log(created_at DESC);

-- 3. RLS: allow org members to read/insert activity log, and admins/owners to delete
ALTER TABLE IF EXISTS activity_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS activity_log_org_member ON activity_log;
CREATE POLICY activity_log_org_member
  ON activity_log
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM memberships m
      WHERE m.org_id = activity_log.org_id
        AND m.user_id = auth.uid()
    )
  );

-- Note: In a hardened deployment you may want more granular policies per action.

-- 4. Backfill: if institutional_answers exists, ensure is_active true where null
UPDATE institutional_answers SET is_active = true WHERE is_active IS NULL;
