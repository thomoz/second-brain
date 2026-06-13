# Feature: Phase 8 — Security Hardening

The following plan should be complete, but validate codebase patterns and imports before
implementing each task. Pay special attention to hook response format (sys.exit(2) vs JSON),
sys.path patterns, and the false-positive exclusion list in block-secrets.py — omitting it
will cause the hook to block our own codebase files.

## Feature Description

Four security layers that protect API keys from accidental LLM exposure, sanitize all
external data before it reaches the LLM, and enforce security boundaries at the hook level
so they can never be bypassed regardless of what an email or WhatsApp message says.

Two new PreToolUse hooks (`block-secrets.py`, `command-guard.py`) are wired into
`settings.json` alongside the existing `soul-protect.py`. `sanitize.py` is already complete
from Phase 6 but sanitization must be wired into the two remaining unsanitized data paths:
`whatsapp.py`'s `format_messages_for_context()` and `engine.py`'s incoming message handler.

## User Story

As Shaun (a multi-business founder whose Second Brain reads emails, WhatsApp, and calendar),
I want every LLM tool call intercepted before it can touch credential files or run dangerous
commands,
So that a crafted email cannot trick the LLM into exfiltrating my API keys or running
destructive operations.

## Problem Statement

After Phase 7, the Second Brain reads email/calendar/WhatsApp content and passes it to the
LLM. A crafted message could attempt:
- **Direct read**: trick LLM into `Read(".env")` to surface API keys
- **Bash exfiltration**: `printenv | grep TOKEN` to dump secrets
- **Two-step attack**: write a `dump_env.py` script then execute it
- **Destructive ops**: `rm -rf Memory/` or `git push --force`

## Solution Statement

Two deterministic PreToolUse hooks (no LLM involved — pure regex/pattern matching) that
intercept all file and Bash tool calls before execution. Combined with the existing
`soul-protect.py`, every dangerous tool call is blocked at the hook layer with a clear
reason message.

## Feature Metadata

**Feature Type**: New Capability (Security)
**Estimated Complexity**: Medium
**Primary Systems Affected**: `.claude/hooks/`, `.claude/settings.json`, test suite
**Dependencies**: stdlib only (`json`, `re`, `sys`, `os`, `pathlib`) — no new packages

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `.claude/hooks/soul-protect.py` (full) — Existing hook that uses JSON output + sys.exit(0).
  New hooks use `sys.exit(2)` + stderr instead. Do not change soul-protect's format.
- `.claude/scripts/shared.py` (lines 98–135) — `DANGEROUS_BASH_PATTERNS` list. command-guard.py
  imports this. Must use `Path(__file__).resolve()` for the sys.path injection (not a relative
  string literal) because hooks can be invoked from any CWD.
- `.claude/scripts/sanitize.py` (full) — Already complete; no changes needed. Read to understand
  the `TRUST_BOUNDARY_INSTRUCTION` and `wrap_external_data` patterns already in use.
- `.claude/settings.json` (full) — Current hook wiring. Phase 8 adds two new PreToolUse entries.
  Block-secrets fires first (matcher: `Read|Bash|Grep|Edit|Write|Glob`), then command-guard
  (matcher: `Bash`), then soul-protect (matcher: `Write|Edit`). Ordering matters.
- `.claude/scripts/tests/test_sanitize.py` (full) — Mirror this test style for new tests.
  Class-per-group, method-per-case, descriptive names. No fixtures needed for hook tests.
- `.claude/scripts/tests/test_guardrail.py` (full) — Existing; do NOT touch this file.
  New hook tests go in separate files.

### Cole's Reference Files — READ THESE BEFORE IMPLEMENTING

- `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\hooks\block-secrets.py`
  (full, 338 lines) — Use this as the direct implementation reference. Our version extends
  it with Windows-specific patterns. The exit code 2 + stderr pattern comes from here.

### New Files to Create

```
.claude/hooks/block-secrets.py           — Layer 1: credential protection (Cole's base + Windows)
.claude/hooks/command-guard.py           — Layer 3: destructive command guardrails
.claude/scripts/tests/test_block_secrets.py  — Tests for block-secrets hook
.claude/scripts/tests/test_command_guard.py  — Tests for command-guard hook
```

### Files to Update

```
.claude/settings.json                    — Wire two new PreToolUse hooks
```

### Files to Update (additions from Cole's plan — not in original scope)

```
.claude/scripts/integrations/whatsapp.py — Add sanitize_external_text() to format_messages_for_context()
.claude/chat/engine.py                   — Add check_injection_patterns() logging on incoming WhatsApp text
.claude/scripts/shared.py               — Add git push --force + social media POST to DANGEROUS_BASH_PATTERNS
CLAUDE.md                               — Add Security section documenting active hooks and test commands
```

### Files NOT to Touch

```
.claude/scripts/sanitize.py             — Already complete (Phase 6)
.claude/hooks/soul-protect.py           — Already complete (Phase 6); keep JSON output format
.claude/scripts/tests/test_guardrail.py — Existing tests; do not modify
.claude/scripts/tests/test_sanitize.py  — Existing tests; do not modify
```

