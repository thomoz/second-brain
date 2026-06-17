# Feature: Phase 7 — WhatsApp Chat Bot

The following plan should be complete, but validate codebase patterns and imports before
implementing each task. Pay special attention to `sys.path` injection patterns and how
existing scripts export symbols — import from the right files.

## Feature Description

A persistent conversational bot that lets Shaun query his Second Brain via WhatsApp,
including hands-free via CarPlay (Siri sends WhatsApp → bot replies → Siri reads aloud).
The bot polls GREEN-API for incoming messages (no public URL, no webhook server), routes
them through a conversation engine backed by `sdk_compat.query()`, persists sessions in
SQLite for conversational continuity, and replies via GREEN-API `sendMessage`.

## User Story

As Shaun (a multi-business founder who's often driving or hosting shows),
I want to query my Second Brain by WhatsApp message — including by voice via CarPlay —
So that I can get instant answers about my inbox, calendar, drafts, and business context
without needing a laptop or Claude Code open.

## Problem Statement

After Phase 6, the Second Brain can proactively push information to Shaun (heartbeat +
toast notifications). Phase 7 adds the pull side: Shaun can ask a question at any time
from his phone or car and get a contextual answer sourced from the Memory vault.

## Solution Statement

A polling-based WhatsApp bot (`asyncio` + GREEN-API REST) built in `.claude/chat/` that
mirrors Cole's multi-platform chat architecture (models / session / engine / router /
adapters) but adapted for WhatsApp instead of Slack, with sdk_compat instead of the
native claude_agent_sdk, and read-only Memory access instead of full tool access.

## Feature Metadata

**Feature Type**: New Capability  
**Estimated Complexity**: Medium  
**Primary Systems Affected**: New `.claude/chat/` subsystem; minor update to `heartbeat.py` and `config.py`  
**Dependencies**: All from Phase 6 (already installed) — `requests`, `sdk_compat`, `sanitize`, `shared`, `integrations/whatsapp.py`

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `.claude/scripts/config.py` (lines 1–172) — All path/env constants. New chat constants go here. Note `PROJECT_ROOT`, `DATA_DIR`, `STATE_DIR`, `WHATSAPP_*` vars already defined.
- `.claude/scripts/sdk_compat.py` (full) — Import surface: `query`, `ClaudeAgentOptions`, `AssistantMessage`, `TextBlock`, `ResultMessage`. Pattern: `from sdk_compat import ...`.
- `.claude/scripts/integrations/whatsapp.py` (full) — `get_greenapi_base()`, `send_message()`, `WhatsAppMessage`. The adapter imports `send_message` and `get_greenapi_base` from here. Do NOT re-implement these.
- `.claude/scripts/notifications.py` (full) — `send_whatsapp_notification()` (outbound only, Phase 6). Not used by bot; heartbeat still uses it.
- `.claude/scripts/sanitize.py` — `TRUST_BOUNDARY_INSTRUCTION`, `wrap_external_data`. Engine imports these for system prompt.
- `.claude/scripts/shared.py` — `append_to_daily_log`. Engine may use for error logging.
- `.claude/scripts/heartbeat.py` (lines 165–200, `build_snapshot`) — Confirm WhatsApp polling is NOT currently called. Add lock-file guard near any future WhatsApp gather call, and defensively in the preamble.
- `.claude/scripts/pyproject.toml` — Dependency list; `requests` already present, no new deps needed.
- `.claude/scripts/tests/test_whatsapp.py` — Test pattern: monkeypatch `config.*` attrs, mock `requests`. Mirror this in new test files.
- `.claude/scripts/.env` — Add three new variables: `CHAT_MAX_TURNS`, `CHAT_MAX_BUDGET_USD`, `WHATSAPP_POLL_INTERVAL`.
- `.agent/plans/phase-7-whatsapp-bot-handoff.md` — Architecture decisions, security filter rule, lock-file design, config constants, Task Scheduler command. Read in full before implementing.

### Cole's Reference Files — READ THESE BEFORE IMPLEMENTING

All at `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\chat\`:

- `models.py` — Platform enum, User, Channel, Thread, IncomingMessage, OutgoingMessage dataclasses. Adapt: add `Platform.WHATSAPP`, keep `Platform.CLI`, drop Slack/Discord/Telegram/Web.
- `session.py` — `SQLiteSessionStore`, `Session`, `get_session_store()`. Adapt: drop `HeartbeatThread`, drop `PostgresSessionStore` (psycopg dep already present but unneeded for Phase 7). Keep SQLite store verbatim.
- `engine.py` — `ConversationEngine.handle_message()`. Adapt: (1) replace `from claude_agent_sdk import` with `from sdk_compat import`, (2) `allowed_tools=["Read", "Glob", "Grep"]`, (3) `system_prompt` as a string (not dict preset), (4) remove Slack attachment / image path / validate_bash_command logic.
- `router.py` — `ChatRouter`. Use nearly verbatim; `send_files` call already guarded by `hasattr`, so it's a no-op for our adapter.
- `adapters/slack.py` — Reference for adapter contract only. Replace entirely with WhatsApp polling adapter.
- `main.py` — Entry point pattern. Adapt: remove Slack tokens, add WhatsApp env-var validation, add lock-file lifecycle.

### New Files to Create

```
.claude/chat/
├── __init__.py
├── models.py
├── session.py
├── engine.py
├── router.py
├── main.py
└── adapters/
    ├── __init__.py
    └── whatsapp.py

