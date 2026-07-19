# Feature: Reflection Tightening and MEMORY.md Bloat Prevention

The following plan should be complete, but validate codebase patterns and task sanity before implementing.

## Feature Description

The nightly reflection process is causing MEMORY.md to bloat over time in two ways:
1. `memory_additions` items (the fallback catch-all bucket) write dated `## YYYY-MM-DD Reflection` sections directly into MEMORY.md — these accumulate without bound.
2. The reflection prompt filtering is too loose, allowing routine email notifications (DocuSign work orders, PayPal confirmations, automated alerts from unknown senders) to land in `active_items`.

MEMORY.md is loaded in full at every session start. Bloat here directly eats into available context tokens for doing actual work. The fix tightens the prompt, eliminates the `memory_additions` dated-section pattern, and adds active item pruning so resolved/stale items are removed rather than just accumulating.

## User Story

As Shaun (second brain owner),
I want reflection to route content precisely and filter aggressively,
So that MEMORY.md stays lean, loads fast, and contains only genuinely actionable open loops.

## Problem Statement

- `memory_additions` is a catch-all fallback that dumps dated sections into MEMORY.md. These never get cleaned up and compound with each reflection run.
- Active items only grow — nothing removes them when they become stale or resolved.
- The reflection prompt has no explicit exclusion rules for spam/notifications, so routine emails surface as "active items" worth tracking.

## Solution Statement

1. **Eliminate `memory_additions` as a MEMORY.md destination** — redirect these to the daily log (where they belong as ephemeral noise) or drop them entirely, unless they inform the second brain about essential data that will help you to better understand Shaun and help you to help him.
2. **Tighten the reflection prompt** — add explicit exclusion rules (notifications, unknown senders, resolved items, transactional emails) and a strict bar for active_items.
3. **Add active item pruning** — in the same LLM call, ask the model to identify which existing active items are now resolved/stale so Python can remove them.
4. **Manual cleanup** — remove existing dated Reflection sections from MEMORY.md and prune spam active items.

## Feature Metadata

**Feature Type**: Enhancement / Bug Fix
**Estimated Complexity**: Low-Medium
**Primary Systems Affected**: `memory_reflect.py`, `test_memory_reflect.py`, `Memory/MEMORY.md`
**Dependencies**: None new — all routing helpers already exist

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `.claude/scripts/memory_reflect.py` (lines 153–161) — `apply_memory_additions`: writes dated `## Reflection` sections to MEMORY.md. This is the primary bloat driver to eliminate.
- `.claude/scripts/memory_reflect.py` (lines 252–274) — `update_memory_active_items`: appends to Active Items section. Needs a paired removal function.
- `.claude/scripts/memory_reflect.py` (lines 339–406) — `reflection_prompt`: where filtering rules live. This is the main text to rewrite.
- `.claude/scripts/memory_reflect.py` (lines 434–498) — `run_reflection` apply block: calls `apply_memory_additions` at line 479. Remove this call or redirect to daily log.
- `.claude/scripts/tests/test_memory_reflect.py` (lines 61–94) — tests for `apply_memory_additions`. These will need updating since the function behavior changes.
- `.claude/scripts/shared.py` — `append_to_daily_log`: use this to redirect memory_additions noise to daily log instead.
- `Memory/MEMORY.md` — current live file. Contains dated Reflection sections (Jun 17, 18, 22, 24) and spam active items to manually prune.

### New Files to Create

None — all changes are to existing files.

### Patterns to Follow

**Prompt structure**: The existing reflection prompt structure (JSON output with routing keys) is correct. Only the filtering rules and `memory_additions` routing guidance need to change.

**Routing helpers already exist**: `append_to_entity_page`, `append_to_topic_page`, `append_to_profile_file`, `archive_decision`, `update_memory_active_items`, `update_memory_preferences` — all work correctly. Do not change them.

**Test pattern**: Use `monkeypatch.setattr(memory_reflect, "MEMORY_FILE", mem_file)` for all file-path patching. Follow this pattern for any new test.

**`append_to_daily_log`** is already imported in `memory_reflect.py` via `from shared import append_to_daily_log`. Use it as the redirect destination for demoted `memory_additions` content.

---

## IMPLEMENTATION PLAN

### Phase 1: Add active item pruning function

Add `remove_memory_active_items(items_to_remove: list[str]) -> bool` to `memory_reflect.py`. It reads the Active Items section, removes lines matching the provided strings (substring match), and writes back atomically.

### Phase 2: Rewrite the reflection prompt

