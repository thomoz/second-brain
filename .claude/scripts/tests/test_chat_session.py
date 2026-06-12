"""Unit tests for chat/session.py — uses :memory: SQLite."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "chat"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from session import SQLiteSessionStore, Session, get_session_store


@pytest.fixture
def store(tmp_path):
    return SQLiteSessionStore(tmp_path / "test_chat.db")


def _make_session(session_id: str = "whatsapp:61410868612@c.us:") -> Session:
    now = datetime.now()
    return Session(
        session_id=session_id,
        agent_session_id="sdk-abc123",
        platform="whatsapp",
        channel_id="61410868612@c.us",
        thread_id="",
        user_id="61410868612@c.us",
        created_at=now,
        updated_at=now,
        message_count=1,
        total_cost_usd=0.01,
    )


def test_create_and_get(store):
    s = _make_session()
    store.create(s)
    result = store.get("whatsapp", "61410868612@c.us", "")
    assert result is not None
    assert result.agent_session_id == "sdk-abc123"


def test_get_nonexistent(store):
    result = store.get("whatsapp", "unknown@c.us", "")
    assert result is None


def test_update(store):
    s = _make_session()
    store.create(s)
    s.agent_session_id = "sdk-updated"
    s.message_count = 2
    store.update(s)
    result = store.get("whatsapp", "61410868612@c.us", "")
    assert result.agent_session_id == "sdk-updated"
    assert result.message_count == 2


def test_list_active(store):
    store.create(_make_session("whatsapp:a@c.us:"))
    store.create(_make_session("whatsapp:b@c.us:"))
    active = store.list_active()
    assert len(active) == 2


def test_get_session_store_returns_sqlite(tmp_path):
    store = get_session_store(tmp_path / "chat.db")
    assert isinstance(store, SQLiteSessionStore)
