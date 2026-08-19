from __future__ import annotations

from fourteen_crash_signals_daily_check import config, db, retail_leverage

_FIXTURE_TEXT = r'...\"name\":\"EQUITY PUT/CALL RATIO\",\"value\":\"0.65\"...'


def test_putcall_regex_extracts_from_escaped_json_fixture():
    match = retail_leverage._PUTCALL_RE.search(_FIXTURE_TEXT)
    assert match is not None
    assert match.group(1) == "0.65"


def test_unknown_when_fetch_returns_none(db_conn, monkeypatch):
    monkeypatch.setattr(retail_leverage, "_fetch_putcall_ratio_live", lambda: None)
    result = retail_leverage.check_retail_leverage(db_conn)
    assert result.verdict == "unknown"


def test_unknown_accumulating_baseline_with_correct_day_count(db_conn, monkeypatch):
    monkeypatch.setattr(retail_leverage, "_fetch_putcall_ratio_live", lambda: 0.65)
    for i in range(5):
        db_conn.execute(
            "INSERT INTO signals_putcall_history (observed_at, ratio) VALUES (?, ?)",
            (f"2026-07-{i + 1:02d}", 0.6 + i * 0.01),
        )
    db_conn.commit()
    result = retail_leverage.check_retail_leverage(db_conn)
    assert result.verdict == "unknown"
    assert "accumulating baseline" in result.detail
    assert "day 6 of" in result.detail


def test_record_putcall_ratio_called_even_on_accumulating_baseline_path(db_conn, monkeypatch):
    monkeypatch.setattr(retail_leverage, "_fetch_putcall_ratio_live", lambda: 0.65)
    retail_leverage.check_retail_leverage(db_conn)
    rows = db.get_putcall_history(db_conn, since_days=90)
    assert len(rows) == 1
    assert rows[0]["ratio"] == 0.65


def _seed_history(db_conn, values: list[float]):
    for i, v in enumerate(values):
        db_conn.execute(
            "INSERT INTO signals_putcall_history (observed_at, ratio) VALUES (?, ?)",
            (f"2026-06-{i + 1:02d}", v),
        )
    db_conn.commit()


def test_flags_when_zscore_at_or_below_threshold(db_conn, monkeypatch):
    values = [0.9 + (i % 3) * 0.01 for i in range(config.SIGNALS_PUTCALL_MIN_HISTORY_DAYS)]
    _seed_history(db_conn, values)
    monkeypatch.setattr(retail_leverage, "_fetch_putcall_ratio_live", lambda: 0.3)  # far below mean
    result = retail_leverage.check_retail_leverage(db_conn)
    assert result.verdict == "flag"


def test_stays_ok_when_zscore_above_threshold(db_conn, monkeypatch):
    values = [0.9 + (i % 3) * 0.01 for i in range(config.SIGNALS_PUTCALL_MIN_HISTORY_DAYS)]
    _seed_history(db_conn, values)
    monkeypatch.setattr(retail_leverage, "_fetch_putcall_ratio_live", lambda: 0.91)
    result = retail_leverage.check_retail_leverage(db_conn)
    assert result.verdict == "ok"


def test_never_flags_when_stdev_zero(db_conn, monkeypatch):
    values = [0.65] * config.SIGNALS_PUTCALL_MIN_HISTORY_DAYS
    _seed_history(db_conn, values)
    monkeypatch.setattr(retail_leverage, "_fetch_putcall_ratio_live", lambda: 0.1)  # very different, but stdev=0
    result = retail_leverage.check_retail_leverage(db_conn)
    assert result.verdict == "ok"