.claude/scripts/tests/
├── test_chat_session.py
├── test_whatsapp_adapter.py
└── test_chat_engine.py
```

### Existing Files to Update

- `.claude/scripts/config.py` — Add Phase 7 chat constants block
- `.claude/scripts/.env` — Add `CHAT_MAX_TURNS`, `CHAT_MAX_BUDGET_USD`, `WHATSAPP_POLL_INTERVAL`
- `.claude/scripts/heartbeat.py` — Add WhatsApp bot lock-file guard

### Patterns to Follow

**sys.path injection** (all chat files need both chat dir and scripts dir on path):
```python
# In adapters/whatsapp.py:
_CHAT_DIR = Path(__file__).resolve().parent.parent   # .claude/chat/
_SCRIPTS_DIR = _CHAT_DIR.parent / "scripts"          # .claude/scripts/
sys.path.insert(0, str(_CHAT_DIR))
sys.path.insert(0, str(_SCRIPTS_DIR))

# In engine.py, router.py, session.py, models.py:
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(Path(__file__).resolve().parent))  # add chat/ itself
sys.path.insert(0, str(_SCRIPTS_DIR))
```

**Flat imports** (no package-relative imports — all files use flat names):
```python
from models import IncomingMessage, OutgoingMessage, Platform, Channel, User, Thread
from session import SQLiteSessionStore, Session, get_session_store
from engine import ConversationEngine
from router import ChatRouter
```

**sdk_compat import** (never import from claude_agent_sdk directly):
```python
from sdk_compat import query, ClaudeAgentOptions, AssistantMessage, TextBlock, ResultMessage
```

**Env var pattern** (match config.py style):
```python
CHAT_DB_PATH = DATA_DIR / "chat.db"
CHAT_MAX_TURNS = int(_os.getenv("CHAT_MAX_TURNS", "20"))
CHAT_MAX_BUDGET_USD = float(_os.getenv("CHAT_MAX_BUDGET_USD", "0.50"))
WHATSAPP_POLL_INTERVAL = float(_os.getenv("WHATSAPP_POLL_INTERVAL", "1.0"))
```

**Test monkeypatch pattern** (from `test_whatsapp.py`):
```python
def test_something(monkeypatch):
    import config
    monkeypatch.setattr(config, "WHATSAPP_INSTANCE_ID", "test123")
```

---

## IMPLEMENTATION PLAN

### Phase 1: Config & Foundation

Add constants, update env, create package stubs.

### Phase 2: Core Chat Module

Port Cole's models, session store, engine, and router with WhatsApp adaptations.

### Phase 3: WhatsApp Adapter

The new code: polling adapter that owns the GREEN-API receive/delete loop, security filter, and send.

### Phase 4: Entry Point & Heartbeat Guard

`main.py` with lock-file lifecycle; `heartbeat.py` guard.

### Phase 5: Tests & Scheduler

Unit tests for session, adapter, engine. Task Scheduler registration command.

---

## STEP-BY-STEP TASKS

---

### Task 1 — ADD Phase 7 constants to `config.py`

- **LOCATION**: `.claude/scripts/config.py` — append a new `# Phase 7: Chat Bot` block after the Phase 6 block (after `is_within_active_hours`)
- **ADD**:
```python
# ---------------------------------------------------------------------------
# Phase 7: WhatsApp Chat Bot
# ---------------------------------------------------------------------------

CHAT_DB_PATH = DATA_DIR / "chat.db"
CHAT_MAX_TURNS = int(_os.getenv("CHAT_MAX_TURNS", "20"))
CHAT_MAX_BUDGET_USD = float(_os.getenv("CHAT_MAX_BUDGET_USD", "0.50"))
WHATSAPP_POLL_INTERVAL = float(_os.getenv("WHATSAPP_POLL_INTERVAL", "1.0"))

# Lock file: bot writes this on start, heartbeat checks it before WA polling
BOT_LOCK_FILE = STATE_DIR / "whatsapp-bot.lock"
```
- **GOTCHA**: `DATA_DIR`, `STATE_DIR`, `_os` are already defined earlier in the file — do not redefine.
- **VALIDATE**: `cd .claude\scripts && uv run python -c "from config import CHAT_DB_PATH, BOT_LOCK_FILE; print(CHAT_DB_PATH, BOT_LOCK_FILE)"`

---

### Task 2 — UPDATE `.env` with chat variables

- **LOCATION**: `.claude/scripts/.env`
- **IMPORTANT**: The WhatsApp credentials are **already live in this file** — do NOT overwrite or regenerate them:
  ```
  WHATSAPP_INSTANCE_ID=7107649252        ← already set, working
  WHATSAPP_API_TOKEN=e52f276b...         ← already set, working
  WHATSAPP_MY_NUMBER=61410868612         ← already set, working
  ```
