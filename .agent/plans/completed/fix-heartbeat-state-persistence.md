# Feature: Fix Heartbeat State Persistence + Error Diagnostics

The following plan should be complete, but validate codebase patterns and task sanity before implementing.
Pay special attention to import ordering in config.py — path constants must be defined after PROJECT_ROOT.

## Feature Description

Two bugs found after Phase 9 deployment and documented in `handoff-heartbeat-state-vps.md`:

1. **State not persisting on VPS** — every heartbeat run shows `is_first_run=True` because
   `heartbeat-state.json` never survives between runs. Root cause: `config.py` defines
   `STATE_DIR`, `VAULT_DIR`, and `DATA_DIR` as relative `Path("...")` objects. When systemd
   runs the heartbeat from a working directory other than the project root, these resolve to
   the wrong location (or nowhere). The fix is to anchor every path constant in `config.py`
   to the absolute `PROJECT_ROOT` computed from `__file__`, which is CWD-independent.

2. **Heartbeat error log is opaque** — when the LLM call fails, the daily log records only
   the raw exception string. On 2026-06-14, the logged message was
   `Command failed with exit code 1 (exit code: 1)\nError output: Check stderr output for details`
   — useless for diagnosis. The fix adds the active backend name and a truncated traceback
   to the log entry so future failures identify the backend and root cause immediately.

## User Story

As Shaun (Second Brain operator),
I want the heartbeat to remember its last run state across executions and produce actionable error logs,
So that it diffs against real prior state (not a phantom first-run) and I can diagnose failures without SSH-ing in.

## Problem Statement

`config.py` has a split personality: `PROJECT_ROOT` is computed from `__file__` in the
Phase 6 section (line 109) but never used to anchor the Phase 1 path constants defined
at the top of the file (lines 10–19). Those top-of-file constants use bare `Path("Memory")`
and `Path(".claude/data")` — strings that resolve relative to whatever `os.getcwd()` is at
the moment of import, which under systemd is typically `/` or the service's `WorkingDirectory`.

On Windows Task Scheduler the CWD is usually set correctly, but the error at 20:00 on 2026-06-14
(`Command failed with exit code 1`) shows the `claude_code_sdk` backend was active (not Pi),
implying `SB_AGENT_BACKEND` wasn't set on that scheduler invocation or the fallback triggered.
Better diagnostics would have shown this immediately.

## Solution Statement

- Move `PROJECT_ROOT` to the very top of `config.py` (before all other path constants) and
  rewrite every top-of-file `Path("...")` to `PROJECT_ROOT / "..."`. The Phase 6 duplicate
  definition is then removed.
- Add `import traceback` and `BACKEND` to `heartbeat.py`'s imports; extend the LLM-error
  except block to log `[backend]`, the exception message, and a 800-char traceback tail.
- Add `tests/test_config.py` to assert all exported path constants are absolute and are
  children of `PROJECT_ROOT`.

## Feature Metadata

**Feature Type**: Bug Fix  
**Estimated Complexity**: Low  
**Primary Systems Affected**: `config.py`, `heartbeat.py`  
**Dependencies**: None (stdlib only changes)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `.claude/scripts/config.py` (lines 1–19) — Path constants to fix; all are relative today
- `.claude/scripts/config.py` (lines 108–110) — Duplicate `PROJECT_ROOT` definition to remove
- `.claude/scripts/heartbeat.py` (lines 40–75) — Import block; add `traceback` + `BACKEND` here
- `.claude/scripts/heartbeat.py` (lines 686–693) — The `asyncio.run(_run())` try/except to improve
- `.claude/scripts/pi_sdk_compat.py` (lines 449–458) — How Pi surfaces stderr in RuntimeError; confirms `pi failed (exit N): <detail>` format
- `.claude/scripts/tests/test_heartbeat.py` — Test pattern reference (monkeypatch, tmp_path, direct imports)
- `.claude/scripts/tests/conftest.py` — `sys.path.insert` pattern all test files use

### New Files to Create

- `.claude/scripts/tests/test_config.py` — Unit tests asserting path constants are absolute

