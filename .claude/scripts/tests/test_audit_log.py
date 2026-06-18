"""Tests for append_audit_log in shared.py."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import append_audit_log


def test_audit_log_creates_file(tmp_path):
    log = tmp_path / "security_audit.log"
    append_audit_log("block-secrets", "Read", "Blocked: .env", ".env", _path=log)
    assert log.exists()
    content = log.read_text(encoding="utf-8")
    assert "block-secrets" in content
    assert "Read" in content
    assert ".env" in content


def test_audit_log_format(tmp_path):
    """Each line has all pipe-separated fields."""
    log = tmp_path / "audit.log"
    append_audit_log("command-guard", "Bash", "Blocked: rm -rf", "rm -rf /tmp", _path=log)
    line = log.read_text(encoding="utf-8").strip()
    parts = [p.strip() for p in line.split("|")]
    assert len(parts) == 5
    assert "hook=command-guard" in parts[1]
    assert "tool=Bash" in parts[2]
    assert "Blocked: rm -rf" in parts[3]
    assert "rm -rf /tmp" in parts[4]


def test_audit_log_payload_truncated(tmp_path):
    """Payloads longer than 120 chars are truncated in the log."""
    log = tmp_path / "audit.log"
    long_payload = "x" * 200
    append_audit_log("block-secrets", "Bash", "Blocked", long_payload, _path=log)
    content = log.read_text(encoding="utf-8")
    assert "x" * 121 not in content
    assert "x" * 120 in content


def test_audit_log_newlines_stripped_from_payload(tmp_path):
    """Newlines in payload are replaced with spaces so each event is one line."""
    log = tmp_path / "audit.log"
    append_audit_log("block-secrets", "Bash", "Blocked", "line1\nline2", _path=log)
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert "line1 line2" in lines[0]


def test_audit_log_oserror_is_silent():
    """OSError from audit log write must never crash the hook."""
    with patch("builtins.open", side_effect=OSError("disk full")):
        append_audit_log("block-secrets", "Read", "Blocked: .env", ".env")
