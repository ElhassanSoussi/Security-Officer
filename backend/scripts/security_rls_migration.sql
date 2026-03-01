-- =============================================
-- Security RLS Migration (Membership-Scoped Tenancy)
--
-- Goal:
--   - Deny-by-default: no anon reads
--   - Authenticated users can only access rows in orgs they belong to
--   - Safe to re-run: drops existing policies on target tables first
--
-- Run this in Supabase SQL Editor (Dashboard -> SQL Editor).
-- =============================================

-- -------------------------------------------------------------
-- 0) Enable RLS on core tables (IF EXISTS is safe across envs)
-- -------------------------------------------------------------
ALTER TABLE IF EXISTS organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS memberships   ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS projects      ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS documents     ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS runs          ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS run_audits    ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS exports       ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS chunks        ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS plans         ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS audit_events  ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS subscriptions ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  EXECUTE 'ALTER TABLE activities ENABLE ROW LEVEL SECURITY';
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
  EXECUTE 'ALTER TABLE org_usage ENABLE ROW LEVEL SECURITY';
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
  EXECUTE 'ALTER TABLE invites ENABLE ROW LEVEL SECURITY';
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
  EXECUTE 'ALTER TABLE billing_events ENABLE ROW LEVEL SECURITY';
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- -------------------------------------------------------------
-- 1) Drop existing policies on tenant tables (remove permissive rules)
-- -------------------------------------------------------------
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT schemaname, tablename, policyname
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename IN (
        'organizations', 'memberships', 'projects', 'documents', 'runs',
        'run_audits', 'exports', 'chunks', 'plans', 'audit_events', 'subscriptions',
        'activities', 'org_usage', 'invites', 'billing_events'
      )
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON %I.%I', r.policyname, r.schemaname, r.tablename);
  END LOOP;
END $$;

-- -------------------------------------------------------------
-- 2) Organizations
-- -------------------------------------------------------------
-- Read orgs you own or belong to.
CREATE POLICY "organizations_select_member"
  ON organizations FOR SELECT TO authenticated
  USING (
    owner_id::text = auth.uid()::text
    OR id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text)
  );

-- Create orgs only as yourself.
CREATE POLICY "organizations_insert_owner"
  ON organizations FOR INSERT TO authenticated
  WITH CHECK (owner_id::text = auth.uid()::text);

-- Update org only as owner.
CREATE POLICY "organizations_update_owner"
  ON organizations FOR UPDATE TO authenticated
  USING (owner_id::text = auth.uid()::text)
  WITH CHECK (owner_id::text = auth.uid()::text);

-- -------------------------------------------------------------
-- 3) Memberships
-- -------------------------------------------------------------
-- Read your memberships (and org owners can read org memberships).
CREATE POLICY "memberships_select_member"
  ON memberships FOR SELECT TO authenticated
  USING (
    user_id::text = auth.uid()::text
    OR org_id IN (SELECT id FROM organizations WHERE owner_id::text = auth.uid()::text)
  );

-- Insert memberships only by org owners (includes initial owner membership on org creation).
CREATE POLICY "memberships_insert_owner"
  ON memberships FOR INSERT TO authenticated
  WITH CHECK (
    org_id IN (SELECT id FROM organizations WHERE owner_id::text = auth.uid()::text)
  );

-- Update/remove memberships only by org owners.
CREATE POLICY "memberships_update_owner"
  ON memberships FOR UPDATE TO authenticated
  USING (org_id IN (SELECT id FROM organizations WHERE owner_id::text = auth.uid()::text))
  WITH CHECK (org_id IN (SELECT id FROM organizations WHERE owner_id::text = auth.uid()::text));

CREATE POLICY "memberships_delete_owner"
  ON memberships FOR DELETE TO authenticated
  USING (org_id IN (SELECT id FROM organizations WHERE owner_id::text = auth.uid()::text));

-- -------------------------------------------------------------
-- 4) Projects (membership-scoped)
-- -------------------------------------------------------------
CREATE POLICY "projects_select_member"
  ON projects FOR SELECT TO authenticated
  USING (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text));

CREATE POLICY "projects_insert_member"
  ON projects FOR INSERT TO authenticated
  WITH CHECK (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text));

CREATE POLICY "projects_update_member"
  ON projects FOR UPDATE TO authenticated
  USING (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text))
  WITH CHECK (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text));

CREATE POLICY "projects_delete_owner"
  ON projects FOR DELETE TO authenticated
  USING (org_id IN (SELECT id FROM organizations WHERE owner_id::text = auth.uid()::text));

-- -------------------------------------------------------------
-- 5) Documents (membership-scoped)
-- -------------------------------------------------------------
CREATE POLICY "documents_select_member"
  ON documents FOR SELECT TO authenticated
  USING (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text));

CREATE POLICY "documents_insert_member"
  ON documents FOR INSERT TO authenticated
  WITH CHECK (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text));

CREATE POLICY "documents_update_member"
  ON documents FOR UPDATE TO authenticated
  USING (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text))
  WITH CHECK (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text));

CREATE POLICY "documents_delete_owner"
  ON documents FOR DELETE TO authenticated
  USING (org_id IN (SELECT id FROM organizations WHERE owner_id::text = auth.uid()::text));

