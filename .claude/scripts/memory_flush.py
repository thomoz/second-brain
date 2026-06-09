"""Background agent summarizer. Spawned by PreCompact/SessionEnd hooks.
Reads conversation transcript, extracts worth-keeping items, appends to daily log."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# CRITICAL: prevents recursion -- must be set before any LLM import
os.environ["AGENT_INVOKED_BY"] = "memory_flush"

sys.path.insert(0, str(Path(__file__).resolve().parent))

DEDUP_FILE = Path(".claude/data/flush_dedup.json")
TRANSCRIPT_CHAR_LIMIT = 12_000


def _already_flushed_recently(session_id: str) -> bool:
    """Skip if same session flushed in last 60 seconds."""
    if not DEDUP_FILE.exists():
        return False
    try:
        data = json.loads(DEDUP_FILE.read_text())
        last = data.get(session_id, 0)
        return (time.time() - last) < 60
    except (json.JSONDecodeError, OSError):
        return False


def _mark_flushed(session_id: str) -> None:
    try:
        data = json.loads(DEDUP_FILE.read_text()) if DEDUP_FILE.exists() else {}
    except (json.JSONDecodeError, OSError):
        data = {}
    data[session_id] = time.time()
    DEDUP_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEDUP_FILE.write_text(json.dumps(data))


async def flush(transcript: str, session_id: str) -> None:
    if _already_flushed_recently(session_id):
        return

    # Take the tail: most recent content is what needs summarising
    transcript = transcript[-TRANSCRIPT_CHAR_LIMIT:]

    from sdk_compat import AgentOptions, query

    result_text = ""
    async for msg in query(
        prompt=f"""Review this conversation and extract anything worth remembering:
decisions made, lessons learned, action items, key facts about businesses or projects.
Write a concise bullet-point summary (max 10 bullets, each under 100 chars).
If nothing is worth remembering, output only: FLUSH_OK

Conversation:
{transcript}""",
        options=AgentOptions(
            allowed_tools=[],
            permission_mode="dontAsk",
            setting_sources=[],
        ),
    ):
        if hasattr(msg, "content"):
            for block in msg.content:
                if hasattr(block, "text"):
                    result_text += block.text

    result_text = result_text.strip()
    if result_text and result_text != "FLUSH_OK":
        from shared import append_to_daily_log
        append_to_daily_log(f"**[Session summary]**\n{result_text}")

    _mark_flushed(session_id)


def _parse_args() -> tuple[str, str]:
    """Parse args for both call patterns. Returns (transcript_text, session_id)."""
    args = sys.argv[1:]

    # Pi extension style: --context-file <path>
    if "--context-file" in args:
        idx = args.index("--context-file")
        context_file = Path(args[idx + 1])
        try:
            text = context_file.read_text(encoding="utf-8")
        except OSError:
            text = ""
        try:
            context_file.unlink()  # clean up temp file
        except OSError:
            pass
        return text, "pi-session"

    # Claude Code hook style: <transcript_path> <session_id>
    if len(args) >= 2:
        transcript_path = Path(args[0])
        session_id = args[1]
        try:
            text = transcript_path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        return text, session_id

    return "", "unknown"


if __name__ == "__main__":
    transcript_text, session_id = _parse_args()
    if transcript_text:
        asyncio.run(flush(transcript_text, session_id))
