-- Billing events schema for local/Supabase environments
-- Safe to run multiple times.

create table if not exists billing_events (
  id uuid primary key default gen_random_uuid(),
  org_id uuid,
  stripe_event_id text unique,
  type text,
  raw_payload jsonb,
  created_at timestamptz default now()
);

-- Indexes for lookup
create index if not exists idx_billing_events_org_id on billing_events(org_id);
create index if not exists idx_billing_events_stripe_event on billing_events(stripe_event_id);

-- Enable RLS
alter table billing_events enable row level security;

-- Policies: authenticated users in org can read; service role can write via default bypass.
drop policy if exists "billing_events_select_member" on billing_events;
create policy "billing_events_select_member"
  on billing_events
  for select
  to authenticated
  using (
    org_id is null
    or exists (
      select 1 from memberships m
      where m.org_id = billing_events.org_id
        and m.user_id = auth.uid()
    )
  );

-- Optional insert policy for authenticated org members (most writes happen via service role)
drop policy if exists "billing_events_insert_member" on billing_events;
create policy "billing_events_insert_member"
  on billing_events
  for insert
  to authenticated
  with check (
    org_id is null
    or exists (
      select 1 from memberships m
      where m.org_id = billing_events.org_id
        and m.user_id = auth.uid()
    )
  );
