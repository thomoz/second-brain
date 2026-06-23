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
import engine as engine_module


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

    with patch("engine._check_and_clear_profile_timeout", return_value=False):
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
        with patch("engine.reset_session") as mock_reset:
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


@pytest.mark.asyncio
async def test_ask_me_questions_resets_thread(engine, store):
    """Ask Me Questions resets the existing thread before entering profile mode."""
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

    mock_assistant = MagicMock()
    mock_assistant.__class__.__name__ = "AssistantMessage"
    mock_text_block = MagicMock()
    mock_text_block.__class__.__name__ = "TextBlock"
    mock_text_block.text = "Great, let us begin."
    mock_assistant.content = [mock_text_block]

    mock_result = MagicMock()
    mock_result.__class__.__name__ = "ResultMessage"
    mock_result.session_id = "sdk-session-new"
    mock_result.total_cost_usd = 0.005

    async def mock_query(prompt, options=None):
        yield mock_assistant
        yield mock_result

    with patch("engine.query", side_effect=mock_query):
        with patch("engine.AssistantMessage", type(mock_assistant)):
            with patch("engine.TextBlock", type(mock_text_block)):
                with patch("engine.ResultMessage", type(mock_result)):
                    with patch("engine.reset_session") as mock_reset:
                        responses = []
                        async for msg in engine.handle_message(_make_incoming("ask me questions")):
                            responses.append(msg)

    assert len(responses) == 1
    mock_reset.assert_called_once_with("codex-thread-xyz")


# ---------------------------------------------------------------------------
# _load_assistant_commands tests
# ---------------------------------------------------------------------------

def test_load_assistant_commands_returns_content(tmp_path):
    """_load_assistant_commands returns file content when ASSISTANT.md exists."""
    memory_dir = tmp_path / "Memory"
    memory_dir.mkdir()
    (memory_dir / "ASSISTANT.md").write_text("# Save Commands\nroute here", encoding="utf-8")
    result = engine_module._load_assistant_commands(tmp_path)
    assert "Save Commands" in result
    assert "route here" in result


def test_load_assistant_commands_missing_returns_empty(tmp_path):
    """_load_assistant_commands returns empty string when ASSISTANT.md is absent."""
    result = engine_module._load_assistant_commands(tmp_path)
    assert result == ""


@pytest.mark.asyncio
async def test_system_prompt_includes_assistant_commands(engine, store):
    """handle_message injects ASSISTANT.md into system_prompt when file exists."""
    memory_dir = engine.project_root / "Memory"
    assistant_file = memory_dir / "ASSISTANT.md"
    original = assistant_file.read_text(encoding="utf-8") if assistant_file.exists() else None

    sentinel = "SENTINEL_SAVE_COMMANDS_TEST"
    assistant_file.write_text(sentinel, encoding="utf-8")

    captured_options = {}

    async def mock_query(prompt, options=None):
        captured_options["system_prompt"] = options.system_prompt if options else ""
        yield MagicMock(**{"__class__.__name__": "ResultMessage",
                           "session_id": "s1", "total_cost_usd": 0.0})

    try:
        with patch("engine._check_and_clear_profile_timeout", return_value=False):
            with patch("engine.query", side_effect=mock_query):
                with patch("engine.ResultMessage"):
                    async for _ in engine.handle_message(_make_incoming("test")):
                        pass
        assert sentinel in captured_options.get("system_prompt", "")
    finally:
        if original is not None:
            assistant_file.write_text(original, encoding="utf-8")
        elif assistant_file.exists():
            assistant_file.unlink()


@pytest.mark.asyncio
async def test_allowed_tools_includes_websearch(engine, store):
    """handle_message passes WebSearch in allowed_tools to the query call."""
    captured_options = {}

    async def mock_query(prompt, options=None):
        captured_options["allowed_tools"] = options.allowed_tools if options else []
        yield MagicMock(**{"__class__.__name__": "ResultMessage",
                           "session_id": "s1", "total_cost_usd": 0.0})

    with patch("engine._check_and_clear_profile_timeout", return_value=False):
        with patch("engine.query", side_effect=mock_query):
            with patch("engine.ResultMessage"):
                async for _ in engine.handle_message(_make_incoming("test")):
                    pass
    assert "WebSearch" in captured_options.get("allowed_tools", [])
    assert "Write" in captured_options.get("allowed_tools", [])
