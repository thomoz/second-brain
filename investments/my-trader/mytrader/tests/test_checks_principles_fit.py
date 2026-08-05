from __future__ import annotations

from mytrader.checks import CheckResult, principles_fit
from mytrader.market_data import TickerData

_OK = CheckResult(name="valuation", verdict="ok", detail="fine", data={"pe": 20.0})


def test_no_data_returns_unknown():
    result = principles_fit.check("X", None, [], None, None, None)
    assert result.verdict == "unknown"


def test_etf_skips_principles_grading(monkeypatch, tmp_path):
    """The 9 frameworks (Buffett/Graham/etc.) grade individual operating businesses,
    not diversified funds -- confirmed live 2026-08-04 (IVV/SPY both landed ~35/100
    despite being exactly what they're supposed to be). Must skip before ever calling
    score_thesis_against_principle, not just score low."""
    (tmp_path / "buffett.md").write_text("Buffett criteria", encoding="utf-8")
    monkeypatch.setattr("scripts.config.PRINCIPLES_DIR", tmp_path)
    calls = []
    monkeypatch.setattr(
        "scripts.score.score_thesis_against_principle",
        lambda *a, **k: calls.append(a) or (99, "should not be called"),
    )
    data = TickerData(ticker="IVV", info={"quoteType": "ETF"}, dividends=None)
    result = principles_fit.check("IVV", data, [_OK], None, None, None)
    assert result.verdict == "unknown"
    assert "Skipped for ETFs" in result.detail
    assert calls == []


def test_no_principle_files_returns_unknown(monkeypatch, tmp_path):
    monkeypatch.setattr("scripts.config.PRINCIPLES_DIR", tmp_path / "does-not-exist")
    data = TickerData(ticker="X", info={}, dividends=None)
    result = principles_fit.check("X", data, [_OK], None, None, None)
    assert result.verdict == "unknown"


def test_averages_scores_across_principle_files(monkeypatch, tmp_path):
    (tmp_path / "buffett.md").write_text("Buffett criteria", encoding="utf-8")
    (tmp_path / "graham.md").write_text("Graham criteria", encoding="utf-8")
    monkeypatch.setattr("scripts.config.PRINCIPLES_DIR", tmp_path)

    calls = []

    def _fake_score(thesis, principle_name, file_content):
        calls.append((principle_name, thesis))
        return (80, "sounds good") if principle_name == "buffett" else (40, "meh")

    monkeypatch.setattr("scripts.score.score_thesis_against_principle", _fake_score)

    data = TickerData(ticker="X", info={}, dividends=None)
    result = principles_fit.check("X", data, [_OK], None, 5.0, 10.0)

    assert result.data["average"] == 60.0
    assert result.verdict == "info"  # 60 < OPPORTUNITY_SCORE_FLAG (70)
    assert len(calls) == 2
    assert calls[0][1] == calls[1][1]  # same thesis passed to every principle file


def test_high_average_flags_interesting(monkeypatch, tmp_path):
    (tmp_path / "buffett.md").write_text("Buffett criteria", encoding="utf-8")
    monkeypatch.setattr("scripts.config.PRINCIPLES_DIR", tmp_path)
    monkeypatch.setattr(
        "scripts.score.score_thesis_against_principle", lambda *a, **k: (85, "great fit")
    )

    data = TickerData(ticker="X", info={}, dividends=None)
    result = principles_fit.check("X", data, [_OK], None, None, None)

    assert result.verdict == "interesting"


def test_thesis_includes_check_data_and_flags():
    other_checks = [
        CheckResult(name="valuation", verdict="ok", detail="fine", data={"pe": 17.5}),
        CheckResult(
            name="balance_sheet", verdict="flag",
            detail="debt/equity 200.0 (0/10 -- poor); current ratio 0.80 (0/10 -- poor)",
            data={"debt_to_equity": 200.0, "current_ratio": 0.8},
        ),
        CheckResult(name="dividend", verdict="info", detail="No dividend history"),
    ]
    thesis = principles_fit._build_thesis(
        "UBER", other_checks, {"score": 54, "provisional": False}, -3.2, -6.3
    )
    assert "PE 17.5" in thesis
    assert "Debt-to-equity: 2.00x (debt is 200% of equity; this tool flags at or above 1.5x)." in thesis
    assert "Current ratio 0.80" in thesis
    assert "Balance sheet check flagged this run: debt/equity 200.0 (0/10 -- poor); current ratio 0.80 (0/10 -- poor)" in thesis
    assert "No dividend history" in thesis
    assert "-3.2% over 1 month" in thesis
    assert "-6.3% over 3 months" in thesis
    assert "54/100" in thesis
    assert "balance_sheet" in thesis


def test_thesis_notes_no_active_flags_when_clean():
    other_checks = [CheckResult(name="valuation", verdict="ok", detail="fine", data={"pe": 17.5})]
    thesis = principles_fit._build_thesis("KO", other_checks, None, None, None)
    assert "No active risk flags this run" in thesis


def test_thesis_omits_macro_section_when_no_snapshot():
    other_checks = [CheckResult(name="valuation", verdict="ok", detail="fine", data={"pe": 17.5})]
    thesis = principles_fit._build_thesis("KO", other_checks, None, None, None, macro_rows=None)
    assert "Macro regime" not in thesis


