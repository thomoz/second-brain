# Feature: WhatsApp Save Commands â€” VPS Vault Pipeline

The following plan should be complete, but validate codebase patterns and task sanity before implementing.
Pay special attention to the `_load_vault_context()` pattern â€” every new loader must follow it exactly.
All writes go inside `Memory/` only. The sandbox is already `workspace-write` for tool-using calls.

## Feature Description

Enable Shaun to say "save this to Juno characters" or "remind me to X" in WhatsApp (often via
CarPlay) and have the VPS bot write the content directly to the correct vault file immediately â€”
not deferred to the 8am reflection. A new `Memory/ASSISTANT.md` manifest defines all routing
rules and is injected into the system prompt so the LLM handles intent detection and routing
via the existing `Write` tool. WebSearch is also enabled in `allowed_tools` so the bot can
answer research questions.

## User Story

As Shaun (multi-business founder driving 12â€“15 hrs/week)
I want to dictate "save this to Juno characters" via CarPlay
So that vault content is written immediately without waiting for the 8am reflection cycle

## Problem Statement

WhatsApp messages are logged to daily logs and reflected at 8am AEST into entity pages. But
when Shaun dictates something important mid-drive, there's no way to route it directly to the
right vault file in real time. The existing `Write` tool is in `allowed_tools` but the LLM has
no routing instructions. The system prompt has no save command manifest. WebSearch is wired in
the backend (`codex_sdk_compat.py:145,148`) but missing from `allowed_tools`, so the bot can't
answer live research questions.

## Solution Statement

1. Create `Memory/ASSISTANT.md` â€” the personal assistant command manifest. Defines trigger
   phrases, routing table, save format, confirmation rules, and new-entity flow.
2. Add `_load_assistant_commands()` to `engine.py` following the exact pattern of
   `_load_vault_context()` (line 12). Inject its output into `system_prompt` always.
3. Add `"WebSearch"` to `allowed_tools` in `engine.py:222`.
4. Clean up `Memory/scratch.md` â€” remove `## Unsorted` section (only Reminders + Ideas needed).
5. Discovery task: verify Write tool works live on VPS under Codex's workspace-write sandbox.
6. Add unit tests covering the new loader and the updated `allowed_tools`.

## Feature Metadata

**Feature Type**: Enhancement  
**Estimated Complexity**: Low  
**Primary Systems Affected**: `engine.py`, `Memory/ASSISTANT.md`, `Memory/scratch.md`  
**Dependencies**: None new â€” Write and WebSearch already wired in `codex_sdk_compat.py`

---

## CONTEXT REFERENCES

### Relevant Codebase Files â€” READ BEFORE IMPLEMENTING

- `.claude/chat/engine.py` (lines 12â€“26) â€” `_load_vault_context()`: the exact pattern to mirror
  for `_load_assistant_commands()`. Pre-loads file in Python so LLM never needs a Read tool call
  (Read fails on VPS under bwrap).
- `.claude/chat/engine.py` (lines 187â€“225) â€” `handle_message()`: system_prompt construction and
  `allowed_tools`. This is where ASSISTANT.md content gets appended and WebSearch gets added.
- `.claude/chat/engine.py` (line 222) â€” `allowed_tools: ["Read", "Glob", "Grep", "Write"]`.
  Add `"WebSearch"` here.
- `.claude/scripts/codex_sdk_compat.py` (lines 145â€“149) â€” `_WEB_TOOLS` and `_wants_web()`:
  WebSearch is already handled â€” adding it to `allowed_tools` is all that's needed.
- `.claude/scripts/codex_sdk_compat.py` (lines 374â€“383) â€” sandbox config: tool-using calls use
  `workspace-write` (not read-only), network access enabled. Write tool should work here.
- `Memory/SOUL.md` â€” rule: "Never modify files outside Memory/". ASSISTANT.md must reinforce
  this â€” all save commands write to `Memory/` only.
- `Memory/scratch.md` â€” current structure has Reminders, Ideas, Unsorted. Remove Unsorted.
- `Memory/entities/juno-wonderdog/` â€” 4 sub-files: index.md, characters.md, story.md,
  development.md. LLM routes by content type.
- `Memory/entities/simone-kensington/` â€” same 4 sub-files.
- `.claude/scripts/tests/test_chat_engine.py` â€” full mock pattern for engine tests. Mirror
  `test_handle_message_new_session` for new loader tests (patch `engine.query`, use
  `_make_incoming()` fixture).

