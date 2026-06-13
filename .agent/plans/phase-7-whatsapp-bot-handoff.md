# Phase 7 Handoff: WhatsApp Chat Bot

This document captures all design decisions made during Phase 6 planning so they can
be loaded as context when running `/plan-feature` for Phase 7 in a new session.
DO NOT implement from this doc — run `/plan-feature` first to generate the full plan.

---

## Mutual Exclusion: Bot vs Heartbeat WhatsApp Polling

**Decision (2026-06-12):** The GREEN-API notification queue is destructive — whoever calls
`receiveNotification` first consumes the message. The heartbeat and the bot must never
both poll the queue at the same time.

**Implementation rule:**
- The bot writes a **lock file** at `.claude/data/state/whatsapp-bot.lock` when it starts,
  and deletes it on clean shutdown.
- The heartbeat checks for this lock file before its WhatsApp polling step. If the lock
  exists → skip WhatsApp polling entirely, log "bot running — WhatsApp polling skipped".
- The bot's `_poll_once()` is the sole consumer of the queue while it is running.

**Lock file approach** (simple, no IPC needed):
```python
# In chat/main.py — on startup:
BOT_LOCK_FILE = Path(".claude/data/state/whatsapp-bot.lock")
BOT_LOCK_FILE.write_text(str(os.getpid()))
# On shutdown (finally block):
BOT_LOCK_FILE.unlink(missing_ok=True)
```

```python
# In heartbeat.py — before WhatsApp gather:
BOT_LOCK_FILE = DATA_DIR / "state" / "whatsapp-bot.lock"
if BOT_LOCK_FILE.exists():
    print("[heartbeat] WhatsApp bot running — skipping WA polling")
    whatsapp_data = []
else:
    whatsapp_data = get_unread_messages()
```

**Phase 6 code unchanged** — `get_unread_messages()` in `whatsapp.py` stays as-is.
Heartbeat just gains the lock-check guard. Bot writes/deletes its own lock file.

---

## What Phase 7 Builds

A persistent conversational bot that lets Shaun query his Second Brain via WhatsApp,
including from CarPlay (Siri sends WhatsApp → bot replies → Siri reads aloud).

PRD reference: `.agent/plans/second-brain-prd.md` → "Phase 7: Chat Interface (WhatsApp Bot)"

Cole's reference implementation:
- `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\chat\` (full directory)

---

## Key Design Decisions (already made — do not relitigate)

### Security: Polling, not webhook

Cole's Slack integration uses Socket Mode: the bot connects outbound via WebSocket, no
public URL, no attack surface. We follow the same principle for WhatsApp.

**Decision: Use GREEN-API polling mode, not webhook + Cloudflare Tunnel.**

GREEN-API polling:
```python
# Poll notification queue (outbound HTTP, no inbound server needed)
resp = requests.get(f"{BASE}/receiveNotification/{api_token}", timeout=5)
data = resp.json()
if data:
    receipt_id = data["receiptId"]
    msg = parse_payload(data)
    requests.delete(f"{BASE}/deleteNotification/{api_token}/{receipt_id}")
```

Benefits:
- No public URL → no attack surface (equivalent to Slack Socket Mode)
- No Cloudflare Tunnel needed → simpler setup, no account required
- No aiohttp webhook server needed → simpler code
- 1-second poll interval adds ~1s latency, acceptable given 5–15s LLM response time

**Do NOT use webhook mode. Do NOT add Cloudflare Tunnel. Do NOT add aiohttp.**

### CarPlay Flow

```
Shaun speaks → Siri → WhatsApp message to "Second Brain" contact (own number)
  → GREEN-API polling detects incoming message
  → ConversationEngine calls sdk_compat
  → LLM reads Memory vault (read-only)
  → Response sent via GREEN-API send_message
  → Siri reads WhatsApp reply aloud
