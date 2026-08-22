"""Conversation engine: routes WhatsApp messages through sdk_compat with session persistence."""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any


def _load_vault_context(project_root: Path) -> str:
    """Pre-load core vault files for every WhatsApp message.

    Gives the LLM basic memory of who Shaun is without needing Read tool calls,
    which fail on VPS due to bwrap sandboxing restrictions.
    """
    lines = ["# Vault Memory (Pre-Loaded — do not re-read these files via Read tool)"]
    for rel in ("Memory/MEMORY.md", "Memory/USER.md"):
        fpath = project_root / rel
        try:
            content = fpath.read_text(encoding="utf-8")
            lines.append(f"\n## {rel}\n{content}")
        except OSError:
            pass
    return "\n".join(lines)


def _load_context_bridge() -> str:
    """Pre-load a temporary context file for WhatsApp chat only, kept outside this repo.

    Lets Shaun hand the bot short-lived context for something outside the vault
    (e.g. a side project kept in its own repo) without that content ever touching
    this repo's working tree, git history, or vault-sync — deliberately stored
    under the home directory rather than under project_root, so it's never even
    adjacent to a gitignore rule. Drop a file at
    ~/second-brain-bridge/context-bridge.md and delete it when the conversation
    is done.
    """
    fpath = Path.home() / "second-brain-bridge" / "context-bridge.md"
    try:
        content = fpath.read_text(encoding="utf-8")
    except OSError:
        return ""
    if not content.strip():
        return ""
    return (
        "# Temporary Context Bridge (private, session-only — never persist this "
        "content into Memory/ or any tracked file; it lives only in this chat and "
        "today's daily log)\n" + content
    )


def _load_assistant_commands(project_root: Path) -> str:
    """Pre-load Memory/ASSISTANT.md into system prompt.

    Loaded in Python before the LLM call so Write routing works without
    a Read tool call (Read fails on VPS due to bwrap sandboxing).
    """
    fpath = project_root / "Memory" / "ASSISTANT.md"
    try:
        return fpath.read_text(encoding="utf-8")
    except OSError:
        return ""


def _load_profile_context(project_root: Path) -> str:
    """Pre-load profile files + last 3 daily logs into a string for system prompt injection.

    Runs in Python before the LLM call so the LLM never needs to use Read for this —
    which fails on VPS due to bwrap sandboxing restrictions.
    """
    import datetime as _dt

    lines = [
        "# Profile Context (Pre-Loaded — do not re-read these files via Read tool)",
        "The 7 profile files and last 3 daily logs are already below.",
        "Use this content to determine which questions have been asked and answered.",
        "A profile topic is 'covered' if its file has a dated ## YYYY-MM-DD Update section with real content.",
    ]

    for fname in ("values.md", "goals.md", "history.md", "personality.md", "health.md", "relationships.md", "finances.md"):
        fpath = project_root / "Memory" / "Profile" / fname
        try:
            content = fpath.read_text(encoding="utf-8")
        except OSError:
            content = "_(not yet populated)_"
        lines.append(f"\n## Memory/Profile/{fname}\n{content}")

    lines.append("\n# Recent Daily Logs")
    try:
        from config import DAILY_DIR, now_local
        today = now_local().date()
        for i in range(3):
            day = today - _dt.timedelta(days=i)
            log_path = DAILY_DIR / f"{day.isoformat()}.md"
            try:
                content = log_path.read_text(encoding="utf-8")
                lines.append(f"\n## Daily log {day.isoformat()}\n{content}")
            except OSError:
                pass
    except Exception:
        pass

    return "\n".join(lines)


def _is_new_sydney_day(session_created_at: datetime) -> bool:
    """True if session_created_at falls on an earlier Sydney calendar day than now.

    Old rows written before this check existed may be naive (VPS system clock,
    effectively UTC) - treat those as stale too rather than risk an aware/naive
    comparison error, since a broken pre-existing session should reset anyway.
    """
    from config import now_local

    now = now_local()
    if session_created_at.tzinfo is None:
        return True
    return session_created_at.astimezone(now.tzinfo).date() != now.date()


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

try:
    from codex_sdk_compat import reset_session  # noqa: E402