---

## PATTERNS TO FOLLOW

### Hook Response Format — Two Patterns in Use (Do Not Mix)

**Pattern A: JSON output** (used by soul-protect.py — keep as-is):
```python
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": "reason text",
    }
}))
sys.exit(0)
```

**Pattern B: sys.exit(2) + stderr** (Cole's pattern — use for block-secrets and command-guard):
```python
print(
    f"SECURITY: {reason}. "
    "API keys and credentials must never enter the context window.",
    file=sys.stderr,
)
sys.exit(2)
```

Use Pattern B for all new hooks. It is simpler and Claude Code displays stderr as a
tool-use error that the LLM sees as a block reason.

### sys.path Injection for Hooks (use __file__-relative, not CWD-relative)

```python
# command-guard.py needs to import from .claude/scripts/
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from shared import DANGEROUS_BASH_PATTERNS
```

### Subshell Extraction (mirror Cole's pattern exactly)

```python
import re
def all_segments(command: str):
    """Yield top-level command and any subshell contents."""
    yield command
    for sub in re.findall(r'\$\((.*?)\)', command, re.DOTALL):
        yield sub
    for sub in re.findall(r'`(.*?)`', command, re.DOTALL):
        yield sub
```

Apply recursively in `check_bash_command()` for nested subshells.

### Test Invocation Pattern for Hook Scripts

Hooks read from stdin. Test them by piping JSON directly:

```powershell
# Block test (expect exit code 2)
echo '{"tool_name":"Read","tool_input":{"file_path":".env"}}' | python .claude/hooks/block-secrets.py

# Allow test (expect exit code 0)
echo '{"tool_name":"Read","tool_input":{"file_path":"Memory/SOUL.md"}}' | python .claude/hooks/block-secrets.py

# Dangerous bash (expect exit code 2)
echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf Memory/"}}' | python .claude/hooks/command-guard.py
```

---

## IMPLEMENTATION PLAN

### Phase 1: block-secrets.py (Layer 1 — credential protection)

Build the credential-protection hook based on Cole's reference. Three additions beyond Cole's
verbatim code:

1. **Outlook/Gmail token patterns** — Cole covers `google_token.json` and `credentials.json`
   but not our per-account `token_gmail_*.json` or `outlook_token.json`. Add both.
2. **Windows PowerShell patterns** — Add `Get-Content.*\.env`, `$env:[A-Z_]*(TOKEN|KEY|SECRET)`,
   `Write-Host.*\$env:` to DANGEROUS_BASH_PATTERNS inside block-secrets.py (in addition to
   Cole's Unix patterns).
3. **WhatsApp token** — Add `whatsapp.*token` to SENSITIVE_FILE_PATTERNS (belt-and-suspenders;
   the .env block already covers the main risk).

**Critical: SECRET_FALSE_POSITIVES list** — Cole's pattern `re.compile(r"secret", re.IGNORECASE)`
would block reading `.claude/hooks/block-secrets.py` itself without the false-positive exclusion.
The exclusion list (`.py`, `.md`, `.ts`, `.js`, `.toml`, `.yaml`, `.txt`, `.yml`) MUST be
included or Phase 8 implementation will be self-blocking.

**EXFILTRATION_CONTENT_PATTERNS** — Cole's two-step attack defense checks the *content being
written* (Edit/Write tool) for scripts that would print/exfiltrate env vars. Include this
section verbatim — it catches the "write a dump_env.py then run it" attack vector.

### Phase 2: command-guard.py (Layer 3 — destructive command guardrails)

Separate concern from block-secrets: blocks destructive/dangerous operations (rm -rf, git
operations, package installs, payment API calls) using `DANGEROUS_BASH_PATTERNS` from
`shared.py`. This covers threat categories Cole doesn't have a separate file for, since his
`block-secrets.py` focuses only on credential exfiltration.

Import `DANGEROUS_BASH_PATTERNS` from shared.py (don't duplicate the list). Apply the same
subshell extraction and binary-path-prefix stripping as Cole's block-secrets.py.

### Phase 3: settings.json update

Add both hooks in correct order. All three PreToolUse hooks run independently — Claude Code
evaluates each matcher and runs matching hooks. Ordering within the array determines which
fires first when multiple match the same tool:

1. `block-secrets.py` on `Read|Bash|Grep|Edit|Write|Glob` (broadest — fires on all file tools)
2. `command-guard.py` on `Bash` (Bash only — destructive ops)
3. `soul-protect.py` on `Write|Edit` (SOUL.md protection — already wired)

### Phase 4: Tests

Mirror `test_sanitize.py` style. Two new test files — one per hook. Test via subprocess
(pipe JSON to stdin, check exit code + stderr) rather than importing hook internals directly,
since the hooks use sys.exit() and read from sys.stdin.

---

## STEP-BY-STEP TASKS

---

### Task 1: CREATE `.claude/hooks/block-secrets.py`

- **IMPLEMENT**: Cole's `block-secrets.py` verbatim as the base (lines 1–337 of reference)
- **ADD to SENSITIVE_FILE_PATTERNS**:
  ```python
  re.compile(r"token_gmail_\w+\.json", re.IGNORECASE),   # per-account Gmail tokens
  re.compile(r"outlook_token\.json", re.IGNORECASE),       # Outlook MSAL token
  re.compile(r"whatsapp.*token", re.IGNORECASE),           # GREEN-API token (belt+suspenders)
  ```
- **ADD to DANGEROUS_BASH_PATTERNS** (Windows PowerShell additions after Cole's Unix list):
  ```python
  # Windows PowerShell env/secret exposure
  (re.compile(r"Get-Content\b.*\.env\b", re.IGNORECASE), "Reading .env file with Get-Content"),
  (re.compile(r"\$env:[A-Z_]*(TOKEN|KEY|SECRET|PASSWORD|APIKEY)", re.IGNORECASE),
   "Accessing secret environment variable via PowerShell"),
  (re.compile(r"Write-Host\s+.*\$env:", re.IGNORECASE), "PowerShell printing env variable"),
  (re.compile(r"\[Environment\]::GetEnvironmentVariable.*(?:TOKEN|KEY|SECRET|PASSWORD)", re.IGNORECASE),
   "PowerShell GetEnvironmentVariable accessing secret"),
  ```
- **KEEP verbatim from Cole**: `SECRET_FALSE_POSITIVES`, `EXFILTRATION_CONTENT_PATTERNS`,
  `is_sensitive_file()`, `check_bash_command()`, `check_written_content()`, `main()`
- **RESPONSE FORMAT**: `sys.exit(2)` + stderr (Pattern B above) — already in Cole's code
- **GOTCHA**: Cole's `main()` uses `sys.exit(1)` on `json.JSONDecodeError`. Override this to
  `sys.exit(0)` — explicit fail-open per design principle 1. A malformed hook event should
  never block legitimate tool calls.
- **GOTCHA**: Do NOT remove `SECRET_FALSE_POSITIVES`. Without it, `block-secrets.py` blocks
  reading itself (filename contains "secret"). The false-positive list allows `.py` files.
- **GOTCHA**: `EXFILTRATION_CONTENT_PATTERNS` uses `re.IGNORECASE` without `re.DOTALL`,
  so patterns only match within a single line. This is intentional — avoids cross-line
  false positives in legitimate integration scripts.
- **VALIDATE**:
  ```powershell
  cd "O:/AI/Dynamous/Courses/second-brain-workshop"
  echo '{"tool_name":"Read","tool_input":{"file_path":".env"}}' | python .claude/hooks/block-secrets.py ; echo "Exit: $LASTEXITCODE"
  echo '{"tool_name":"Read","tool_input":{"file_path":"Memory/SOUL.md"}}' | python .claude/hooks/block-secrets.py ; echo "Exit: $LASTEXITCODE"
  echo '{"tool_name":"Bash","tool_input":{"command":"cat .env"}}' | python .claude/hooks/block-secrets.py ; echo "Exit: $LASTEXITCODE"
  echo '{"tool_name":"Read","tool_input":{"file_path":".claude/hooks/block-secrets.py"}}' | python .claude/hooks/block-secrets.py ; echo "Exit: $LASTEXITCODE"
  ```
  Expected: `.env` → exit 2 | `SOUL.md` → exit 0 | `cat .env` → exit 2 | `block-secrets.py` → exit 0

---

### Task 2: CREATE `.claude/hooks/command-guard.py`

- **IMPLEMENT**: Minimal script — reads stdin, checks only Bash tool calls, imports from shared.py
- **PATTERN**:
  ```python
  #!/usr/bin/env python3
  """PreToolUse hook: block dangerous bash commands (destructive ops, package installs)."""
  from __future__ import annotations

  import json
  import re
  import sys
  from pathlib import Path

  # __file__-relative path — robust regardless of hook invocation CWD
  sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
  from shared import DANGEROUS_BASH_PATTERNS

  _COMPILED = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_BASH_PATTERNS]

  # Strip binary path prefixes that could bypass pattern matching
  _PATH_PREFIXES = [
      "/usr/bin/", "/bin/", "/usr/local/bin/",
      "C:\\Windows\\System32\\", "C:\\Windows\\SysWOW64\\",
  ]

  def _strip_prefixes(cmd: str) -> str:
      for prefix in _PATH_PREFIXES:
          cmd = cmd.replace(prefix, "")
      return cmd

  def _all_segments(command: str):
      yield command
      for sub in re.findall(r'\$\((.*?)\)', command, re.DOTALL):
          yield sub
      for sub in re.findall(r'`(.*?)`', command, re.DOTALL):
          yield sub

  def check_command(command: str) -> str | None:
      normalized = _strip_prefixes(" ".join(command.split()))
      for segment in _all_segments(normalized):
          for pattern in _COMPILED:
              if pattern.search(segment):
                  return f"Blocked: matches dangerous pattern '{pattern.pattern}'"
      return None

  def main() -> None:
      try:
          data = json.load(sys.stdin)
      except json.JSONDecodeError:
          sys.exit(0)  # Malformed input — allow (fail open on parse errors)

      if data.get("tool_name") != "Bash":
          sys.exit(0)

      command = data.get("tool_input", {}).get("command", "")
      reason = check_command(command)

      if reason:
          print(
              f"SECURITY: {reason}. This command matches a dangerous pattern and cannot "
              "be executed autonomously. Ask Shaun to run it manually if needed.",
              file=sys.stderr,
          )
          sys.exit(2)

      sys.exit(0)

  if __name__ == "__main__":
      main()
  ```
- **GOTCHA**: `shared.py` has `\beval\b` which matches the word "eval" anywhere. This is
  intentional — shell eval is dangerous. But if a legitimate test script uses the string
  "eval" in a comment, it would also be blocked. Accept this trade-off.
- **GOTCHA**: `subprocess.*shell\s*=\s*True` is in DANGEROUS_BASH_PATTERNS. This could block
  writing scripts that pass `shell=True` to subprocess. Accept this trade-off.
- **VALIDATE**:
  ```powershell
  cd "O:/AI/Dynamous/Courses/second-brain-workshop"
  echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf Memory/"}}' | python .claude/hooks/command-guard.py ; echo "Exit: $LASTEXITCODE"
  echo '{"tool_name":"Bash","tool_input":{"command":"uv run python heartbeat.py"}}' | python .claude/hooks/command-guard.py ; echo "Exit: $LASTEXITCODE"
  echo '{"tool_name":"Bash","tool_input":{"command":"git status"}}' | python .claude/hooks/command-guard.py ; echo "Exit: $LASTEXITCODE"
  echo '{"tool_name":"Read","tool_input":{"file_path":"Memory/SOUL.md"}}' | python .claude/hooks/command-guard.py ; echo "Exit: $LASTEXITCODE"
  ```
  Expected: `rm -rf` → exit 2 | `uv run` → exit 0 | `git status` → exit 0 | Read tool → exit 0

---

### Task 3: UPDATE `.claude/settings.json`

- **IMPLEMENT**: Add two new PreToolUse hook entries. Keep all existing hooks unchanged.
- **PATTERN** (full replacement of settings.json):
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
          "matcher": "Read|Bash|Grep|Edit|Write|Glob",
          "hooks": [
            {
              "type": "command",
              "command": "python .claude/hooks/block-secrets.py",
              "timeout": 10
            }
          ]
        },
        {
          "matcher": "Bash",
          "hooks": [
            {
              "type": "command",
              "command": "python .claude/hooks/command-guard.py",
              "timeout": 10
            }
          ]
        },
        {
          "matcher": "Write|Edit",
          "hooks": [
            {
              "type": "command",
              "command": "python .claude/hooks/soul-protect.py",
              "shell": "powershell",
              "timeout": 10
            }
          ]
        }
      ]
    }
  }
  ```
- **GOTCHA**: Hook order matters. `block-secrets` before `command-guard` means credential
  checks run first. A Bash command that tries both `cat .env` and `rm -rf /` will be blocked
  by block-secrets before command-guard even runs.
- **GOTCHA**: `soul-protect.py` retains `"shell": "powershell"` — do not remove it.
- **VALIDATE**:
  ```powershell
  # Validate JSON syntax
  python -c "import json; json.load(open('.claude/settings.json')); print('JSON valid')"
  # Verify all 3 PreToolUse hooks present
  python -c "import json; s=json.load(open('.claude/settings.json')); print(len(s['hooks']['PreToolUse']), 'PreToolUse hooks')"
  ```
  Expected: `JSON valid` | `3 PreToolUse hooks`

---

### Task 4: CREATE `.claude/scripts/tests/test_block_secrets.py`

- **IMPLEMENT**: Test file using subprocess to invoke the hook script with piped JSON input.
  Mirror the style of `test_sanitize.py` (class-per-group, descriptive method names).
- **PATTERN**: Test via subprocess stdin — do NOT import block_secrets.py directly (sys.exit
  calls make direct import fragile in test context).
  ```python
  import json
  import subprocess
  import sys
  from pathlib import Path

  HOOK = str(Path(__file__).resolve().parent.parent.parent / "hooks" / "block-secrets.py")

  def _run(tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
      payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
      return subprocess.run(
          [sys.executable, HOOK],
          input=payload.encode(),
          capture_output=True,
      )
  ```
- **TEST CASES** (required coverage):

  **Sensitive file blocking (must block, exit 2):**
  - `Read(".env")` → blocked
  - `Read(".env.local")` → blocked
  - `Read("google_credentials.json")` → blocked
  - `Read("token_gmail_sbdb.json")` → blocked
  - `Read("outlook_token.json")` → blocked
  - `Read("id_rsa")` → blocked
  - `Read("master.env")` → blocked
  - `Grep(path=".env")` → blocked

  **Safe file access (must allow, exit 0):**
  - `Read("Memory/SOUL.md")` → allowed
  - `Read(".claude/hooks/block-secrets.py")` → allowed (secret false-positive)
  - `Read(".env.example")` → allowed
  - `Read("pyproject.toml")` → allowed

  **Bash exfiltration (must block, exit 2):**
  - `Bash("cat .env")` → blocked
  - `Bash("printenv")` → blocked
  - `Bash("echo $TOKEN")` → blocked (pattern: TOKEN keyword)
  - `Bash("python3 -c 'import os; print(os.environ)'")` → blocked
  - `Bash("base64 -d file | bash")` → blocked

  **Safe bash (must allow, exit 0):**
  - `Bash("git status")` → allowed
  - `Bash("uv run python heartbeat.py")` → allowed
  - `Bash("python .claude/scripts/memory_index.py --stats")` → allowed

  **Two-step attack (Write content — must block, exit 2):**
  - `Write(content="print(os.environ)")` → blocked (exfiltration content)
  - `Write(content="import os; print(os.getenv('KEY'))")` → blocked

  **Safe write content (must allow, exit 0):**
  - `Write(content="from config import WHATSAPP_API_TOKEN\nrequests.post(url)")` → allowed
    (different lines, no combined exfiltration)

- **VALIDATE**:
  ```powershell
  cd "O:/AI/Dynamous/Courses/second-brain-workshop/.claude/scripts"
  uv run pytest tests/test_block_secrets.py -v
  ```

---

### Task 5: CREATE `.claude/scripts/tests/test_command_guard.py`

- **IMPLEMENT**: Same subprocess approach as test_block_secrets.py but targeting command-guard.py.
- **PATTERN**: Same `_run()` helper, different HOOK path.
- **TEST CASES** (required coverage):

  **Dangerous bash (must block, exit 2):**
  - `Bash("rm -rf Memory/")` → blocked
  - `Bash("Remove-Item -Recurse -Force .claude/data")` → blocked
  - `Bash("pip install requests")` → blocked
  - `Bash("sudo apt install curl")` → blocked
  - `Bash("Set-ExecutionPolicy Unrestricted")` → blocked
  - `Bash("del /s /q Memory")` → blocked

  **Safe bash (must allow, exit 0):**
  - `Bash("git status")` → allowed
  - `Bash("git log --oneline -5")` → allowed
  - `Bash("uv run python heartbeat.py --dry-run")` → allowed
  - `Bash("python .claude/scripts/memory_search.py 'karaoke'")` → allowed

  **Non-Bash tools (must allow, exit 0):**
  - `Read("Memory/SOUL.md")` → allowed (command-guard is Bash-only)
  - `Write(file_path="Memory/daily/2026-06-13.md", content="test")` → allowed

- **VALIDATE**:
  ```powershell
  cd "O:/AI/Dynamous/Courses/second-brain-workshop/.claude/scripts"
  uv run pytest tests/test_command_guard.py -v
  ```

---

### Task 6: UPDATE `.claude/scripts/shared.py` — Add missing DANGEROUS_BASH_PATTERNS

- **WHY**: Cole's `command-guard.py` description includes "unauthorized POST, automated writes
  outside vault". Our current `DANGEROUS_BASH_PATTERNS` has no social media POST patterns and
  no `git push --force` guard.
- **ADD** to the end of `DANGEROUS_BASH_PATTERNS` in `shared.py`:
  ```python
  # Social media / outbound POST guard (never auto-post)
  r"curl\s+.*-X\s+POST.*(?:twitter|instagram|linkedin|facebook|tiktok|reddit|api\.openai)",
  r"curl\s+.*(?:twitter|instagram|linkedin|facebook|tiktok).*-X\s+POST",
  r"wget\s+.*--post-data.*(?:twitter|instagram|linkedin|facebook)",
  # Git push guard (never push without explicit approval)
  r"git\s+push\s+.*--force",
  r"git\s+push\s+.*-f\b",
  # Writes outside Memory/ vault (catches absolute path writes to system dirs)
  r">\s*/(?!tmp|var/tmp)[a-z]",
  ```
- **GOTCHA**: Keep the list in sync with `pi_ext/pi_safety.ts` — add the same patterns there
  in the TypeScript equivalent. The comment `# Keep this list in sync` already exists in shared.py.
- **VALIDATE**:
  ```powershell
  cd "O:/AI/Dynamous/Courses/second-brain-workshop"
  python -c "from .claude.scripts.shared import DANGEROUS_BASH_PATTERNS; print(len(DANGEROUS_BASH_PATTERNS), 'patterns')"
  # Or from scripts dir:
  cd "O:/AI/Dynamous/Courses/second-brain-workshop/.claude/scripts"
  uv run python -c "from shared import DANGEROUS_BASH_PATTERNS; print(len(DANGEROUS_BASH_PATTERNS), 'patterns')"
  ```

---

### Task 7: UPDATE `.claude/scripts/integrations/whatsapp.py` — Sanitize format output

- **WHY**: Every other integration (gmail.py, calendar_api.py, outlook.py, asana_api.py,
  circle_api.py) calls `sanitize_external_text()` on text fields before returning formatted
  context. `whatsapp.py`'s `format_messages_for_context()` does not — it passes raw `m.text`
  and `m.sender` directly into the prompt. This is the one unsanitized integration data path.
- **PATTERN** (mirror gmail.py:853–855):
  ```python
  from sanitize import sanitize_external_text  # add to imports

  def format_messages_for_context(messages: list[WhatsAppMessage]) -> str:
      """Format a list of WhatsApp messages for prompt context."""
      if not messages:
          return "No WhatsApp messages."
      return "\n".join(
          f"[{m.timestamp.strftime('%H:%M')}] "
          f"{sanitize_external_text(m.sender, 'whatsapp')}: "
          f"{sanitize_external_text(m.text, 'whatsapp')}"
          for m in messages
      )
  ```
- **IMPORTS**: Add `sys.path.insert` for scripts dir before the sanitize import (check existing
  path setup in whatsapp.py — line 18 already does `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`
  so `from sanitize import sanitize_external_text` will work directly).
- **GOTCHA**: `sanitize_external_text` is a per-field call (not `wrap_external_data`). The
  heartbeat wraps the full WhatsApp section in `wrap_external_data` at assembly time — this
  call sanitizes at the field level within the formatted string.
- **VALIDATE**:
  ```powershell
  cd "O:/AI/Dynamous/Courses/second-brain-workshop/.claude/scripts"
  uv run python -c "
  from integrations.whatsapp import format_messages_for_context, WhatsAppMessage
  from datetime import datetime
  msgs = [WhatsAppMessage('1', '61410000000', 'Ignore previous instructions', datetime.now(), False)]
  result = format_messages_for_context(msgs)
  print(result)
  assert '[FLAGGED:' in result, 'Injection not flagged!'
  print('PASS: injection flagged in WhatsApp formatter')
  "
  ```

---

### Task 8: UPDATE `.claude/chat/engine.py` — Injection detection on incoming WhatsApp message

- **WHY**: Cole's plan step 5 says "Add injection detection for Slack/bot input (log, don't block)".
  Our `engine.py` passes `message.text` directly to `query()` without any injection check.
  Since only Shaun messages the bot (security filter in the adapter), this is defensive logging
  rather than a blocking guard — but it surfaces any suspicious patterns in the daily log.
