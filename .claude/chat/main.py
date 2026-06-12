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

from config import (  # noqa: E402
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Second Brain WhatsApp Bot")
    parser.add_argument("--test", action="store_true", help="Validate config and exit")
    args = parser.parse_args()

    # Validate required credentials
    missing = [
        n
        for v, n in [
            (WHATSAPP_INSTANCE_ID, "WHATSAPP_INSTANCE_ID"),
            (WHATSAPP_API_TOKEN, "WHATSAPP_API_TOKEN"),
            (WHATSAPP_MY_NUMBER, "WHATSAPP_MY_NUMBER"),
        ]
        if not v
    ]
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
        # Lazy imports — validate components independently
        from session import get_session_store

        store = get_session_store(CHAT_DB_PATH)
        print(f"  Session store OK ({len(store.list_active())} active sessions)")

        try:
            from engine import ConversationEngine

            engine = ConversationEngine(store, PROJECT_ROOT, CHAT_MAX_TURNS, CHAT_MAX_BUDGET_USD)
            print("  Engine OK")
        except ModuleNotFoundError as e:
            print(f"  Engine: SKIPPED (SDK not installed in this env: {e})")
            engine = None  # type: ignore[assignment]

        from adapters.whatsapp import WhatsAppPollingAdapter

        adapter = WhatsAppPollingAdapter(
            WHATSAPP_INSTANCE_ID, WHATSAPP_API_TOKEN, WHATSAPP_MY_NUMBER, WHATSAPP_POLL_INTERVAL
        )
        print(f"  Adapter OK ({adapter.platform.value})")

        if engine is not None:
            from router import ChatRouter

            router = ChatRouter(engine)
            router.register(adapter)
            print("  Router OK")

        print("\nAll checks passed. Run without --test to start.")
        return

    # Full run — lazy imports (engine requires claude_agent_sdk / configured backend)
    from adapters.whatsapp import WhatsAppPollingAdapter
    from engine import ConversationEngine
    from router import ChatRouter
    from session import get_session_store

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
