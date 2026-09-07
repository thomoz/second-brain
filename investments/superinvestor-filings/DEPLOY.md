# Superinvestor Filings Scanner — Deploy (EDGAR leg)

Systemd unit install is a manual step (`deploy.ps1` does not `sudo cp` unit files —
see MEMORY.md "systemd unit deploys often need manual sudo cp"). Run this after the
code is committed, pushed, and `deploy.ps1` has synced the VPS working tree.

One pasteable block (per MEMORY.md "Manual command chaining"):

```
ssh secondbrain@137.184.102.104
cd /home/secondbrain/second-brain && git pull && \
  sudo cp scripts/systemd/second-brain-superinvestor-edgar.service scripts/systemd/second-brain-superinvestor-edgar.timer /etc/systemd/system/ && \
  sudo systemctl daemon-reload && \
  sudo systemctl enable --now second-brain-superinvestor-edgar.timer && \
  cd investments && /home/secondbrain/second-brain/investments/.venv/bin/python -m uv sync && \
  cd superinvestor-filings && \
  /home/secondbrain/second-brain/investments/.venv/bin/python -m superinvestor_filings.main scan
```

The final `scan` is the first run: it seeds the seen-log silently with the last
30 days of filings and sends **no** WhatsApp alert — expect "0 new filing(s)
(first-run seed complete, no alerts)". Every run after that alerts only on
genuinely-new filings.

## Verify

```
systemctl status second-brain-superinvestor-edgar.timer
sudo systemctl start second-brain-superinvestor-edgar.service && tail -n 40 /home/secondbrain/second-brain/investments/superinvestor-filings/superinvestor_edgar_runs.log
cat /home/secondbrain/second-brain/investments/superinvestor-filings/superinvestor-filings-report.md
```

## Sanity-check the tracked CIKs (one-off, after first deploy)

The 6 Pabrai / Dalal Street CIKs in `superinvestor_filings/config.py` were resolved
2026-09-07 via EDGAR company search. A dead CIK is silently skipped, so confirm each
resolves:

```
/home/secondbrain/second-brain/investments/.venv/bin/python -m superinvestor_filings.main resolve-ciks
```

Compare the printed `(entity name, CIK)` pairs against the config list and prune /
add as needed (config edit only, no code change).
