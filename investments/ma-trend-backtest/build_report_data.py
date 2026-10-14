"""Trim results.json down to exactly what the artifact report needs, as one JSON blob."""

import json
from pathlib import Path

HERE = Path(__file__).parent
d = json.load(open(HERE / "results" / "results.json"))

HEADLINE = str(d["headline_ma"])
ma200 = d["ma_results"][HEADLINE]


def metrics_of(block, cost_label):
    return block["costs"][cost_label]["metrics"]


def curve_of(block, cost_label):
    c = block["costs"][cost_label]["equity_curve_monthly"]
    return c["dates"], c["equity"]


bh = d["buy_and_hold"]
lc0 = ma200["variants"]["long_cash_0pct"]
lct = ma200["variants"]["long_cash_tbill"]
ls = ma200["variants"]["long_short"]

dates, bh_eq = curve_of(bh, "after_costs")
_, lc0_eq = curve_of(lc0, "after_costs")
_, lct_eq = curve_of(lct, "after_costs")
_, ls_eq = curve_of(ls, "after_costs")

out = {
    "meta": {
        "generated_at": d["generated_at"],
        "data_start": d["data_range"]["start"],
        "data_end": d["data_range"]["end"],
        "initial_capital": d["assumptions"]["initial_capital"],
        "assumptions": d["assumptions"],
        "headline_ma": d["headline_ma"],
        "ma_lengths": d["ma_lengths_tested"],
    },
    "headline": {
        "equity_curves": {
            "dates": dates,
            "buy_hold": bh_eq,
            "long_cash_0": lc0_eq,
            "long_cash_tbill": lct_eq,
            "long_short": ls_eq,
        },
        "comparison": {
            "buy_hold": {"before": metrics_of(bh, "before_costs"), "after": metrics_of(bh, "after_costs")},
            "long_cash_0": {"before": metrics_of(lc0, "before_costs"), "after": metrics_of(lc0, "after_costs")},
            "long_cash_tbill": {"before": metrics_of(lct, "before_costs"), "after": metrics_of(lct, "after_costs")},
            "long_short": {"before": metrics_of(ls, "before_costs"), "after": metrics_of(ls, "after_costs")},
        },
        "year_by_year": {
            "buy_hold": bh["year_by_year"],
            "long_cash_0": lc0["year_by_year"],
            "long_cash_tbill": lct["year_by_year"],
            "long_short": ls["year_by_year"],
        },
        "bear_markets": {
            name: {
                "buy_hold": {k: v for k, v in bh["bear_markets"][name].items()},
                "long_cash": {k: v for k, v in lct["bear_markets"][name].items()},
                "long_short": {k: v for k, v in ls["bear_markets"][name].items()},
            }
            for name in bh["bear_markets"]
        },
        "trades": {
            "long_cash": lct["trades"],
            "long_short": ls["trades"],
        },
        "init_rules": {
            "long_cash": lct["init_rule"],
            "long_short": ls["init_rule"],
        },
        "sub_period_cagr": {
            "buy_hold": bh["sub_period_cagr"],
            "long_cash_tbill": lct["sub_period_cagr"],
            "long_short": ls["sub_period_cagr"],
        },
    },
    "ma_sweep": {
        "buy_hold_after": metrics_of(bh, "after_costs"),
        "rows": {
            str(ma): {
                "long_cash_tbill": {
                    "after": metrics_of(d["ma_results"][str(ma)]["variants"]["long_cash_tbill"], "after_costs"),
                    "before": metrics_of(d["ma_results"][str(ma)]["variants"]["long_cash_tbill"], "before_costs"),
                    "sub_period": d["ma_results"][str(ma)]["variants"]["long_cash_tbill"]["sub_period_cagr"],
                },
                "long_short": {
                    "after": metrics_of(d["ma_results"][str(ma)]["variants"]["long_short"], "after_costs"),
                    "before": metrics_of(d["ma_results"][str(ma)]["variants"]["long_short"], "before_costs"),
                    "sub_period": d["ma_results"][str(ma)]["variants"]["long_short"]["sub_period_cagr"],
                },
            }
            for ma in d["ma_lengths_tested"]
        },
    },
    "bear_market_defs": d["bear_markets"],
}

with open(HERE / "results" / "report_data.json", "w") as f:
    json.dump(out, f)

print("Wrote", HERE / "results" / "report_data.json")
print("Size (KB):", (HERE / "results" / "report_data.json").stat().st_size / 1024)