- **ADD ONLY** these three new lines at the end:
```
# Phase 7: Chat Bot
CHAT_MAX_TURNS=20
CHAT_MAX_BUDGET_USD=0.50
WHATSAPP_POLL_INTERVAL=1.0
```
- **VALIDATE**: `cd .claude\scripts && uv run python -c "from config import CHAT_MAX_TURNS, WHATSAPP_POLL_INTERVAL, WHATSAPP_INSTANCE_ID; print(CHAT_MAX_TURNS, WHATSAPP_POLL_INTERVAL, WHATSAPP_INSTANCE_ID)"`

---

### Task 3 — CREATE `.claude/chat/__init__.py`

- **IMPLEMENT**: Empty file — marks `chat/` as a Python package.
- **VALIDATE**: `Test-Path .claude\chat\__init__.py`

---

### Task 4 — CREATE `.claude/chat/models.py`

- **MIRROR**: Cole's `models.py` with these adaptations:
  - `Platform` enum: keep only `WHATSAPP = "whatsapp"` and `CLI = "cli"`; drop SLACK/DISCORD/TELEGRAM/WEB
  - All dataclasses (`User`, `Channel`, `Thread`, `Attachment`, `IncomingMessage`, `OutgoingMessage`) are verbatim
- **IMPLEMENT**:
```python
"""Platform-agnostic message models for the Second Brain chat interface."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

class Platform(Enum):
    WHATSAPP = "whatsapp"
    CLI = "cli"

# ... User, Channel, Thread, Attachment, IncomingMessage, OutgoingMessage verbatim from Cole
```
- **VALIDATE**: `cd .claude\scripts && uv run python -c "import sys; sys.path.insert(0,'../chat'); from models import Platform, IncomingMessage; print(Platform.WHATSAPP)"`

---

### Task 5 — CREATE `.claude/chat/session.py`

- **MIRROR**: Cole's `session.py` with these adaptations:
  - Keep `Session` dataclass verbatim
  - Keep `SQLiteSessionStore` verbatim (all CRUD methods)
  - **DROP** `HeartbeatThread` dataclass (no heartbeat-thread concept in WhatsApp)
  - **DROP** `save_heartbeat_thread()` and `get_heartbeat_thread()` methods
  - **DROP** `PostgresSessionStore` class entirely
  - `get_session_store()` factory: SQLite only (no DATABASE_URL branch needed, simplify)
- **IMPORTS** needed at top of file:
```python
import sys
from pathlib import Path
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
```
- **`get_session_store` simplified**:
```python
def get_session_store(chat_db_path: Path | None = None) -> SQLiteSessionStore:
    if chat_db_path is None:
        from config import CHAT_DB_PATH
        chat_db_path = CHAT_DB_PATH
    return SQLiteSessionStore(chat_db_path)
```
- **VALIDATE**: `cd .claude\scripts && uv run python -c "import sys; sys.path.insert(0,'../chat'); from session import SQLiteSessionStore, get_session_store; s=SQLiteSessionStore(':memory:'); print('ok')"`

---

### Task 6 — CREATE `.claude/chat/engine.py`

- **MIRROR**: Cole's `engine.py` with significant simplification for WhatsApp:
- **REMOVE**: `_build_attachment_context`, `_extract_image_paths`, `_IMAGE_EXTENSIONS`, `_IMAGE_PATH_RE`, `_get_heartbeat_context`, all attachment/image logic
- **REMOVE**: `validate_bash_command` import and HookMatcher from options
- **CHANGE** imports:
  ```python
  # Replace: from claude_agent_sdk import ...
  # With:
  from sdk_compat import query, ClaudeAgentOptions, AssistantMessage, TextBlock, ResultMessage
  ```
- **CHANGE** `handle_message` options to WhatsApp-appropriate:
  ```python
  soul_text = (self.project_root / "Memory" / "SOUL.md").read_text(encoding="utf-8")
  system_prompt = (
      soul_text
      + "\n\n# WhatsApp Chat Bot Rules\n"
      "You are responding via WhatsApp (possibly via CarPlay / Siri). "
      "Be concise and use plain text only — no markdown headers, no bullet formatting that sounds bad read aloud.\n"
      "Give a single, complete answer. Do not split across multiple turns.\n"
      "Keep answers short enough to read on a phone screen.\n"
      f"\n\n{TRUST_BOUNDARY_INSTRUCTION}"
  )

  options_kwargs = {
      "cwd": str(self.project_root),
      "system_prompt": system_prompt,
      "allowed_tools": ["Read", "Glob", "Grep"],   # Read-only Memory access
      "permission_mode": "dontAsk",
      "max_turns": self.max_turns,
  }
  if existing:
      options_kwargs["resume"] = existing.agent_session_id
  options = ClaudeAgentOptions(**options_kwargs)
  ```
- **SIMPLIFY** response collection: collect only final `AssistantMessage` text, yield ONE `OutgoingMessage` at the end (no streaming partial yields):
  ```python
  response_text = ""
  session_id_from_sdk: str | None = None
  cost_usd: float = 0.0

  async for sdk_msg in query(prompt=message.text, options=options):
      if isinstance(sdk_msg, AssistantMessage):
          response_text = ""
          for block in sdk_msg.content:
              if isinstance(block, TextBlock):
                  response_text += block.text
      elif isinstance(sdk_msg, ResultMessage):
          session_id_from_sdk = sdk_msg.session_id
          cost_usd = sdk_msg.total_cost_usd or 0.0

  if response_text.strip():
      yield OutgoingMessage(text=response_text.strip(), channel=message.channel, thread=message.thread)
  ```
