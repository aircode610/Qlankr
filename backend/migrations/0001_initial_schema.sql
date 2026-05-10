-- 0001_initial_schema.sql
-- Tables: profiles, projects, pr_analyses, bug_reports, user_credentials.

create extension if not exists pgcrypto;

-- profiles
create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  created_at timestamptz default now()
);

alter table profiles enable row level security;

create policy "profiles_self_read" on profiles
  for select using (id = auth.uid());
create policy "profiles_self_update" on profiles
  for update using (id = auth.uid()) with check (id = auth.uid());

-- projects
create table projects (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  repo_url text not null,
  owner text not null,
  repo_name text not null,
  index_status text not null default 'pending',
  index_error text,
  graph_stats jsonb,
  last_indexed_at timestamptz,
  created_at timestamptz default now(),
  unique (user_id, repo_url)
);

create index projects_user_created_idx
  on projects (user_id, created_at desc);

alter table projects enable row level security;
create policy "projects_owner_all" on projects
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- pr_analyses
create table pr_analyses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid not null references projects(id) on delete cascade,
  pr_url text not null,
  pr_number int,
  pr_title text,
  status text not null default 'running',
  failure_reason text,
  gather_output jsonb,
  unit_output jsonb,
  integration_output jsonb,
  e2e_output jsonb,
  final_result jsonb,
  created_at timestamptz default now(),
  completed_at timestamptz
);

create index pr_analyses_project_created_idx
  on pr_analyses (project_id, created_at desc);

alter table pr_analyses enable row level security;
create policy "pr_analyses_owner_all" on pr_analyses
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- bug_reports
create table bug_reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid not null references projects(id) on delete cascade,
  bug_description text not null,
  severity text,
  status text not null default 'running',
  failure_reason text,
  triage_output jsonb,
  mechanics_output jsonb,
  reproduction_output jsonb,
  research_output jsonb,
  report_output jsonb,
  final_report jsonb,
  created_at timestamptz default now(),
  completed_at timestamptz
);

create index bug_reports_project_created_idx
  on bug_reports (project_id, created_at desc);

alter table bug_reports enable row level security;
create policy "bug_reports_owner_all" on bug_reports
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- user_credentials
create table user_credentials (
  user_id uuid primary key references auth.users(id) on delete cascade,
  anthropic_api_key text,
  github_token text,
  jira_creds jsonb,
  notion_creds jsonb,
  confluence_creds jsonb,
  grafana_creds jsonb,
  kibana_creds jsonb,
  postman_creds jsonb,
  updated_at timestamptz default now()
);

alter table user_credentials enable row level security;
create policy "credentials_owner_all" on user_credentials
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());