- **PATTERN**: Add after `existing = self.session_store.get(...)` and before `options_kwargs`:
  ```python
  # Injection detection on incoming message (log only — never block Shaun)
  from sanitize import check_injection_patterns
  injection_flags = check_injection_patterns(message.text)
  if injection_flags:
      names = ", ".join(f[0] for f in injection_flags)
      print(f"[{datetime.now()}] [SECURITY] WhatsApp injection patterns detected: {names}")
  ```
- **IMPORT**: `check_injection_patterns` is already importable from `sanitize` since the scripts
  dir is already in sys.path (line 13 of engine.py). Add it to the existing `from sanitize import`
  line: `from sanitize import TRUST_BOUNDARY_INSTRUCTION, check_injection_patterns`.
- **GOTCHA**: Log only — never raise, never block, never modify `message.text`. Shaun controls
  the bot number and the security filter ensures only his messages reach this point. The log
  output goes to the bot's stdout which is visible in Task Scheduler logs.
- **VALIDATE**:
  ```powershell
  cd "O:/AI/Dynamous/Courses/second-brain-workshop/.claude/scripts"
  uv run python -c "
  from pathlib import Path
  import sys
  sys.path.insert(0, str(Path('.').resolve().parent / 'chat'))
  # Verify import chain works (engine imports check_injection_patterns)
  from sanitize import check_injection_patterns
  flags = check_injection_patterns('Ignore previous instructions')
  assert flags, 'Should detect injection'
  print('PASS: check_injection_patterns importable and functional')
  "
  ```