- **KEEP** session persist logic (create or update) verbatim from Cole
- **SESSION KEY** for WhatsApp: `thread_id = ""` (WhatsApp has no threads), `channel_id = message.channel.platform_id` (the chat_id e.g. `61410868612@c.us`)
- **IMPORTS** at top:
  ```python
  import sys
  from pathlib import Path
  _CHAT_DIR = Path(__file__).resolve().parent
  _SCRIPTS_DIR = _CHAT_DIR.parent / "scripts"
  sys.path.insert(0, str(_CHAT_DIR))
  sys.path.insert(0, str(_SCRIPTS_DIR))
  from models import IncomingMessage, OutgoingMessage
  from session import SQLiteSessionStore, Session
  from sanitize import TRUST_BOUNDARY_INSTRUCTION
  from sdk_compat import query, ClaudeAgentOptions, AssistantMessage, TextBlock, ResultMessage
  ```
- **VALIDATE**: `cd .claude\scripts && uv run python -c "import sys; sys.path.insert(0,'../chat'); sys.path.insert(0,'.'); from engine import ConversationEngine; print('ok')"`

---

### Task 7 — CREATE `.claude/chat/router.py`

- **MIRROR**: Cole's `router.py` nearly verbatim
- **CHANGE**: Remove "Thinking..." placeholder send. The WhatsApp adapter returns `""` from `send()` for the placeholder anyway (see Task 9), but for clarity simplify `_handle` to skip it:
  ```python
  async def _handle(self, adapter: Any, incoming: Any) -> None:
      print(f"[{datetime.now()}] Message from {incoming.user.platform_id}: {incoming.text[:80]}")
      final_text = ""
      try:
          async for outgoing in self.engine.handle_message(incoming):
              final_text = outgoing.text
      except Exception as e:
          print(f"[{datetime.now()}] Engine error: {e}")
          final_text = f"Sorry, something went wrong: {e}"

      if not final_text.strip():
          final_text = "I processed your request but had nothing to report."
      try:
          await adapter.send(OutgoingMessage(text=final_text, channel=incoming.channel, thread=incoming.thread))
      except Exception as e:
          print(f"[{datetime.now()}] Failed to send response: {e}")
  ```
- **KEEP**: `run()`, `register()`, `_listen()`, `shutdown()` verbatim
- **REMOVE**: `send_files` block (WhatsApp has no file upload via GREEN-API)
- **IMPORTS**:
  ```python
  import sys
  from pathlib import Path
  _SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
  sys.path.insert(0, str(Path(__file__).resolve().parent))
  sys.path.insert(0, str(_SCRIPTS_DIR))
  ```
- **VALIDATE**: `cd .claude\scripts && uv run python -c "import sys; sys.path.insert(0,'../chat'); sys.path.insert(0,'.'); from router import ChatRouter; print('ok')"`

---

### Task 8 — CREATE `.claude/chat/adapters/__init__.py`

- **IMPLEMENT**: Empty file.
- **VALIDATE**: `Test-Path .claude\chat\adapters\__init__.py`

---

### Task 9 — CREATE `.claude/chat/adapters/whatsapp.py`

This is the key new component. Poll-based, no webhook server, no public URL.

- **IMPORTS**:
```python
from __future__ import annotations
import asyncio
import sys
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any
import requests

_CHAT_DIR = Path(__file__).resolve().parent.parent   # .claude/chat/
_SCRIPTS_DIR = _CHAT_DIR.parent / "scripts"          # .claude/scripts/
sys.path.insert(0, str(_CHAT_DIR))
sys.path.insert(0, str(_SCRIPTS_DIR))

from models import Channel, IncomingMessage, OutgoingMessage, Platform, Thread, User
```

