-- Phase 15: Compliance Intelligence + Institutional Memory
-- Apply in Supabase SQL Editor or via: psql "$DATABASE_URL" -f this_file.sql

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Institutional Answer Memory
--    Stores canonical approved answers keyed by normalized question hash.
--    Checked BEFORE retrieval/generation on each analyze-excel call.
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists institutional_answers (
  id                       uuid primary key default gen_random_uuid(),
  org_id                   text not null,
  normalized_question_hash text not null,   -- sha256 hex of lowercased/stripped question
  canonical_question_text  text not null,
  canonical_answer         text not null,
  confidence_level         text not null default 'MEDIUM' check (confidence_level in ('HIGH','MEDIUM','LOW')),
  source_doc_ids           text[] default '{}',
  use_count                integer not null default 1,
  last_used_at             timestamptz not null default now(),
  created_at               timestamptz not null default now()
);

-- Unique constraint: one canonical answer per (org, question hash)
create unique index if not exists institutional_answers_org_hash_uniq
  on institutional_answers(org_id, normalized_question_hash);

-- Fast lookup index
create index if not exists institutional_answers_org_idx
  on institutional_answers(org_id);

-- RLS
alter table institutional_answers enable row level security;

drop policy if exists "institutional_answers_org_member" on institutional_answers;
create policy "institutional_answers_org_member"
  on institutional_answers
  using (
    exists (
      select 1 from memberships m
      where m.org_id = institutional_answers.org_id
        and m.user_id = auth.uid()
    )
    or
    exists (
      select 1 from organizations o
      where o.id = institutional_answers.org_id
        and o.owner_id = auth.uid()
    )
  );

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Add reused_from_memory flag to run_audits (safe: IF NOT EXISTS pattern)
-- ─────────────────────────────────────────────────────────────────────────────

do $$
begin
  if not exists (
    select 1 from information_schema.columns
    where table_name = 'run_audits' and column_name = 'reused_from_memory'
  ) then
    alter table run_audits add column reused_from_memory boolean not null default false;
  end if;
end $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Compliance Health View — per-run aggregated stats for trend charts
-- ─────────────────────────────────────────────────────────────────────────────

create or replace view compliance_run_stats as
select
  r.id                                                      as run_id,
  r.org_id,
  r.project_id,
  r.questionnaire_filename,
  r.created_at,
  count(a.id)                                               as total_questions,
  count(a.id) filter (where lower(a.confidence_score::text) = 'high'
    or (a.confidence_score ~ '^[0-9.]+$' and a.confidence_score::float >= 0.8))  as high_conf,
  count(a.id) filter (where lower(a.confidence_score::text) = 'medium'
    or (a.confidence_score ~ '^[0-9.]+$'
        and a.confidence_score::float >= 0.5
        and a.confidence_score::float < 0.8))               as medium_conf,
  count(a.id) filter (where lower(a.confidence_score::text) = 'low'
    or (a.confidence_score ~ '^[0-9.]+$' and a.confidence_score::float < 0.5))  as low_conf,
  count(a.id) filter (where a.review_status = 'approved')   as approved,
  count(a.id) filter (where a.review_status = 'rejected')   as rejected,
  count(a.id) filter (where a.review_status = 'pending'
    or a.review_status is null)                             as pending,
  count(a.id) filter (where a.reused_from_memory = true)    as memory_reused
from runs r
left join run_audits a on a.run_id = r.id
group by r.id, r.org_id, r.project_id, r.questionnaire_filename, r.created_at;
