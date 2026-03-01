-- =============================================
-- RLS Migration — FIXED TYPE CASTING
-- Paste this ENTIRE block and click Run
-- =============================================

-- 1. Drop overly-permissive INSERT policies
DROP POLICY IF EXISTS "authenticated_can_insert_orgs" ON organizations;
DROP POLICY IF EXISTS "authenticated_can_insert_memberships" ON memberships;
DO $$ BEGIN
  EXECUTE 'DROP POLICY IF EXISTS \"authenticated_can_insert_subscriptions\" ON subscriptions';
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- 2. Enable RLS on all tenant tables
ALTER TABLE IF EXISTS organizations   ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS memberships     ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS projects        ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS documents       ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS runs            ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS exports         ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS chunks          ENABLE ROW LEVEL SECURITY;

-- 3. Organizations: only owner can INSERT
DROP POLICY IF EXISTS "org_insert_owner_only" ON organizations;
CREATE POLICY "org_insert_owner_only"
  ON organizations FOR INSERT TO authenticated
  WITH CHECK (owner_id::text = auth.uid()::text);

-- 4. Memberships: org owners can add members, users can add self
DROP POLICY IF EXISTS "membership_insert_by_owner" ON memberships;
CREATE POLICY "membership_insert_by_owner"
  ON memberships FOR INSERT TO authenticated
  WITH CHECK (
    org_id::text IN (SELECT id::text FROM organizations WHERE owner_id::text = auth.uid()::text)
    OR user_id::text = auth.uid()::text
  );

-- 5. Documents: membership-scoped
DROP POLICY IF EXISTS "doc_select_member" ON documents;
CREATE POLICY "doc_select_member"
  ON documents FOR SELECT TO authenticated
  USING (org_id::text IN (SELECT org_id::text FROM memberships WHERE user_id::text = auth.uid()::text));

DROP POLICY IF EXISTS "doc_insert_member" ON documents;
CREATE POLICY "doc_insert_member"
  ON documents FOR INSERT TO authenticated
  WITH CHECK (org_id::text IN (SELECT org_id::text FROM memberships WHERE user_id::text = auth.uid()::text));

DROP POLICY IF EXISTS "doc_update_member" ON documents;
CREATE POLICY "doc_update_member"
  ON documents FOR UPDATE TO authenticated
  USING (org_id::text IN (SELECT org_id::text FROM memberships WHERE user_id::text = auth.uid()::text))
  WITH CHECK (org_id::text IN (SELECT org_id::text FROM memberships WHERE user_id::text = auth.uid()::text));

-- 6. Runs: membership-scoped
DROP POLICY IF EXISTS "run_select_member" ON runs;
CREATE POLICY "run_select_member"
  ON runs FOR SELECT TO authenticated
  USING (org_id::text IN (SELECT org_id::text FROM memberships WHERE user_id::text = auth.uid()::text));

DROP POLICY IF EXISTS "run_insert_member" ON runs;
CREATE POLICY "run_insert_member"
  ON runs FOR INSERT TO authenticated
  WITH CHECK (org_id::text IN (SELECT org_id::text FROM memberships WHERE user_id::text = auth.uid()::text));

DROP POLICY IF EXISTS "run_update_member" ON runs;
CREATE POLICY "run_update_member"
  ON runs FOR UPDATE TO authenticated
  USING (org_id::text IN (SELECT org_id::text FROM memberships WHERE user_id::text = auth.uid()::text))
  WITH CHECK (org_id::text IN (SELECT org_id::text FROM memberships WHERE user_id::text = auth.uid()::text));

-- 7. Exports: membership-scoped
DROP POLICY IF EXISTS "export_select_member" ON exports;
CREATE POLICY "export_select_member"
  ON exports FOR SELECT TO authenticated
  USING (org_id::text IN (SELECT org_id::text FROM memberships WHERE user_id::text = auth.uid()::text));

DROP POLICY IF EXISTS "export_insert_member" ON exports;
CREATE POLICY "export_insert_member"
  ON exports FOR INSERT TO authenticated
  WITH CHECK (org_id::text IN (SELECT org_id::text FROM memberships WHERE user_id::text = auth.uid()::text));

-- 8. Chunks: membership-scoped reads only
DROP POLICY IF EXISTS "chunk_select_member" ON chunks;
CREATE POLICY "chunk_select_member"
  ON chunks FOR SELECT TO authenticated
  USING (
    document_id::text IN (
      SELECT id::text FROM documents
      WHERE org_id::text IN (SELECT org_id::text FROM memberships WHERE user_id::text = auth.uid()::text)
    )
  );

-- 9. Verify
SELECT tablename, policyname, cmd
FROM pg_policies
WHERE tablename IN (
  'organizations', 'memberships', 'projects', 'documents',
  'runs', 'exports', 'chunks'
)
ORDER BY tablename, policyname;