- **CLASS**:
```python
class WhatsAppPollingAdapter:
    """GREEN-API polling adapter — outbound connections only, no public URL."""

    def __init__(
        self,
        instance_id: str,
        api_token: str,
        my_number: str,
        poll_interval: float = 1.0,
    ) -> None:
        self.instance_id = instance_id
        self.api_token = api_token
        self.my_number = my_number          # e.g. "61410868612"
        self.poll_interval = poll_interval

    @property
    def platform(self) -> Platform:
        return Platform.WHATSAPP

    async def connect(self) -> None:
        """No-op — polling requires no persistent connection."""
        print(f"[{datetime.now()}] WhatsApp adapter ready (polling instance {self.instance_id})")

    async def disconnect(self) -> None:
        """No-op."""
        print(f"[{datetime.now()}] WhatsApp adapter stopped")

    async def listen(self) -> AsyncIterator[IncomingMessage]:
        """Yield one IncomingMessage per poll cycle that has a valid message."""
        loop = asyncio.get_running_loop()
        while True:
            msg = await loop.run_in_executor(None, self._poll_once)
            if msg is not None:
                yield msg
            else:
                await asyncio.sleep(self.poll_interval)

    def _poll_once(self) -> IncomingMessage | None:
        """
        Single poll: GET one notification, filter, parse, DELETE (acknowledge).
        Returns IncomingMessage or None if queue empty / not processable.
        """
        from integrations.whatsapp import get_greenapi_base

        base = get_greenapi_base(self.instance_id)
        try:
            resp = requests.get(f"{base}/receiveNotification/{self.api_token}", timeout=5)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data is None:
                return None  # Queue empty

            receipt_id = data.get("receiptId")
            body = data.get("body", {})

            def _ack() -> None:
                if receipt_id:
                    try:
                        requests.delete(
                            f"{base}/deleteNotification/{self.api_token}/{receipt_id}",
                            timeout=5,
                        )
                    except Exception:
                        pass

            # Only handle inbound text messages
            if body.get("typeWebhook") != "incomingMessageReceived":
                _ack()
                return None

            sender_data = body.get("senderData", {})
            sender = sender_data.get("sender", "")

            # Security filter: only respond to Shaun's own number
            if self.my_number not in sender:
                _ack()
                return None

            msg_data = body.get("messageData", {})
            if msg_data.get("typeMessage") != "textMessage":
                _ack()  # Acknowledge image/audio/etc. without processing
                return None

            text = msg_data.get("textMessageData", {}).get("textMessage", "").strip()
            if not text:
                _ack()
                return None

            chat_id = sender_data.get("chatId", sender)
            _ack()

            return IncomingMessage(
                text=text,
                user=User(platform=Platform.WHATSAPP, platform_id=sender),
                channel=Channel(platform=Platform.WHATSAPP, platform_id=chat_id, is_dm=True),
                platform=Platform.WHATSAPP,
                thread=None,
                platform_message_id=str(receipt_id),
                raw_event=body,
            )

        except Exception as e:
            print(f"[{datetime.now()}] WhatsApp poll error: {e}")
            return None

    async def send(self, message: OutgoingMessage) -> str:
        """Send a WhatsApp message. Returns '' (no editable message ID in GREEN-API)."""
        from integrations.whatsapp import send_message as _send_wa
        chat_id = message.channel.platform_id
        ok = _send_wa(chat_id, message.text)
        if not ok:
            print(f"[{datetime.now()}] WhatsApp send failed for {chat_id}")
        return ""  # No message ID — router always sends fresh messages

    async def update(self, message: OutgoingMessage) -> None:
        """No-op — GREEN-API does not support message editing."""
        pass
```

- **GOTCHA**: `get_greenapi_base` is in `integrations/whatsapp.py`, not `config.py`. Import from there.
- **GOTCHA**: `my_number` in `.env` is `61410868612` (no `@c.us`). The `sender` field from GREEN-API is `61410868612@c.us`. The `in` check handles this: `"61410868612" in "61410868612@c.us"` → True.
- **GOTCHA**: `asyncio.get_running_loop()` not `asyncio.get_event_loop()` — required for Python 3.10+.
- **VALIDATE**: `cd .claude\scripts && uv run python -c "import sys; sys.path.insert(0,'../chat'); sys.path.insert(0,'.'); from adapters.whatsapp import WhatsAppPollingAdapter; a=WhatsAppPollingAdapter('x','y','61410868612'); print(a.platform)"`

---

### Task 10 — CREATE `.claude/chat/main.py`

- **IMPLEMENT**: Entry point with lock-file lifecycle, `--test` flag, startup banner.

