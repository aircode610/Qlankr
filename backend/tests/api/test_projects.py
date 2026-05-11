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
