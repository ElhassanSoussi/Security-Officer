-- =============================================
-- Audit Events (tenant-scoped)
-- Adds an audit_events table + RLS policies.
-- Run in Supabase SQL Editor.
-- =============================================

-- Table
CREATE TABLE IF NOT EXISTS audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  user_id text NOT NULL,
  event_type text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_events_org_created_at
  ON audit_events (org_id, created_at DESC);

-- RLS
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;

-- Read: members can read org events
DROP POLICY IF EXISTS "audit_events_select_member" ON audit_events;
CREATE POLICY "audit_events_select_member"
  ON audit_events FOR SELECT TO authenticated
  USING (
    org_id IN (SELECT org_id FROM memberships WHERE user_id = auth.uid()::text)
  );

-- Insert: members can write their own events
DROP POLICY IF EXISTS "audit_events_insert_member" ON audit_events;
CREATE POLICY "audit_events_insert_member"
  ON audit_events FOR INSERT TO authenticated
  WITH CHECK (
    org_id IN (SELECT org_id FROM memberships WHERE user_id = auth.uid()::text)
    AND user_id = auth.uid()::text
  );

