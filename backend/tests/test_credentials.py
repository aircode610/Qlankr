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
    save_credentials(uid, anthropic_api_key="sk-2")
    creds = load_credentials(uid)
    assert creds.anthropic_api_key == "sk-2"
    assert creds.github_token == "ghp_1"


def test_credentials_are_per_user(fake_supabase):
    uid_a, uid_b = uuid4(), uuid4()
    save_credentials(uid_a, anthropic_api_key="sk-a")
    save_credentials(uid_b, anthropic_api_key="sk-b")
    assert load_credentials(uid_a).anthropic_api_key == "sk-a"
    assert load_credentials(uid_b).anthropic_api_key == "sk-b"