```python
"""
WhatsApp chat bot entry point for Second Brain.

Usage:
    cd .claude/scripts && uv run python ../chat/main.py
    cd .claude/scripts && uv run python ../chat/main.py --test
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# AGENT_INVOKED_BY must be set before any imports (soul-protect hook)
os.environ["AGENT_INVOKED_BY"] = "chat"

_CHAT_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _CHAT_DIR.parent / "scripts"
sys.path.insert(0, str(_CHAT_DIR))
sys.path.insert(0, str(_SCRIPTS_DIR))

from config import (          # noqa: E402
    BOT_LOCK_FILE,
    CHAT_DB_PATH,
    CHAT_MAX_BUDGET_USD,
    CHAT_MAX_TURNS,
    PROJECT_ROOT,
    WHATSAPP_API_TOKEN,
    WHATSAPP_INSTANCE_ID,
    WHATSAPP_MY_NUMBER,
    WHATSAPP_POLL_INTERVAL,
)
from engine import ConversationEngine        # noqa: E402
from router import ChatRouter                # noqa: E402
from session import get_session_store        # noqa: E402
from adapters.whatsapp import WhatsAppPollingAdapter  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Second Brain WhatsApp Bot")
    parser.add_argument("--test", action="store_true", help="Validate config and exit")
    args = parser.parse_args()

    # Validate required credentials
    missing = [v for v, n in [
        (WHATSAPP_INSTANCE_ID, "WHATSAPP_INSTANCE_ID"),
        (WHATSAPP_API_TOKEN, "WHATSAPP_API_TOKEN"),
        (WHATSAPP_MY_NUMBER, "WHATSAPP_MY_NUMBER"),
    ] if not v]
    if missing:
        print(f"ERROR: Missing env vars: {', '.join(missing)}")
        print("Check .claude/scripts/.env")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print("Second Brain — WhatsApp Bot")
    print(f"{'=' * 60}")
    print(f"  Instance:      {WHATSAPP_INSTANCE_ID}")
    print(f"  My number:     {WHATSAPP_MY_NUMBER}")
    print(f"  Poll interval: {WHATSAPP_POLL_INTERVAL}s")
    print(f"  Max turns:     {CHAT_MAX_TURNS}")
    print(f"  Max budget:    ${CHAT_MAX_BUDGET_USD:.2f}")
    print(f"  DB:            {CHAT_DB_PATH}")
    print(f"  Lock file:     {BOT_LOCK_FILE}")
    print(f"{'=' * 60}\n")

    if args.test:
        store = get_session_store(CHAT_DB_PATH)
        print(f"  Session store OK ({len(store.list_active())} active sessions)")
        engine = ConversationEngine(store, PROJECT_ROOT, CHAT_MAX_TURNS, CHAT_MAX_BUDGET_USD)
        print("  Engine OK")
        adapter = WhatsAppPollingAdapter(
            WHATSAPP_INSTANCE_ID, WHATSAPP_API_TOKEN, WHATSAPP_MY_NUMBER, WHATSAPP_POLL_INTERVAL
        )
        print(f"  Adapter OK ({adapter.platform.value})")
        router = ChatRouter(engine)
        router.register(adapter)
        print("  Router OK")
        print("\nAll checks passed. Run without --test to start.")
        return

    # Write lock file — heartbeat checks this before WA polling
    BOT_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    BOT_LOCK_FILE.write_text(str(os.getpid()))
    print(f"[{datetime.now()}] Lock file written: {BOT_LOCK_FILE}")

    store = get_session_store(CHAT_DB_PATH)
    engine = ConversationEngine(store, PROJECT_ROOT, CHAT_MAX_TURNS, CHAT_MAX_BUDGET_USD)
    adapter = WhatsAppPollingAdapter(
        WHATSAPP_INSTANCE_ID, WHATSAPP_API_TOKEN, WHATSAPP_MY_NUMBER, WHATSAPP_POLL_INTERVAL
    )
    router = ChatRouter(engine)
    router.register(adapter)

    print(f"[{datetime.now()}] Bot started. Listening for messages from {WHATSAPP_MY_NUMBER}...")

    try:
        asyncio.run(router.run())
    except KeyboardInterrupt:
        print(f"\n[{datetime.now()}] Shutting down...")
        asyncio.run(router.shutdown())
    finally:
        # Always remove lock file on exit
        BOT_LOCK_FILE.unlink(missing_ok=True)
        print(f"[{datetime.now()}] Lock file removed. Goodbye!")


if __name__ == "__main__":
    main()
```

- **GOTCHA**: `os.environ["AGENT_INVOKED_BY"] = "chat"` must be the FIRST line before any imports — the soul-protect hook reads this env var.
- **GOTCHA**: `BOT_LOCK_FILE.unlink(missing_ok=True)` requires Python 3.8+. Already satisfied (`requires-python = ">=3.12"`).
- **VALIDATE**: `cd .claude\scripts && uv run python ../chat/main.py --test`

---

### Task 11 — UPDATE `heartbeat.py` — add lock-file guard

- **LOCATION**: `.claude/scripts/heartbeat.py`
- **FIND** the `build_snapshot()` function or the section where WhatsApp data would be gathered
- **ADD** a guard. If WhatsApp polling IS present in the current heartbeat, add:
  ```python
  # Guard: skip WA polling if the chat bot is running (shared destructive queue)
  from config import BOT_LOCK_FILE
  if BOT_LOCK_FILE.exists():
      print(f"[{now_local()}] WhatsApp bot running — skipping WA polling")
      whatsapp_data = []
  else:
      from integrations.whatsapp import get_unread_messages
      whatsapp_data = get_unread_messages()
  ```
- **IF** WhatsApp polling is NOT in the current heartbeat (check before implementing — read `build_snapshot()` in full), add as a TODO comment near the `_gather_emails()` block:
  ```python
  # TODO Phase 7: WhatsApp inbound polling goes here.
  # Guard required: check BOT_LOCK_FILE exists before calling get_unread_messages()
  # from config import BOT_LOCK_FILE
  # if not BOT_LOCK_FILE.exists(): whatsapp_data = get_unread_messages()
  ```
- **VALIDATE**: Read the function, confirm the guard is present.

---

### Task 12 — VERIFY `pyproject.toml` — no new deps needed

- **CHECK**: `requests` already present (Phase 4). No new dependencies required for Phase 7.
- **VALIDATE**: `cd .claude\scripts && uv run python -c "import requests, asyncio; print('all ok')"`

---

### Task 13 — CREATE `tests/test_chat_session.py`

```python
"""Unit tests for chat/session.py — uses :memory: SQLite."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "chat"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from session import SQLiteSessionStore, Session, get_session_store


@pytest.fixture
def store():
    return SQLiteSessionStore(Path(":memory:"))


def _make_session(session_id="whatsapp:61410868612@c.us:") -> Session:
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
```

