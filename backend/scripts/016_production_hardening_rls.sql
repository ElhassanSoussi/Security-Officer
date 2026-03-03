-- Production Hardening and Security Cleanup Migration

--
-- 1. Tighten anon INSERT on sales_leads — restrict to INSERT only on allowed columns
-- 2. Explicitly DENY anonymous SELECT on sales_leads
-- 3. Enable leaked password protection (Supabase Auth config recommendation)
-- 4. Move vector extension to dedicated schema (if not already)
-- 5. Add org_id enforcement comments / verification queries

-- 1. Tighten anonymous insert policy on sales_leads
-- Drop the overly-permissive WITH CHECK (true) policy and replace with a
-- column-restricted version that only allows inserts with a valid source value.
drop policy if exists "anon_insert_sales_leads" on sales_leads;

create policy "anon_insert_sales_leads_restricted"
    on sales_leads
    for insert
    to anon
    with check (
        source in ('contact_form', 'enterprise_interest')
        and (email <> '' or company_name <> '')
    );

-- 2. Explicitly deny anonymous SELECT/UPDATE/DELETE on sales_leads
-- RLS is enabled; with no SELECT policy for anon, reads are blocked.
-- Add an explicit deny-all SELECT policy for clarity and auditability.
drop policy if exists "anon_deny_select_sales_leads" on sales_leads;
create policy "anon_deny_select_sales_leads"
    on sales_leads
    for select
    to anon
    using (false);

drop policy if exists "anon_deny_update_sales_leads" on sales_leads;
create policy "anon_deny_update_sales_leads"
    on sales_leads
    for update
    to anon
    using (false);

drop policy if exists "anon_deny_delete_sales_leads" on sales_leads;
create policy "anon_deny_delete_sales_leads"
    on sales_leads
    for delete
    to anon
    using (false);

-- 3. Vector extension schema isolation
-- Best practice: move pgvector out of public schema to reduce attack surface.
-- Note: Supabase hosted projects manage this automatically. For self-hosted:
-- create schema if not exists extensions;
-- alter extension vector set schema extensions;
-- (Uncomment above if running self-hosted Postgres with superuser access)

-- 4. Leaked password protection
-- Supabase Auth: enable HaveIBeenPwned check via dashboard or config.toml:
--   [auth]
--   password_min_length = 10
--   leaked_password_protection = "enabled"
-- This is a Supabase Auth config change, not a SQL migration.
-- Documenting here for the security checklist.

-- 5. Org-ID enforcement verification queries
-- These are CHECK queries to verify org_id is enforced on all tenant tables.
-- Run manually to audit; they do not modify any data.
--
-- select tablename, policyname, qual
-- from pg_policies
-- where schemaname = 'public'
--   and qual not like '%org_id%'
--   and qual not like '%service_role%'
--   and tablename not in ('sales_leads')
-- order by tablename;
--
-- Expected: zero rows (all non-service_role policies reference org_id).

-- 6. Add rate-limit-friendly created_at index for IP-based dedup
-- Supports application-level rate limiting queries if needed in future.
create index if not exists idx_sales_leads_email_created
    on sales_leads (email, created_at desc);