Update `reflection_prompt` in `run_reflection()` with:
- Strict active_items bar: only items requiring multi-session follow-up tied to a named business/project/person already in the vault
- Explicit exclusion list: DocuSign, PayPal, automated alerts, unknown senders, newsletters, one-time admin tasks, anything already resolved
- New `resolved_items` key: list of substrings from existing active items that can now be removed
- Remove `memory_additions` from the routing guidance entirely (or describe it as "use daily_log_only for noise, not MEMORY.md")
- Add `daily_log_only` key: items the model wants to note but don't warrant MEMORY.md space

### Phase 3: Update `run_reflection` apply block

- Call `remove_memory_active_items(parsed["resolved_items"])` before adding new active items
- Replace the `apply_memory_additions` call with `append_to_daily_log` for any `memory_additions` content (or just drop it)
- Add `daily_log_only` handling: append these to daily log if non-empty

### Phase 4: Update tests

- Update `test_apply_memory_additions_*` tests — the function still exists but now redirects to daily log rather than writing MEMORY.md sections
- Add `test_remove_memory_active_items_*` tests
- Add a test for the new prompt schema (`resolved_items`, `daily_log_only` keys)

### Phase 5: Manual MEMORY.md cleanup

Remove existing dated Reflection sections and prune spam active items directly.

### Phase 6: Deploy to VPS

---

## STEP-BY-STEP TASKS

### Task 1: ADD `remove_memory_active_items` to `memory_reflect.py`

- **ADD** after `update_memory_preferences` (around line 293):
```python
def remove_memory_active_items(items_to_remove: list[str]) -> bool:
    """Remove resolved active items from MEMORY.md Active Items section.
    Matches by substring — each entry in items_to_remove is a unique fragment of the line to remove.
    Returns True if any lines were removed."""
    if not items_to_remove or not MEMORY_FILE.exists():
        return False
    with file_lock(MEMORY_FILE):
        current = MEMORY_FILE.read_text(encoding="utf-8")
        lines = current.splitlines(keepends=True)
        new_lines = []
        removed = 0
        for line in lines:
            if any(fragment.lower() in line.lower() for fragment in items_to_remove):
                removed += 1
            else:
                new_lines.append(line)
        if removed == 0:
            return False
        atomic_write(MEMORY_FILE, "".join(new_lines))
    return True
```
- **VALIDATE**: `python -c "from memory_reflect import remove_memory_active_items; print('ok')"`

### Task 2: Update `parse_reflection_response` to include new keys

- **UPDATE** `.claude/scripts/memory_reflect.py` lines 136–150
- **ADD** two new keys to the returned dict:
  - `"resolved_items": data.get("resolved_items") or []` — substrings of active items to remove
  - `"daily_log_only": data.get("daily_log_only") or []` — noise items for daily log only
- **VALIDATE**: existing `test_parse_full_new_schema` still passes (new keys default to `[]`)

### Task 3: Rewrite `reflection_prompt` in `run_reflection()`

- **UPDATE** `.claude/scripts/memory_reflect.py` lines 339–406
- **REPLACE** the `## Output Format` JSON block with the new schema (add `resolved_items`, `daily_log_only`)
- **REPLACE** the `## Routing Rules` section with the tightened rules below

New routing rules to use (replace the existing block verbatim):

```
## Routing Rules

### active_items — STRICT BAR
Only add if ALL of the following are true:
  1. Requires action that cannot be completed in a single session
  2. Relates to a named business, project, or person already tracked in the vault
  3. Is NOT a routine notification, automated alert, or transactional email
Target: under 20 total active items. Quality over quantity.

### NEVER add to active_items:
  - DocuSign / e-signature notifications
  - PayPal / Stripe / bank transaction emails
  - Automated security alerts (password change, login notification) unless the account is actively compromised
  - Newsletters, subscription emails, marketing
  - Emails from senders not already tracked as a contact or entity
  - Items that can be handled in a single sitting
  - Items already present in Current MEMORY.md

### resolved_items
List substrings (unique fragments) of existing active items in Current MEMORY.md that are now
clearly resolved, stale (>14 days old with no follow-up), or irrelevant. Python will remove
lines containing these substrings. Be conservative — only include items you are confident are done.

### daily_log_only
Items worth noting briefly but not worth tracking across sessions. These go to the daily log.
Use for: routine email follow-ups, one-off admin tasks, transactional notifications.

### entity_updates
"page" must be a stem from the Existing Entity Pages list. Facts about named businesses, people, venues.

### topic_updates
"page" must be a stem from the Existing Topic Pages list. Investment notes, growth strategy, etc.

### new_entity_pages / new_topic_pages
Only suggest if name appears in 3+ Memory/ files already.

### profile_updates
Personal statements about values, goals, health, relationships, finances.
"file" must be one of: values, goals, history, personality, health, relationships, finances.
Profile/ files are permanent — never suggest archiving or summarising.

### decision_archive
Only for COMPLETED decisions — no future action needed.

### memory_preferences
Standing communication or tool preferences only.

### memory_additions — REDIRECT, DO NOT USE FOR MEMORY.md
This key is deprecated as a MEMORY.md destination. If you have items that don't fit the above
categories, put them in daily_log_only instead. memory_additions is ignored.

### nothing_to_update
Set true with all empty lists if the log contains nothing worth promoting.

### General
- Do NOT add anything already present in Current MEMORY.md or Current USER.md
- NEVER include SOUL.md content or personality edits
- Keep each item under 120 chars
- When in doubt, use daily_log_only or nothing_to_update — prefer a lean MEMORY.md
```

