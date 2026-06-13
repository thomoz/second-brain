"""
GREEN-API WhatsApp client for Second Brain.

Phase 6: outbound send only.
Phase 7 will add inbound polling (do not call get_unread_messages
if the Phase 7 bot is running — the notification queue is destructive).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sanitize import sanitize_external_text  # noqa: E402


@dataclass
class WhatsAppMessage:
    id: str
    sender: str
    text: str
    timestamp: datetime
    is_from_me: bool


def get_greenapi_base(instance_id: str) -> str:
    """Return the GREEN-API base URL for the given instance."""
    return f"https://api.green-api.com/waInstance{instance_id}"


def send_message(
    chat_id: str,
    text: str,
    instance_id: str = "",
    api_token: str = "",
) -> bool:
    """Send a WhatsApp message via GREEN-API. Returns True on success."""
    from config import WHATSAPP_API_TOKEN, WHATSAPP_INSTANCE_ID

    iid = instance_id or WHATSAPP_INSTANCE_ID
    tok = api_token or WHATSAPP_API_TOKEN
    if not iid or not tok:
        return False
    try:
        resp = requests.post(
            f"{get_greenapi_base(iid)}/sendMessage/{tok}",
            json={"chatId": chat_id, "message": text},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[whatsapp] send_message error: {e}")
        return False


def get_unread_messages(limit: int = 10) -> list[WhatsAppMessage]:
    """Poll GREEN-API notification queue for incoming text messages.

    DESTRUCTIVE — dequeues messages. Do not call if Phase 7 bot is running.
    """
    from config import WHATSAPP_API_TOKEN, WHATSAPP_INSTANCE_ID

    iid = WHATSAPP_INSTANCE_ID
    tok = WHATSAPP_API_TOKEN
    if not iid or not tok:
        return []

    base = get_greenapi_base(iid)
    messages: list[WhatsAppMessage] = []

    for _ in range(limit):
        try:
            resp = requests.get(f"{base}/receiveNotification/{tok}", timeout=10)
            if resp.status_code != 200:
                break
            data = resp.json()
            if data is None:
                break

            receipt_id = data.get("receiptId")
            body = data.get("body", {})
            msg_type = body.get("typeWebhook", "")

            if msg_type == "incomingMessageReceived":
                msg_data = body.get("messageData", {})
                if msg_data.get("typeMessage") == "textMessage":
                    sender = body.get("senderData", {}).get("sender", "")
                    text = msg_data.get("textMessageData", {}).get("textMessage", "")
                    ts_raw = body.get("timestamp", 0)
                    ts = datetime.fromtimestamp(ts_raw) if ts_raw else datetime.now()
                    messages.append(
                        WhatsAppMessage(
                            id=str(receipt_id),
                            sender=sender,
                            text=text,
                            timestamp=ts,
                            is_from_me=False,
                        )
                    )

            # Dequeue regardless of type
            if receipt_id:
                requests.delete(
                    f"{base}/deleteNotification/{tok}/{receipt_id}",
                    timeout=10,
                )
        except Exception as e:
            print(f"[whatsapp] get_unread_messages error: {e}")
            break

    return messages


def format_messages_for_context(messages: list[WhatsAppMessage]) -> str:
    """Format a list of WhatsApp messages for prompt context."""
    if not messages:
        return "No WhatsApp messages."
    return "\n".join(
        f"[{m.timestamp.strftime('%H:%M')}] "
        f"{sanitize_external_text(m.sender, 'whatsapp')}: "
        f"{sanitize_external_text(m.text, 'whatsapp')}"
        for m in messages
    )
