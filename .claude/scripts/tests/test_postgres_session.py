"""Tests for PostgresSessionStore — skipped unless TEST_DATABASE_URL is set."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "chat"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not TEST_DB_URL, reason="TEST_DATABASE_URL not set")

from session import PostgresSessionStore, Session  # noqa: E402


@pytest.fixture
def store():
    s = PostgresSessionStore(TEST_DB_URL)
    conn = s._get_conn()
    conn.cursor().execute("DELETE FROM chat_sessions")
    conn.commit()
    yield s
    conn = s._get_conn()
    conn.cursor().execute("DELETE FROM chat_sessions")
    conn.commit()


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
    s.message_count = 5
    store.update(s)
    result = store.get("whatsapp", "61410868612@c.us", "")
    assert result.agent_session_id == "sdk-updated"
    assert result.message_count == 5


def test_list_active(store):
    store.create(_make_session("whatsapp:a@c.us:"))
    store.create(_make_session("whatsapp:b@c.us:"))
    active = store.list_active()
    assert len(active) == 2


def test_list_active_by_platform(store):
    store.create(_make_session("whatsapp:a@c.us:"))
    active = store.list_active(platform="whatsapp")
    assert len(active) == 1
    none = store.list_active(platform="slack")
    assert len(none) == 0


def test_get_session_store_returns_postgres():
    from session import get_session_store

    store = get_session_store()
    assert isinstance(store, PostgresSessionStore)
