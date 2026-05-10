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


def test_insert_clobbers_attacker_supplied_user_id(fake):
    uid_a, uid_b = uuid4(), uuid4()
    scoped = UserScoped(fake, uid_a)
    scoped.table("projects").insert({"repo_url": "z", "user_id": str(uid_b)}).execute()

    rows = fake.table("projects").select("*").execute().data
    assert len(rows) == 1
    assert rows[0]["user_id"] == str(uid_a)  # not uid_b


def test_upsert_does_not_touch_other_users_row(fake):
    uid_a, uid_b = uuid4(), uuid4()
    fake.table("user_credentials").insert({"user_id": str(uid_b), "anthropic_api_key": "uid_b_key"}).execute()

    scoped_a = UserScoped(fake, uid_a)
    scoped_a.table("user_credentials").upsert({"anthropic_api_key": "uid_a_key"}).execute()

    rows = fake.table("user_credentials").select("*").execute().data
    by_uid = {r["user_id"]: r["anthropic_api_key"] for r in rows}
    assert by_uid[str(uid_a)] == "uid_a_key"
    assert by_uid[str(uid_b)] == "uid_b_key"  # unchanged
