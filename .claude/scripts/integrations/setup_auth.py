"""
One-time auth setup for all Second Brain integrations.

Walks through Google OAuth for 8 Gmail accounts and Outlook device code flow.

Usage:
    uv run python integrations/setup_auth.py          # Full interactive setup
    uv run python integrations/setup_auth.py --check  # Status check only (no auth flows)
    uv run python integrations/setup_auth.py --headless  # Use manual URL flow (no browser)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import GMAIL_ACCOUNTS, GOOGLE_CALENDAR_IDS, GOOGLE_CREDENTIALS_FILE, ensure_directories  # noqa: E402


def print_header(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def print_status(name: str, ok: bool, detail: str = "") -> None:
    """Print a status line."""
    icon = "[OK]" if ok else "[--]"
    suffix = f" - {detail}" if detail else ""
    print(f"  {icon} {name}{suffix}")


def check_google(check_only: bool = False, headless: bool = False) -> bool:
    """Authenticate all 8 Gmail accounts + validate Calendar access."""
    from integrations.auth import is_google_authenticated, run_initial_auth

    print_header("Google OAuth — Gmail (8 accounts) + Calendar (6 calendars)")

    if not GOOGLE_CREDENTIALS_FILE.exists():
        print(f"  Missing: {GOOGLE_CREDENTIALS_FILE}")
        print("  Download from Google Cloud Console → Credentials → OAuth client ID → Desktop app")
        return False

    # Calendar sharing notice
    print("  NOTE: Non-personal calendars must be shared with shaunthommo10@gmail.com")
    print("  in Google Calendar settings for multi-calendar access to work.")
    print(f"  Calendars to configure: {', '.join(GOOGLE_CALENDAR_IDS.keys())}\n")

    all_ok = True
    for account_name, email in GMAIL_ACCOUNTS.items():
        if is_google_authenticated(account_name):
            print_status(f"Gmail [{account_name}]", True, email)
            continue
        if check_only:
            print_status(f"Gmail [{account_name}]", False, f"{email} — not authenticated")
            all_ok = False
            continue
        print(f"\n  Authenticating {account_name} ({email})...")
        try:
            run_initial_auth(account_name=account_name, headless=headless)
            print_status(f"Gmail [{account_name}]", True, email)
        except Exception as e:
            print_status(f"Gmail [{account_name}]", False, str(e))
            all_ok = False

    return all_ok


def check_outlook(check_only: bool = False) -> bool:
    """Authenticate Outlook via MSAL device code flow."""
    from config import OUTLOOK_CLIENT_ID
    from integrations.outlook import get_access_token, is_outlook_authenticated

    print_header("Outlook (Microsoft Graph — Device Code Flow)")

    if not OUTLOOK_CLIENT_ID:
        print_status("Outlook", False, "OUTLOOK_CLIENT_ID not set in .env")
        return False

    if is_outlook_authenticated():
        print_status("Outlook", True, "Token exists and is valid/refreshable")
        return True

    if check_only:
        print_status("Outlook", False, "Not authenticated — run without --check")
        return False

    try:
        get_access_token()  # Triggers device code flow
        print_status("Outlook", True, "Authenticated successfully")
        return True
    except Exception as e:
        print_status("Outlook", False, str(e))
        return False


def main() -> None:
    """Run auth setup."""
    parser = argparse.ArgumentParser(description="Set up Second Brain integrations")
    parser.add_argument("--check", action="store_true", help="Check status only (no auth flows)")
    parser.add_argument(
        "--headless", action="store_true",
        help="Use manual URL copy-paste flow (for remote/headless machines)"
    )
    args = parser.parse_args()

    ensure_directories()

    print_header("Second Brain — Integrations Auth Setup")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    mode = "Status Check" if args.check else ("Headless Setup" if args.headless else "Interactive Setup")
    print(f"  Mode: {mode}")

    results = {
        "Google (Gmail + Calendar)": check_google(check_only=args.check, headless=args.headless),
        "Outlook": check_outlook(check_only=args.check),
    }

    print_header("Summary")
    for name, ok in results.items():
        print_status(name, ok)

    configured = sum(1 for ok in results.values() if ok)
    total = len(results)
    print(f"\n  {configured}/{total} integrations configured")

    if configured < total and not args.check:
        print("\n  Re-run with --check to see what's still needed.")

    sys.exit(0 if configured == total else 1)


if __name__ == "__main__":
    main()
