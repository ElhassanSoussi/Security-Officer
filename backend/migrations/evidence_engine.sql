-- Evidence-Based Answer Engine — database additions
-- Apply once against your Supabase project.

-- ─── document_chunks view ────────────────────────────────────────────────────
-- Provides the requested interface over the existing `chunks` table, mapping
-- the `content` column to `chunk_text` without duplicating storage.

create or replace view document_chunks as
select
    id,
    document_id,
    content          as chunk_text,
    embedding,
    page_number,
    created_at
from chunks;

-- ─── generated_answers table ─────────────────────────────────────────────────
-- One row per question per run. Written immediately after answer generation.

create table if not exists generated_answers (
    id              uuid primary key default gen_random_uuid(),
    run_id          uuid not null references runs(id) on delete cascade,
    org_id          text not null,
    question_text   text not null,
    answer_text     text not null default '',
    confidence      float not null default 0.0,
    source_document text,
    page_number     integer,
    source_excerpt  text,
    needs_review    boolean not null default false,
    created_at      timestamp with time zone default timezone('utc', now()) not null
);

create index if not exists generated_answers_run_id_idx
    on generated_answers (run_id);

create index if not exists generated_answers_org_id_idx
    on generated_answers (org_id);

create index if not exists generated_answers_needs_review_idx
    on generated_answers (run_id, needs_review)
    where needs_review = true;

-- Row-level security: org members can read/write their own org's rows.
alter table generated_answers enable row level security;

create policy "org members can read generated_answers"
    on generated_answers for select
    using (
        org_id in (
            select org_id from org_members where user_id = auth.uid()
        )
    );

create policy "service role can write generated_answers"
    on generated_answers for all
    to service_role
    using (true)
    with check (true);
