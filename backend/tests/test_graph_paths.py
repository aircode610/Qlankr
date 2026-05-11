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
