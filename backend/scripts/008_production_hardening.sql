-- Production Hardening Migration
-- Run this migration AFTER all previous migrations have been applied.
-- 
-- Changes:
--   1. Adds immutable flag to audit_events (marks entries as non-editable)
--   2. Revokes UPDATE/DELETE on audit_events for authenticated role
--   3. Adds index on audit_events(org_id, created_at) for query performance

-- 1. Mark audit entries as immutable (column for application-level enforcement)
DO $$ BEGIN
    ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS immutable boolean NOT NULL DEFAULT true;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- 2. Revoke UPDATE and DELETE on audit_events for the authenticated role.
--    This prevents any RLS-scoped user from modifying or deleting audit records.
REVOKE UPDATE, DELETE ON audit_events FROM authenticated;

-- 3. Performance index for audit queries filtered by org + date
CREATE INDEX IF NOT EXISTS idx_audit_events_org_created
    ON audit_events (org_id, created_at DESC);

-- 4. Performance index for run_audits filtered by org + date
CREATE INDEX IF NOT EXISTS idx_run_audits_org_created
    ON run_audits (org_id, created_at DESC);
