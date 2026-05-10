# Supabase Persistence & Multi-Tenant User Workspaces — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Supabase-backed persistence to Qlankr: per-user authentication, per-user indexed projects with isolated KuzuDB graphs on the backend filesystem, persisted history of every PR analysis and bug reproduction run, and BYO API keys per user.

**Architecture:** Supabase Cloud (Auth + Postgres) is the source of truth for users, projects, runs, and credentials. KuzuDB graph contents stay on the backend filesystem under per-user directories. The FastAPI backend validates Supabase JWTs on every request, uses the service-role key for DB writes, and filters every query by `user_id`. The frontend uses `@supabase/supabase-js` directly for sign-in and injects bearer tokens on every backend call.

**Tech Stack:** Supabase Cloud (Postgres 15, GoTrue), `supabase-py` v2, `PyJWT`, FastAPI, React 18, `@supabase/supabase-js` v2, `react-router-dom` v6, KuzuDB (unchanged), GitNexus MCP (per-user-parameterised).

**Reference spec:** `docs/superpowers/specs/2026-05-10-supabase-persistence-design.md`

---

## File Structure

### Backend — new files

| Path | Responsibility |
|---|---|
| `backend/db.py` | Supabase client singleton + `user_scoped(user_id, table)` helper that injects `user_id` on insert and `where user_id = ...` on select/update/delete |
| `backend/auth.py` | `get_current_user` FastAPI dependency: verifies JWT, returns `UUID` |
| `backend/credentials.py` | `UserCredentials` dataclass + `load_credentials(user_id)` + `save_credentials(user_id, ...)` |
| `backend/startup.py` | Startup hook: reconcile orphaned `running` rows to `cancelled` |
| `backend/migrations/0001_initial_schema.sql` | All five tables, indexes, RLS policies |
| `backend/migrations/0002_profile_trigger.sql` | DB trigger that inserts a `profiles` row on `auth.users` insert |
| `backend/scripts/migrate_legacy_registry.py` | Read `~/.qlankr/registry.json`, print legacy projects (no DB writes) |
| `backend/tests/test_auth.py` | JWT verification unit tests |
| `backend/tests/test_db.py` | `user_scoped` helper unit tests against fake client |
| `backend/tests/test_credentials.py` | Credential round-trip tests |
| `backend/tests/api/test_projects.py` | Projects endpoints |
| `backend/tests/api/test_credentials_endpoint.py` | Settings endpoints |
| `backend/tests/api/test_history.py` | History endpoints |
| `backend/tests/fake_supabase.py` | In-memory fake Supabase client for tests |

### Backend — modified files

| Path | What changes |
|---|---|
| `backend/main.py` | Every state-touching endpoint gains `user_id: UUID = Depends(get_current_user)`; new endpoints for projects/history/credentials; old `/settings/integrations` retired |
| `backend/indexer.py` | `~/.qlankr/registry.json` removed; projects come from Postgres; KuzuDB paths become `~/.qlankr/graphs/{user_id}/{owner}_{repo}/` |
| `backend/agent/sessions.py` | INSERT a `pr_analyses` row on run start; UPDATE per-stage outputs as nodes complete |
| `backend/agent/bug_run_registry.py` | Same pattern for `bug_reports` |
| `backend/agent/tools.py` | MCP clients built per user from `UserCredentials`; per-user dict cache with fixed cap |
| `backend/agent/tool_health.py` | Replaced: env-var fallback removed, reads from `UserCredentials` |
| `backend/requirements.txt` | Add `supabase==2.*`, `PyJWT==2.*` |
| `backend/tests/conftest.py` | Add `auth_user` fixture (mock JWT validation); swap real Supabase client for `fake_supabase` |

### Frontend — new files

| Path | Responsibility |
|---|---|
| `frontend/src/services/supabase.ts` | `@supabase/supabase-js` client singleton |
| `frontend/src/auth/AuthProvider.tsx` | Holds session, exposes `useAuth()` |
| `frontend/src/auth/RequireAuth.tsx` | Route wrapper that redirects unauthenticated users to `/login` |
| `frontend/src/pages/LoginPage.tsx` | Email/password + magic link |
| `frontend/src/pages/SignupPage.tsx` | Email/password signup |
| `frontend/src/pages/AuthCallbackPage.tsx` | Handles magic-link return |
| `frontend/src/pages/ProjectsListPage.tsx` | List of user's indexed projects + "New project" entry |
| `frontend/src/pages/ProjectDetailLayout.tsx` | Tabbed shell: Graph / Analyze / Bugs / History |
| `frontend/src/pages/HistoryList.tsx` | Paginated list of past PR analyses + bug reports for a project |
| `frontend/src/pages/PrAnalysisReplay.tsx` | Read-only view of a past PR analysis |
| `frontend/src/pages/BugReportReplay.tsx` | Read-only view of a past bug report |
| `frontend/src/__tests__/AuthProvider.test.tsx` | Provider state transitions |
| `frontend/src/__tests__/RequireAuth.test.tsx` | Redirect behaviour |
| `frontend/src/__tests__/ProjectsListPage.test.tsx` | Renders projects from API |
| `frontend/src/__tests__/HistoryList.test.tsx` | Renders history rows |

### Frontend — modified files

| Path | What changes |
|---|---|
| `frontend/package.json` | Add `@supabase/supabase-js`, `react-router-dom`, `@types/react-router-dom` |
| `frontend/src/App.tsx` | Router setup; existing app content moves into `ProjectDetailLayout` |
| `frontend/src/hooks/useAppState.tsx` | `repoUrl: string \| null` → `currentProject: Project \| null` |
| `frontend/src/services/api.ts` | Bearer-token injection on every fetch; new history/credentials methods |
| `frontend/src/components/SettingsPanel.tsx` | Adds "API Keys" section (Anthropic + GitHub); existing integration creds rewire to `/settings/credentials` |
| `frontend/src/components/Navbar.tsx` | User menu (sign out) + projects nav link |

### Cross-cutting

| Path | What changes |
|---|---|
| `docker-compose.yml` | Named volume mounted at `/data/graphs`; new env vars passed through |
| `.env.example` | Adds new Supabase env vars; removes `ANTHROPIC_API_KEY` / `GITHUB_TOKEN` |
| `README.md` | Updated Setup section pointing to Supabase free-tier signup |

---

## Phase 0 — Setup

### Task 1: Add backend dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add the two new packages**

Open `backend/requirements.txt` and append:

```
supabase==2.30.0
PyJWT==2.10.1
```

(Note: pins chosen to coexist with existing transitive deps — `mcp` requires `pyjwt>=2.10.1`; `mcp-atlassian` requires `httpx>=0.28`, and `supabase==2.30.0` accepts `httpx>=0.26,<0.29`, so the resolver picks an `httpx 0.28.x`.)

- [ ] **Step 2: Install locally and verify import**

Run:

```bash
cd backend
pip install -r requirements.txt
python -c "import supabase, jwt; print(supabase.__version__, jwt.__version__)"
```

Expected: prints two version strings with no traceback.

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "deps(backend): add supabase and PyJWT"
```

---

### Task 2: Add frontend dependencies

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install the two new packages**

Run:

```bash
cd frontend
npm install @supabase/supabase-js@^2.46.1 react-router-dom@^6.27.0
```

- [ ] **Step 2: Verify imports work**

Run:

```bash
npx tsc --noEmit
```

Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "deps(frontend): add @supabase/supabase-js and react-router-dom"
```

---

### Task 3: Create the initial schema migration

**Files:**
- Create: `backend/migrations/0001_initial_schema.sql`

- [ ] **Step 1: Write the SQL file**

Create `backend/migrations/0001_initial_schema.sql`:

```sql
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/migrations/0001_initial_schema.sql
git commit -m "feat(db): initial schema migration"
```

---

### Task 4: Add the profile-creation trigger

**Files:**
- Create: `backend/migrations/0002_profile_trigger.sql`

- [ ] **Step 1: Write the trigger SQL**

Create `backend/migrations/0002_profile_trigger.sql`:

```sql
-- 0002_profile_trigger.sql
-- Auto-create a profiles row whenever a new auth.users row is inserted.

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, coalesce(new.raw_user_meta_data->>'display_name', split_part(new.email, '@', 1)));
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
```

- [ ] **Step 2: Commit**

```bash
git add backend/migrations/0002_profile_trigger.sql
git commit -m "feat(db): auto-create profiles row on auth.users insert"
```

---

### Task 5: Bootstrap a Supabase project and apply migrations

This is a manual / operator task. No code commit.

- [ ] **Step 1: Create a Supabase project**

Go to https://supabase.com, create a new project, and record the project URL.

- [ ] **Step 2: Capture the keys**

From the Supabase dashboard's "Project Settings → API" page, capture:
- `Project URL` → `SUPABASE_URL` and `VITE_SUPABASE_URL`
- `anon public` key → `SUPABASE_ANON_KEY` and `VITE_SUPABASE_ANON_KEY`
- `service_role secret` key → `SUPABASE_SERVICE_ROLE_KEY`
- `JWT Secret` (from "Project Settings → API → JWT Settings") → `SUPABASE_JWT_SECRET`

- [ ] **Step 3: Apply both migrations**

In the Supabase dashboard "SQL Editor", paste and run the contents of `backend/migrations/0001_initial_schema.sql`, then `backend/migrations/0002_profile_trigger.sql`.

Verify in "Table Editor" that `profiles`, `projects`, `pr_analyses`, `bug_reports`, `user_credentials` exist and RLS is enabled (lock icon next to each table).

- [ ] **Step 4: Add the new env vars to a local `.env` file**

In the repo root:

```
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_JWT_SECRET=<64-char hex>
VITE_SUPABASE_URL=https://<project-ref>.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
```

Verify the file is gitignored (it already is via `.env`).

---

## Phase 1 — Auth foundation

### Task 6: Backend JWT verification

**Files:**
- Create: `backend/auth.py`
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_auth.py`:

```python
import os
import time
from uuid import uuid4

import jwt
import pytest

from auth import InvalidToken, verify_jwt


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret-please-ignore")


def _make_token(payload):
    return jwt.encode(payload, "test-secret-please-ignore", algorithm="HS256")


def test_verify_jwt_returns_user_id_for_valid_token():
    uid = uuid4()
    token = _make_token({
        "sub": str(uid),
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
    })
    assert verify_jwt(token) == uid


def test_verify_jwt_rejects_expired_token():
    token = _make_token({
        "sub": str(uuid4()),
        "aud": "authenticated",
        "exp": int(time.time()) - 1,
    })
    with pytest.raises(InvalidToken, match="expired"):
        verify_jwt(token)


def test_verify_jwt_rejects_wrong_audience():
    token = _make_token({
        "sub": str(uuid4()),
        "aud": "service_role",
        "exp": int(time.time()) + 3600,
    })
    with pytest.raises(InvalidToken):
        verify_jwt(token)


def test_verify_jwt_rejects_bad_signature():
    payload = {"sub": str(uuid4()), "aud": "authenticated", "exp": int(time.time()) + 3600}
    token = jwt.encode(payload, "wrong-secret", algorithm="HS256")
    with pytest.raises(InvalidToken):
        verify_jwt(token)
```

- [ ] **Step 2: Run tests, confirm they fail**

Run:

```bash
cd backend
pytest tests/test_auth.py -v
```

Expected: import error or `ModuleNotFoundError: auth`.

- [ ] **Step 3: Implement `auth.py`**

Create `backend/auth.py`:

```python
import os
from uuid import UUID

import jwt
from fastapi import Header, HTTPException


class InvalidToken(Exception):
    pass


def verify_jwt(token: str) -> UUID:
    secret = os.environ["SUPABASE_JWT_SECRET"]
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError as e:
        raise InvalidToken("expired") from e
    except jwt.InvalidTokenError as e:
        raise InvalidToken(str(e)) from e
    sub = payload.get("sub")
    if not sub:
        raise InvalidToken("missing sub")
    return UUID(sub)


async def get_current_user(authorization: str = Header(...)) -> UUID:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        return verify_jwt(token)
    except InvalidToken as e:
        raise HTTPException(status_code=401, detail=str(e))
```

- [ ] **Step 4: Run tests, confirm they pass**

Run:

```bash
pytest tests/test_auth.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/auth.py backend/tests/test_auth.py
git commit -m "feat(auth): JWT verification + get_current_user dependency"
```

---

### Task 7: Fake Supabase client for tests

**Files:**
- Create: `backend/tests/fake_supabase.py`

- [ ] **Step 1: Write the fake client**

Create `backend/tests/fake_supabase.py`:

```python
"""In-memory fake of the supabase-py client surface we use.

Only the parts of the `.table(...).select/insert/update/delete/eq/execute()`
chain that this codebase touches are implemented. Add more as needed.
"""
from __future__ import annotations

import copy
import uuid
from typing import Any


class _Query:
    def __init__(self, store: dict, table: str, op: str, payload: Any = None):
        self._store = store
        self._table = table
        self._op = op
        self._payload = payload
        self._filters: list[tuple[str, Any]] = []

    def eq(self, column: str, value: Any) -> "_Query":
        self._filters.append((column, value))
        return self

    def order(self, *_args, **_kwargs) -> "_Query":
        return self

    def limit(self, *_args) -> "_Query":
        return self

    def execute(self):
        rows = self._store.setdefault(self._table, [])
        if self._op == "select":
            matched = [r for r in rows if self._matches(r)]
            return _Response(matched)
        if self._op == "insert":
            payload = copy.deepcopy(self._payload)
            if isinstance(payload, list):
                for row in payload:
                    row.setdefault("id", str(uuid.uuid4()))
                rows.extend(payload)
                return _Response(payload)
            payload.setdefault("id", str(uuid.uuid4()))
            rows.append(payload)
            return _Response([payload])
        if self._op == "update":
            updated = []
            for row in rows:
                if self._matches(row):
                    row.update(self._payload)
                    updated.append(row)
            return _Response(updated)
        if self._op == "delete":
            removed = [r for r in rows if self._matches(r)]
            self._store[self._table] = [r for r in rows if not self._matches(r)]
            return _Response(removed)
        raise NotImplementedError(self._op)

    def _matches(self, row: dict) -> bool:
        return all(row.get(c) == v for c, v in self._filters)


