import pytest

from indexer import (
    _detect_stage,
    _parse_markdown_table,
    _parse_owner_repo,
    _split_row,
    _to_records,
    _unwrap_text,
)


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


# --- _split_row ---

def test_split_row_three_columns():
    assert _split_row("| a | b | c |") == ["a", "b", "c"]


def test_split_row_single_column():
    assert _split_row("| single |") == ["single"]


def test_split_row_separator_row():
    assert _split_row("| --- | --- |") == ["---", "---"]


def test_split_row_no_leading_pipe():
    assert _split_row("a | b | c") == []


def test_split_row_strips_whitespace():
    assert _split_row("|  foo  |  bar  |") == ["foo", "bar"]


# --- _unwrap_text ---

def test_unwrap_text_plain_string():
    assert _unwrap_text("hello") == "hello"


def test_unwrap_text_object_with_content():
    class Msg:
        content = "from content attr"
    assert _unwrap_text(Msg()) == "from content attr"


def test_unwrap_text_list_of_text_blocks():
    blocks = [{"type": "text", "text": "part1"}, {"type": "text", "text": "part2"}]
    assert _unwrap_text(blocks) == "part1\npart2"


def test_unwrap_text_list_skips_non_text_blocks():
    blocks = [{"type": "image", "url": "x"}, {"type": "text", "text": "ok"}]
    assert _unwrap_text(blocks) == "ok"


def test_unwrap_text_non_string_returns_empty():
    assert _unwrap_text(42) == ""


def test_unwrap_text_empty_string():
    assert _unwrap_text("") == ""


# --- _to_records ---

def test_to_records_empty_string():
    assert _to_records("") == []


def test_to_records_json_array():
    import json
    data = [{"id": "a", "val": 1}, {"id": "b", "val": 2}]
    assert _to_records(json.dumps(data)) == data


def test_to_records_json_dict():
    import json
    data = {"key": "value"}
    assert _to_records(json.dumps(data)) == [data]


def test_to_records_json_with_markdown_key():
    import json
    md = "| name |\n| --- |\n| alice |"
    assert _to_records(json.dumps({"markdown": md})) == [{"name": "alice"}]


def test_to_records_raw_markdown_table():
    md = "| col1 | col2 |\n| --- | --- |\n| x | y |"
    result = _to_records(md)
    assert result == [{"col1": "x", "col2": "y"}]


def test_to_records_strips_prose_footer():
    import json
    data = [{"id": "a"}]
    text = json.dumps(data) + "\n---\n**Next:** do something"
    assert _to_records(text) == data


def test_to_records_filters_non_dict_items():
    import json
    # list containing a non-dict element
    assert _to_records(json.dumps([{"a": 1}, "not a dict", 42])) == [{"a": 1}]


# --- _parse_markdown_table ---

def test_parse_markdown_table_basic():
    md = "| name | value |\n| --- | --- |\n| foo | bar |"
    assert _parse_markdown_table(md) == [{"name": "foo", "value": "bar"}]


def test_parse_markdown_table_multiple_rows():
    md = "| x |\n| --- |\n| 1 |\n| 2 |"
    result = _parse_markdown_table(md)
    assert len(result) == 2
    # JSON-parseable cells are decoded (1 → int)
    assert result[0] == {"x": 1}
    assert result[1] == {"x": 2}


def test_parse_markdown_table_json_cell_value():
    import json
    node = {"id": "File:foo.py", "name": "foo.py"}
    md = f"| f |\n| --- |\n| {json.dumps(node)} |"
    result = _parse_markdown_table(md)
    assert result == [{"f": node}]


def test_parse_markdown_table_skips_wrong_column_count():
    md = "| a | b |\n| --- | --- |\n| only_one |\n| x | y |"
    result = _parse_markdown_table(md)
    assert result == [{"a": "x", "b": "y"}]


def test_parse_markdown_table_empty_string():
    assert _parse_markdown_table("") == []


def test_parse_markdown_table_only_header():
    assert _parse_markdown_table("| a | b |") == []
