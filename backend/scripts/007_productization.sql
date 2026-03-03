-- Productization: Project Onboarding and Production Indexes Migration
-- Safe: all operations are idempotent (IF NOT EXISTS)

-- ═══════════════════════════════════════════════════════════════════════════════
-- Project Onboarding Checklist
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS project_onboarding (
  project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  step          TEXT NOT NULL,
  completed_by  UUID,
  completed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, step)
);

ALTER TABLE project_onboarding ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'project_onboarding' AND policyname = 'project_onboarding_org_access'
  ) THEN
    CREATE POLICY project_onboarding_org_access ON project_onboarding
      FOR ALL USING (
        project_id IN (
          SELECT p.id FROM projects p
          JOIN memberships m ON m.org_id = p.org_id
          WHERE m.user_id = auth.uid()
        )
      );
  END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- Performance indexes for overview queries
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_runs_project_created
  ON runs (project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_run_audits_project_review
  ON run_audits (project_id, review_status);

CREATE INDEX IF NOT EXISTS idx_project_documents_project
  ON project_documents (project_id);
