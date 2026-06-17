"""Conversation engine: routes WhatsApp messages through sdk_compat with session persistence."""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any


def _profile_session_state_path(project_root: Path) -> Path:
    return project_root / ".claude" / "data" / "state" / "profile-session.json"


def _save_profile_session_state(project_root: Path, channel_id: str) -> None:
    from shared import load_state, save_state
    state_path = _profile_session_state_path(project_root)
    state = load_state(state_path)
    now_str = datetime.now().isoformat()
    state[channel_id] = {"started_at": now_str, "last_message_at": now_str}
    save_state(state_path, state)


def _update_profile_session_timestamp(project_root: Path, channel_id: str) -> None:
    from shared import load_state, save_state
    state_path = _profile_session_state_path(project_root)
    state = load_state(state_path)
    if channel_id in state:
        state[channel_id]["last_message_at"] = datetime.now().isoformat()
        save_state(state_path, state)


def _check_and_clear_profile_timeout(project_root: Path, channel_id: str, timeout_minutes: int = 10) -> bool:
    """Returns True if a profile session exists and has been silent for > timeout_minutes."""
    from shared import load_state, save_state
    state_path = _profile_session_state_path(project_root)
    state = load_state(state_path)
    if channel_id not in state:
        return False
    last = datetime.fromisoformat(state[channel_id]["last_message_at"])
    if (datetime.now() - last).total_seconds() > timeout_minutes * 60:
        del state[channel_id]
        save_state(state_path, state)
        return True
    return False

_CHAT_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _CHAT_DIR.parent / "scripts"
sys.path.insert(0, str(_CHAT_DIR))
sys.path.insert(0, str(_SCRIPTS_DIR))

from models import IncomingMessage, OutgoingMessage  # noqa: E402
from session import Session, SQLiteSessionStore  # noqa: E402

from sanitize import TRUST_BOUNDARY_INSTRUCTION, check_injection_patterns  # noqa: E402
from shared import append_to_daily_log  # noqa: E402
from sdk_compat import (  # noqa: E402
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)


