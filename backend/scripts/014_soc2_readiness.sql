-- SOC2 Readiness Foundations — Migration
-- Immutable Activity Log Protection + Data Retention Support

-- ────────────────────────────────────────────────────────────
-- Part 2: Immutable Activity Log — DB-level constraints
-- ────────────────────────────────────────────────────────────

-- Ensure created_at is NOT NULL with a default
ALTER TABLE activity_log
  ALTER COLUMN created_at SET NOT NULL,
  ALTER COLUMN created_at SET DEFAULT now();

-- Block DELETE on activity_log (immutable audit trail)
CREATE OR REPLACE FUNCTION prevent_activity_log_delete()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'activity_log rows are immutable and cannot be deleted (SOC2 compliance)';
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_activity_log_delete ON activity_log;
CREATE TRIGGER trg_prevent_activity_log_delete
  BEFORE DELETE ON activity_log
  FOR EACH ROW
  EXECUTE FUNCTION prevent_activity_log_delete();

-- Block UPDATE on activity_log (immutable audit trail)
CREATE OR REPLACE FUNCTION prevent_activity_log_update()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'activity_log rows are immutable and cannot be updated (SOC2 compliance)';
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_activity_log_update ON activity_log;
CREATE TRIGGER trg_prevent_activity_log_update
  BEFORE UPDATE ON activity_log
  FOR EACH ROW
  EXECUTE FUNCTION prevent_activity_log_update();

-- ────────────────────────────────────────────────────────────
-- Part 2b: Same protection for audit_events table
-- ────────────────────────────────────────────────────────────

ALTER TABLE audit_events
  ALTER COLUMN created_at SET NOT NULL,
  ALTER COLUMN created_at SET DEFAULT now();

CREATE OR REPLACE FUNCTION prevent_audit_events_delete()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_events rows are immutable and cannot be deleted (SOC2 compliance)';
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_audit_events_delete ON audit_events;
CREATE TRIGGER trg_prevent_audit_events_delete
  BEFORE DELETE ON audit_events
  FOR EACH ROW
  EXECUTE FUNCTION prevent_audit_events_delete();

CREATE OR REPLACE FUNCTION prevent_audit_events_update()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_events rows are immutable and cannot be updated (SOC2 compliance)';
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_audit_events_update ON audit_events;
CREATE TRIGGER trg_prevent_audit_events_update
  BEFORE UPDATE ON audit_events
  FOR EACH ROW
  EXECUTE FUNCTION prevent_audit_events_update();

-- ────────────────────────────────────────────────────────────
-- Part 3: Data Retention — add soft-delete column to runs
-- ────────────────────────────────────────────────────────────

-- Add soft-delete support column (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'runs' AND column_name = 'retained_until'
  ) THEN
    ALTER TABLE runs ADD COLUMN retained_until timestamptz DEFAULT NULL;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'runs' AND column_name = 'retention_deleted_at'
  ) THEN
    ALTER TABLE runs ADD COLUMN retention_deleted_at timestamptz DEFAULT NULL;
  END IF;
END $$;

-- Index for retention job queries
CREATE INDEX IF NOT EXISTS idx_runs_retention
  ON runs (created_at)
  WHERE retention_deleted_at IS NULL;
