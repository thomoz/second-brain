# AI-Resistant Moat Scanner — Deploy

One systemd timer, installed manually (`deploy.ps1` does not copy unit files). Run
this after the code is committed, pushed, and `deploy.ps1` has synced the VPS working
tree.

## Install block (one pasteable `&&` chain)

```
ssh secondbrain@137.184.102.104
cd /home/secondbrain/second-brain && git pull && \
  ~/.local/bin/uv sync --directory investments --all-packages && \
  sudo cp scripts/systemd/second-brain-ai-moat-scan.service scripts/systemd/second-brain-ai-moat-scan.timer /etc/systemd/system/ && \
  sudo systemctl daemon-reload && \
  sudo systemctl enable --now second-brain-ai-moat-scan.timer && \
  cd investments/ai-resistant-moat-scanner && \
  ../.venv/bin/python -m ai_resistant_moat_scanner.main scan
```

The final `scan` is the first real run. There is **no** silent-seed / alert-suppression
window here (unlike superinvestor-filings) — the first run does a full universe slice
plus all 30 seed names and **will** fire a WhatsApp "AI-Resistant Moat Alert" for any
seed name that scores ≥ 80. That is expected and fine.

## Verify

```
systemctl list-timers 'second-brain-ai-moat-scan*' --no-pager
sudo systemctl start second-brain-ai-moat-scan.service && tail -n 40 /home/secondbrain/second-brain/investments/ai-resistant-moat-scanner/moat_scan_runs.log
cat /home/secondbrain/second-brain/investments/ai-resistant-moat-scanner/moat-scan-report.md
cat /home/secondbrain/second-brain/investments/ai-resistant-moat-scanner/moat-candidates-pending-review.md
```

## Sanity-check the first real run

- Seed names (CRM, NOW, INTU, VEEV, TYL…) should land high (moat ~75–95).
- A thin point-tool should land low.
- Theses should quote real 10-K language.
- No defense contractor (LDOS, CACI) appears; PLTR/BA appear only if screened, tagged `REVIEW:`.
- Then decide whether to loosen `MOAT_STAGE_THRESHOLD` (80 → lower) the same way the
  cash-value scanner went 0.80 → 0.50 after its first run.

## Finviz filter tokens

The five `MOAT_FINVIZ_SECTOR_SCREENS` strings were verified live during the build
(`cap_midover,fa_grossmargin_o60,geo_usa,sh_avgvol_o100,sec_<sector>` — all returned
non-empty, industry labels matched). Finviz renames tokens occasionally; a wrong
token just yields a smaller/empty screened universe and the seed list still carries
the scan. Re-verify with:

```
cd /home/secondbrain/second-brain/investments/ai-resistant-moat-scanner
../.venv/bin/python -c "
from ai_resistant_moat_scanner import universe
rows = universe.fetch_screened_universe() or []
print(len(rows)); [print(r) for r in rows[:10]]
"
```
