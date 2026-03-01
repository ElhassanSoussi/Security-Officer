-- Phase 3 Part 1: Deterministic Retrieval Engine — DB Migration
-- Run in Supabase SQL Editor (or via psql). Fully idempotent.

begin;

-- ---------------------------------------------------------------------------
-- 1. run_audits — add retrieval metadata columns
--    These columns capture deterministic retrieval context per answer.
-- ---------------------------------------------------------------------------
alter table if exists run_audits
  add column if not exists embedding_similarity_score float,
  add column if not exists chunk_id uuid,
  add column if not exists source_document_id uuid,
  add column if not exists token_count_used int,
  add column if not exists model_used text,
  add column if not exists generation_time_ms int,
  add column if not exists confidence_score float,
  add column if not exists confidence_reason text,
  add column if not exists retrieval_mode text;  -- 'standard' | 'strict'

-- Index for retrieval analytics (similarity-based queries)
create index if not exists idx_run_audits_similarity
  on run_audits (run_id, embedding_similarity_score desc nulls last);

-- ---------------------------------------------------------------------------
-- 2. audit_trail — immutable compliance audit log
--    NO DELETE policy. Every status change or answer edit is recorded.
-- ---------------------------------------------------------------------------
create table if not exists audit_trail (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null,
  project_id uuid,
  org_id uuid not null,
  audit_id uuid,                    -- FK to run_audits row being changed
  question_text text,
  previous_status text,
  new_status text,
  previous_answer text,
  new_answer text,
  user_id text not null,
  created_at timestamptz not null default now(),
  metadata jsonb default '{}'::jsonb
);

-- Index for querying by run and by project
create index if not exists idx_audit_trail_run
  on audit_trail (run_id, created_at desc);

create index if not exists idx_audit_trail_project
  on audit_trail (project_id, created_at desc) where project_id is not null;

create index if not exists idx_audit_trail_org
  on audit_trail (org_id, created_at desc);

-- Enable RLS
alter table if exists audit_trail enable row level security;

-- RLS: members can read audit trail in their org
drop policy if exists "audit_trail_select_member" on audit_trail;
create policy "audit_trail_select_member"
  on audit_trail for select to authenticated
  using (
    exists (
      select 1 from memberships m
      where m.org_id = audit_trail.org_id
        and m.user_id::text = auth.uid()::text
    )
  );

-- RLS: members can insert into audit trail (logging)
drop policy if exists "audit_trail_insert_member" on audit_trail;
create policy "audit_trail_insert_member"
  on audit_trail for insert to authenticated
  with check (
    exists (
      select 1 from memberships m
      where m.org_id = audit_trail.org_id
        and m.user_id::text = auth.uid()::text
    )
  );

-- CRITICAL: NO DELETE policy on audit_trail. This is intentional.
-- The audit trail must be immutable for compliance.

-- NO UPDATE policy on audit_trail either. Append-only.

-- Service-role bypass for admin operations
drop policy if exists "audit_trail_service_role" on audit_trail;
create policy "audit_trail_service_role"
  on audit_trail for all to service_role
  using (true)
  with check (true);

-- ---------------------------------------------------------------------------
-- 3. Update match_chunks RPC to return chunk_id (already present but ensure)
--    The existing RPC already returns chunk_id = c.id. No change needed.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- 4. retrieval_config — per-org retrieval settings (optional override)
-- ---------------------------------------------------------------------------
create table if not exists retrieval_config (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations(id) on delete cascade,
  similarity_threshold float not null default 0.55,
  top_k int not null default 5,
  strict_mode boolean not null default false,
  retrieval_debug boolean not null default false,
  model_name text not null default 'gpt-4-turbo',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (org_id)
);

alter table if exists retrieval_config enable row level security;

drop policy if exists "retrieval_config_select_member" on retrieval_config;
create policy "retrieval_config_select_member"
  on retrieval_config for select to authenticated
  using (
    exists (
      select 1 from memberships m
      where m.org_id = retrieval_config.org_id
        and m.user_id::text = auth.uid()::text
    )
  );

drop policy if exists "retrieval_config_upsert_member" on retrieval_config;
create policy "retrieval_config_upsert_member"
  on retrieval_config for insert to authenticated
  with check (
    exists (
      select 1 from memberships m
      where m.org_id = retrieval_config.org_id
        and m.user_id::text = auth.uid()::text
    )
  );

drop policy if exists "retrieval_config_update_member" on retrieval_config;
create policy "retrieval_config_update_member"
  on retrieval_config for update to authenticated
  using (
    exists (
      select 1 from memberships m
      where m.org_id = retrieval_config.org_id
        and m.user_id::text = auth.uid()::text
    )
  );

drop policy if exists "retrieval_config_service_role" on retrieval_config;
create policy "retrieval_config_service_role"
  on retrieval_config for all to service_role
  using (true)
  with check (true);

commit;