```

Setup: Create a WhatsApp contact named "Second Brain" with Shaun's own mobile number.
Siri can then be told "Message Second Brain: [query]".

### Number Setup Note (as of 2026-06-12)

GREEN-API is currently connected to Shaun's personal number (61410868612). This means
WhatsApp notifications arrive from Shaun's own number — no push notification fires.

A second SIM (Aldi prepaid) has been ordered. Once it arrives:
1. Register WhatsApp on the Aldi number
2. In GREEN-API: delete current instance → create new instance → scan QR with Aldi number
3. Update `.env`: new `WHATSAPP_INSTANCE_ID`, `WHATSAPP_API_TOKEN`, and Aldi number for instance
4. `WHATSAPP_MY_NUMBER` stays as `61410868612` (Shaun's personal number — used by security filter)
5. Update "Second Brain" phone contact to point to the Aldi number

After this, messages arrive FROM the bot number TO Shaun's personal number → normal notifications.

### Self-Message Security Filter

The bot must ONLY respond to messages from `WHATSAPP_MY_NUMBER`. All other senders ignored.
```python
sender = payload.get("senderData", {}).get("chatId", "")
if WHATSAPP_MY_NUMBER not in sender:
    continue  # skip
```

This prevents anyone who learns the bot is running from injecting messages.

### Bot is Read-Only

The bot's LLM call uses `allowed_tools=["Read", "Glob", "Grep"]`.
No Write, Edit, or Bash. The bot answers questions from Memory vault — it does not
update it. Heartbeat + Reflection handle Memory writes.

### Session Persistence

Conversations persisted in SQLite (`chat.db`) at `.claude/data/chat.db`.
Session key: `"whatsapp:{chat_id}:{thread_id}"` (thread_id is empty for WhatsApp).
Session stores `agent_session_id` for sdk_compat resume.

On each incoming message:
- Look up existing session by key
- If found: `options.resume = existing.agent_session_id`
- If not: start fresh
- Save updated session after response

This gives conversational continuity across CarPlay interactions (e.g., "What about that
last email?" works if it's in the same session).

### AGENT_INVOKED_BY

Set `os.environ["AGENT_INVOKED_BY"] = "chat"` at the top of the bot entry point
(before imports). This activates the soul-protect.py hook and prevents SOUL.md edits
even though the bot is in interactive/read-only mode.

### No Cloudflare Tunnel

Since we use polling, no public URL is required. Remove all Cloudflare Tunnel references.
The bot process runs entirely locally with outbound connections only.

---

## Architecture

```
chat/
├── __init__.py
├── models.py          # Platform enum (WHATSAPP + CLI), User, IncomingMessage, OutgoingMessage
├── session.py         # SQLiteSessionStore + Session dataclass + get_session_store()
├── engine.py          # ConversationEngine.handle_message() — calls sdk_compat
├── router.py          # ChatRouter.run() — connects engine + adapter
├── main.py            # Entry point: asyncio.run(main())
└── adapters/
    ├── __init__.py
    ├── base.py        # PlatformAdapter Protocol
    └── whatsapp.py    # WhatsAppPollingAdapter — polls GREEN-API, no webhook server
```

Lives at `.claude/chat/` (not inside `.claude/scripts/`).

---

## WhatsApp Polling Adapter Design

```python
class WhatsAppPollingAdapter:
    def __init__(self, instance_id, api_token, my_number, poll_interval=1.0):
        self.instance_id = instance_id
        self.api_token = api_token
        self.my_number = my_number
        self.poll_interval = poll_interval

    async def connect(self) -> None:
        pass  # No server to start

    async def disconnect(self) -> None:
        pass

    async def listen(self) -> AsyncIterator[IncomingMessage]:
        while True:
            msg = await asyncio.get_event_loop().run_in_executor(None, self._poll_once)
            if msg:
                yield msg
            else:
                await asyncio.sleep(self.poll_interval)

    def _poll_once(self) -> IncomingMessage | None:
        # 1. GET receiveNotification
        # 2. If empty: return None
        # 3. Filter: only process if sender == my_number
        # 4. If not a text message: delete + return None
        # 5. Parse payload → IncomingMessage
        # 6. DELETE deleteNotification (acknowledge)
        # 7. return IncomingMessage

    async def send(self, message: OutgoingMessage) -> str:
        from integrations.whatsapp import send_message
        send_message(message.channel_id, message.text)
        return ""

    async def send_typing(self, channel_id: str) -> None:
        pass  # GREEN-API typing indicator not universally supported
