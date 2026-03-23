import json

import pytest

from indexer import _detect_stage, _parse_owner_repo, _read_graph_data


# --- _parse_owner_repo ---

def test_parse_owner_repo_standard_url():
    owner, repo = _parse_owner_repo("https://github.com/alice/myrepo")
    assert owner == "alice"
    assert repo == "myrepo"


def test_parse_owner_repo_strips_git_suffix():
    owner, repo = _parse_owner_repo("https://github.com/alice/myrepo.git")
    assert owner == "alice"
    assert repo == "myrepo"


def test_parse_owner_repo_rejects_short_path():
    with pytest.raises(ValueError):
        _parse_owner_repo("https://github.com/alice")


def test_parse_owner_repo_rejects_no_path():
    with pytest.raises(ValueError):
        _parse_owner_repo("https://github.com/")


# --- _detect_stage ---

def test_detect_stage_clone_keyword():
    assert _detect_stage("Cloning repository into /tmp/...") == "clone"


def test_detect_stage_cloning_keyword():
    assert _detect_stage("cloning owner/repo") == "clone"


def test_detect_stage_parsing_keyword():
    assert _detect_stage("Parsing source files with Tree-sitter") == "parsing"


def test_detect_stage_cluster_keyword():
    assert _detect_stage("Running clustering algorithm (Leiden)") == "clustering"


def test_detect_stage_resolve_keyword():
    assert _detect_stage("Resolving cross-file imports") == "resolution"


def test_detect_stage_unknown_defaults_to_analyze():
    assert _detect_stage("foobar xyzzy 12345") == "analyze"


# --- _read_graph_data ---

def test_read_graph_data_no_dir(tmp_path):
    result = _read_graph_data(str(tmp_path))
    assert result.nodes == []
    assert result.edges == []
    assert result.clusters == []


def test_read_graph_data_unified_graph_json(tmp_path):
    gn_dir = tmp_path / ".gitnexus"
    gn_dir.mkdir()
    data = {
        "nodes": [{"id": "n1", "label": "file.py", "type": "file", "cluster": "auth"}],
        "edges": [{"source": "n1", "target": "n2", "type": "CALLS"}],
        "clusters": [{"id": "auth", "label": "Auth", "size": 1}],
    }
    (gn_dir / "graph.json").write_text(json.dumps(data))

    result = _read_graph_data(str(tmp_path))

    assert len(result.nodes) == 1
    assert result.nodes[0].id == "n1"
    assert result.nodes[0].type == "file"
    assert len(result.edges) == 1
    assert result.edges[0].type == "CALLS"
    assert len(result.clusters) == 1
    assert result.clusters[0].id == "auth"


def test_read_graph_data_invalid_node_type_coercion(tmp_path):
    gn_dir = tmp_path / ".gitnexus"
    gn_dir.mkdir()
    data = {
        "nodes": [{"id": "n1", "label": "x", "type": "unknown", "cluster": "c"}],
        "edges": [],
        "clusters": [],
    }
    (gn_dir / "graph.json").write_text(json.dumps(data))

    result = _read_graph_data(str(tmp_path))
    assert result.nodes[0].type == "file"  # coerced from "unknown"


def test_read_graph_data_invalid_edge_type_coercion(tmp_path):
    gn_dir = tmp_path / ".gitnexus"
    gn_dir.mkdir()
    data = {
        "nodes": [],
        "edges": [{"source": "a", "target": "b", "type": "CONTAINS"}],
        "clusters": [],
    }
    (gn_dir / "graph.json").write_text(json.dumps(data))

    result = _read_graph_data(str(tmp_path))
    assert result.edges[0].type == "CALLS"  # coerced from "CONTAINS"


def test_read_graph_data_fallback_split_files(tmp_path):
    gn_dir = tmp_path / ".gitnexus"
    gn_dir.mkdir()
    (gn_dir / "clusters.json").write_text(
        json.dumps([{"id": "auth", "label": "Auth", "size": 2}])
    )
    (gn_dir / "nodes.json").write_text(
        json.dumps([{"id": "n1", "label": "f.py", "type": "file", "cluster": "auth"}])
    )
    (gn_dir / "edges.json").write_text(
        json.dumps([{"source": "n1", "target": "n2", "type": "IMPORTS"}])
    )

    result = _read_graph_data(str(tmp_path))

    assert len(result.clusters) == 1
    assert len(result.nodes) == 1
    assert len(result.edges) == 1
    assert result.edges[0].type == "IMPORTS"


def test_read_graph_data_partial_split_files(tmp_path):
    gn_dir = tmp_path / ".gitnexus"
    gn_dir.mkdir()
    (gn_dir / "clusters.json").write_text(
        json.dumps([{"id": "auth", "label": "Auth", "size": 2}])
    )
    # No nodes.json, no edges.json

    result = _read_graph_data(str(tmp_path))

    assert len(result.clusters) == 1
    assert result.nodes == []
    assert result.edges == []
