"""
Test: fake WhatsApp message → engine → daily log flush.

Sends one synthetic WhatsApp message through ConversationEngine and checks
whether the conversation summary appears in today's daily log afterwards.

Usage:
    uv run python .claude/scripts/tests/test_whatsapp_flush.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Wire up paths
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_CHAT_DIR = _SCRIPTS_DIR.parent / "chat"
sys.path.insert(0, str(_SCRIPTS_DIR))
sys.path.insert(0, str(_CHAT_DIR))

from config import CHAT_DB_PATH, DAILY_DIR, PROJECT_ROOT, now_local  # noqa: E402
from engine import ConversationEngine  # noqa: E402
from models import Channel, IncomingMessage, Platform, Thread, User  # noqa: E402
from session import get_session_store  # noqa: E402


TEST_MESSAGE = "This is a memory flush test. Please reply with exactly: FLUSH_TEST_OK"
TEST_USER_ID = "test-flush-user"
TEST_CHANNEL_ID = "test-flush-channel"


async def run() -> None:
    print(f"[{now_local()}] Starting WhatsApp flush test...")

    store = get_session_store(CHAT_DB_PATH)
    engine = ConversationEngine(
        session_store=store,
        project_root=PROJECT_ROOT,
        max_turns=3,
        max_budget_usd=0.10,
    )

    msg = IncomingMessage(
        text=TEST_MESSAGE,
        platform=Platform.WHATSAPP,
        user=User(platform=Platform.WHATSAPP, platform_id=TEST_USER_ID, display_name="Flush Tester"),
        channel=Channel(platform=Platform.WHATSAPP, platform_id=TEST_CHANNEL_ID, is_dm=True),
        thread=Thread(thread_id=TEST_CHANNEL_ID),
        timestamp=datetime.now(),
    )

    print(f"[{now_local()}] Sending fake message: {TEST_MESSAGE!r}")
    response_text = ""
    async for reply in engine.handle_message(msg):
        response_text = reply.text
        print(f"[{now_local()}] Engine response: {reply.text[:120]}")

    # Give the SessionEnd hook a moment to fire and write the flush
    await asyncio.sleep(3)

    # Check today's daily log for evidence of the conversation
    today_log = DAILY_DIR / f"{now_local().strftime('%Y-%m-%d')}.md"
    if today_log.exists():
        content = today_log.read_text(encoding="utf-8")
        if "FLUSH_TEST_OK" in content or "flush" in content.lower() or "whatsapp" in content.lower():
            print(f"\nPASS: Daily log contains conversation evidence — flush is working.")
        else:
            print(f"\nFAIL: Daily log exists but no flush evidence found.")
        print(f"  Log tail (last 800 chars):\n---\n{content[-800:]}\n---")
    else:
        print(f"\nFAIL: Daily log not found at {today_log}")

    print(f"[{now_local()}] Done.")


if __name__ == "__main__":
    asyncio.run(run())
