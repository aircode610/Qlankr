# Supabase Persistence & Multi-Tenant User Workspaces

**Status:** Draft, pending implementation plan
**Date:** 2026-05-10

## 1. Goal

Add persistent, per-user state to Qlankr so that:

- Each user has their own account and signs in to use the app.
- Each user sees only their own indexed projects (a "tab with all their indexed projects").
- For each project, the user can see the history of every PR analysis and bug reproduction they've run, including each pipeline stage's output and the final result.
- The system is designed as if it will serve many users, even though the immediate operator plans to run it for ~4 teammates and not deploy it publicly.

## 2. Non-goals

- Deployment, hosting, or production infrastructure beyond the Docker Compose story already in the repo.
- Sharing projects, runs, or graphs between users.
- Cross-machine resumption of indexed graphs (graphs are local cache, not synced).
- Resuming an in-flight run after backend restart. Past runs are persisted as they complete; an in-flight run that dies with the backend is lost and must be re-triggered.
- OAuth sign-in (GitHub/Google). Email/password + magic link only for v1.
- Quota enforcement on disk usage, API calls, or Anthropic spend.
- Replaying, mutating, or re-triggering historical runs from the history view. History is read-only.

## 3. Decisions (with reasoning)

| Decision | Choice | Why |
|---|---|---|
| User model | Public multi-tenant with Supabase Auth + RLS | Frame the app as a real product even though the initial user pool is small. Public signup remains enabled. |
| Supabase host | Supabase Cloud only | Simplest. No extra docker services. Free tier is sufficient. |
| Graph data storage | Per-user KuzuDB on backend filesystem; Supabase only stores project metadata | Graphs are too large for Postgres. Per-user paths give airtight privacy for private repos. |
| History granularity | Final result + per-stage JSONB column on type-specific tables | History view should show what each pipeline stage produced. Type-specific tables are simpler than polymorphic stage rows. |
| Run durability | Past runs persisted as each stage completes; in-flight runs are still in-memory and ephemeral on backend restart | Avoids LangGraph Postgres-checkpointer plumbing. Matches the usual meaning of "history". |
| API keys | Bring-your-own (BYO): Anthropic key, GitHub token, integration tokens stored per-user | Public-multi-tenant pattern. The operator does not eat strangers' Anthropic costs. |
| Schema shape | Type-specific tables: separate `pr_analyses` and `bug_reports`, one row per run, one JSONB column per stage | Faster queries, schema mirrors the actual pipeline shape, no aggregation per render. |
| Credential encryption in DB | Skip (plain text columns behind RLS) | Simplification accepted by the operator given small initial user pool. RLS + service-role discipline is the security boundary. |
| Disk quota per user | Skip | Simplification accepted. No column or limit. Documented as a known limitation. |
| MCP-client-per-user cache | Trivial: keep instances around with a simple per-user LRU cap, no eviction sophistication | Simplification accepted. Behavior is fine for any small user count and is not load-bearing for correctness. |
| Legacy `~/.qlankr/registry.json` migration | Dry-run / non-destructive script that prints what it would do | Matches "production-shape" hygiene. Old data has no `user_id`, so it cannot be silently attached to anyone. |

## 4. Architecture overview

```
Browser (React + Vite)
  ├── @supabase/supabase-js  → signs in, holds JWT, auto-refreshes
  └── api client             → injects Authorization: Bearer <JWT> on every backend call
        │
        ▼
FastAPI backend
  ├── auth dep    → verifies JWT, extracts user_id (sub claim)
  ├── db helper   → uses SUPABASE_SERVICE_ROLE_KEY; every query filters by user_id
  ├── creds       → reads per-user credentials from Postgres for this run
  ├── MCP clients → built per user; bounded cache keyed by user_id
  └── KuzuDB      → ~/.qlankr/graphs/{user_id}/{owner_repo}/db.kuzu
        │
        ▼
Supabase Cloud
  ├── Auth (auth.users)
  └── Postgres
      ├── profiles
      ├── projects
      ├── pr_analyses
      ├── bug_reports
      └── user_credentials
```

**Source-of-truth split:**
- Supabase: who exists, what they own, what they've done, their credentials.
- Backend filesystem: indexed graph contents (cache; rebuildable from a fresh re-index).

If a user logs in from a new machine, they see their projects in the UI but each project shows `local_graph_present=false` until they re-trigger indexing on this machine.

## 5. Database schema

All tables are RLS-protected. The default policy on every user-owned table is:

```sql
USING (user_id = auth.uid())
WITH CHECK (user_id = auth.uid())
```

The backend uses `SUPABASE_SERVICE_ROLE_KEY` (which bypasses RLS) and is responsible for filtering by `user_id` explicitly on every query. RLS is the second line of defense, not the first.

