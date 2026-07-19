"""GREEN-API polling adapter — outbound connections only, no public URL."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

import requests

_CHAT_DIR = Path(__file__).resolve().parent.parent  # .claude/chat/
_SCRIPTS_DIR = _CHAT_DIR.parent / "scripts"  # .claude/scripts/
sys.path.insert(0, str(_CHAT_DIR))
sys.path.insert(0, str(_SCRIPTS_DIR))

from models import Channel, IncomingMessage, OutgoingMessage, Platform, User  # noqa: E402


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
        self.my_number = my_number  # e.g. "61410868612"
        self.poll_interval = poll_interval
        self.my_lid = ""  # e.g. "215895204962474@lid" — resolved at connect()

    @property
    def platform(self) -> Platform:
        return Platform.WHATSAPP

    async def connect(self) -> None:
        from integrations.whatsapp import get_own_chat_id

        self.my_lid = get_own_chat_id(self.instance_id, self.api_token)
        print(f"[{datetime.now()}] WhatsApp adapter ready (polling instance {self.instance_id})")

    async def disconnect(self) -> None:
        print(f"[{datetime.now()}] WhatsApp adapter stopped")

    async def listen(self) -> AsyncIterator[IncomingMessage]:
        loop = asyncio.get_running_loop()
        while True:
            msg = await loop.run_in_executor(None, self._poll_once)
            if msg is not None:
                yield msg
            else:
                await asyncio.sleep(self.poll_interval)

    def _poll_once(self) -> IncomingMessage | None:
        """Single poll: GET one notification, filter, parse, DELETE (acknowledge)."""
        from integrations.whatsapp import get_greenapi_base

        base = get_greenapi_base(self.instance_id)
        try:
            resp = requests.get(f"{base}/receiveNotification/{self.api_token}", timeout=15)
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

            if body.get("typeWebhook") != "incomingMessageReceived":
                _ack()
                return None

            sender_data = body.get("senderData", {})
            sender = sender_data.get("sender", "")

            # Security filter: only respond to Shaun's own account, by phone-number JID
            # or lid (fail-closed: no match on either configured identifier blocks it)
            is_mine = bool(self.my_number) and self.my_number in sender
            if not is_mine and self.my_lid:
                is_mine = sender == self.my_lid
            if not is_mine:
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
