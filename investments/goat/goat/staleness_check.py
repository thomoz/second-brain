"""Cross-package report staleness check -- runs as part of the daily Goat Monitor
digest (goat-monitor.timer is the first VPS investments job each morning, 21:35 UTC
/ 07:35 AEST, and already has a WhatsApp channel Shaun reads daily) since a
dedicated timer/report for this alone would be one more thing to independently go
stale. Path-only, no cross-package imports -- goat only depends on my-trader (see
pyproject.toml), so this deliberately does NOT import superinvestor_filings /
ai_resistant_moat_scanner / fourteen_crash_signals_daily_check's own config
modules just to get their report paths; those paths are stable and already
exhaustively documented in investments/TOOLS.md, so they're inlined below instead
of adding three new workspace dependencies to goat for this alone.

Added 2026-09-22 after a real ~30-hour outage (VPS's vault-sync git push silently
failing every cycle -- see run_vault_sync.sh's own stash-wrap fix for the root
cause) went undetected until Shaun happened to notice a stale report by eye. This
check does not fix that failure mode -- it makes the NEXT one loud instead of
silent."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

from . import config

INVESTMENTS_DIR = config.GOAT_DIR.parent  # goat/goat/config.py -> investments/goat -> investments/


class WatchedReport(NamedTuple):
    path: Path
    max_age_days: int
    label: str


# (path, max staleness in days before flagging, human label). max_age_days is set
# generously above each report's own daily-timer cadence (2 days, not 1) so a
# single day's ordinary timing jitter or a one-off transient scan failure never
# fires this -- only a report that's genuinely missed at least one full cycle.
WATCHED_REPORTS: tuple[WatchedReport, ...] = (
    WatchedReport(INVESTMENTS_DIR / "goat" / "goat-report.md", 2, "Goat Monitor"),
    WatchedReport(INVESTMENTS_DIR / "goat" / "sector-ranking.md", 2, "Goat sector rotation"),
    WatchedReport(INVESTMENTS_DIR / "goat" / "industry-ranking.md", 2, "Goat industry rotation"),
    WatchedReport(INVESTMENTS_DIR / "goat" / "heartbeat-candidates-pending-review.md", 2, "Goat heartbeat scan"),
    WatchedReport(INVESTMENTS_DIR / "goat" / "dma-breakout-candidates-pending-review.md", 2, "Goat DMA breakout scan"),
    WatchedReport(INVESTMENTS_DIR / "goat" / "insider-scan-report.md", 2, "Goat insider scan"),
    WatchedReport(INVESTMENTS_DIR / "goat" / "hated-industries-report.md", 2, "Goat hated industries scan"),
    WatchedReport(INVESTMENTS_DIR / "my-trader" / "my-trader-report.md", 2, "my-trader Monitor"),
    WatchedReport(INVESTMENTS_DIR / "my-trader" / "cash-value-report.md", 2, "Cash-Value Scan"),
    WatchedReport(INVESTMENTS_DIR / "my-trader" / "earnings-watch-report.md", 2, "Earnings Deterioration Watch"),
    WatchedReport(
        INVESTMENTS_DIR / "superinvestor-filings" / "superinvestor-filings-report.md", 2,
        "Superinvestor Filings Scanner",
    ),
    WatchedReport(
        INVESTMENTS_DIR / "ai-resistant-moat-scanner" / "moat-scan-report.md", 2, "AI-Resistant Moat Scan"
    ),
    WatchedReport(
        INVESTMENTS_DIR / "fourteen-crash-signals-daily-check" / "crash-signals-report.md", 2,
        "Fourteen Crash Signals Daily Check",
    ),
)


def check_stale_reports(
    reports: tuple[WatchedReport, ...] = WATCHED_REPORTS, now: datetime | None = None
) -> list[str]:
    """Returns a human-readable warning line per report whose file hasn't been
    written to within its max_age_days -- empty list means everything's fresh.
    Uses the file's own mtime (these files are overwritten in place by each scan
    directly on this machine, not checked out via git, so mtime is a true "when
    was this last actually generated" signal here, not a checkout artifact). A
    missing file is reported as stale too, not skipped -- a report that never got
    created at all is a worse signal than a late one, not a lesser one."""
    now = now or datetime.now(timezone.utc)
    warnings: list[str] = []
    for report in reports:
        if not report.path.exists():
            warnings.append(f"{report.label}: report file missing entirely ({report.path.name})")
            continue
        mtime = datetime.fromtimestamp(report.path.stat().st_mtime, tz=timezone.utc)
        age = now - mtime
        if age > timedelta(days=report.max_age_days):
            warnings.append(
                f"{report.label}: {report.path.name} last updated {age.days}d ago "
                f"(expected within {report.max_age_days}d)"
            )
    return warnings


def maybe_notify_stale_reports(warnings: list[str]) -> None:
    """Bespoke rather than reusing monitor.maybe_notify -- same reasoning as
    hormuz_risk.maybe_notify: this isn't a per-ticker alert/candidate, it's a
    handful of free-text lines about the sync pipeline itself."""
    if not warnings:
        return

    import sys
    from pathlib import Path as _Path

    _scripts_dir = _Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
    sys.path.insert(0, str(_scripts_dir))
    from notifications import send_toast_notification, send_whatsapp_notification

    summary = f"{len(warnings)} investments report(s) look stale"
    send_toast_notification("Goat Monitor", summary + " -- vault sync may have stopped, check the VPS")
    lines = [f"Goat Monitor: {summary} -- vault sync may have stopped."] + [f"- {w}" for w in warnings]
    send_whatsapp_notification("\n".join(lines))
