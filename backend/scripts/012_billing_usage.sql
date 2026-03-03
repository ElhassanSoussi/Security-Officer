-- Subscription Plans and Usage Metrics Migration
-- Run in Supabase SQL Editor (once).

-- ─── 1. subscriptions ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subscriptions (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id              text NOT NULL,
  plan_name           text NOT NULL DEFAULT 'FREE'
                          CHECK (plan_name IN ('FREE', 'PRO', 'ENTERPRISE')),
  max_runs_per_month  integer NOT NULL DEFAULT 10,
  max_documents       integer NOT NULL DEFAULT 25,
  max_memory_entries  integer NOT NULL DEFAULT 100,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS subscriptions_org_idx ON subscriptions(org_id);

ALTER TABLE IF EXISTS subscriptions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS subscriptions_read_member ON subscriptions;
CREATE POLICY subscriptions_read_member
  ON subscriptions FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM memberships m
      WHERE m.org_id = subscriptions.org_id
        AND m.user_id = auth.uid()
    )
  );

-- ─── 2. usage_metrics ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS usage_metrics (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id       text NOT NULL,
  metric_type  text NOT NULL
                   CHECK (metric_type IN (
                     'RUN_CREATED',
                     'DOCUMENT_UPLOADED',
                     'MEMORY_STORED',
                     'EVIDENCE_GENERATED'
                   )),
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS usage_metrics_org_idx  ON usage_metrics(org_id);
CREATE INDEX IF NOT EXISTS usage_metrics_type_idx ON usage_metrics(org_id, metric_type);
CREATE INDEX IF NOT EXISTS usage_metrics_month_idx
  ON usage_metrics(org_id, date_trunc('month', created_at));

ALTER TABLE IF EXISTS usage_metrics ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS usage_metrics_read_member ON usage_metrics;
CREATE POLICY usage_metrics_read_member
  ON usage_metrics FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM memberships m
      WHERE m.org_id = usage_metrics.org_id
        AND m.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS usage_metrics_insert_member ON usage_metrics;
CREATE POLICY usage_metrics_insert_member
  ON usage_metrics FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM memberships m
      WHERE m.org_id = usage_metrics.org_id
        AND m.user_id = auth.uid()
    )
  );