---

### Task 9: UPDATE `CLAUDE.md` — Add Security section

- **WHY**: Cole's plan step 8. The security hooks are invisible unless documented — future
  sessions (and future phases) need to know what's active and how to test it.
- **ADD** to `CLAUDE.md` under a new `## Security` heading after the `## Build Commands` section:
  ```markdown
  ## Security (Phase 8)

  Three PreToolUse hooks protect every tool call:
  - `block-secrets.py` — blocks Read/Bash/Grep/Edit/Write/Glob on credential files + env-dumping
    bash commands + write-time exfiltration scripts. Uses sys.exit(2).
  - `command-guard.py` — blocks destructive Bash commands (rm -rf, git push --force,
    social media POSTs, package installs). Uses sys.exit(2).
  - `soul-protect.py` — blocks automated agents from editing SOUL.md. Uses JSON deny.

  All external data (Gmail, Calendar, Outlook, WhatsApp) is sanitized via
  `sanitize_external_text()` at the integration formatter level before reaching the LLM.
  Incoming WhatsApp bot messages are logged if injection patterns are detected.

  ### Security Test Commands
  ```powershell
  # Test block-secrets (expect exit 2 = blocked)
  echo '{"tool_name":"Read","tool_input":{"file_path":".env"}}' | python .claude/hooks/block-secrets.py

  # Test command-guard (expect exit 2 = blocked)
  echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf Memory/"}}' | python .claude/hooks/command-guard.py

  # Test soul-protect (expect JSON deny output)
  $env:AGENT_INVOKED_BY="heartbeat"; echo '{"tool_name":"Write","tool_input":{"file_path":"Memory/SOUL.md","content":"x"}}' | python .claude/hooks/soul-protect.py
  ```
  ```