### 5.1 `profiles`

Extends `auth.users` with optional display data.

```sql
create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  created_at timestamptz default now()
);
```

A row is created for each new user via a Supabase database trigger on `auth.users` insert.

### 5.2 `projects`

One row per `(user, indexed repo)`. The same repo URL can exist multiple times across users; each user has their own row.

```sql
create table projects (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  repo_url text not null,
  owner text not null,
  repo_name text not null,
  index_status text not null default 'pending',  -- pending|indexing|ready|failed|stale
  index_error text,
  graph_stats jsonb,
  last_indexed_at timestamptz,
  created_at timestamptz default now(),
  unique (user_id, repo_url)
);

create index projects_user_id_created_at_idx
  on projects (user_id, created_at desc);
```

`graph_stats` example: `{"node_count": 12345, "edge_count": 56789, "languages": ["python","typescript"]}`.

### 5.3 `pr_analyses`

One row per PR analysis run. Stage outputs are written as their corresponding LangGraph nodes complete.

```sql
create table pr_analyses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid not null references projects(id) on delete cascade,
  pr_url text not null,
  pr_number int,
  pr_title text,
  status text not null default 'running',  -- running|completed|failed|cancelled
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
```

### 5.4 `bug_reports`

One row per bug reproduction run.

```sql
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
```

### 5.5 `user_credentials`

BYO keys + integration tokens. One row per user. Plain `text` columns behind RLS — encryption is intentionally not used (see `Decisions`).

```sql
create table user_credentials (
  user_id uuid primary key references auth.users(id) on delete cascade,
  anthropic_api_key text,
  github_token text,
  jira_creds jsonb,         -- { url, email, api_token } shape, free-form
  notion_creds jsonb,
  confluence_creds jsonb,
  grafana_creds jsonb,
  kibana_creds jsonb,
  postman_creds jsonb,
  updated_at timestamptz default now()
);
```

## 6. Auth flow

### 6.1 Frontend

- New `<AuthProvider>` wraps the app. Uses `@supabase/supabase-js` directly for sign-in / sign-up — no backend roundtrip.
- New routes: `/login`, `/signup`, `/auth/callback`.
- The existing app becomes the protected area, gated by `<RequireAuth>` which redirects unauthenticated users to `/login`.
- Token auto-refresh handled by the Supabase JS SDK.
- The api client injects `Authorization: Bearer ${session.access_token}` on every fetch.

### 6.2 Backend

- New `backend/auth.py` with FastAPI dependency `get_current_user(authorization: str = Header(...)) -> UUID`.
  1. Strip `Bearer ` prefix; verify JWT signature using `SUPABASE_JWT_SECRET` (HS256).
  2. Validate `aud == "authenticated"` and `exp > now`.
  3. Return `UUID(payload["sub"])`.
- Every existing endpoint that touches state gains `user_id: UUID = Depends(get_current_user)`.
- Public endpoints: `/health` only.

### 6.3 Sign-in methods (v1)

- Email + password.
- Magic link.
- Public signup is enabled.

OAuth (GitHub, Google) is one Supabase config flag away but is out of scope for v1.

## 7. Backend changes

### 7.1 New modules

- `backend/db.py` — Supabase client singleton with the service-role key. Provides `db.user_scoped(user_id)` ergonomic wrapper that returns a builder which always injects `where user_id = $1` into selects/updates/deletes. JWT verification helper.
- `backend/auth.py` — `get_current_user` dependency described above.
- `backend/credentials.py` — replaces the env-var fallback in `tool_health.py`. Reads per-user credentials from `user_credentials`, returns a `UserCredentials` dataclass. Downstream code (Anthropic client init, MCP client init) reads from this dataclass instead of `os.environ`.

### 7.2 Modified modules

