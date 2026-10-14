# Volume-Spike + Record-Earnings Scanner — Deploy

One systemd timer, installed manually (`deploy.ps1` does not copy unit files). Run
this after the code is committed, pushed, and `deploy.ps1` has synced the VPS working
tree.

## Install block (one pasteable `&&` chain)

```
ssh secondbrain@137.184.102.104
cd /home/secondbrain/second-brain && git pull && \
  ~/.local/bin/uv sync --directory investments --all-packages --all-extras && \
  sudo cp scripts/systemd/second-brain-volume-earnings-scan.service scripts/systemd/second-brain-volume-earnings-scan.timer /etc/systemd/system/ && \
  sudo systemctl daemon-reload && \
  sudo systemctl enable --now second-brain-volume-earnings-scan.timer && \
  cd investments/volume-earnings-scanner && \
  ../.venv/bin/python -m volume_earnings_scanner.main scan
```

The final `scan` is the first real run. Unlike superinvestor-filings there is no
silent-seed window -- the first run scores slice 1/5 of the screened small/micro-cap
universe and **will** fire a WhatsApp "Volume/Earnings Scanner Alert" for any name
that trips a signal. That is expected and fine.

## Verify

```
systemctl list-timers 'second-brain-volume-earnings-scan*' --no-pager
sudo systemctl start second-brain-volume-earnings-scan.service && tail -n 40 /home/secondbrain/second-brain/investments/volume-earnings-scanner/volume_earnings_scan_runs.log
cat /home/secondbrain/second-brain/investments/volume-earnings-scanner/volume-earnings-candidates-pending-review.md
```

## Sanity-check the first real run

- No exceptions in the log; the report file exists even with zero candidates.
- A ticker currently held/watchlisted should never appear as a new candidate (it may
  still show up tagged `held`/`watchlist` if scored, depending on how the first run's
  rows look -- confirm against `investments/my-trader/holdings.md`/`watchlist.md`).
- No defense contractor (LMT, RTX, etc.) appears anywhere.
- Then decide whether to tune `VE_VOLUME_SPIKE_RATIO_THRESHOLD` (3.0) or the earnings
  quarter minimums, the same way Cash-Value Scan went 0.80 -> 0.50 after its first run.

## Finviz filter tokens + yfinance accessor (Phase 0 findings, review before relying on live data)

Live-verified 2026-10-14 (see `volume_earnings_scanner/config.py` and
`earnings_signal.py` module docstrings for the full detail):

- `cap_microunder,geo_usa` and `cap_small,geo_usa` both returned real, correctly
  cap-bucketed results (nano+micro under ~$300M; small ~$300M-$2B) -- no token
  correction needed, matching the filter-naming convention's implied boundaries.
- `Ticker.quarterly_income_stmt`'s `"Diluted EPS"` row is the chosen EPS accessor
  (newest-first, 5-6 quarters typical even for small/micro-caps, with occasional
  NaN gaps handled as missing-quarter rather than dropped positionally).

Re-verify the Finviz tokens with:

```
cd /home/secondbrain/second-brain/investments/volume-earnings-scanner
../.venv/bin/python -c "
from volume_earnings_scanner import universe
rows = universe.fetch_screened_universe() or []
print(len(rows)); [print(r) for r in rows[:10]]
"
```

## Not yet done (explicit follow-ups, not part of this build)

- `investments/TOOLS.md` doesn't have a row for this tool yet -- add one once the
  first few live runs look sane (per that file's own "update whenever a tool's
  schedule/command/output changes" instruction).
- `second-brain-ai-moat-scan.timer`'s pre-existing absence from `deploy.ps1`'s
  `$TIMERS` list was noticed while building this plan but is **out of scope** here --
  flagged to Shaun separately, not silently fixed in this PR.
