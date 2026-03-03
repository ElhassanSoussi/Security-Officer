-- Evidence Vault and Immutable Audit Export Migration

-- 1. Add is_locked to runs
ALTER TABLE IF EXISTS runs
  ADD COLUMN IF NOT EXISTS is_locked boolean NOT NULL DEFAULT false;

-- 2. Create run_evidence_records table
CREATE TABLE IF NOT EXISTS run_evidence_records (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id        uuid NOT NULL,
  org_id        text NOT NULL,
  generated_by  text NOT NULL,
  sha256_hash   text NOT NULL,
  health_score  integer NOT NULL DEFAULT 0,
  package_size  integer NULL,            -- bytes, optional
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS run_evidence_run_idx  ON run_evidence_records(run_id);
CREATE INDEX IF NOT EXISTS run_evidence_org_idx  ON run_evidence_records(org_id);

-- 3. RLS: org members can read; only admin/owner can delete
ALTER TABLE IF EXISTS run_evidence_records ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS evidence_read_org_member ON run_evidence_records;
CREATE POLICY evidence_read_org_member
  ON run_evidence_records
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM memberships m
      WHERE m.org_id = run_evidence_records.org_id
        AND m.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS evidence_insert_member ON run_evidence_records;
CREATE POLICY evidence_insert_member
  ON run_evidence_records
  FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM memberships m
      WHERE m.org_id = run_evidence_records.org_id
        AND m.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS evidence_delete_admin ON run_evidence_records;
CREATE POLICY evidence_delete_admin
  ON run_evidence_records
  FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM memberships m
      WHERE m.org_id = run_evidence_records.org_id
        AND m.user_id = auth.uid()
        AND m.role IN ('owner', 'admin')
    )
  );
