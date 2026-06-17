# Feature: Fix Reflection for Codex Backend — Structured Output

The following plan should be complete, but validate codebase patterns and task
sanity before implementing. Pay special attention to imports, file paths, and the
existing shared utility surface in `shared.py`.

## Feature Description

`memory_reflect.py` currently asks the LLM to write directly to `Memory/MEMORY.md`
and `Memory/USER.md` using Claude SDK named tools (`Edit`, `Write`). The Codex
backend has no named tool API — it uses OS-sandbox shell access. The LLM sees
"Use the Edit tool" in the prompt, has no such tool, and generates text describing
what it *would* write without actually writing anything. `run_reflection()` then
incorrectly records `"promoted"` because the response text is not exactly
`"REFLECTION_OK"`.

Result: MEMORY.md has not been updated since 12 June 2026 (the last day Claude SDK
was the active backend). Every nightly VPS reflection silently fails to persist.

## User Story

As Shaun's Second Brain
I want nightly reflection to reliably update MEMORY.md and USER.md
So that long-term memory accumulates regardless of which LLM backend is active

## Problem Statement

The current design couples file-write operations to the Claude SDK tool-call API.
Two backends (Codex, Pi) do not honour those tool names, so file writes never
happen. The bug is silent: `run_reflection()` only checks for the literal string
`"REFLECTION_OK"` in the response and falls through to the "promoted" branch even
when no files changed.

## Solution Statement

Replace tool-based file writing with **structured output + Python applies changes**:

1. Prompt the LLM to output a JSON block describing what to add to each file.
2. Python parses that JSON and writes the changes using existing `shared.py`
   utilities (`file_lock`, `atomic_write`).
3. Works for Claude, Codex, and Pi — all can produce JSON text output.
4. The `allowed_tools` list becomes `[]` (lean/read-only call) since the LLM no
   longer needs file access.

## Feature Metadata

**Feature Type**: Bug Fix
**Estimated Complexity**: Low
**Primary Systems Affected**: `memory_reflect.py`, `shared.py` (minor), tests
**Dependencies**: None new — uses existing `shared.py`, `config.py`, `json` stdlib

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `.claude/scripts/memory_reflect.py` (entire file, ~277 lines)
  Key sections: `run_reflection()` line 127, `reflection_prompt` string line 160,
  `_run()` async inner fn line 206, response branch line 240+. Also note
  `trim_memory_if_needed()` line 80 has a relative path bug
  `Path("Memory/Research")` — fix this too.

- `.claude/scripts/shared.py` (lines 1-100)
  Provides `file_lock`, `atomic_write`, `append_to_daily_log`, `load_state`,
  `save_state`. All file writes must go through `file_lock` + `atomic_write`.

- `.claude/scripts/config.py` (lines 1-50)
  `MEMORY_FILE`, `USER_FILE`, `VAULT_DIR`, `DAILY_DIR`, `now_local()`,
  `get_today_log_path()`. Import all path constants from here — never hardcode.

- `.claude/scripts/sdk_compat.py`
  Backend selector. `allowed_tools=[]` signals a lean (reasoning-only) call;
  correct for the new structured-output approach.

- `.claude/scripts/codex_sdk_compat.py` (lines 140-145)
  Confirms: "Codex has no allow-list; we only need to know (a) whether this is a
  lean call". `lean = allowed_tools is not None and len(allowed_tools) == 0`.
  Passing `allowed_tools=[]` puts Codex in `read-only` sandbox — appropriate
  since Python (not Codex) will now write the files.

- `.claude/scripts/tests/test_heartbeat.py`
  Reference for test style: `pytest`, `monkeypatch`, `tmp_path`, no live API,
  import specific functions, test edge cases. Mirror this pattern exactly.

- `.claude/scripts/tests/conftest.py`
  Check for any shared fixtures before writing new ones.

### New Files to Create

- `.claude/scripts/tests/test_memory_reflect.py`
  Unit tests for the three new pure functions: `parse_reflection_response`,
  `apply_memory_additions`, `apply_user_updates`.

---

## CONTEXT: Expected JSON Schema

