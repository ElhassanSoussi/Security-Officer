-- Enable the pgvector extension to work with embedding vectors
create extension if not exists vector;

-- Create a table to store documents
create table documents (
  id uuid primary key default gen_random_uuid(),
  org_id text not null, -- For multi-tenancy (or 'default' for single user)
  project_id text,      -- Optional, if document is specific to a project
  scope text not null check (scope in ('LOCKER', 'PROJECT', 'NYC_GLOBAL')),
  filename text not null,
  metadata jsonb default '{}'::jsonb,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Create a table to store chunks
create table chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid references documents(id) on delete cascade,
  page_number integer not null,
  chunk_index integer not null,
  content text not null,
  embedding vector(1536), -- OpenAI text-embedding-3-small dimension
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Create an index for faster similarity search
create index on chunks using ivfflat (embedding vector_cosine_ops)
with (lists = 100);

-- RPC function to search for documents
create or replace function match_chunks (
  query_embedding vector(1536),
  match_threshold float,
  match_count int,
  filter jsonb
)
returns table (
  chunk_id uuid,
  document_id uuid,
  content text,
  page_number int,
  chunk_index int,
  document_filename text,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    c.id as chunk_id,
    c.document_id,
    c.content,
    c.page_number,
    c.chunk_index,
    d.filename as document_filename,
    1 - (c.embedding <=> query_embedding) as similarity
  from chunks c
  join documents d on c.document_id = d.id
  where 1 - (c.embedding <=> query_embedding) > match_threshold
  and d.org_id = (filter ->> 'org_id')
  and (
    (filter ->> 'project_id') is null 
    or d.project_id = (filter ->> 'project_id')
    or d.scope = 'NYC_GLOBAL' -- Always include global rules if needed, though strictly we might want separate queries
  )
  order by c.embedding <=> query_embedding
  limit match_count;
end;
$$;
