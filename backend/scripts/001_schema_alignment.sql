-- Phase 1B schema alignment (idempotent)
-- Purpose: eliminate drift warnings in local/prod by aligning the DB schema
-- with current backend expectations used by Settings, Audit, Runs, and Billing.
--
-- Run in Supabase SQL Editor (or via psql) before restarting the backend.

begin;

-- ---------------------------------------------------------------------------
-- Organizations (settings + plan metadata)
-- ---------------------------------------------------------------------------
alter table if exists organizations
  add column if not exists plan_tier text not null default 'starter';

alter table if exists organizations
  add column if not exists trade_type text;

alter table if exists organizations
  add column if not exists company_size text;

-- ---------------------------------------------------------------------------
-- Usage tracking (entitlements / billing summary)
-- ---------------------------------------------------------------------------
create table if not exists org_usage (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations(id) on delete cascade,
  period_start timestamptz not null,
  questionnaires_used int not null default 0,
  exports_used int not null default 0,
  storage_used_bytes bigint not null default 0,
  created_at timestamptz not null default now(),
  unique (org_id, period_start)
);

create index if not exists idx_org_usage_org_period on org_usage (org_id, period_start desc);

alter table if exists org_usage enable row level security;

drop policy if exists "org_usage_select_member" on org_usage;
create policy "org_usage_select_member"
  on org_usage for select to authenticated
  using (
    exists (
      select 1 from memberships m
      where m.org_id = org_usage.org_id
        and m.user_id::text = auth.uid()::text
    )
  );

drop policy if exists "org_usage_insert_member" on org_usage;
create policy "org_usage_insert_member"
  on org_usage for insert to authenticated
  with check (
    exists (
      select 1 from memberships m
      where m.org_id = org_usage.org_id
        and m.user_id::text = auth.uid()::text
    )
  );

drop policy if exists "org_usage_update_member" on org_usage;
create policy "org_usage_update_member"
  on org_usage for update to authenticated
  using (
    exists (
      select 1 from memberships m
      where m.org_id = org_usage.org_id
        and m.user_id::text = auth.uid()::text
    )
  )
  with check (true);

-- ---------------------------------------------------------------------------
-- Audit events (best-effort writes should have a real table)
-- ---------------------------------------------------------------------------
create table if not exists audit_events (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations(id) on delete cascade,
  user_id text not null,
  event_type text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_audit_events_org_created_at
  on audit_events (org_id, created_at desc);

alter table if exists audit_events enable row level security;

drop policy if exists "audit_events_select_member" on audit_events;
create policy "audit_events_select_member"
  on audit_events for select to authenticated
  using (
    exists (
      select 1 from memberships m
      where m.org_id = audit_events.org_id
        and m.user_id::text = auth.uid()::text
    )
  );

drop policy if exists "audit_events_insert_member" on audit_events;
create policy "audit_events_insert_member"
  on audit_events for insert to authenticated
  with check (
    exists (
      select 1 from memberships m
      where m.org_id = audit_events.org_id
        and m.user_id::text = auth.uid()::text
    )
  );

-- ---------------------------------------------------------------------------
-- Billing events (deep health / billing integration)
-- ---------------------------------------------------------------------------
create table if not exists billing_events (
  id uuid primary key default gen_random_uuid(),
  org_id uuid references organizations(id) on delete set null,
  stripe_event_id text unique,
  type text,
  raw_payload jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_billing_events_org_id on billing_events (org_id);
create index if not exists idx_billing_events_created_at on billing_events (created_at desc);

alter table if exists billing_events enable row level security;

drop policy if exists "billing_events_select_member" on billing_events;
create policy "billing_events_select_member"
  on billing_events for select to authenticated
  using (
    org_id is null
    or exists (
      select 1 from memberships m
      where m.org_id = billing_events.org_id
        and m.user_id::text = auth.uid()::text
    )
  );

drop policy if exists "billing_events_insert_member" on billing_events;
create policy "billing_events_insert_member"
  on billing_events for insert to authenticated
  with check (
    org_id is null
    or exists (
      select 1 from memberships m
      where m.org_id = billing_events.org_id
        and m.user_id::text = auth.uid()::text
    )
  );

-- ---------------------------------------------------------------------------
-- Runs / Exports / Run Audits columns used by current backend code
-- ---------------------------------------------------------------------------
alter table if exists runs
  add column if not exists progress int,
  add column if not exists error_message text,
  add column if not exists updated_at timestamptz,
  add column if not exists completed_at timestamptz,
  add column if not exists output_filename text,
  add column if not exists export_filename text;

alter table if exists exports
  add column if not exists size_bytes bigint,
  add column if not exists storage_path text,
  add column if not exists error_message text;

alter table if exists run_audits
  add column if not exists sheet_name text,
  add column if not exists original_answer text,
  add column if not exists source_document text,
  add column if not exists page_number text,
  add column if not exists is_overridden boolean not null default false;

commit;
