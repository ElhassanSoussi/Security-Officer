-- Phase 22: Sales Engine — Database Migration
-- Creates tables and indexes for lead capture, demo workspace, and trial tracking.

-- ── sales_leads table ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sales_leads (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name TEXT NOT NULL DEFAULT '',
    contact_name TEXT NOT NULL DEFAULT '',
    email       TEXT NOT NULL DEFAULT '',
    phone       TEXT DEFAULT '',
    company_size TEXT DEFAULT '',
    message     TEXT DEFAULT '',
    source      TEXT NOT NULL DEFAULT 'contact_form',
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sales_leads_created ON sales_leads (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sales_leads_source  ON sales_leads (source);

-- Grant service role access
ALTER TABLE sales_leads ENABLE ROW LEVEL SECURITY;

-- Service role can do everything; no user-level RLS needed (admin endpoints only)
CREATE POLICY IF NOT EXISTS "service_role_all_sales_leads"
    ON sales_leads
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- Allow anonymous inserts for the public contact form
CREATE POLICY IF NOT EXISTS "anon_insert_sales_leads"
    ON sales_leads
    FOR INSERT
    WITH CHECK (true);
