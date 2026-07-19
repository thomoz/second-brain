"""Smoke tests for Phase 4 integration helpers."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestConfigMultiAccount:
    def test_gmail_accounts_loaded(self) -> None:
        from config import GMAIL_ACCOUNTS

        assert len(GMAIL_ACCOUNTS) == 8

    def test_calendar_ids_loaded(self) -> None:
        from config import GOOGLE_CALENDAR_IDS

        assert len(GOOGLE_CALENDAR_IDS) == 6

    def test_local_tz_alias(self) -> None:
        from config import LOCAL_TZ, TZ

        assert LOCAL_TZ is TZ

    def test_google_token_file_per_account(self) -> None:
        from config import google_token_file

        path = google_token_file("personal")
        assert "token_gmail_personal.json" in str(path)

    def test_outlook_constants_present(self) -> None:
        from config import OUTLOOK_CLIENT_ID, OUTLOOK_TENANT_ID

        assert OUTLOOK_CLIENT_ID  # non-empty
        assert OUTLOOK_TENANT_ID == "consumers"

    def test_integrations_dir_is_absolute(self) -> None:
        from config import INTEGRATIONS_DIR

        assert INTEGRATIONS_DIR.is_absolute()

    def test_google_credentials_path(self) -> None:
        from config import GOOGLE_CREDENTIALS_FILE

        assert GOOGLE_CREDENTIALS_FILE.exists()


class TestGmailFormatting:
    def test_format_empty(self) -> None:
        from integrations.gmail import format_emails_for_context

        assert format_emails_for_context([]) == "No emails found."


class TestCalendarFormatting:
    def test_format_empty_dict(self) -> None:
        from integrations.calendar_api import format_all_calendars_for_context

        result = format_all_calendars_for_context({})
        assert "No calendar data" in result

    def test_format_empty_calendar(self) -> None:
        from integrations.calendar_api import format_all_calendars_for_context

        result = format_all_calendars_for_context({"personal": []})
        assert "personal" in result
        assert "No upcoming events" in result


class TestOutlookFormatting:
    def test_format_empty(self) -> None:
        from integrations.outlook import format_messages_for_context

        assert format_messages_for_context([]) == "No Outlook messages found."


class TestOutlookJunkRules:
    def _make_message(self, subject: str = "", sender: str = "", sender_email: str = ""):
        from datetime import datetime, timezone

        from integrations.outlook import OutlookMessage

        return OutlookMessage(
            id="1",
            subject=subject,
            sender=sender,
            sender_email=sender_email,
            date=datetime.now(timezone.utc),
            snippet="",
            is_unread=False,
            thread_id="t1",
        )

    def test_load_junk_rules_missing_file_returns_empty(self, monkeypatch, tmp_path) -> None:
        import integrations.outlook as outlook

        monkeypatch.setattr(outlook, "OUTLOOK_JUNK_RULES_FILE", tmp_path / "does-not-exist.json")
        assert outlook.load_junk_rules() == {"subject_contains": [], "sender_contains": []}

    def test_find_rule_match_subject_keyword(self) -> None:
        from integrations.outlook import find_rule_match

        msg = self._make_message(subject="Claim your FREE prize now")
        rules = {"subject_contains": ["free prize"], "sender_contains": []}
        assert find_rule_match(msg, rules) == "free prize"

    def test_find_rule_match_sender_keyword(self) -> None:
        from integrations.outlook import find_rule_match

        msg = self._make_message(subject="Hello", sender="Spammy Co", sender_email="x@spam.example.com")
        rules = {"subject_contains": [], "sender_contains": ["spam.example.com"]}
        assert find_rule_match(msg, rules) == "spam.example.com"

    def test_find_rule_match_no_match_returns_none(self) -> None:
        from integrations.outlook import find_rule_match

        msg = self._make_message(subject="Invoice attached", sender="Real Vendor", sender_email="x@vendor.com")
        rules = {"subject_contains": ["free prize"], "sender_contains": ["spam.example.com"]}
        assert find_rule_match(msg, rules) is None