### Patterns to Follow

**Test file header** (mirror `test_heartbeat.py` lines 1–14):
```python
"""Tests for config.py path constants."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
```

**Module-attribute monkeypatching** (used in `test_heartbeat.py` lines 104–106):
```python
monkeypatch.setattr(heartbeat, "DRAFTS_ACTIVE_DIR", active_dir)
```

**Error logging pattern** (existing style in `heartbeat.py` line 692):
```python
append_to_daily_log(f"**ERROR**: Heartbeat LLM failed — {e}")
```

**Absolute path derivation** (already used for INTEGRATIONS_DIR in `config.py` line 65):
```python
INTEGRATIONS_DIR = Path(__file__).resolve().parent / "integrations"
```
Mirror this pattern — same `__file__` anchor, just three `.parent` hops instead of one.

---

## IMPLEMENTATION PLAN

### Phase 1: Fix config.py path anchoring

Move `PROJECT_ROOT` to the top of the file and rewrite all relative path constants to use it.
Remove the now-duplicate `PROJECT_ROOT` definition in the Phase 6 section.

### Phase 2: Improve heartbeat.py error diagnostics

Add `traceback` import and `BACKEND` to the import block.
Extend the LLM-error except block to log backend name + traceback tail.

### Phase 3: Add test coverage

Create `tests/test_config.py` to assert path absoluteness and parentage.
Run the full test suite to confirm no regressions.

### Phase 4: Smoke-test on VPS (manual)

SSH to VPS, pull the fix, verify `heartbeat-state.json` is created at the correct absolute path
after `--force --dry-run`, then run `--force` to confirm Gemini quota is clear and a clean run
saves state correctly.

---

## STEP-BY-STEP TASKS

### TASK 1 — UPDATE `.claude/scripts/config.py` (path anchoring)

- **IMPLEMENT**: Add `PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent` as the
  first constant after the imports (before `VAULT_DIR`). Then change:
  - `VAULT_DIR = Path("Memory")` → `VAULT_DIR = PROJECT_ROOT / "Memory"`
  - `SCRIPTS_DIR = Path(".claude/scripts")` → `SCRIPTS_DIR = PROJECT_ROOT / ".claude/scripts"`
  - `DATA_DIR = Path(".claude/data")` → `DATA_DIR = PROJECT_ROOT / ".claude/data"`
  - All derived constants (`MEMORY_DIR`, `DAILY_DIR`, `DRAFTS_DIR`, `ACTIVE_DRAFTS_DIR`,
    `STATE_DIR`) remain unchanged — they inherit absoluteness from their parents.
  - In the Phase 6 section (~line 108–110), **REMOVE** the now-duplicate block:
    ```python
    # Project root — absolute, so scripts can resolve paths regardless of CWD
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    ```
- **GOTCHA**: `INTEGRATIONS_DIR` at line 65 already uses `Path(__file__).resolve().parent`
  — leave it as-is; it is already absolute.
- **GOTCHA**: `DATABASE_PATH` is defined as `DATA_DIR / "memory.db"` — it becomes absolute
  automatically once `DATA_DIR` is absolute. No change needed.
- **PATTERN**: Mirror the `INTEGRATIONS_DIR` derivation but go up three `.parent` hops:
  `Path(__file__).resolve().parent.parent.parent` (scripts → .claude → project root)
- **VALIDATE**: `cd .claude/scripts && python -c "from config import STATE_DIR, VAULT_DIR, DATA_DIR; print(STATE_DIR, VAULT_DIR, DATA_DIR); assert STATE_DIR.is_absolute(), 'not absolute'"`

### TASK 2 — UPDATE `.claude/scripts/heartbeat.py` (error diagnostics)

- **IMPLEMENT Part A** — Add `import traceback` to the stdlib imports block (near `import sys`,
  around line 31).
- **IMPLEMENT Part B** — Add `BACKEND` to the existing `sdk_compat` import (lines 61–68):
  ```python
  from sdk_compat import (
      BACKEND,
      AssistantMessage,
      ...
  )
  ```
