-- Compliance Intelligence Engine — Database Migration
-- Apply via: psql "$DATABASE_URL" -f 022_compliance_engine.sql
-- Or paste into Supabase SQL Editor.

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. compliance_scores
--    One row per project per scoring run. Latest row = current score.
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists compliance_scores (
  id           uuid primary key default gen_random_uuid(),
  org_id       text not null,
  project_id   uuid not null references projects(id) on delete cascade,
  overall_score integer not null check (overall_score >= 0 and overall_score <= 100),
  risk_level   text not null check (risk_level in ('low', 'medium', 'high')),
  created_at   timestamptz not null default now()
);

create index if not exists compliance_scores_project_idx
  on compliance_scores(project_id, created_at desc);

create index if not exists compliance_scores_org_idx
  on compliance_scores(org_id, created_at desc);

alter table compliance_scores enable row level security;

drop policy if exists "compliance_scores_org_member" on compliance_scores;
create policy "compliance_scores_org_member"
  on compliance_scores
  using (
    exists (
      select 1 from memberships m
      where m.org_id = compliance_scores.org_id
        and m.user_id = auth.uid()
    )
    or exists (
      select 1 from organizations o
      where o.id = compliance_scores.org_id
        and o.owner_id = auth.uid()
    )
  );


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. compliance_issues
--    One row per detected compliance issue on a project.
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists compliance_issues (
  id           uuid primary key default gen_random_uuid(),
  org_id       text not null,
  project_id   uuid not null references projects(id) on delete cascade,
  issue_type   text not null,
  severity     text not null check (severity in ('low', 'medium', 'high')),
  description  text not null,
  status       text not null default 'open' check (status in ('open', 'resolved')),
  created_at   timestamptz not null default now()
);

create index if not exists compliance_issues_project_idx
  on compliance_issues(project_id, status, severity);

create index if not exists compliance_issues_org_idx
  on compliance_issues(org_id, status);

alter table compliance_issues enable row level security;

drop policy if exists "compliance_issues_org_member" on compliance_issues;
create policy "compliance_issues_org_member"
  on compliance_issues
  using (
    exists (
      select 1 from memberships m
      where m.org_id = compliance_issues.org_id
        and m.user_id = auth.uid()
    )
    or exists (
      select 1 from organizations o
      where o.id = compliance_issues.org_id
        and o.owner_id = auth.uid()
    )
  );


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. document_metadata
--    Enriched metadata extracted during document upload / analysis.
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists document_metadata (
  id              uuid primary key default gen_random_uuid(),
  org_id          text not null,
  document_id     uuid not null references documents(id) on delete cascade,
  document_type   text not null default 'unknown',
  expiration_date date,
  risk_level      text not null default 'low' check (risk_level in ('low', 'medium', 'high')),
  last_checked    timestamptz not null default now(),
  created_at      timestamptz not null default now()
);

create unique index if not exists document_metadata_doc_uniq
  on document_metadata(document_id);

create index if not exists document_metadata_org_idx
  on document_metadata(org_id);

create index if not exists document_metadata_expiry_idx
  on document_metadata(expiration_date)
  where expiration_date is not null;

alter table document_metadata enable row level security;

drop policy if exists "document_metadata_org_member" on document_metadata;
create policy "document_metadata_org_member"
  on document_metadata
  using (
    exists (
      select 1 from memberships m
      where m.org_id = document_metadata.org_id
        and m.user_id = auth.uid()
    )
    or exists (
      select 1 from organizations o
      where o.id = document_metadata.org_id
        and o.owner_id = auth.uid()
    )
  );
