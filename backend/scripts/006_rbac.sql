-- Role-Based Access Control Migration
-- Run with: psql $DATABASE_URL -f 006_rbac.sql
-- Or apply via Supabase SQL Editor.

-- 1. Normalize any legacy 'manager' roles to 'compliance_manager'
UPDATE memberships
SET role = 'compliance_manager'
WHERE role = 'manager';

-- 2. Add CHECK constraint on role column (idempotent via DO block)
DO $$
BEGIN
    -- Drop old constraint if it exists (schema may have evolved)
    BEGIN
        ALTER TABLE memberships DROP CONSTRAINT IF EXISTS memberships_role_check;
    EXCEPTION WHEN undefined_object THEN
        NULL;
    END;

    ALTER TABLE memberships
        ADD CONSTRAINT memberships_role_check
        CHECK (role IN ('owner', 'admin', 'compliance_manager', 'reviewer', 'viewer'));
EXCEPTION WHEN duplicate_object THEN
    NULL; -- constraint already exists
END;
$$;

-- 3. Default role for new memberships is 'viewer'
ALTER TABLE memberships ALTER COLUMN role SET DEFAULT 'viewer';

-- 4. Add index on memberships for faster role lookups (idempotent)
CREATE INDEX IF NOT EXISTS idx_memberships_org_user
    ON memberships (org_id, user_id);

-- 5. RLS policy: users can read their own memberships
-- (Ensure this doesn't conflict with existing policies)
DO $$
BEGIN
    DROP POLICY IF EXISTS "Users can read own memberships" ON memberships;
    CREATE POLICY "Users can read own memberships"
        ON memberships FOR SELECT
        USING (user_id = auth.uid()::text);
EXCEPTION WHEN undefined_table THEN
    NULL; -- table doesn't exist in this env
END;
$$;

-- Verify
SELECT role, count(*) FROM memberships GROUP BY role ORDER BY role;