- `backend/agent/sessions.py` — keep the in-memory dict for in-flight runs. Add hooks: on run start, INSERT a row in `pr_analyses` with `status='running'`; on each LangGraph node completion, UPDATE the corresponding stage column; on terminal state, set `completed_at` and final status. The in-memory `session_id` maps 1:1 to the row id.
- `backend/agent/bug_run_registry.py` — same pattern for `bug_reports`.
- `backend/indexer.py` — `~/.qlankr/registry.json` is removed. `register_repo` becomes "INSERT into projects". `list_indexed_repos(user_id)` becomes `SELECT * FROM projects WHERE user_id = $1`. KuzuDB writes go to `~/.qlankr/graphs/{user_id}/{owner_repo}/`. GitNexus MCP server is parameterized per user-project.
- `backend/agent/tools.py` — MCP clients are now built per user from `UserCredentials`. A simple per-user dict cache `Dict[UUID, MCPClient]` keeps instances around; oldest-first eviction once the dict exceeds a small fixed cap (e.g. 16 entries). No idle timer required for the small initial user pool.
- `backend/main.py` — every state-touching endpoint gains the `user_id` dependency. New endpoints:
  - `GET /projects` — list this user's projects
  - `POST /projects` — create a project (idempotent on `(user_id, repo_url)`)
  - `GET /projects/{id}` — project detail incl. `local_graph_present` flag
  - `DELETE /projects/{id}` — deletes the row + `rm -rf ~/.qlankr/graphs/{user_id}/{owner}_{repo}/`
  - `POST /projects/{id}/index` — trigger (re-)indexing
  - `GET /projects/{id}/pr-analyses` — paginated history
  - `GET /projects/{id}/bug-reports` — paginated history
  - `GET /pr-analyses/{id}` — single run detail
  - `GET /bug-reports/{id}` — single run detail
  - `GET /settings/credentials` — read user_credentials (returns sanitized view; raw values not echoed back)
  - `POST /settings/credentials` — upsert
  - Old `/settings/integrations` endpoints retire; behavior moves under `/settings/credentials`.

### 7.3 SSE behavior

- Existing SSE endpoints (`/index`, `/analyze`, `/bug-report`) continue to stream as before.
- Each stage transition additionally writes its output to Postgres before emitting `stage_change`. If the DB write fails, the SSE event is still emitted (do not block the user) and an `ERROR` is logged. No automatic recovery; the row will simply be missing that stage's output in the history view.

### 7.4 MCP-client-per-user

- GitNexus, GitHub MCP, Jira MCP, etc. were designed for a single-user backend. Each is now instantiated per user, with credentials and (for GitNexus) per-user KuzuDB path passed in.
- A simple `Dict[UUID, Dict[str, MCPClient]]` cache keeps instances around for the duration of the backend process. When the dict exceeds a small fixed cap (e.g. 16 user entries), the oldest entry is evicted.
- Credentials read at run start. If a user updates their credentials mid-run, the in-flight run continues with the old credentials. Documented behavior.

### 7.5 Startup reconciliation

- On backend startup, a single SQL update marks any rows still in `status='running'` as `status='cancelled'` with `failure_reason='backend restarted'`. This prevents history views from showing perpetually-running phantom rows after a restart.

## 8. Frontend changes

### 8.1 Routing

`react-router-dom` is added. Routes:

```
/login
/signup
/auth/callback
/projects                          → ProjectsListPage
/projects/:id                      → ProjectDetailLayout
  ├── /                             → graph view (default tab)
  ├── /analyze                      → PR analysis (existing PrAnalysisPanel, scoped)
  ├── /bugs                         → bug reproduction (existing ResearchPanel, scoped)
  ├── /history                      → HistoryList
  ├── /history/pr/:runId            → PrAnalysisReplay (read-only)
  └── /history/bug/:runId           → BugReportReplay (read-only)
/settings                          → per-user creds + BYO keys
```

### 8.2 New components

- `<AuthProvider>`, `<RequireAuth>`, `<LoginPage>`, `<SignupPage>` — auth plumbing.
- `<ProjectsListPage>` — list of indexed projects with status badge, last-indexed timestamp, run counts. "+ New project" entry point.
- `<ProjectDetailLayout>` — tabbed shell: Graph / Analyze / Bugs / History. The current `<App>` content moves here, scoped to one project.
- `<HistoryList>` — paginated list of past PR analyses + bug reports.
- `<PrAnalysisReplay>` and `<BugReportReplay>` — read-only views of past stage outputs. Reuses existing stage-output components in non-interactive mode.

### 8.3 Modified components

- `useAppState` — `repoUrl: string | null` becomes `currentProject: Project | null`. In-flight `sessionId` lifecycle is unchanged.
- `services/api.ts` — every fetch gets the bearer token; new methods for the history endpoints.
- `SettingsPanel.tsx` — adds Anthropic API key + GitHub token at the top. Existing integration creds panel rewires to write through `/settings/credentials`.
- `Navbar.tsx` — adds user menu (sign out) + projects nav link.

### 8.4 Cross-machine UX

When the user opens a project on a new machine, `GET /projects/:id` returns `local_graph_present: false` (the backend checks if the KuzuDB path exists on its filesystem). The project detail page shows a yellow banner with a "Re-index on this machine" button. The graph + analyze + bugs tabs are disabled until indexing completes.

## 9. Per-user KuzuDB layout

```
~/.qlankr/graphs/
├── {user_id_a}/
│   ├── octocat_hello-world/
│   │   └── db.kuzu
│   └── microsoft_typescript/
│       └── db.kuzu
└── {user_id_b}/
    └── ...
```