-- -------------------------------------------------------------
-- 6) Chunks (scoped via parent document)
-- -------------------------------------------------------------
CREATE POLICY "chunks_select_member"
  ON chunks FOR SELECT TO authenticated
  USING (
    document_id IN (
      SELECT id FROM documents
      WHERE org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text)
    )
  );

-- Inserts are needed for ingestion (chunking + embedding) when using the caller's JWT.
CREATE POLICY "chunks_insert_member"
  ON chunks FOR INSERT TO authenticated
  WITH CHECK (
    document_id IN (
      SELECT id FROM documents
      WHERE org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text)
    )
  );

-- No UPDATE/DELETE policy for chunks (immutable by default).

-- -------------------------------------------------------------
-- 7) Runs (membership-scoped)
-- -------------------------------------------------------------
CREATE POLICY "runs_select_member"
  ON runs FOR SELECT TO authenticated
  USING (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text));

CREATE POLICY "runs_insert_member"
  ON runs FOR INSERT TO authenticated
  WITH CHECK (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text));

CREATE POLICY "runs_update_member"
  ON runs FOR UPDATE TO authenticated
  USING (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text))
  WITH CHECK (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text));

-- -------------------------------------------------------------
-- 8) Run Audits (membership-scoped)
-- -------------------------------------------------------------
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'run_audits') THEN
    EXECUTE 'CREATE POLICY "run_audits_select_member"
      ON run_audits FOR SELECT TO authenticated
      USING (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text))';

    EXECUTE 'CREATE POLICY "run_audits_insert_member"
      ON run_audits FOR INSERT TO authenticated
      WITH CHECK (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text))';

    EXECUTE 'CREATE POLICY "run_audits_update_member"
      ON run_audits FOR UPDATE TO authenticated
      USING (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text))
      WITH CHECK (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text))';
  END IF;
END $$;

-- -------------------------------------------------------------
-- 9) Exports (membership-scoped)
-- -------------------------------------------------------------
CREATE POLICY "exports_select_member"
  ON exports FOR SELECT TO authenticated
  USING (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text));

CREATE POLICY "exports_insert_member"
  ON exports FOR INSERT TO authenticated
  WITH CHECK (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text));

-- -------------------------------------------------------------
-- 10) Plans (public catalog for authenticated users)
-- -------------------------------------------------------------
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'plans') THEN
    EXECUTE 'CREATE POLICY "plans_select_authenticated"
      ON plans FOR SELECT TO authenticated
      USING (auth.role() = ''authenticated'')';
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- -------------------------------------------------------------
-- 11) Audit Events (membership-scoped)
-- -------------------------------------------------------------
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'audit_events') THEN
    EXECUTE 'CREATE POLICY "audit_events_select_member"
      ON audit_events FOR SELECT TO authenticated
      USING (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text))';

    EXECUTE 'CREATE POLICY "audit_events_insert_self"
      ON audit_events FOR INSERT TO authenticated
      WITH CHECK (
        org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text)
        AND user_id::text = auth.uid()::text
      )';
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- -------------------------------------------------------------
-- 12) Optional tables (best-effort)
-- -------------------------------------------------------------
-- Subscriptions: member-scoped read
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'subscriptions') THEN
    EXECUTE 'CREATE POLICY "subscriptions_select_member"
      ON subscriptions FOR SELECT TO authenticated
      USING (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text))';
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- Activities / Org usage: member-scoped read + write
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'activities') THEN
    EXECUTE 'CREATE POLICY "activities_select_member"
      ON activities FOR SELECT TO authenticated
      USING (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text))';
    EXECUTE 'CREATE POLICY "activities_insert_member"
      ON activities FOR INSERT TO authenticated
      WITH CHECK (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text))';
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'org_usage') THEN
    EXECUTE 'CREATE POLICY "org_usage_select_member"
      ON org_usage FOR SELECT TO authenticated
      USING (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text))';
    EXECUTE 'CREATE POLICY "org_usage_insert_member"
      ON org_usage FOR INSERT TO authenticated
      WITH CHECK (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text))';
    EXECUTE 'CREATE POLICY "org_usage_update_member"
      ON org_usage FOR UPDATE TO authenticated
      USING (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text))
      WITH CHECK (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text))';
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- Invites / Billing events: member-scoped reads (writes via service_role/admin)
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'invites') THEN
    EXECUTE 'CREATE POLICY "invites_select_member"
      ON invites FOR SELECT TO authenticated
      USING (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text))';
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'billing_events') THEN
    EXECUTE 'CREATE POLICY "billing_events_select_member"
      ON billing_events FOR SELECT TO authenticated
      USING (org_id IN (SELECT org_id FROM memberships WHERE user_id::text = auth.uid()::text))';
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- -------------------------------------------------------------
-- 13) Verify
-- -------------------------------------------------------------
SELECT tablename, policyname, cmd, qual, with_check
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN (
    'organizations', 'memberships', 'projects', 'documents', 'runs', 'run_audits',
    'exports', 'chunks', 'plans', 'audit_events', 'subscriptions', 'activities',
    'org_usage', 'invites', 'billing_events'
  )
ORDER BY tablename, policyname;