The LLM must return a JSON block (fenced with ```json or bare) in this shape:

```json
{
  "memory_additions": [
    "- VPS must track same branch as local; run deploy.ps1 after any branch switch",
    "- All script paths must be __file__-anchored; Task Scheduler CWD is .claude/scripts/"
  ],
  "user_updates": [],
  "nothing_to_update": false
}
```

Rules the LLM is told (in the new prompt):
- Each item is a complete markdown bullet starting with `- `
- `memory_additions` appended to MEMORY.md under a new dated section
- `user_updates` appended to USER.md under a new dated section
- If nothing is worth adding, set `"nothing_to_update": true` (both lists empty)
- Do NOT duplicate items already present in the current file content

Python then:
1. Extracts JSON from the response (strip fences if needed)
2. If `nothing_to_update=true` log `REFLECTION_OK`, done
3. Otherwise append additions to MEMORY.md and/or USER.md

### Why a dated section (not inline section matching)?

Inserting bullets into the right existing section requires fragile header parsing.
A dated section (`## 2026-06-17 Reflection`) is simpler, always correct, and the
existing `trim_memory_if_needed()` handles pruning when the file grows too large.
The LLM has the full current MEMORY.md in context and is told not to duplicate.

---

## PATTERNS TO FOLLOW

**JSON extraction from LLM text** (stdlib only):
```python
import json, re

def _extract_json(text: str) -> dict:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else text.strip()
    return json.loads(raw)
```

**Atomic file append** (mirror shared.py `atomic_write` + `file_lock`):
```python
from shared import atomic_write, file_lock

with file_lock(MEMORY_FILE):
    current = MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else ""
    updated = current.rstrip() + f"\n\n## {date_str} Reflection\n" + "\n".join(items) + "\n"
    atomic_write(MEMORY_FILE, updated)
```

**Lean LLM call** (`allowed_tools=[]` — Codex read-only sandbox, Claude no tools):
```python
options=ClaudeAgentOptions(
    allowed_tools=[],   # structured output -- Python writes files, not the LLM
    max_turns=1,
)
```
No `hooks` kwarg needed — LLM cannot use Write/Edit so soul-protect is irrelevant.

**Test pattern** (from test_heartbeat.py):
```python
def test_parse_reflection_response_nothing_to_update():
    text = '{"memory_additions": [], "user_updates": [], "nothing_to_update": true}'
    result = parse_reflection_response(text)
    assert result["nothing_to_update"] is True
    assert result["memory_additions"] == []
```

---

## IMPLEMENTATION PLAN

### Phase 1: Extract Pure Helper Functions

Add three standalone functions to `memory_reflect.py` that can be unit-tested
without LLM calls:
1. `parse_reflection_response(text: str) -> dict`
2. `apply_memory_additions(additions: list[str], date_str: str) -> bool`
3. `apply_user_updates(updates: list[str], date_str: str) -> bool`

### Phase 2: Rewrite the Reflection Prompt

Replace tool-instruction prompt with structured-output prompt. Still pass full
current MEMORY.md and USER.md (so LLM can avoid duplicates), but ask for JSON.

### Phase 3: Update `run_reflection()` Orchestration

- `allowed_tools=[]`, `max_turns=1`
- After `asyncio.run(_run())`: parse JSON, apply changes, log result

### Phase 4: Fix `trim_memory_if_needed` Relative Path

Line ~89: `Path("Memory/Research")` -> `VAULT_DIR / "Research"`

### Phase 5: Tests

`test_memory_reflect.py` covering all three new functions.

---

## STEP-BY-STEP TASKS

### Task 1: ADD `parse_reflection_response()` to `memory_reflect.py`

Insert after `trim_memory_if_needed()`, before `protect_soul` (around line 103):

```python
def parse_reflection_response(text: str) -> dict:
    """Extract JSON from LLM response. Returns dict with keys:
    memory_additions, user_updates, nothing_to_update."""
    import re
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else text.strip()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {"memory_additions": [], "user_updates": [], "nothing_to_update": True, "_parse_error": True}
    return {
        "memory_additions": data.get("memory_additions") or [],
        "user_updates": data.get("user_updates") or [],
        "nothing_to_update": bool(data.get("nothing_to_update", False)),
    }
```

- IMPORTS: Add `import json` and `import re` at stdlib imports if not present
- VALIDATE: `python -c "from memory_reflect import parse_reflection_response; print(parse_reflection_response('{\"nothing_to_update\": true}'))"`

### Task 2: ADD `apply_memory_additions()` and `apply_user_updates()` to `memory_reflect.py`

Insert after `parse_reflection_response`:

```python
def apply_memory_additions(additions: list[str], date_str: str) -> bool:
    """Append additions to MEMORY.md under a dated section. Returns True if wrote."""
    if not additions:
        return False
    with file_lock(MEMORY_FILE):
        current = MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else "# Memory\n"
        section = f"\n## {date_str} Reflection\n" + "\n".join(additions) + "\n"
        atomic_write(MEMORY_FILE, current.rstrip() + section)
    return True


def apply_user_updates(updates: list[str], date_str: str) -> bool:
    """Append updates to USER.md under a dated section. Returns True if wrote."""
    if not updates:
        return False
    with file_lock(USER_FILE):
        current = USER_FILE.read_text(encoding="utf-8") if USER_FILE.exists() else "# User\n"
        section = f"\n## {date_str} Reflection\n" + "\n".join(updates) + "\n"
        atomic_write(USER_FILE, current.rstrip() + section)
    return True
```

- IMPORTS: `atomic_write` must be added to `from shared import ...`
- GOTCHA: `file_lock` is already imported — do not add a duplicate import
- VALIDATE: `python -c "from memory_reflect import apply_memory_additions; print('ok')"`

### Task 3: FIX relative path in `trim_memory_if_needed()`

- UPDATE `.claude/scripts/memory_reflect.py` line ~89
- CHANGE `archive_dir = Path("Memory/Research")` to `archive_dir = VAULT_DIR / "Research"`
- IMPORTS: Add `VAULT_DIR` to the `from config import (...)` block
- VALIDATE: `python -c "from memory_reflect import trim_memory_if_needed; print('ok')"`

### Task 4: REWRITE `reflection_prompt` in `run_reflection()`

Replace the entire `reflection_prompt = f"""..."""` string with:

```python
    reflection_prompt = f"""Daily memory reflection for {owner}'s Second Brain.

Review yesterday's daily log and decide what (if anything) should be added to
long-term memory files. Respond with a single JSON block and nothing else.

## Current MEMORY.md
{current_memory}

## Current USER.md
{current_user}

## Yesterday's Daily Log ({date_str})
{wrap_external_data(log_content, "daily_logs")}

{TRUST_BOUNDARY_INSTRUCTION}

## Output Format

Respond with ONLY this JSON (no prose, no extra text):

```json
{{
  "memory_additions": [
    "- item worth adding to MEMORY.md"
  ],
  "user_updates": [
    "- item worth adding to USER.md"
  ],
  "nothing_to_update": false
}}
```

## Rules

- Each item is a complete markdown bullet starting with `- `
- memory_additions: key decisions, project status, config changes, lessons learned
- user_updates: communication preferences, schedule patterns, tool preferences
  (only when there is clear repeated evidence, not one-off mentions)
- Do NOT add anything already in Current MEMORY.md or Current USER.md above
- NEVER include SOUL.md content or personality changes
- If nothing is worth adding set "nothing_to_update": true with empty lists
- Keep items concise (under 120 chars each)
"""
```

- GOTCHA: `{{` and `}}` are escaped f-string braces for the JSON example — correct syntax
- VALIDATE: `python -c "import memory_reflect"` (checks no f-string syntax errors)

### Task 5: UPDATE `_run()` and the LLM call in `run_reflection()`

Replace the `async def _run()` inner function:

OLD: wrapped in `with file_lock(MEMORY_FILE)`, uses `allowed_tools=[...files...]`, `hooks={...}`, `max_turns=5`

NEW:
```python
    async def _run() -> None:
        nonlocal response_text
        async for message in query(
            prompt=reflection_prompt,
            options=ClaudeAgentOptions(
                allowed_tools=[],   # lean -- Python writes files, not the LLM
                max_turns=1,
            ),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text
            elif isinstance(message, ResultMessage):
                print(f"[{now_local()}] Reflection LLM completed: {message.subtype}")
```

- REMOVE: `with file_lock(MEMORY_FILE):` wrapper (now inside `apply_*` functions)
- REMOVE: `hooks` kwarg (soul-protect not needed when LLM cannot write files)
- REMOVE: `protect_soul` async function above `run_reflection()`
- VALIDATE: `python -c "import ast, pathlib; ast.parse(pathlib.Path('memory_reflect.py').read_text()); print('syntax ok')"`

### Task 6: UPDATE result-handling block after `asyncio.run(_run())`

Replace the post-`_run()` block (trim + state save + log):

```python
    # Parse structured output and apply changes
    parsed = parse_reflection_response(response_text)

    if parsed.get("_parse_error"):
        print(f"[{now_local()}] Reflection: could not parse LLM response — skipping")
        append_to_daily_log(f"**[Reflection]** Parse error — raw: {response_text[:200]}")
        return

    wrote_memory = apply_memory_additions(parsed["memory_additions"], date_str)
    wrote_user = apply_user_updates(parsed["user_updates"], date_str)

    # Trim MEMORY.md if it grew too large
    trim_memory_if_needed()

    # Save state
    state["last_run_date"] = today_str
    state["log_processed"] = date_str
    state["result"] = "REFLECTION_OK" if parsed["nothing_to_update"] else "promoted"
    save_state(REFLECTION_STATE_FILE, state)

    if parsed["nothing_to_update"] and not (wrote_memory or wrote_user):
        append_to_daily_log("REFLECTION_OK — nothing to promote from yesterday's log")
        print(f"[{now_local()}] Reflection OK — nothing to promote")
    else:
        append_to_daily_log(f"**[Reflection]** Promoted items from {date_str} to MEMORY.md/USER.md")
        print(f"[{now_local()}] Reflection complete — items promoted")
```

- VALIDATE: `python -c "import ast, pathlib; ast.parse(pathlib.Path('memory_reflect.py').read_text()); print('syntax ok')"`

### Task 7: UPDATE imports at top of `memory_reflect.py`

Final import block:

```python
import json
import re
...
from config import (
    DAILY_DIR,
    MEMORY_FILE,
    OWNER_NAME,
    REFLECTION_STATE_FILE,
    USER_FILE,
    VAULT_DIR,
    ensure_directories,
    get_today_log_path,
    now_local,
)
from sanitize import TRUST_BOUNDARY_INSTRUCTION, wrap_external_data
from sdk_compat import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)
from shared import append_to_daily_log, atomic_write, file_lock, load_state, save_state
```

- REMOVE: `HookMatcher` from sdk_compat imports (no longer used)
- REMOVE: `Any` from typing imports if only used by `protect_soul` (check first)
- VALIDATE: `python -c "import memory_reflect; print('imports ok')"`

### Task 8: CREATE `.claude/scripts/tests/test_memory_reflect.py`

```python
"""Unit tests for memory_reflect.py helpers -- no live API calls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory_reflect import (
    apply_memory_additions,
    apply_user_updates,
    parse_reflection_response,
    trim_memory_if_needed,
)


# --- parse_reflection_response ---

def test_parse_nothing_to_update():
    text = '{"memory_additions": [], "user_updates": [], "nothing_to_update": true}'
    result = parse_reflection_response(text)
    assert result["nothing_to_update"] is True
    assert result["memory_additions"] == []


def test_parse_with_additions():
    payload = {
        "memory_additions": ["- item one", "- item two"],
        "user_updates": ["- prefers short answers"],
        "nothing_to_update": False,
    }
    result = parse_reflection_response(json.dumps(payload))
    assert result["nothing_to_update"] is False
    assert len(result["memory_additions"]) == 2
    assert len(result["user_updates"]) == 1


def test_parse_fenced_json():
    text = "```json\n{\"memory_additions\": [\"- bullet\"], \"user_updates\": [], \"nothing_to_update\": false}\n```"
    result = parse_reflection_response(text)
    assert result["memory_additions"] == ["- bullet"]


def test_parse_malformed_returns_parse_error():
    result = parse_reflection_response("not json at all")
    assert result.get("_parse_error") is True
    assert result["nothing_to_update"] is True


def test_parse_missing_keys_defaults_to_empty():
    result = parse_reflection_response('{"nothing_to_update": false}')
    assert result["memory_additions"] == []
    assert result["user_updates"] == []


# --- apply_memory_additions ---

def test_apply_memory_additions_writes_section(tmp_path, monkeypatch):
    import memory_reflect
    mem_file = tmp_path / "MEMORY.md"
    mem_file.write_text("# Memory\n\n## Key Facts\n- existing\n", encoding="utf-8")
    monkeypatch.setattr(memory_reflect, "MEMORY_FILE", mem_file)

    result = apply_memory_additions(["- new item"], "2026-06-17")
    assert result is True
    content = mem_file.read_text(encoding="utf-8")
    assert "## 2026-06-17 Reflection" in content
    assert "- new item" in content
    assert "- existing" in content


def test_apply_memory_additions_empty_list_noop(tmp_path, monkeypatch):
    import memory_reflect
    mem_file = tmp_path / "MEMORY.md"
    mem_file.write_text("# Memory\n", encoding="utf-8")
    monkeypatch.setattr(memory_reflect, "MEMORY_FILE", mem_file)

    result = apply_memory_additions([], "2026-06-17")
    assert result is False
    assert mem_file.read_text(encoding="utf-8") == "# Memory\n"


def test_apply_memory_additions_creates_file_if_missing(tmp_path, monkeypatch):
    import memory_reflect
    mem_file = tmp_path / "MEMORY.md"
    monkeypatch.setattr(memory_reflect, "MEMORY_FILE", mem_file)

    result = apply_memory_additions(["- new item"], "2026-06-17")
    assert result is True
    assert mem_file.exists()
    assert "- new item" in mem_file.read_text(encoding="utf-8")


# --- apply_user_updates ---

def test_apply_user_updates_writes_section(tmp_path, monkeypatch):
    import memory_reflect
    user_file = tmp_path / "USER.md"
    user_file.write_text("# User\n", encoding="utf-8")
    monkeypatch.setattr(memory_reflect, "USER_FILE", user_file)

    result = apply_user_updates(["- prefers bullets"], "2026-06-17")
    assert result is True
    content = user_file.read_text(encoding="utf-8")
    assert "## 2026-06-17 Reflection" in content
    assert "- prefers bullets" in content


def test_apply_user_updates_empty_list_noop(tmp_path, monkeypatch):
    import memory_reflect
    user_file = tmp_path / "USER.md"
    user_file.write_text("# User\n", encoding="utf-8")
    monkeypatch.setattr(memory_reflect, "USER_FILE", user_file)

    result = apply_user_updates([], "2026-06-17")
    assert result is False


# --- trim_memory_if_needed ---

def test_trim_skips_when_small(tmp_path, monkeypatch):
    import memory_reflect
    mem_file = tmp_path / "MEMORY.md"
    mem_file.write_text("# Memory\n- line\n", encoding="utf-8")
    monkeypatch.setattr(memory_reflect, "MEMORY_FILE", mem_file)

    result = trim_memory_if_needed(max_lines=200)
    assert result is False


def test_trim_archives_overflow(tmp_path, monkeypatch):
    import memory_reflect
    mem_file = tmp_path / "MEMORY.md"
    mem_file.write_text("\n".join(f"- line {i}" for i in range(10)) + "\n", encoding="utf-8")
    monkeypatch.setattr(memory_reflect, "MEMORY_FILE", mem_file)
    monkeypatch.setattr(memory_reflect, "VAULT_DIR", tmp_path)

    result = trim_memory_if_needed(max_lines=5)
    assert result is True
    remaining = mem_file.read_text(encoding="utf-8").splitlines()
    assert len(remaining) <= 5
```

- VALIDATE: `uv run pytest tests/test_memory_reflect.py -v`

### Task 9: FORCE REFLECT on VPS to confirm end-to-end

After committing, pushing, and deploying:

```powershell
# Deploy
powershell -File "O:\AI\Dynamous\Courses\second-brain-workshop\scripts\deploy.ps1"

# Force reflection
ssh secondbrain@137.184.102.104 "cd /home/secondbrain/second-brain && .claude/scripts/.venv/bin/python .claude/scripts/memory_reflect.py --force 2>&1"

# Confirm MEMORY.md updated
ssh secondbrain@137.184.102.104 "tail -15 /home/secondbrain/second-brain/Memory/MEMORY.md"

# Confirm git status shows Memory/ modified
ssh secondbrain@137.184.102.104 "git -C /home/secondbrain/second-brain status --short Memory/"
```

---

## VALIDATION COMMANDS

### Level 1: Syntax
```powershell
cd "O:\AI\Dynamous\Courses\second-brain-workshop\.claude\scripts"
python -c "import ast, pathlib; ast.parse(pathlib.Path('memory_reflect.py').read_text()); print('syntax ok')"
```

### Level 2: Imports
```powershell
python -c "import memory_reflect; print('imports ok')"
```

### Level 3: Unit Tests
```powershell
uv run pytest tests/test_memory_reflect.py -v
uv run pytest tests/ -x -q --tb=short
```

### Level 4: Dry-Run
```powershell
uv run python memory_reflect.py --dry-run
```

### Level 5: Force Reflect VPS
```powershell
ssh secondbrain@137.184.102.104 ".claude/scripts/.venv/bin/python /home/secondbrain/second-brain/.claude/scripts/memory_reflect.py --force 2>&1"
ssh secondbrain@137.184.102.104 "tail -15 /home/secondbrain/second-brain/Memory/MEMORY.md"
```

Expected: new `## YYYY-MM-DD Reflection` section visible in MEMORY.md.

---

## ACCEPTANCE CRITERIA

- [ ] `memory_reflect.py` no longer uses `allowed_tools=["Read", "Write", "Edit",...]` in the reflection call
- [ ] `reflection_prompt` no longer says "Use the Edit tool"
- [ ] `reflection_prompt` requests JSON output per the defined schema
- [ ] `parse_reflection_response()` handles valid JSON, fenced JSON, missing keys, malformed
- [ ] `apply_memory_additions()` appends dated section to MEMORY.md via `file_lock` + `atomic_write`
- [ ] `apply_user_updates()` appends dated section to USER.md via `file_lock` + `atomic_write`
- [ ] `trim_memory_if_needed()` uses `VAULT_DIR / "Research"` not `Path("Memory/Research")`
- [ ] `protect_soul` async function removed (no longer needed)
- [ ] `HookMatcher` removed from imports
- [ ] All new tests pass: `uv run pytest tests/test_memory_reflect.py -v`
- [ ] Full suite passes: `uv run pytest tests/ -x -q` (173+ passed)
- [ ] VPS forced reflection writes to MEMORY.md (confirmed via tail + git status)
- [ ] Vault sync commits and pushes the change

---

## NOTES

### Why `allowed_tools=[]` is safe

`memory_reflect.py` already passes the full MEMORY.md and USER.md content in
context. Tool-based reads were redundant. Removing tools simplifies the call,
eliminates the soul-protect hook (SOUL.md cannot be edited if no Write tool
exists), and makes the script backend-neutral.

### Heartbeat has the same root cause — out of scope here

`heartbeat.py` line 674 also uses `allowed_tools=["Read", "Write", "Edit",...]`.
Heartbeat's tool use creates draft files and updates HABITS.md checkboxes — a more
complex structured-output schema. Note as follow-up:
`fix-heartbeat-codex-draft-creation.md`.

### False positive "promoted" state is fixed

The existing bug where `result = "promoted"` fires even when nothing was written
is corrected: the new logic uses `parsed["nothing_to_update"]` as the authoritative
signal, not whether response text avoids the literal string `"REFLECTION_OK"`.

### Confidence Score: 9/10

Self-contained change, all dependencies internal, established test pattern in
project. Only uncertainty: whether the Codex LLM reliably emits valid JSON when
asked. `parse_reflection_response` gracefully handles malformed responses.