- **IMPLEMENT Part C** — Replace the LLM-error except block (~lines 688–693):

  **Before:**
  ```python
  except Exception as e:
      print(f"[{now_local()}] Heartbeat LLM error: {e}")
      append_to_daily_log(f"**ERROR**: Heartbeat LLM failed — {e}")
      return
  ```

  **After:**
  ```python
  except Exception as e:
      _tb = traceback.format_exc()
      print(f"[{now_local()}] Heartbeat LLM error ({BACKEND} backend): {e}", file=sys.stderr)
      print(_tb, file=sys.stderr)
      append_to_daily_log(
          f"**ERROR**: Heartbeat LLM failed [{BACKEND} backend]\n"
          f"{e}\n\n```\n{_tb[-800:]}\n```"
      )
      return
  ```

- **GOTCHA**: `_tb` shadows nothing — it's a local variable inside the except block only.
  Use the underscore-prefix to signal it's ephemeral.
- **PATTERN**: `append_to_daily_log` already accepts multi-line strings (it just appends them).
  The triple-backtick fence is valid Markdown in Obsidian and will render clearly.
- **VALIDATE**: `cd .claude/scripts && python -c "import heartbeat"` — should import cleanly
  with no NameError on `traceback` or `BACKEND`.

### TASK 3 — CREATE `.claude/scripts/tests/test_config.py`

- **IMPLEMENT**: New test file asserting all path constants are absolute and children of PROJECT_ROOT:

```python
"""Tests for config.py — ensures path constants are absolute and CWD-independent."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config


def test_project_root_is_absolute():
    assert config.PROJECT_ROOT.is_absolute()


def test_vault_dir_is_absolute():
    assert config.VAULT_DIR.is_absolute()


def test_data_dir_is_absolute():
    assert config.DATA_DIR.is_absolute()


def test_state_dir_is_absolute():
    assert config.STATE_DIR.is_absolute()


def test_daily_dir_is_absolute():
    assert config.DAILY_DIR.is_absolute()


def test_state_dir_child_of_project_root():
    assert str(config.STATE_DIR).startswith(str(config.PROJECT_ROOT))


def test_vault_dir_child_of_project_root():
    assert str(config.VAULT_DIR).startswith(str(config.PROJECT_ROOT))


def test_data_dir_child_of_project_root():
    assert str(config.DATA_DIR).startswith(str(config.PROJECT_ROOT))
```

- **PATTERN**: `sys.path.insert` header mirrors `test_heartbeat.py` lines 13–14.
- **VALIDATE**: `cd .claude/scripts && uv run pytest tests/test_config.py -v`

### TASK 4 — RUN full test suite (regression check)

- **VALIDATE**: `cd .claude/scripts && uv run pytest tests/ -v`
- Expected: all previously-passing tests still pass; 8 new `test_config` tests pass.
- Total should increase from 155 → 163.

### TASK 5 — VERIFY on VPS (manual, post-deploy)

SSH in and run:
```bash
cd ~/second-brain

# Pull the fix
git pull

# Confirm state directory resolves to the right absolute path
.claude/scripts/.venv/bin/python -c "
from .claude.scripts.config import STATE_DIR, VAULT_DIR
print('STATE_DIR:', STATE_DIR)
print('VAULT_DIR:', VAULT_DIR)
assert STATE_DIR.is_absolute()
print('OK — paths are absolute')
"

# Or simpler via uv:
cd .claude/scripts
uv run python -c "from config import STATE_DIR; print(STATE_DIR); assert STATE_DIR.is_absolute()"

# Dry run (no LLM, just confirm data gathering works)
uv run python heartbeat.py --dry-run --force

# Check state file is now written to correct location
ls -la ~/second-brain/.claude/data/state/

# Force a full run (Gemini quota should be clear — resets midnight UTC = 10am AEST)
uv run python heartbeat.py --force

# Confirm state persisted
cat ~/second-brain/.claude/data/state/heartbeat-state.json
```

---

## TESTING STRATEGY

### Unit Tests

