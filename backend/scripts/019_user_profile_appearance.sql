-- User Profile & Appearance (idempotent)
-- Adds a user_profiles table for display name, avatar, public email, and theme preference.
-- RLS: each user can only read/write their own row.

BEGIN;

CREATE TABLE IF NOT EXISTS user_profiles (
  user_id uuid PRIMARY KEY,
  display_name text,
  avatar_url text,
  public_email text,
  theme_preference text NOT NULL DEFAULT 'system',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chk_theme_preference CHECK (theme_preference IN ('light', 'dark', 'system'))
);

-- RLS
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS user_profiles_select_own ON user_profiles;
CREATE POLICY user_profiles_select_own ON user_profiles
  FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS user_profiles_insert_own ON user_profiles;
CREATE POLICY user_profiles_insert_own ON user_profiles
  FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS user_profiles_update_own ON user_profiles;
CREATE POLICY user_profiles_update_own ON user_profiles
  FOR UPDATE USING (auth.uid() = user_id);

-- Service-role bypass (admin operations)
DROP POLICY IF EXISTS user_profiles_service_role ON user_profiles;
CREATE POLICY user_profiles_service_role ON user_profiles
  FOR ALL USING (current_setting('request.jwt.claim.role', true) = 'service_role');

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles (user_id);

-- Auto-update updated_at on changes
CREATE OR REPLACE FUNCTION update_user_profiles_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_profiles_updated_at ON user_profiles;
CREATE TRIGGER trg_user_profiles_updated_at
  BEFORE UPDATE ON user_profiles
  FOR EACH ROW EXECUTE FUNCTION update_user_profiles_updated_at();

COMMIT;
