"""Unit tests for chat/engine.py — mocks sdk_compat.query."""

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