class _Response:
    def __init__(self, data):
        self.data = data


class _Table:
    def __init__(self, store: dict, name: str):
        self._store = store
        self._name = name

    def select(self, *_args, **_kwargs) -> _Query:
        return _Query(self._store, self._name, "select")

    def insert(self, payload) -> _Query:
        return _Query(self._store, self._name, "insert", payload)

    def update(self, payload) -> _Query:
        return _Query(self._store, self._name, "update", payload)

    def delete(self) -> _Query:
        return _Query(self._store, self._name, "delete")

    def upsert(self, payload) -> _Query:
        # Treat upsert as insert-or-update keyed by primary key (id or user_id).
        key = "user_id" if "user_id" in payload else "id"
        existing = self._store.setdefault(self._name, [])
        match = next((r for r in existing if r.get(key) == payload.get(key)), None)
        if match:
            match.update(payload)
            return _Query(self._store, self._name, "select")  # noop-ish
        return self.insert(payload)


class FakeSupabaseClient:
    def __init__(self):
        self._store: dict = {}

    def table(self, name: str) -> _Table:
        return _Table(self._store, name)

    def reset(self):
        self._store.clear()
```

- [ ] **Step 2: Commit**

```bash
git add backend/tests/fake_supabase.py
git commit -m "test: in-memory fake supabase client"
```

---

### Task 8: Backend Supabase client + user_scoped helper

**Files:**
- Create: `backend/db.py`
- Test: `backend/tests/test_db.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_db.py`:

```python
from uuid import uuid4

import pytest

from db import UserScoped
from tests.fake_supabase import FakeSupabaseClient


@pytest.fixture
def fake():
    return FakeSupabaseClient()


def test_select_filters_by_user_id(fake):
    uid_a, uid_b = uuid4(), uuid4()
    fake.table("projects").insert({"user_id": str(uid_a), "repo_url": "x"}).execute()
    fake.table("projects").insert({"user_id": str(uid_b), "repo_url": "y"}).execute()

    scoped = UserScoped(fake, uid_a)
    rows = scoped.table("projects").select("*").execute().data
    assert len(rows) == 1
    assert rows[0]["repo_url"] == "x"


def test_insert_injects_user_id(fake):
    uid = uuid4()
    scoped = UserScoped(fake, uid)
    scoped.table("projects").insert({"repo_url": "z"}).execute()

    rows = fake.table("projects").select("*").execute().data
    assert rows[0]["user_id"] == str(uid)


def test_update_filters_by_user_id(fake):
    uid_a, uid_b = uuid4(), uuid4()
    fake.table("projects").insert({"user_id": str(uid_a), "repo_url": "x", "owner": "old"}).execute()
    fake.table("projects").insert({"user_id": str(uid_b), "repo_url": "x", "owner": "old"}).execute()

    scoped = UserScoped(fake, uid_a)
    scoped.table("projects").update({"owner": "new"}).eq("repo_url", "x").execute()

    rows = fake.table("projects").select("*").execute().data
    owners = {(r["user_id"], r["owner"]) for r in rows}
    assert owners == {(str(uid_a), "new"), (str(uid_b), "old")}


def test_delete_filters_by_user_id(fake):
    uid_a, uid_b = uuid4(), uuid4()
    fake.table("projects").insert({"user_id": str(uid_a), "repo_url": "x"}).execute()
    fake.table("projects").insert({"user_id": str(uid_b), "repo_url": "x"}).execute()

    scoped = UserScoped(fake, uid_a)
    scoped.table("projects").delete().eq("repo_url", "x").execute()

    rows = fake.table("projects").select("*").execute().data
    assert len(rows) == 1
    assert rows[0]["user_id"] == str(uid_b)
```

- [ ] **Step 2: Run tests, confirm they fail**

Run:

```bash
cd backend
pytest tests/test_db.py -v
```

Expected: `ModuleNotFoundError: db`.

- [ ] **Step 3: Implement `db.py`**

Create `backend/db.py`:

```python
import os
from functools import lru_cache
from uuid import UUID

from supabase import Client, create_client


@lru_cache(maxsize=1)
def get_client() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


class _ScopedQuery:
    def __init__(self, client, table: str, user_id: UUID, op: str, payload=None):
        self._client = client
        self._table = table
        self._user_id = str(user_id)
        self._op = op
        self._payload = payload
        self._extra_filters: list[tuple[str, object]] = []

    def eq(self, column: str, value):
        self._extra_filters.append((column, value))
        return self

    def order(self, *args, **kwargs):
        self._order = (args, kwargs)
        return self

    def limit(self, n: int):
        self._limit = n
        return self

    def execute(self):
        tbl = self._client.table(self._table)
        if self._op == "select":
            q = tbl.select(*(self._payload or ["*"])).eq("user_id", self._user_id)
            for c, v in self._extra_filters:
                q = q.eq(c, v)
            order = getattr(self, "_order", None)
            if order:
                q = q.order(*order[0], **order[1])
            limit = getattr(self, "_limit", None)
            if limit is not None:
                q = q.limit(limit)
            return q.execute()
        if self._op == "insert":
            row = {**self._payload, "user_id": self._user_id}
            return tbl.insert(row).execute()
        if self._op == "update":
            q = tbl.update(self._payload).eq("user_id", self._user_id)
            for c, v in self._extra_filters:
                q = q.eq(c, v)
            return q.execute()
        if self._op == "delete":
            q = tbl.delete().eq("user_id", self._user_id)
            for c, v in self._extra_filters:
                q = q.eq(c, v)
            return q.execute()
        if self._op == "upsert":
            row = {**self._payload, "user_id": self._user_id}
            return tbl.upsert(row).execute()
        raise NotImplementedError(self._op)


class _ScopedTable:
    def __init__(self, client, table: str, user_id: UUID):
        self._client = client
        self._table = table
        self._user_id = user_id

    def select(self, *columns):
        return _ScopedQuery(self._client, self._table, self._user_id, "select", list(columns) or ["*"])

    def insert(self, payload: dict):
        return _ScopedQuery(self._client, self._table, self._user_id, "insert", payload)

    def update(self, payload: dict):
        return _ScopedQuery(self._client, self._table, self._user_id, "update", payload)

    def delete(self):
        return _ScopedQuery(self._client, self._table, self._user_id, "delete")

    def upsert(self, payload: dict):
        return _ScopedQuery(self._client, self._table, self._user_id, "upsert", payload)


class UserScoped:
    """All operations filter and inject user_id automatically."""

    def __init__(self, client, user_id: UUID):
        self._client = client
        self._user_id = user_id

    def table(self, name: str) -> _ScopedTable:
        return _ScopedTable(self._client, name, self._user_id)


def user_scoped(user_id: UUID) -> UserScoped:
    return UserScoped(get_client(), user_id)
```

- [ ] **Step 4: Run tests, confirm they pass**

Run:

```bash
pytest tests/test_db.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/db.py backend/tests/test_db.py
git commit -m "feat(db): supabase client + user_scoped wrapper"
```

---

### Task 9: Update conftest to wire fake client + auth fixture

**Files:**
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Inspect the current conftest**

Open `backend/tests/conftest.py` and confirm the existing autouse `reset_registry` and `client` fixtures.

- [ ] **Step 2: Add fake Supabase + auth user fixtures**

Append to `backend/tests/conftest.py`:

```python
from uuid import UUID, uuid4

import db
from tests.fake_supabase import FakeSupabaseClient


@pytest.fixture
def fake_supabase(monkeypatch):
    fake = FakeSupabaseClient()
    monkeypatch.setattr(db, "get_client", lambda: fake)
    return fake


@pytest.fixture
def auth_user(monkeypatch):
    """Bypass JWT verification; every request authenticates as this user."""
    uid = uuid4()

    async def _override():
        return uid

    from auth import get_current_user
    from main import app

    app.dependency_overrides[get_current_user] = _override
    yield uid
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def second_user(monkeypatch):
    uid = uuid4()
    yield uid
```

- [ ] **Step 3: Run the existing test suite to confirm nothing is broken**

Run:

```bash
cd backend
pytest -q
```

Expected: existing tests still pass (the new fixtures are opt-in).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: add fake_supabase and auth_user fixtures"
```

---

### Task 10: Frontend Supabase client

**Files:**
- Create: `frontend/src/services/supabase.ts`

- [ ] **Step 1: Write the client**

Create `frontend/src/services/supabase.ts`:

```typescript
import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!url || !anonKey) {
  // Surface this loudly during dev: missing env vars make every fetch silently fail.
  throw new Error(
    "VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY must be set in .env"
  );
}

export const supabase = createClient(url, anonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});
```

- [ ] **Step 2: Add env types**

Create `frontend/src/env.d.ts` (or append if it exists):

```typescript
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_SUPABASE_URL: string;
  readonly VITE_SUPABASE_ANON_KEY: string;
  readonly VITE_USE_MOCK_SSE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run:

```bash
cd frontend
npx tsc --noEmit
```

Expected: exits 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/supabase.ts frontend/src/env.d.ts
git commit -m "feat(frontend): supabase client singleton"
```

---

### Task 11: AuthProvider and useAuth hook

**Files:**
- Create: `frontend/src/auth/AuthProvider.tsx`
- Test: `frontend/src/__tests__/AuthProvider.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/__tests__/AuthProvider.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "../auth/AuthProvider";

vi.mock("../services/supabase", () => {
  const listeners: Array<(event: string, session: unknown) => void> = [];
  return {
    supabase: {
      auth: {
        getSession: vi.fn().mockResolvedValue({
          data: { session: { user: { id: "u-1" }, access_token: "tok" } },
        }),
        onAuthStateChange: vi.fn((cb: (e: string, s: unknown) => void) => {
          listeners.push(cb);
          return { data: { subscription: { unsubscribe: vi.fn() } } };
        }),
      },
    },
  };
});

function Probe() {
  const { user, loading } = useAuth();
  if (loading) return <div>loading</div>;
  return <div>user:{user?.id ?? "anon"}</div>;
}

describe("AuthProvider", () => {
  it("hydrates the session on mount", async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    expect(screen.getByText("loading")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("user:u-1")).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run test, confirm it fails**

Run:

```bash
cd frontend
npx vitest run src/__tests__/AuthProvider.test.tsx
```

Expected: fails with "Cannot find module '../auth/AuthProvider'".

- [ ] **Step 3: Implement the provider**

Create `frontend/src/auth/AuthProvider.tsx`:

```tsx
import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import type { Session, User } from "@supabase/supabase-js";

import { supabase } from "../services/supabase";

