from __future__ import annotations

import sys
import types

from superinvestor_filings import notify


def _fake_notifications(toast, whatsapp):
    mod = types.ModuleType("notifications")
    mod.send_toast_notification = lambda *a, **k: toast.append((a, k))
    mod.send_whatsapp_notification = lambda *a, **k: whatsapp.append((a, k))
    return mod


def test_empty_list_is_a_noop():
    notify.send_digest([])  # must not raise, no notifications module needed


def test_grouped_whatsapp_body_contains_every_filing(monkeypatch):
    toast, whatsapp = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications(toast, whatsapp))

    notify.send_digest([
        {"filer_display": "Mohnish Pabrai / Dalal Street",
         "summary": "SC 13G on RAIN (5.2% of class) [5% cross]"},
        {"filer_display": "Mohnish Pabrai / Dalal Street",
         "summary": "Form 4 on AMR (sold 40,000 sh)"},
    ])
    assert len(toast) == 1
    assert len(whatsapp) == 1
    (body,), _ = whatsapp[0]
    assert body.startswith("Superinvestor filing:")
    assert "SC 13G on RAIN" in body
    assert "Form 4 on AMR" in body
    assert "2 new fast disclosure(s)" in body


def test_notifications_path_resolves_to_claude_scripts():
    from pathlib import Path

    p = Path(notify.__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
    assert p.name == "scripts"
    assert (p / "notifications.py").exists()
