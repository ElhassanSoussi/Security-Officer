-- Institutional Knowledge Memory System
-- Apply once against your Supabase project.

create table if not exists knowledge_memory (
    id               uuid primary key default gen_random_uuid(),
    organization_id  uuid not null,
    question_text    text not null,
    answer_text      text not null,
    embedding        vector(1536),
    confidence       float not null default 0.0,
    source_run_id    uuid references runs(id) on delete set null,
    approved_by      uuid,
    created_at       timestamp with time zone default timezone('utc', now()) not null,
    updated_at       timestamp with time zone default timezone('utc', now()) not null
);

create table if not exists memory_matches (
    id                uuid primary key default gen_random_uuid(),
    question_text     text not null,
    matched_memory_id uuid not null references knowledge_memory(id) on delete cascade,
    similarity_score  float not null,
    used_in_run       uuid references runs(id) on delete set null,
    created_at        timestamp with time zone default timezone('utc', now()) not null
);

create index if not exists knowledge_memory_org_idx
    on knowledge_memory (organization_id);

create index if not exists knowledge_memory_run_idx
    on knowledge_memory (source_run_id);

create index if not exists memory_matches_memory_id_idx
    on memory_matches (matched_memory_id);

create index if not exists memory_matches_run_idx
    on memory_matches (used_in_run);

alter table knowledge_memory enable row level security;
alter table memory_matches enable row level security;

create policy "org members can read knowledge_memory"
    on knowledge_memory for select
    using (
        organization_id::text in (
            select org_id from org_members where user_id = auth.uid()
        )
    );

create policy "service role can write knowledge_memory"
    on knowledge_memory for all
    to service_role
    using (true)
    with check (true);

create policy "org members can read memory_matches"
    on memory_matches for select
    using (
        exists (
            select 1 from knowledge_memory km
            join org_members om on om.org_id = km.organization_id::text
            where km.id = memory_matches.matched_memory_id
              and om.user_id = auth.uid()
        )
    );

create policy "service role can write memory_matches"
    on memory_matches for all
    to service_role
    using (true)
    with check (true);

create or replace function match_knowledge_memory(
    query_embedding   vector(1536),
    match_threshold   float,
    match_count       int,
    filter_org_id     uuid
)
returns table (
    id               uuid,
    question_text    text,
    answer_text      text,
    confidence       float,
    source_run_id    uuid,
    approved_by      uuid,
    similarity       float,
    created_at       timestamptz
)
language sql stable
as $$
    select
        km.id,
        km.question_text,
        km.answer_text,
        km.confidence,
        km.source_run_id,
        km.approved_by,
        1 - (km.embedding <=> query_embedding) as similarity,
        km.created_at
    from knowledge_memory km
    where km.organization_id = filter_org_id
      and km.embedding is not null
      and 1 - (km.embedding <=> query_embedding) >= match_threshold
    order by km.embedding <=> query_embedding
    limit match_count;
$$;
