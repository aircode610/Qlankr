-- 0003_project_names.sql
-- Projects are now created by name first; the repo URL is attached later when indexing.
--   * Add `name` column (user-visible label).
--   * Make repo_url / owner / repo_name nullable.
--   * Drop the (user_id, repo_url) uniqueness — a project can have no URL yet, and
--     two projects can target the same repo if the user wants.

alter table projects add column if not exists name text;
alter table projects alter column repo_url drop not null;
alter table projects alter column owner drop not null;
alter table projects alter column repo_name drop not null;
alter table projects drop constraint if exists projects_user_id_repo_url_key;
