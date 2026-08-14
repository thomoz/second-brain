"""
Deterministic hourly check for new entries in
Memory/whatsapp-handoff-messages-for-local-session.md -- alerts via Windows toast
(local) the moment a new handoff arrives, instead of relying on the LLM-based
heartbeat to notice one buried in a large context blob.

Built 2026-08-14, the same day a 12-day vault-sync outage was found and fixed (see
Memory/daily/2026/08/2026-08-14.md) -- during that outage, WhatsApp "leave a handoff
for next local session" messages (then routed to a section inside Memory/HEARTBEAT.md
per Memory/ASSISTANT.md) were landing correctly but never surfacing locally, and were
hard to find precisely because "HEARTBEAT.md" gave no hint it held them. Moved the
same day to this dedicated, explicitly-named file (Shaun: "if they're in a separate,
logically named file... we should likely never lose it again").

Deliberately separate from heartbeat.py: heartbeat.py's alerting is an LLM judgment
call over a large prompt and currently only runs on the VPS (Windows Heartbeat task
disabled per Phase 9). This script is a small, deterministic diff -- new entry present
since last run, or not -- and is meant to run locally (toast notifications only mean
anything on this machine).

Usage:
    uv run python handoff_check.py              # normal run
    uv run python handoff_check.py --dry-run    # print what would happen, no state write, no alert
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import HANDOFF_FILE, STATE_DIR  # noqa: E402
from notifications import send_toast_notification  # noqa: E402
from shared import load_state, save_state  # noqa: E402

HANDOFF_STATE_FILE = STATE_DIR / "handoff-check-state.json"

_SECTION_HEADER = "## Active handoffs"
_DATED_HEADING_RE = r"\d{4}-\d{2}-\d{2} \[WhatsApp save\]"
_ENTRY_RE = re.compile(
    r"^## (\d{4}-\d{2}-\d{2}) \[WhatsApp save\]\n(.*?)(?=\n## |\Z)",
    re.DOTALL | re.MULTILINE,
)


def _extract_active_handoffs_section(text: str) -> str:
    """Return the text between '## Active handoffs' and the next top-level '## '
    heading that isn't itself a dated entry (defensive -- the file is single-purpose
    today, but this still won't misparse if a new section is ever added below)."""
    start = text.find(_SECTION_HEADER)
    if start == -1:
        return ""
    rest = text[start + len(_SECTION_HEADER):]
    m = re.search(rf"\n## (?!{_DATED_HEADING_RE})", rest)
    return rest[: m.start()] if m else rest


def parse_handoff_entries(heartbeat_text: str) -> list[dict[str, str]]:
    """Parse dated '## YYYY-MM-DD [WhatsApp save]' entries out of the Active
    handoffs section. Returns [{"date": ..., "text": ..., "hash": ...}, ...]."""
    section = _extract_active_handoffs_section(heartbeat_text)
    entries = []
    for m in _ENTRY_RE.finditer(section):
        date_str = m.group(1)
        body = m.group(2).strip()
        if not body:
            continue
        identity = f"{date_str}\n{body}"
        entries.append({
            "date": date_str,
            "text": body,
            "hash": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        })
    return entries


def check_for_new_handoffs(dry_run: bool = False) -> list[dict[str, str]]:
    """Compare current handoff entries against the last-seen state, toast-alert on
    anything new, then update state. Returns the newly-seen entries.

    First-ever run (no state file) seeds the baseline silently -- existing entries
    at the moment this feature is turned on aren't "new arrivals," so they don't
    trigger a alert flood on day one."""
    if not HANDOFF_FILE.exists():
        return []

    text = HANDOFF_FILE.read_text(encoding="utf-8")
    entries = parse_handoff_entries(text)

    state = load_state(HANDOFF_STATE_FILE)
    is_first_run = "seen_hashes" not in state
    seen_hashes = set(state.get("seen_hashes", []))

    new_entries = [] if is_first_run else [e for e in entries if e["hash"] not in seen_hashes]

    if dry_run:
        print(f"Total active handoffs: {len(entries)}")
        print(f"New since last check: {len(new_entries)}")
        for e in new_entries:
            print(f"  - [{e['date']}] {e['text'][:80]}")
        return new_entries

    if new_entries:
        title = "New Handoff" if len(new_entries) == 1 else f"{len(new_entries)} New Handoffs"
        body = "\n".join(f"[{e['date']}] {e['text']}" for e in new_entries)
        send_toast_notification(title, body)

    save_state(HANDOFF_STATE_FILE, {"seen_hashes": [e["hash"] for e in entries]})
    return new_entries


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Memory/HEARTBEAT.md for new VPS handoffs")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would happen, no state write, no alert",
    )
    args = parser.parse_args()
    check_for_new_handoffs(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