- **VALIDATE**: `cd .claude\scripts && uv run pytest tests/test_chat_session.py -v`

---

### Task 14 — CREATE `tests/test_whatsapp_adapter.py`

```python
"""Unit tests for chat/adapters/whatsapp.py — no live API calls."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "chat"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from adapters.whatsapp import WhatsAppPollingAdapter
from models import Platform


INSTANCE = "7107649252"
TOKEN = "testtoken"
MY_NUMBER = "61410868612"

SAMPLE_PAYLOAD = {
    "receiptId": 12345,
    "body": {
        "typeWebhook": "incomingMessageReceived",
        "senderData": {
            "chatId": "61410868612@c.us",
            "sender": "61410868612@c.us",
        },
        "messageData": {
            "typeMessage": "textMessage",
            "textMessageData": {"textMessage": "What's on my calendar?"},
        },
    },
}

OTHER_PAYLOAD = {
    "receiptId": 99,
    "body": {
        "typeWebhook": "incomingMessageReceived",
        "senderData": {"chatId": "61499999999@c.us", "sender": "61499999999@c.us"},
        "messageData": {"typeMessage": "textMessage", "textMessageData": {"textMessage": "hack"}},
    },
}


def make_adapter():
    return WhatsAppPollingAdapter(INSTANCE, TOKEN, MY_NUMBER)


def test_platform():
    assert make_adapter().platform == Platform.WHATSAPP


def test_poll_once_returns_message(requests_mock):
    adapter = make_adapter()
    requests_mock.get(f"https://api.green-api.com/waInstance{INSTANCE}/receiveNotification/{TOKEN}", json=SAMPLE_PAYLOAD)
    requests_mock.delete(f"https://api.green-api.com/waInstance{INSTANCE}/deleteNotification/{TOKEN}/12345")
    msg = adapter._poll_once()
    assert msg is not None
    assert msg.text == "What's on my calendar?"
    assert msg.platform == Platform.WHATSAPP


def test_poll_once_filters_unknown_sender(requests_mock):
    adapter = make_adapter()
    requests_mock.get(f"https://api.green-api.com/waInstance{INSTANCE}/receiveNotification/{TOKEN}", json=OTHER_PAYLOAD)
    requests_mock.delete(f"https://api.green-api.com/waInstance{INSTANCE}/deleteNotification/{TOKEN}/99")
    msg = adapter._poll_once()
    assert msg is None


def test_poll_once_empty_queue(requests_mock):
    adapter = make_adapter()
    requests_mock.get(f"https://api.green-api.com/waInstance{INSTANCE}/receiveNotification/{TOKEN}", json=None)
    msg = adapter._poll_once()
    assert msg is None


def test_poll_once_non_text_message(requests_mock):
    payload = {
        "receiptId": 200,
        "body": {
            "typeWebhook": "incomingMessageReceived",
            "senderData": {"chatId": "61410868612@c.us", "sender": "61410868612@c.us"},
            "messageData": {"typeMessage": "imageMessage"},
        },
    }
    adapter = make_adapter()
    requests_mock.get(f"https://api.green-api.com/waInstance{INSTANCE}/receiveNotification/{TOKEN}", json=payload)
    requests_mock.delete(f"https://api.green-api.com/waInstance{INSTANCE}/deleteNotification/{TOKEN}/200")
    msg = adapter._poll_once()
    assert msg is None
```

- **GOTCHA**: `requests_mock` requires `pytest-requests-mock` or use `unittest.mock.patch`. Add `requests-mock>=1.11` to `pyproject.toml` dev deps if not present.
- **VALIDATE**: `cd .claude\scripts && uv run pytest tests/test_whatsapp_adapter.py -v`

---

### Task 15 — CREATE `tests/test_chat_engine.py`

```python
"""Unit tests for chat/engine.py — mocks sdk_compat.query."""
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "chat"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from models import Channel, IncomingMessage, Platform, User
from session import SQLiteSessionStore
from engine import ConversationEngine


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


@pytest.fixture
def store():
    return SQLiteSessionStore(Path(":memory:"))


@pytest.fixture
def engine(store):
    return ConversationEngine(store, PROJECT_ROOT, max_turns=5, max_budget_usd=0.10)


def _make_incoming(text="hello"):
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
```

- **VALIDATE**: `cd .claude\scripts && uv run pytest tests/test_chat_engine.py -v`

---

### Task 16 — REGISTER Windows Task Scheduler (manual step)

Run this once in an elevated PowerShell after confirming `--test` passes:

```powershell
$project = "O:\AI\Dynamous\Courses\second-brain-workshop"
$action = New-ScheduledTaskAction `
    -Execute "uv" `
    -Argument "run python ..\chat\main.py" `
    -WorkingDirectory "$project\.claude\scripts"

$trigger = New-ScheduledTaskTrigger -AtLogOn

Register-ScheduledTask `
    -TaskName "SecondBrain-WhatsAppBot" `
    -Action $action `
    -Trigger $trigger `
    -RunLevel Highest `
    -Force
```

- **VALIDATE**: `Get-ScheduledTask -TaskName "SecondBrain-WhatsAppBot"`
- **MANUAL TEST**: Send yourself a WhatsApp and confirm the bot replies.

