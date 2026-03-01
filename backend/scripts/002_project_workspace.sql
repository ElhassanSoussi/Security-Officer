-- Phase 2: Project Workspace + Knowledge Vault + Review → Export Gate
-- Run in Supabase SQL Editor (or via psql). Fully idempotent.

begin;

-- ---------------------------------------------------------------------------
-- 1. Projects table: ensure created_by column exists
-- ---------------------------------------------------------------------------
alter table if exists projects
  add column if not exists created_by text;

-- ---------------------------------------------------------------------------
-- 2. project_documents — lightweight metadata table linking uploaded files
--    to a project. The actual chunks live in documents + chunks tables.
--    This table provides a clean UI-facing registry with upload metadata.
-- ---------------------------------------------------------------------------
create table if not exists project_documents (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  document_id uuid not null references documents(id) on delete cascade,
  org_id uuid not null references organizations(id) on delete cascade,
  uploaded_by text,               -- user_id of uploader
  display_name text,              -- human-friendly label (defaults to filename)
  file_type text,                 -- 'pdf', 'docx', 'txt'
  file_size_bytes bigint,
  created_at timestamptz not null default now(),
  unique (project_id, document_id)
);

create index if not exists idx_project_documents_project
  on project_documents (project_id, created_at desc);

create index if not exists idx_project_documents_org
  on project_documents (org_id);

alter table if exists project_documents enable row level security;

-- RLS: members can read project documents in their org
drop policy if exists "project_documents_select_member" on project_documents;
create policy "project_documents_select_member"
  on project_documents for select to authenticated
  using (
    exists (
      select 1 from memberships m
      where m.org_id = project_documents.org_id
        and m.user_id::text = auth.uid()::text
    )
  );

-- RLS: members can insert project documents in their org
drop policy if exists "project_documents_insert_member" on project_documents;
create policy "project_documents_insert_member"
  on project_documents for insert to authenticated
  with check (
    exists (
      select 1 from memberships m
      where m.org_id = project_documents.org_id
        and m.user_id::text = auth.uid()::text
    )
  );

-- RLS: members can delete their own project documents
drop policy if exists "project_documents_delete_member" on project_documents;
create policy "project_documents_delete_member"
  on project_documents for delete to authenticated
  using (
    exists (
      select 1 from memberships m
      where m.org_id = project_documents.org_id
        and m.user_id::text = auth.uid()::text
    )
  );

-- ---------------------------------------------------------------------------
-- 3. run_audits — ensure all Phase 2 review columns exist
-- ---------------------------------------------------------------------------
alter table if exists run_audits
  add column if not exists review_status text not null default 'pending',
  add column if not exists reviewer_id text,
  add column if not exists reviewed_at timestamptz,
  add column if not exists review_notes text,
  add column if not exists source_excerpt text,
  add column if not exists source_document_id uuid,
  add column if not exists final_answer text,
  add column if not exists editor_id text,
  add column if not exists edited_at timestamptz;

-- Index for efficient review status filtering
create index if not exists idx_run_audits_review_status
  on run_audits (run_id, review_status);

-- ---------------------------------------------------------------------------
-- 4. runs — ensure project_id and questions counters exist
-- ---------------------------------------------------------------------------
alter table if exists runs
  add column if not exists questions_total int not null default 0,
  add column if not exists questions_answered int not null default 0,
  add column if not exists questions_approved int not null default 0;

-- ---------------------------------------------------------------------------
-- 5. Audit log: project_id linkage for activity feed
-- ---------------------------------------------------------------------------
alter table if exists activities
  add column if not exists user_id text;

-- ---------------------------------------------------------------------------
-- 6. Service-role bypass policies (for admin operations)
-- ---------------------------------------------------------------------------

-- project_documents: service_role can do anything
drop policy if exists "project_documents_service_role" on project_documents;
create policy "project_documents_service_role"
  on project_documents for all to service_role
  using (true)
  with check (true);

-- ---------------------------------------------------------------------------
-- 7. Documents table: ensure project_id is indexed for retrieval scoping
-- ---------------------------------------------------------------------------
create index if not exists idx_documents_project_id
  on documents (project_id) where project_id is not null;

create index if not exists idx_documents_org_project
  on documents (org_id, project_id);

commit;