- One KuzuDB file per user-project pair.
- Deleting a project = `rm -rf` of the project directory; no DB-level cleanup.
- The backend instantiates a GitNexus MCP client per user, with the user's directory as the working root. Cache as described in §7.4.

## 10. Deployment & env vars

### 10.1 New env vars

| Variable | Required | Where read | Notes |
|---|---|---|---|
| `SUPABASE_URL` | Yes | backend | Project URL from Supabase dashboard |
| `SUPABASE_ANON_KEY` | Yes | (used at frontend build via `VITE_SUPABASE_ANON_KEY`) | Public, browser-safe |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | backend | Bypasses RLS; backend-only; never exposed to frontend |
| `SUPABASE_JWT_SECRET` | Yes | backend | For local JWT verification (HS256) |
| `VITE_SUPABASE_URL` | Yes | frontend | Same value as `SUPABASE_URL` |
| `VITE_SUPABASE_ANON_KEY` | Yes | frontend | Same value as `SUPABASE_ANON_KEY` |

### 10.2 Removed env vars

- `ANTHROPIC_API_KEY` — now per-user in `user_credentials.anthropic_api_key`.
- `GITHUB_TOKEN` — now per-user in `user_credentials.github_token`.

### 10.3 Docker compose changes

- No new services; Supabase is cloud.
- Backend service gets a named volume mounted at `/data/graphs`. The `~/.qlankr/graphs` path is rewritten to live under that volume so per-user KuzuDB files survive `docker compose down`.
- Frontend service unchanged structurally; new build-time `VITE_SUPABASE_*` env vars.

### 10.4 Migrations

- Schema lives in `backend/migrations/*.sql`, applied via the Supabase CLI (or a `migrate.sh` wrapper). For local dev: `supabase db push` documented in setup.
- One-time script `backend/scripts/migrate_legacy_registry.py` reads `~/.qlankr/registry.json` if present and prints what it would migrate. It does not modify any DB row. Old data has no `user_id`, so silent attribution would be wrong; the script's job is to surface "you have N legacy projects; log in as user X and import them via the UI."

### 10.5 `.env.example`

Updated with the new variables and a one-line pointer to where each comes from in the Supabase dashboard. The README's "Setup" section is updated to point users at Supabase free-tier signup.

## 11. Risks & known limitations

1. **MCP-server lifecycle.** MCP servers were not designed for many concurrent per-user instances. The simple cap-and-evict cache is correct for a small user pool; if usage grows, eviction will need refinement.
2. **Credentials read at run start, not refreshed mid-run.** If a user updates their Jira token while a research stage is running, the in-flight stage uses the old token. Documented behavior.
3. **JWT expiry mid-run.** Supabase access tokens expire after 1h by default. The frontend SDK auto-refreshes; the backend authenticates once at request start and does not re-verify mid-stream. Long SSE streams continue to function because the backend doesn't re-validate on the same connection.
4. **No credential encryption in DB.** Plain text behind RLS + service-role discipline. Acceptable trade-off given the operator's choice. To revisit, add `cryptography` + pgcrypto + a `QLANKR_ENCRYPTION_KEY` env var; rotation of that key is a known footgun.
5. **No disk quota.** A user could index a large number of huge repos. No enforcement mechanism. Document in the setup notes.
6. **Repeated indexing of the same public repo by multiple users.** Each user re-indexes. Future work could add a shared public-repo pool, but is out of scope.
7. **In-flight runs are still ephemeral.** A backend restart loses any active analysis. Past stages already persisted; the run is left in `status='running'` and reconciled to `cancelled` on next backend startup (§7.5).
8. **RLS bypass via service role.** The backend is the security boundary. The `db.user_scoped(user_id)` wrapper exists to make it ergonomically hard to forget the filter; code review should treat any raw-client query as a red flag.
9. **Local dev requires Supabase.** Once env vars are required, neither `npm run dev` nor `./start_local.sh` work without a Supabase project configured. Setup docs explicitly direct the developer to free-tier signup.
10. **Legacy `~/.qlankr/registry.json`.** Existing local indexes are not auto-migrated. They remain on disk but are invisible to the new app until the user creates a project pointing at the same repo URL and re-triggers indexing.

## 12. Out of scope (deferred follow-ups)

- Sharing projects or runs between users.
- Cross-machine graph sync (Supabase Storage uploads of KuzuDB snapshots).
- LangGraph Postgres-backed checkpointer for in-flight run resumption.
- OAuth sign-in.
- Quotas (Anthropic spend, disk, API call rate).
- Public-repo shared-graph pool.
- Replay/re-trigger of historical runs.
- Encrypting credentials at rest.
