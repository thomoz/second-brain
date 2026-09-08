# Superinvestor Filings Scanner — Deploy

Two systemd timers, installed manually (`deploy.ps1` does not copy unit files — see
MEMORY.md "systemd unit deploys often need manual sudo cp"). Run this after the code
is committed, pushed, and `deploy.ps1` has synced the VPS working tree.

## EDGAR leg (US) — already live as of 2026-09-08

`second-brain-superinvestor-edgar.timer` (02:35 UTC) is installed and running. If
re-installing, the block is the same shape as the SAST block below with
`superinvestor-edgar` in place of `superinvestor-sast` and no leg flag change needed
(the service already runs `scan --edgar-only`).

## SAST leg (India / BSE) — install block

```
ssh secondbrain@137.184.102.104
cd /home/secondbrain/second-brain && git pull && \
  ~/.local/bin/uv sync --directory investments --all-packages && \
  sudo cp scripts/systemd/second-brain-superinvestor-sast.service scripts/systemd/second-brain-superinvestor-sast.timer /etc/systemd/system/ && \
  sudo cp scripts/systemd/second-brain-superinvestor-edgar.service /etc/systemd/system/ && \
  sudo systemctl daemon-reload && \
  sudo systemctl enable --now second-brain-superinvestor-sast.timer && \
  cd investments/superinvestor-filings && \
  ../.venv/bin/python -m superinvestor_filings.main scan --india-only
```

(The second `sudo cp` refreshes the EDGAR `.service`, which changed to
`scan --edgar-only` so it no longer double-runs the India leg.)

The final `scan --india-only` is the SAST leg's first run: it seeds the seen-log
silently with the last ~28 days of BSE SAST disclosures and sends **no** WhatsApp
alert — expect "0 new filing(s) (first-run seed complete, no alerts)". Every run
after that alerts only on genuinely-new disclosures that name-match a tracked
investor's `india_aliases`.

## Verify

```
systemctl list-timers 'second-brain-superinvestor-*' --no-pager
sudo systemctl start second-brain-superinvestor-sast.service && tail -n 40 /home/secondbrain/second-brain/investments/superinvestor-filings/superinvestor_sast_runs.log
cat /home/secondbrain/second-brain/investments/superinvestor-filings/superinvestor-filings-report.md
```

## Verify the india_aliases (one-off, after first SAST run)

`india_aliases` in `config.py` is `["pabrai", "dalal street", "dhandho"]` — a guess.
Confirm Pabrai's fund entities actually file on BSE under names that contain one of
these substrings by eyeballing a month of real acquirer names:

```
cd /home/secondbrain/second-brain/investments/superinvestor-filings
../.venv/bin/python -c "
from superinvestor_filings import sast_monitor as m
from datetime import date, timedelta
prev=(date.today()-timedelta(days=28)).strftime('%Y%m%d'); to=date.today().strftime('%Y%m%d')
rows=m.fetch_sast_disclosures(prev,to) or []
seen=set()
for r in rows:
    if m._reg_label(r.get('SUBCATNAME','')):
        a=m._acquirer_name(r.get('HEADLINE',''), r.get('NEWSSUB',''))
        if a: seen.add(a)
for a in sorted(seen): print(a)
"
```

Grep that list for Pabrai's entities and adjust `india_aliases` (config edit only).

## Sanity-check the tracked CIKs (EDGAR) — done 2026-09-08

All 6 confirmed valid against the live SEC submissions API. `resolve-ciks` does a
broad full-text search (returns subject companies too) so it is not a validity test
— `fetch_filing_index(cik)` returning non-null is.
