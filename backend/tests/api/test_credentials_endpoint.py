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