- **VALIDATE**: Prompt contains `resolved_items`, `daily_log_only`, explicit exclusion list, and no mention of `memory_additions` as a MEMORY.md destination.

### Task 4: Update `run_reflection` apply block

- **UPDATE** `.claude/scripts/memory_reflect.py` lines 442–498
- **ADD** before `update_memory_active_items` call:
  ```python
  # Prune resolved/stale active items first
  wrote_pruned = remove_memory_active_items(parsed.get("resolved_items", []))
  ```
- **REPLACE** the `apply_memory_additions` call (line 479) with:
  ```python
  # memory_additions deprecated as MEMORY.md destination — redirect noise to daily log
  all_noise = parsed["memory_additions"] + parsed.get("daily_log_only", [])
  if all_noise:
      append_to_daily_log("[Reflection noise]\n" + "\n".join(all_noise))
  wrote_memory = False  # no longer writes to MEMORY.md
  ```
- **UPDATE** `wrote_any` to include `wrote_pruned`
- **VALIDATE**: `python .claude/scripts/memory_reflect.py --dry-run` exits cleanly

### Task 5: Update `test_memory_reflect.py`

- **UPDATE** `test_apply_memory_additions_writes_section` — it currently asserts `## 2026-06-17 Reflection` appears in MEMORY.md. This behavior is now removed. Update to assert the function returns True but MEMORY.md does NOT get a dated section. (The function itself can still exist for backward compat but behaviour changes, OR mark it as deprecated and skip the test.)
  - Simplest approach: keep `apply_memory_additions` intact, but add a test that `run_reflection` no longer calls it with MEMORY.md content.
  - Alternatively: update the assertion to check it does NOT write to MEMORY.md.

- **ADD** `test_remove_memory_active_items_removes_matching_line`:
```python
def test_remove_memory_active_items_removes_matching_line(tmp_path, monkeypatch):
    import memory_reflect
    mem_file = tmp_path / "MEMORY.md"
    mem_file.write_text(
        "# Memory\n\n## Active Items\n\n- (Jun 17) DocuSign work order\n- (Jun 18) real item\n\n## Preferences\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(memory_reflect, "MEMORY_FILE", mem_file)
    result = memory_reflect.remove_memory_active_items(["DocuSign work order"])
    assert result is True
    content = mem_file.read_text(encoding="utf-8")
    assert "DocuSign work order" not in content
    assert "real item" in content
```

- **ADD** `test_remove_memory_active_items_no_match_returns_false`:
```python
def test_remove_memory_active_items_no_match_returns_false(tmp_path, monkeypatch):
    import memory_reflect
    mem_file = tmp_path / "MEMORY.md"
    mem_file.write_text("# Memory\n\n## Active Items\n\n- (Jun 17) real item\n", encoding="utf-8")
    monkeypatch.setattr(memory_reflect, "MEMORY_FILE", mem_file)
    result = memory_reflect.remove_memory_active_items(["nonexistent fragment"])
    assert result is False
    assert "real item" in mem_file.read_text(encoding="utf-8")
```

- **ADD** `test_parse_includes_resolved_items_and_daily_log_only`:
```python
def test_parse_includes_resolved_items_and_daily_log_only():
    payload = {
        "active_items": [],
        "resolved_items": ["DocuSign work order"],
        "daily_log_only": ["- PayPal receipt noted"],
        "nothing_to_update": False,
    }
    result = parse_reflection_response(json.dumps(payload))
    assert result["resolved_items"] == ["DocuSign work order"]
    assert result["daily_log_only"] == ["- PayPal receipt noted"]
```

- **VALIDATE**: `cd .claude/scripts && uv run pytest tests/test_memory_reflect.py -v`

### Task 6: Manual cleanup of `Memory/MEMORY.md`

