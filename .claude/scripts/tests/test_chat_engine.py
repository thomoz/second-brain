"""Unit tests for chat/engine.py â€” mocks sdk_compat.query."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure chat/ and scripts/ are on path before any local imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "chat"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Mock claude_agent_sdk before importing engine (not installed in this test env)
_mock_sdk = MagicMock()
sys.modules.setdefault("claude_agent_sdk", _mock_sdk)

import pytest
from models import Channel, IncomingMessage, Platform, User
from session import SQLiteSessionStore
from engine import ConversationEngine


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


@pytest.fixture
def store(tmp_path):
    return SQLiteSessionStore(tmp_path / "test_engine.db")


@pytest.fixture
def engine(store):
    return ConversationEngine(store, PROJECT_ROOT, max_turns=5, max_budget_usd=0.10)


def _make_incoming(text: str = "hello") -> IncomingMessage:
    return IncomingMessage(
        text=text,
        user=User(Platform.WHATSAPP, "61410868612@c.us"),
        channel=Channel(Platform.WHATSAPP, "61410868612@c.us", is_dm=True),
        platform=Platform.WHATSAPP,
    )


@pytest.mark.asyncio
async def test_handle_message_new_session(engine, store):
    """Engine creates session and returns response text."""
    mock_assistant = MagicMock()
    mock_assistant.__class__.__name__ = "AssistantMessage"
    mock_text_block = MagicMock()
    mock_text_block.__class__.__name__ = "TextBlock"
    mock_text_block.text = "You have 3 events today."
    mock_assistant.content = [mock_text_block]

    mock_result = MagicMock()
    mock_result.__class__.__name__ = "ResultMessage"
    mock_result.session_id = "sdk-session-abc"
    mock_result.total_cost_usd = 0.005

    async def mock_query(prompt, options=None):
        yield mock_assistant
        yield mock_result

    with patch("engine.query", side_effect=mock_query):
        with patch("engine.AssistantMessage", type(mock_assistant)):
            with patch("engine.TextBlock", type(mock_text_block)):
                with patch("engine.ResultMessage", type(mock_result)):
                    responses = []
                    async for msg in engine.handle_message(_make_incoming()):
                        responses.append(msg)

    assert len(responses) == 1
    assert "3 events" in responses[0].text

    # Session should be persisted
    session = store.get("whatsapp", "61410868612@c.us", "")
    assert session is not None
    assert session.agent_session_id == "sdk-session-abc"


@pytest.mark.asyncio
async def test_reset_no_existing_session(engine, store):
    """Reset phrase with no prior session returns confirmation without calling the LLM."""
    with patch("engine.query") as mock_query:
        responses = []
        async for msg in engine.handle_message(_make_incoming("new conversation thread")):
            responses.append(msg)

    assert len(responses) == 1
    assert "reset" in responses[0].text.lower()
    mock_query.assert_not_called()


@pytest.mark.asyncio
async def test_reset_with_existing_session(engine, store):
    """Reset phrase with a prior session calls reset_session and returns confirmation without LLM."""
    from session import Session
    store.create(Session(
        session_id="whatsapp:61410868612@c.us:",
        agent_session_id="codex-thread-xyz",
        platform="whatsapp",
        channel_id="61410868612@c.us",
        thread_id="",
        user_id="61410868612@c.us",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        message_count=5,
    ))

    with patch("engine.query") as mock_query:
        with patch("codex_sdk_compat.reset_session") as mock_reset:
            responses = []
            async for msg in engine.handle_message(_make_incoming("new conversation thread")):
                responses.append(msg)

    assert len(responses) == 1
    assert "reset" in responses[0].text.lower()
    mock_query.assert_not_called()
    mock_reset.assert_called_once_with("codex-thread-xyz")


@pytest.mark.asyncio
async def test_reset_case_insensitive(engine, store):
    """Reset phrase triggers regardless of capitalisation."""
    with patch("engine.query") as mock_query:
        responses = []
        async for msg in engine.handle_message(_make_incoming("New Conversation Thread")):
            responses.append(msg)

    assert len(responses) == 1
    assert "reset" in responses[0].text.lower()
    mock_query.assert_not_called()