class ConversationEngine:
    """Routes incoming messages to the LLM backend with session persistence.

    Uses sdk_compat so the backend (Claude, Pi, Codex) is swappable by env var.
    Read-only Memory access only: allowed_tools = ["Read", "Glob", "Grep"].
    """

    def __init__(
        self,
        session_store: SQLiteSessionStore,
        project_root: Path,
        max_turns: int = 20,
        max_budget_usd: float = 0.50,
    ) -> None:
        self.session_store = session_store
        self.project_root = project_root
        self.max_turns = max_turns
        self.max_budget_usd = max_budget_usd

    async def handle_message(self, message: IncomingMessage) -> AsyncIterator[OutgoingMessage]:
        """Process an incoming message and yield a single response OutgoingMessage."""
        # WhatsApp has no threads — channel_id is the session key
        thread_id = ""
        platform_str = message.platform.value
        channel_id = message.channel.platform_id

        existing = self.session_store.get(platform_str, channel_id, thread_id)

        # Injection detection on incoming message (log only — never block Shaun)
        injection_flags = check_injection_patterns(message.text)
        if injection_flags:
            names = ", ".join(f[0] for f in injection_flags)
            print(f"[{datetime.now()}] [SECURITY] WhatsApp injection patterns detected: {names}")

        # Ask Me Questions profile-building mode detection
        _AQM_PHRASES = ["ask me questions", "ask me a question", "coaching session", "profile building", "build my profile"]
        _is_profile_mode = any(phrase in message.text.lower() for phrase in _AQM_PHRASES)

        # Check for 10-min timeout on active profile session (BEFORE LLM call)
        if not _is_profile_mode and _check_and_clear_profile_timeout(self.project_root, channel_id):
            yield OutgoingMessage(
                text="Profile session ended (10 min timeout). I've saved everything we covered to your profile. Type 'ask me questions' any time to continue.",
                channel=message.channel,
                thread=message.thread,
            )
            return

        # Build system prompt from SOUL.md + WhatsApp rules
        try:
            soul_text = (self.project_root / "Memory" / "SOUL.md").read_text(encoding="utf-8")
        except Exception:
            soul_text = "You are Shaun's Second Brain assistant."

        system_prompt = (
            soul_text
            + "\n\n# WhatsApp Chat Bot Rules\n"
            "You are responding via WhatsApp (possibly via CarPlay / Siri). "
            "Be concise and use plain text only — no markdown headers, no bullet formatting "
            "that sounds bad read aloud.\n"
            "Give a single, complete answer. Do not split across multiple turns.\n"
            "Keep answers short enough to read on a phone screen.\n"
            f"\n\n{TRUST_BOUNDARY_INSTRUCTION}"
        )

        if _is_profile_mode:
            skill_path = self.project_root / ".claude" / "skills" / "ask-me-questions" / "SKILL.md"
            try:
                skill_text = skill_path.read_text(encoding="utf-8")
                system_prompt += f"\n\n# Profile Building Mode\n{skill_text}"
            except OSError:
                pass
            _save_profile_session_state(self.project_root, channel_id)
        else:
            _update_profile_session_timestamp(self.project_root, channel_id)

        options_kwargs: dict[str, Any] = {
            "cwd": str(self.project_root),
            "system_prompt": system_prompt,
            "allowed_tools": ["Read", "Glob", "Grep"],
            "permission_mode": "dontAsk",
            "max_turns": self.max_turns,
        }
        if existing:
            options_kwargs["resume"] = existing.agent_session_id
            print(f"[{datetime.now()}] Resuming session {existing.session_id}")
        else:
            print(f"[{datetime.now()}] New session for {platform_str}:{channel_id}:")

        options = ClaudeAgentOptions(**options_kwargs)

        response_text = ""
        session_id_from_sdk: str | None = None
        cost_usd: float = 0.0

        try:
            async for sdk_msg in query(prompt=message.text, options=options):
                if isinstance(sdk_msg, AssistantMessage):
                    response_text = ""
                    for block in sdk_msg.content:
                        if isinstance(block, TextBlock):
                            response_text += block.text
                elif isinstance(sdk_msg, ResultMessage):
                    session_id_from_sdk = sdk_msg.session_id
                    cost_usd = sdk_msg.total_cost_usd or 0.0
                    cost_str = f"${cost_usd:.4f}"
                    print(
                        f"[{datetime.now()}] Agent done: "
                        f"session={session_id_from_sdk}, cost={cost_str}"
                    )
        except Exception as e:
            print(f"[{datetime.now()}] Agent error: {e}")
            yield OutgoingMessage(
                text=f"Sorry, I hit an error: {e}",
                channel=message.channel,
                thread=message.thread,
            )
            return

        if response_text.strip():
            yield OutgoingMessage(
                text=response_text.strip(),
                channel=message.channel,
                thread=message.thread,
            )
            # Write conversation turn to daily log (SessionEnd hook doesn't fire in headless mode)
            user_label = message.user.display_name or message.user.platform_id
            append_to_daily_log(
                f"**[WhatsApp]** {user_label}: {message.text}\n"
                f"**[Brain]** {response_text.strip()}"
            )

        # Persist session
        if session_id_from_sdk:
            now = datetime.now()
            if existing:
                existing.agent_session_id = session_id_from_sdk
                existing.message_count += 1
                existing.total_cost_usd += cost_usd
                existing.updated_at = now
                self.session_store.update(existing)
            else:
                self.session_store.create(
                    Session(
                        session_id=f"{platform_str}:{channel_id}:{thread_id}",
                        agent_session_id=session_id_from_sdk,
                        platform=platform_str,
                        channel_id=channel_id,
                        thread_id=thread_id,
                        user_id=message.user.platform_id,
                        created_at=now,
                        updated_at=now,
                        message_count=1,
                        total_cost_usd=cost_usd,
                    )
                )