### New Files to Create

- `Memory/ASSISTANT.md` â€” personal assistant command manifest (injected into system prompt)

### Files to Modify

- `.claude/chat/engine.py` â€” add `_load_assistant_commands()`, inject into system_prompt, add
  WebSearch to allowed_tools
- `Memory/scratch.md` â€” remove `## Unsorted` section
- `.claude/scripts/tests/test_chat_engine.py` â€” add tests for new loader and allowed_tools

### Patterns to Follow

**Vault pre-loader pattern** (`engine.py:12â€“26`):
```python
def _load_assistant_commands(project_root: Path) -> str:
    """Pre-load Memory/ASSISTANT.md into system prompt.

    Loaded in Python before the LLM call so Write routing works without
    a Read tool call (Read fails on VPS due to bwrap sandboxing).
    """
    fpath = project_root / "Memory" / "ASSISTANT.md"
    try:
        return fpath.read_text(encoding="utf-8")
    except OSError:
        return ""
```

**System prompt injection** (after the existing `_load_vault_context()` call, engine.py:202â€“203):
```python
assistant_cmds = _load_assistant_commands(self.project_root)
if assistant_cmds:
    system_prompt += f"\n\n{assistant_cmds}"
```

**allowed_tools change** (engine.py:222):
```python
"allowed_tools": ["Read", "Glob", "Grep", "Write", "WebSearch"],
```

**Save format in ASSISTANT.md** (dated heading, append to end of section):
```markdown
## 2026-06-23 [WhatsApp save]
[content]
```

**Test pattern** (mirror `test_handle_message_new_session` in test_chat_engine.py):
- Patch `engine.query` with async generator mock
- Patch `engine._check_and_clear_profile_timeout` â†’ `return False`
- Assert `_load_assistant_commands(PROJECT_ROOT)` returns string
- Assert `"WebSearch"` in `options_kwargs["allowed_tools"]` (capture via patch)

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation â€” ASSISTANT.md manifest

Create the vault file that defines all save command routing. This is the only new file.
Everything else is wired from here.

### Phase 2: Engine changes

Add the loader function and inject into system_prompt. Add WebSearch to allowed_tools.
Two surgical edits to engine.py.

### Phase 3: scratch.md cleanup

Remove the `## Unsorted` section. One Edit call.

### Phase 4: Testing

Add unit tests for `_load_assistant_commands()` and confirm WebSearch is in allowed_tools.
Run full test suite to confirm zero regressions.

### Phase 5: VPS discovery test

Send a live WhatsApp message that triggers a save command. Confirm Write tool fires and
the vault file is updated within the 2-min sync window. If Write is blocked (bwrap),
document the fallback approach (Python direct-write in engine.py).

---

## STEP-BY-STEP TASKS

### Task 1: CREATE `Memory/ASSISTANT.md`

- **IMPLEMENT**: Write the personal assistant command manifest. Must cover: trigger phrases,
  routing table, sub-file routing, save format, confirmation rules, new-entity flow, and the
  hard rule that all writes go to `Memory/` only.
- **CONTENT**:

```markdown
---
title: Assistant Commands
type: system
updated: 2026-06-23
---
# Personal Assistant Command Manifest

This file is loaded into every WhatsApp session. It defines how to handle save commands.
All writes must be to files inside `Memory/` only.

---

## Save & Notes

### Trigger Phrases
- "save this" / "remember this" / "log this" / "note this"
- "save to [entity]" â€” e.g. "save to Juno characters", "save to Simone", "save to scratch"
- "remind me to [X]" â†’ `Memory/scratch.md` Reminders section
- "add to [section]" â€” route as per routing table below

### Routing Table
| Phrase / keyword            | Target                                                   |
|-----------------------------|----------------------------------------------------------|
| "juno" / "wonderdog"        | `Memory/entities/juno-wonderdog/` â€” pick sub-file        |
| "simone" / "kensington"     | `Memory/entities/simone-kensington/` â€” pick sub-file     |
| "investment" / "stocks"     | `Memory/topics/investment-strategy.md`                   |
| "remind me"                 | `Memory/scratch.md` â†’ under `## Reminders`                 |
| no entity named             | `Memory/scratch.md` â†’ under `## Ideas`                     |