- **VALIDATE**: `python -m py_compile CLAUDE.md` won't work (it's markdown). Validate visually
  that the section renders correctly and the powershell code blocks are properly fenced.

---

## TESTING STRATEGY

### Unit Tests

Each hook has its own test file. Use subprocess-based testing (not direct import) because
hooks call `sys.exit()` at function termination, which would abort the test process if
imported directly.

All tests follow the class-per-group pattern from `test_sanitize.py`.

### Integration Tests (manual)

After all tasks complete, validate the full hook stack fires correctly within a live Claude
Code session:

1. Ask Claude: `Read the file .env` — should see hook block with SECURITY message
2. Ask Claude: `Run rm -rf .claude/data/` — should see hook block
3. Ask Claude: `Read Memory/SOUL.md` — should succeed normally
4. Ask Claude: `Write a test file to Memory/test.md` — should succeed normally

### Edge Cases to Test

- Subshell bypass: `$(cat .env)` inside a larger bash command — must be blocked
- Path prefix bypass: `/usr/bin/cat .env` — must be blocked (prefixes stripped)
- Wildcard bypass: `cat .en*` — must be blocked (Cole's pattern covers this)
- False positive: reading `block-secrets.py` itself — must be allowed
- False positive: reading `.env.example` — must be allowed

---

## VALIDATION COMMANDS

### Level 1: Syntax Check

```powershell
cd "O:/AI/Dynamous/Courses/second-brain-workshop"
python -m py_compile .claude/hooks/block-secrets.py && echo "block-secrets.py: OK"
python -m py_compile .claude/hooks/command-guard.py && echo "command-guard.py: OK"
python -c "import json; json.load(open('.claude/settings.json')); print('settings.json: OK')"
python -m py_compile .claude/scripts/integrations/whatsapp.py && echo "whatsapp.py: OK"
python -m py_compile .claude/chat/engine.py && echo "engine.py: OK"
python -m py_compile .claude/scripts/shared.py && echo "shared.py: OK"
```

### Level 2: Hook Smoke Tests

```powershell
cd "O:/AI/Dynamous/Courses/second-brain-workshop"
# block-secrets — should block
echo '{"tool_name":"Read","tool_input":{"file_path":".env"}}' | python .claude/hooks/block-secrets.py
echo "block-secrets .env exit: $LASTEXITCODE"

# block-secrets — should allow
echo '{"tool_name":"Read","tool_input":{"file_path":"Memory/SOUL.md"}}' | python .claude/hooks/block-secrets.py
echo "block-secrets SOUL.md exit: $LASTEXITCODE"

# command-guard — should block
echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf Memory/"}}' | python .claude/hooks/command-guard.py
echo "command-guard rm exit: $LASTEXITCODE"

# command-guard — should allow
echo '{"tool_name":"Bash","tool_input":{"command":"git status"}}' | python .claude/hooks/command-guard.py
echo "command-guard git exit: $LASTEXITCODE"
```

Expected exit codes: `.env` → 2, `SOUL.md` → 0, `rm -rf` → 2, `git status` → 0

### Level 3: Full Test Suite

```powershell
cd "O:/AI/Dynamous/Courses/second-brain-workshop/.claude/scripts"
uv run pytest tests/test_block_secrets.py tests/test_command_guard.py -v
uv run pytest tests/ -v  # Full suite — confirm no regressions
```

### Level 4: Settings Validation

```powershell
cd "O:/AI/Dynamous/Courses/second-brain-workshop"
python -c "
import json
s = json.load(open('.claude/settings.json'))
ptu = s['hooks']['PreToolUse']
print(f'PreToolUse hooks: {len(ptu)}')
for h in ptu:
    cmd = h['hooks'][0]['command']
    print(f'  matcher={h[\"matcher\"]!r} -> {cmd}')
"
```

Expected output:
```
PreToolUse hooks: 3
  matcher='Read|Bash|Grep|Edit|Write|Glob' -> python .claude/hooks/block-secrets.py
  matcher='Bash' -> python .claude/hooks/command-guard.py
  matcher='Write|Edit' -> python .claude/hooks/soul-protect.py
```

### Level 5: Live Hook Verification (post-implementation, in Claude Code session)

```
Ask Claude: "Read the file .env"
Expected: SECURITY block message, tool call denied

Ask Claude: "Run git status"
Expected: Succeeds normally

Ask Claude: "Read Memory/SOUL.md"
Expected: Succeeds normally
```

---

## ACCEPTANCE CRITERIA

- [ ] `block-secrets.py` blocks `.env`, all token JSON files, SSH keys, and credential files
- [ ] `block-secrets.py` blocks bash exfiltration patterns (cat .env, printenv, echo $TOKEN, etc.)
- [ ] `block-secrets.py` blocks write-time exfiltration (content containing `print(os.environ)`)
- [ ] `block-secrets.py` allows reading `.py`, `.md`, `.ts` files that mention "secret" (false-positive list works)
- [ ] `block-secrets.py` allows `.env.example`
- [ ] `command-guard.py` blocks `rm -rf`, `Remove-Item -Recurse -Force`, `del /s`
- [ ] `command-guard.py` blocks `pip install`, `npm install`, `sudo`, `Set-ExecutionPolicy Unrestricted`
- [ ] `command-guard.py` allows `git status`, `uv run`, `python` scripts
- [ ] `command-guard.py` only fires on Bash tool (not Read, Write, Edit)
- [ ] `shared.py` has `git push --force` and social media POST patterns
- [ ] `settings.json` has 3 PreToolUse hooks in correct order
- [ ] `whatsapp.py` `format_messages_for_context()` calls `sanitize_external_text()` on text and sender
- [ ] `engine.py` logs injection detections on incoming WhatsApp messages (does not block)
- [ ] `CLAUDE.md` has a Security section with active hooks listed and test commands
- [ ] All new tests pass (`test_block_secrets.py`, `test_command_guard.py`)
- [ ] Full test suite passes with zero regressions (`uv run pytest tests/ -v`)
- [ ] `soul-protect.py` still works (JSON output format unchanged)

---

## COMPLETION CHECKLIST

- [ ] Task 1: `block-secrets.py` created and smoke-tested
- [ ] Task 2: `command-guard.py` created and smoke-tested
- [ ] Task 3: `settings.json` updated and validated
- [ ] Task 4: `test_block_secrets.py` created and passing
- [ ] Task 5: `test_command_guard.py` created and passing
- [ ] Task 6: `shared.py` DANGEROUS_BASH_PATTERNS extended
- [ ] Task 7: `whatsapp.py` formatter sanitized
- [ ] Task 8: `engine.py` injection logging added
- [ ] Task 9: `CLAUDE.md` Security section added
- [ ] Full test suite green
- [ ] Manual live hook verification in Claude Code session
- [ ] All acceptance criteria checked

---

## NOTES

### Cole's Key Design Principles (apply these throughout implementation)

1. **Fail-open on malformed hook input** — if `json.load(sys.stdin)` raises `JSONDecodeError`,
   use `sys.exit(0)` (allow) not `sys.exit(1)` or `sys.exit(2)`. Safety over lockout: a broken
   hook should never prevent legitimate work. Cole's reference uses `sys.exit(1)` — we use `sys.exit(0)`
   to be explicitly fail-open. Our `command-guard.py` template already has this correct.
   Ensure `block-secrets.py` does too.

2. **Sanitization at the format choke point** — `sanitize_external_text()` is called inside each
   integration's formatter function (not at the LLM call site). This means every integration that
   gets added in future phases automatically gets sanitization for free. Task 7 completes the last
   missing integration (whatsapp.py).

3. **Log-don't-block for WhatsApp bot input** — when injection patterns are detected in an incoming
   WhatsApp message, log the detection but always pass the message through. The user (Shaun) controls
   the input; blocking creates lockout. Task 8 implements this.

4. **Write restrictions only apply to automated processes, not interactive sessions** — this applies
   specifically to `soul-protect.py` (uses `AGENT_INVOKED_BY` check — already implemented in Phase 6).
   `block-secrets.py` and `command-guard.py` do NOT check `AGENT_INVOKED_BY` — credential protection
   and destructive-command blocking apply universally regardless of who drives the session.
   Cole's `block-secrets.py` has no `AGENT_INVOKED_BY` check — confirmed.

5. **Three separate hooks, clean separation of concerns** — block-secrets (credential exfiltration),
   command-guard (destructive ops), soul-protect (memory integrity). Do not merge them. Each has a
   different matcher, different threat model, and different response format.

---

### Why two hooks instead of one?

Cole consolidates everything in `block-secrets.py`. We split into two because:
- `block-secrets.py` focuses on credential exfiltration (a single threat category)
- `command-guard.py` covers destructive/dangerous operations (a separate threat category)
- `shared.py`'s `DANGEROUS_BASH_PATTERNS` already exists and is referenced by `pi_safety.ts`
  — consolidating into block-secrets would create divergence with the TypeScript safety layer

### hook response format divergence (JSON vs exit 2)

`soul-protect.py` uses JSON output (Pattern A). New hooks use sys.exit(2) (Pattern B).
Both are valid Claude Code hook response formats. Do not "fix" soul-protect to use exit 2
— it's working correctly and changing it would be unnecessary churn.

### sanitize.py is already done

`sanitize.py` and `TRUST_BOUNDARY_INSTRUCTION` are complete from Phase 6 and match Cole's
reference exactly. They are already injected into every heartbeat and chat system prompt.
Phase 8 adds no changes to sanitize.py — it is Layer 2 and is already deployed.

### .gitignore is already correct

All credential files (`.env`, `token_gmail_*.json`, `outlook_token.json`) are already in
`.gitignore` from Phase 4. Phase 8 adds no new .gitignore entries.

### Confidence Score: 9/10

The architecture is clear, Cole's reference is comprehensive and readable, and the two new
files are self-contained with no new dependencies. The one risk is false-positive tuning —
particularly the `EXFILTRATION_CONTENT_PATTERNS` write-check against our own integration
scripts. The test suite should catch any regressions before they affect live sessions.
