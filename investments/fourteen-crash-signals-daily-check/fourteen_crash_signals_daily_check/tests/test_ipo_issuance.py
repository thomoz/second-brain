from __future__ import annotations

from datetime import date

from fourteen_crash_signals_daily_check import ipo_issuance


def _make_fake_count(current_by_form: dict[str, int | None], prior_by_form: dict[str, int | None]):
    """side-effect function keyed on forms + whether startdt is in the current or
    prior-year window (roughly one year apart)."""
    today = date.today()

    def _fake(forms, startdt=None, enddt=None):
        if startdt is not None and (today - startdt).days > 200:
            return prior_by_form.get(forms)
        return current_by_form.get(forms)

    return _fake


def test_flags_when_either_subsignal_ratio_meets_threshold(monkeypatch):
    fake = _make_fake_count({"S-1": 100, "424B4": 5}, {"S-1": 50, "424B4": 5})  # S-1 ratio 2.0x
    monkeypatch.setattr(ipo_issuance.sec_filings, "edgar_fulltext_search_count", fake)
    result = ipo_issuance.check_ipo_issuance()
    assert result.verdict == "flag"


def test_stays_ok_when_neither_subsignal_flags(monkeypatch):
    fake = _make_fake_count({"S-1": 55, "424B4": 5}, {"S-1": 50, "424B4": 5})
    monkeypatch.setattr(ipo_issuance.sec_filings, "edgar_fulltext_search_count", fake)
    result = ipo_issuance.check_ipo_issuance()
    assert result.verdict == "ok"


def test_unknown_only_when_both_subsignals_current_window_returns_none(monkeypatch):
    fake = _make_fake_count({"S-1": None, "424B4": None}, {"S-1": 50, "424B4": 5})
    monkeypatch.setattr(ipo_issuance.sec_filings, "edgar_fulltext_search_count", fake)
    result = ipo_issuance.check_ipo_issuance()
    assert result.verdict == "unknown"


def test_one_subsignal_degrades_when_only_prior_window_returns_none(monkeypatch):
    fake = _make_fake_count({"S-1": 55, "424B4": 5}, {"S-1": None, "424B4": 5})
    monkeypatch.setattr(ipo_issuance.sec_filings, "edgar_fulltext_search_count", fake)
    result = ipo_issuance.check_ipo_issuance()
    assert result.verdict in ("ok", "flag")
    assert "no prior-year comparison available" in result.detail


def test_divide_by_zero_guard_when_prior_is_zero(monkeypatch):
    fake = _make_fake_count({"S-1": 5, "424B4": 5}, {"S-1": 0, "424B4": 5})
    monkeypatch.setattr(ipo_issuance.sec_filings, "edgar_fulltext_search_count", fake)
    result = ipo_issuance.check_ipo_issuance()
    assert result.verdict in ("ok", "flag")  # no crash
