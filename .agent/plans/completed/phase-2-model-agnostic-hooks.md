# Phase 2: Model-Agnostic Hooks and Context Persistence

The following plan is complete and self-contained. Validate patterns against the
reference implementation before writing each file. All content is specified inline.

## Before You Start

- `/prime` has already been run by the user -- full project context is loaded.
- The Python venv at `.claude/scripts/.venv` already exists. Do NOT recreate it.
  Packages already installed: httpx, python-dotenv, pytest, colorama, anyio,
  pygments, packaging, typing_extensions. Phase 2 needs no additional pip installs
  (all scripts use stdlib + python-dotenv which is already present).
- Cole's reference files are at:
  `O:\AI\Dynamous\Courses\workshops\off-claudes-leash\reference-implementation\`
  Read them before implementing Tasks 2, 3, 3b, 7, and 8.
- Cole's original Second Brain (feature reference for Phases 3-9) is at:
  `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\`
  Not needed for Phase 2.

## Feature Description

Build the runtime layer that makes every Claude Code session context-aware and
persists conversation summaries to the daily log. Three lifecycle hooks
(SessionStart, SessionEnd, PreCompact) inject memory context and flush summaries.
A model-agnostic shim layer (sdk_compat -> pi_sdk_compat) means the LLM backend
is a single environment variable, not a hard dependency.

## User Story

As Shaun Thomson (multi-business founder),
I want every Claude Code session to automatically load my business context and
save important decisions to my daily log without manual effort,
So that the Second Brain is always up to date regardless of which LLM backend
is running underneath.

## Problem Statement

Without this phase, every Claude Code session starts cold (no SOUL/USER/MEMORY
context), conversation insights are lost when sessions end, and all scripts are
hardwired to claude_agent_sdk -- making provider switching impossible without
touching every file.

## Solution Statement

Build a model-agnostic shim (sdk_compat.py) that routes to Pi or Claude based
on SB_AGENT_BACKEND env var. Wire three Claude Code hooks for context injection
and memory flush. Extract context building into session_context.py so both the
Claude hook and any future Pi chat path use the same logic.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: .claude/scripts/, .claude/hooks/, .claude/settings.json
**Dependencies**: Pi coding agent (optional at runtime; only needed when SB_AGENT_BACKEND=pi)

---

## CONTEXT REFERENCES

### Relevant Codebase Files -- READ BEFORE IMPLEMENTING

- `O:\AI\Dynamous\Courses\workshops\off-claudes-leash\reference-implementation\sdk_compat.py`
  Why: Exact backend-selector pattern to adapt. Lines 1-98 are the full file.

- `O:\AI\Dynamous\Courses\workshops\off-claudes-leash\reference-implementation\pi_sdk_compat.py`
  Why: Full Pi subprocess driver. Lines 1-496 are the full file. Adapt model
  defaults only; transport, JSONL parsing, and tool mapping copy verbatim.

- `O:\AI\Dynamous\Courses\workshops\off-claudes-leash\reference-implementation\session_context.py`
  Why: Context builder pattern (read_file_safe, build_context, character cap).
  Adapt to our vault (drop REPOSITORIES.md / core-memories.md, add HEARTBEAT.md).

- `O:\AI\Dynamous\Courses\workshops\off-claudes-leash\reference-implementation\pi_ext\pi_safety.ts`
  Why: Copy verbatim. Complete dangerous-bash + SOUL.md protection extension.

- `O:\AI\Dynamous\Courses\workshops\off-claudes-leash\reference-implementation\pi_ext\pi_memory_hooks.ts`
  Why: Copy verbatim. Complete PreCompact + SessionEnd flush extension with
  debounce logic and detached spawn pattern.

- `.agent/plans/second-brain-prd.md` (lines 258-600)
  Why: Phase 2 spec -- shared.py contents, memory_flush.py spec, hook pseudocode,
  settings.json final shape, AGENT_INVOKED_BY recursion-prevention pattern.

- `Memory/SOUL.md`, `Memory/USER.md`, `Memory/MEMORY.md`, `Memory/HEARTBEAT.md`
  Why: These are the files session_context.py reads. Confirm paths before coding.

### New Files to Create

```
.claude/scripts/config.py              (write fresh)
.claude/scripts/sdk_compat.py          (copy verbatim from Cole's reference)
.claude/scripts/pi_sdk_compat.py       (copy verbatim from Cole's reference)
.claude/scripts/codex_sdk_compat.py    (copy verbatim from Cole's reference)
.claude/scripts/session_context.py     (adapt from Cole's reference -- our vault layout)
.claude/scripts/shared.py              (write fresh per PRD spec)
.claude/scripts/memory_flush.py        (write fresh per PRD spec)
.claude/scripts/pi_ext/pi_safety.ts    (adapt from Cole's reference -- our patterns)
.claude/scripts/pi_ext/pi_memory_hooks.ts  (adapt from Cole's reference -- our flush target)
.claude/hooks/session-start-context.py (write fresh)
.claude/hooks/session-end-flush.py     (write fresh)
.claude/hooks/pre-compact-flush.py     (write fresh)
.claude/hooks/soul-protect.py          (write fresh)
.claude/settings.json                  (write fresh)
.claude/data/state/.gitkeep            (directory stub for heartbeat-state.json)
.claude/data/flush_dedup.json          (empty JSON object -- pre-create so flush works)
```

### Patterns to Follow

**Recursion prevention (CRITICAL):**
Every script that calls the LLM must set this env var BEFORE the first LLM call:
```python
os.environ["AGENT_INVOKED_BY"] = "memory_flush"  # or heartbeat, reflection, chat
```
The SessionEnd and PreCompact hooks read this and exit immediately if set.
Without it, a session-end flush spawns another session, spawning another flush.

**Backend selector (sdk_compat.py pattern):**
```python
_BACKEND = os.getenv("SB_AGENT_BACKEND", "claude").strip().lower()
if TYPE_CHECKING:
    from claude_agent_sdk import query, ClaudeAgentOptions, ...
elif _BACKEND == "pi":
    from pi_sdk_compat import query, ClaudeAgentOptions, ...
else:
    from claude_agent_sdk import query, ClaudeAgentOptions, ...
# Then alias for our PRD naming:
AgentOptions = ClaudeAgentOptions
```

**Safe file reads (session_context.py pattern):**
```python
def read_file_safe(path: Path) -> str:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except OSError:
        pass
    return ""
```

**Windows file locking (shared.py -- msvcrt branch):**
```python
import msvcrt
with open(lock_path, 'w') as f:
    while True:
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            break
        except OSError:
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
```

**Atomic writes (shared.py):**
```python
def atomic_write(path: Path, content: str):
    tmp = str(path) + ".tmp"
    Path(tmp).write_text(content, encoding="utf-8")
    os.replace(tmp, str(path))
```

**Hook output format (all Claude Code hooks):**
```python
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",   # or PreToolUse
        "additionalContext": "..."         # for SessionStart
        # OR "permissionDecision": "deny"  # for PreToolUse block
    }
}))
sys.exit(0)
```

**Async subprocess spawn (memory_flush.py -- detached background):**
```python
subprocess.Popen(
    [sys.executable, ".claude/scripts/memory_flush.py", transcript_path, session_id],
    start_new_session=True,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
```

---

## IMPLEMENTATION PLAN

These are internal build stages within Phase 2 only -- not the project's phases.

### Stage 1: Foundation (config + shim layer)

Build the path/timezone constants and the model-agnostic shim before anything
tries to import from them.

Tasks: config.py, sdk_compat.py, pi_sdk_compat.py, codex_sdk_compat.py

### Stage 2: Utilities (shared + context + flush)

Build shared file utilities, context builder, and the memory flush script.
These are imported by the hooks.

Tasks: shared.py, session_context.py, memory_flush.py

### Stage 3: Pi extensions

Adapt the TypeScript safety and memory-hooks extensions from Cole's reference.
These are loaded by pi_sdk_compat at runtime via `-e` flag; no compilation needed.

Tasks: pi_ext/pi_safety.ts, pi_ext/pi_memory_hooks.ts

### Stage 4: Claude Code hooks + settings

Wire the four hooks and register them in settings.json.

Tasks: four hook scripts, settings.json, data stubs

### Stage 5: CLAUDE.md update

Add build commands and mark Phase 2 complete.

---

## STEP-BY-STEP TASKS

Execute every task in order. Each task is independently verifiable.

---

### TASK 1 -- CREATE `.claude/scripts/config.py`

Path constants and timezone-aware now_local(). Imported by session_context.py
and potentially by future scripts (heartbeat, reflection).

**IMPLEMENT:**
```python
"""Central path constants and timezone utilities for Second Brain scripts."""
from __future__ import annotations

import zoneinfo
from datetime import datetime
from pathlib import Path

# Vault root (all Memory/ paths are relative to repo root)
VAULT_DIR = Path("Memory")
MEMORY_DIR = VAULT_DIR
DAILY_DIR = VAULT_DIR / "daily"
DRAFTS_DIR = VAULT_DIR / "drafts"
ACTIVE_DRAFTS_DIR = DRAFTS_DIR / "active"

# Runtime dirs
SCRIPTS_DIR = Path(".claude/scripts")
DATA_DIR = Path(".claude/data")
STATE_DIR = DATA_DIR / "state"

# Timezone: all timestamps use Sydney local time
TZ = zoneinfo.ZoneInfo("Australia/Sydney")


def now_local() -> datetime:
    """Current datetime in Australia/Sydney timezone."""
    return datetime.now(tz=TZ)
```

**GOTCHA:** `zoneinfo` is stdlib in Python 3.9+. If the venv Python is older,
use `pip install backports.zoneinfo` and add a try/except import fallback.
Check: `python --version` in `.claude/scripts/.venv`.

**VALIDATE:**
```powershell
cd "O:\AI\Dynamous\Courses\second-brain-workshop"
.claude\scripts\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.claude/scripts'); from config import now_local, DAILY_DIR; print(now_local(), DAILY_DIR)"
```
Expected: current Sydney datetime and `Memory\daily`

---

### TASK 2 -- CREATE `.claude/scripts/sdk_compat.py`

Cole's universal backend selector. COPY VERBATIM -- zero changes.
Source: `O:\AI\Dynamous\Courses\workshops\off-claudes-leash\reference-implementation\sdk_compat.py`

This file is a drop-in for any claude_agent_sdk app. It reads `SB_AGENT_BACKEND`
(claude / pi / codex) and re-exports an identical surface from whichever backend
is active. Do not modify it -- any customisation belongs in config or env vars.

**PATTERN:** Reference `sdk_compat.py` lines 1-98 -- copy every line exactly.

**GOTCHA:** The `if TYPE_CHECKING:` block imports from `claude_agent_sdk` for
mypy only. At runtime the elif/else picks the real backend. This is intentional.

**VALIDATE:**
```powershell
.claude\scripts\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.claude/scripts'); from sdk_compat import ClaudeAgentOptions, BACKEND, run_text; print('backend:', BACKEND)"
```
Expected: `backend: claude` (or `pi` / `codex` if SB_AGENT_BACKEND is set)

---

### TASK 3 -- CREATE `.claude/scripts/pi_sdk_compat.py`

Cole's Pi subprocess driver. COPY VERBATIM -- zero changes.
Source: `O:\AI\Dynamous\Courses\workshops\off-claudes-leash\reference-implementation\pi_sdk_compat.py`

Drop-in for any claude_agent_sdk app. Drives `pi --mode json` as a subprocess,
parses its JSONL stream, re-exposes query/ClaudeAgentOptions/AssistantMessage etc.
Model defaults (PI_MODEL_CHEAP/MID/STRONG) are env-configurable -- no code change needed.

**GOTCHA:** Pi does NOT need to be installed for claude backend. `_find_pi()`
raises `FileNotFoundError` only when `query()` actually runs under the pi backend.

**VALIDATE:**
```powershell
.claude\scripts\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.claude/scripts'); from pi_sdk_compat import ClaudeAgentOptions, query, AssistantMessage, ResultMessage; print('pi_sdk_compat OK')"
```
Expected: `pi_sdk_compat OK`

---

### TASK 3b -- CREATE `.claude/scripts/codex_sdk_compat.py`

Cole's Codex CLI backend. COPY VERBATIM -- zero changes.
Source: `O:\AI\Dynamous\Courses\workshops\off-claudes-leash\reference-implementation\codex_sdk_compat.py`

Third backend option: set `SB_AGENT_BACKEND=codex` to route all LLM calls
through the OpenAI Codex CLI instead of Pi or Claude. No changes required.

**VALIDATE:**
```powershell
.claude\scripts\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.claude/scripts'); from codex_sdk_compat import ClaudeAgentOptions, query; print('codex_sdk_compat OK')"
```
Expected: `codex_sdk_compat OK`

---

### TASK 4 -- CREATE `.claude/scripts/session_context.py`

Context builder. ADAPT reference `session_context.py`. Our vault differs from
the reference (no REPOSITORIES.md, no core-memories.md; we have HEARTBEAT.md).

**IMPLEMENT:** Adapt reference `session_context.py` with these changes:
1. Import from our `config.py` (not the reference's config):
   ```python
   from config import DAILY_DIR, MEMORY_DIR, now_local
   ```
2. In `build_context()`: replace the REPOSITORIES.md and core-memories.md reads
   with a HEARTBEAT.md read:
   ```python
   heartbeat = read_file_safe(MEMORY_DIR / "HEARTBEAT.md")
   if heartbeat:
       parts.append("## Heartbeat Monitoring\n" + heartbeat.strip())
   ```
3. Read order: Today date, BOOTSTRAP (if present), SOUL, USER, MEMORY,
   HEARTBEAT, recent daily log
4. Keep `MAX_CONTEXT_CHARS = 60_000` and the truncation logic unchanged
5. Keep `get_recent_daily_log()` unchanged but use last 3 days instead of
   today-only fallback:
   ```python
   for i in range(3):
       d = (now_local() - timedelta(days=i)).strftime("%Y-%m-%d")
       content = read_file_safe(DAILY_DIR / f"{d}.md")
       if content:
           # append to parts with label "Daily log YYYY-MM-DD"
   ```
   This matches the PRD spec (last 3 days of logs).

**PATTERN:** Reference `session_context.py` lines 1-110

**VALIDATE:**
```powershell
.claude\scripts\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.claude/scripts'); from session_context import build_context; ctx = build_context(); print(ctx[:300])"
```
Expected: Output begins with today's date and contains "Soul" section header.

---

### TASK 5 -- CREATE `.claude/scripts/shared.py`

File locking, atomic writes, retry, daily log append, dangerous bash patterns.
Written fresh per PRD spec. Windows-first (`msvcrt` locking).

**IMPLEMENT:**
```python
"""Shared utilities: file locking, atomic writes, retry, daily log, bash patterns."""
from __future__ import annotations

import contextlib
import datetime
import os
import re
import time
from pathlib import Path


@contextlib.contextmanager
def file_lock(path: Path):
    """Cross-platform exclusive file lock (Windows: msvcrt; POSIX: fcntl)."""
    lock_path = str(path) + ".lock"
    if os.name == "nt":
        import msvcrt
        with open(lock_path, "w") as f:
            while True:
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
            try:
                yield
            finally:
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
    else:
        import fcntl
        with open(lock_path, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


def with_retry(fn, max_retries: int = 3, base_delay: float = 1.0):
    """Retry with exponential backoff. Wrap external API calls with this."""
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(base_delay * (2 ** attempt))


def atomic_write(path: Path, content: str) -> None:
    """Write to .tmp then os.replace -- prevents partial writes on crash."""
    tmp = str(path) + ".tmp"
    Path(tmp).write_text(content, encoding="utf-8")
    os.replace(tmp, str(path))


def append_to_daily_log(text: str) -> None:
    """Append timestamped entry to today's daily log with file locking."""
    from config import DAILY_DIR, now_local
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    today = now_local().strftime("%Y-%m-%d")
    log_path = DAILY_DIR / f"{today}.md"
    timestamp = now_local().strftime("%H:%M")
    entry = f"\n## {timestamp}\n{text.strip()}\n"
    with file_lock(log_path):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)


# Dangerous bash patterns used by command-guard.py (Phase 8) and pi_safety.ts.
# Keep this list in sync with the TypeScript version in pi_ext/pi_safety.ts.
DANGEROUS_BASH_PATTERNS: list[str] = [
    r"rm\s+(-[a-z]*f[a-z]*\s+|--force\s+)",
    r"\bdd\b.*of=",
    r"\bmkfs\b",
    r">\s*/dev/(sd|hd|nvme)",
    r"truncate.*--size\s+0",
    r"\bshred\b",
    r"Remove-Item.*-Recurse.*-Force",
    r"Format-Volume",
    r"(cat|type|Get-Content)\s+.*\.env",
    r"\bprintenv\b",
    r"\$env:[A-Z_]*(TOKEN|KEY|SECRET|PASSWORD|APIKEY)",
    r"echo\s+\$[A-Z_]*(TOKEN|KEY|SECRET)",
    r"python.*os\.environ",
    r"import\s+os.*\bgetenv\b",
    r"curl\s+.*\$\w*(TOKEN|KEY|SECRET)",
    r"wget\s+.*\|\s*(ba)?sh",
    r"pip\s+install\b",
    r"pip3\s+install\b",
    r"npm\s+install\b",
    r"brew\s+install\b",
    r"apt(-get)?\s+install\b",
    r"choco\s+install\b",
    r"winget\s+install\b",
    r"\bsudo\b",
    r"chmod\s+[0-7]*7[0-7][0-7]",
    r"icacls.*grant.*Everyone",
    r"Set-ExecutionPolicy\s+Unrestricted",
    r"\beval\b",
    r"\bexec\b\s+[^(]",
    r"os\.system\s*\(",
    r"subprocess.*shell\s*=\s*True",
    r"\b(stripe|paypal|square)\b.*\b(charge|payment|transfer)\b",
    r"del\s+/[sqa]",
    r"Remove-Item.*\*",
]
```

**VALIDATE:**
```powershell
.claude\scripts\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.claude/scripts'); from shared import append_to_daily_log, DANGEROUS_BASH_PATTERNS; print('patterns:', len(DANGEROUS_BASH_PATTERNS)); append_to_daily_log('Phase 2 shared.py test entry'); print('append OK')"
```
Expected: `patterns: 34` (or similar count) and `append OK`. Check that
`Memory\daily\<today>.md` was created/updated.

---

### TASK 6 -- CREATE `.claude/scripts/memory_flush.py`

Background LLM summarizer. Sets AGENT_INVOKED_BY, reads a transcript, calls
sdk_compat.query with no tools, appends bullet summary to daily log.

Supports TWO call patterns:
- Claude Code hook style: `python memory_flush.py <transcript_path> <session_id>`
- Pi memory-hooks style: `python memory_flush.py --context-file <tmp_path>`
  (Pi extension writes transcript to a temp file, we read + delete it)

**IMPLEMENT:**
```python
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

    transcript = transcript[:TRANSCRIPT_CHAR_LIMIT]

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
```

**GOTCHA:** The `AGENT_INVOKED_BY` must be set at module level, before any
import of sdk_compat, otherwise a recursive SessionEnd could fire.

**VALIDATE:**
```powershell
# Test with dummy transcript (no real LLM call -- just verifies arg parsing and import)
echo "test transcript" | .claude\scripts\.venv\Scripts\python.exe .claude\scripts\memory_flush.py --help 2>&1
.claude\scripts\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.claude/scripts'); import memory_flush; print('import OK, AGENT_INVOKED_BY:', __import__('os').environ.get('AGENT_INVOKED_BY'))"
```
Expected: `import OK, AGENT_INVOKED_BY: memory_flush`

---

### TASK 7 -- CREATE `.claude/scripts/pi_ext/pi_safety.ts`

ADAPT from Cole's reference. The lifecycle mechanism (pi.on "tool_call") is
general; the dangerous pattern list and protected paths are ours to configure.
Source: `O:\AI\Dynamous\Courses\workshops\off-claudes-leash\reference-implementation\pi_ext\pi_safety.ts`

**IMPLEMENT:** Copy the reference file then:
1. Replace the `DANGEROUS_BASH_PATTERNS` string array with patterns that match
   our `shared.py`'s `DANGEROUS_BASH_PATTERNS` list (keep as plain strings,
   not regex -- the TS version uses `includes()` not regex match).
2. The `isProtectedPath()` function and `pi.on("tool_call")` handler are correct
   as-is -- SOUL.md protection and bash blocking are what we need.

**GOTCHA:** The directory `.claude/scripts/pi_ext/` must be created first.
Use the Write tool to create the file (it will create the parent directory).

**VALIDATE:**
```powershell
Test-Path ".claude\scripts\pi_ext\pi_safety.ts"
(Get-Content ".claude\scripts\pi_ext\pi_safety.ts" | Select-String "SOUL").Count
```
Expected: True, and count >= 1

---

### TASK 8 -- CREATE `.claude/scripts/pi_ext/pi_memory_hooks.ts`

ADAPT from Cole's reference. The lifecycle wiring (session_before_compact,
session_shutdown, debounce, detached spawn) is general and correct. The flush
target (memory_flush.py path and call signature) must match our project.
Source: `O:\AI\Dynamous\Courses\workshops\off-claudes-leash\reference-implementation\pi_ext\pi_memory_hooks.ts`

**IMPLEMENT:** Copy the reference file then verify:
1. `spawnFlush()` calls `memory_flush.py --context-file <tmp>` -- this matches
   our memory_flush.py's `--context-file` arg parser. No change needed.
2. `SB_FLUSH_SCRIPTS` and `SB_FLUSH_PYTHON` env vars are set by pi_sdk_compat.py
   when it launches Pi. No change needed.
3. `STATE_FILE` path (pi_flush_state.json) lands in `.claude/data/` -- correct
   for our project layout. No change needed.

**VALIDATE:**
```powershell
Test-Path ".claude\scripts\pi_ext\pi_memory_hooks.ts"
(Get-Content ".claude\scripts\pi_ext\pi_memory_hooks.ts" | Select-String "session_before_compact").Count
```
Expected: True, and count >= 1

---

### TASK 9 -- CREATE `.claude/hooks/session-start-context.py`

SessionStart hook. Checks for BOOTSTRAP.md (first-run), otherwise calls
session_context.build_context() and returns the result as additionalContext.

**IMPLEMENT:**
```python
#!/usr/bin/env python3
"""SessionStart hook: inject memory context into every conversation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add scripts dir to path for session_context and config imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

data = json.load(sys.stdin)

# First-run: inject BOOTSTRAP.md if it still exists
bootstrap = Path("Memory/BOOTSTRAP.md")
if bootstrap.exists():
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                "[FIRST-RUN ONBOARDING IN PROGRESS]\n\n"
                + bootstrap.read_text(encoding="utf-8")
            ),
        }
    }))
    sys.exit(0)

# Normal session: inject SOUL + USER + MEMORY + HEARTBEAT + recent daily logs
from session_context import build_context

context = build_context("startup")
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": context,
    }
}))
sys.exit(0)
```

**GOTCHA:** The hook is called by Claude Code with `python .claude/hooks/...`
from the repo root. Path("Memory/BOOTSTRAP.md") is relative to CWD (repo root).
The sys.path.insert must point to `.claude/scripts` relative to the hook file.

**VALIDATE:**
```powershell
echo "{}" | .claude\scripts\.venv\Scripts\python.exe .claude\hooks\session-start-context.py | python -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'additionalContext' in d['hookSpecificOutput'] else 'FAIL')"
```
Expected: `OK`

---

### TASK 10 -- CREATE `.claude/hooks/session-end-flush.py`

SessionEnd hook. Checks AGENT_INVOKED_BY guard, then spawns memory_flush.py
as a detached background process.

**IMPLEMENT:**
```python
#!/usr/bin/env python3
"""SessionEnd hook: spawn memory_flush.py as background process."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

data = json.load(sys.stdin)

# Recursion guard: if WE are a flush/heartbeat/reflection run, exit silently
if os.environ.get("AGENT_INVOKED_BY"):
    sys.exit(0)

transcript_path = data.get("transcript_path", "")
session_id = data.get("session_id", "unknown")

if not transcript_path or not Path(transcript_path).exists():
    sys.exit(0)

scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
venv_python = scripts_dir / ".venv" / "Scripts" / "python.exe"
python_exe = str(venv_python) if venv_python.exists() else sys.executable

subprocess.Popen(
    [python_exe, str(scripts_dir / "memory_flush.py"), transcript_path, session_id],
    start_new_session=True,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
sys.exit(0)
```

**VALIDATE:**
```powershell
echo '{"transcript_path":"","session_id":"test"}' | .claude\scripts\.venv\Scripts\python.exe .claude\hooks\session-end-flush.py; echo "exit: $LASTEXITCODE"
```
Expected: exit code 0 (no output, exits cleanly)

---

### TASK 11 -- CREATE `.claude/hooks/pre-compact-flush.py`

PreCompact hook. Identical pattern to session-end-flush.py.

**IMPLEMENT:**
```python
#!/usr/bin/env python3
"""PreCompact hook: flush conversation to daily log before auto-compaction."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

data = json.load(sys.stdin)

# Recursion guard
if os.environ.get("AGENT_INVOKED_BY"):
    sys.exit(0)

transcript_path = data.get("transcript_path", "")
session_id = data.get("session_id", "unknown")

if not transcript_path or not Path(transcript_path).exists():
    sys.exit(0)

scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
venv_python = scripts_dir / ".venv" / "Scripts" / "python.exe"
python_exe = str(venv_python) if venv_python.exists() else sys.executable

subprocess.Popen(
    [python_exe, str(scripts_dir / "memory_flush.py"), transcript_path, session_id],
    start_new_session=True,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
sys.exit(0)
```

**VALIDATE:**
```powershell
echo '{"transcript_path":"","session_id":"test"}' | .claude\scripts\.venv\Scripts\python.exe .claude\hooks\pre-compact-flush.py; echo "exit: $LASTEXITCODE"
```
Expected: exit code 0

---

### TASK 12 -- CREATE `.claude/hooks/soul-protect.py`

PreToolUse hook. Blocks any Write/Edit targeting SOUL.md when the caller is
the reflection agent.

**IMPLEMENT:**
```python
#!/usr/bin/env python3
"""PreToolUse hook: block reflection agent from editing SOUL.md."""
from __future__ import annotations

import json
import os
import sys

data = json.load(sys.stdin)

if os.environ.get("AGENT_INVOKED_BY") == "reflection":
    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")
    if "SOUL.md" in file_path:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "SOUL.md is write-protected during reflection. "
                    "Log personality change suggestions to the daily log instead."
                ),
            }
        }))
        sys.exit(0)

sys.exit(0)
```

**VALIDATE:**
```powershell
# Simulate a reflection agent trying to edit SOUL.md
$env:AGENT_INVOKED_BY = "reflection"
echo '{"tool_name":"Edit","tool_input":{"file_path":"Memory/SOUL.md"}}' | .claude\scripts\.venv\Scripts\python.exe .claude\hooks\soul-protect.py | python -c "import sys,json; d=json.load(sys.stdin); print(d['hookSpecificOutput']['permissionDecision'])"
$env:AGENT_INVOKED_BY = ""
```
Expected: `deny`

---

### TASK 13 -- CREATE `.claude/settings.json`

Wire SessionStart, SessionEnd, and PreCompact hooks. soul-protect (PreToolUse)
is included now; block-secrets and command-guard are added in Phase 8.

**IMPLEMENT:**
```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/session-start-context.py",
            "timeout": 30
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/session-end-flush.py",
            "timeout": 120
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/pre-compact-flush.py",
            "timeout": 120
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/soul-protect.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

**GOTCHA:** The `shell` key was in the PRD sample but is not valid in all Claude
Code versions. Omit it -- Claude Code picks the system shell automatically.

**VALIDATE:**
```powershell
python -c "import json; d=json.load(open('.claude/settings.json')); print('hooks:', list(d['hooks'].keys()))"
```
Expected: `hooks: ['SessionStart', 'SessionEnd', 'PreCompact', 'PreToolUse']`

---

### TASK 14 -- CREATE data directory stubs

Create the data directories that runtime scripts write to, so they don't fail
on first run due to missing parent directories.

**IMPLEMENT:**
Create these files/dirs:
- `.claude/data/state/.gitkeep` -- heartbeat state dir (Phase 6)
- `.claude/data/flush_dedup.json` -- pre-seed with empty object: `{}`

**VALIDATE:**
```powershell
Test-Path ".claude\data\state\.gitkeep"
Get-Content ".claude\data\flush_dedup.json"
```
Expected: True, `{}`

---

### TASK 15 -- UPDATE `CLAUDE.md`

Add Phase 2 build commands and mark phase complete.

**UPDATE** the `## Build Commands` section to:
```markdown
## Build Commands

# Test hooks (pipe empty JSON to stdin)
echo {} | python .claude/hooks/session-start-context.py
echo {} | python .claude/hooks/session-end-flush.py
echo {} | python .claude/hooks/pre-compact-flush.py

# Test context injection
python -c "import sys; sys.path.insert(0,'.claude/scripts'); from session_context import build_context; print(build_context()[:500])"

# Manual memory flush (replace paths as needed)
python .claude/scripts/memory_flush.py <transcript_path> <session_id>
```

**UPDATE** the `## Completed Phases` section to add:
```markdown
### Phase 2: Model-Agnostic Hooks and Context Persistence (2026-06-08)
Lifecycle hooks (SessionStart, SessionEnd, PreCompact, PreToolUse/soul-protect)
wired via .claude/settings.json. Backend-agnostic shim layer: sdk_compat.py
(selector) + pi_sdk_compat.py (Pi subprocess driver). Shared utilities in
shared.py. Context builder in session_context.py. Background summarizer in
memory_flush.py. Pi safety + memory-hooks TypeScript extensions in pi_ext/.
```

**VALIDATE:**
```powershell
Select-String "Phase 2" CLAUDE.md
```
Expected: match on the completed phase entry

---

## TESTING STRATEGY

### Unit Tests (manual -- no pytest framework configured yet)

1. **config.py**: `now_local()` returns Sydney-timezone datetime
2. **sdk_compat.py**: imports without error; `BACKEND` is `"claude"` by default
3. **pi_sdk_compat.py**: imports without error; `ClaudeAgentOptions()` constructs
4. **session_context.py**: `build_context()` returns non-empty string containing
   SOUL.md content; handles missing daily log gracefully
5. **shared.py**: `append_to_daily_log("test")` creates/appends to today's log
6. **memory_flush.py**: imports without error; `AGENT_INVOKED_BY` set at module load
7. **session-start-context.py**: returns valid JSON with `additionalContext`
8. **soul-protect.py**: returns deny when `AGENT_INVOKED_BY=reflection` + SOUL.md path

### Integration Test

Manually trigger SessionStart by piping `{}` to the hook script. Verify the
output JSON contains recognisable content from SOUL.md or USER.md.

### Edge Cases

- Missing daily log files: session_context silently skips missing files
- Empty transcript passed to memory_flush: skips LLM call, exits cleanly
- BOOTSTRAP.md present: session-start-context returns bootstrap content, not full context
- Non-reflection caller tries to edit SOUL.md: soul-protect exits 0 (no block)

---

## VALIDATION COMMANDS

### Level 1: All imports resolve

```powershell
cd "O:\AI\Dynamous\Courses\second-brain-workshop"
.claude\scripts\.venv\Scripts\python.exe -c "
import sys
sys.path.insert(0, '.claude/scripts')
from config import now_local, DAILY_DIR
from sdk_compat import ClaudeAgentOptions, BACKEND, run_text
from pi_sdk_compat import ClaudeAgentOptions, query as pi_query
from session_context import build_context
from shared import append_to_daily_log, DANGEROUS_BASH_PATTERNS
import memory_flush
print('All imports OK')
print('BACKEND:', BACKEND)
print('AGENT_INVOKED_BY:', __import__('os').environ.get('AGENT_INVOKED_BY'))
"
```
Expected: `All imports OK`, `BACKEND: claude`, `AGENT_INVOKED_BY: memory_flush`

Note: `ClaudeAgentOptions` is just the class name in Cole's shim -- it is NOT
hardwired to Claude. Which backend runs depends entirely on SB_AGENT_BACKEND.

### Level 2: Hook smoke tests

```powershell
# SessionStart returns valid JSON
echo "{}" | .claude\scripts\.venv\Scripts\python.exe .claude\hooks\session-start-context.py | .claude\scripts\.venv\Scripts\python.exe -c "import sys,json; d=json.load(sys.stdin); print('SessionStart OK, context chars:', len(d['hookSpecificOutput']['additionalContext']))"

# SessionEnd exits cleanly with no transcript
echo '{"transcript_path":"","session_id":"test"}' | .claude\scripts\.venv\Scripts\python.exe .claude\hooks\session-end-flush.py
echo "SessionEnd exit: $LASTEXITCODE"

# soul-protect blocks SOUL.md write when reflection
$env:AGENT_INVOKED_BY="reflection"; echo '{"tool_name":"Edit","tool_input":{"file_path":"Memory/SOUL.md"}}' | .claude\scripts\.venv\Scripts\python.exe .claude\hooks\soul-protect.py | .claude\scripts\.venv\Scripts\python.exe -c "import sys,json; d=json.load(sys.stdin); print('soul-protect:', d['hookSpecificOutput']['permissionDecision'])"; $env:AGENT_INVOKED_BY=""
```
Expected: SessionStart OK with char count > 100, SessionEnd exit 0, soul-protect: deny

### Level 3: Context quality

```powershell
.claude\scripts\.venv\Scripts\python.exe -c "
import sys
sys.path.insert(0, '.claude/scripts')
from session_context import build_context
ctx = build_context()
assert 'SongbookDB' in ctx, 'USER.md not loaded'
assert 'Advisor' in ctx, 'SOUL.md not loaded'
print('Context quality OK')
print('Total chars:', len(ctx))
"
```
Expected: `Context quality OK`

### Level 4: settings.json is valid JSON with all four hook events

```powershell
.claude\scripts\.venv\Scripts\python.exe -c "
import json
d = json.load(open('.claude/settings.json'))
required = {'SessionStart','SessionEnd','PreCompact','PreToolUse'}
found = set(d['hooks'].keys())
assert required == found, f'Missing: {required - found}'
print('settings.json OK:', sorted(found))
"
```
Expected: `settings.json OK: ['PreCompact', 'PreToolUse', 'SessionEnd', 'SessionStart']`

### Level 5: File tree check

```powershell
@(
  ".claude\scripts\config.py",
  ".claude\scripts\sdk_compat.py",
  ".claude\scripts\pi_sdk_compat.py",
  ".claude\scripts\session_context.py",
  ".claude\scripts\shared.py",
  ".claude\scripts\memory_flush.py",
  ".claude\scripts\pi_ext\pi_safety.ts",
  ".claude\scripts\pi_ext\pi_memory_hooks.ts",
  ".claude\hooks\session-start-context.py",
  ".claude\hooks\session-end-flush.py",
  ".claude\hooks\pre-compact-flush.py",
  ".claude\hooks\soul-protect.py",
  ".claude\settings.json",
  ".claude\data\state\.gitkeep",
  ".claude\data\flush_dedup.json"
) | ForEach-Object { "$_ : $(Test-Path $_)" }
```
Expected: all 15 lines end with `: True`

---

## ACCEPTANCE CRITERIA

- [ ] All 15 files created in correct locations
- [ ] All Level 1-5 validation commands pass with zero errors
- [ ] `build_context()` returns a string containing SOUL.md and USER.md content
- [ ] SessionStart hook returns valid JSON with non-empty `additionalContext`
- [ ] soul-protect.py returns `deny` when AGENT_INVOKED_BY=reflection + SOUL.md target
- [ ] soul-protect.py returns exit 0 (no output) for non-reflection callers
- [ ] `sdk_compat.BACKEND` defaults to `"claude"` when SB_AGENT_BACKEND is unset
- [ ] `AgentOptions` is importable from `sdk_compat` as an alias of `ClaudeAgentOptions`
- [ ] `AGENT_INVOKED_BY` is set to `"memory_flush"` on `import memory_flush`
- [ ] CLAUDE.md updated with Phase 2 build commands and completed phase entry
- [ ] No hardcoded claude_agent_sdk imports in any of the new scripts
  (sdk_compat.py's TYPE_CHECKING block is the only allowed exception)

---

## COMPLETION CHECKLIST

- [ ] Tasks 1-15 completed in order
- [ ] Each task's VALIDATE command executed and passed
- [ ] Level 1-5 validation suite all green
- [ ] CLAUDE.md updated
- [ ] No regressions: existing Memory/ vault files untouched

---

## NOTES

**Why memory_flush.py supports two call patterns:**
Claude Code hooks call it as `memory_flush.py <transcript_path> <session_id>`.
The Pi memory-hooks TypeScript extension (pi_memory_hooks.ts) writes a temp file
and calls `memory_flush.py --context-file <path>`. Both patterns must work so
the flush behavior is identical regardless of which runtime is in use.

**Why the shell key is omitted from settings.json:**
The PRD sample included `"shell": "powershell"` but Claude Code hook schema does
not universally support it. Omitting it is safer -- Claude Code uses the system
default shell, which is PowerShell on Windows.

**Why pi_sdk_compat.py keeps ClaudeAgentOptions as the class name:**
The Pi shim is a compatibility facade that mirrors the claude_agent_sdk API shape.
Renaming the class internally would break any future code that passes
ClaudeAgentOptions instances across the boundary. sdk_compat.py adds AgentOptions
as an alias at the selector level -- callers can use either name.

**What comes next (Phase 3):**
Memory search (embeddings + SQLite hybrid RAG) builds on the shared.py file-lock
and config.py path constants created in this phase.

**Pi not required until SB_AGENT_BACKEND=pi:**
The pi_sdk_compat.py and pi_ext/*.ts files are present but never executed unless
the env var is set. Claude backend is the default and works without Pi installed.