type AuthContextValue = {
  session: Session | null;
  user: User | null;
  loading: boolean;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session ?? null);
      setLoading(false);
    });

    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s ?? null);
    });

    return () => {
      active = false;
      sub.subscription.unsubscribe();
    };
  }, []);

  const value: AuthContextValue = {
    session,
    user: session?.user ?? null,
    loading,
    signOut: async () => {
      await supabase.auth.signOut();
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
```

- [ ] **Step 4: Run test, confirm it passes**

Run:

```bash
npx vitest run src/__tests__/AuthProvider.test.tsx
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/auth/AuthProvider.tsx frontend/src/__tests__/AuthProvider.test.tsx
git commit -m "feat(frontend): AuthProvider + useAuth hook"
```

---

### Task 12: RequireAuth wrapper

**Files:**
- Create: `frontend/src/auth/RequireAuth.tsx`
- Test: `frontend/src/__tests__/RequireAuth.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/__tests__/RequireAuth.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { RequireAuth } from "../auth/RequireAuth";
import * as AuthMod from "../auth/AuthProvider";

describe("RequireAuth", () => {
  it("renders children when authenticated", () => {
    vi.spyOn(AuthMod, "useAuth").mockReturnValue({
      session: { user: { id: "u" } } as never,
      user: { id: "u" } as never,
      loading: false,
      signOut: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/secret"]}>
        <Routes>
          <Route path="/secret" element={<RequireAuth><div>secret</div></RequireAuth>} />
          <Route path="/login" element={<div>login page</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText("secret")).toBeInTheDocument();
  });

  it("redirects to /login when not authenticated", () => {
    vi.spyOn(AuthMod, "useAuth").mockReturnValue({
      session: null,
      user: null,
      loading: false,
      signOut: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/secret"]}>
        <Routes>
          <Route path="/secret" element={<RequireAuth><div>secret</div></RequireAuth>} />
          <Route path="/login" element={<div>login page</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText("login page")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test, confirm it fails**

Run:

```bash
npx vitest run src/__tests__/RequireAuth.test.tsx
```

Expected: fails on missing `RequireAuth` import.

- [ ] **Step 3: Implement RequireAuth**

Create `frontend/src/auth/RequireAuth.tsx`:

```tsx
import { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "./AuthProvider";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <div className="p-8 text-sm text-gray-500">Loading…</div>;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return <>{children}</>;
}
```

- [ ] **Step 4: Run test, confirm it passes**

Run:

```bash
npx vitest run src/__tests__/RequireAuth.test.tsx
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/auth/RequireAuth.tsx frontend/src/__tests__/RequireAuth.test.tsx
git commit -m "feat(frontend): RequireAuth route wrapper"
```

---

### Task 13: Login, signup, and auth-callback pages

**Files:**
- Create: `frontend/src/pages/LoginPage.tsx`
- Create: `frontend/src/pages/SignupPage.tsx`
- Create: `frontend/src/pages/AuthCallbackPage.tsx`

- [ ] **Step 1: Create LoginPage**

Create `frontend/src/pages/LoginPage.tsx`:

```tsx
import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { supabase } from "../services/supabase";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? "/projects";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [magicSent, setMagicSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function signInWithPassword(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setBusy(false);
    if (error) {
      setError(error.message);
      return;
    }
    navigate(from, { replace: true });
  }

  async function sendMagicLink() {
    setError(null);
    setBusy(true);
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
    });
    setBusy(false);
    if (error) {
      setError(error.message);
      return;
    }
    setMagicSent(true);
  }

  return (
    <div className="mx-auto max-w-sm p-8">
      <h1 className="mb-6 text-2xl font-semibold">Sign in</h1>
      <form onSubmit={signInWithPassword} className="space-y-3">
        <input
          type="email"
          required
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded border p-2"
        />
        <input
          type="password"
          required
          placeholder="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded border p-2"
        />
        <button disabled={busy} className="w-full rounded bg-black px-4 py-2 text-white disabled:opacity-50">
          Sign in
        </button>
      </form>
      <div className="my-4 text-center text-xs text-gray-500">or</div>
      <button
        type="button"
        onClick={sendMagicLink}
        disabled={busy || !email}
        className="w-full rounded border px-4 py-2 disabled:opacity-50"
      >
        Email me a magic link
      </button>
      {magicSent && <p className="mt-3 text-sm text-green-700">Check your inbox.</p>}
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      <p className="mt-6 text-sm">
        No account? <a href="/signup" className="underline">Sign up</a>
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Create SignupPage**

Create `frontend/src/pages/SignupPage.tsx`:

```tsx
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { supabase } from "../services/supabase";

export function SignupPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmSent, setConfirmSent] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
    });
    setBusy(false);
    if (error) {
      setError(error.message);
      return;
    }
    if (data.session) {
      navigate("/projects", { replace: true });
    } else {
      setConfirmSent(true);
    }
  }

  return (
    <div className="mx-auto max-w-sm p-8">
      <h1 className="mb-6 text-2xl font-semibold">Create your account</h1>
      <form onSubmit={submit} className="space-y-3">
        <input
          type="email"
          required
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded border p-2"
        />
        <input
          type="password"
          required
          minLength={8}
          placeholder="password (min 8)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded border p-2"
        />
        <button disabled={busy} className="w-full rounded bg-black px-4 py-2 text-white disabled:opacity-50">
          Sign up
        </button>
      </form>
      {confirmSent && <p className="mt-3 text-sm text-green-700">Check your inbox to confirm.</p>}
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      <p className="mt-6 text-sm">
        Have an account? <a href="/login" className="underline">Sign in</a>
      </p>
    </div>
  );
}
```

- [ ] **Step 3: Create AuthCallbackPage**

Create `frontend/src/pages/AuthCallbackPage.tsx`:

```tsx
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthProvider";

export function AuthCallbackPage() {
  const { loading, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (loading) return;
    navigate(user ? "/projects" : "/login", { replace: true });
  }, [loading, user, navigate]);

  return <div className="p-8 text-sm text-gray-500">Signing you in…</div>;
}
```

- [ ] **Step 4: Type-check**

Run:

```bash
cd frontend
npx tsc --noEmit
```

Expected: exits 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/LoginPage.tsx frontend/src/pages/SignupPage.tsx frontend/src/pages/AuthCallbackPage.tsx
git commit -m "feat(frontend): login, signup, and auth callback pages"
```

---

### Task 14: Bearer-token injection in api client

**Files:**
- Modify: `frontend/src/services/api.ts`

- [ ] **Step 1: Read the current api client**

Open `frontend/src/services/api.ts` to see how it currently constructs requests. Look for a `fetch` wrapper or `makeRequest` function.

- [ ] **Step 2: Add a header helper**

Near the top of `frontend/src/services/api.ts`, after existing imports, add:

```typescript
import { supabase } from "./supabase";

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new Error("Not authenticated");
  return { Authorization: `Bearer ${token}` };
}
```

- [ ] **Step 3: Wire `authHeaders()` into every fetch**

Find every `fetch(...)` and `EventSource(...)` call in this file. For each:

- For `fetch`: merge `await authHeaders()` into the request's `headers`.
- For `EventSource`: replace with a wrapper that uses `fetch` + a `ReadableStream` reader (EventSource cannot send Authorization headers). Suggested helper:

```typescript
export async function authedSse(
  url: string,
  init: RequestInit,
  onEvent: (event: string, data: unknown) => void
): Promise<void> {
  const headers = { ...(await authHeaders()), Accept: "text/event-stream", "Content-Type": "application/json", ...(init.headers ?? {}) };
  const resp = await fetch(url, { ...init, headers });
  if (!resp.ok || !resp.body) throw new Error(`SSE failed: ${resp.status}`);
  const reader = resp.body.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) return;
    buf += value;
    let idx;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const block = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      try {
        onEvent(event, JSON.parse(data));
      } catch {
        onEvent(event, data);
      }
    }
  }
}
```

Replace existing `EventSource` usages with `authedSse(...)`. Keep the per-event-type callback shape the existing code expects.

- [ ] **Step 4: Type-check**

Run:

```bash
cd frontend
npx tsc --noEmit
```

Expected: exits 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat(frontend): bearer-token injection on every API call"
```

---

### Task 15: Route the app

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Save the current App.tsx contents elsewhere temporarily**

The existing `App.tsx` body will move into `ProjectDetailLayout` in Task 21. For now, wrap it as a placeholder.

- [ ] **Step 2: Rewrite `App.tsx` to route**

Replace `frontend/src/App.tsx` with:

```tsx
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthProvider";
import { RequireAuth } from "./auth/RequireAuth";
import { LoginPage } from "./pages/LoginPage";
import { SignupPage } from "./pages/SignupPage";
import { AuthCallbackPage } from "./pages/AuthCallbackPage";

// Placeholder until Task 17/21 build the real pages.
function ProjectsPagePlaceholder() {
  return <div className="p-8">Projects list goes here.</div>;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />

          <Route
            path="/projects/*"
            element={
              <RequireAuth>
                <ProjectsPagePlaceholder />
              </RequireAuth>
            }
          />

          <Route path="/" element={<Navigate to="/projects" replace />} />
          <Route path="*" element={<Navigate to="/projects" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
```

- [ ] **Step 3: Verify dev server boots**

Run:

```bash
cd frontend
npm run dev
```

Open http://localhost:5173 in a browser. Expected: redirected to `/login`. After signing up with a real Supabase project, redirected to the placeholder. Stop the dev server (Ctrl+C).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(frontend): router + auth gating, placeholder projects page"
```

---

**Phase 1 complete.** At this point auth works end-to-end: sign up, log in, log out. Backend endpoints still don't validate auth — that's Phase 2.

---

## Phase 2 — Projects model + per-user filesystem

### Task 16: Add `user_id` dependency to existing endpoints

**Files:**
- Modify: `backend/main.py`
- Test: `backend/tests/api/test_endpoints.py` (existing)

- [ ] **Step 1: Read the existing endpoints**

Open `backend/main.py`. List every endpoint that touches state: `/index`, `/repos`, `/graph/...`, `/file-content/...`, `/analyze`, `/analyze/{session_id}/...`, `/bug-report`, `/bug-report/{session_id}/...`, `/settings/integrations`.

- [ ] **Step 2: Update tests to use `auth_user` fixture**

For each test file under `backend/tests/api/`, add `auth_user` to fixtures and add `headers={"Authorization": "Bearer test"}` to any request that hits a state-touching endpoint. Example diff for one test:

```python
# Before:
def test_repos_empty(client):
    r = await client.get("/repos")

# After:
async def test_repos_empty(client, auth_user):
    r = await client.get("/repos", headers={"Authorization": "Bearer test"})
```

- [ ] **Step 3: Add `Depends(get_current_user)` to each state-touching endpoint**

Update `backend/main.py`. For each endpoint listed in Step 1, add a parameter `user_id: UUID = Depends(get_current_user)`. Endpoints that don't yet use `user_id` for filtering will still accept it (we wire it through in later tasks). Example:

```python
from auth import get_current_user
from uuid import UUID

@app.get("/repos")
async def repos(user_id: UUID = Depends(get_current_user)):
    return list_indexed_repos()  # still ignores user_id for now; fixed in Task 19
```

`/health` (if present) stays public.

- [ ] **Step 4: Run all api tests**

Run:

```bash
cd backend
pytest tests/api -v
```

Expected: tests pass (those using `auth_user` send a bearer; the bypass returns a UUID).

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/api/
git commit -m "feat(api): require auth on all state-touching endpoints"
```

---

### Task 17: Projects table CRUD helpers

**Files:**
- Create: `backend/projects.py`
- Test: `backend/tests/test_projects_module.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_projects_module.py`:

```python
from uuid import uuid4

import pytest

from projects import (
    create_project,
    delete_project,
    get_project,
    list_projects,
    parse_repo_url,
)


def test_parse_repo_url():
    assert parse_repo_url("https://github.com/foo/bar") == ("foo", "bar")
    assert parse_repo_url("https://github.com/foo/bar.git") == ("foo", "bar")
    assert parse_repo_url("https://github.com/Foo/Bar-Baz") == ("Foo", "Bar-Baz")


def test_parse_repo_url_rejects_invalid():
    with pytest.raises(ValueError):
        parse_repo_url("not-a-url")
    with pytest.raises(ValueError):
        parse_repo_url("https://github.com/onlyone")


def test_create_and_list(fake_supabase, monkeypatch):
    uid = uuid4()
    p = create_project(uid, "https://github.com/foo/bar")
    assert p["owner"] == "foo"
    assert p["repo_name"] == "bar"
    assert p["index_status"] == "pending"

    rows = list_projects(uid)
    assert len(rows) == 1
    assert rows[0]["id"] == p["id"]


def test_create_is_idempotent_per_user(fake_supabase):
    uid = uuid4()
    a = create_project(uid, "https://github.com/foo/bar")
    b = create_project(uid, "https://github.com/foo/bar")
    assert a["id"] == b["id"]


def test_list_is_scoped_to_user(fake_supabase):
    uid_a, uid_b = uuid4(), uuid4()
    create_project(uid_a, "https://github.com/foo/bar")
    create_project(uid_b, "https://github.com/foo/bar")
    assert len(list_projects(uid_a)) == 1
    assert len(list_projects(uid_b)) == 1


def test_get_returns_none_for_other_user(fake_supabase):
    uid_a, uid_b = uuid4(), uuid4()
    p = create_project(uid_a, "https://github.com/foo/bar")
    assert get_project(uid_b, p["id"]) is None


def test_delete_removes_row(fake_supabase):
    uid = uuid4()
    p = create_project(uid, "https://github.com/foo/bar")
    delete_project(uid, p["id"])
    assert list_projects(uid) == []
```

- [ ] **Step 2: Run tests, confirm they fail**

Run:

```bash
cd backend
pytest tests/test_projects_module.py -v
```

Expected: `ModuleNotFoundError: projects`.

- [ ] **Step 3: Implement `projects.py`**

Create `backend/projects.py`:

```python
import re
from uuid import UUID

from db import user_scoped


_GITHUB_RE = re.compile(r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$")


def parse_repo_url(repo_url: str) -> tuple[str, str]:
    m = _GITHUB_RE.match(repo_url.strip())
    if not m:
        raise ValueError(f"Not a GitHub repo URL: {repo_url}")
    return m.group("owner"), m.group("repo")


def list_projects(user_id: UUID) -> list[dict]:
    scoped = user_scoped(user_id)
    res = scoped.table("projects").select("*").order("created_at", desc=True).execute()
    return res.data or []


def get_project(user_id: UUID, project_id: str) -> dict | None:
    scoped = user_scoped(user_id)
    res = scoped.table("projects").select("*").eq("id", project_id).execute()
    rows = res.data or []
    return rows[0] if rows else None


def create_project(user_id: UUID, repo_url: str) -> dict:
    owner, repo = parse_repo_url(repo_url)
    scoped = user_scoped(user_id)
    existing = scoped.table("projects").select("*").eq("repo_url", repo_url).execute().data or []
    if existing:
        return existing[0]
    res = scoped.table("projects").insert({
        "repo_url": repo_url,
        "owner": owner,
        "repo_name": repo,
        "index_status": "pending",
    }).execute()
    return (res.data or [])[0]


def delete_project(user_id: UUID, project_id: str) -> None:
    scoped = user_scoped(user_id)
    scoped.table("projects").delete().eq("id", project_id).execute()


def update_status(user_id: UUID, project_id: str, *, status: str, error: str | None = None, stats: dict | None = None, last_indexed_at: str | None = None) -> None:
    payload = {"index_status": status}
    if error is not None:
        payload["index_error"] = error
    if stats is not None:
        payload["graph_stats"] = stats
    if last_indexed_at is not None:
        payload["last_indexed_at"] = last_indexed_at
    scoped = user_scoped(user_id)
    scoped.table("projects").update(payload).eq("id", project_id).execute()
```

- [ ] **Step 4: Run tests, confirm they pass**

Run:

```bash
pytest tests/test_projects_module.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/projects.py backend/tests/test_projects_module.py
git commit -m "feat(projects): CRUD helpers with per-user scoping"
```

---

### Task 18: Per-user KuzuDB filesystem layout

**Files:**
- Create: `backend/graph_paths.py`
- Test: `backend/tests/test_graph_paths.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_graph_paths.py`:

```python
from pathlib import Path
from uuid import uuid4

from graph_paths import graph_dir, graphs_root, user_present_repos


def test_graph_dir_namespaces_by_user_and_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("QLANKR_GRAPHS_ROOT", str(tmp_path))
    uid = uuid4()
    p = graph_dir(uid, "foo", "bar")
    assert p == tmp_path / str(uid) / "foo_bar"


def test_graph_dir_creates_parent(tmp_path, monkeypatch):
    monkeypatch.setenv("QLANKR_GRAPHS_ROOT", str(tmp_path))
    uid = uuid4()
    graph_dir(uid, "foo", "bar", ensure=True)
    assert (tmp_path / str(uid) / "foo_bar").is_dir()


def test_graphs_root_default(monkeypatch):
    monkeypatch.delenv("QLANKR_GRAPHS_ROOT", raising=False)
    monkeypatch.setenv("HOME", "/home/test")
    assert graphs_root() == Path("/home/test/.qlankr/graphs")


def test_user_present_repos(tmp_path, monkeypatch):
    monkeypatch.setenv("QLANKR_GRAPHS_ROOT", str(tmp_path))
    uid = uuid4()
    (tmp_path / str(uid) / "foo_bar").mkdir(parents=True)
    (tmp_path / str(uid) / "baz_qux").mkdir(parents=True)
    assert set(user_present_repos(uid)) == {("foo", "bar"), ("baz", "qux")}
```

- [ ] **Step 2: Run tests, confirm they fail**

Run:

```bash
cd backend
pytest tests/test_graph_paths.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `graph_paths.py`**

Create `backend/graph_paths.py`:

```python
import os
from pathlib import Path
from uuid import UUID


def graphs_root() -> Path:
    override = os.environ.get("QLANKR_GRAPHS_ROOT")
    if override:
        return Path(override)
    return Path(os.environ["HOME"]) / ".qlankr" / "graphs"


def graph_dir(user_id: UUID, owner: str, repo: str, ensure: bool = False) -> Path:
    path = graphs_root() / str(user_id) / f"{owner}_{repo}"
    if ensure:
        path.mkdir(parents=True, exist_ok=True)
    return path


def user_present_repos(user_id: UUID) -> list[tuple[str, str]]:
    user_root = graphs_root() / str(user_id)
    if not user_root.is_dir():
        return []
    out = []
    for entry in user_root.iterdir():
        if not entry.is_dir():
            continue
        if "_" not in entry.name:
            continue
        owner, repo = entry.name.split("_", 1)
        out.append((owner, repo))
    return out
```

- [ ] **Step 4: Run tests, confirm they pass**

Run:

```bash
pytest tests/test_graph_paths.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/graph_paths.py backend/tests/test_graph_paths.py
git commit -m "feat(graphs): per-user KuzuDB path helper"
```

---

### Task 19: Refactor indexer to use projects table + per-user paths

**Files:**
- Modify: `backend/indexer.py`

- [ ] **Step 1: Read the current indexer**

Open `backend/indexer.py`. Identify:
- The module-level `_registry` dict and `~/.qlankr/registry.json` load/save calls
- The `register_repo`, `list_indexed_repos`, and `get_graph_*` helpers
- Where GitNexus is configured / where the KuzuDB path is set

- [ ] **Step 2: Remove the JSON registry**

Delete the JSON load/save code at module import. Replace `_registry` reads/writes with calls to `projects` module functions.

Concretely, replace:

```python
# old
_REGISTRY_PATH = Path.home() / ".qlankr" / "registry.json"
_registry: dict[str, dict] = {}

def _load_registry(): ...
def _save_registry(): ...
```

with: (nothing — delete this block)

- [ ] **Step 3: Rewrite the public surface to be user-scoped**

Every function in `indexer.py` that was global gains a `user_id: UUID` parameter. Example:

```python
from uuid import UUID

from graph_paths import graph_dir
from projects import (
    create_project,
    get_project,
    list_projects,
    parse_repo_url,
    update_status,
)


def list_indexed_repos(user_id: UUID) -> list[dict]:
    return list_projects(user_id)


def register_repo(user_id: UUID, repo_url: str) -> dict:
    return create_project(user_id, repo_url)


def get_kuzu_path(user_id: UUID, project_id: str) -> Path:
    project = get_project(user_id, project_id)
    if not project:
        raise KeyError(project_id)
    return graph_dir(user_id, project["owner"], project["repo_name"], ensure=True)
```

The actual indexing pipeline (cloning + GitNexus) is invoked via `index_project(user_id, project_id)` which:
1. Marks project `index_status='indexing'` via `projects.update_status`
2. Clones the repo to a temp dir
3. Boots GitNexus with `--db-path` = `get_kuzu_path(user_id, project_id) / "db.kuzu"`
4. Streams progress
5. On success: `update_status(user_id, project_id, status='ready', stats={...}, last_indexed_at=now)`
6. On failure: `update_status(user_id, project_id, status='failed', error=str(e))`

Keep streaming events in the same SSE format the frontend already expects.

- [ ] **Step 4: Update existing indexer tests**

Open `backend/tests/indexer/` and refactor each test to:
- Use `fake_supabase` fixture
- Pass a `user_id: UUID = uuid4()` into every indexer call
- Use `monkeypatch.setenv("QLANKR_GRAPHS_ROOT", str(tmp_path))`

- [ ] **Step 5: Run indexer tests**

Run:

```bash
cd backend
pytest tests/indexer -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/indexer.py backend/tests/indexer/
git commit -m "refactor(indexer): use projects table + per-user KuzuDB paths"
```

---

### Task 20: Wire projects endpoints into main.py

**Files:**
- Modify: `backend/main.py`
- Test: `backend/tests/api/test_projects.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/api/test_projects.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_get_projects_empty(client, auth_user, fake_supabase):
    r = await client.get("/projects", headers={"Authorization": "Bearer test"})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_post_projects_creates(client, auth_user, fake_supabase):
    r = await client.post(
        "/projects",
        headers={"Authorization": "Bearer test"},
        json={"repo_url": "https://github.com/foo/bar"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["owner"] == "foo"
    assert body["repo_name"] == "bar"
    assert body["index_status"] == "pending"


@pytest.mark.asyncio
async def test_post_projects_is_idempotent(client, auth_user, fake_supabase):
    payload = {"repo_url": "https://github.com/foo/bar"}
    a = await client.post("/projects", headers={"Authorization": "Bearer test"}, json=payload)
    b = await client.post("/projects", headers={"Authorization": "Bearer test"}, json=payload)
    assert a.json()["id"] == b.json()["id"]


@pytest.mark.asyncio
async def test_delete_project_removes_row(client, auth_user, fake_supabase, tmp_path, monkeypatch):
    monkeypatch.setenv("QLANKR_GRAPHS_ROOT", str(tmp_path))
    created = await client.post(
        "/projects",
        headers={"Authorization": "Bearer test"},
        json={"repo_url": "https://github.com/foo/bar"},
    )
    pid = created.json()["id"]

    r = await client.delete(f"/projects/{pid}", headers={"Authorization": "Bearer test"})
    assert r.status_code == 204

    listing = await client.get("/projects", headers={"Authorization": "Bearer test"})
    assert listing.json() == []


@pytest.mark.asyncio
async def test_get_project_detail_reports_local_graph_presence(client, auth_user, fake_supabase, tmp_path, monkeypatch):
    monkeypatch.setenv("QLANKR_GRAPHS_ROOT", str(tmp_path))
    created = await client.post(
        "/projects",
        headers={"Authorization": "Bearer test"},
        json={"repo_url": "https://github.com/foo/bar"},
    )
    pid = created.json()["id"]

    r = await client.get(f"/projects/{pid}", headers={"Authorization": "Bearer test"})
    assert r.status_code == 200
    body = r.json()
    assert body["local_graph_present"] is False

    (tmp_path / str(auth_user) / "foo_bar").mkdir(parents=True)
    r = await client.get(f"/projects/{pid}", headers={"Authorization": "Bearer test"})
    assert r.json()["local_graph_present"] is True


@pytest.mark.asyncio
async def test_get_project_returns_404_for_other_user(client, auth_user, fake_supabase, monkeypatch):
    from uuid import uuid4
    from auth import get_current_user
    from main import app

    other = uuid4()

    # Create as "other" user
    async def _override():
        return other

    app.dependency_overrides[get_current_user] = _override
    created = await client.post(
        "/projects",
        headers={"Authorization": "Bearer test"},
        json={"repo_url": "https://github.com/foo/bar"},
    )
    pid = created.json()["id"]

    # Switch back to auth_user
    async def _override_back():
        return auth_user

    app.dependency_overrides[get_current_user] = _override_back

    r = await client.get(f"/projects/{pid}", headers={"Authorization": "Bearer test"})
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests, confirm they fail**

Run:

```bash
cd backend
pytest tests/api/test_projects.py -v
```

Expected: 404s and routing errors.

- [ ] **Step 3: Add endpoints to `main.py`**

Add to `backend/main.py`:

```python
import shutil
from uuid import UUID

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user
from graph_paths import graph_dir
from projects import (
    create_project,
    delete_project,
    get_project,
    list_projects,
)


class CreateProjectBody(BaseModel):
    repo_url: str


@app.get("/projects")
async def get_projects(user_id: UUID = Depends(get_current_user)):
    return list_projects(user_id)


@app.post("/projects", status_code=201)
async def post_project(body: CreateProjectBody, user_id: UUID = Depends(get_current_user)):
    try:
        return create_project(user_id, body.repo_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/projects/{project_id}")
async def get_project_detail(project_id: str, user_id: UUID = Depends(get_current_user)):
    project = get_project(user_id, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="not found")
    local_graph_present = graph_dir(user_id, project["owner"], project["repo_name"]).is_dir()
    return {**project, "local_graph_present": local_graph_present}


@app.delete("/projects/{project_id}", status_code=204)
async def delete_project_endpoint(project_id: str, user_id: UUID = Depends(get_current_user)):
    project = get_project(user_id, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="not found")
    delete_project(user_id, project_id)
    path = graph_dir(user_id, project["owner"], project["repo_name"])
    if path.is_dir():
        shutil.rmtree(path)
    return None
```

- [ ] **Step 4: Run tests, confirm they pass**

Run:

```bash
pytest tests/api/test_projects.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/api/test_projects.py
git commit -m "feat(api): /projects CRUD endpoints"
```

---

### Task 21: ProjectsListPage frontend

**Files:**
- Create: `frontend/src/pages/ProjectsListPage.tsx`
- Test: `frontend/src/__tests__/ProjectsListPage.test.tsx`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add API methods**

In `frontend/src/services/api.ts`, add:

```typescript
export type Project = {
  id: string;
  user_id: string;
  repo_url: string;
  owner: string;
  repo_name: string;
  index_status: "pending" | "indexing" | "ready" | "failed" | "stale";
  index_error?: string | null;
  graph_stats?: { node_count?: number; edge_count?: number } | null;
  last_indexed_at?: string | null;
  created_at: string;
};

export type ProjectDetail = Project & { local_graph_present: boolean };

export async function listProjects(): Promise<Project[]> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/projects`, {
    headers: { ...(await authHeaders()) },
  });
  if (!r.ok) throw new Error(`listProjects ${r.status}`);
  return r.json();
}

export async function createProject(repo_url: string): Promise<Project> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/projects`, {
    method: "POST",
    headers: { ...(await authHeaders()), "Content-Type": "application/json" },
    body: JSON.stringify({ repo_url }),
  });
  if (!r.ok) throw new Error(`createProject ${r.status}`);
  return r.json();
}

export async function getProject(id: string): Promise<ProjectDetail> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/projects/${id}`, {
    headers: { ...(await authHeaders()) },
  });
  if (!r.ok) throw new Error(`getProject ${r.status}`);
  return r.json();
}

export async function deleteProject(id: string): Promise<void> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/projects/${id}`, {
    method: "DELETE",
    headers: { ...(await authHeaders()) },
  });
  if (!r.ok && r.status !== 204) throw new Error(`deleteProject ${r.status}`);
}
```

- [ ] **Step 2: Write the failing test**

Create `frontend/src/__tests__/ProjectsListPage.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ProjectsListPage } from "../pages/ProjectsListPage";
import * as api from "../services/api";

describe("ProjectsListPage", () => {
  it("renders projects from the API", async () => {
    vi.spyOn(api, "listProjects").mockResolvedValue([
      {
        id: "p1",
        user_id: "u",
        repo_url: "https://github.com/foo/bar",
        owner: "foo",
        repo_name: "bar",
        index_status: "ready",
        graph_stats: { node_count: 10, edge_count: 20 },
        last_indexed_at: "2026-05-10T12:00:00Z",
        created_at: "2026-05-10T11:00:00Z",
      },
    ]);

    render(
      <MemoryRouter>
        <ProjectsListPage />
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText("foo/bar")).toBeInTheDocument());
    expect(screen.getByText(/ready/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Implement ProjectsListPage**

Create `frontend/src/pages/ProjectsListPage.tsx`:

```tsx
import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { createProject, listProjects, Project } from "../services/api";

export function ProjectsListPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [repoUrl, setRepoUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listProjects().then(setProjects).catch((e) => setError(String(e)));
  }, []);

  async function add(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const p = await createProject(repoUrl);
      setProjects((prev) => [p, ...prev]);
      setRepoUrl("");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl p-8">
      <h1 className="mb-6 text-2xl font-semibold">Your projects</h1>
      <form onSubmit={add} className="mb-6 flex gap-2">
        <input
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          placeholder="https://github.com/owner/repo"
          className="flex-1 rounded border p-2"
        />
        <button disabled={busy || !repoUrl} className="rounded bg-black px-4 py-2 text-white disabled:opacity-50">
          Add
        </button>
      </form>
      {error && <p className="mb-3 text-sm text-red-700">{error}</p>}
      <ul className="space-y-2">
        {projects.map((p) => (
          <li key={p.id} className="rounded border p-3">
            <Link to={`/projects/${p.id}`} className="font-medium underline">
              {p.owner}/{p.repo_name}
            </Link>
            <span className="ml-2 rounded bg-gray-100 px-2 py-0.5 text-xs">{p.index_status}</span>
            {p.graph_stats?.node_count != null && (
              <span className="ml-2 text-xs text-gray-500">
                {p.graph_stats.node_count} nodes, {p.graph_stats.edge_count} edges
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: Wire into routing**

Update `frontend/src/App.tsx`, replacing `ProjectsPagePlaceholder` with `ProjectsListPage`:

```tsx
import { ProjectsListPage } from "./pages/ProjectsListPage";
// ...
<Route
  path="/projects"
  element={
    <RequireAuth>
      <ProjectsListPage />
    </RequireAuth>
  }
/>
```

- [ ] **Step 5: Run tests, confirm they pass**

Run:

```bash
cd frontend
npx vitest run src/__tests__/ProjectsListPage.test.tsx
```

Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/ProjectsListPage.tsx frontend/src/__tests__/ProjectsListPage.test.tsx frontend/src/services/api.ts frontend/src/App.tsx
git commit -m "feat(frontend): ProjectsListPage + projects API client"
```

---

### Task 22: ProjectDetailLayout shell + tab routing

**Files:**
- Create: `frontend/src/pages/ProjectDetailLayout.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/hooks/useAppState.tsx`

- [ ] **Step 1: Update `useAppState` to hold `currentProject`**

Open `frontend/src/hooks/useAppState.tsx`. Replace `repoUrl` references with `currentProject: ProjectDetail | null`. Keep `sessionId` and other in-flight state intact.

Add an action to set `currentProject` and a `useCurrentProject()` selector.

- [ ] **Step 2: Create ProjectDetailLayout**

Create `frontend/src/pages/ProjectDetailLayout.tsx`:

```tsx
import { useEffect } from "react";
import { Link, Outlet, useParams } from "react-router-dom";

import { getProject } from "../services/api";
import { useAppState } from "../hooks/useAppState";

export function ProjectDetailLayout() {
  const { id } = useParams<{ id: string }>();
  const { currentProject, setCurrentProject } = useAppState();

  useEffect(() => {
    if (!id) return;
    getProject(id).then(setCurrentProject).catch(() => setCurrentProject(null));
  }, [id, setCurrentProject]);

  if (!currentProject) return <div className="p-8 text-sm text-gray-500">Loading project…</div>;

  return (
    <div className="mx-auto max-w-6xl p-6">
      <header className="mb-4 flex items-center justify-between">
        <div>
          <Link to="/projects" className="text-sm underline">← Projects</Link>
          <h1 className="text-xl font-semibold">{currentProject.owner}/{currentProject.repo_name}</h1>
        </div>
        <span className="rounded bg-gray-100 px-2 py-0.5 text-xs">{currentProject.index_status}</span>
      </header>

      {!currentProject.local_graph_present && (
        <div className="mb-4 rounded border border-yellow-400 bg-yellow-50 p-3 text-sm">
          This project has no indexed graph on this machine. Re-index to enable analysis.
        </div>
      )}

      <nav className="mb-4 flex gap-3 border-b text-sm">
        <Link to="" className="px-3 py-2 hover:underline">Graph</Link>
        <Link to="analyze" className="px-3 py-2 hover:underline">PR Analysis</Link>
        <Link to="bugs" className="px-3 py-2 hover:underline">Bug Reproduction</Link>
        <Link to="history" className="px-3 py-2 hover:underline">History</Link>
      </nav>

      <Outlet />
    </div>
  );
}
```

- [ ] **Step 3: Wire nested routes in App.tsx**

Update `frontend/src/App.tsx`:

```tsx
import { ProjectDetailLayout } from "./pages/ProjectDetailLayout";
// ...
<Route
  path="/projects/:id"
  element={<RequireAuth><ProjectDetailLayout /></RequireAuth>}
>
  {/* Each nested route renders into the <Outlet/> in ProjectDetailLayout */}
  <Route index element={<div className="p-4 text-sm text-gray-500">Graph view (existing component will move here in Task 23).</div>} />
  <Route path="analyze" element={<div className="p-4">PR analysis (existing component moves here).</div>} />
  <Route path="bugs" element={<div className="p-4">Bug reproduction (existing component moves here).</div>} />
  <Route path="history" element={<div className="p-4">History (Task 31).</div>} />
</Route>
```

- [ ] **Step 4: Type-check**

Run:

```bash
cd frontend
npx tsc --noEmit
```

Expected: exits 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ProjectDetailLayout.tsx frontend/src/hooks/useAppState.tsx frontend/src/App.tsx
git commit -m "feat(frontend): ProjectDetailLayout shell with tab routing"
```

---

### Task 23: Move existing GraphCanvas / PrAnalysisPanel / ResearchPanel into project routes

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/GraphCanvas.tsx` (small adjustments)
- Modify: `frontend/src/components/PrAnalysisPanel.tsx`
- Modify: `frontend/src/components/ResearchPanel.tsx`

- [ ] **Step 1: Inspect existing components**

Open each component and identify props they currently take (likely `repoUrl` or read directly from `useAppState`). They will now read `currentProject` from `useAppState` and use `currentProject.owner` / `repo_name` / `id` instead of `repoUrl`.

- [ ] **Step 2: Refactor components to read currentProject**

For each component, replace:

```typescript
const { repoUrl } = useAppState();
```

with:

```typescript
const { currentProject } = useAppState();
if (!currentProject) return null;
```

Update any internal calls that used `repoUrl` to use `currentProject.repo_url`, `currentProject.owner`, `currentProject.repo_name`, or `currentProject.id` as appropriate.

- [ ] **Step 3: Wire components into nested routes**

Update `frontend/src/App.tsx`:

```tsx
import { GraphCanvas } from "./components/GraphCanvas";
import { PrAnalysisPanel } from "./components/PrAnalysisPanel";
import { ResearchPanel } from "./components/ResearchPanel";
// ...
<Route path="/projects/:id" element={<RequireAuth><ProjectDetailLayout /></RequireAuth>}>
  <Route index element={<GraphCanvas />} />
  <Route path="analyze" element={<PrAnalysisPanel />} />
  <Route path="bugs" element={<ResearchPanel />} />
  <Route path="history" element={<div className="p-4">History (Task 31).</div>} />
</Route>
```

- [ ] **Step 4: Type-check and run vitest**

Run:

```bash
cd frontend
npx tsc --noEmit && npx vitest run
```

Expected: type-check passes; tests pass (or are updated to mock `currentProject` instead of `repoUrl`).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/GraphCanvas.tsx frontend/src/components/PrAnalysisPanel.tsx frontend/src/components/ResearchPanel.tsx
git commit -m "refactor(frontend): components consume currentProject instead of repoUrl"
```

---

**Phase 2 complete.** Users can sign in, see their projects list, create a project, and view its detail page. Analysis still uses old behaviour (next phase wires up BYO keys + persistence).

---

## Phase 3 — BYO credentials

### Task 24: Credentials module

**Files:**
- Create: `backend/credentials.py`
- Test: `backend/tests/test_credentials.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_credentials.py`:

```python
from uuid import uuid4

from credentials import UserCredentials, load_credentials, save_credentials


def test_load_returns_empty_credentials_for_new_user(fake_supabase):
    creds = load_credentials(uuid4())
    assert creds == UserCredentials()
    assert creds.anthropic_api_key is None
    assert creds.jira is None


def test_save_then_load_roundtrip(fake_supabase):
    uid = uuid4()
    save_credentials(
        uid,
        anthropic_api_key="sk-test",
        github_token="ghp_test",
        jira={"url": "https://x.atlassian.net", "email": "a@b.c", "api_token": "j"},
    )
    creds = load_credentials(uid)
    assert creds.anthropic_api_key == "sk-test"
    assert creds.github_token == "ghp_test"
    assert creds.jira == {"url": "https://x.atlassian.net", "email": "a@b.c", "api_token": "j"}


def test_save_is_partial_update(fake_supabase):
    uid = uuid4()
    save_credentials(uid, anthropic_api_key="sk-1", github_token="ghp_1")
    save_credentials(uid, anthropic_api_key="sk-2")  # only updates one field
    creds = load_credentials(uid)
    assert creds.anthropic_api_key == "sk-2"
    assert creds.github_token == "ghp_1"  # not cleared


def test_credentials_are_per_user(fake_supabase):
    uid_a, uid_b = uuid4(), uuid4()
    save_credentials(uid_a, anthropic_api_key="sk-a")
    save_credentials(uid_b, anthropic_api_key="sk-b")
    assert load_credentials(uid_a).anthropic_api_key == "sk-a"
    assert load_credentials(uid_b).anthropic_api_key == "sk-b"
```

- [ ] **Step 2: Run tests, confirm they fail**

Run:

```bash
cd backend
pytest tests/test_credentials.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `credentials.py`**

Create `backend/credentials.py`:

```python
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from db import user_scoped


@dataclass(frozen=True)
class UserCredentials:
    anthropic_api_key: str | None = None
    github_token: str | None = None
    jira: dict | None = None
    notion: dict | None = None
    confluence: dict | None = None
    grafana: dict | None = None
    kibana: dict | None = None
    postman: dict | None = None


_COLUMN_MAP = {
    "anthropic_api_key": "anthropic_api_key",
    "github_token": "github_token",
    "jira": "jira_creds",
    "notion": "notion_creds",
    "confluence": "confluence_creds",
    "grafana": "grafana_creds",
    "kibana": "kibana_creds",
    "postman": "postman_creds",
}


def load_credentials(user_id: UUID) -> UserCredentials:
    scoped = user_scoped(user_id)
    res = scoped.table("user_credentials").select("*").execute()
    rows = res.data or []
    if not rows:
        return UserCredentials()
    row = rows[0]
    return UserCredentials(
        anthropic_api_key=row.get("anthropic_api_key"),
        github_token=row.get("github_token"),
        jira=row.get("jira_creds"),
        notion=row.get("notion_creds"),
        confluence=row.get("confluence_creds"),
        grafana=row.get("grafana_creds"),
        kibana=row.get("kibana_creds"),
        postman=row.get("postman_creds"),
    )


def save_credentials(user_id: UUID, **updates: Any) -> None:
    payload = {_COLUMN_MAP[k]: v for k, v in updates.items() if k in _COLUMN_MAP}
    if not payload:
        return
    scoped = user_scoped(user_id)
    existing = scoped.table("user_credentials").select("user_id").execute().data or []
    if existing:
        scoped.table("user_credentials").update(payload).execute()
    else:
        scoped.table("user_credentials").insert(payload).execute()
```

- [ ] **Step 4: Run tests, confirm they pass**

Run:

```bash
pytest tests/test_credentials.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/credentials.py backend/tests/test_credentials.py
git commit -m "feat(credentials): per-user UserCredentials load/save"
```

---

### Task 25: Settings credentials endpoints

**Files:**
- Modify: `backend/main.py`
- Test: `backend/tests/api/test_credentials_endpoint.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/api/test_credentials_endpoint.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_get_returns_sanitised_view_when_empty(client, auth_user, fake_supabase):
    r = await client.get("/settings/credentials", headers={"Authorization": "Bearer test"})
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "has_anthropic_api_key": False,
        "has_github_token": False,
        "integrations": {
            "jira": False, "notion": False, "confluence": False,
            "grafana": False, "kibana": False, "postman": False,
        },
    }


@pytest.mark.asyncio
async def test_post_saves_and_get_reflects(client, auth_user, fake_supabase):
    r = await client.post(
        "/settings/credentials",
        headers={"Authorization": "Bearer test"},
        json={
            "anthropic_api_key": "sk-test",
            "jira": {"url": "https://x.atlassian.net", "email": "a@b", "api_token": "j"},
        },
    )
    assert r.status_code == 204

    r = await client.get("/settings/credentials", headers={"Authorization": "Bearer test"})
    body = r.json()
    assert body["has_anthropic_api_key"] is True
    assert body["has_github_token"] is False
    assert body["integrations"]["jira"] is True


@pytest.mark.asyncio
async def test_raw_secrets_never_echoed(client, auth_user, fake_supabase):
    await client.post(
        "/settings/credentials",
        headers={"Authorization": "Bearer test"},
        json={"anthropic_api_key": "sk-very-secret"},
    )
    r = await client.get("/settings/credentials", headers={"Authorization": "Bearer test"})
    assert "sk-very-secret" not in r.text
```

- [ ] **Step 2: Run tests, confirm they fail**

Run:

```bash
cd backend
pytest tests/api/test_credentials_endpoint.py -v
```

Expected: 404 (endpoint not defined).

- [ ] **Step 3: Add endpoints to `main.py`**

Add to `backend/main.py`:

```python
from pydantic import BaseModel

from credentials import load_credentials, save_credentials


class UpdateCredentialsBody(BaseModel):
    anthropic_api_key: str | None = None
    github_token: str | None = None
    jira: dict | None = None
    notion: dict | None = None
    confluence: dict | None = None
    grafana: dict | None = None
    kibana: dict | None = None
    postman: dict | None = None


@app.get("/settings/credentials")
async def get_credentials(user_id: UUID = Depends(get_current_user)):
    creds = load_credentials(user_id)
    return {
        "has_anthropic_api_key": creds.anthropic_api_key is not None,
        "has_github_token": creds.github_token is not None,
        "integrations": {
            name: getattr(creds, name) is not None
            for name in ("jira", "notion", "confluence", "grafana", "kibana", "postman")
        },
    }


@app.post("/settings/credentials", status_code=204)
async def post_credentials(body: UpdateCredentialsBody, user_id: UUID = Depends(get_current_user)):
    updates = body.model_dump(exclude_none=True)
    save_credentials(user_id, **updates)
    return None
```

- [ ] **Step 4: Run tests, confirm they pass**

Run:

```bash
pytest tests/api/test_credentials_endpoint.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/api/test_credentials_endpoint.py
git commit -m "feat(api): /settings/credentials get + upsert"
```

---

### Task 26: Replace tool_health env-var fallback with UserCredentials

**Files:**
- Modify: `backend/agent/tool_health.py`
- Modify: `backend/agent/tools.py`

- [ ] **Step 1: Read current tool_health.py**

Open `backend/agent/tool_health.py`. Identify the `_credential_session_overrides` dict and the env-var fallback that builds per-integration credentials.

- [ ] **Step 2: Rewrite tool_health to accept UserCredentials**

Replace the body of `backend/agent/tool_health.py` with functions that operate on a `UserCredentials` instance:

```python
from credentials import UserCredentials


def health_for(creds: UserCredentials) -> dict[str, dict]:
    """Return a dict keyed by integration name with {connected: bool, error: str|None}."""
    return {
        "anthropic": {"connected": creds.anthropic_api_key is not None, "error": None},
        "github": {"connected": creds.github_token is not None, "error": None},
        "jira": {"connected": creds.jira is not None, "error": None},
        "notion": {"connected": creds.notion is not None, "error": None},
        "confluence": {"connected": creds.confluence is not None, "error": None},
        "grafana": {"connected": creds.grafana is not None, "error": None},
        "kibana": {"connected": creds.kibana is not None, "error": None},
        "postman": {"connected": creds.postman is not None, "error": None},
    }
```

Remove `_credential_session_overrides`, env-var fallback code, and the global `apply_overrides()` function.

- [ ] **Step 3: Rewrite tools.py to take UserCredentials**

Open `backend/agent/tools.py`. Identify the function that constructs MCP clients (likely `build_tools()` or `init_mcp_clients()`). Change its signature to accept `creds: UserCredentials` and use those fields to construct MCP client configs.

Add a per-user cache:

```python
from uuid import UUID
from credentials import UserCredentials

_MCP_CACHE: dict[UUID, dict[str, "MCPClient"]] = {}
_CACHE_CAP = 16


def get_mcp_clients(user_id: UUID, creds: UserCredentials) -> dict[str, "MCPClient"]:
    if user_id in _MCP_CACHE:
        return _MCP_CACHE[user_id]
    if len(_MCP_CACHE) >= _CACHE_CAP:
        oldest = next(iter(_MCP_CACHE))
        _MCP_CACHE.pop(oldest)
    clients = _build_mcp_clients(creds)
    _MCP_CACHE[user_id] = clients
    return clients


def invalidate_user(user_id: UUID) -> None:
    _MCP_CACHE.pop(user_id, None)
```

Where `_build_mcp_clients` is the old body of `build_tools` but reading from `creds.*` instead of `os.environ`.

- [ ] **Step 4: Update callers**

Find every call to `build_tools()` (PR agent, bug agent). At the call site, look up `user_id` from the run context, call `load_credentials(user_id)`, then `get_mcp_clients(user_id, creds)`.

- [ ] **Step 5: Run all existing agent tests**

Run:

```bash
cd backend
pytest tests/agent -v
```

Expected: tests pass, or are updated to inject a `UserCredentials` fixture and a mocked `get_mcp_clients`.

- [ ] **Step 6: Commit**

```bash
git add backend/agent/tool_health.py backend/agent/tools.py backend/tests/agent/
git commit -m "refactor(agent): per-user UserCredentials replaces env-var fallback"
```

---

### Task 27: SettingsPanel — add API Keys section

**Files:**
- Modify: `frontend/src/components/SettingsPanel.tsx`
- Modify: `frontend/src/services/api.ts`

- [ ] **Step 1: Add API methods**

In `frontend/src/services/api.ts`:

```typescript
export type CredentialStatus = {
  has_anthropic_api_key: boolean;
  has_github_token: boolean;
  integrations: Record<"jira" | "notion" | "confluence" | "grafana" | "kibana" | "postman", boolean>;
};

export async function getCredentialStatus(): Promise<CredentialStatus> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/settings/credentials`, {
    headers: { ...(await authHeaders()) },
  });
  if (!r.ok) throw new Error(`getCredentialStatus ${r.status}`);
  return r.json();
}

export async function saveCredentials(body: Partial<{
  anthropic_api_key: string;
  github_token: string;
  jira: object;
  notion: object;
  confluence: object;
  grafana: object;
  kibana: object;
  postman: object;
}>): Promise<void> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/settings/credentials`, {
    method: "POST",
    headers: { ...(await authHeaders()), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok && r.status !== 204) throw new Error(`saveCredentials ${r.status}`);
}
```

- [ ] **Step 2: Add API Keys section to SettingsPanel**

Open `frontend/src/components/SettingsPanel.tsx`. At the top of the rendered content, add:

```tsx
import { getCredentialStatus, saveCredentials, CredentialStatus } from "../services/api";

// inside the component:
const [status, setStatus] = useState<CredentialStatus | null>(null);
const [anthropicKey, setAnthropicKey] = useState("");
const [githubToken, setGithubToken] = useState("");

useEffect(() => {
  getCredentialStatus().then(setStatus).catch(console.error);
}, []);

async function saveApiKeys() {
  const body: Partial<{anthropic_api_key: string; github_token: string}> = {};
  if (anthropicKey) body.anthropic_api_key = anthropicKey;
  if (githubToken) body.github_token = githubToken;
  await saveCredentials(body);
  setAnthropicKey("");
  setGithubToken("");
  setStatus(await getCredentialStatus());
}
```

Render a section:

```tsx
<section className="mb-6 rounded border p-4">
  <h2 className="mb-2 font-semibold">API Keys</h2>
  <div className="mb-2 text-sm text-gray-500">
    Anthropic key: {status?.has_anthropic_api_key ? "set" : "missing"}
  </div>
  <input
    type="password"
    placeholder="sk-ant-..."
    value={anthropicKey}
    onChange={(e) => setAnthropicKey(e.target.value)}
    className="mb-2 w-full rounded border p-2"
  />
  <div className="mb-2 text-sm text-gray-500">
    GitHub token: {status?.has_github_token ? "set" : "missing"}
  </div>
  <input
    type="password"
    placeholder="ghp_..."
    value={githubToken}
    onChange={(e) => setGithubToken(e.target.value)}
    className="mb-2 w-full rounded border p-2"
  />
  <button onClick={saveApiKeys} className="rounded bg-black px-3 py-1 text-white">Save</button>
</section>
```

- [ ] **Step 3: Rewire existing integrations panel to `/settings/credentials`**

In the existing `SettingsPanel`, the integration credential form was hitting `/settings/integrations`. Update its submit handler to call `saveCredentials({ jira: {...} })` (and similarly for other integrations).

- [ ] **Step 4: Type-check**

Run:

```bash
cd frontend
npx tsc --noEmit
```

Expected: exits 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/SettingsPanel.tsx frontend/src/services/api.ts
git commit -m "feat(frontend): API Keys section in Settings; integrations save to /settings/credentials"
```

---

**Phase 3 complete.** Every user supplies their own Anthropic key + GitHub token + integration tokens. The old global env-var pattern is gone.

---

## Phase 4 — Run persistence + history

### Task 28: Persist PR analysis runs as they progress

**Files:**
- Modify: `backend/agent/sessions.py`
- Test: `backend/tests/test_sessions.py` (existing)

- [ ] **Step 1: Read current sessions.py**

Open `backend/agent/sessions.py`. Identify:
- `_sessions: dict` and helpers (`new_session`, `get_session`, `set_session`, `clear_sessions`)
- Where stage outputs would naturally land (probably the LangGraph state)

- [ ] **Step 2: Add DB hooks**

Wire calls to Supabase at three points:

(a) **On run start** (where `new_session` is called):

```python
from uuid import UUID
from db import user_scoped


def new_session(user_id: UUID, project_id: str, pr_url: str, pr_number: int | None, pr_title: str | None) -> str:
    session_id = _generate_session_id()
    _sessions[session_id] = {...}  # existing
    scoped = user_scoped(user_id)
    scoped.table("pr_analyses").insert({
        "id": session_id,
        "project_id": project_id,
        "pr_url": pr_url,
        "pr_number": pr_number,
        "pr_title": pr_title,
        "status": "running",
    }).execute()
    return session_id
```

(b) **On each stage completion** (where a LangGraph node finishes — likely in `agent.py` or via a callback hook):

```python
def record_stage(user_id: UUID, session_id: str, stage: str, output: dict) -> None:
    column = {
        "gather": "gather_output",
        "unit": "unit_output",
        "integration": "integration_output",
        "e2e": "e2e_output",
    }[stage]
    try:
        scoped = user_scoped(user_id)
        scoped.table("pr_analyses").update({column: output}).eq("id", session_id).execute()
    except Exception as e:
        # Spec §7.3: DB write failures must not block the SSE stream
        import logging
        logging.error("failed to persist stage %s for run %s: %s", stage, session_id, e)
```

(c) **On terminal state**:

```python
def finalize(user_id: UUID, session_id: str, *, final_result: dict | None, status: str, failure_reason: str | None = None) -> None:
    from datetime import datetime, timezone
    scoped = user_scoped(user_id)
    payload = {
        "status": status,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    if final_result is not None:
        payload["final_result"] = final_result
    if failure_reason is not None:
        payload["failure_reason"] = failure_reason
    try:
        scoped.table("pr_analyses").update(payload).eq("id", session_id).execute()
    except Exception as e:
        import logging
        logging.error("failed to finalize run %s: %s", session_id, e)
```

- [ ] **Step 3: Wire hooks into the LangGraph pipeline**

In `backend/agent/agent.py`, find each LangGraph node (gather, unit, integration, e2e). After each node's logic, call `sessions.record_stage(user_id, session_id, "gather", gather_output)` etc. On the END / FAIL transitions, call `sessions.finalize(...)`.

- [ ] **Step 4: Update existing sessions tests**

Open `backend/tests/test_sessions.py`. Add `fake_supabase` fixture to relevant tests. Assert that after `new_session(...)` a row exists in `fake_supabase._store["pr_analyses"]`, and that `record_stage(...)` updates the corresponding column.

- [ ] **Step 5: Run tests**

Run:

```bash
cd backend
pytest tests/test_sessions.py tests/agent -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/agent/sessions.py backend/agent/agent.py backend/tests/test_sessions.py
git commit -m "feat(sessions): persist PR analysis stages and final result"
```

---

### Task 29: Persist bug-report runs as they progress

**Files:**
- Modify: `backend/agent/bug_run_registry.py`
- Modify: `backend/agent/bug_agent.py`

- [ ] **Step 1: Mirror Task 28 for bug reports**

In `bug_run_registry.py`, add `new_bug_run(user_id, project_id, bug_description)`, `record_bug_stage(user_id, session_id, stage, output)`, and `finalize_bug_run(...)`. The stage→column map:

```python
{
    "triage": "triage_output",
    "mechanics": "mechanics_output",
    "reproduction": "reproduction_output",
    "research": "research_output",
    "report": "report_output",
}
```

`finalize_bug_run` writes `final_report`, `status`, `completed_at`, and (if known) `severity` extracted from `triage_output`.

- [ ] **Step 2: Wire hooks in bug_agent.py**

For each LangGraph node in the bug pipeline, call `record_bug_stage(...)` after node logic. On terminal, call `finalize_bug_run(...)`.

- [ ] **Step 3: Update existing bug tests**

In `backend/tests/agent/test_bug_reproduction.py`, add `fake_supabase` fixture and assertions on persisted rows.

- [ ] **Step 4: Run tests**

Run:

```bash
cd backend
pytest tests/agent -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/agent/bug_run_registry.py backend/agent/bug_agent.py backend/tests/agent/
git commit -m "feat(bug): persist bug-report stages and final report"
```

---

### Task 30: History endpoints

**Files:**
- Modify: `backend/main.py`
- Test: `backend/tests/api/test_history.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/api/test_history.py`:

```python
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_list_pr_analyses_for_project(client, auth_user, fake_supabase):
    # Seed two analyses for one project
    project_id = str(uuid4())
    fake_supabase.table("projects").insert({
        "id": project_id, "user_id": str(auth_user),
        "repo_url": "x", "owner": "o", "repo_name": "r",
        "index_status": "ready",
    }).execute()
    for pr in ("https://github.com/o/r/pull/1", "https://github.com/o/r/pull/2"):
        fake_supabase.table("pr_analyses").insert({
            "user_id": str(auth_user), "project_id": project_id,
            "pr_url": pr, "status": "completed",
        }).execute()

    r = await client.get(
        f"/projects/{project_id}/pr-analyses",
        headers={"Authorization": "Bearer test"},
    )
    assert r.status_code == 200
    assert len(r.json()) == 2


@pytest.mark.asyncio
async def test_get_pr_analysis_detail(client, auth_user, fake_supabase):
    project_id = str(uuid4())
    fake_supabase.table("projects").insert({
        "id": project_id, "user_id": str(auth_user),
        "repo_url": "x", "owner": "o", "repo_name": "r", "index_status": "ready",
    }).execute()
    res = fake_supabase.table("pr_analyses").insert({
        "user_id": str(auth_user), "project_id": project_id,
        "pr_url": "https://github.com/o/r/pull/1", "status": "completed",
        "final_result": {"summary": "hello"},
    }).execute()
    run_id = res.data[0]["id"]

    r = await client.get(f"/pr-analyses/{run_id}", headers={"Authorization": "Bearer test"})
    assert r.status_code == 200
    assert r.json()["final_result"] == {"summary": "hello"}


@pytest.mark.asyncio
async def test_list_bug_reports_for_project(client, auth_user, fake_supabase):
    project_id = str(uuid4())
    fake_supabase.table("projects").insert({
        "id": project_id, "user_id": str(auth_user),
        "repo_url": "x", "owner": "o", "repo_name": "r", "index_status": "ready",
    }).execute()
    fake_supabase.table("bug_reports").insert({
        "user_id": str(auth_user), "project_id": project_id,
        "bug_description": "crash on save", "status": "completed",
    }).execute()

    r = await client.get(
        f"/projects/{project_id}/bug-reports",
        headers={"Authorization": "Bearer test"},
    )
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["bug_description"] == "crash on save"


@pytest.mark.asyncio
async def test_other_users_runs_not_visible(client, auth_user, fake_supabase):
    project_id = str(uuid4())
    other = uuid4()
    fake_supabase.table("projects").insert({
        "id": project_id, "user_id": str(other),
        "repo_url": "x", "owner": "o", "repo_name": "r", "index_status": "ready",
    }).execute()
    fake_supabase.table("pr_analyses").insert({
        "user_id": str(other), "project_id": project_id,
        "pr_url": "x", "status": "completed",
    }).execute()

    r = await client.get(
        f"/projects/{project_id}/pr-analyses",
        headers={"Authorization": "Bearer test"},
    )
    assert r.json() == []
```

- [ ] **Step 2: Run tests, confirm they fail**

Run:

```bash
cd backend
pytest tests/api/test_history.py -v
```

Expected: 404s.

- [ ] **Step 3: Add endpoints**

Add to `backend/main.py`:

```python
@app.get("/projects/{project_id}/pr-analyses")
async def list_pr_analyses(project_id: str, user_id: UUID = Depends(get_current_user)):
    scoped = user_scoped(user_id)
    res = scoped.table("pr_analyses").select("*").eq("project_id", project_id).order("created_at", desc=True).execute()
    return res.data or []


@app.get("/projects/{project_id}/bug-reports")
async def list_bug_reports(project_id: str, user_id: UUID = Depends(get_current_user)):
    scoped = user_scoped(user_id)
    res = scoped.table("bug_reports").select("*").eq("project_id", project_id).order("created_at", desc=True).execute()
    return res.data or []


@app.get("/pr-analyses/{run_id}")
async def get_pr_analysis(run_id: str, user_id: UUID = Depends(get_current_user)):
    scoped = user_scoped(user_id)
    rows = (scoped.table("pr_analyses").select("*").eq("id", run_id).execute().data) or []
    if not rows:
        raise HTTPException(status_code=404, detail="not found")
    return rows[0]


@app.get("/bug-reports/{run_id}")
async def get_bug_report(run_id: str, user_id: UUID = Depends(get_current_user)):
    scoped = user_scoped(user_id)
    rows = (scoped.table("bug_reports").select("*").eq("id", run_id).execute().data) or []
    if not rows:
        raise HTTPException(status_code=404, detail="not found")
    return rows[0]
```

- [ ] **Step 4: Run tests, confirm they pass**

Run:

```bash
pytest tests/api/test_history.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/api/test_history.py
git commit -m "feat(api): history list + detail endpoints for PR analyses and bug reports"
```

---

### Task 31: Startup reconciliation

**Files:**
- Create: `backend/startup.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Create startup module**

Create `backend/startup.py`:

```python
"""Startup hooks that run once when the FastAPI app boots."""
from db import get_client


def reconcile_orphaned_runs() -> None:
    """Mark any pr_analyses / bug_reports rows still in status='running' as cancelled.

    A row in 'running' state at startup means the previous backend died mid-run.
    """
    client = get_client()
    payload = {"status": "cancelled", "failure_reason": "backend restarted"}
    client.table("pr_analyses").update(payload).eq("status", "running").execute()
    client.table("bug_reports").update(payload).eq("status", "running").execute()
```

- [ ] **Step 2: Wire into FastAPI lifespan**

In `backend/main.py`, find the FastAPI app creation. Add:

```python
from contextlib import asynccontextmanager

from startup import reconcile_orphaned_runs


@asynccontextmanager
async def lifespan(app):
    try:
        reconcile_orphaned_runs()
    except Exception as e:
        import logging
        logging.warning("startup reconciliation failed (non-fatal): %s", e)
    yield


app = FastAPI(lifespan=lifespan)  # if FastAPI() is currently called without lifespan
```

(If `FastAPI(...)` is already constructed elsewhere with other kwargs, add `lifespan=lifespan` to that call.)

- [ ] **Step 3: Smoke-test the startup hook**

Run:

```bash
cd backend
SUPABASE_URL=https://example.com \
SUPABASE_SERVICE_ROLE_KEY=sb_test \
SUPABASE_JWT_SECRET=test \
python -c "from startup import reconcile_orphaned_runs; print('import ok')"
```

Expected: prints "import ok" with no traceback.

- [ ] **Step 4: Commit**

```bash
git add backend/startup.py backend/main.py
git commit -m "feat(startup): reconcile orphaned running rows on backend boot"
```

---

### Task 32: HistoryList frontend page

**Files:**
- Create: `frontend/src/pages/HistoryList.tsx`
- Test: `frontend/src/__tests__/HistoryList.test.tsx`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add API methods**

In `frontend/src/services/api.ts`:

```typescript
export type PrAnalysisRow = {
  id: string;
  project_id: string;
  pr_url: string;
  pr_number: number | null;
  pr_title: string | null;
  status: "running" | "completed" | "failed" | "cancelled";
  created_at: string;
  completed_at: string | null;
};

export type BugReportRow = {
  id: string;
  project_id: string;
  bug_description: string;
  severity: string | null;
  status: "running" | "completed" | "failed" | "cancelled";
  created_at: string;
  completed_at: string | null;
};

export async function listPrAnalyses(projectId: string): Promise<PrAnalysisRow[]> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/projects/${projectId}/pr-analyses`, {
    headers: { ...(await authHeaders()) },
  });
  if (!r.ok) throw new Error(`listPrAnalyses ${r.status}`);
  return r.json();
}

export async function listBugReports(projectId: string): Promise<BugReportRow[]> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/projects/${projectId}/bug-reports`, {
    headers: { ...(await authHeaders()) },
  });
  if (!r.ok) throw new Error(`listBugReports ${r.status}`);
  return r.json();
}

export async function getPrAnalysis(id: string): Promise<PrAnalysisRow & Record<string, unknown>> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/pr-analyses/${id}`, {
    headers: { ...(await authHeaders()) },
  });
  if (!r.ok) throw new Error(`getPrAnalysis ${r.status}`);
  return r.json();
}

export async function getBugReport(id: string): Promise<BugReportRow & Record<string, unknown>> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/bug-reports/${id}`, {
    headers: { ...(await authHeaders()) },
  });
  if (!r.ok) throw new Error(`getBugReport ${r.status}`);
  return r.json();
}
```

- [ ] **Step 2: Write the failing test**

Create `frontend/src/__tests__/HistoryList.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { HistoryList } from "../pages/HistoryList";
import * as api from "../services/api";

describe("HistoryList", () => {
  it("shows past PR analyses and bug reports", async () => {
    vi.spyOn(api, "listPrAnalyses").mockResolvedValue([
      {
        id: "r1", project_id: "p", pr_url: "https://github.com/o/r/pull/1",
        pr_number: 1, pr_title: "Add stuff", status: "completed",
        created_at: "2026-05-10T12:00:00Z", completed_at: "2026-05-10T12:05:00Z",
      },
    ]);
    vi.spyOn(api, "listBugReports").mockResolvedValue([
      {
        id: "b1", project_id: "p", bug_description: "crash on save",
        severity: "high", status: "completed",
        created_at: "2026-05-10T13:00:00Z", completed_at: "2026-05-10T13:10:00Z",
      },
    ]);

    render(
      <MemoryRouter initialEntries={["/projects/p/history"]}>
        <Routes>
          <Route path="/projects/:id/history" element={<HistoryList />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText(/Add stuff/)).toBeInTheDocument());
    expect(screen.getByText(/crash on save/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Implement HistoryList**

Create `frontend/src/pages/HistoryList.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  BugReportRow,
  listBugReports,
  listPrAnalyses,
  PrAnalysisRow,
} from "../services/api";

export function HistoryList() {
  const { id } = useParams<{ id: string }>();
  const [pr, setPr] = useState<PrAnalysisRow[]>([]);
  const [bugs, setBugs] = useState<BugReportRow[]>([]);

  useEffect(() => {
    if (!id) return;
    listPrAnalyses(id).then(setPr).catch(console.error);
    listBugReports(id).then(setBugs).catch(console.error);
  }, [id]);

  return (
    <div className="space-y-6">
      <section>
        <h2 className="mb-2 font-semibold">PR analyses</h2>
        <ul className="space-y-1">
          {pr.map((row) => (
            <li key={row.id} className="rounded border p-2 text-sm">
              <Link to={`/projects/${id}/history/pr/${row.id}`} className="underline">
                {row.pr_title ?? row.pr_url}
              </Link>
              <span className="ml-2 text-xs text-gray-500">{row.status} · {row.created_at}</span>
            </li>
          ))}
          {pr.length === 0 && <li className="text-sm text-gray-500">No PR analyses yet.</li>}
        </ul>
      </section>

      <section>
        <h2 className="mb-2 font-semibold">Bug reports</h2>
        <ul className="space-y-1">
          {bugs.map((row) => (
            <li key={row.id} className="rounded border p-2 text-sm">
              <Link to={`/projects/${id}/history/bug/${row.id}`} className="underline">
                {row.bug_description.slice(0, 80)}
              </Link>
              <span className="ml-2 text-xs text-gray-500">{row.status} · {row.created_at}</span>
            </li>
          ))}
          {bugs.length === 0 && <li className="text-sm text-gray-500">No bug reports yet.</li>}
        </ul>
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Wire route**

Update `frontend/src/App.tsx`, replacing the placeholder history route:

```tsx
import { HistoryList } from "./pages/HistoryList";
// ...
<Route path="history" element={<HistoryList />} />
```

- [ ] **Step 5: Run test**

Run:

```bash
cd frontend
npx vitest run src/__tests__/HistoryList.test.tsx
```

Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/HistoryList.tsx frontend/src/__tests__/HistoryList.test.tsx frontend/src/services/api.ts frontend/src/App.tsx
git commit -m "feat(frontend): HistoryList page + history API client"
```

---

### Task 33: Replay pages (read-only views of past runs)

**Files:**
- Create: `frontend/src/pages/PrAnalysisReplay.tsx`
- Create: `frontend/src/pages/BugReportReplay.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Implement PrAnalysisReplay**

Create `frontend/src/pages/PrAnalysisReplay.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getPrAnalysis } from "../services/api";

type Detail = {
  id: string;
  pr_url: string;
  pr_title: string | null;
  status: string;
  gather_output: unknown;
  unit_output: unknown;
  integration_output: unknown;
  e2e_output: unknown;
  final_result: unknown;
  created_at: string;
  completed_at: string | null;
};

function Section({ title, value }: { title: string; value: unknown }) {
  if (value == null) return null;
  return (
    <section className="rounded border p-3">
      <h3 className="mb-2 font-medium">{title}</h3>
      <pre className="overflow-x-auto whitespace-pre-wrap text-xs">{JSON.stringify(value, null, 2)}</pre>
    </section>
  );
}

export function PrAnalysisReplay() {
  const { id: projectId, runId } = useParams<{ id: string; runId: string }>();
  const [detail, setDetail] = useState<Detail | null>(null);

  useEffect(() => {
    if (!runId) return;
    getPrAnalysis(runId).then((d) => setDetail(d as Detail)).catch(console.error);
  }, [runId]);

  if (!detail) return <div className="p-4 text-sm text-gray-500">Loading…</div>;

  return (
    <div className="space-y-3">
      <Link to={`/projects/${projectId}/history`} className="text-sm underline">← History</Link>
      <h2 className="text-lg font-semibold">{detail.pr_title ?? detail.pr_url}</h2>
      <p className="text-xs text-gray-500">{detail.status} · {detail.created_at}</p>
      <Section title="Gather" value={detail.gather_output} />
      <Section title="Unit tests" value={detail.unit_output} />
      <Section title="Integration tests" value={detail.integration_output} />
      <Section title="E2E plan" value={detail.e2e_output} />
      <Section title="Final result" value={detail.final_result} />
    </div>
  );
}
```

- [ ] **Step 2: Implement BugReportReplay**

Create `frontend/src/pages/BugReportReplay.tsx` (analogous structure):

```tsx
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getBugReport } from "../services/api";

type Detail = {
  id: string;
  bug_description: string;
  severity: string | null;
  status: string;
  triage_output: unknown;
  mechanics_output: unknown;
  reproduction_output: unknown;
  research_output: unknown;
  report_output: unknown;
  final_report: unknown;
  created_at: string;
  completed_at: string | null;
};

function Section({ title, value }: { title: string; value: unknown }) {
  if (value == null) return null;
  return (
    <section className="rounded border p-3">
      <h3 className="mb-2 font-medium">{title}</h3>
      <pre className="overflow-x-auto whitespace-pre-wrap text-xs">{JSON.stringify(value, null, 2)}</pre>
    </section>
  );
}

export function BugReportReplay() {
  const { id: projectId, runId } = useParams<{ id: string; runId: string }>();
  const [detail, setDetail] = useState<Detail | null>(null);

  useEffect(() => {
    if (!runId) return;
    getBugReport(runId).then((d) => setDetail(d as Detail)).catch(console.error);
  }, [runId]);

  if (!detail) return <div className="p-4 text-sm text-gray-500">Loading…</div>;

  return (
    <div className="space-y-3">
      <Link to={`/projects/${projectId}/history`} className="text-sm underline">← History</Link>
      <h2 className="text-lg font-semibold">Bug: {detail.bug_description.slice(0, 100)}</h2>
      <p className="text-xs text-gray-500">{detail.status} · {detail.severity ?? "no severity"} · {detail.created_at}</p>
      <Section title="Triage" value={detail.triage_output} />
      <Section title="Mechanics" value={detail.mechanics_output} />
      <Section title="Reproduction" value={detail.reproduction_output} />
      <Section title="Research" value={detail.research_output} />
      <Section title="Report" value={detail.report_output} />
      <Section title="Final report" value={detail.final_report} />
    </div>
  );
}
```

- [ ] **Step 3: Wire routes**

Update `frontend/src/App.tsx`:

```tsx
import { PrAnalysisReplay } from "./pages/PrAnalysisReplay";
import { BugReportReplay } from "./pages/BugReportReplay";
// ...
<Route path="history/pr/:runId" element={<PrAnalysisReplay />} />
<Route path="history/bug/:runId" element={<BugReportReplay />} />
```

- [ ] **Step 4: Type-check**

Run:

```bash
cd frontend
npx tsc --noEmit
```

Expected: exits 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/PrAnalysisReplay.tsx frontend/src/pages/BugReportReplay.tsx frontend/src/App.tsx
git commit -m "feat(frontend): replay pages for past PR analyses and bug reports"
```

---

**Phase 4 complete.** Every run that completes (or partially completes) appears in the user's project history and can be viewed read-only.

---

## Phase 5 — Cross-cutting

### Task 34: Navbar with user menu

**Files:**
- Modify: `frontend/src/components/Navbar.tsx`

- [ ] **Step 1: Add user menu and sign-out button**

In `frontend/src/components/Navbar.tsx`, add:

```tsx
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthProvider";

export function Navbar() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  async function handleSignOut() {
    await signOut();
    navigate("/login");
  }

  return (
    <nav className="flex items-center justify-between border-b p-3">
      <Link to="/projects" className="font-semibold">Qlankr</Link>
      <div className="flex items-center gap-3 text-sm">
        <Link to="/settings" className="underline">Settings</Link>
        {user && (
          <>
            <span className="text-gray-500">{user.email}</span>
            <button onClick={handleSignOut} className="rounded border px-2 py-1">Sign out</button>
          </>
        )}
      </div>
    </nav>
  );
}
```

- [ ] **Step 2: Mount Navbar inside the authenticated shell**

In `frontend/src/App.tsx`, wrap routes that require auth with the navbar (use a layout route):

```tsx
import { Navbar } from "./components/Navbar";

function AuthedShell() {
  return (
    <>
      <Navbar />
      <Outlet />
    </>
  );
}

// Inside <Routes>:
<Route element={<RequireAuth><AuthedShell /></RequireAuth>}>
  <Route path="/projects" element={<ProjectsListPage />} />
  <Route path="/projects/:id" element={<ProjectDetailLayout />}>
    <Route index element={<GraphCanvas />} />
    <Route path="analyze" element={<PrAnalysisPanel />} />
    <Route path="bugs" element={<ResearchPanel />} />
    <Route path="history" element={<HistoryList />} />
    <Route path="history/pr/:runId" element={<PrAnalysisReplay />} />
    <Route path="history/bug/:runId" element={<BugReportReplay />} />
  </Route>
  <Route path="/settings" element={<SettingsPanel />} />
</Route>
```

Import `Outlet` from `react-router-dom` at the top.

- [ ] **Step 3: Type-check**

Run:

```bash
cd frontend
npx tsc --noEmit
```

Expected: exits 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Navbar.tsx frontend/src/App.tsx
git commit -m "feat(frontend): navbar with user menu + signed-in shell"
```

---

### Task 35: Docker-compose volume for graphs

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Inspect current docker-compose.yml**

Open `docker-compose.yml`. Locate the `backend` service and its current volumes list.

- [ ] **Step 2: Add a named volume**

Edit `docker-compose.yml`:

```yaml
services:
  backend:
    # ... existing ...
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
      - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
      - SUPABASE_JWT_SECRET=${SUPABASE_JWT_SECRET}
      - QLANKR_GRAPHS_ROOT=/data/graphs
      # ... existing LANGSMITH vars stay
    volumes:
      - qlankr_graphs:/data/graphs
      # ... existing code mounts stay

  frontend:
    # ... existing ...
    environment:
      - VITE_API_URL=${VITE_API_URL}
      - VITE_SUPABASE_URL=${VITE_SUPABASE_URL}
      - VITE_SUPABASE_ANON_KEY=${VITE_SUPABASE_ANON_KEY}

volumes:
  qlankr_graphs:
```

Remove `ANTHROPIC_API_KEY` and `GITHUB_TOKEN` from the backend environment list — they are no longer used.

- [ ] **Step 3: Smoke-test compose config**

Run:

```bash
docker compose config
```

Expected: prints resolved config without errors. The `qlankr_graphs` volume should appear.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(docker): named volume for per-user KuzuDB graphs; env vars updated"
```

---

### Task 36: Update .env.example and README

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Update `.env.example`**

Replace the contents of `.env.example` with:

```bash
# Supabase (required) — get these from https://supabase.com → Project Settings → API
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_JWT_SECRET=

# Same Supabase values, exposed to the Vite frontend build
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...

# Backend URL the frontend talks to
VITE_API_URL=http://localhost:8000

# Optional — LangSmith tracing
LANGSMITH_API_KEY=
LANGSMITH_TRACING=
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_PROJECT=qlankr

# Optional — override where per-user KuzuDB graphs live on the backend filesystem.
# In docker-compose this is set to /data/graphs.
QLANKR_GRAPHS_ROOT=
```

Note that `ANTHROPIC_API_KEY` and `GITHUB_TOKEN` are no longer here — they are entered per-user via the Settings UI after sign-in.

- [ ] **Step 2: Update README "Setup" section**

In `README.md`, replace the existing "Setup" section with:

```markdown
## Setup

**1. Create a Supabase project** (free tier is enough).

Sign up at https://supabase.com, create a project, and copy these values from
**Project Settings → API**:

- Project URL → `SUPABASE_URL` and `VITE_SUPABASE_URL`
- `anon` key → `SUPABASE_ANON_KEY` and `VITE_SUPABASE_ANON_KEY`
- `service_role` key → `SUPABASE_SERVICE_ROLE_KEY`
- JWT secret → `SUPABASE_JWT_SECRET`

**2. Apply the database schema.**

In the Supabase dashboard SQL editor, run both migration files in order:

- `backend/migrations/0001_initial_schema.sql`
- `backend/migrations/0002_profile_trigger.sql`

**3. Configure environment.**

```bash
git clone https://github.com/<your-org>/qlankr.git
cd qlankr
cp .env.example .env
# fill in the Supabase values from step 1
```

**4. Start.**

```bash
docker compose up
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000

Visit the frontend, sign up, then open **Settings** to add your Anthropic API
key, GitHub token, and any integration credentials (Jira, Notion, Grafana, etc.).
```

- [ ] **Step 3: Commit**

```bash
git add .env.example README.md
git commit -m "docs: update setup for Supabase + BYO keys"
```

---

### Task 37: Legacy registry migration script

**Files:**
- Create: `backend/scripts/migrate_legacy_registry.py`

- [ ] **Step 1: Create the dry-run script**

Create `backend/scripts/migrate_legacy_registry.py`:

```python
"""Surface legacy ~/.qlankr/registry.json contents.

This script does NOT write to the database. Legacy entries have no user_id
so we cannot safely auto-attribute them. The intended workflow:

1. Run this script.
2. Note the legacy projects.
3. Log into the new app as the appropriate user.
4. Add each repo URL via the Projects UI.
5. Re-trigger indexing on this machine.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    path = Path(os.environ.get("HOME", "~")).expanduser() / ".qlankr" / "registry.json"
    if not path.exists():
        print(f"No legacy registry found at {path}")
        return 0

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        print(f"Could not parse {path}: {e}", file=sys.stderr)
        return 1

    if not data:
        print(f"{path} is empty.")
        return 0

    print(f"Legacy registry at {path} contains {len(data)} projects:\n")
    for key, meta in data.items():
        repo_name = meta.get("repo_name") or key
        path_ = meta.get("path", "?")
        print(f"  - {key}")
        print(f"      repo_name: {repo_name}")
        print(f"      path:      {path_}")
    print("\nNext step: log into the app as the user who owns each project")
    print("and re-add each repo URL via the Projects UI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke-test the script with a fake registry**

Run:

```bash
mkdir -p /tmp/fakehome/.qlankr
echo '{"foo/bar": {"repo_name": "foo/bar", "path": "/tmp/foo_bar"}}' > /tmp/fakehome/.qlankr/registry.json
HOME=/tmp/fakehome python backend/scripts/migrate_legacy_registry.py
```

Expected: prints "Legacy registry at /tmp/fakehome/.qlankr/registry.json contains 1 projects".

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/migrate_legacy_registry.py
git commit -m "feat(scripts): dry-run legacy registry surfacing script"
```

---

### Task 38: Manual end-to-end smoke test

This is a manual operator task — no code commits.

- [ ] **Step 1: Apply migrations to your dev Supabase project** (already done in Task 5; verify tables exist).

- [ ] **Step 2: Start the stack**

```bash
docker compose up --build
```

- [ ] **Step 3: Sign up**

Open http://localhost:5173, click "Sign up", create an account, confirm email if required.

- [ ] **Step 4: Add API keys**

Navigate to Settings, paste an Anthropic API key and a GitHub token. Save.

- [ ] **Step 5: Add a project**

On the Projects page, paste a GitHub repo URL and click Add. Verify the row appears with status `pending`.

- [ ] **Step 6: Index the project**

Click into the project. Trigger indexing (mechanism depends on whether the indexing UI uses an explicit "Index" button or auto-runs). Verify SSE events stream, status transitions to `indexing` then `ready`.

- [ ] **Step 7: Run a PR analysis**

Open the Analyze tab, paste a PR URL, run analysis. After it completes, navigate to History and verify the run appears with all stages populated.

- [ ] **Step 8: Run a bug reproduction**

Open the Bugs tab, describe a bug, run reproduction. After it completes, verify it appears in History.

- [ ] **Step 9: Verify per-user isolation**

In an incognito window, sign up as a second user. Verify their Projects page is empty and they cannot see the first user's project at `/projects/<id1>` (should 404).

- [ ] **Step 10: Verify restart reconciliation**

While a run is in progress, `docker compose restart backend`. After restart, navigate to History — the previously-running row should now show `cancelled` with `failure_reason: 'backend restarted'`.

---

## Self-review

### Spec coverage

- §3 decisions on auth/host/graph storage/history/durability/keys/schema/encryption/quota/cache/migration → all covered across Phases 0–5.
- §5 schema (5 tables) → Task 3.
- §6 auth flow → Tasks 6, 10–13.
- §7 backend changes:
  - §7.1 new modules → Tasks 6, 7, 8, 24, 31.
  - §7.2 modified modules and endpoints → Tasks 16, 17, 19, 20, 25, 26, 28, 29, 30.
  - §7.3 SSE behaviour → Task 28 includes the "DB-write failures don't block SSE" pattern.
  - §7.4 MCP-client-per-user → Task 26.
  - §7.5 startup reconciliation → Task 31.
- §8 frontend changes → Tasks 11, 12, 13, 14, 15, 21, 22, 23, 27, 32, 33, 34.
- §9 per-user KuzuDB layout → Tasks 18, 19, 35.
- §10 deployment + env vars + docker-compose + migrations → Tasks 35, 36, 37.
- §11 risks → all addressed or surfaced; Task 31 closes risk #7.
- §12 deferred items → not implemented (correct).

### Placeholder scan

- No "TBD" / "TODO" / "fill in" left in plan steps.
- No "similar to Task N" — code blocks repeat where needed.
- All steps have concrete commands or code.

### Type consistency

- `UserCredentials` field names (`anthropic_api_key`, `github_token`, `jira`, etc.) match between Task 24 (definition), Task 25 (endpoint body field names), Task 26 (consumer), and Task 27 (frontend body fields).
- Stage column names in Task 28 (`gather_output`, `unit_output`, `integration_output`, `e2e_output`) match the schema in Task 3.
- Stage column names in Task 29 (`triage_output`, `mechanics_output`, `reproduction_output`, `research_output`, `report_output`) match Task 3.
- Status enum values (`running` / `completed` / `failed` / `cancelled`) consistent across Tasks 3, 28, 29, 31.
- `local_graph_present` flag name consistent across Tasks 20 (backend), 22 (frontend).
- `Project` type fields in Task 21 match the schema in Task 3.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-10-supabase-persistence.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
