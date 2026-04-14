from agent.sessions import (
    clear_sessions,
    create_session,
    get_session,
    update_session,
)


def test_create_session_generates_unique_ids():
    clear_sessions()
    a = create_session("https://github.com/o/a/pull/1")
    b = create_session("https://github.com/o/b/pull/2")
    assert a.session_id != b.session_id
    assert len(a.session_id) == 12


def test_get_session_returns_none_for_unknown():
    clear_sessions()
    assert get_session("doesnotexist") is None


def test_update_session_modifies_only_specified_fields():
    clear_sessions()
    s = create_session("https://github.com/x/y/pull/3")
    assert s.current_stage == "gathering"
    update_session(s.session_id, current_stage="unit_testing", thread_id="t-1")
    loaded = get_session(s.session_id)
    assert loaded is not None
    assert loaded.current_stage == "unit_testing"
    assert loaded.thread_id == "t-1"
    assert loaded.pr_url == "https://github.com/x/y/pull/3"


def test_to_status_dict_fields():
    clear_sessions()
    s = create_session("https://github.com/x/y/pull/3")
    update_session(s.session_id, intermediate_result={"a": 1})
    d = get_session(s.session_id).to_status_dict()
    assert d["session_id"] == s.session_id
    assert d["current_stage"] == "gathering"
    assert "created_at" in d
    assert d["intermediate_result"] == {"a": 1}
