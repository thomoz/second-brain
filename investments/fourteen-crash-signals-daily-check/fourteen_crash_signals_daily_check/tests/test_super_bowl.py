from __future__ import annotations

from datetime import date

from fourteen_crash_signals_daily_check import config, super_bowl


class _FixedDate(date):
    _today: date

    @classmethod
    def today(cls):
        return cls._today


def _freeze(monkeypatch, today: date) -> None:
    fixed = type("_FixedDate", (_FixedDate,), {"_today": today})
    monkeypatch.setattr(super_bowl, "date", fixed)


def test_check_super_bowl_signal_unknown_with_days_left_when_target_in_future(monkeypatch):
    monkeypatch.setattr(config, "SIGNALS_NEXT_SUPER_BOWL_DATE", date(2027, 2, 14))
    _freeze(monkeypatch, date(2027, 1, 1))
    result = super_bowl.check_super_bowl_signal()
    assert result.verdict == "unknown"
    assert result.data["days_left"] == 44


def test_check_super_bowl_signal_flags_when_target_is_today(monkeypatch):
    monkeypatch.setattr(config, "SIGNALS_NEXT_SUPER_BOWL_DATE", date(2027, 2, 14))
    _freeze(monkeypatch, date(2027, 2, 14))
    result = super_bowl.check_super_bowl_signal()
    assert result.verdict == "flag"


def test_check_super_bowl_signal_flags_when_target_is_in_past(monkeypatch):
    monkeypatch.setattr(config, "SIGNALS_NEXT_SUPER_BOWL_DATE", date(2027, 2, 14))
    _freeze(monkeypatch, date(2027, 3, 1))
    result = super_bowl.check_super_bowl_signal()
    assert result.verdict == "flag"
