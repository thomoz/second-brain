from __future__ import annotations

from fourteen_crash_signals_daily_check import debt_issuance


def test_flags_with_clear_divergence(monkeypatch):
    monkeypatch.setattr(debt_issuance.sec_filings, "get_cik", lambda conn, ticker: "1341439")
    # baseline_rate = baseline_count / (730/180) = baseline_count / 4.0556
    # want trailing_count >= baseline_rate * 2.0
    counts = iter([10, 4])  # baseline_rate ~= 0.986, trailing=10 >> 2x
    monkeypatch.setattr(debt_issuance.sec_filings, "edgar_fulltext_search_count", lambda *a, **k: next(counts))
    result = debt_issuance._check_one_ticker(None, "ORCL")
    assert result.verdict == "flag"


def test_stays_ok_when_below_ratio(monkeypatch):
    monkeypatch.setattr(debt_issuance.sec_filings, "get_cik", lambda conn, ticker: "1341439")
    counts = iter([1, 20])  # baseline_rate ~= 4.93, trailing=1, well below 2x
    monkeypatch.setattr(debt_issuance.sec_filings, "edgar_fulltext_search_count", lambda *a, **k: next(counts))
    result = debt_issuance._check_one_ticker(None, "ORCL")
    assert result.verdict == "ok"


def test_ok_no_divide_by_zero_when_baseline_count_zero(monkeypatch):
    monkeypatch.setattr(debt_issuance.sec_filings, "get_cik", lambda conn, ticker: "1341439")
    counts = iter([1, 0])  # baseline_count=0 -> baseline_rate=0.0
    monkeypatch.setattr(debt_issuance.sec_filings, "edgar_fulltext_search_count", lambda *a, **k: next(counts))
    result = debt_issuance._check_one_ticker(None, "ORCL")
    assert result.verdict == "ok"
    assert result.data["baseline_rate"] == 0.0


def test_ticker_skipped_when_get_cik_returns_none(monkeypatch):
    monkeypatch.setattr(debt_issuance.sec_filings, "get_cik", lambda conn, ticker: None)
    result = debt_issuance._check_one_ticker(None, "ORCL")
    assert result is None


def test_ticker_skipped_when_search_count_returns_none(monkeypatch):
    monkeypatch.setattr(debt_issuance.sec_filings, "get_cik", lambda conn, ticker: "1341439")
    monkeypatch.setattr(debt_issuance.sec_filings, "edgar_fulltext_search_count", lambda *a, **k: None)
    result = debt_issuance._check_one_ticker(None, "ORCL")
    assert result is None


def test_check_debt_issuance_empty_watchlist_returns_empty_list():
    assert debt_issuance.check_debt_issuance(None, []) == []
