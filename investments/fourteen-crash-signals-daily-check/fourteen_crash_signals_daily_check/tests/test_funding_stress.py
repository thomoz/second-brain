from __future__ import annotations

from datetime import date, timedelta

from fourteen_crash_signals_daily_check import config, funding_stress


def _series(values: list[float], start: date) -> list[tuple[date, float]]:
    return [(start + timedelta(days=i), v) for i, v in enumerate(values)]


def _fake_fred(series_map: dict[str, list[tuple[date, float]] | None]):
    def _fred_series_range(series_id, start, end):
        return series_map.get(series_id)

    return _fred_series_range


def test_flags_when_spread_zscore_at_or_above_threshold(monkeypatch):
    start = date.today() - timedelta(days=10)
    cp = _series([1.0] * 9 + [10.0], start)  # last value is a big outlier -> high z-score
    tbill = _series([0.0] * 10, start)
    monkeypatch.setattr(
        funding_stress, "fred_series_range",
        _fake_fred({"DCPN3M": cp, "DTB3": tbill, "STLFSI4": None, "NFCI": None}),
    )
    result = funding_stress.check_funding_stress()
    assert result.verdict == "flag"
    assert result.data["spread_zscore"] >= config.SIGNALS_FUNDING_SPREAD_FLAG_ZSCORE


def test_stays_ok_when_spread_zscore_below_threshold_and_no_index_elevated(monkeypatch):
    start = date.today() - timedelta(days=10)
    cp = _series([1.0] * 10, start)  # flat -> stdev 0 -> None -> unknown, use slight variation instead
    cp = _series([1.0, 1.1, 1.0, 1.1, 1.0, 1.1, 1.0, 1.1, 1.0, 1.05], start)
    tbill = _series([0.0] * 10, start)
    monkeypatch.setattr(
        funding_stress, "fred_series_range",
        _fake_fred({"DCPN3M": cp, "DTB3": tbill, "STLFSI4": None, "NFCI": None}),
    )
    result = funding_stress.check_funding_stress()
    assert result.verdict == "ok"


def test_flags_via_corroborating_index_when_spread_itself_is_ok(monkeypatch):
    start = date.today() - timedelta(days=10)
    cp = _series([1.0, 1.1, 1.0, 1.1, 1.0, 1.1, 1.0, 1.1, 1.0, 1.05], start)
    tbill = _series([0.0] * 10, start)
    stlfsi = _series([0.0] * 9 + [10.0], start)  # outlier -> high z-score, crosses threshold
    monkeypatch.setattr(
        funding_stress, "fred_series_range",
        _fake_fred({"DCPN3M": cp, "DTB3": tbill, "STLFSI4": stlfsi, "NFCI": None}),
    )
    result = funding_stress.check_funding_stress()
    assert result.verdict == "flag"
    assert "STLFSI4" in result.detail


def test_unknown_when_spread_series_unavailable(monkeypatch):
    monkeypatch.setattr(
        funding_stress, "fred_series_range",
        _fake_fred({"DCPN3M": None, "DTB3": None, "STLFSI4": None, "NFCI": None}),
    )
    result = funding_stress.check_funding_stress()
    assert result.verdict == "unknown"


def test_date_misalignment_between_cp_and_tbill_history_drops_unmatched_dates(monkeypatch):
    start = date.today() - timedelta(days=10)
    cp = _series([1.0, 1.1, 1.0, 1.1, 1.0, 1.1, 1.0, 1.1, 1.0, 1.05], start)
    tbill_short = _series([0.0] * 9, start)  # missing the last date cp has
    monkeypatch.setattr(
        funding_stress, "fred_series_range",
        _fake_fred({"DCPN3M": cp, "DTB3": tbill_short, "STLFSI4": None, "NFCI": None}),
    )
    result = funding_stress.check_funding_stress()
    assert result.verdict in ("ok", "flag")  # no crash -- degrades gracefully