```

---

## GREEN-API Payload Reference

```json
{
  "typeWebhook": "incomingMessageReceived",
  "receiptId": 1234567,
  "instanceData": {"idInstance": 12345},
  "timestamp": 1700000000,
  "idMessage": "AABBCC...",
  "senderData": {
    "chatId": "61412345678@c.us",
    "chatName": "Second Brain",
    "sender": "61412345678@c.us"
  },
  "messageData": {
    "typeMessage": "textMessage",
    "textMessageData": {"textMessage": "What's in my inbox?"}
  }
}
```

`receiptId` is what you pass to `deleteNotification` to acknowledge the message.

---

## Files Already Created by Phase 6 (reuse in Phase 7)

By the time Phase 7 is planned, Phase 6 will have delivered:

- `.claude/scripts/integrations/whatsapp.py` — `send_message()`, `get_greenapi_base()`,
  `get_unread_messages()` (the polling loop in the adapter replaces `get_unread_messages()`
  but the REST helpers are reused)
- `.claude/scripts/config.py` — `WHATSAPP_INSTANCE_ID`, `WHATSAPP_API_TOKEN`,
  `WHATSAPP_MY_NUMBER` already defined
- `.claude/data/chat.db` path defined in Phase 6 config (but CHAT_DB_PATH constant and
  CHAT_MAX_TURNS etc. are deferred to Phase 7 config additions)

---

## New Config Constants Needed in Phase 7

Add to `.claude/scripts/config.py` during Phase 7:
```python
CHAT_DB_PATH = DATA_DIR / "chat.db"
CHAT_MAX_TURNS = int(_os.getenv("CHAT_MAX_TURNS", "20"))
CHAT_MAX_BUDGET_USD = float(_os.getenv("CHAT_MAX_BUDGET_USD", "0.50"))
WHATSAPP_POLL_INTERVAL = float(_os.getenv("WHATSAPP_POLL_INTERVAL", "1.0"))
```

Add to `.env`:
```
CHAT_MAX_TURNS=20
CHAT_MAX_BUDGET_USD=0.50
WHATSAPP_POLL_INTERVAL=1.0
```

---

## Cole's Reference Files to Read During Phase 7 Planning

All at `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\`:
- `.claude/chat/models.py` — Platform enum + dataclasses
- `.claude/chat/session.py` — SQLiteSessionStore pattern
- `.claude/chat/engine.py` — ConversationEngine + sdk_compat resume pattern
- `.claude/chat/router.py` — ChatRouter.run() + _handle() pattern
- `.claude/chat/adapters/base.py` — PlatformAdapter Protocol
- `.claude/chat/adapters/slack.py` — Adapter pattern to replace (Slack → WhatsApp polling)

Key adaptation for all Cole's chat files: replace `from claude_agent_sdk import ...`
with `from sdk_compat import ...`.

---

## sdk_compat Session Resume Pattern

```python
# In engine.py handle_message():
existing = self.sessions.get(session_key)
options = ClaudeAgentOptions(
    allowed_tools=["Read", "Glob", "Grep"],
    max_turns=self.max_turns,
)
if existing and existing.agent_session_id:
    options.resume = existing.agent_session_id  # Continues conversation history

result = query(message.text, options=options)
# Save agent_session_id from result for next turn
```

---

## Windows Task Scheduler (Phase 7 addition)

```powershell
# WhatsApp bot — start on login (persistent background process):
$trigger = New-ScheduledTaskTrigger -AtLogOn
$action = New-ScheduledTaskAction `
    -Execute "uv" `
    -Argument "run python -m chat.main" `
    -WorkingDirectory "O:\AI\Dynamous\Courses\second-brain-workshop\.claude"
Register-ScheduledTask -TaskName "SecondBrain-WhatsAppBot" -Trigger $trigger -Action $action -RunLevel Highest
```

---

## Testing Approach

- `test_chat_session.py` — SQLiteSessionStore with `":memory:"` SQLite path
- `test_whatsapp_adapter.py` — Mock requests; test `_poll_once()` with sample JSON payload
- `test_chat_engine.py` — Mock sdk_compat `query()`; verify session key, resume logic
- Manual end-to-end: send WhatsApp message to self, verify bot replies

---

## Confidence Estimate for Phase 7

~8/10. The architecture is clear, Cole's reference is solid, and polling is simpler than
webhook. Main unknowns:
1. sdk_compat `query()` is synchronous — engine.py needs `run_in_executor` wrapper
2. GREEN-API polling payload shape may need minor adjustment from the reference above
3. Session resume behaviour depends on sdk_compat backend (Claude vs Pi)
