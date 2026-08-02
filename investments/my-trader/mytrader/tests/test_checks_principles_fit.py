from __future__ import annotations

from mytrader.checks import CheckResult, principles_fit
from mytrader.market_data import TickerData

_OK = CheckResult(name="valuation", verdict="ok", detail="fine", data={"pe": 20.0})


def test_no_data_returns_unknown():
    result = principles_fit.check("X", None, [], None, None, None)
    assert result.verdict == "unknown"


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
            name="balance_sheet", verdict="flag", detail="bad",
            data={"debt_to_equity": 200.0, "current_ratio": 0.8},
        ),
        CheckResult(name="dividend", verdict="info", detail="No dividend history"),
    ]
    thesis = principles_fit._build_thesis(
        "UBER", other_checks, {"score": 54, "provisional": False}, -3.2, -6.3
    )
    assert "PE 17.5" in thesis
    assert "Debt/equity 200.0" in thesis
    assert "Current ratio 0.80" in thesis
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