---

## TESTING STRATEGY

### Unit Tests

- `test_chat_session.py` — SQLiteSessionStore CRUD with `:memory:` database
- `test_whatsapp_adapter.py` — `_poll_once()` with mocked `requests` (valid msg, security filter, empty queue, non-text)
- `test_chat_engine.py` — `handle_message()` with mocked `sdk_compat.query` (new session, session resume)

### Integration Tests

- `main.py --test` — validates all components can be instantiated without errors

### Edge Cases to Test

- Security filter: message from unknown number → ignored
- Non-text message (image, audio) → acknowledged + ignored
- Empty GREEN-API queue → `None` returned, 1-second sleep, no error
- GREEN-API error (HTTP 500) → `None` returned, loop continues
- Bot lock-file created on start → exists during run → deleted on exit

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```powershell
cd .claude\scripts
uv run ruff check ../chat/ --select E,F,I,N,W,UP
```

### Level 2: Unit Tests

```powershell
cd .claude\scripts
uv run pytest tests/test_chat_session.py tests/test_whatsapp_adapter.py tests/test_chat_engine.py -v
```

### Level 3: Config Check

```powershell
cd .claude\scripts
uv run python -c "from config import CHAT_DB_PATH, BOT_LOCK_FILE, CHAT_MAX_TURNS, WHATSAPP_POLL_INTERVAL; print('Config OK:', CHAT_DB_PATH)"
```

### Level 4: Dry-run Start

```powershell
cd .claude\scripts
uv run python ../chat/main.py --test
```

### Level 5: Manual End-to-End

1. Start bot: `cd .claude\scripts && uv run python ../chat/main.py`
2. Confirm lock file exists: `Test-Path .claude\data\state\whatsapp-bot.lock`
3. Send a WhatsApp to yourself: "What's on my calendar today?"
4. Confirm reply arrives within ~10 seconds
5. Stop bot (Ctrl+C), confirm lock file deleted: `Test-Path .claude\data\state\whatsapp-bot.lock` → False

---

## ACCEPTANCE CRITERIA

- [ ] `main.py --test` runs without errors
- [ ] All unit tests pass (`test_chat_session`, `test_whatsapp_adapter`, `test_chat_engine`)
- [ ] Ruff linting passes on `.claude/chat/`
- [ ] Lock file created on bot start, deleted on bot stop
- [ ] Heartbeat has lock-file guard (comment or active guard)
- [ ] Bot only responds to messages from `WHATSAPP_MY_NUMBER`
- [ ] Non-text messages (images, audio) are acknowledged and ignored
- [ ] Sessions persisted in `.claude/data/chat.db`
- [ ] Manual WhatsApp message → bot reply in < 15 seconds
- [ ] No changes to Phase 6 files (`integrations/whatsapp.py`, `notifications.py`, `heartbeat.py` logic)
- [ ] Task Scheduler task registered

---

## COMPLETION CHECKLIST

- [ ] Tasks 1–2: config.py + .env updated
- [ ] Tasks 3–9: all chat module files created
- [ ] Task 10: main.py created and `--test` passes
- [ ] Task 11: heartbeat.py guard added
- [ ] Tasks 13–15: all tests written and passing
- [ ] All validation commands executed
- [ ] Manual end-to-end test confirmed
- [ ] Task 16: Task Scheduler registered

---

## NOTES

**Why polling, not webhook**: GREEN-API polling is outbound-only HTTP — equivalent security to Slack Socket Mode. No public URL, no Cloudflare Tunnel, no aiohttp server. Adds ~1s latency, acceptable for a bot with 5–15s LLM response time.

**Number situation (2026-06-12)**: GREEN-API is currently connected to Shaun's personal number (61410868612). This means the bot sends FROM the same number it receives FROM — WhatsApp may not deliver self-messages as normal push notifications. An Aldi prepaid SIM has been ordered. Once it arrives, re-register GREEN-API on the Aldi number, update `.env` with new `WHATSAPP_INSTANCE_ID` and `WHATSAPP_API_TOKEN`, and update the "Second Brain" contact to point to the Aldi number. `WHATSAPP_MY_NUMBER` stays as `61410868612`.

**Read-only bot**: `allowed_tools=["Read", "Glob", "Grep"]` — the bot can read Memory/ but cannot write. Heartbeat + reflection handle all Memory writes. This is intentional and matches SOUL.md Advisor mode.

**CarPlay UX**: Siri sends the WhatsApp to the "Second Brain" contact (Shaun's own number or Aldi number). The bot responds. Siri reads the reply aloud. Keep bot responses short and in plain text — no markdown, no bullet points that sound weird when read aloud.

**Session resume**: `options_kwargs["resume"] = existing.agent_session_id` enables conversational continuity. If the backend (Pi or Claude) doesn't support resume, it gracefully starts a new session. This is safe.

**Confidence score: 8/10** — architecture is clear, Cole's reference is solid, polling is simpler than webhook. Main unknowns: (1) sdk_compat `query()` resume behaviour under current backend, (2) GREEN-API payload shape may vary slightly from reference (verify with `--dry-run` poll), (3) `pytest-requests-mock` may need adding to dev deps.