All tests use `pytest` + `monkeypatch` + `tmp_path`. No async test fixtures needed for these tasks
(only the heartbeat's `_run()` is async; the error block and config constants are synchronous).

New `test_config.py` tests are pure import-time assertions — no mocking or fixtures required.

### Edge Cases

- `config.py` imported from any CWD (e.g., `/`, `C:\Windows\System32`, the scripts dir itself)
  → all paths must be absolute and correct regardless
- `STATE_DIR.mkdir(parents=True, exist_ok=True)` called in `ensure_directories()` — verify this
  still works with the now-absolute path (it should; `Path.mkdir` works the same for absolute paths)

---

## VALIDATION COMMANDS

### Level 1 — Syntax check
```powershell
cd .claude/scripts
uv run python -c "import config; import heartbeat"
```

### Level 2 — New unit tests
```powershell
cd .claude/scripts
uv run pytest tests/test_config.py -v
```

### Level 3 — Full regression suite
```powershell
cd .claude/scripts
uv run pytest tests/ -v
```

### Level 4 — Manual path check (Windows)
```powershell
cd .claude/scripts
uv run python -c "from config import STATE_DIR, VAULT_DIR, DATA_DIR; print(STATE_DIR); print(VAULT_DIR); print(DATA_DIR)"
```
Expected: three absolute Windows paths starting with the project drive letter.

### Level 5 — Dry run heartbeat
```powershell
cd .claude/scripts
uv run python heartbeat.py --dry-run --force
```
Expected: snapshot printed, no errors, no CWD-relative path warnings.

---

## ACCEPTANCE CRITERIA

- [ ] `config.STATE_DIR.is_absolute()` returns `True` when imported from any working directory
- [ ] `config.VAULT_DIR.is_absolute()` returns `True` when imported from any working directory
- [ ] `config.DATA_DIR.is_absolute()` returns `True` when imported from any working directory
- [ ] `PROJECT_ROOT` is defined exactly once in `config.py` (at the top, before all path constants)
- [ ] After a VPS heartbeat run, `~/second-brain/.claude/data/state/heartbeat-state.json` exists
  and `is_first_run` is absent from the next run's diff log
- [ ] Heartbeat LLM failures log `[backend]` + truncated traceback in the daily log
- [ ] All 8 `test_config.py` tests pass
- [ ] Full test suite passes (163 tests, 0 failures)
- [ ] No regressions in existing heartbeat, guardrail, or integration tests

---

## COMPLETION CHECKLIST

- [ ] Task 1: config.py path anchoring complete; `PROJECT_ROOT` defined once at top
- [ ] Task 2: heartbeat.py imports `traceback` + `BACKEND`; except block logs backend + traceback
- [ ] Task 3: `tests/test_config.py` created with 8 assertions
- [ ] Task 4: Full test suite passes
- [ ] Task 5: VPS verified — state file persists between heartbeat runs

---

## NOTES

**Why not fix `INTEGRATIONS_DIR`?**
It's already absolute: `Path(__file__).resolve().parent / "integrations"`. No change needed.

**Why three `.parent` hops from `config.py`?**
`config.py` lives at `.claude/scripts/config.py`:
- `.parent` → `.claude/scripts/`
- `.parent.parent` → `.claude/`
- `.parent.parent.parent` → project root

**Gemini quota (transient, no code fix)**
The 20:00 error on 2026-06-14 was the `claude_code_sdk` backend failing (message format
`Command failed with exit code 1` is characteristic of `claude_code_sdk`, not Pi's
`RuntimeError("pi failed (exit N): ...")`). This implies `SB_AGENT_BACKEND` was not set to
`pi` for that scheduler invocation. The Gemini quota exhaustion on the VPS is a separate
issue. After the path fix, verify `SB_AGENT_BACKEND=pi` is set in the Task Scheduler action's
environment or `.env` file so Windows uses Pi (not claude_code_sdk).

**Confidence Score: 9/10**
The changes are surgical (two files, one new test file). The only risk is if a third file
imports these constants and re-resolves them relative to something unexpected — but all
callers import from `config.py` and receive the `Path` object directly, so absoluteness
is preserved at the import site.