### Sub-File Routing (for entity folders)
Pick the sub-file based on content type â€” do not ask Shaun:
- Character descriptions, traits, backstory â†’ `characters.md`
- Plot, narrative, scene ideas, story beats â†’ `story.md`
- General notes, decisions, development log entries â†’ `development.md`
- High-level overview or summary â†’ `index.md`

### Save Format
Append content under a dated heading at the end of the target section:

```
## YYYY-MM-DD [WhatsApp save]
[content verbatim or lightly formatted]
```

Do not overwrite existing content. Always append.

### Confirmation
Always reply with a single short confirmation after saving:
- "Saved to Juno characters."
- "Reminder added to scratch."
- "Saved to investment strategy."

If the destination is genuinely ambiguous (two entities equally likely), ask one clarifying
question before writing. Do not ask if the context makes the destination clear.

### "Save this" â€” Infer from Context
If Shaun says "save this" with no explicit entity, infer the subject from the most recent
exchange in the conversation. If the last topic was Juno, route to Juno development.
If the conversation has no clear subject, route to `Memory/scratch.md` Ideas section, or if in doubt, ask Shaun for clarification.

### New Entity Flow
If Shaun names an entity with no existing folder:
1. Suggest the file path (e.g. "I'll create `Memory/entities/new-entity/index.md` â€” confirm?")
2. Wait for confirmation before writing.
3. On confirm, create the file with a minimal stub and append the content.

---

## Reminders

_(Future section â€” remind me to X commands will route here via scratch.md for now.)_

---

## Email Drafting

_(Future section â€” drafts go to Memory/drafts/active/ with YAML frontmatter.)_

---

## Calendar

_(Future section â€” log-only for now.)_

---

## General Research

_(Future section â€” "look up X and save what you find".)_

---

## Entity Management

_(Future section â€” create/update entity pages from WhatsApp.)_
```

- **GOTCHA**: SOUL.md says "Never modify files outside Memory/". ASSISTANT.md must reinforce
  this within its own text. The Write tool must only target `Memory/` paths.
- **VALIDATE**: `python -c "from pathlib import Path; p = Path('Memory/ASSISTANT.md'); print(p.read_text()[:100])"`

---

### Task 2: ADD `_load_assistant_commands()` to `engine.py`

- **IMPLEMENT**: Add function after `_load_vault_context()` (line 26) and before `_load_profile_context()` (line 29).
- **PATTERN**: Mirror `_load_vault_context()` exactly (engine.py:12â€“26) â€” single file, OSError catch, returns string.
- **IMPORTS**: None new â€” uses only `Path` (already imported).
- **GOTCHA**: Do NOT add a `lines = [...]` header list like `_load_vault_context()` does. ASSISTANT.md
  is a self-contained markdown file with its own headers â€” return raw content only.
- **CODE**:
```python
def _load_assistant_commands(project_root: Path) -> str:
    """Pre-load Memory/ASSISTANT.md into system prompt.

    Loaded in Python before the LLM call so Write routing works without
    a Read tool call (Read fails on VPS due to bwrap sandboxing).
    """
    fpath = project_root / "Memory" / "ASSISTANT.md"
    try:
        return fpath.read_text(encoding="utf-8")
    except OSError:
        return ""
```
- **VALIDATE**: `python -c "import sys; sys.path.insert(0,'.claude/chat'); sys.path.insert(0,'.claude/scripts'); from engine import _load_assistant_commands; from pathlib import Path; print(_load_assistant_commands(Path('.'))[:80])"`

---

### Task 3: INJECT ASSISTANT.md into system_prompt in `engine.py`

- **IMPLEMENT**: In `handle_message()`, after the system_prompt is fully constructed (after
  line 203 â€” the `f"\n\n{_load_vault_context(...)}"` line), append ASSISTANT.md content.
  This must be outside both the `if _is_profile_mode:` and `else:` branches â€” it's always-on.
- **LOCATION**: engine.py between lines 203 and 205. The current block ends at 203 with
  `f"\n\n{_load_vault_context(self.project_root)}"`. Add the injection immediately after
  the closing paren of the system_prompt assignment.
- **CODE** (insert after the system_prompt assignment block):
```python
        assistant_cmds = _load_assistant_commands(self.project_root)
        if assistant_cmds:
            system_prompt += f"\n\n{assistant_cmds}"
