-- Multi-Run Intelligence and Institutional Memory Engine — DB Migration
-- Run in Supabase SQL Editor (or via psql). Fully idempotent.

begin;

-- ---------------------------------------------------------------------------
-- 1. question_embeddings — Institutional memory: approved Q&A pairs with embeddings
--    When a question is approved, its embedding + answer are stored here.
--    On future runs, we search for similar questions to reuse approved answers.
-- ---------------------------------------------------------------------------
create table if not exists question_embeddings (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null,
  project_id uuid,
  run_id uuid not null,
  audit_id uuid not null,               -- FK to run_audits row that was approved
  question_text text not null,
  answer_text text not null,
  embedding vector(1536),                -- OpenAI text-embedding-3-small
  source_document text,
  source_excerpt text,
  confidence_score float,
  similarity_score float,                -- Original retrieval similarity when first answered
  review_status text not null default 'approved',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Index for fast vector similarity search within an org
create index if not exists idx_question_embeddings_org
  on question_embeddings (org_id);

create index if not exists idx_question_embeddings_project
  on question_embeddings (org_id, project_id) where project_id is not null;

-- IVFFlat index for embedding similarity search
-- (Only create if the table has rows; on empty table, ivfflat needs at least 100 rows.
--  We use a simple btree on org_id instead and rely on exact search for small datasets.)
-- For production with many rows, run:
--   CREATE INDEX idx_question_embeddings_vector ON question_embeddings
--     USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

-- Enable RLS
alter table if exists question_embeddings enable row level security;

-- RLS: members can read approved Q&A in their org
drop policy if exists "question_embeddings_select_member" on question_embeddings;
create policy "question_embeddings_select_member"
  on question_embeddings for select to authenticated
  using (
    exists (
      select 1 from memberships m
      where m.org_id = question_embeddings.org_id
        and m.user_id::text = auth.uid()::text
    )
  );

-- RLS: members can insert into question_embeddings (storing approved answers)
drop policy if exists "question_embeddings_insert_member" on question_embeddings;
create policy "question_embeddings_insert_member"
  on question_embeddings for insert to authenticated
  with check (
    exists (
      select 1 from memberships m
      where m.org_id = question_embeddings.org_id
        and m.user_id::text = auth.uid()::text
    )
  );

-- RLS: members can update (e.g., re-approve with new answer)
drop policy if exists "question_embeddings_update_member" on question_embeddings;
create policy "question_embeddings_update_member"
  on question_embeddings for update to authenticated
  using (
    exists (
      select 1 from memberships m
      where m.org_id = question_embeddings.org_id
        and m.user_id::text = auth.uid()::text
    )
  );

-- Service-role bypass
drop policy if exists "question_embeddings_service_role" on question_embeddings;
create policy "question_embeddings_service_role"
  on question_embeddings for all to service_role
  using (true)
  with check (true);

-- ---------------------------------------------------------------------------
-- 2. RPC: match_question_embeddings — search for similar approved Q&A pairs
-- ---------------------------------------------------------------------------
create or replace function match_question_embeddings(
  query_embedding vector(1536),
  match_threshold float,
  match_count int,
  filter_org_id uuid,
  filter_project_id uuid default null
)
returns table (
  id uuid,
  question_text text,
  answer_text text,
  source_document text,
  source_excerpt text,
  confidence_score float,
  similarity float,
  run_id uuid,
  audit_id uuid,
  project_id uuid
)
language plpgsql
as $$
begin
  return query
  select
    qe.id,
    qe.question_text,
    qe.answer_text,
    qe.source_document,
    qe.source_excerpt,
    qe.confidence_score,
    1 - (qe.embedding <=> query_embedding) as similarity,
    qe.run_id,
    qe.audit_id,
    qe.project_id
  from question_embeddings qe
  where 1 - (qe.embedding <=> query_embedding) > match_threshold
    and qe.org_id = filter_org_id
    and qe.review_status = 'approved'
    and (
      filter_project_id is null
      or qe.project_id = filter_project_id
      or qe.project_id is null  -- org-wide approved answers are always searchable
    )
  order by qe.embedding <=> query_embedding
  limit match_count;
end;
$$;

-- ---------------------------------------------------------------------------
-- 3. run_audits — add columns for answer reuse + delta tracking
-- ---------------------------------------------------------------------------
alter table if exists run_audits
  add column if not exists answer_origin text default 'generated',  -- 'generated' | 'reused' | 'suggested'
  add column if not exists reused_from_question_id uuid,            -- FK to question_embeddings.id
  add column if not exists reuse_similarity_score float,            -- similarity to reused question
  add column if not exists change_type text;                        -- 'NEW' | 'MODIFIED' | 'UNCHANGED' (delta tracking)

-- Index for delta tracking queries
create index if not exists idx_run_audits_change_type
  on run_audits (run_id, change_type) where change_type is not null;

-- Index for reuse analytics
create index if not exists idx_run_audits_answer_origin
  on run_audits (run_id, answer_origin) where answer_origin is not null;

-- ---------------------------------------------------------------------------
-- 4. runs — add previous_run_id for delta tracking lineage
-- ---------------------------------------------------------------------------
alter table if exists runs
  add column if not exists previous_run_id uuid;  -- FK to runs.id for delta comparison

commit;
