"""History store — round-trip tests."""

from __future__ import annotations

from pathlib import Path

from clawdeck.core.history import HistoryStore


def test_create_and_list_sessions(tmp_path: Path):
    store = HistoryStore(tmp_path / "chats.db")
    s1 = store.create_session("Hello")
    s2 = store.create_session("World")
    rows = store.list_sessions()
    assert {r.id for r in rows} == {s1.id, s2.id}
    assert rows[0].title in {"Hello", "World"}


def test_add_and_list_messages(tmp_path: Path):
    store = HistoryStore(tmp_path / "chats.db")
    s = store.create_session("chat")
    store.add_message(s.id, "user", "hi")
    m = store.add_message(s.id, "agent", "hello!", tokens_in=2, tokens_out=3)
    msgs = store.list_messages(s.id)
    assert [x.text for x in msgs] == ["hi", "hello!"]
    assert m.tokens_out == 3


def test_delete_session_cascades(tmp_path: Path):
    store = HistoryStore(tmp_path / "chats.db")
    s = store.create_session("x")
    store.add_message(s.id, "user", "hi")
    store.delete_session(s.id)
    assert store.list_messages(s.id) == []
    assert store.list_sessions() == []


def test_rename_and_star(tmp_path: Path):
    store = HistoryStore(tmp_path / "chats.db")
    s = store.create_session("initial")
    store.rename_session(s.id, "renamed")
    store.star_session(s.id, True)
    rows = store.list_sessions()
    assert rows[0].title == "renamed"
    assert rows[0].starred is True


def test_daily_tokens_aggregates(tmp_path: Path):
    store = HistoryStore(tmp_path / "chats.db")
    s = store.create_session("t")
    store.add_message(s.id, "user", "a", tokens_in=5, tokens_out=0)
    store.add_message(s.id, "agent", "b", tokens_in=0, tokens_out=10)
    daily = store.daily_tokens(days=7)
    assert len(daily) == 1
    _, tin, tout = daily[0]
    assert tin == 5
    assert tout == 10


def test_profile_filter(tmp_path: Path):
    store = HistoryStore(tmp_path / "chats.db")
    store.create_session("a", profile="local")
    store.create_session("b", profile="vps")
    local = store.list_sessions(profile="local")
    vps = store.list_sessions(profile="vps")
    assert len(local) == 1 and local[0].profile == "local"
    assert len(vps) == 1 and vps[0].profile == "vps"