```
- **GOTCHA**: The system_prompt is a string literal built with `(` ... `)`. The injection
  must come AFTER the closing `)` of that block, not inside it. Check indentation carefully â€”
  this is inside `handle_message()` (one level of indent).
- **VALIDATE**: `python -c "import sys; sys.path.insert(0,'.claude/chat'); sys.path.insert(0,'.claude/scripts'); from unittest.mock import MagicMock; import engine; print('ok')"`

---

### Task 4: ADD `"WebSearch"` to `allowed_tools` in `engine.py`

- **IMPLEMENT**: In `handle_message()` at line 222, add `"WebSearch"` to the list.
- **LOCATION**: `engine.py:222` â€” `"allowed_tools": ["Read", "Glob", "Grep", "Write"],`
- **CHANGE**:
```python
"allowed_tools": ["Read", "Glob", "Grep", "Write", "WebSearch"],
```
- **WHY IT WORKS**: `codex_sdk_compat.py:148` â€” `_wants_web()` checks if any tool in
  `allowed_tools` is in `_WEB_TOOLS = {"WebSearch", "WebFetch"}`. Adding "WebSearch" causes
  `tools.web_search=true` to be passed to Codex at line 378. Network access is already enabled
  for workspace-write calls (line 382â€“383).
- **GOTCHA**: "WebFetch" is also in `_WEB_TOOLS` but is not needed in `allowed_tools` unless
  explicit URL fetching is wanted. Only add `"WebSearch"` for now.
- **VALIDATE**: `python -c "import sys; sys.path.insert(0,'.claude/chat'); sys.path.insert(0,'.claude/scripts'); from engine import ConversationEngine; print('allowed_tools ok')"`

---

### Task 5: REMOVE `## Unsorted` section from `Memory/scratch.md`

- **IMPLEMENT**: Edit scratch.md â€” remove the `## Unsorted` section and its trailing `---`.
  Keep only: frontmatter, intro paragraph, `## Reminders`, `## Ideas`.
- **CURRENT STATE** (scratch.md): Has `## Reminders`, `## Ideas`, `## Unsorted` (with trailing `---`)
- **RESULT**: File ends after `## Ideas` section with its `---` separator.
- **GOTCHA**: Preserve the final `---` that closes the Ideas section. Only remove the
  Unsorted heading, its content `_(Anything else.)_`, and the final `---` line after it.
- **VALIDATE**: `python -c "from pathlib import Path; t = Path('Memory/scratch.md').read_text(); assert 'Unsorted' not in t; print('ok')"`

---

### Task 6: ADD unit tests to `test_chat_engine.py`

- **IMPLEMENT**: Add 4 new tests after the existing tests. Follow the mock pattern in
  `test_handle_message_new_session` (lines 46â€“80).
- **PATTERN**: `test_chat_engine.py:46â€“80` â€” `patch("engine.query")`, `_make_incoming()`,
  async generator yield pattern.
- **TESTS TO ADD**:

```python
def test_load_assistant_commands_returns_content(tmp_path):
    """_load_assistant_commands returns file content when ASSISTANT.md exists."""
    memory_dir = tmp_path / "Memory"
    memory_dir.mkdir()
    (memory_dir / "ASSISTANT.md").write_text("# Save Commands\nroute here", encoding="utf-8")
    result = engine._load_assistant_commands(tmp_path)
    assert "Save Commands" in result
    assert "route here" in result


def test_load_assistant_commands_missing_returns_empty(tmp_path):
    """_load_assistant_commands returns empty string when ASSISTANT.md is absent."""
    result = engine._load_assistant_commands(tmp_path)
    assert result == ""


@pytest.mark.asyncio
async def test_system_prompt_includes_assistant_commands(engine, store, tmp_path):
    """handle_message injects ASSISTANT.md into system_prompt when file exists."""
    # Plant a sentinel in ASSISTANT.md inside engine's project_root
    memory_dir = engine.project_root / "Memory"
    assistant_file = memory_dir / "ASSISTANT.md"
    original = assistant_file.read_text(encoding="utf-8") if assistant_file.exists() else None

    sentinel = "SENTINEL_SAVE_COMMANDS_TEST"
    assistant_file.write_text(sentinel, encoding="utf-8")

    captured_options = {}

    async def mock_query(prompt, options=None):
        captured_options["system_prompt"] = options.system_prompt if options else ""
        yield MagicMock(**{"__class__.__name__": "ResultMessage",
                           "session_id": "s1", "total_cost_usd": 0.0})

    try:
        with patch("engine._check_and_clear_profile_timeout", return_value=False):
            with patch("engine.query", side_effect=mock_query):
                with patch("engine.ResultMessage"):
                    async for _ in engine.handle_message(_make_incoming("test")):
                        pass
        assert sentinel in captured_options.get("system_prompt", "")
    finally:
        if original is not None:
            assistant_file.write_text(original, encoding="utf-8")
        elif assistant_file.exists():
            assistant_file.unlink()


@pytest.mark.asyncio
async def test_allowed_tools_includes_websearch(engine, store):
    """handle_message passes WebSearch in allowed_tools to the query call."""
    captured_options = {}

    async def mock_query(prompt, options=None):
        captured_options["allowed_tools"] = options.allowed_tools if options else []
        yield MagicMock(**{"__class__.__name__": "ResultMessage",
                           "session_id": "s1", "total_cost_usd": 0.0})

    with patch("engine._check_and_clear_profile_timeout", return_value=False):
        with patch("engine.query", side_effect=mock_query):
            with patch("engine.ResultMessage"):
                async for _ in engine.handle_message(_make_incoming("test")):
                    pass
    assert "WebSearch" in captured_options.get("allowed_tools", [])
    assert "Write" in captured_options.get("allowed_tools", [])
```

