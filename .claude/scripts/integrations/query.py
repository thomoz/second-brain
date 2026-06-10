"""
Unified CLI for Second Brain direct integrations.

Usage:
    python integrations/query.py gmail list --max 5
    python integrations/query.py gmail list --account sbdb
    python integrations/query.py calendar today
    python integrations/query.py calendar all
    python integrations/query.py outlook list --max 5
    python integrations/query.py outlook unread
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def cmd_gmail(args: argparse.Namespace) -> None:
    """Handle Gmail commands."""
    from integrations.gmail import (
        check_for_urgent_emails,
        create_gmail_draft,
        create_gmail_draft_from_file,
        format_emails_for_context,
        format_thread_for_context,
        get_email_details,
        get_gmail_service,
        get_thread_messages,
        get_unread_count,
        list_all_accounts,
        list_attachments,
        list_emails,
    )

    account = getattr(args, "account", None)

    if args.action == "list":
        hours = args.hours if args.hours is not None else (None if args.query else 24)
        if account:
            emails = list_emails(
                max_results=args.max,
                query=args.query or "",
                unread_only=args.unread,
                hours_ago=hours,
                account_name=account,
            )
        else:
            emails = list_all_accounts(max_per_account=args.max, hours_ago=hours)
        print(format_emails_for_context(emails))

    elif args.action == "urgent":
        if account:
            urgent = check_for_urgent_emails(hours_ago=args.hours, account_name=account)
        else:
            from integrations.gmail import list_all_accounts as _all

            urgent = _all(max_per_account=20, unread_only=True, hours_ago=args.hours or 2)
        if urgent:
            print(f"Found {len(urgent)} potentially urgent emails:\n")
            print(format_emails_for_context(urgent))
        else:
            print("No urgent emails found")

    elif args.action == "unread":
        if account:
            print(f"Unread ({account}): {get_unread_count(account_name=account)}")
        else:
            from config import GMAIL_ACCOUNTS
            from integrations.auth import is_google_authenticated

            for acct in GMAIL_ACCOUNTS:
                if is_google_authenticated(acct):
                    count = get_unread_count(account_name=acct)
                    print(f"  {acct}: {count} unread")

    elif args.action == "read":
        if not args.message_id:
            print("Error: message_id required for read command")
            sys.exit(1)
        acct = account or "personal"
        service = get_gmail_service(acct)
        email = get_email_details(service, args.message_id, include_body=True)
        if email:
            print(f"Subject: {email.subject}")
            print(f"From: {email.sender} <{email.sender_email}>")
            print(f"Date: {email.date}")
            print(f"\n{email.body or email.snippet}")
        else:
            print("Email not found")

    elif args.action == "thread":
        if not args.message_id:
            print("Error: thread_id required for thread command")
            sys.exit(1)
        emails = get_thread_messages(args.message_id)
        print(format_thread_for_context(emails))

    elif args.action == "attachments":
        if not args.message_id:
            print("Error: message_id required for attachments command")
            sys.exit(1)
        atts = list_attachments(args.message_id)
        if not atts:
            print("No attachments found.")
        else:
            for a in atts:
                print(f"  - {a.filename} ({a.mime_type}, {a.size / 1024:.1f} KB)")
                print(f"    attachment_id: {a.id}")

    elif args.action == "create-draft":
        from_file = getattr(args, "from_file", None)
        if from_file:
            result = create_gmail_draft_from_file(from_file)
        else:
            to = getattr(args, "to", None)
            subject = getattr(args, "draft_subject", None)
            body = getattr(args, "body", None)
            if not to or not subject or not body:
                print("Error: --from-file or (--to, --subject, --body) required")
                sys.exit(1)
            result = create_gmail_draft(
                to=to,
                subject=subject,
                body=body,
                thread_id=getattr(args, "thread_id", None),
                message_id=args.message_id,
            )
        print(json.dumps(result, indent=2))


def cmd_calendar(args: argparse.Namespace) -> None:
    """Handle Calendar commands."""
    from integrations.calendar_api import (
        check_for_upcoming_meetings,
        format_all_calendars_for_context,
        format_events_for_context,
        get_all_calendars_events,
        get_today_events,
        get_upcoming_events,
    )

    calendar_name = getattr(args, "calendar", None)

    if args.action == "all":
        results = get_all_calendars_events(hours_ahead=args.hours)
        print(format_all_calendars_for_context(results))

    elif args.action == "today":
        if calendar_name:
            from config import GOOGLE_CALENDAR_IDS

            cal_id = GOOGLE_CALENDAR_IDS.get(calendar_name)
            if not cal_id:
                print(f"Unknown calendar: {calendar_name}")
                print(f"Available: {', '.join(GOOGLE_CALENDAR_IDS.keys())}")
                sys.exit(1)
            events = get_today_events(calendar_id=cal_id)
        else:
            events = get_today_events()
        print(format_events_for_context(events))

    elif args.action == "upcoming":
        if calendar_name:
            from config import GOOGLE_CALENDAR_IDS

            cal_id = GOOGLE_CALENDAR_IDS.get(calendar_name)
            events = get_upcoming_events(hours_ahead=args.hours, calendar_id=cal_id)
        else:
            events = get_upcoming_events(hours_ahead=args.hours)
        print(format_events_for_context(events))

    elif args.action == "soon":
        events = check_for_upcoming_meetings(hours_ahead=4)
        print(format_events_for_context(events))


def cmd_whatsapp(args: argparse.Namespace) -> None:
    """Handle WhatsApp commands via GREEN-API."""
    from config import WHATSAPP_MY_NUMBER
    from integrations.whatsapp import format_messages_for_context, get_unread_messages, send_message

    if args.action == "list":
        msgs = get_unread_messages(limit=args.max)
        print(format_messages_for_context(msgs))
    elif args.action == "unread":
        msgs = get_unread_messages(limit=50)
        print(f"Unread WhatsApp messages: {len(msgs)}")
    elif args.action == "send":
        if not args.text:
            print("Error: --text required for send command")
            sys.exit(1)
        chat_id = args.chat_id or f"{WHATSAPP_MY_NUMBER}@c.us"
        ok = send_message(chat_id, args.text)
        print("Sent" if ok else "Failed to send")


def cmd_outlook(args: argparse.Namespace) -> None:
    """Handle Outlook commands."""
    from integrations.outlook import (
        format_messages_for_context,
        get_unread_count,
        list_messages,
    )

    if args.action == "list":
        msgs = list_messages(max_results=args.max, hours_ago=args.hours)
        print(format_messages_for_context(msgs))

    elif args.action == "unread":
        print(f"Unread Outlook messages: {get_unread_count()}")

    elif args.action == "urgent":
        msgs = list_messages(max_results=20, unread_only=True, hours_ago=args.hours or 2)
        print(format_messages_for_context(msgs))


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Second Brain Direct Integrations")
    subparsers = parser.add_subparsers(dest="service", required=True)

    # Gmail
    gmail_parser = subparsers.add_parser("gmail", help="Gmail operations (8 accounts)")
    gmail_parser.add_argument(
        "action",
        choices=["list", "urgent", "unread", "read", "thread", "attachments", "create-draft"],
    )
    gmail_parser.add_argument("message_id", nargs="?", default=None)
    gmail_parser.add_argument("--max", type=int, default=10)
    gmail_parser.add_argument("--query", default=None)
    gmail_parser.add_argument("--hours", type=int, default=None)
    gmail_parser.add_argument("--unread", action="store_true")
    gmail_parser.add_argument(
        "--account",
        default=None,
        help="Account name (e.g. personal, sbdb, karaoke); defaults to all",
    )
    gmail_parser.add_argument("--from-file", default=None, dest="from_file")
    gmail_parser.add_argument("--to", default=None)
    gmail_parser.add_argument("--subject", dest="draft_subject", default=None)
    gmail_parser.add_argument("--body", default=None)
    gmail_parser.add_argument("--thread-id", default=None)

    # Calendar
    cal_parser = subparsers.add_parser("calendar", help="Calendar operations (6 calendars)")
    cal_parser.add_argument("action", choices=["all", "today", "upcoming", "soon"])
    cal_parser.add_argument("--hours", type=int, default=24)
    cal_parser.add_argument(
        "--calendar",
        default=None,
        help="Calendar name (e.g. personal, bgk, bingo); defaults to primary",
    )

    # Outlook
    outlook_parser = subparsers.add_parser("outlook", help="Outlook inbox operations")
    outlook_parser.add_argument("action", choices=["list", "unread", "urgent"])
    outlook_parser.add_argument("--max", type=int, default=10)
    outlook_parser.add_argument("--hours", type=int, default=None)

    # WhatsApp
    wa_parser = subparsers.add_parser("whatsapp", help="WhatsApp operations via GREEN-API")
    wa_parser.add_argument("action", choices=["list", "unread", "send"])
    wa_parser.add_argument("--max", type=int, default=10)
    wa_parser.add_argument("--text", default=None)
    wa_parser.add_argument("--chat-id", default=None, dest="chat_id")

    args = parser.parse_args()

    try:
        if args.service == "gmail":
            cmd_gmail(args)
        elif args.service == "calendar":
            cmd_calendar(args)
        elif args.service == "outlook":
            cmd_outlook(args)
        elif args.service == "whatsapp":
            cmd_whatsapp(args)
    except Exception as e:
        print(json.dumps({"error": str(e), "type": "runtime"}, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
