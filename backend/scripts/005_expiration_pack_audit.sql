-- Expiration Tracking, Compliance Packs, and Audit Events Index Migration
-- Safe: all operations are idempotent (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS)

-- ═══════════════════════════════════════════════════════════════════════════════
-- Part 2: Expiration columns on project_documents
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE project_documents
  ADD COLUMN IF NOT EXISTS expiration_date DATE DEFAULT NULL;

ALTER TABLE project_documents
  ADD COLUMN IF NOT EXISTS reminder_days_before INTEGER DEFAULT 30;

-- Index for expiration queries
CREATE INDEX IF NOT EXISTS idx_project_documents_expiration
  ON project_documents (project_id, expiration_date)
  WHERE expiration_date IS NOT NULL;

-- ═══════════════════════════════════════════════════════════════════════════════
-- Part 3: Compliance packs table
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS compliance_packs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  org_id        UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  created_by    UUID NOT NULL,
  document_ids  JSONB NOT NULL DEFAULT '[]',
  file_count    INTEGER NOT NULL DEFAULT 0,
  size_bytes    BIGINT DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RLS for compliance_packs
ALTER TABLE compliance_packs ENABLE ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS "compliance_packs_org_access"
  ON compliance_packs
  FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM memberships WHERE user_id = auth.uid()
    )
  );

CREATE INDEX IF NOT EXISTS idx_compliance_packs_project
  ON compliance_packs (project_id);

CREATE INDEX IF NOT EXISTS idx_compliance_packs_org
  ON compliance_packs (org_id);

-- ═══════════════════════════════════════════════════════════════════════════════
-- Part 4: Audit events indexes for performance
-- ═══════════════════════════════════════════════════════════════════════════════

-- Ensure audit_events table has proper indexes for filtering
CREATE INDEX IF NOT EXISTS idx_audit_events_org_created
  ON audit_events (org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_events_event_type
  ON audit_events (org_id, event_type);

CREATE INDEX IF NOT EXISTS idx_audit_events_date_range
  ON audit_events (org_id, created_at);