- **IMPORTS**: `MagicMock` is already imported at test_chat_engine.py:8. No new imports needed.
- **GOTCHA**: The `test_system_prompt_includes_assistant_commands` test writes to the real
  `engine.project_root` which is the live repo. Use try/finally to restore the original
  file. If the file doesn't exist yet (before Task 1), the test should create a temp one
  and remove it in finally.
- **VALIDATE**: `python -m pytest .claude/scripts/tests/test_chat_engine.py -v`

---

### Task 7: DISCOVERY â€” Test Write tool live on VPS

- **IMPLEMENT**: This is a manual test task, not a code task. After deploying (Task 8),
  send a WhatsApp message that triggers a save. Check if the vault file is updated.
- **TEST MESSAGE**: "save to scratch: Testing Write tool from CarPlay flow"
- **EXPECTED RESULT**: Within 2 minutes, `Memory/scratch.md` should have a new entry under
  `## Ideas` with today's date heading.
- **IF WRITE FAILS** (bwrap permission denied in logs):
  - Check VPS logs: `tail -f .claude/scripts/whatsapp_runs.log`
  - The sandbox is already `workspace-write` (codex_sdk_compat.py:374). If Write still
    fails, the Codex sandbox may be blocking filesystem writes to the vault path.
  - Fallback: add a Python direct-write helper in `engine.py` that the LLM calls via a
    special syntax (e.g. `VAULT_WRITE:path:content`). Document in this plan and
    create a follow-up task.
- **VALIDATE** (run on VPS after deploy):
```bash
tail -20 .claude/scripts/whatsapp_runs.log
python -c "from pathlib import Path; print(Path('Memory/scratch.md').read_text()[-500:])"
```

---

### Task 8: DEPLOY to VPS

- **IMPLEMENT**: Commit all changes, push, deploy via `scripts/deploy.ps1`.
- **COMMIT MESSAGE**: `feat: WhatsApp save commands + WebSearch + ASSISTANT.md manifest`
- **DEPLOY COMMAND**: Use `/commit` skill, then `scripts/deploy.ps1` or the standard deploy flow.
- **PRE-DEPLOY CHECKLIST**:
  - [ ] All tests pass: `python -m pytest .claude/scripts/tests/test_chat_engine.py -v`
  - [ ] ASSISTANT.md exists at `Memory/ASSISTANT.md`
  - [ ] scratch.md has no `## Unsorted` section
  - [ ] engine.py has `_load_assistant_commands()` function
  - [ ] engine.py system_prompt block injects assistant_cmds
  - [ ] `"WebSearch"` in `allowed_tools`
- **VALIDATE**: Check VPS service is running after deploy:
```powershell
ssh secondbrain@137.184.102.104 "sudo systemctl status second-brain-whatsapp.service"
```

---

## TESTING STRATEGY

### Unit Tests

Run after Tasks 1â€“6 before deploy:
```powershell
python -m pytest .claude/scripts/tests/test_chat_engine.py -v
```

Expected: all existing tests pass + 4 new tests pass.

### Integration Tests

Run the full test suite to catch regressions:
```powershell
python -m pytest .claude/scripts/tests/ -v
```