def test_thesis_includes_macro_snapshot_when_provided():
    other_checks = [CheckResult(name="valuation", verdict="ok", detail="fine", data={"pe": 17.5})]
    macro_rows = [
        {"name": "recession_signal", "verdict": "flag", "detail": "10Y-3M curve inverted",
         "computed_at": "2026-08-01T21:30:00+00:00"},
        {"name": "credit_spreads", "verdict": "ok", "detail": "HY OAS 3.2%",
         "computed_at": "2026-08-01T21:30:00+00:00"},
    ]
    thesis = principles_fit._build_thesis("KO", other_checks, None, None, None, macro_rows=macro_rows)
    assert "Macro regime as of 2026-08-01" in thesis
    assert "recession_signal [flag] 10Y-3M curve inverted" in thesis
    assert "credit_spreads [ok] HY OAS 3.2%" in thesis


def test_check_reads_macro_snapshot_from_db_conn(db_conn, monkeypatch, tmp_path):
    from mytrader import db as mytrader_db

    (tmp_path / "buffett.md").write_text("Buffett criteria", encoding="utf-8")
    monkeypatch.setattr("scripts.config.PRINCIPLES_DIR", tmp_path)

    captured_thesis = {}

    def _fake_score(thesis, principle_name, file_content):
        captured_thesis["value"] = thesis
        return (80, "great fit")

    monkeypatch.setattr("scripts.score.score_thesis_against_principle", _fake_score)
    mytrader_db.upsert_macro_snapshot(
        db_conn, [CheckResult(name="move_index", verdict="ok", detail="MOVE at 90.0")]
    )

    data = TickerData(ticker="KO", info={}, dividends=None)
    result = principles_fit.check("KO", data, [_OK], None, None, None, db_conn)

    assert "Macro regime" in captured_thesis["value"]
    assert "move_index [ok] MOVE at 90.0" in captured_thesis["value"]
    assert result.data["macro_snapshot_as_of"] is not None


def test_check_macro_snapshot_as_of_none_without_conn(monkeypatch, tmp_path):
    (tmp_path / "buffett.md").write_text("Buffett criteria", encoding="utf-8")
    monkeypatch.setattr("scripts.config.PRINCIPLES_DIR", tmp_path)
    monkeypatch.setattr("scripts.score.score_thesis_against_principle", lambda *a, **k: (80, "fine"))

    data = TickerData(ticker="KO", info={}, dividends=None)
    result = principles_fit.check("KO", data, [_OK], None, None, None)  # no conn passed

    assert "Macro regime" not in result.data["thesis"]
    assert result.data.get("macro_snapshot_as_of") is None


def test_thesis_omits_filing_section_when_none():
    other_checks = [CheckResult(name="valuation", verdict="ok", detail="fine", data={"pe": 17.5})]
    thesis = principles_fit._build_thesis("KO", other_checks, None, None, None, filing_summaries=None)
    assert "filing highlights" not in thesis


def test_thesis_includes_filing_summaries_when_provided():
    other_checks = [CheckResult(name="valuation", verdict="ok", detail="fine", data={"pe": 17.5})]
    thesis = principles_fit._build_thesis(
        "KO", other_checks, None, None, None,
        filing_summaries={"10-K": "Strong moat, rising margins."},
    )
    assert "10-K filing highlights" in thesis
    assert "Strong moat, rising margins." in thesis


def test_check_calls_filing_lookup_when_conn_given(db_conn, monkeypatch, tmp_path):
    (tmp_path / "buffett.md").write_text("Buffett criteria", encoding="utf-8")
    monkeypatch.setattr("scripts.config.PRINCIPLES_DIR", tmp_path)
    monkeypatch.setattr("scripts.score.score_thesis_against_principle", lambda *a, **k: (80, "fine"))

    calls = []

    def _fake_lookup(ticker, conn):
        calls.append(ticker)
        return {"10-K": "Solid fundamentals."}

    monkeypatch.setattr("mytrader.checks.principles_fit.sec_filings.get_filing_summaries_for_ticker", _fake_lookup)

    data = TickerData(ticker="KO", info={}, dividends=None)
    result = principles_fit.check("KO", data, [_OK], None, None, None, db_conn)

    assert calls == ["KO"]
    assert result.data["filing_types_used"] == ["10-K"]


def test_check_skips_filing_lookup_without_conn(monkeypatch, tmp_path):
    (tmp_path / "buffett.md").write_text("Buffett criteria", encoding="utf-8")
    monkeypatch.setattr("scripts.config.PRINCIPLES_DIR", tmp_path)
    monkeypatch.setattr("scripts.score.score_thesis_against_principle", lambda *a, **k: (80, "fine"))

    def _raise_if_called(ticker, conn):
        raise AssertionError("filing lookup should not be called when conn is None")

    monkeypatch.setattr("mytrader.checks.principles_fit.sec_filings.get_filing_summaries_for_ticker", _raise_if_called)

    data = TickerData(ticker="KO", info={}, dividends=None)
    result = principles_fit.check("KO", data, [_OK], None, None, None)  # no conn passed

    assert result.data["filing_types_used"] == []