except ImportError:
    def reset_session(key: str) -> bool:  # type: ignore[misc]
        return False


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
        # WhatsApp has no threads â€” channel_id is the session key
        thread_id = ""
        platform_str = message.platform.value
        channel_id = message.channel.platform_id

        existing = self.session_store.get(platform_str, channel_id, thread_id)

        # force_new_thread: start a fresh Codex agent thread this turn but keep
        # `existing` (the DB row, keyed on platform:channel:thread) so the row
        # gets updated with the new thread id afterwards instead of a duplicate
        # INSERT on the same (unique) session_id.
        force_new_thread = False

        # Daily session reset: a WhatsApp thread resumed across many messages
        # eventually grows past Codex's auto-compaction threshold, which is
        # currently broken upstream (openai/codex#38513 - remote compact 404s).
        # Starting a fresh agent thread each Sydney calendar day keeps sessions
        # short enough that compaction rarely triggers, independent of that bug.
        if existing is not None and _is_new_sydney_day(existing.created_at):
            reset_session(existing.agent_session_id)
            force_new_thread = True

        # Injection detection on incoming message (log only â€” never block Shaun)
        injection_flags = check_injection_patterns(message.text)
        if injection_flags:
            names = ", ".join(f[0] for f in injection_flags)
            print(f"[{datetime.now()}] [SECURITY] WhatsApp injection patterns detected: {names}")

        # Conversation thread reset
        _reset_phrases = ["new conversation thread", "start new conversation"]
        if any(phrase in message.text.lower() for phrase in _reset_phrases):
            if existing and not force_new_thread:
                reset_session(existing.agent_session_id)
            yield OutgoingMessage(
                text="Conversation thread reset. Starting fresh â€” your vault memory is intact.",
                channel=message.channel,
                thread=message.thread,
            )
            return

        # Ask Me Questions profile-building mode detection
        _AQM_PHRASES = ["ask me questions", "ask me a question", "coaching session", "profile building", "build my profile"]
        _is_profile_mode = any(phrase in message.text.lower() for phrase in _AQM_PHRASES)

        # Check for 10-min timeout on active profile session (BEFORE LLM call)
        if not _is_profile_mode and _check_and_clear_profile_timeout(self.project_root, channel_id):
            if existing and not force_new_thread:
                reset_session(existing.agent_session_id)
            force_new_thread = True
            # Silent reset — no WhatsApp notification to avoid cluttering CarPlay unread queue

        # Build system prompt from SOUL.md + WhatsApp rules
        try:
            soul_text = (self.project_root / "Memory" / "SOUL.md").read_text(encoding="utf-8")
        except Exception:
            soul_text = "You are Shaun's Second Brain assistant."

        system_prompt = (
            soul_text
            + "\n\n# WhatsApp Chat Bot Rules\n"
            "You are responding via WhatsApp (possibly via CarPlay / Siri). "
            "Be concise and use plain text only â€” no markdown headers, no bullet formatting "
            "that sounds bad read aloud.\n"
            "Give a single, complete answer. Do not split across multiple turns.\n"
            "Keep answers short enough to read on a phone screen.\n"
            f"\n\n{TRUST_BOUNDARY_INSTRUCTION}"
            f"\n\n{_load_vault_context(self.project_root)}"
        )

        assistant_cmds = _load_assistant_commands(self.project_root)
        if assistant_cmds:
            system_prompt += f"\n\n{assistant_cmds}"

        bridge_context = _load_context_bridge()
        if bridge_context:
            system_prompt += f"\n\n{bridge_context}"

        if _is_profile_mode:
            if existing and not force_new_thread:
                reset_session(existing.agent_session_id)
            force_new_thread = True
            skill_path = self.project_root / ".claude" / "skills" / "ask-me-questions" / "SKILL.md"
            try:
                skill_text = skill_path.read_text(encoding="utf-8")
                system_prompt += f"\n\n# Profile Building Mode\n{skill_text}"
            except OSError:
                pass
            system_prompt += f"\n\n{_load_profile_context(self.project_root)}"
            _save_profile_session_state(self.project_root, channel_id)
        else:
            _update_profile_session_timestamp(self.project_root, channel_id)

        options_kwargs: dict[str, Any] = {
            "cwd": str(self.project_root),
            "system_prompt": system_prompt,
            "allowed_tools": ["Read", "Glob", "Grep", "Write", "WebSearch"],
            "permission_mode": "dontAsk",
            "max_turns": self.max_turns,
        }
        if existing and not force_new_thread:
            options_kwargs["resume"] = existing.agent_session_id
            print(f"[{datetime.now()}] Resuming session {existing.session_id}")
        else:
            print(f"[{datetime.now()}] New session for {platform_str}:{channel_id}:")

        options = ClaudeAgentOptions(**options_kwargs)

        response_text = ""
        session_id_from_sdk: str | None = None
        cost_usd: float = 0.0

        async def _run(opts: ClaudeAgentOptions) -> None:
            nonlocal response_text, session_id_from_sdk, cost_usd
            async for sdk_msg in query(prompt=message.text, options=opts):
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

        try:
            await _run(options)
        except Exception as e:
            # Codex's remote auto-compaction is currently 404ing upstream
            # (openai/codex#38513) once a resumed thread's context grows large
            # enough to trigger it. That leaves the saved thread id permanently
            # broken - every future message would resume the same dead thread
            # and hit the same error forever. Reset it and, for this specific
            # failure, retry once on a fresh thread so Shaun doesn't see the
            # hiccup on WhatsApp at all.
            is_compact_failure = "compact" in str(e).lower()
            if existing:
                reset_session(existing.agent_session_id)
            if is_compact_failure and existing:
                print(f"[{datetime.now()}] Compact error, retrying on fresh session: {e}")
                options_kwargs.pop("resume", None)
                force_new_thread = True
                try:
                    await _run(ClaudeAgentOptions(**options_kwargs))
                except Exception as retry_e:
                    e = retry_e
                else:
                    e = None
            if e is not None:
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
            from config import now_local
            now = now_local()
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
