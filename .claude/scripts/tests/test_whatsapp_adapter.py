"""Unit tests for chat/adapters/whatsapp.py — no live API calls."""

from __future__ import annotations

import sys
from pathlib import Path

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
    requests_mock.get(
        f"https://api.green-api.com/waInstance{INSTANCE}/receiveNotification/{TOKEN}",
        json=SAMPLE_PAYLOAD,
    )
    requests_mock.delete(
        f"https://api.green-api.com/waInstance{INSTANCE}/deleteNotification/{TOKEN}/12345"
    )
    msg = adapter._poll_once()
    assert msg is not None
    assert msg.text == "What's on my calendar?"
    assert msg.platform == Platform.WHATSAPP


def test_poll_once_filters_unknown_sender(requests_mock):
    adapter = make_adapter()
    requests_mock.get(
        f"https://api.green-api.com/waInstance{INSTANCE}/receiveNotification/{TOKEN}",
        json=OTHER_PAYLOAD,
    )
    requests_mock.delete(
        f"https://api.green-api.com/waInstance{INSTANCE}/deleteNotification/{TOKEN}/99"
    )
    msg = adapter._poll_once()
    assert msg is None


def test_poll_once_empty_queue(requests_mock):
    adapter = make_adapter()
    requests_mock.get(
        f"https://api.green-api.com/waInstance{INSTANCE}/receiveNotification/{TOKEN}",
        json=None,
    )
    msg = adapter._poll_once()
    assert msg is None


def test_poll_once_empty_my_number_blocks_all(requests_mock):
    """Adapter with empty my_number is fail-closed — no sender is allowed through."""
    adapter = WhatsAppPollingAdapter(INSTANCE, TOKEN, my_number="")
    requests_mock.get(
        f"https://api.green-api.com/waInstance{INSTANCE}/receiveNotification/{TOKEN}",
        json=SAMPLE_PAYLOAD,
    )
    requests_mock.delete(
        f"https://api.green-api.com/waInstance{INSTANCE}/deleteNotification/{TOKEN}/12345"
    )
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
    requests_mock.get(
        f"https://api.green-api.com/waInstance{INSTANCE}/receiveNotification/{TOKEN}",
        json=payload,
    )
    requests_mock.delete(
        f"https://api.green-api.com/waInstance{INSTANCE}/deleteNotification/{TOKEN}/200"
    )
    msg = adapter._poll_once()
    assert msg is None
