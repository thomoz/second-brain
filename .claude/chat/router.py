"""Chat router: connects the WhatsApp adapter to the conversation engine."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(_SCRIPTS_DIR))

from engine import ConversationEngine  # noqa: E402
from models import OutgoingMessage, Platform  # noqa: E402


class ChatRouter:
    """Routes messages between platform adapters and the conversation engine."""

    def __init__(self, engine: ConversationEngine) -> None:
        self.engine = engine
        self.adapters: dict[Platform, Any] = {}

    def register(self, adapter: Any) -> None:
        self.adapters[adapter.platform] = adapter
        print(f"[{datetime.now()}] Registered adapter: {adapter.platform.value}")

    async def run(self) -> None:
        if not self.adapters:
            print(f"[{datetime.now()}] No adapters registered, nothing to do")
            return

        await asyncio.gather(*(a.connect() for a in self.adapters.values()))
        print(f"[{datetime.now()}] All adapters connected")

        tasks = [asyncio.create_task(self._listen(adapter)) for adapter in self.adapters.values()]
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            print(f"[{datetime.now()}] Router shutting down...")

    async def _listen(self, adapter: Any) -> None:
        try:
            async for incoming in adapter.listen():
                asyncio.create_task(self._handle(adapter, incoming))
        except asyncio.CancelledError:
            return
        except Exception as e:
            print(f"[{datetime.now()}] Listener error ({adapter.platform.value}): {e}")

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
            await adapter.send(
                OutgoingMessage(text=final_text, channel=incoming.channel, thread=incoming.thread)
            )
        except Exception as e:
            print(f"[{datetime.now()}] Failed to send response: {e}")

    async def shutdown(self) -> None:
        for adapter in self.adapters.values():
            try:
                await adapter.disconnect()
            except Exception as e:
                print(f"[{datetime.now()}] Error disconnecting {adapter.platform.value}: {e}")