### Edge Cases

- Save with no entity named â†’ routes to scratch.md Ideas
- "remind me to X" â†’ scratch.md Reminders
- "save this" with ambiguous prior context â†’ LLM asks for clarification
- Entity named doesn't exist â†’ LLM suggests path, waits for confirm
- ASSISTANT.md missing from disk â†’ `_load_assistant_commands()` returns `""`, system_prompt unaffected
- WebSearch query during normal chat â†’ Codex gets `tools.web_search=true`

---

## VALIDATION COMMANDS

### Level 1: Syntax

```powershell
# Verify engine.py parses cleanly
python -c "import sys; sys.path.insert(0,'.claude/chat'); sys.path.insert(0,'.claude/scripts'); import engine; print('engine ok')"
```

### Level 2: Unit Tests

```powershell
python -m pytest .claude/scripts/tests/test_chat_engine.py -v
```

### Level 3: Full Test Suite

```powershell
python -m pytest .claude/scripts/tests/ -v
```

### Level 4: Manual VPS Validation

After deploy, send WhatsApp message: `"save to scratch: save command test"`

Check vault updated:
```bash
# On VPS
tail -20 Memory/scratch.md
tail -10 .claude/scripts/whatsapp_runs.log
```

Check WebSearch works:
```
# WhatsApp message:
"What's the current AUD/USD rate?"
```

---

## ACCEPTANCE CRITERIA

- [ ] `Memory/ASSISTANT.md` exists and contains routing table, trigger phrases, save format, confirmation rules
- [ ] `engine.py` has `_load_assistant_commands()` function (after line 26)
- [ ] `engine.py` system_prompt always includes ASSISTANT.md content when file exists
- [ ] `"WebSearch"` in `allowed_tools` in `engine.py:222`
- [ ] `Memory/scratch.md` has no `## Unsorted` section
- [ ] 4 new tests pass in `test_chat_engine.py`
- [ ] Full test suite passes with zero regressions
- [ ] Live VPS test: WhatsApp save command writes to `Memory/scratch.md` within 2 min
- [ ] Live VPS test: WebSearch question returns a real-time answer

---

## COMPLETION CHECKLIST

- [x] Task 1: ASSISTANT.md created
- [x] Task 2: `_load_assistant_commands()` added to engine.py
- [x] Task 3: system_prompt injection added to engine.py
- [x] Task 4: `"WebSearch"` added to `allowed_tools`
- [x] Task 5: `## Unsorted` removed from scratch.md
- [x] Task 6: 7 unit tests added (4 engine + 3 block-secrets) — 265 passing
- [ ] Task 7: VPS Write tool confirmed working (or fallback documented)
- [ ] Task 8: Deployed to VPS, WhatsApp bot restarted
- [ ] All validation commands executed and passing

---

## NOTES

**Why ASSISTANT.md and not hardcoded Python?**
The routing manifest lives in the vault so Shaun can add new entities and commands by editing a
Markdown file, without touching Python code. The LLM handles intent detection naturally â€” no
regex or keyword matching needed in Python.

**WebSearch backend wiring**
Already complete in `codex_sdk_compat.py:145â€“149,377â€“378`. Adding `"WebSearch"` to `allowed_tools`
is the only change needed. The Codex sandbox network access is already enabled for tool-using
calls (line 382â€“383).

**SOUL.md rule: files outside Memory/**
SOUL.md says "Never modify files outside Memory/". Save commands only write to `Memory/` â€” this
is within permitted scope. ASSISTANT.md reinforces this rule explicitly so the LLM doesn't
attempt writes to other directories.

**bwrap on VPS**
Read tool fails under bwrap (confirmed via daily log 2026-06-23:83â€“85). That's why all loaders
use Python pre-reads. Write tool has not been tested yet under the Codex workspace-write sandbox.
Task 7 is the discovery step. If Write is blocked, the fallback is a Python helper in engine.py
that performs the write directly after parsing the LLM's response for a `VAULT_WRITE:path:content`
sentinel â€” but this adds complexity and should only be built if Write actually fails.

**Confidence Score: 8/10**
The implementation is straightforward. The only risk is Task 7 (VPS Write tool) â€” if Codex's
workspace-write sandbox blocks writes to `Memory/`, a fallback needs designing. All other tasks
have clear patterns, confirmed wiring, and zero new dependencies.
