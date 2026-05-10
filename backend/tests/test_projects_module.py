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
