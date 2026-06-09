"""
Outlook/Microsoft 365 integration for Second Brain.

Read-only access to Outlook inbox via Microsoft Graph API.
Uses MSAL device code flow (no browser required on first run).

Usage:
    uv run python -m integrations.outlook list --max 5
    uv run python -m integrations.outlook unread
    uv run python -m integrations.outlook auth
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (  # noqa: E402
    LOCAL_TZ,
    OUTLOOK_CLIENT_ID,
    OUTLOOK_SCOPES,
    OUTLOOK_TENANT_ID,
    OUTLOOK_TOKEN_FILE,
    now_local,
)
from sanitize import sanitize_external_text  # noqa: E402
from shared import with_retry  # noqa: E402

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


@dataclass
class OutlookMessage:
    id: str
    subject: str
    sender: str
    sender_email: str
    date: datetime
    snippet: str
    is_unread: bool
    thread_id: str
    labels: list[str] = field(default_factory=list)


def _get_token_cache() -> Any:
    import msal
    cache = msal.SerializableTokenCache()
    if OUTLOOK_TOKEN_FILE.exists():
        cache.deserialize(OUTLOOK_TOKEN_FILE.read_text(encoding="utf-8"))
    return cache


def _save_token_cache(cache: Any) -> None:
    if cache.has_state_changed:
        OUTLOOK_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTLOOK_TOKEN_FILE.write_text(cache.serialize(), encoding="utf-8")


def get_access_token() -> str:
    """Acquire Outlook access token. Uses cached token if valid; device code flow otherwise."""
    import msal

    if not OUTLOOK_CLIENT_ID:
        raise RuntimeError(
            "OUTLOOK_CLIENT_ID not set in .env\n"
            "Add: OUTLOOK_CLIENT_ID=<your-azure-app-client-id>"
        )

    cache = _get_token_cache()
    app = msal.PublicClientApplication(
        OUTLOOK_CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{OUTLOOK_TENANT_ID}",
        token_cache=cache,
    )

    # Try silent token refresh first
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(OUTLOOK_SCOPES, account=accounts[0])
        if result and "access_token" in result:
            _save_token_cache(cache)
            return result["access_token"]

    # Device code flow (interactive — only runs when no cached token)
    flow = app.initiate_device_flow(scopes=OUTLOOK_SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(f"Device flow failed: {flow.get('error_description', 'unknown')}")

    print("\n" + "=" * 60)
    print("  OUTLOOK AUTHENTICATION")
    print("=" * 60)
    print(f"\n{flow['message']}\n")

    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(f"Outlook auth failed: {result.get('error_description', result)}")

    _save_token_cache(cache)
    return result["access_token"]


def is_outlook_authenticated() -> bool:
    """Check if a valid Outlook token exists without triggering auth flow."""
    if not OUTLOOK_TOKEN_FILE.exists():
        return False
    try:
        import msal
        cache = _get_token_cache()
        app = msal.PublicClientApplication(
            OUTLOOK_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{OUTLOOK_TENANT_ID}",
            token_cache=cache,
        )
        accounts = app.get_accounts()
        return bool(accounts)
    except Exception:
        return False


def _parse_outlook_message(msg: dict[str, Any]) -> OutlookMessage:
    """Parse a Graph API message dict into OutlookMessage."""
    sender_info = msg.get("from", {}).get("emailAddress", {})
    received = msg.get("receivedDateTime", "")
    try:
        date = datetime.fromisoformat(received.replace("Z", "+00:00"))
    except Exception:
        date = now_local()

    return OutlookMessage(
        id=msg.get("id", ""),
        subject=msg.get("subject", "(no subject)"),
        sender=sender_info.get("name", ""),
        sender_email=sender_info.get("address", ""),
        date=date,
        snippet=msg.get("bodyPreview", "")[:200],
        is_unread=not msg.get("isRead", True),
        thread_id=msg.get("conversationId", ""),
    )


def list_messages(
    max_results: int = 15,
    unread_only: bool = False,
    hours_ago: int | None = None,
) -> list[OutlookMessage]:
    """List Outlook messages, optionally filtered."""
    import requests

    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    filters: list[str] = []
    if unread_only:
        filters.append("isRead eq false")
    if hours_ago:
        from datetime import timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        filters.append(f"receivedDateTime ge {cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')}")

    params: dict[str, Any] = {
        "$top": max_results,
        "$select": "id,subject,from,receivedDateTime,bodyPreview,isRead,conversationId",
        "$orderby": "receivedDateTime desc",
    }
    if filters:
        params["$filter"] = " and ".join(filters)

    result: dict[str, Any] = with_retry(
        lambda: requests.get(
            f"{GRAPH_BASE}/me/messages",
            headers=headers,
            params=params,
        ).json()
    )

    return [_parse_outlook_message(m) for m in result.get("value", [])]


def get_unread_count() -> int:
    """Get count of unread messages in Outlook inbox."""
    import requests

    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    result: dict[str, Any] = with_retry(
        lambda: requests.get(
            f"{GRAPH_BASE}/me/mailFolders/inbox",
            headers=headers,
            params={"$select": "unreadItemCount"},
        ).json()
    )
    return int(result.get("unreadItemCount", 0))


def format_messages_for_context(messages: list[OutlookMessage], max_chars: int = 2000) -> str:
    """Format Outlook messages for context injection."""
    if not messages:
        return "No Outlook messages found."
    output: list[str] = []
    chars = 0
    for msg in messages:
        date_local = msg.date.astimezone(LOCAL_TZ) if msg.date.tzinfo else msg.date
        subject = sanitize_external_text(msg.subject, "outlook")
        sender = sanitize_external_text(msg.sender, "outlook")
        snippet = sanitize_external_text(msg.snippet[:100], "outlook")
        entry = (
            f"- **{subject}** [thread_id: {msg.thread_id}]\n"
            f"  From: {sender} <{msg.sender_email}>\n"
            f"  Date: {date_local.strftime('%Y-%m-%d %H:%M')}\n"
            f"  {'[UNREAD] ' if msg.is_unread else ''}{snippet}"
        )
        if chars + len(entry) > max_chars:
            output.append(f"\n... and {len(messages) - len(output)} more")
            break
        output.append(entry)
        chars += len(entry)
    return "\n\n".join(output)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Outlook integration")
    parser.add_argument("command", choices=["auth", "list", "unread"])
    parser.add_argument("--max", type=int, default=10)
    parser.add_argument("--hours", type=int, default=None)
    args = parser.parse_args()

    if args.command == "auth":
        get_access_token()
        print("Outlook authentication successful!")
    elif args.command == "list":
        msgs = list_messages(max_results=args.max, hours_ago=args.hours)
        print(format_messages_for_context(msgs))
    elif args.command == "unread":
        print(f"Unread Outlook messages: {get_unread_count()}")