- **REMOVE** the following dated Reflection sections from `Memory/MEMORY.md` (they are pure noise, already represented in daily logs):
  - `## 2026-06-17 Reflection` block and all its bullets
  - `## 2026-06-18 Reflection` block and all its bullets
  - `## 2026-06-22 Reflection` block and all its bullets
  - `## 2026-06-24 Reflection` block and all its bullets

- **REMOVE** from Active Items — confirmed spam/noise:
  - `(Jun 25) Open completed DocuSign work order from murray@solomonsreynella.com.au and confirm details`
  - Review and prune any other items clearly resolved or transactional

- **VALIDATE**: Line count of `Memory/MEMORY.md` is under 100 lines after cleanup.

### Task 7: Run full test suite

- **VALIDATE**: `cd .claude/scripts && uv run pytest -v`
- All 155+ tests must pass. Note any failures and fix before deploying.

### Task 8: Commit and deploy to VPS

- **VALIDATE pre-commit**: `cd .claude/scripts && uv run pytest -v` green
- **COMMIT**: `git add .claude/scripts/memory_reflect.py .claude/scripts/tests/test_memory_reflect.py Memory/MEMORY.md`
- **COMMIT MESSAGE**: `fix: tighten reflection prompt, eliminate memory_additions bloat, add active item pruning`
- **DEPLOY**: Run `scripts/deploy.ps1` or follow established deploy workflow
- **VALIDATE on VPS**: `uv run python memory_reflect.py --dry-run` — exits cleanly
- **VALIDATE on VPS**: `uv run python memory_reflect.py --force` — runs reflection, check MEMORY.md has no new dated section

---

## TESTING STRATEGY

### Unit Tests

All in `tests/test_memory_reflect.py`. Use `tmp_path` + `monkeypatch.setattr` for file paths. No live LLM calls.

### Edge Cases

- `remove_memory_active_items` with empty list → returns False, no file write
- `remove_memory_active_items` with fragment that matches nothing → returns False
- `remove_memory_active_items` with fragment matching multiple lines → removes all matches (acceptable)
- `parse_reflection_response` with old schema (no `resolved_items`) → defaults to `[]`, no crash
- `daily_log_only` items land in daily log, not MEMORY.md

---

## VALIDATION COMMANDS

### Level 1: Syntax
```powershell
cd .claude/scripts
uv run python -c "import memory_reflect; print('import ok')"
```

### Level 2: Unit Tests
```powershell
cd .claude/scripts
uv run pytest tests/test_memory_reflect.py -v
```

### Level 3: Full Suite (no regressions)
```powershell
cd .claude/scripts
uv run pytest -v
```

### Level 4: Dry run
```powershell
python .claude/scripts/memory_reflect.py --dry-run
```

### Level 5: Forced reflection run (local, check MEMORY.md after)
```powershell
python .claude/scripts/memory_reflect.py --force
# Then verify Memory/MEMORY.md has no new ## YYYY-MM-DD Reflection section
```

---

## ACCEPTANCE CRITERIA

- [ ] `Memory/MEMORY.md` contains NO dated `## YYYY-MM-DD Reflection` sections after cleanup
- [ ] Active Items section in `Memory/MEMORY.md` contains no spam/notification items
- [ ] `memory_additions` no longer writes to `MEMORY.md` — noise goes to daily log
- [ ] `resolved_items` key exists in reflection prompt and `parse_reflection_response`
- [ ] `remove_memory_active_items()` function exists and is tested
- [ ] All existing tests pass (no regressions in 155+ tests)
- [ ] New tests for `remove_memory_active_items` and new schema keys pass
- [ ] `memory_reflect.py --force` on VPS produces no dated section in MEMORY.md
- [ ] MEMORY.md remains under 120 lines after a fresh reflection run

---

## NOTES

**Why not change `apply_memory_additions` itself?** The function is tested and working. The fix is to stop calling it for MEMORY.md content in `run_reflection` — backward compat tests can stay, just update the assertion about what ends up where.

**`resolved_items` matching strategy**: Substring match is intentional. Active items are natural language bullets with dates; exact match is too fragile. The LLM is instructed to provide unique-enough fragments. If a false-positive removal is a concern, make matching case-sensitive (default in the implementation above is case-insensitive).

**Deploy workflow reminder**: Per memory — `/commit` auto-pushes and deploys to VPS; heartbeat pauses during deploy.

**Confidence score: 9/10** — the routing infrastructure already exists and works. The changes are targeted: one new function, one prompt rewrite, one apply-block change, test additions, and manual file cleanup. Low risk of regression.
