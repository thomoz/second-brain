"""Platform-agnostic message models for the Second Brain chat interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Platform(Enum):
    WHATSAPP = "whatsapp"
    CLI = "cli"


class MessageType(Enum):
    TEXT = "text"
    FILE = "file"
    REACTION = "reaction"


@dataclass
class User:
    platform: Platform
    platform_id: str
    display_name: str | None = None

    @property
    def unified_id(self) -> str:
        return f"{self.platform.value}:{self.platform_id}"


@dataclass
class Channel:
    platform: Platform
    platform_id: str
    name: str | None = None
    is_dm: bool = False

    @property
    def unified_id(self) -> str:
        return f"{self.platform.value}:{self.platform_id}"


@dataclass
class Thread:
    thread_id: str
    parent_message_id: str | None = None


@dataclass
class Attachment:
    filename: str
    mimetype: str | None = None
    url: str | None = None
    size_bytes: int | None = None


@dataclass
class IncomingMessage:
    text: str
    user: User
    channel: Channel
    platform: Platform
    thread: Thread | None = None
    platform_message_id: str | None = None
    attachments: list[Attachment] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    raw_event: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutgoingMessage:
    text: str
    channel: Channel
    thread: Thread | None = None
    is_update: bool = False
    update_message_id: str | None = None
    attachments: list[Attachment] = field(default_factory=list)
